"""Shared settings for splitting connected Green dot contours."""

from __future__ import annotations

DEFAULT_GREEN_DOT_SPLIT_MODE = "balanced"
VALID_GREEN_DOT_SPLIT_MODES = frozenset({"balanced", "aggressive"})


def normalize_green_dot_split_mode(
    value: object,
    *,
    default: str = DEFAULT_GREEN_DOT_SPLIT_MODE,
) -> str:
    """Return a supported Green dot split mode."""

    candidate = str(value or "").strip().lower()
    if candidate in VALID_GREEN_DOT_SPLIT_MODES:
        return candidate
    if default in VALID_GREEN_DOT_SPLIT_MODES:
        return default
    return DEFAULT_GREEN_DOT_SPLIT_MODE
