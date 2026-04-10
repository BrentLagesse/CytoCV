"""Canonical contour-slot helpers for modern Red/Green measurements."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np


CELL_MASK_KEY = "cell_mask"
CANONICAL_RED_SLOTS_KEY = "canonical_red_slots"
CANONICAL_GREEN_SLOTS_KEY = "canonical_green_slots"


@dataclass(slots=True)
class CanonicalContourSlot:
    """Cell-clipped contour slot used consistently across modern statistics."""

    source_index: int
    mask: np.ndarray
    contours: tuple[np.ndarray, ...]
    area: float
    center: tuple[float, float]

    @property
    def center_int(self) -> tuple[int, int]:
        return (int(round(self.center[0])), int(round(self.center[1])))


def load_cell_mask(image_name: str, cell_id: int, output_dir: str, shape: tuple[int, int]) -> np.ndarray:
    """Build the segmented cell mask from the saved outline pixel list."""

    mask = np.zeros(shape, np.uint8)
    outline_filename = os.path.splitext(str(image_name))[0] + f"-{cell_id}.outline"
    mask_file_path = os.path.join(output_dir, "output", outline_filename)
    try:
        with open(mask_file_path, "r", encoding="utf-8") as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                if len(row) < 2:
                    continue
                try:
                    y = int(row[0])
                    x = int(row[1])
                except (TypeError, ValueError):
                    continue
                if 0 <= y < shape[0] and 0 <= x < shape[1]:
                    mask[y, x] = 255
    except FileNotFoundError:
        return mask
    return mask


def _shape_tuple(shape: tuple[int, ...] | Iterable[int]) -> tuple[int, int]:
    values = tuple(int(value) for value in shape)
    if len(values) < 2:
        raise ValueError("Expected at least two dimensions for contour shape")
    return values[0], values[1]


def _full_frame_mask(shape: tuple[int, int]) -> np.ndarray:
    return np.full(shape, 255, dtype=np.uint8)


def _extract_mask_contours(mask: np.ndarray) -> tuple[np.ndarray, ...]:
    contours, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_contours = []
    for contour in contours:
        if contour is None or len(contour) == 0:
            continue
        valid_contours.append(contour)
    return tuple(valid_contours)


def _mask_area_from_contours(contours: tuple[np.ndarray, ...]) -> float:
    return float(sum(cv2.contourArea(contour) for contour in contours))


def _mask_center(mask: np.ndarray) -> tuple[float, float]:
    moment = cv2.moments(mask, binaryImage=True)
    if moment["m00"] != 0:
        return (moment["m10"] / moment["m00"], moment["m01"] / moment["m00"])
    points = np.column_stack(np.nonzero(mask))
    if points.size == 0:
        return (0.0, 0.0)
    # np.nonzero returns rows, cols -> convert to x, y order.
    return (float(np.mean(points[:, 1])), float(np.mean(points[:, 0])))


def build_canonical_contour_slots(
    raw_contours,
    cell_mask: np.ndarray,
    shape: tuple[int, int] | Iterable[int],
    *,
    limit: int = 3,
) -> list[CanonicalContourSlot]:
    """Return ranked, cell-clipped contour slots for a raw contour family."""

    height_width = _shape_tuple(shape)
    slots: list[CanonicalContourSlot] = []
    for source_index, contour in enumerate(raw_contours or []):
        if contour is None or len(contour) < 3:
            continue
        raw_mask = np.zeros(height_width, np.uint8)
        cv2.drawContours(raw_mask, [contour], -1, 255, thickness=-1)
        clipped_mask = cv2.bitwise_and(raw_mask, cell_mask)
        if not np.any(clipped_mask):
            continue
        clipped_contours = _extract_mask_contours(clipped_mask)
        if not clipped_contours:
            continue
        slots.append(
            CanonicalContourSlot(
                source_index=source_index,
                mask=clipped_mask,
                contours=clipped_contours,
                area=_mask_area_from_contours(clipped_contours),
                center=_mask_center(clipped_mask),
            )
        )

    slots.sort(key=lambda slot: (-slot.area, slot.center[0], slot.center[1]))
    return slots[:limit]


def build_canonical_contour_payload(
    contours_data: dict,
    *,
    image_name: str,
    cell_id: int,
    output_dir: str,
    shape: tuple[int, int] | Iterable[int],
    limit: int = 3,
) -> dict:
    """Attach canonical contour slots and cell mask to a contour payload."""

    height_width = _shape_tuple(shape)
    payload = dict(contours_data or {})
    cell_mask = load_cell_mask(image_name, cell_id, output_dir, height_width)
    payload[CELL_MASK_KEY] = cell_mask
    payload[CANONICAL_RED_SLOTS_KEY] = build_canonical_contour_slots(
        payload.get("dot_contours", []),
        cell_mask,
        height_width,
        limit=limit,
    )
    payload[CANONICAL_GREEN_SLOTS_KEY] = build_canonical_contour_slots(
        payload.get("contours_green", payload.get("contours_gfp", [])),
        cell_mask,
        height_width,
        limit=limit,
    )
    return payload


def _resolve_cell_mask(contours_data: dict, shape: tuple[int, int] | Iterable[int]) -> np.ndarray:
    height_width = _shape_tuple(shape)
    cell_mask = contours_data.get(CELL_MASK_KEY)
    if isinstance(cell_mask, np.ndarray) and cell_mask.shape[:2] == height_width and np.any(cell_mask):
        return cell_mask
    return _full_frame_mask(height_width)


def get_canonical_red_slots(
    contours_data: dict,
    shape: tuple[int, int] | Iterable[int],
    *,
    limit: int = 3,
) -> list[CanonicalContourSlot]:
    """Return canonical Red contour slots, deriving them locally when absent."""

    slots = contours_data.get(CANONICAL_RED_SLOTS_KEY)
    if slots is not None:
        return list(slots)[:limit]
    return build_canonical_contour_slots(
        contours_data.get("dot_contours", []),
        _resolve_cell_mask(contours_data, shape),
        shape,
        limit=limit,
    )


def get_canonical_green_slots(
    contours_data: dict,
    shape: tuple[int, int] | Iterable[int],
    *,
    limit: int = 3,
) -> list[CanonicalContourSlot]:
    """Return canonical Green contour slots, deriving them locally when absent."""

    slots = contours_data.get(CANONICAL_GREEN_SLOTS_KEY)
    if slots is not None:
        return list(slots)[:limit]
    return build_canonical_contour_slots(
        contours_data.get("contours_green", contours_data.get("contours_gfp", [])),
        _resolve_cell_mask(contours_data, shape),
        shape,
        limit=limit,
    )


def flatten_slot_contours(slots: Iterable[CanonicalContourSlot]) -> list[np.ndarray]:
    """Return a flattened contour list for overlay drawing."""

    contours: list[np.ndarray] = []
    for slot in slots:
        contours.extend(slot.contours)
    return contours
