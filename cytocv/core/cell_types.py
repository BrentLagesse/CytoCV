"""Canonical cell type and inclusion mode helpers."""

from __future__ import annotations

from typing import Any


CELL_TYPE_SINGLE = "single_cell"
CELL_TYPE_PAIR = "cell_pair"
CELL_TYPE_UNKNOWN = "unknown"

CELL_TYPE_CHOICES = (
    (CELL_TYPE_SINGLE, "Single Cell"),
    (CELL_TYPE_PAIR, "Cell Pair"),
    (CELL_TYPE_UNKNOWN, "Unknown"),
)
CELL_TYPE_LABELS = dict(CELL_TYPE_CHOICES)
CELL_TYPE_VALUES = frozenset(CELL_TYPE_LABELS)

CELL_INCLUSION_MODE_PAIRS_ONLY = "cell_pairs_only"
CELL_INCLUSION_MODE_SINGLES_ONLY = "single_cells_only"
CELL_INCLUSION_MODE_SINGLES_AND_PAIRS = "single_cells_and_cell_pairs"

CELL_INCLUSION_MODE_CHOICES = (
    (CELL_INCLUSION_MODE_PAIRS_ONLY, "Cell pairs only"),
    (CELL_INCLUSION_MODE_SINGLES_ONLY, "Single cells only"),
    (CELL_INCLUSION_MODE_SINGLES_AND_PAIRS, "Single cells and cell pairs"),
)
CELL_INCLUSION_MODE_VALUES = frozenset(
    value for value, _label in CELL_INCLUSION_MODE_CHOICES
)

CELL_TYPE_FILTER_ALL = "all"
CELL_TYPE_FILTER_SINGLE = CELL_TYPE_SINGLE
CELL_TYPE_FILTER_PAIR = CELL_TYPE_PAIR
CELL_TYPE_FILTER_VALUES = frozenset(
    {
        CELL_TYPE_FILTER_ALL,
        CELL_TYPE_FILTER_SINGLE,
        CELL_TYPE_FILTER_PAIR,
    }
)


def normalize_cell_type(value: Any, *, default: str = CELL_TYPE_UNKNOWN) -> str:
    """Return a canonical persisted cell type."""

    raw = str(value or "").strip().lower()
    if raw in CELL_TYPE_VALUES:
        return raw
    return default if default in CELL_TYPE_VALUES else CELL_TYPE_UNKNOWN


def cell_type_label(value: Any) -> str:
    """Return a user-facing label for a persisted cell type."""

    return CELL_TYPE_LABELS.get(normalize_cell_type(value), CELL_TYPE_LABELS[CELL_TYPE_UNKNOWN])


def normalize_cell_inclusion_mode(value: Any) -> str:
    """Return a canonical analysis-time cell inclusion mode."""

    raw = str(value or "").strip().lower()
    if raw in CELL_INCLUSION_MODE_VALUES:
        return raw
    return CELL_INCLUSION_MODE_PAIRS_ONLY


def normalize_cell_type_filter(value: Any) -> str:
    """Return a canonical display/export cell type row filter value."""

    raw = str(value or "").strip().lower()
    if raw in CELL_TYPE_FILTER_VALUES:
        return raw
    return CELL_TYPE_FILTER_ALL


def cell_type_from_statistics(stat: Any) -> str:
    """Return the best-known cell type for a model row or serialized mapping."""

    if isinstance(stat, dict):
        direct = stat.get("cell_type")
        if direct:
            return normalize_cell_type(direct)
        properties = stat.get("properties")
        if isinstance(properties, dict):
            return normalize_cell_type(properties.get("cell_type"))
        return CELL_TYPE_UNKNOWN

    direct = getattr(stat, "cell_type", None)
    if direct:
        return normalize_cell_type(direct)
    properties = getattr(stat, "properties", None)
    if isinstance(properties, dict):
        return normalize_cell_type(properties.get("cell_type"))
    return CELL_TYPE_UNKNOWN


def matches_cell_type_filter(stat: Any, filter_value: Any) -> bool:
    """Return whether one statistics row should be included by cell type."""

    normalized_filter = normalize_cell_type_filter(filter_value)
    if normalized_filter == CELL_TYPE_FILTER_ALL:
        return True
    return cell_type_from_statistics(stat) == normalized_filter


def filter_statistics_by_cell_type(statistics: Any, filter_value: Any):
    """Filter a QuerySet/list/list-like collection without mutating the source."""

    normalized_filter = normalize_cell_type_filter(filter_value)
    if normalized_filter == CELL_TYPE_FILTER_ALL:
        return statistics
    if statistics is None:
        return []
    return [
        stat
        for stat in statistics
        if matches_cell_type_filter(stat, normalized_filter)
    ]
