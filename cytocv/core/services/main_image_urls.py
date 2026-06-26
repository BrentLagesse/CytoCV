from __future__ import annotations

from typing import Mapping

from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
    channel_slug,
)
from core.config import DEFAULT_CHANNEL_CONFIG
from core.services.artifact_paths import output_frame_url
from core.services.channel_presence import get_channel_presence

MAIN_IMAGE_CHANNEL_ROLES: tuple[str, ...] = (
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_RED,
    CHANNEL_ROLE_GREEN,
)


def resolve_main_image_url(
    *,
    uuid: str,
    image_name: str,
    channel_role: str,
    channel_config: Mapping[str, int],
    available_frames: Mapping[int, str],
    present_channels=None,
) -> str:
    if present_channels is not None and channel_role not in set(present_channels):
        return ""
    fallback_frame_idx = int(DEFAULT_CHANNEL_CONFIG.get(channel_role, 0))
    configured_frame_idx = int(channel_config.get(channel_role, fallback_frame_idx))
    resolved = available_frames.get(configured_frame_idx)
    if not resolved:
        resolved = available_frames.get(fallback_frame_idx)
    if not resolved and available_frames:
        first_idx = sorted(available_frames.keys())[0]
        resolved = available_frames[first_idx]
    if resolved:
        return resolved

    return output_frame_url(
        uuid=uuid,
        image_name=image_name,
        frame_index=fallback_frame_idx,
    )


def build_main_image_paths(
    *,
    uuid: str,
    image_name: str,
    channel_config: Mapping[str, int],
    available_frames: Mapping[int, str],
) -> dict[str, str]:
    presence = get_channel_presence(uuid)
    present_channels = (
        presence.present_channels
        if presence.present_channels or presence.source != "ambiguous"
        else None
    )
    return {
        channel_slug(channel_role): resolve_main_image_url(
            uuid=uuid,
            image_name=image_name,
            channel_role=channel_role,
            channel_config=channel_config,
            available_frames=available_frames,
            present_channels=present_channels,
        )
        for channel_role in MAIN_IMAGE_CHANNEL_ROLES
    }
