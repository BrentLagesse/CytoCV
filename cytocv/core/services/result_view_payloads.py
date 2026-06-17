from __future__ import annotations

import math
from typing import Any

from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
    channel_display_label,
    channel_slug,
)
from core.services.puncta_line_mode import VALID_PUNCTA_LINE_MODES

RESULT_CHANNEL_ORDER = [
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_RED,
    CHANNEL_ROLE_GREEN,
]
NUCLEAR_CELL_PAIR_MODES = {"green_nucleus", "red_nucleus"}


def resolve_nuclear_cell_pair_mode(stats_iterable: Any) -> str | None:
    modes = set()
    for stat in stats_iterable:
        props = stat.properties or {}
        mode = props.get("nuclear_cell_pair_mode", props.get("nuclear_cellular_mode"))
        if mode in NUCLEAR_CELL_PAIR_MODES:
            modes.add(mode)
    return modes.pop() if len(modes) == 1 else None


def resolve_puncta_line_mode(stats_iterable: Any) -> str | None:
    modes = set()
    for stat in stats_iterable:
        props = stat.properties or {}
        mode = props.get("puncta_line_mode")
        if mode in VALID_PUNCTA_LINE_MODES:
            modes.add(mode)
    return modes.pop() if len(modes) == 1 else None


def resolve_cell_table_modes(stats_iterable: Any) -> tuple[str | None, str | None]:
    return (
        resolve_nuclear_cell_pair_mode(stats_iterable),
        resolve_puncta_line_mode(stats_iterable),
    )


def sanitize_for_json(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_json(item) for item in value]
    return value


def detected_channel_labels(channel_config: dict[str, int]) -> list[str]:
    return [
        channel_display_label(channel_name)
        for channel_name, _ in sorted(channel_config.items(), key=lambda entry: entry[1])
    ]


def channel_config_payload(channel_config: dict[str, int]) -> dict[str, int]:
    return {
        channel_slug(channel_name): channel_index
        for channel_name, channel_index in channel_config.items()
    }
