"""Scale metadata normalization and unit-conversion helpers."""

from __future__ import annotations

import math
from typing import Any

DEFAULT_MICRONS_PER_PIXEL = 0.1
MIN_MICRONS_PER_PIXEL = 0.0001
MAX_MICRONS_PER_PIXEL = 10000.0
ANISOTROPY_TOLERANCE = 1e-9
LENGTH_UNITS = {"px", "um"}
SCALE_SOURCES = {"metadata", "manual_global", "manual_override", "manual_fallback"}
SCALE_STATUSES = {"ok", "missing", "invalid", "anisotropic_avg"}

SCALE_SOURCE_LABELS = {
    "metadata": "Metadata",
    "manual_global": "Manual",
    "manual_override": "Manual override",
    "manual_fallback": "Manual fallback",
}

SCALE_STATUS_LABELS = {
    "ok": "OK",
    "missing": "Missing metadata",
    "invalid": "Invalid metadata",
    "anisotropic_avg": "Averaged dx/dy",
}

DISTANCE_MODE_LABELS = {
    "scalar": "Scalar",
    "anisotropic_xy": "Anisotropic XY",
}

SPATIAL_STAT_UNITS = {"px", "um"}


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def normalize_length_unit(value: Any, default: str = "px") -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in LENGTH_UNITS:
        return default
    return normalized


def normalize_spatial_stats_unit(value: Any, default: str = "px") -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in SPATIAL_STAT_UNITS:
        return default
    return normalized


def _as_positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def parse_microns_per_pixel(value: Any, default: float = DEFAULT_MICRONS_PER_PIXEL) -> float:
    parsed = _as_positive_float(value)
    if parsed is None:
        return default
    if parsed < MIN_MICRONS_PER_PIXEL or parsed > MAX_MICRONS_PER_PIXEL:
        return default
    return parsed


def format_scale_value(value: Any, precision: int = 4) -> str:
    parsed = parse_microns_per_pixel(value)
    formatted = f"{parsed:.{precision}f}"
    return formatted.rstrip("0").rstrip(".")


def build_scale_info(
    *,
    manual_um_per_px: Any,
    prefer_metadata: Any,
    metadata_um_per_px: Any = None,
    status: Any = "missing",
    dx: Any = None,
    dy: Any = None,
    dz: Any = None,
    note: Any = "",
) -> dict[str, Any]:
    """Build a normalized scale payload from run defaults and metadata output."""

    manual_value = parse_microns_per_pixel(manual_um_per_px)
    metadata_value = _as_positive_float(metadata_um_per_px)
    prefer_metadata_value = _as_bool(prefer_metadata, default=True)

    raw_status = str(status or "").strip().lower()
    normalized_status = raw_status if raw_status in SCALE_STATUSES else "missing"
    normalized_note = str(note or "").strip()

    if metadata_value is not None:
        if normalized_status in {"missing", "invalid"}:
            normalized_status = "ok"
    else:
        if normalized_status not in {"missing", "invalid"}:
            normalized_status = "missing"

    if prefer_metadata_value and metadata_value is not None:
        source = "metadata"
        effective = metadata_value
        if normalized_status == "anisotropic_avg" and not normalized_note:
            normalized_note = "Metadata dx/dy differ; using averaged µm/px."
    elif prefer_metadata_value:
        source = "manual_fallback"
        effective = manual_value
        if not normalized_note:
            normalized_note = "Metadata scale unavailable; using manual global scale."
    else:
        source = "manual_global"
        effective = manual_value
        normalized_note = ""

    return {
        "effective_um_per_px": effective,
        "manual_um_per_px": manual_value,
        "metadata_um_per_px": metadata_value,
        "prefer_metadata": prefer_metadata_value,
        "source": source,
        "status": normalized_status,
        "dx": _as_positive_float(dx),
        "dy": _as_positive_float(dy),
        "dz": _as_positive_float(dz),
        "note": normalized_note,
    }


def normalize_scale_info(
    raw_scale_info: Any,
    *,
    manual_default: Any = DEFAULT_MICRONS_PER_PIXEL,
    prefer_metadata_default: bool = True,
) -> dict[str, Any]:
    """Normalize stored scale info into canonical shape."""

    default_manual = parse_microns_per_pixel(manual_default)
    if not isinstance(raw_scale_info, dict):
        return build_scale_info(
            manual_um_per_px=default_manual,
            prefer_metadata=prefer_metadata_default,
        )

    normalized = build_scale_info(
        manual_um_per_px=raw_scale_info.get("manual_um_per_px", default_manual),
        prefer_metadata=raw_scale_info.get("prefer_metadata", prefer_metadata_default),
        metadata_um_per_px=raw_scale_info.get("metadata_um_per_px"),
        status=raw_scale_info.get("status", "missing"),
        dx=raw_scale_info.get("dx"),
        dy=raw_scale_info.get("dy"),
        dz=raw_scale_info.get("dz"),
        note=raw_scale_info.get("note", ""),
    )

    source = str(raw_scale_info.get("source") or "").strip().lower()
    if source == "manual_override":
        override_value = _as_positive_float(raw_scale_info.get("effective_um_per_px"))
        if override_value is not None:
            normalized["source"] = "manual_override"
            normalized["effective_um_per_px"] = override_value
            normalized["note"] = ""
        return normalized

    if source in {"metadata", "manual_global", "manual_fallback"}:
        if source == "metadata" and normalized["metadata_um_per_px"] is not None:
            normalized["source"] = "metadata"
            normalized["effective_um_per_px"] = normalized["metadata_um_per_px"]
        elif source == "manual_global":
            normalized["source"] = "manual_global"
            normalized["effective_um_per_px"] = normalized["manual_um_per_px"]
        elif source == "manual_fallback":
            normalized["source"] = "manual_fallback"
            normalized["effective_um_per_px"] = normalized["manual_um_per_px"]
            if not normalized["note"]:
                normalized["note"] = "Metadata scale unavailable; using manual global scale."

    return normalized


def apply_run_scale_preferences(
    raw_scale_info: Any,
    *,
    manual_um_per_px: Any,
    prefer_metadata: Any,
) -> dict[str, Any]:
    """Apply run-level metadata/manual preference while preserving extracted metadata."""

    normalized = normalize_scale_info(raw_scale_info, manual_default=manual_um_per_px)
    return build_scale_info(
        manual_um_per_px=manual_um_per_px,
        prefer_metadata=prefer_metadata,
        metadata_um_per_px=normalized.get("metadata_um_per_px"),
        status=normalized.get("status", "missing"),
        dx=normalized.get("dx"),
        dy=normalized.get("dy"),
        dz=normalized.get("dz"),
        note=normalized.get("note", ""),
    )


def apply_manual_override_scale(raw_scale_info: Any, *, effective_um_per_px: Any) -> dict[str, Any]:
    """Apply a per-file manual override scale in preprocess."""

    normalized = normalize_scale_info(raw_scale_info)
    override_value = parse_microns_per_pixel(
        effective_um_per_px,
        default=normalized["effective_um_per_px"],
    )
    normalized["effective_um_per_px"] = override_value
    normalized["source"] = "manual_override"
    normalized["note"] = ""
    return normalized


def clear_manual_override_scale(
    raw_scale_info: Any,
    *,
    manual_default: Any = DEFAULT_MICRONS_PER_PIXEL,
) -> dict[str, Any]:
    """Revert a per-file manual override back to metadata/manual auto resolution."""

    normalized = normalize_scale_info(raw_scale_info, manual_default=manual_default)
    return build_scale_info(
        manual_um_per_px=normalized.get("manual_um_per_px", manual_default),
        prefer_metadata=normalized.get("prefer_metadata", True),
        metadata_um_per_px=normalized.get("metadata_um_per_px"),
        status=normalized.get("status", "missing"),
        dx=normalized.get("dx"),
        dy=normalized.get("dy"),
        dz=normalized.get("dz"),
        note="",
    )


def resolve_scale_context(
    raw_scale_info: Any,
    *,
    manual_default: Any = DEFAULT_MICRONS_PER_PIXEL,
    prefer_metadata_default: bool = True,
) -> dict[str, Any]:
    """Resolve normalized scalar scale info into XY-aware conversion context."""

    normalized = normalize_scale_info(
        raw_scale_info,
        manual_default=manual_default,
        prefer_metadata_default=prefer_metadata_default,
    )
    effective_um_per_px = parse_microns_per_pixel(
        normalized.get("effective_um_per_px"),
        default=parse_microns_per_pixel(manual_default),
    )
    source = normalized.get("source")
    raw_dx = _as_positive_float(normalized.get("dx"))
    raw_dy = _as_positive_float(normalized.get("dy"))
    can_use_metadata_axes = source == "metadata" and raw_dx is not None and raw_dy is not None

    x_um_per_px = parse_microns_per_pixel(
        raw_dx if can_use_metadata_axes else effective_um_per_px,
        default=effective_um_per_px,
    )
    y_um_per_px = parse_microns_per_pixel(
        raw_dy if can_use_metadata_axes else effective_um_per_px,
        default=effective_um_per_px,
    )

    is_anisotropic = abs(x_um_per_px - y_um_per_px) > ANISOTROPY_TOLERANCE
    distance_mode = "anisotropic_xy" if can_use_metadata_axes and is_anisotropic else "scalar"
    proxy_raw = math.sqrt(x_um_per_px * y_um_per_px)
    line_width_proxy_um_per_px = parse_microns_per_pixel(
        proxy_raw,
        default=effective_um_per_px,
    )

    return {
        **normalized,
        "x_um_per_px": x_um_per_px,
        "y_um_per_px": y_um_per_px,
        "is_anisotropic": is_anisotropic,
        "distance_mode": distance_mode,
        "line_width_proxy_um_per_px": line_width_proxy_um_per_px,
        "distance_mode_label": DISTANCE_MODE_LABELS.get(distance_mode, "Scalar"),
    }


def convert_pixel_delta_to_microns(
    delta_x_px: Any,
    delta_y_px: Any,
    *,
    x_um_per_px: Any,
    y_um_per_px: Any,
) -> float:
    """Convert pixel-space deltas to physical micrometer distance using XY scales."""

    try:
        dx_px = float(delta_x_px)
        dy_px = float(delta_y_px)
    except (TypeError, ValueError):
        return 0.0

    x_scale = parse_microns_per_pixel(x_um_per_px)
    y_scale = parse_microns_per_pixel(y_um_per_px)
    return float(math.hypot(dx_px * x_scale, dy_px * y_scale))


def get_scale_sidebar_payload(
    raw_scale_info: Any,
    *,
    manual_default: Any = DEFAULT_MICRONS_PER_PIXEL,
) -> dict[str, Any]:
    """Return normalized scale payload plus UI display metadata."""

    normalized = resolve_scale_context(raw_scale_info, manual_default=manual_default)
    source = normalized["source"]
    status = normalized["status"]
    is_warning = source == "manual_fallback" or status in {"invalid", "anisotropic_avg"}
    if status == "missing" and source == "manual_fallback":
        is_warning = True

    note = normalized.get("note") or ""
    if source == "manual_fallback" and not note:
        note = "Metadata scale unavailable; using manual global scale."
    if status == "anisotropic_avg":
        note = (
            "Anisotropic metadata detected: distance checks use per-axis dx/dy; "
            "line width conversion uses geometric proxy."
        )
    if status == "invalid" and not note:
        note = "Metadata scale values are invalid; using manual scale."

    is_metadata_anisotropic = bool(
        normalized.get("source") == "metadata" and normalized.get("is_anisotropic")
    )
    source_label = (
        "Anisotropic auto"
        if is_metadata_anisotropic
        else SCALE_SOURCE_LABELS.get(source, "Manual")
    )
    if normalized.get("is_anisotropic"):
        scale_summary_label = (
            f"dx {format_scale_value(normalized['x_um_per_px'])} / "
            f"dy {format_scale_value(normalized['y_um_per_px'])} µm/px"
        )
    else:
        scale_summary_label = f"{format_scale_value(normalized['x_um_per_px'])} µm/px"

    return {
        **normalized,
        "effective_label": f"{format_scale_value(normalized['effective_um_per_px'])} µm/px",
        "source_label": source_label,
        "status_label": SCALE_STATUS_LABELS.get(status, "Unknown"),
        "is_warning": is_warning,
        "note": note,
        "scale_summary_label": scale_summary_label,
        "line_width_proxy_label": f"{format_scale_value(normalized['line_width_proxy_um_per_px'])} µm/px",
    }


def get_scale_context_payload(
    raw_scale_info: Any,
    *,
    manual_default: Any = DEFAULT_MICRONS_PER_PIXEL,
) -> dict[str, Any]:
    """Return the minimal file-level scale context required for stat conversion."""

    resolved = resolve_scale_context(raw_scale_info, manual_default=manual_default)
    return {
        "effective_um_per_px": resolved["effective_um_per_px"],
        "x_um_per_px": resolved["x_um_per_px"],
        "y_um_per_px": resolved["y_um_per_px"],
        "distance_mode": resolved["distance_mode"],
        "is_anisotropic": bool(resolved["is_anisotropic"]),
    }


def convert_area_pixels_to_display_units(
    pixel_area: Any,
    *,
    unit: Any,
    x_um_per_px: Any,
    y_um_per_px: Any,
) -> float | None:
    """Convert a pixel area to either px² or µm²."""

    try:
        numeric = float(pixel_area)
    except (TypeError, ValueError):
        return None
    if normalize_spatial_stats_unit(unit, default="px") == "px":
        return numeric
    return float(
        numeric * parse_microns_per_pixel(x_um_per_px) * parse_microns_per_pixel(y_um_per_px)
    )


def convert_distance_pixels_to_display_units(
    pixel_distance: Any,
    *,
    unit: Any,
    effective_um_per_px: Any,
    x_um_per_px: Any,
    y_um_per_px: Any,
    delta_x_px: Any = None,
    delta_y_px: Any = None,
) -> float | None:
    """Convert a pixel distance to either px or µm, using anisotropic axes when possible."""

    try:
        numeric = float(pixel_distance)
    except (TypeError, ValueError):
        return None
    if normalize_spatial_stats_unit(unit, default="px") == "px":
        return numeric

    try:
        dx_px = float(delta_x_px)
        dy_px = float(delta_y_px)
    except (TypeError, ValueError):
        dx_px = None
        dy_px = None

    if dx_px is not None and dy_px is not None:
        return convert_pixel_delta_to_microns(
            dx_px,
            dy_px,
            x_um_per_px=x_um_per_px,
            y_um_per_px=y_um_per_px,
        )
    return float(numeric * parse_microns_per_pixel(effective_um_per_px))


def format_spatial_stat_header(label: str, *, spatial_kind: str | None, unit: Any) -> str:
    """Append the active unit marker to a spatial-stat header label."""

    if spatial_kind not in {"distance", "area"}:
        return label
    normalized_unit = normalize_spatial_stats_unit(unit, default="px")
    if spatial_kind == "area":
        suffix = "µm²" if normalized_unit == "um" else "px²"
    else:
        suffix = "µm" if normalized_unit == "um" else "px"
    return f"{label} ({suffix})"


def convert_length_to_pixels(
    raw_value: Any,
    unit: Any,
    *,
    minimum_px: int,
    fallback_px: int,
    um_per_px: Any,
) -> int:
    """Convert plugin length values to integer pixel units for inference."""

    try:
        numeric = float(raw_value)
    except (TypeError, ValueError):
        return fallback_px

    normalized_unit = normalize_length_unit(unit, default="px")
    if normalized_unit == "um":
        scale = _as_positive_float(um_per_px)
        if scale is None or scale < MIN_MICRONS_PER_PIXEL or scale > MAX_MICRONS_PER_PIXEL:
            return fallback_px
        pixels = numeric / scale
    else:
        pixels = numeric

    if not math.isfinite(pixels):
        return fallback_px
    return max(minimum_px, int(round(pixels)))
