"""Helpers for toggle-driven measurement/contour ratio output."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


DEFAULT_NUCLEAR_CELL_PAIR_MODE = "green_nucleus"
VALID_NUCLEAR_CELL_PAIR_MODES = frozenset({"green_nucleus", "red_nucleus"})

_MODE_RATIO_CONFIG = {
    "red_nucleus": {
        "pair_label": "Green/Red",
        "formula_text": "Green in Red / Red in Red",
        "numerator_prefix": "green_intensity",
        "denominator_prefix": "red_intensity",
    },
    "green_nucleus": {
        "pair_label": "Red/Green",
        "formula_text": "Red in Green / Green in Green",
        "numerator_prefix": "red_in_green_intensity",
        "denominator_prefix": "green_in_green_intensity",
    },
}


def normalize_nuclear_cell_pair_mode(
    value: str | None,
    default: str = DEFAULT_NUCLEAR_CELL_PAIR_MODE,
) -> str:
    """Return a supported nucleus/cell-pair mode."""
    if value in VALID_NUCLEAR_CELL_PAIR_MODES:
        return str(value)
    return default


def _source_value(source: Any, field_name: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_measurement_contour_ratio_metadata(mode: str | None = None) -> dict[str, str]:
    """Return the public label metadata for the selected ratio mode."""
    normalized_mode = normalize_nuclear_cell_pair_mode(mode)
    config = _MODE_RATIO_CONFIG[normalized_mode]
    pair_label = str(config["pair_label"])
    formula_text = str(config["formula_text"])
    return {
        "mode": normalized_mode,
        "pair_label": pair_label,
        "formula_text": formula_text,
        "display_text": f"{pair_label}: {formula_text}",
    }


def calculate_measurement_contour_ratio_value(
    source: Any,
    index: int,
    *,
    mode: str | None = None,
) -> float:
    """Calculate a single measurement/contour ratio value from raw sums."""
    metadata = get_measurement_contour_ratio_metadata(
        mode if mode is not None else _source_value(source, "nuclear_cell_pair_mode")
    )
    config = _MODE_RATIO_CONFIG[metadata["mode"]]
    numerator = _float_or_zero(
        _source_value(source, f"{config['numerator_prefix']}_{index}")
    )
    denominator = _float_or_zero(
        _source_value(source, f"{config['denominator_prefix']}_{index}")
    )
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def calculate_measurement_contour_ratio_triplet(
    source: Any,
    *,
    mode: str | None = None,
) -> tuple[float, float, float]:
    """Calculate all three measurement/contour ratio slots from raw sums."""
    normalized_mode = mode if mode is not None else _source_value(
        source,
        "nuclear_cell_pair_mode",
    )
    return tuple(
        calculate_measurement_contour_ratio_value(
            source,
            index,
            mode=normalized_mode,
        )
        for index in range(1, 4)
    )


def store_measurement_contour_ratio_triplet(
    target: Any,
    *,
    mode: str | None = None,
) -> tuple[float, float, float]:
    """Persist the derived ratios into the legacy storage fields."""
    ratios = calculate_measurement_contour_ratio_triplet(target, mode=mode)
    for index, value in enumerate(ratios, start=1):
        setattr(target, f"green_red_intensity_{index}", value)
    return ratios


def build_measurement_contour_ratio_payload(
    source: Any,
    *,
    mode: str | None = None,
) -> dict[str, Any]:
    """Expose public ratio keys and labels for display, dashboard, and export."""
    metadata = get_measurement_contour_ratio_metadata(
        mode if mode is not None else _source_value(source, "nuclear_cell_pair_mode")
    )
    ratios = calculate_measurement_contour_ratio_triplet(source, mode=metadata["mode"])
    return {
        "measurement_contour_ratio_1": ratios[0],
        "measurement_contour_ratio_2": ratios[1],
        "measurement_contour_ratio_3": ratios[2],
        "measurement_contour_ratio_pair_label": metadata["pair_label"],
        "measurement_contour_ratio_formula": metadata["formula_text"],
        "measurement_contour_ratio_display_text": metadata["display_text"],
    }


def get_measurement_contour_ratio_headers(mode: str | None = None) -> tuple[str, str, str]:
    """Return the public ratio header triplet for the selected mode."""
    metadata = get_measurement_contour_ratio_metadata(mode)
    pair_label = metadata["pair_label"]
    return tuple(
        f"Measurement/Contour Ratio {index} ({pair_label})"
        for index in range(1, 4)
    )
