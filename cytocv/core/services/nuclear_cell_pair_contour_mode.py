"""Mode constants for Nuclear/Cell-Pair alternate nucleus contours."""

from __future__ import annotations


NUCLEAR_CELL_PAIR_CONTOUR_MODE_BALANCED = "balanced"
NUCLEAR_CELL_PAIR_CONTOUR_MODE_AGGRESSIVE = "aggressive"
DEFAULT_NUCLEAR_CELL_PAIR_CONTOUR_MODE = NUCLEAR_CELL_PAIR_CONTOUR_MODE_BALANCED
NUCLEAR_CELL_PAIR_CONTOUR_MODES = frozenset(
    {
        NUCLEAR_CELL_PAIR_CONTOUR_MODE_BALANCED,
        NUCLEAR_CELL_PAIR_CONTOUR_MODE_AGGRESSIVE,
    }
)

NUCLEAR_CELL_PAIR_ALTERNATE_RED_MASK_KEY = "alternate_nucleus_mask_red"
NUCLEAR_CELL_PAIR_ALTERNATE_GREEN_MASK_KEY = "alternate_nucleus_mask_green"


def normalize_nuclear_cell_pair_contour_mode(
    value,
    *,
    default: str = DEFAULT_NUCLEAR_CELL_PAIR_CONTOUR_MODE,
) -> str:
    """Return a valid Nuclear/Cell-Pair nucleus contour mode."""

    mode = str(value or "").strip().lower()
    if mode in NUCLEAR_CELL_PAIR_CONTOUR_MODES:
        return mode
    return default if default in NUCLEAR_CELL_PAIR_CONTOUR_MODES else DEFAULT_NUCLEAR_CELL_PAIR_CONTOUR_MODE
