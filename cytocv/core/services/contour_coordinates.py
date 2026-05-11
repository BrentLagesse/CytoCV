"""Helpers for contour center coordinates in full-image space."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from core.scale import normalize_spatial_stats_unit, parse_microns_per_pixel


CONTOUR_CENTER_SCHEMA_VERSION = 1
CONTOUR_CENTER_ORIGIN = "main_image_bottom_left"
CONTOUR_CENTER_METHOD = "filled_mask_geometric_centroid"

BLUE_CONTOUR_PREFIX = "blue_contour"
RED_CONTOUR_PREFIXES = tuple(f"red_contour_{idx}" for idx in range(1, 4))
GREEN_CONTOUR_PREFIXES = tuple(f"green_contour_{idx}" for idx in range(1, 4))
RED_GREEN_CONTOUR_PREFIXES = (*RED_CONTOUR_PREFIXES, *GREEN_CONTOUR_PREFIXES)
ALL_CONTOUR_PREFIXES = (BLUE_CONTOUR_PREFIX, *RED_GREEN_CONTOUR_PREFIXES)

CONTOUR_CENTER_FIELDS = tuple(
    f"{prefix}_center_xy" for prefix in ALL_CONTOUR_PREFIXES
)


def center_field_name(contour_prefix: str) -> str:
    """Return the public table/payload field name for a contour prefix."""

    return f"{contour_prefix}_center_xy"


def center_axis_key(contour_prefix: str, axis: str) -> str:
    """Return the property key for a raw contour-center axis."""

    normalized_axis = str(axis).strip().lower()
    if normalized_axis not in {"x", "y"}:
        raise ValueError("axis must be 'x' or 'y'")
    return f"{contour_prefix}_center_{normalized_axis}_px"


def _finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def normalize_crop_origin(
    crop_origin: tuple[Any, Any] | list[Any] | Mapping[str, Any] | None,
) -> tuple[float, float]:
    """Return crop origin as ``(top_px, left_px)`` with safe defaults."""

    if isinstance(crop_origin, Mapping):
        top = _finite_float(crop_origin.get("top", crop_origin.get("crop_top_px")))
        left = _finite_float(crop_origin.get("left", crop_origin.get("crop_left_px")))
    elif isinstance(crop_origin, (tuple, list)) and len(crop_origin) >= 2:
        top = _finite_float(crop_origin[0])
        left = _finite_float(crop_origin[1])
    else:
        top = None
        left = None
    return top or 0.0, left or 0.0


def normalize_image_shape(
    image_shape: tuple[Any, ...] | list[Any] | None,
    *,
    fallback_shape: tuple[Any, ...] | list[Any] | None = None,
) -> tuple[int, int]:
    """Return image shape as ``(height, width)``."""

    source = image_shape if image_shape is not None else fallback_shape
    if not isinstance(source, (tuple, list)) or len(source) < 2:
        return 0, 0
    height = _finite_float(source[0])
    width = _finite_float(source[1])
    if height is None or width is None:
        return 0, 0
    return max(int(height), 0), max(int(width), 0)


def transform_local_center_to_main_bottom_left(
    center: tuple[Any, Any] | list[Any] | None,
    *,
    crop_top_px: Any,
    crop_left_px: Any,
    main_image_height_px: Any,
    main_image_width_px: Any | None = None,
) -> tuple[float, float] | None:
    """Convert a crop-local top-left center to full-image bottom-left pixels."""

    if not isinstance(center, (tuple, list)) or len(center) < 2:
        return None
    local_x = _finite_float(center[0])
    local_y = _finite_float(center[1])
    crop_top = _finite_float(crop_top_px)
    crop_left = _finite_float(crop_left_px)
    main_height = _finite_float(main_image_height_px)
    main_width = _finite_float(main_image_width_px)
    if local_x is None or local_y is None or crop_top is None or crop_left is None:
        return None
    if main_height is None or main_height <= 0:
        return None

    x_px = crop_left + local_x
    y_px = main_height - 1.0 - (crop_top + local_y)
    if main_width is not None and main_width > 0 and not (0.0 <= x_px <= main_width - 1.0):
        return None
    if not (0.0 <= y_px <= main_height - 1.0):
        return None
    return float(x_px), float(y_px)


def build_contour_center_context(
    *,
    crop_origin: tuple[Any, Any] | list[Any] | Mapping[str, Any] | None = None,
    main_image_shape: tuple[Any, ...] | list[Any] | None = None,
    fallback_shape: tuple[Any, ...] | list[Any] | None = None,
) -> dict[str, float | int | str]:
    """Build normalized context used when storing contour centers."""

    crop_top, crop_left = normalize_crop_origin(crop_origin)
    main_height, main_width = normalize_image_shape(
        main_image_shape,
        fallback_shape=fallback_shape,
    )
    return {
        "schema_version": CONTOUR_CENTER_SCHEMA_VERSION,
        "origin": CONTOUR_CENTER_ORIGIN,
        "method": CONTOUR_CENTER_METHOD,
        "crop_top_px": float(crop_top),
        "crop_left_px": float(crop_left),
        "main_image_height_px": int(main_height),
        "main_image_width_px": int(main_width),
    }


def apply_contour_center_context(
    properties: Mapping[str, Any] | None,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Return properties with contour-coordinate metadata set."""

    updated = dict(properties or {})
    updated["contour_center_schema_version"] = CONTOUR_CENTER_SCHEMA_VERSION
    updated["contour_center_origin"] = CONTOUR_CENTER_ORIGIN
    updated["contour_center_method"] = CONTOUR_CENTER_METHOD
    updated["contour_center_crop_top_px"] = context.get("crop_top_px", 0.0)
    updated["contour_center_crop_left_px"] = context.get("crop_left_px", 0.0)
    updated["contour_center_main_image_height_px"] = context.get(
        "main_image_height_px",
        0,
    )
    updated["contour_center_main_image_width_px"] = context.get(
        "main_image_width_px",
        0,
    )
    return updated


def contour_center_context_from_properties(
    properties: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return stored contour-coordinate context from properties."""

    props = properties or {}
    return {
        "crop_top_px": props.get("contour_center_crop_top_px", 0.0),
        "crop_left_px": props.get("contour_center_crop_left_px", 0.0),
        "main_image_height_px": props.get("contour_center_main_image_height_px", 0),
        "main_image_width_px": props.get("contour_center_main_image_width_px", 0),
    }


def clear_contour_center_properties(
    properties: Mapping[str, Any] | None,
    prefixes: tuple[str, ...] = ALL_CONTOUR_PREFIXES,
) -> dict[str, Any]:
    """Return properties with stored center values removed for given prefixes."""

    updated = dict(properties or {})
    for prefix in prefixes:
        updated.pop(center_axis_key(prefix, "x"), None)
        updated.pop(center_axis_key(prefix, "y"), None)
    return updated


def store_contour_center(
    properties: Mapping[str, Any] | None,
    contour_prefix: str,
    local_center: tuple[Any, Any] | list[Any] | None,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Return properties with one contour center stored in full-image pixels."""

    updated = dict(properties or {})
    transformed = transform_local_center_to_main_bottom_left(
        local_center,
        crop_top_px=context.get("crop_top_px", 0.0),
        crop_left_px=context.get("crop_left_px", 0.0),
        main_image_height_px=context.get("main_image_height_px", 0),
        main_image_width_px=context.get("main_image_width_px", 0),
    )
    if transformed is None:
        updated.pop(center_axis_key(contour_prefix, "x"), None)
        updated.pop(center_axis_key(contour_prefix, "y"), None)
        return updated
    x_px, y_px = transformed
    updated[center_axis_key(contour_prefix, "x")] = x_px
    updated[center_axis_key(contour_prefix, "y")] = y_px
    return updated


def store_contour_slot_centers(
    properties: Mapping[str, Any] | None,
    contour_prefixes: tuple[str, ...],
    slots,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Store centers for ranked contour slots and clear missing slot values."""

    updated = clear_contour_center_properties(properties, contour_prefixes)
    for prefix, slot in zip(contour_prefixes, slots):
        updated = store_contour_center(
            updated,
            prefix,
            getattr(slot, "center", None),
            context,
        )
    return updated


def contour_center_from_properties(
    properties: Mapping[str, Any] | None,
    contour_prefix: str,
) -> dict[str, float] | None:
    """Return one raw contour-center payload from stored properties."""

    props = properties or {}
    x_px = _finite_float(props.get(center_axis_key(contour_prefix, "x")))
    y_px = _finite_float(props.get(center_axis_key(contour_prefix, "y")))
    if x_px is None or y_px is None:
        return None
    return {"x_px": x_px, "y_px": y_px}


def contour_center_payloads_from_properties(
    properties: Mapping[str, Any] | None,
    prefixes: tuple[str, ...] = ALL_CONTOUR_PREFIXES,
) -> dict[str, dict[str, float] | None]:
    """Return public serialized center fields for all requested prefixes."""

    return {
        center_field_name(prefix): contour_center_from_properties(properties, prefix)
        for prefix in prefixes
    }


def format_contour_center_payload(
    payload: Mapping[str, Any] | None,
    *,
    unit: Any,
    x_um_per_px: Any,
    y_um_per_px: Any,
) -> str:
    """Format a serialized center as a compact ``x, y`` display value."""

    if not isinstance(payload, Mapping):
        return "N/A"
    x_px = _finite_float(payload.get("x_px"))
    y_px = _finite_float(payload.get("y_px"))
    if x_px is None or y_px is None:
        return "N/A"
    if normalize_spatial_stats_unit(unit, default="px") == "um":
        x_px *= parse_microns_per_pixel(x_um_per_px)
        y_px *= parse_microns_per_pixel(y_um_per_px)
    return f"{x_px:0.3f}, {y_px:0.3f}"


def format_contour_center_from_properties(
    properties: Mapping[str, Any] | None,
    contour_prefix: str,
    *,
    unit: Any,
    x_um_per_px: Any,
    y_um_per_px: Any,
) -> str:
    """Format one stored contour center from model properties."""

    return format_contour_center_payload(
        contour_center_from_properties(properties, contour_prefix),
        unit=unit,
        x_um_per_px=x_um_per_px,
        y_um_per_px=y_um_per_px,
    )
