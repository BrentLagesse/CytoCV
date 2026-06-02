"""Hybrid legacy-scaled measurement helpers for Nuclear Cell Pair intensity.

This compatibility path keeps CytoCV's modern channel identity, canonical
contours, cell-pair mask, and nucleus clipping. It only switches the intensity
pixel source to the YeastAnalysisTool-style 8-bit display-scaled crop.
"""

from __future__ import annotations

from typing import Any


LEGACY_SCALED_MEASUREMENT_MODE = "legacy_scaled_cytocv_masks"


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
