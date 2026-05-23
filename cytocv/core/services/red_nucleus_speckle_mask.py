"""Tight Red-speckle nucleus masks for alternate nucleus detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import cv2
import numpy as np


RED_NUCLEUS_MASK_PAYLOAD_KEY = "alternate_nucleus_mask_red"
RED_NUCLEUS_DEBUG_PAYLOAD_KEY = "alternate_nucleus_debug_red"


@dataclass(slots=True)
class RedNucleusSpeckleMaskResult:
    """Intermediate and final masks for explainable alternate Red detection."""

    original_image: np.ndarray
    processed_image: np.ndarray
    seed_mask: np.ndarray
    threshold_mask: np.ndarray
    accepted_components_mask: np.ndarray
    rejected_components_mask: np.ndarray
    final_mask: np.ndarray
    contours: tuple[np.ndarray, ...]
    base_contour_mask: np.ndarray | None = None
    metrics: dict[str, object] = field(default_factory=dict)


def _height_width(image: np.ndarray) -> tuple[int, int]:
    return int(image.shape[0]), int(image.shape[1])


def _as_gray_float(image: np.ndarray | None) -> np.ndarray | None:
    if image is None:
        return None
    array = np.asarray(image)
    if array.ndim == 3:
        array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
    return array.astype(np.float32, copy=False)


def _support_mask(cell_mask: np.ndarray | None, shape: tuple[int, int]) -> np.ndarray:
    if cell_mask is None:
        return np.full(shape, 255, dtype=np.uint8)
    mask = np.asarray(cell_mask)
    if mask.shape[:2] != shape:
        return np.zeros(shape, dtype=np.uint8)
    if mask.ndim == 3:
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    return np.where(mask > 0, 255, 0).astype(np.uint8)


def contours_to_mask(
    contours: Iterable[np.ndarray] | None,
    shape: tuple[int, int],
    *,
    cell_mask: np.ndarray | None = None,
) -> np.ndarray | None:
    """Fill contours into one mask, optionally clipping to the cell support."""

    contours = [
        contour
        for contour in (contours or [])
        if contour is not None and len(contour) >= 3
    ]
    if not contours:
        return None
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.drawContours(mask, contours, -1, 255, thickness=-1)
    support = _support_mask(cell_mask, shape) if cell_mask is not None else None
    if support is not None:
        mask = cv2.bitwise_and(mask, support)
    return mask


def _empty_result(
    image: np.ndarray,
    *,
    cell_mask: np.ndarray | None,
    base_contours: Iterable[np.ndarray] | None,
    reason: str,
) -> RedNucleusSpeckleMaskResult:
    shape = _height_width(image)
    empty = np.zeros(shape, dtype=np.uint8)
    return RedNucleusSpeckleMaskResult(
        original_image=np.array(image, copy=True),
        processed_image=np.zeros(shape, dtype=np.float32),
        seed_mask=empty.copy(),
        threshold_mask=empty.copy(),
        accepted_components_mask=empty.copy(),
        rejected_components_mask=empty.copy(),
        final_mask=empty.copy(),
        contours=(),
        base_contour_mask=contours_to_mask(base_contours, shape, cell_mask=cell_mask),
        metrics={"status": reason, "final_area_px": 0},
    )


def build_red_nucleus_speckle_mask(
    red_image: np.ndarray | None,
    *,
    cell_mask: np.ndarray | None = None,
    original_image: np.ndarray | None = None,
    base_contours: Iterable[np.ndarray] | None = None,
    min_component_area_px: int = 3,
    max_component_area_fraction: float = 0.35,
) -> RedNucleusSpeckleMaskResult:
    """Build a minimal Red-speckle-derived alternate nucleus mask."""

    gray = _as_gray_float(red_image)
    if gray is None:
        placeholder = np.zeros((1, 1), dtype=np.uint8)
        return _empty_result(
            placeholder,
            cell_mask=None,
            base_contours=None,
            reason="missing_red_image",
        )

    shape = _height_width(gray)
    support = _support_mask(cell_mask, shape)
    source = _as_gray_float(original_image)
    if source is None or source.shape[:2] != shape:
        source = gray
    support_values = gray[support > 0]
    support_values = support_values[np.isfinite(support_values)]
    if support_values.size == 0 or not np.any(support):
        return _empty_result(source, cell_mask=support, base_contours=base_contours, reason="empty_cell_mask")

    processed = cv2.GaussianBlur(np.where(support > 0, gray, 0.0).astype(np.float32), (3, 3), 0)
    values = processed[support > 0]
    values = values[np.isfinite(values)]
    max_value = float(np.max(values)) if values.size else 0.0
    if max_value <= 0.0:
        return _empty_result(source, cell_mask=support, base_contours=base_contours, reason="no_red_signal")

    scaled = np.clip(values * (255.0 / max_value), 0, 255).astype(np.uint8)
    otsu, _ = cv2.threshold(scaled.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    threshold_value = max(float(otsu) * max_value / 255.0, 1.0)
    threshold_mask = np.where((processed >= threshold_value) & (support > 0), 255, 0).astype(np.uint8)
    seed_mask = threshold_mask.copy()

    accepted = np.zeros(shape, dtype=np.uint8)
    rejected = np.zeros(shape, dtype=np.uint8)
    cell_area = max(int(np.count_nonzero(support)), 1)
    max_component_area = max(int(cell_area * max_component_area_fraction), min_component_area_px)
    decisions: list[dict[str, object]] = []
    count, labels, stats, _ = cv2.connectedComponentsWithStats((threshold_mask > 0).astype(np.uint8), 8)
    for label in range(1, count):
        component = np.where(labels == label, 255, 0).astype(np.uint8)
        area = int(stats[label, cv2.CC_STAT_AREA])
        reason = "accepted"
        if area < int(min_component_area_px):
            reason = "too_small"
        elif area > max_component_area:
            reason = "too_large"
        if reason == "accepted":
            accepted[component > 0] = 255
        else:
            rejected[component > 0] = 255
        decisions.append({"area_px": area, "reason": reason})

    final_mask = cv2.bitwise_and(accepted, support)
    contours, _ = cv2.findContours(final_mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = tuple(contour for contour in contours if contour is not None and len(contour) >= 3)
    return RedNucleusSpeckleMaskResult(
        original_image=np.array(source, copy=True),
        processed_image=processed.astype(np.float32, copy=False),
        seed_mask=seed_mask,
        threshold_mask=threshold_mask,
        accepted_components_mask=accepted,
        rejected_components_mask=rejected,
        final_mask=final_mask,
        contours=contours,
        base_contour_mask=contours_to_mask(base_contours, shape, cell_mask=support),
        metrics={
            "status": "ok" if contours else "no_accepted_components",
            "threshold": threshold_value,
            "component_count": int(count - 1),
            "accepted_component_count": int(sum(1 for item in decisions if item["reason"] == "accepted")),
            "rejected_component_count": int(sum(1 for item in decisions if item["reason"] != "accepted")),
            "final_area_px": int(np.count_nonzero(final_mask)),
            "cell_area_px": cell_area,
            "component_decisions": decisions,
        },
    )
