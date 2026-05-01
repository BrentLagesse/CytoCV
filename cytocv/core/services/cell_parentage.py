"""Mother/daughter cell-pair parentage derived from DIC geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from core.services.neck_split import NeckSplit, compute_side_areas


CELL_PARENTAGE_MODE_BEST_EFFORT = "best_effort"

CELL_PARENTAGE_STATUS_IDENTIFIED = "identified"
CELL_PARENTAGE_STATUS_NOT_IDENTIFIED = "not_identified"

CELL_PARENTAGE_METHOD_NECK_SPLIT = "neck_split"
CELL_PARENTAGE_METHOD_PRINCIPAL_AXIS = "principal_axis_median"
CELL_PARENTAGE_METHOD_NONE = "none"

CELL_PARENTAGE_LABEL_IDENTIFIED = "Mother/Daughter identified"
CELL_PARENTAGE_LABEL_NOT_IDENTIFIED = "Not identified"


def _mask_centroid(mask: np.ndarray | None) -> tuple[int, int] | None:
    if mask is None:
        return None
    binary = (mask > 0).astype(np.uint8)
    if not np.any(binary):
        return None
    moments = cv2.moments(binary, binaryImage=True)
    if moments["m00"] != 0:
        return (
            int(round(moments["m10"] / moments["m00"])),
            int(round(moments["m01"] / moments["m00"])),
        )
    points = np.column_stack(np.nonzero(binary))
    if points.size == 0:
        return None
    return (
        int(round(float(np.mean(points[:, 1])))),
        int(round(float(np.mean(points[:, 0])))),
    )


def _point_payload(point: tuple[int, int] | None) -> list[int] | None:
    if point is None:
        return None
    return [int(point[0]), int(point[1])]


@dataclass(slots=True)
class CellParentageResult:
    """Derived mother/daughter geometry plus serializable metadata."""

    status: str
    method: str
    label: str
    reason: str
    mother_mask: np.ndarray | None = None
    daughter_mask: np.ndarray | None = None
    mother_area_px: int = 0
    daughter_area_px: int = 0
    mother_label_position: tuple[int, int] | None = None
    daughter_label_position: tuple[int, int] | None = None
    has_neck_split: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": CELL_PARENTAGE_MODE_BEST_EFFORT,
            "mode_label": "Best Effort",
            "method": self.method,
            "label": self.label,
            "reason": self.reason,
            "mother_area_px": int(self.mother_area_px),
            "daughter_area_px": int(self.daughter_area_px),
            "mother_label_position": _point_payload(self.mother_label_position),
            "daughter_label_position": _point_payload(self.daughter_label_position),
            "has_neck_split": bool(self.has_neck_split),
        }


def _not_identified_result(
    *,
    method: str = CELL_PARENTAGE_METHOD_NONE,
    reason: str,
    has_neck_split: bool = False,
) -> CellParentageResult:
    return CellParentageResult(
        status=CELL_PARENTAGE_STATUS_NOT_IDENTIFIED,
        method=method,
        label=CELL_PARENTAGE_LABEL_NOT_IDENTIFIED,
        reason=reason,
        has_neck_split=has_neck_split,
    )


def _identified_result(
    *,
    method: str,
    mother_mask: np.ndarray,
    daughter_mask: np.ndarray,
    has_neck_split: bool,
) -> CellParentageResult:
    mother_area = int(np.count_nonzero(mother_mask))
    daughter_area = int(np.count_nonzero(daughter_mask))
    return CellParentageResult(
        status=CELL_PARENTAGE_STATUS_IDENTIFIED,
        method=method,
        label=CELL_PARENTAGE_LABEL_IDENTIFIED,
        reason="ok",
        mother_mask=mother_mask,
        daughter_mask=daughter_mask,
        mother_area_px=mother_area,
        daughter_area_px=daughter_area,
        mother_label_position=_mask_centroid(mother_mask),
        daughter_label_position=_mask_centroid(daughter_mask),
        has_neck_split=has_neck_split,
    )


def _derive_from_neck_split(
    cell_mask: np.ndarray,
    split: NeckSplit | None,
) -> CellParentageResult:
    if split is None:
        return _not_identified_result(
            reason="no_neck_split",
            has_neck_split=False,
        )
    if getattr(split, "status", "ok") != "ok":
        return _not_identified_result(
            reason="neck_split_not_ok",
            has_neck_split=False,
        )
    try:
        _, smaller_px, larger_mask, smaller_mask = compute_side_areas(cell_mask, split)
    except ValueError:
        return _not_identified_result(
            reason="invalid_cell_mask",
            has_neck_split=True,
        )
    if smaller_px <= 0 or not np.any(larger_mask) or not np.any(smaller_mask):
        return _not_identified_result(
            reason="split_did_not_separate_pair",
            has_neck_split=True,
        )
    return _identified_result(
        method=CELL_PARENTAGE_METHOD_NECK_SPLIT,
        mother_mask=larger_mask,
        daughter_mask=smaller_mask,
        has_neck_split=True,
    )


def _split_best_effort_by_principal_axis(
    cell_mask: np.ndarray,
    *,
    has_neck_split: bool,
) -> CellParentageResult:
    points_yx = np.column_stack(np.nonzero(cell_mask > 0))
    if points_yx.shape[0] < 2:
        return _not_identified_result(
            method=CELL_PARENTAGE_METHOD_PRINCIPAL_AXIS,
            reason="too_few_cell_pixels",
            has_neck_split=has_neck_split,
        )

    points_xy = points_yx[:, [1, 0]].astype(np.float64)
    centered = points_xy - np.mean(points_xy, axis=0)
    try:
        covariance = np.cov(centered, rowvar=False)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        principal_axis = eigenvectors[:, int(np.argmax(eigenvalues))]
    except (np.linalg.LinAlgError, ValueError, FloatingPointError):
        principal_axis = np.array([1.0, 0.0], dtype=np.float64)

    norm = float(np.linalg.norm(principal_axis))
    if not np.isfinite(norm) or norm <= 0:
        principal_axis = np.array([1.0, 0.0], dtype=np.float64)
    else:
        principal_axis = principal_axis / norm

    projections = centered @ principal_axis
    finite_projection_mask = np.isfinite(projections)
    if not np.all(finite_projection_mask):
        points_yx = points_yx[finite_projection_mask]
        projections = projections[finite_projection_mask]
    if projections.size < 2:
        return _not_identified_result(
            method=CELL_PARENTAGE_METHOD_PRINCIPAL_AXIS,
            reason="degenerate_projection",
            has_neck_split=has_neck_split,
        )

    threshold = _best_effort_projection_threshold(projections)
    first_side = projections <= threshold
    second_side = ~first_side
    if not np.any(first_side) or not np.any(second_side):
        order = np.argsort(projections, kind="mergesort")
        first_side = np.zeros(projections.shape, dtype=bool)
        first_side[order[: max(1, len(order) // 2)]] = True
        second_side = ~first_side

    if not np.any(first_side) or not np.any(second_side):
        return _not_identified_result(
            method=CELL_PARENTAGE_METHOD_PRINCIPAL_AXIS,
            reason="could_not_divide_pair",
            has_neck_split=has_neck_split,
        )

    mask_a = np.zeros_like(cell_mask, dtype=np.uint8)
    mask_b = np.zeros_like(cell_mask, dtype=np.uint8)
    mask_a[points_yx[first_side, 0], points_yx[first_side, 1]] = 255
    mask_b[points_yx[second_side, 0], points_yx[second_side, 1]] = 255

    area_a = int(np.count_nonzero(mask_a))
    area_b = int(np.count_nonzero(mask_b))
    if area_a <= 0 or area_b <= 0:
        return _not_identified_result(
            method=CELL_PARENTAGE_METHOD_PRINCIPAL_AXIS,
            reason="empty_best_effort_side",
            has_neck_split=has_neck_split,
        )
    if area_a >= area_b:
        mother_mask, daughter_mask = mask_a, mask_b
    else:
        mother_mask, daughter_mask = mask_b, mask_a
    return _identified_result(
        method=CELL_PARENTAGE_METHOD_PRINCIPAL_AXIS,
        mother_mask=mother_mask,
        daughter_mask=daughter_mask,
        has_neck_split=has_neck_split,
    )


def _best_effort_projection_threshold(projections: np.ndarray) -> float:
    """Choose a stable split position along the principal-axis projection."""

    finite = projections[np.isfinite(projections)]
    if finite.size < 2:
        return 0.0

    min_projection = float(np.min(finite))
    max_projection = float(np.max(finite))
    extent = max_projection - min_projection
    midpoint = min_projection + extent / 2.0
    if extent <= 0:
        return midpoint

    # A histogram over the long-axis projection approximates the cell-pair
    # cross-section. When there is a waist between lobes, split at that valley;
    # otherwise fall back to the midpoint of the projected pair extent.
    bin_count = int(min(128, max(16, round(extent) + 1)))
    counts, edges = np.histogram(finite, bins=bin_count, range=(min_projection, max_projection))
    if counts.size < 3 or not np.any(counts):
        return midpoint

    kernel = np.array([1.0, 2.0, 1.0], dtype=np.float64) / 4.0
    smoothed = np.convolve(counts.astype(np.float64), kernel, mode="same")
    central_start = max(1, int(round(0.20 * counts.size)))
    central_end = min(counts.size - 1, int(round(0.80 * counts.size)))
    if central_end <= central_start:
        return midpoint

    central = smoothed[central_start:central_end]
    positive = central > 0
    if not np.any(positive):
        return midpoint

    positive_values = central[positive]
    if (
        float(np.max(positive_values)) - float(np.min(positive_values))
        <= max(2.0, 0.10 * float(np.max(positive_values)))
    ):
        return midpoint

    candidate_offsets = np.flatnonzero(central == np.min(positive_values))
    if candidate_offsets.size == 0:
        return midpoint
    centers = (edges[:-1] + edges[1:]) / 2.0
    candidate_bins = candidate_offsets + central_start
    best_bin = min(candidate_bins, key=lambda idx: abs(float(centers[idx]) - midpoint))
    return float(centers[best_bin])


def derive_cell_parentage(
    cell_mask: np.ndarray | None,
    neck_split: NeckSplit | None,
) -> CellParentageResult:
    """Derive mother/daughter geometry from a DIC pair mask.

    Parentage is always best effort: a clean DIC neck split is used when
    available, otherwise the pair mask is split by principal-axis projection.
    """

    if cell_mask is None or cell_mask.size == 0 or not np.any(cell_mask):
        return _not_identified_result(
            reason="empty_cell_mask",
            has_neck_split=bool(
                neck_split is not None and getattr(neck_split, "status", "ok") == "ok"
            ),
        )

    neck_result = _derive_from_neck_split(cell_mask, neck_split)
    if neck_result.status == CELL_PARENTAGE_STATUS_IDENTIFIED:
        return neck_result
    return _split_best_effort_by_principal_axis(
        cell_mask,
        has_neck_split=neck_result.has_neck_split,
    )


def cell_parentage_payload_from_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    """Return a display payload, deriving a fallback from legacy neck metadata."""

    props = properties or {}
    payload = props.get("cell_parentage")
    if isinstance(payload, dict) and payload.get("status"):
        normalized = dict(payload)
        normalized["mode"] = CELL_PARENTAGE_MODE_BEST_EFFORT
        normalized["mode_label"] = "Best Effort"
        normalized.setdefault("method", CELL_PARENTAGE_METHOD_NONE)
        normalized.setdefault("reason", "missing_reason")
        normalized.setdefault("mother_area_px", 0)
        normalized.setdefault("daughter_area_px", 0)
        normalized.setdefault("mother_label_position", None)
        normalized.setdefault("daughter_label_position", None)
        normalized.setdefault("has_neck_split", False)
        normalized.setdefault(
            "label",
            CELL_PARENTAGE_LABEL_IDENTIFIED
            if normalized.get("status") == CELL_PARENTAGE_STATUS_IDENTIFIED
            else CELL_PARENTAGE_LABEL_NOT_IDENTIFIED,
        )
        return normalized

    neck_payload = props.get("neck_split")
    if isinstance(neck_payload, dict) and neck_payload.get("status") == "ok":
        return {
            "status": CELL_PARENTAGE_STATUS_IDENTIFIED,
            "mode": CELL_PARENTAGE_MODE_BEST_EFFORT,
            "mode_label": "Best Effort",
            "method": CELL_PARENTAGE_METHOD_NECK_SPLIT,
            "label": CELL_PARENTAGE_LABEL_IDENTIFIED,
            "reason": "legacy_neck_split",
            "mother_area_px": int(neck_payload.get("side_area_large_px") or 0),
            "daughter_area_px": int(neck_payload.get("side_area_small_px") or 0),
            "mother_label_position": None,
            "daughter_label_position": None,
            "has_neck_split": True,
        }

    return _not_identified_result(
        reason="missing_parentage",
        has_neck_split=False,
    ).to_payload()
