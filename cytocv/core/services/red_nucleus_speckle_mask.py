"""Tight Red-speckle nucleus masks for alternate nucleus detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import cv2
import numpy as np
from core.services.nuclear_cell_pair_contour_mode import (
    NUCLEAR_CELL_PAIR_ALTERNATE_RED_MASK_KEY,
)


RED_NUCLEUS_MASK_PAYLOAD_KEY = NUCLEAR_CELL_PAIR_ALTERNATE_RED_MASK_KEY
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


def _masked_values(image: np.ndarray, support: np.ndarray) -> np.ndarray:
    values = image[support > 0]
    return values[np.isfinite(values)]


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


def _otsu_threshold_abs(image: np.ndarray, support: np.ndarray) -> float:
    values = _masked_values(image, support)
    if values.size == 0 or float(np.max(values)) <= 0.0:
        return 0.0
    high = float(np.percentile(values, 99.5))
    if high <= 0.0:
        high = float(np.max(values))
    if high <= 0.0:
        return 0.0
    scaled = np.clip(values * (255.0 / high), 0, 255).astype(np.uint8)
    otsu, _ = cv2.threshold(
        scaled.reshape(-1, 1),
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )
    return float(otsu) * high / 255.0


def _robust_noise_sigma(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    low_band = values[values <= np.percentile(values, 85.0)]
    if low_band.size == 0:
        low_band = values
    median = float(np.median(low_band))
    mad = float(np.median(np.abs(low_band - median)))
    sigma = 1.4826 * mad
    if sigma <= 0.0:
        sigma = float(np.std(low_band))
    return max(sigma, 1.0)


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
    base_contour_mask = contours_to_mask(base_contours, shape, cell_mask=support)

    support_values = _masked_values(gray, support)
    if support_values.size == 0 or not np.any(support):
        return _empty_result(source, cell_mask=support, base_contours=base_contours, reason="empty_cell_mask")

    background = float(np.median(support_values))
    corrected = np.maximum(gray - background, 0.0).astype(np.float32, copy=False)
    corrected = np.where(support > 0, corrected, 0.0).astype(np.float32, copy=False)
    processed = cv2.GaussianBlur(corrected, (3, 3), 0)
    processed = np.where(support > 0, processed, 0.0).astype(np.float32, copy=False)
    values = _masked_values(processed, support)
    max_value = float(np.max(values)) if values.size else 0.0
    if max_value <= 0.0:
        return _empty_result(source, cell_mask=support, base_contours=base_contours, reason="no_red_signal")

    sigma = _robust_noise_sigma(values)
    otsu_threshold = _otsu_threshold_abs(processed, support)
    seed_threshold = max(otsu_threshold, 2.5 * sigma, 0.35 * max_value)
    seed_threshold = min(seed_threshold, 0.85 * max_value)
    support_threshold = max(0.55 * seed_threshold, 1.5 * sigma, 0.12 * max_value)
    support_threshold = min(support_threshold, seed_threshold)

    seed_mask = np.where((processed >= seed_threshold) & (support > 0), 255, 0).astype(np.uint8)
    threshold_mask = np.where((processed >= support_threshold) & (support > 0), 255, 0).astype(np.uint8)
    if not np.any(seed_mask):
        return _empty_result(source, cell_mask=support, base_contours=base_contours, reason="no_seed_pixels")

    accepted = np.zeros(shape, dtype=np.uint8)
    rejected = np.zeros(shape, dtype=np.uint8)
    decisions: list[dict[str, object]] = []
    cell_area = max(int(np.count_nonzero(support)), 1)
    max_component_area = max(int(cell_area * max_component_area_fraction), min_component_area_px)

    count, labels, stats, _ = cv2.connectedComponentsWithStats((threshold_mask > 0).astype(np.uint8), 8)
    ring_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    for label in range(1, count):
        component = np.where(labels == label, 255, 0).astype(np.uint8)
        area = int(stats[label, cv2.CC_STAT_AREA])
        has_seed = bool(np.any(seed_mask[component > 0]))
        component_values = processed[component > 0]
        peak = float(np.max(component_values)) if component_values.size else 0.0
        mean = float(np.mean(component_values)) if component_values.size else 0.0
        ring = cv2.dilate(component, ring_kernel)
        ring = cv2.bitwise_and(ring, support)
        ring[component > 0] = 0
        ring_values = processed[ring > 0]
        ring_p90 = float(np.percentile(ring_values, 90.0)) if ring_values.size else 0.0

        reason = "accepted"
        if not has_seed:
            reason = "no_seed"
        elif area < int(min_component_area_px):
            reason = "too_small"
        elif area > max_component_area:
            reason = "too_large"
        elif ring_p90 > 0.0 and peak < max(ring_p90 + sigma, ring_p90 * 1.25):
            reason = "low_local_contrast"

        if reason == "accepted":
            accepted[component > 0] = 255
        else:
            rejected[component > 0] = 255

        decisions.append(
            {
                "area_px": area,
                "peak": peak,
                "mean": mean,
                "ring_p90": ring_p90,
                "has_seed": has_seed,
                "reason": reason,
            }
        )

    final_mask = cv2.bitwise_and(accepted, support)
    contours, _ = cv2.findContours(final_mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = tuple(contour for contour in contours if contour is not None and len(contour) >= 3)

    metrics = {
        "status": "ok" if contours else "no_accepted_components",
        "background": background,
        "noise_sigma": sigma,
        "otsu_threshold": otsu_threshold,
        "seed_threshold": seed_threshold,
        "support_threshold": support_threshold,
        "component_count": int(count - 1),
        "accepted_component_count": int(sum(1 for item in decisions if item["reason"] == "accepted")),
        "rejected_component_count": int(sum(1 for item in decisions if item["reason"] != "accepted")),
        "final_area_px": int(np.count_nonzero(final_mask)),
        "cell_area_px": cell_area,
        "final_area_fraction": float(np.count_nonzero(final_mask) / cell_area),
        "component_decisions": decisions,
    }

    return RedNucleusSpeckleMaskResult(
        original_image=np.array(source, copy=True),
        processed_image=processed.astype(np.float32, copy=False),
        seed_mask=seed_mask,
        threshold_mask=threshold_mask,
        accepted_components_mask=accepted,
        rejected_components_mask=rejected,
        final_mask=final_mask,
        contours=contours,
        base_contour_mask=base_contour_mask,
        metrics=metrics,
    )

