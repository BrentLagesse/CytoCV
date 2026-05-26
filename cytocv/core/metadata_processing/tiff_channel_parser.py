"""TIFF channel metadata parsing helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import tifffile

from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
)
from core.channel_ordering import (
    DEFAULT_FALLBACK_CHANNEL_ORDER,
    fallback_channel_config,
    resolve_channel_config,
)

_CHANNEL_ROLES = frozenset(DEFAULT_FALLBACK_CHANNEL_ORDER)
_WAVELENGTH_PATTERN = re.compile(r"(?i)(?:^|[^a-z0-9])w[_\s-]*(\d{3,4})(?=[^a-z0-9]|$)")


def read_tiff_imagej_metadata(path: str | Path) -> dict[str, Any]:
    """Read ImageJ metadata from a TIFF file."""

    with tifffile.TiffFile(path) as tiff:
        metadata = getattr(tiff, "imagej_metadata", None)
        return dict(metadata or {})


def extract_tiff_channel_labels_from_metadata(metadata: dict[str, Any]) -> list[str]:
    """Return channel labels from ImageJ metadata."""

    raw_labels = metadata.get("Labels") or metadata.get("labels")
    if not isinstance(raw_labels, (list, tuple)):
        return []
    return [str(label) for label in raw_labels if str(label).strip()]


def _role_from_wavelength(wavelength: float) -> str | None:
    if abs(wavelength - 625) < 12:
        return CHANNEL_ROLE_RED
    if abs(wavelength - 525) < 12:
        return CHANNEL_ROLE_GREEN
    if abs(wavelength - 435) < 12:
        return CHANNEL_ROLE_BLUE
    return None


def map_tiff_label_to_channel_role(label: str) -> str | None:
    """Map one ImageJ/softWoRx TIFF label to a canonical channel role."""

    normalized = str(label or "").strip()
    lower = normalized.lower()
    compact = "".join(ch for ch in lower if ch.isalnum())

    wavelength_match = _WAVELENGTH_PATTERN.search(lower)
    if wavelength_match:
        role = _role_from_wavelength(float(wavelength_match.group(1)))
        if role:
            return role

    if "dic" in compact or "brightfield" in compact or "transmission" in compact:
        return CHANNEL_ROLE_DIC
    if "r3dref" in compact or "_ref" in lower or lower.endswith("ref.tif"):
        return CHANNEL_ROLE_DIC
    return None


def build_tiff_channel_config_from_labels(labels: list[str]) -> dict[str, int] | None:
    """Build a complete channel config from TIFF labels, or None when ambiguous."""

    if len(labels) != len(_CHANNEL_ROLES):
        return None

    config: dict[str, int] = {}
    for index, label in enumerate(labels):
        role = map_tiff_label_to_channel_role(label)
        if role is None or role in config:
            return None
        config[role] = index

    if set(config) != _CHANNEL_ROLES:
        return None
    return config


def extract_tiff_metadata_channel_config(path: str | Path) -> dict[str, int] | None:
    """Return a metadata-derived TIFF channel config when labels are complete."""

    try:
        metadata = read_tiff_imagej_metadata(path)
        labels = extract_tiff_channel_labels_from_metadata(metadata)
        return build_tiff_channel_config_from_labels(labels)
    except Exception:
        return None


def extract_tiff_channel_config(
    path: str | Path,
    *,
    prefer_metadata: bool = True,
    fallback_order: list[str] | tuple[str, ...] | None = None,
) -> dict[str, int]:
    """Return TIFF channel config, falling back to the configured default order."""

    metadata_config = extract_tiff_metadata_channel_config(path) if prefer_metadata else None
    return resolve_channel_config(
        metadata_config,
        prefer_metadata=prefer_metadata,
        fallback_order=fallback_order,
    )
