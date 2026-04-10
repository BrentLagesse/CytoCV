"""Shared configuration defaults for image processing."""

from __future__ import annotations

import json
import os
from typing import Any

from cytocv.settings import MEDIA_ROOT
from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
    normalize_channel_role,
)

input_dir = ""
output_dir = ""

DEFAULT_CHANNEL_CONFIG: dict[str, int] = {
    CHANNEL_ROLE_RED: 3,
    CHANNEL_ROLE_GREEN: 2,
    CHANNEL_ROLE_BLUE: 1,
    CHANNEL_ROLE_DIC: 0,
}

DEFAULT_PROCESS_CONFIG: dict[str, Any] = {
    "kernel_size": 13,
    "kernel_deviation": 5,
    "puncta_line_width": 1,
    "useCache": "on",
    "red_to_find_pairs": "on",
    "drop_ignore": "off",
    "arrested": "Metaphase Arrested",
}


def default_process_config() -> dict[str, Any]:
    """Return a per-call copy of the default processing configuration."""
    return dict(DEFAULT_PROCESS_CONFIG)


def get_channel_config_for_uuid(uuid: str) -> dict[str, Any]:
    """Load per-file channel mapping or fall back to defaults.

    Args:
        uuid: UUID for the uploaded DV file directory.

    Returns:
        Channel mapping for the given UUID.
    """
    config_path = os.path.join(MEDIA_ROOT, str(uuid), "channel_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            payload = json.load(f)
        return {
            normalize_channel_role(channel_name) or channel_name: int(channel_index)
            for channel_name, channel_index in payload.items()
            if channel_index is not None
        }
    return DEFAULT_CHANNEL_CONFIG
