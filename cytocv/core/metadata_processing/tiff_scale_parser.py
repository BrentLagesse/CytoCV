"""TIFF physical scale metadata parsing helpers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import tifffile


def _empty_scale_result() -> dict[str, Any]:
    return {
        "metadata_um_per_px": None,
        "status": "missing",
        "dx": None,
        "dy": None,
        "dz": None,
        "note": "",
    }


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _valid_scale_value(value: float | None) -> bool:
    return value is not None and value > 0


def _ratio_to_float(value: Any) -> float | None:
    if isinstance(value, tuple) and len(value) == 2:
        numerator = _safe_float(value[0])
        denominator = _safe_float(value[1])
        if numerator is None or denominator in {None, 0}:
            return None
        return numerator / denominator
    return _safe_float(value)


def _unit_um_from_resolution_unit(unit: Any) -> float | None:
    raw_value = getattr(unit, "value", unit)
    try:
        unit_int = int(raw_value)
    except (TypeError, ValueError):
        unit_text = str(raw_value or "").strip().lower()
        if unit_text in {"inch", "inches"}:
            unit_int = 2
        elif unit_text in {"centimeter", "centimeters", "cm"}:
            unit_int = 3
        else:
            unit_int = 0

    if unit_int == 2:
        return 25400.0
    if unit_int == 3:
        return 10000.0
    return None


def _unit_um_from_imagej_unit(unit: Any) -> float | None:
    unit_text = str(unit or "").strip().lower()
    if unit_text in {"um", "µm", "micron", "microns", "micrometer", "micrometers"}:
        return 1.0
    if unit_text in {"nm", "nanometer", "nanometers"}:
        return 0.001
    if unit_text in {"mm", "millimeter", "millimeters"}:
        return 1000.0
    return None


def read_tiff_scale_metadata(path: str | Path) -> dict[str, Any]:
    """Read raw TIFF scale-related metadata through tifffile."""

    with tifffile.TiffFile(path) as tiff:
        if len(tiff.pages) == 0:
            return {"tags": {}, "imagej": {}}
        tags = tiff.pages[0].tags
        imagej_metadata = getattr(tiff, "imagej_metadata", None) or {}
        return {
            "tags": {
                "XResolution": tags["XResolution"].value if "XResolution" in tags else None,
                "YResolution": tags["YResolution"].value if "YResolution" in tags else None,
                "ResolutionUnit": tags["ResolutionUnit"].value if "ResolutionUnit" in tags else None,
            },
            "imagej": dict(imagej_metadata),
        }


def _build_scale_result(
    *,
    unit_um: float | None,
    x_resolution: float | None,
    y_resolution: float | None,
    missing_unit_note: str,
) -> dict[str, Any]:
    result = _empty_scale_result()
    if unit_um is None:
        result["status"] = "missing"
        result["note"] = missing_unit_note
        return result
    if not _valid_scale_value(x_resolution) or not _valid_scale_value(y_resolution):
        result["status"] = "invalid"
        result["note"] = "TIFF resolution values are missing, non-finite, or non-positive."
        return result

    dx = unit_um / x_resolution
    dy = unit_um / y_resolution
    result["dx"] = dx
    result["dy"] = dy
    result["metadata_um_per_px"] = (dx + dy) / 2.0
    if abs(dx - dy) > 1e-9:
        result["status"] = "anisotropic_avg"
        result["note"] = "TIFF X/Y resolution tags differ; using their average."
    else:
        result["status"] = "ok"
    return result


def extract_tiff_scale_metadata(path: str | Path) -> dict[str, Any]:
    """Extract um/px scale metadata from TIFF resolution metadata."""

    try:
        metadata = read_tiff_scale_metadata(path)
    except Exception:
        result = _empty_scale_result()
        result["status"] = "invalid"
        result["note"] = "Unable to read TIFF resolution metadata."
        return result

    tags = metadata["tags"]
    imagej_metadata = metadata["imagej"]
    x_resolution = _ratio_to_float(tags.get("XResolution"))
    y_resolution = _ratio_to_float(tags.get("YResolution"))
    unit_um = _unit_um_from_resolution_unit(tags.get("ResolutionUnit"))
    if unit_um is not None:
        return _build_scale_result(
            unit_um=unit_um,
            x_resolution=x_resolution,
            y_resolution=y_resolution,
            missing_unit_note="TIFF resolution metadata does not include a physical unit.",
        )

    imagej_unit_um = _unit_um_from_imagej_unit(imagej_metadata.get("unit"))
    return _build_scale_result(
        unit_um=imagej_unit_um,
        x_resolution=x_resolution,
        y_resolution=y_resolution,
        missing_unit_note="TIFF resolution metadata does not include a physical unit.",
    )
