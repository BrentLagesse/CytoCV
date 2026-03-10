"""DV metadata scale extraction helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mrc import DVFile


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


def extract_dv_scale_metadata(dv_file_path: str | Path) -> dict[str, Any]:
    """Extract um/px scale metadata from DV header fields (dx/dy/dz)."""

    result = {
        "metadata_um_per_px": None,
        "status": "missing",
        "dx": None,
        "dy": None,
        "dz": None,
        "note": "",
    }

    dv_file = None
    try:
        dv_file = DVFile(dv_file_path)
        metadata = getattr(dv_file, "metadata", {}) or {}
        header = metadata.get("header", {})
        if not isinstance(header, Mapping):
            result["status"] = "missing"
            result["note"] = "DV header metadata was not found."
            return result

        raw_dx = header.get("dx")
        raw_dy = header.get("dy")
        raw_dz = header.get("dz")

        dx = _safe_float(raw_dx)
        dy = _safe_float(raw_dy)
        dz = _safe_float(raw_dz)
        result["dx"] = dx if _valid_scale_value(dx) else None
        result["dy"] = dy if _valid_scale_value(dy) else None
        result["dz"] = dz if _valid_scale_value(dz) else None

        dx_valid = _valid_scale_value(dx)
        dy_valid = _valid_scale_value(dy)
        if dx_valid and dy_valid:
            metadata_scale = (dx + dy) / 2.0
            result["metadata_um_per_px"] = metadata_scale
            if abs(dx - dy) > 1e-9:
                result["status"] = "anisotropic_avg"
                result["note"] = "Header dx/dy differ; using their average."
            else:
                result["status"] = "ok"
                result["note"] = ""
            return result

        if raw_dx is None and raw_dy is None:
            result["status"] = "missing"
            result["note"] = "DV header does not include dx/dy scale values."
        else:
            result["status"] = "invalid"
            result["note"] = "DV header scale values are missing, non-finite, or non-positive."
        return result
    except Exception:
        result["status"] = "invalid"
        result["note"] = "Unable to read DV metadata scale from file header."
        return result
    finally:
        if dv_file is not None:
            dv_file.close()
