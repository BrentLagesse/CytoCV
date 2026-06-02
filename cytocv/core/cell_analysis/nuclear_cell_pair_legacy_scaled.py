"""Hybrid legacy-scaled measurement helpers for Nuclear Cell Pair intensity.

This compatibility path keeps CytoCV's modern channel identity, canonical
contours, cell-pair mask, and nucleus clipping. It only switches the intensity
pixel source to the YeastAnalysisTool-style 8-bit display-scaled crop.
"""

from __future__ import annotations

from typing import Any

import numpy as np


LEGACY_SCALED_MEASUREMENT_MODE = "legacy_scaled_cytocv_masks"
LEGACY_EXACT_CELL_PAIR_MASK_KEY = "legacy_exact_cell_pair_mask"


def truthy_legacy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def legacy_scaled_measurement_keys(mode: str) -> tuple[str, ...]:
    """Return the processed 8-bit measurement keys for the selected NCP mode."""

    if mode == "red_nucleus":
        return ("green_no_bg",)
    return ("red_no_bg",)


def apply_legacy_scaled_provenance(props: dict[str, Any]) -> dict[str, Any]:
    """Annotate results that measured from legacy-scaled pixels."""

    props["nuclear_cell_pair_measurement_mode"] = LEGACY_SCALED_MEASUREMENT_MODE
    props["intensity_pixel_source"] = "legacy_scaled_8bit_crop"
    props["intensity_display_scaled"] = True
    props["intensity_background_subtracted"] = True
    props["legacy_preserves_channel_identity"] = True
    props["legacy_preserves_cytocv_cell_mask"] = True
    props["legacy_preserves_cytocv_contours"] = True
    props["legacy_copies_yat_channel_collision"] = False
    props["legacy_copies_yat_outline_summing"] = False
    props["legacy_copies_yat_contour_selection"] = False
    return props


def select_legacy_exact_cell_pair_mask(
    contours_data: dict[str, Any],
    fallback_mask: np.ndarray,
    shape: tuple[int, int],
) -> tuple[np.ndarray, bool]:
    """Return a valid exact label-pixel cell-pair mask or the current fallback.

    The exact label-pixel mask exists only for the hybrid legacy mode. It matches
    YeastAnalysisTool's cell-pair summing support more closely while keeping
    CytoCV's modern nucleus contours and channel identity.
    """

    candidate = contours_data.get(LEGACY_EXACT_CELL_PAIR_MASK_KEY)
    if candidate is None:
        return fallback_mask, True
    mask = np.asarray(candidate)
    if mask.shape[:2] != shape:
        return fallback_mask, True
    if mask.ndim == 3:
        mask = mask[:, :, 0]
    mask = np.where(mask > 0, 255, 0).astype(np.uint8)
    if not np.any(mask):
        return fallback_mask, True
    return mask, False


def apply_legacy_cell_pair_mask_provenance(
    props: dict[str, Any],
    *,
    fallback_used: bool,
) -> dict[str, Any]:
    """Annotate the cell-pair pixel support used by hybrid legacy mode."""

    props["legacy_cell_pair_pixel_support"] = (
        "filled_cytocv_cell_mask_fallback"
        if fallback_used
        else "segmentation_label_pixels"
    )
    props["legacy_cell_pair_mask_fallback"] = bool(fallback_used)
    props["legacy_uses_filled_cell_mask"] = bool(fallback_used)
    return props
