"""Helpers for the configurable puncta-line measurement mode."""

from __future__ import annotations

from typing import Any

from core.channel_roles import (
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
    channel_display_label,
    normalize_channel_role,
)


DEFAULT_PUNCTA_LINE_MODE = "red_puncta"
VALID_PUNCTA_LINE_MODES = frozenset({"red_puncta", "green_puncta"})

_MODE_CONFIG = {
    "red_puncta": {
        "source_channel": CHANNEL_ROLE_RED,
        "measurement_channel": CHANNEL_ROLE_GREEN,
    },
    "green_puncta": {
        "source_channel": CHANNEL_ROLE_GREEN,
        "measurement_channel": CHANNEL_ROLE_RED,
    },
}


def normalize_puncta_line_mode(
    value: Any,
    default: str = DEFAULT_PUNCTA_LINE_MODE,
) -> str:
    """Return a supported puncta-line mode."""

    candidate = str(value or "").strip()
    if candidate in VALID_PUNCTA_LINE_MODES:
        return candidate
    return default


def _channel_display(channel_role: Any) -> str:
    normalized = normalize_channel_role(channel_role)
    return channel_display_label(normalized or channel_role)


def get_puncta_line_mode_metadata(mode: Any = None) -> dict[str, str]:
    """Return resolved channels and user-facing labels for the selected mode."""

    normalized_mode = normalize_puncta_line_mode(mode)
    config = _MODE_CONFIG[normalized_mode]
    source_channel = str(config["source_channel"])
    measurement_channel = str(config["measurement_channel"])
    source_label = _channel_display(source_channel)
    measurement_label = _channel_display(measurement_channel)
    return {
        "mode": normalized_mode,
        "source_channel": source_channel,
        "measurement_channel": measurement_channel,
        "source_label": source_label,
        "measurement_label": measurement_label,
        "distance_label": f"Distance between {source_label} Puncta",
        "intensity_label": f"{measurement_label} Intensity over {source_label} Line",
        "selector_label": f"{source_label} puncta (measure {measurement_label})",
    }

