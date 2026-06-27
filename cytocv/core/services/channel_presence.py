"""Missing-channel sidecar helpers for uploaded source images."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from django.conf import settings
from core.channel_ordering import (
    DEFAULT_FALLBACK_CHANNEL_ORDER,
    normalize_channel_order,
)
from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_ORDER,
    CHANNEL_ROLE_RED,
    channel_sort_key,
    normalize_channel_role,
)
from core.image_sources import (
    DV_IMAGE_EXTENSION,
    TIFF_IMAGE_EXTENSIONS,
    get_image_layer_count,
    source_image_extension,
)

CHANNEL_PRESENCE_FILE = "channel_presence.json"
OPTIONAL_FLUORESCENCE_CHANNELS = frozenset(
    {CHANNEL_ROLE_BLUE, CHANNEL_ROLE_RED, CHANNEL_ROLE_GREEN}
)
ALL_CHANNELS = frozenset(CHANNEL_ROLE_ORDER)


@dataclass(frozen=True, slots=True)
class ChannelPresence:
    """Sidecar-safe record of which logical channels a source can support."""

    present_channels: frozenset[str]
    missing_channels: frozenset[str]
    source: str = "unknown"
    layer_count: int | None = None
    confirmed: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "layer_count": self.layer_count,
            "present_channels": sorted(self.present_channels, key=channel_sort_key),
            "missing_channels": sorted(self.missing_channels, key=channel_sort_key),
            "source": self.source,
            "confirmed": self.confirmed,
        }


def channel_presence_path(run_uuid: str) -> Path:
    """Return the per-run sidecar path for missing-channel decisions."""

    return Path(settings.MEDIA_ROOT) / str(run_uuid) / CHANNEL_PRESENCE_FILE


def _normalize_channel_set(values: Iterable[object]) -> frozenset[str]:
    normalized = {
        channel
        for channel in (normalize_channel_role(value) for value in values or [])
        if channel in ALL_CHANNELS
    }
    return frozenset(normalized)


def _presence_from_payload(payload: Mapping[str, object]) -> ChannelPresence | None:
    present = _normalize_channel_set(payload.get("present_channels") or [])
    missing = _normalize_channel_set(payload.get("missing_channels") or [])
    if not present and missing:
        present = frozenset(ALL_CHANNELS - missing)
    if not missing and present:
        missing = frozenset(ALL_CHANNELS - present)
    if present | missing != ALL_CHANNELS or present & missing:
        return None
    return ChannelPresence(
        present_channels=present,
        missing_channels=missing,
        source=str(payload.get("source") or "sidecar"),
        layer_count=(
            int(payload["layer_count"])
            if str(payload.get("layer_count") or "").isdigit()
            else None
        ),
        confirmed=bool(payload.get("confirmed", False)),
    )


def read_channel_presence(run_uuid: str) -> ChannelPresence | None:
    path = channel_presence_path(run_uuid)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return _presence_from_payload(payload if isinstance(payload, Mapping) else {})


def write_channel_presence(run_uuid: str, presence: ChannelPresence) -> None:
    """Persist channel presence atomically next to the uploaded run artifacts."""

    path = channel_presence_path(run_uuid)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f".json.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(presence.to_json()), encoding="utf-8")
    tmp_path.replace(path)


def get_channel_presence(
    run_uuid: str,
    *,
    layer_count: int | None = None,
) -> ChannelPresence:
    """Return sidecar presence, falling back to legacy all-present behavior."""

    sidecar = read_channel_presence(run_uuid)
    if sidecar is not None:
        return sidecar
    if layer_count == 3:
        return ChannelPresence(
            present_channels=frozenset(),
            missing_channels=frozenset(),
            source="ambiguous",
            layer_count=layer_count,
        )
    return ChannelPresence(
        present_channels=frozenset(ALL_CHANNELS),
        missing_channels=frozenset(),
        source="legacy_all_present",
        layer_count=layer_count,
        confirmed=False,
    )


def is_channel_present(run_uuid: str, channel_role: object) -> bool:
    """Return whether a logical channel is known to be usable for this run."""

    channel = normalize_channel_role(channel_role)
    if channel is None:
        return False
    return channel in get_channel_presence(run_uuid).present_channels


def missing_channels_for_uuid(run_uuid: str) -> frozenset[str]:
    """Return missing channels from the sidecar or legacy fallback behavior."""

    return get_channel_presence(run_uuid).missing_channels


def _valid_config_channels(channel_config: Mapping[str, object], layer_count: int) -> set[str]:
    available: set[str] = set()
    for raw_channel, raw_index in (channel_config or {}).items():
        channel = normalize_channel_role(raw_channel)
        if channel not in ALL_CHANNELS:
            continue
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if 0 <= index < layer_count:
            available.add(channel)
    return available


def extract_reliable_metadata_channel_config(
    source_image_path: str | Path,
    *,
    prefer_metadata: bool = True,
) -> dict[str, int]:
    """Return metadata-only channel mapping; never fall back to default order."""

    if not prefer_metadata:
        return {}
    extension = source_image_extension(source_image_path)
    try:
        if extension == DV_IMAGE_EXTENSION:
            from core.metadata_processing.dv_channel_parser import (
                extract_dv_metadata_channel_config,
            )

            return dict(extract_dv_metadata_channel_config(source_image_path) or {})
        if extension in TIFF_IMAGE_EXTENSIONS:
            from core.metadata_processing.tiff_channel_parser import (
                extract_tiff_metadata_channel_config,
            )

            return dict(extract_tiff_metadata_channel_config(source_image_path) or {})
    except Exception:
        return {}
    return {}


def _presence_from_metadata(
    metadata_config: Mapping[str, object],
    layer_count: int,
) -> ChannelPresence | None:
    present = _valid_config_channels(metadata_config, layer_count)
    missing = set(ALL_CHANNELS) - present
    if (
        layer_count == 3
        and len(present) == 3
        and CHANNEL_ROLE_DIC in present
        and len(missing) == 1
        and next(iter(missing)) in OPTIONAL_FLUORESCENCE_CHANNELS
    ):
        return ChannelPresence(
            present_channels=frozenset(present),
            missing_channels=frozenset(missing),
            source="metadata",
            layer_count=layer_count,
            confirmed=True,
        )
    if layer_count == 4 and ALL_CHANNELS.issubset(present):
        return ChannelPresence(
            present_channels=frozenset(ALL_CHANNELS),
            missing_channels=frozenset(),
            source="metadata",
            layer_count=layer_count,
            confirmed=True,
        )
    return None


def resolve_channel_presence_for_source(
    source_image_path: str | Path,
    *,
    layer_count: int | None = None,
    prefer_metadata: bool = True,
) -> ChannelPresence:
    """Determine channel presence without inventing labels for ambiguous stacks."""

    if layer_count is None:
        layer_count = get_image_layer_count(str(source_image_path))

    if layer_count == 4:
        return ChannelPresence(
            present_channels=frozenset(ALL_CHANNELS),
            missing_channels=frozenset(),
            source="all_present",
            layer_count=layer_count,
            confirmed=True,
        )

    if layer_count == 3:
        metadata_config = extract_reliable_metadata_channel_config(
            source_image_path,
            prefer_metadata=prefer_metadata,
        )
        metadata_presence = _presence_from_metadata(metadata_config, layer_count)
        if metadata_presence is not None:
            return metadata_presence

    return ChannelPresence(
        present_channels=frozenset(),
        missing_channels=frozenset(),
        source="ambiguous",
        layer_count=layer_count,
    )


def channel_config_for_present_channels(
    *,
    present_channels: Iterable[str],
    fallback_order: Iterable[object] | None = None,
) -> dict[str, int]:
    """Build a compact fallback channel map only for confirmed present channels."""

    present = _normalize_channel_set(present_channels)
    order = normalize_channel_order(
        fallback_order,
        default=DEFAULT_FALLBACK_CHANNEL_ORDER,
    )
    present_order = [channel for channel in order if channel in present]
    return {channel: index for index, channel in enumerate(present_order)}


def resolve_channel_config_and_presence_for_source(
    source_image_path: str | Path,
    *,
    prefer_metadata: bool = True,
    fallback_order: Iterable[object] | None = None,
) -> tuple[dict[str, int], ChannelPresence]:
    """Return the upload-preparation channel map plus its presence sidecar."""

    layer_count = get_image_layer_count(str(source_image_path))
    presence = resolve_channel_presence_for_source(
        source_image_path,
        layer_count=layer_count,
        prefer_metadata=prefer_metadata,
    )

    if layer_count == 3 and presence.present_channels:
        metadata_config = extract_reliable_metadata_channel_config(
            source_image_path,
            prefer_metadata=prefer_metadata,
        )
        metadata_presence = _presence_from_metadata(metadata_config, layer_count)
        if metadata_presence is not None:
            return (
                {
                    channel: int(index)
                    for channel, index in metadata_config.items()
                    if normalize_channel_role(channel) in presence.present_channels
                },
                presence,
            )
    if layer_count == 3:
        return ({}, presence)

    from core.metadata_processing.dv_channel_parser import extract_channel_config

    return (
        extract_channel_config(
            source_image_path,
            prefer_metadata=prefer_metadata,
            fallback_order=fallback_order,
        ),
        presence,
    )
