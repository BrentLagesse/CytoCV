"""Helpers for CytoCV media artifact paths and public URLs.

DB storage currently uses two path styles for compatibility:
- FileField/ImageField values are storage-relative paths under MEDIA_ROOT.
- SegmentedImage.ImagePath and CellPairPrefix are public MEDIA_URL strings.
Keep that distinction explicit when adding new artifact paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings


def _path_stem(value: object) -> str:
    return Path(str(value or "")).stem


def _clean_url_part(value: object) -> str:
    return str(value or "").replace("\\", "/").strip("/")


def media_url(*parts: object) -> str:
    """Return a public URL under MEDIA_URL for the supplied path parts."""

    # Public URLs are stored on SegmentedImage and consumed by templates/JS, so
    # normalize separators without changing the historical MEDIA_URL contract.
    base = str(settings.MEDIA_URL or "/media/").rstrip("/")
    cleaned = [part for part in (_clean_url_part(value) for value in parts) if part]
    if not cleaned:
        return f"{base}/"
    return f"{base}/{'/'.join(cleaned)}"


def output_frame_name(image_name: object, frame_index: int) -> str:
    """Return the generated output frame filename for an image/channel."""

    return f"{_path_stem(image_name)}_frame_{int(frame_index)}.png"


def output_frame_url(*, uuid: object, image_name: object, frame_index: int) -> str:
    """Return the public URL for a generated output frame."""

    return media_url(uuid, "output", output_frame_name(image_name, frame_index))


def segmented_image_file_location(*, uuid: object, image_name: object) -> str:
    """Return the storage-relative SegmentedImage.file_location value."""

    return f"user_{uuid}/{_path_stem(image_name)}.png"


def segmented_image_path_url(
    *,
    uuid: object,
    image_name: object,
    frame_index: int = 0,
) -> str:
    """Return the public URL stored in SegmentedImage.ImagePath."""

    return output_frame_url(uuid=uuid, image_name=image_name, frame_index=frame_index)


def cell_pair_prefix_url(*, uuid: object) -> str:
    """Return the public URL prefix stored in SegmentedImage.CellPairPrefix."""

    return media_url(uuid, "segmented", "cell_")


def segmented_cell_image_url(
    *,
    uuid: object,
    image_name: object,
    channel_index: int,
    cell_id: int,
    outline: bool = True,
) -> str:
    """Return the public URL for a generated segmented cell image."""

    # The outline suffix is part of the display/dashboard image lookup contract.
    suffix = "" if outline else "-no_outline"
    file_name = f"{_path_stem(image_name)}-{int(channel_index)}-{int(cell_id)}{suffix}.png"
    return media_url(uuid, "segmented", file_name)


def normalize_media_field_path(value: Any) -> Path | None:
    """Resolve storage-relative or MEDIA_URL-prefixed field values for cleanup.

    Absolute paths are returned unchanged so existing MEDIA_ROOT safety checks can
    reject paths outside the managed media tree.
    """

    raw = str(value or "").strip()
    if not raw:
        return None

    normalized = raw.replace("\\", "/")
    media_prefix = str(settings.MEDIA_URL or "/media/").replace("\\", "/")
    media_prefix = f"/{media_prefix.lstrip('/')}".rstrip("/") + "/"
    if normalized.startswith(media_prefix):
        normalized = normalized[len(media_prefix):]

    candidate = Path(normalized)
    if candidate.is_absolute():
        return candidate
    return Path(settings.MEDIA_ROOT) / normalized
