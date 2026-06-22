"""Row filtering helpers for final canonical Puncta Source contour counts."""

from __future__ import annotations

import math
from typing import Any

from core.services.puncta_line_mode import normalize_puncta_line_mode
from core.services.signal_quantification import SIGNAL_MODE_PUNCTA_DISTANCE


PUNCTA_SOURCE_CONTOUR_FILTER_ALL = "all"
PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_1 = "exactly_1"
PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_2 = "exactly_2"
PUNCTA_SOURCE_CONTOUR_COUNT_SOURCE = "standard_canonical_slots_v1"

_FILTER_ALIASES = {
    "1": PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_1,
    "2": PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_2,
}
_ALLOWED_FILTERS = {
    PUNCTA_SOURCE_CONTOUR_FILTER_ALL,
    PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_1,
    PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_2,
}
_EXACT_FILTER_COUNTS = {
    PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_1: 1,
    PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_2: 2,
}


def normalize_puncta_source_contour_count_filter(value: Any) -> str:
    """Return a canonical Puncta Source contour count filter value."""

    if value is None or isinstance(value, bool):
        return PUNCTA_SOURCE_CONTOUR_FILTER_ALL
    raw = str(value).strip().lower()
    if not raw:
        return PUNCTA_SOURCE_CONTOUR_FILTER_ALL
    if raw in _ALLOWED_FILTERS:
        return raw
    return _FILTER_ALIASES.get(raw, PUNCTA_SOURCE_CONTOUR_FILTER_ALL)


def _as_nonnegative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _as_positive_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().upper() in {"", "N/A", "NA", "NONE"}:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def _get_mapping_or_attr(stat: Any, key: str, default: Any = None) -> Any:
    if isinstance(stat, dict):
        return stat.get(key, default)
    return getattr(stat, key, default)


def _get_properties(stat: Any) -> dict[str, Any]:
    if isinstance(stat, dict):
        properties = stat.get("properties")
        if isinstance(properties, dict):
            return properties
        return stat
    properties = getattr(stat, "properties", None)
    return properties if isinstance(properties, dict) else {}


def count_valid_contour_slots(slots: Any) -> int:
    """Count final canonical slots that have a positive area."""

    if not slots:
        return 0
    count = 0
    for slot in slots:
        area = _get_mapping_or_attr(slot, "area")
        if _as_positive_number(area) is not None:
            count += 1
    return count


def _derive_from_size_slots(stat: Any, channel: str) -> int | None:
    """Return a count from old public size slots when at least one is populated."""

    if channel not in {"red", "green"}:
        return None
    count = 0
    saw_populated_slot = False
    for index in range(1, 4):
        value = _get_mapping_or_attr(stat, f"{channel}_contour_{index}_size")
        positive_value = _as_positive_number(value)
        if positive_value is None:
            continue
        saw_populated_slot = True
        count += 1
    return count if saw_populated_slot else None


def puncta_source_channel_from_statistics(stat: Any) -> str | None:
    """Return the source channel when a row is applicable to Puncta Distance."""

    properties = _get_properties(stat)
    if properties.get("signal_quantification_mode") != SIGNAL_MODE_PUNCTA_DISTANCE:
        return None
    stored_channel = str(properties.get("puncta_source_contour_count_channel") or "").lower()
    if stored_channel in {"red", "green"}:
        return stored_channel
    puncta_line_mode = normalize_puncta_line_mode(properties.get("puncta_line_mode"))
    return "green" if puncta_line_mode == "green_puncta" else "red"


def derive_puncta_source_contour_count_from_statistics(stat: Any) -> int | None:
    """Return stored or safely derived final source contour count for one row."""

    properties = _get_properties(stat)
    channel = puncta_source_channel_from_statistics(stat)
    if channel is None:
        return None

    stored_source_count = _as_nonnegative_int(
        properties.get("puncta_source_contour_count")
    )
    if stored_source_count is not None:
        return stored_source_count

    stored_channel_count = _as_nonnegative_int(
        properties.get(f"{channel}_contour_count")
    )
    if stored_channel_count is not None:
        return stored_channel_count

    direct_source_count = _as_nonnegative_int(
        _get_mapping_or_attr(stat, "puncta_source_contour_count")
    )
    if direct_source_count is not None:
        return direct_source_count

    return _derive_from_size_slots(stat, channel)


def matches_puncta_source_contour_count_filter(stat: Any, filter_value: Any) -> bool:
    """Return whether one statistics row should be included for the filter."""

    normalized = normalize_puncta_source_contour_count_filter(filter_value)
    if normalized == PUNCTA_SOURCE_CONTOUR_FILTER_ALL:
        return True
    if puncta_source_channel_from_statistics(stat) is None:
        return True
    expected_count = _EXACT_FILTER_COUNTS.get(normalized)
    if expected_count is None:
        return True
    return derive_puncta_source_contour_count_from_statistics(stat) == expected_count


def filter_statistics_by_puncta_source_contour_count(statistics: Any, filter_value: Any):
    """Filter a QuerySet/list/list-like collection without mutating the source."""

    normalized = normalize_puncta_source_contour_count_filter(filter_value)
    if normalized == PUNCTA_SOURCE_CONTOUR_FILTER_ALL:
        return statistics
    if statistics is None:
        return []
    return [
        stat
        for stat in statistics
        if matches_puncta_source_contour_count_filter(stat, normalized)
    ]
