from __future__ import annotations

from pathlib import Path
from typing import Mapping

from django.conf import settings

from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
    channel_slug,
)
from core.config import DEFAULT_CHANNEL_CONFIG

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
) -> str:
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

    image_stem = Path(str(image_name or "")).stem
    image_file_name = f"{image_stem}_frame_{fallback_frame_idx}"
    return f"{settings.MEDIA_URL}{uuid}/output/{image_file_name}.png"


def build_main_image_paths(
    *,
    uuid: str,
    image_name: str,
    channel_config: Mapping[str, int],
    available_frames: Mapping[int, str],
) -> dict[str, str]:
    return {
        channel_slug(channel_role): resolve_main_image_url(
            uuid=uuid,
            image_name=image_name,
            channel_role=channel_role,
            channel_config=channel_config,
            available_frames=available_frames,
        )
        for channel_role in MAIN_IMAGE_CHANNEL_ROLES
    }
