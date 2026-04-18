"""Detect and persist the internal neck-split line of a connected cell pair.

Phase 1 scope: pure geometry, sidecar persistence, and non-destructive area
computation.
"""

from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from core.artifact_constants import NECK_SPLIT_SUFFIX


# `cv2.convexityDefects` returns depth in fixed-point units where 256 == 1 px.
DEFECT_DEPTH_FIXED_POINT = 256

# Default minimum defect depth to accept (in fixed-point units). ~1 px of
# inward concavity. Looser than a tuned value but rejects contour noise.
DEFAULT_MIN_DEFECT_DEPTH = DEFECT_DEPTH_FIXED_POINT

# Search the top-N deepest defects for a valid cross-lobe chord.
MAX_DEFECT_CANDIDATES = 6

# Number of evenly-spaced samples along the chord used to verify it lies
# inside the pair mask.
CHORD_SAMPLE_COUNT = 20

STATUS_OK = "ok"
STATUS_NO_NECK = "no_neck"
STATUS_MULTI_COMPONENT = "multi_component"

SIDECAR_HEADER = (
    "status",
    "x1",
    "y1",
    "x2",
    "y2",
    "defect_depth_1",
    "defect_depth_2",
)


@dataclass(slots=True)
class NeckSplit:
    """Two absolute-frame endpoints of the internal neck chord."""

    x1: int
    y1: int
    x2: int
    y2: int
    status: str = STATUS_OK
    defect_depth_1: int = 0
    defect_depth_2: int = 0

    @property
    def endpoints(self) -> tuple[tuple[int, int], tuple[int, int]]:
        return (self.x1, self.y1), (self.x2, self.y2)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "NeckSplit":
        return cls(
            x1=int(data["x1"]),
            y1=int(data["y1"]),
            x2=int(data["x2"]),
            y2=int(data["y2"]),
            status=str(data.get("status", STATUS_OK)),
            defect_depth_1=int(data.get("defect_depth_1", 0)),
            defect_depth_2=int(data.get("defect_depth_2", 0)),
        )


def _chord_inside_mask(p1: tuple[int, int], p2: tuple[int, int], mask: np.ndarray) -> bool:
    """Sample the chord and require every interior sample to land on mask."""

    h, w = mask.shape[:2]
    xs = np.linspace(p1[0], p2[0], CHORD_SAMPLE_COUNT)
    ys = np.linspace(p1[1], p2[1], CHORD_SAMPLE_COUNT)
    # Skip the two endpoints (which sit on the contour boundary, not interior).
    for i in range(1, CHORD_SAMPLE_COUNT - 1):
        x = int(round(xs[i]))
        y = int(round(ys[i]))
        if x < 0 or x >= w or y < 0 or y >= h:
            return False
        if not mask[y, x]:
            return False
    return True


def _component_count(pair_mask: np.ndarray) -> int:
    """Number of foreground components in a binary mask."""

    binary = (pair_mask > 0).astype(np.uint8)
    num, _ = cv2.connectedComponents(binary, connectivity=8)
    return max(num - 1, 0)


def detect_neck_split(
    outer_contour: np.ndarray,
    pair_mask: np.ndarray,
    *,
    min_defect_depth: int = DEFAULT_MIN_DEFECT_DEPTH,
) -> Optional[NeckSplit]:
    """Return the chord across the pair's neck, or ``None`` if one is not found.

    Uses `cv2.convexityDefects` on the outer contour: the two deepest defect
    `far` points on opposite sides of the neck form the natural split chord.
    Returns ``None`` when the mask has no usable neck, letting callers
    distinguish "write sidecar" from "skip".
    """

    if outer_contour is None or len(outer_contour) < 4:
        return None
    if pair_mask is None or pair_mask.size == 0:
        return None
    if _component_count(pair_mask) > 1:
        return None

    hull = cv2.convexHull(outer_contour, returnPoints=False)
    if hull is None or len(hull) < 3:
        return None

    # `cv2.convexityDefects` requires hull indices to be in ascending order.
    hull = np.sort(hull.flatten()).reshape(-1, 1)
    try:
        defects = cv2.convexityDefects(outer_contour, hull)
    except cv2.error:
        return None
    if defects is None:
        return None

    candidates = [
        (int(far_idx), int(depth))
        for _start, _end, far_idx, depth in defects[:, 0]
        if int(depth) >= int(min_defect_depth)
    ]
    candidates.sort(key=lambda row: row[1], reverse=True)
    candidates = candidates[:MAX_DEFECT_CANDIDATES]

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            far_i, depth_i = candidates[i]
            far_j, depth_j = candidates[j]
            p1 = tuple(int(v) for v in outer_contour[far_i][0])
            p2 = tuple(int(v) for v in outer_contour[far_j][0])
            if p1 == p2:
                continue
            if not _chord_inside_mask(p1, p2, pair_mask):
                continue
            return NeckSplit(
                x1=p1[0],
                y1=p1[1],
                x2=p2[0],
                y2=p2[1],
                status=STATUS_OK,
                defect_depth_1=depth_i,
                defect_depth_2=depth_j,
            )

    return None


def compute_side_areas(
    pair_mask: np.ndarray,
    split: NeckSplit,
    *,
    line_thickness: int = 2,
) -> tuple[int, int, np.ndarray, np.ndarray]:
    """Compute the two side areas without mutating ``pair_mask``.

    Rasterizes a black chord onto a copy of the mask and runs
    ``cv2.connectedComponents``. Returns ``(larger_px, smaller_px, larger_mask,
    smaller_mask)`` with ``*_mask`` as ``uint8`` 0/255 arrays. If the chord
    does not cleanly separate the mask into two components, returns the full
    mask as ``larger_mask`` and an empty ``smaller_mask``.
    """

    if pair_mask is None or pair_mask.size == 0:
        raise ValueError("pair_mask is empty")
    working = pair_mask.copy()
    cv2.line(
        working,
        (int(split.x1), int(split.y1)),
        (int(split.x2), int(split.y2)),
        0,
        thickness=int(line_thickness),
        lineType=cv2.LINE_8,
    )
    binary = (working > 0).astype(np.uint8)
    num, labels = cv2.connectedComponents(binary, connectivity=8)
    regions: list[tuple[int, np.ndarray]] = []
    for label in range(1, num):
        region = (labels == label).astype(np.uint8) * 255
        regions.append((int(np.count_nonzero(region)), region))
    regions.sort(key=lambda row: row[0], reverse=True)
    if not regions:
        empty = np.zeros_like(pair_mask, dtype=np.uint8)
        return 0, 0, empty, empty.copy()
    if len(regions) == 1:
        larger_px, larger_mask = regions[0]
        empty = np.zeros_like(pair_mask, dtype=np.uint8)
        return larger_px, 0, larger_mask, empty
    larger_px, larger_mask = regions[0]
    smaller_px, smaller_mask = regions[1]
    return larger_px, smaller_px, larger_mask, smaller_mask


def sidecar_path(output_dir: str | os.PathLike, image_name: str, cell_id: int) -> Path:
    """Path to the neck-split sidecar for a given pair."""

    stem = os.path.splitext(str(image_name))[0]
    return Path(output_dir) / "output" / f"{stem}-{int(cell_id)}{NECK_SPLIT_SUFFIX}"


def write_neck_split(path: str | os.PathLike, split: NeckSplit) -> None:
    """Persist a ``NeckSplit`` as a one-row CSV with a header."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(SIDECAR_HEADER)
        writer.writerow(
            [
                split.status,
                int(split.x1),
                int(split.y1),
                int(split.x2),
                int(split.y2),
                int(split.defect_depth_1),
                int(split.defect_depth_2),
            ]
        )


def read_neck_split(path: str | os.PathLike) -> Optional[NeckSplit]:
    """Read a sidecar. Missing file returns ``None``; malformed rows return ``None``."""

    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            rows = [row for row in reader if row]
    except FileNotFoundError:
        return None
    if not rows:
        return None
    data_rows = rows[1:] if rows[0] and rows[0][0] == SIDECAR_HEADER[0] else rows
    if not data_rows:
        return None
    row = data_rows[0]
    if len(row) < 5:
        return None
    try:
        status = str(row[0])
        x1 = int(row[1])
        y1 = int(row[2])
        x2 = int(row[3])
        y2 = int(row[4])
        depth_1 = int(row[5]) if len(row) > 5 else 0
        depth_2 = int(row[6]) if len(row) > 6 else 0
    except (TypeError, ValueError):
        return None
    return NeckSplit(
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        status=status,
        defect_depth_1=depth_1,
        defect_depth_2=depth_2,
    )
