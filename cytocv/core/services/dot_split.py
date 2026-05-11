"""Shared settings for splitting connected fluorescence dot contours."""

from __future__ import annotations

DEFAULT_DOT_SPLIT_MODE = "aggressive"
VALID_DOT_SPLIT_MODES = frozenset({"balanced", "aggressive"})


def normalize_dot_split_mode(
    value: object,
    *,
    default: str = DEFAULT_DOT_SPLIT_MODE,
) -> str:
    """Return a supported fluorescence dot split mode."""

    candidate = str(value or "").strip().lower()
    if candidate in VALID_DOT_SPLIT_MODES:
        return candidate
    if default in VALID_DOT_SPLIT_MODES:
        return default
    return DEFAULT_DOT_SPLIT_MODE


# Compatibility aliases for persisted Red/Green setting names and older imports.
DEFAULT_GREEN_DOT_SPLIT_MODE = DEFAULT_DOT_SPLIT_MODE
DEFAULT_RED_DOT_SPLIT_MODE = DEFAULT_DOT_SPLIT_MODE
VALID_GREEN_DOT_SPLIT_MODES = VALID_DOT_SPLIT_MODES


def normalize_green_dot_split_mode(
    value: object,
    *,
    default: str = DEFAULT_GREEN_DOT_SPLIT_MODE,
) -> str:
    """Return a supported Green dot split mode."""

    return normalize_dot_split_mode(value, default=default)


def normalize_red_dot_split_mode(
    value: object,
    *,
    default: str = DEFAULT_RED_DOT_SPLIT_MODE,
) -> str:
    """Return a supported Red dot split mode."""

    return normalize_dot_split_mode(value, default=default)
