"""Backward-compatible imports for fluorescence dot split settings.

Use :mod:`core.services.dot_split` for new code.
"""

from __future__ import annotations

from core.services.dot_split import (
    DEFAULT_DOT_SPLIT_MODE,
    DEFAULT_GREEN_DOT_SPLIT_MODE,
    DEFAULT_RED_DOT_SPLIT_MODE,
    VALID_DOT_SPLIT_MODES,
    VALID_GREEN_DOT_SPLIT_MODES,
    normalize_dot_split_mode,
    normalize_green_dot_split_mode,
    normalize_red_dot_split_mode,
)

__all__ = [
    "DEFAULT_DOT_SPLIT_MODE",
    "DEFAULT_GREEN_DOT_SPLIT_MODE",
    "DEFAULT_RED_DOT_SPLIT_MODE",
    "VALID_DOT_SPLIT_MODES",
    "VALID_GREEN_DOT_SPLIT_MODES",
    "normalize_dot_split_mode",
    "normalize_green_dot_split_mode",
    "normalize_red_dot_split_mode",
]
