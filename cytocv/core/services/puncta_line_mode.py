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
PUNCTA_LINE_MODE_RED_PUNCTA = "red_puncta"
PUNCTA_LINE_MODE_GREEN_PUNCTA = "green_puncta"
PUNCTA_LINE_MODE_RED_ONLY = "red_puncta_only"
PUNCTA_LINE_MODE_GREEN_ONLY = "green_puncta_only"
VALID_PUNCTA_LINE_MODES = frozenset(
    {
        PUNCTA_LINE_MODE_RED_PUNCTA,
        PUNCTA_LINE_MODE_GREEN_PUNCTA,
        PUNCTA_LINE_MODE_RED_ONLY,
        PUNCTA_LINE_MODE_GREEN_ONLY,
    }
)
PUNCTA_LINE_MODE_ORDER = (
    PUNCTA_LINE_MODE_RED_PUNCTA,
    PUNCTA_LINE_MODE_GREEN_PUNCTA,
    PUNCTA_LINE_MODE_RED_ONLY,
    PUNCTA_LINE_MODE_GREEN_ONLY,
)
SINGLE_CHANNEL_PUNCTA_LINE_MODES = frozenset(
    {PUNCTA_LINE_MODE_RED_ONLY, PUNCTA_LINE_MODE_GREEN_ONLY}
)

_MODE_CONFIG = {
    PUNCTA_LINE_MODE_RED_PUNCTA: {
        "source_channel": CHANNEL_ROLE_RED,
        "measurement_channel": CHANNEL_ROLE_GREEN,
        "selector_label": "Red Puncta (Measure Green)",
    },
    PUNCTA_LINE_MODE_GREEN_PUNCTA: {
        "source_channel": CHANNEL_ROLE_GREEN,
        "measurement_channel": CHANNEL_ROLE_RED,
        "selector_label": "Green Puncta (Measure Red)",
    },
    PUNCTA_LINE_MODE_RED_ONLY: {
        "source_channel": CHANNEL_ROLE_RED,
        "measurement_channel": None,
        "selector_label": "Red Puncta Only",
    },
    PUNCTA_LINE_MODE_GREEN_ONLY: {
        "source_channel": CHANNEL_ROLE_GREEN,
        "measurement_channel": None,
        "selector_label": "Green Puncta Only",
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
    """Return a channel display label for a role id or already-formatted value."""

    normalized = normalize_channel_role(channel_role)
    return channel_display_label(normalized or channel_role)


def is_single_channel_puncta_line_mode(mode: Any = None) -> bool:
    """Return whether the mode has no opposite-channel line-intensity output."""

    return normalize_puncta_line_mode(mode) in SINGLE_CHANNEL_PUNCTA_LINE_MODES


def required_channels_for_puncta_line_mode(mode: Any = None) -> frozenset[str]:
    """Return color-channel requirements for a puncta mode, excluding DIC."""

    metadata = get_puncta_line_mode_metadata(mode)
    required = {metadata["source_channel"]}
    measurement_channel = metadata.get("measurement_channel")
    if measurement_channel:
        required.add(str(measurement_channel))
    return frozenset(required)


def get_puncta_line_mode_metadata(mode: Any = None) -> dict[str, Any]:
    """Return resolved channels and user-facing labels for the selected mode."""

    normalized_mode = normalize_puncta_line_mode(mode)
    config = _MODE_CONFIG[normalized_mode]
    source_channel = str(config["source_channel"])
    measurement_channel = config["measurement_channel"]
    source_label = _channel_display(source_channel)
    measurement_label = _channel_display(measurement_channel) if measurement_channel else "N/A"
    is_single_channel = measurement_channel is None
    return {
        "mode": normalized_mode,
        "source_channel": source_channel,
        "measurement_channel": str(measurement_channel) if measurement_channel else "",
        "source_label": source_label,
        "measurement_label": measurement_label,
        "distance_label": f"Distance Between {source_label} Puncta",
        "intensity_label": (
            f"{measurement_label} Intensity Over {source_label} Line"
            if not is_single_channel
            else "Opposite-Channel Line Intensity (N/A)"
        ),
        "selector_label": str(config.get("selector_label") or ""),
        "is_single_channel": is_single_channel,
    }


def get_puncta_line_mode_options() -> list[dict[str, Any]]:
    """Return ordered selector options and channel requirements for the UI."""

    options: list[dict[str, Any]] = []
    for mode in PUNCTA_LINE_MODE_ORDER:
        metadata = get_puncta_line_mode_metadata(mode)
        required_channels = [metadata["source_channel"]]
        measurement_channel = metadata.get("measurement_channel")
        if measurement_channel:
            required_channels.append(str(measurement_channel))
        options.append(
            {
                "value": metadata["mode"],
                "text": metadata["selector_label"],
                "label": metadata["selector_label"],
                "source_channel": metadata["source_channel"],
                "measurement_channel": measurement_channel or "",
                "required_channels": required_channels,
                "is_single_channel": metadata["is_single_channel"],
            }
        )
    return options
