"""Shared configuration defaults for image processing."""

from __future__ import annotations

import json
import os
from typing import Any

from yeastweb.settings import MEDIA_ROOT

input_dir = ""
output_dir = ""

DEFAULT_CHANNEL_CONFIG: dict[str, int] = {
    "mCherry": 3,
    "GFP": 2,
    "DAPI": 1,
    "DIC": 0,
}

DEFAULT_PROCESS_CONFIG: dict[str, Any] = {
    "kernel_size": 13,
    "kernel_deviation": 5,
    "mCherry_line_width": 1,
    "mCherry_dot_method": "current",
    "legacy_gfp_otsu_bias": 0.0,
    "legacy_gfp_min_area": 14.0,
    "legacy_gfp_max_count": 8,
    "useCache": "on",
    "mCherry_to_find_pairs": "on",
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
            return json.load(f)
    return DEFAULT_CHANNEL_CONFIG
