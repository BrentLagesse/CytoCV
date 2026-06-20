"""Helpers for deciding whether stored stat values were actually calculated."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from core.services.signal_quantification import build_stat_visibility


STAT_FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "puncta_distance": (
        "puncta_distance",
        "puncta_line_intensity",
    ),
    "red_green_intensity": (
        "red_contour_1_size",
        "red_contour_2_size",
        "red_contour_3_size",
        "red_contour_1_center_xy",
        "red_contour_2_center_xy",
        "red_contour_3_center_xy",
        "green_contour_1_size",
        "green_contour_2_size",
        "green_contour_3_size",
        "green_contour_1_center_xy",
        "green_contour_2_center_xy",
        "green_contour_3_center_xy",
        "red_in_red_total_intensity_1",
        "red_in_red_max_intensity_1",
        "red_in_red_average_intensity_1",
        "red_in_red_total_intensity_2",
        "red_in_red_max_intensity_2",
        "red_in_red_average_intensity_2",
        "red_in_red_total_intensity_3",
        "red_in_red_max_intensity_3",
        "red_in_red_average_intensity_3",
        "green_in_red_total_intensity_1",
        "green_in_red_max_intensity_1",
        "green_in_red_average_intensity_1",
        "green_in_red_total_intensity_2",
        "green_in_red_max_intensity_2",
        "green_in_red_average_intensity_2",
        "green_in_red_total_intensity_3",
        "green_in_red_max_intensity_3",
        "green_in_red_average_intensity_3",
        "red_in_green_total_intensity_1",
        "red_in_green_max_intensity_1",
        "red_in_green_average_intensity_1",
        "red_in_green_total_intensity_2",
        "red_in_green_max_intensity_2",
        "red_in_green_average_intensity_2",
        "red_in_green_total_intensity_3",
        "red_in_green_max_intensity_3",
        "red_in_green_average_intensity_3",
        "green_in_green_total_intensity_1",
        "green_in_green_max_intensity_1",
        "green_in_green_average_intensity_1",
        "green_in_green_total_intensity_2",
        "green_in_green_max_intensity_2",
        "green_in_green_average_intensity_2",
        "green_in_green_total_intensity_3",
        "green_in_green_max_intensity_3",
        "green_in_green_average_intensity_3",
        "green_red_intensity_1",
        "green_red_intensity_2",
        "green_red_intensity_3",
        "measurement_contour_ratio_1",
        "measurement_contour_ratio_2",
        "measurement_contour_ratio_3",
        "distance_of_green_from_red_1",
        "distance_of_green_from_red_2",
        "distance_of_green_from_red_3",
    ),
    "nuclear_cell_pair_intensity": (
        "nuclear_cell_pair_contour_source",
        "nuclear_cell_pair_contour_channel",
        "nuclear_cell_pair_measurement_channel",
        "nuclear_cell_pair_status",
        "cell_pair_intensity_sum",
        "nucleus_intensity_sum",
        "cytoplasmic_intensity",
        "nuclear_cytoplasmic_ratio",
    ),
    "cen_dot": (
        "cell_parentage",
        "category_cen_dot",
        "category_cen_dot_label",
        "cen_dot_location",
    ),
    "biorientation": (
        "colinear_dots",
        "off_axis_dots",
    ),
    "legacy_blue_intensity": (
        "blue_contour_size",
        "blue_contour_center_xy",
        "red_blue_intensity_1",
        "red_blue_intensity_2",
        "red_blue_intensity_3",
        "cell_pair_intensity_sum_blue",
        "nucleus_intensity_sum_blue",
        "cytoplasmic_intensity_blue",
    ),
}

STAT_FIELD_TO_GROUP = {
    field_name: group_name
    for group_name, field_names in STAT_FIELD_GROUPS.items()
    for field_name in field_names
}


def default_stat_visibility() -> dict[str, bool]:
    """Return legacy-compatible visibility for rows without selection metadata."""

    return {group_name: True for group_name in STAT_FIELD_GROUPS}


def normalize_stat_visibility(value: Any) -> dict[str, bool] | None:
    """Return a complete stat-visibility map when ``value`` is mapping-like."""

    if not isinstance(value, Mapping):
        return None
    return {
        group_name: bool(value.get(group_name, True))
        for group_name in STAT_FIELD_GROUPS
    }


def _properties_from_source(source: Any) -> dict[str, Any]:
    if source is None:
        return {}
    if isinstance(source, Mapping):
        properties = source.get("properties", source)
    else:
        properties = getattr(source, "properties", {}) or {}
    return dict(properties) if isinstance(properties, Mapping) else {}


def _first_record(data: Any) -> Any:
    if data is None:
        return None
    if hasattr(data, "first"):
        try:
            return data.first()
        except Exception:
            return None
    if isinstance(data, (list, tuple)) and data:
        return data[0]
    return None


def resolve_stat_visibility(
    source: Any = None,
    *,
    selected_plugins: Iterable[Any] | None = None,
    stat_visibility: Mapping[str, Any] | None = None,
) -> dict[str, bool]:
    """Resolve calculated stat groups from selected plugins or row metadata."""

    if selected_plugins is not None:
        return build_stat_visibility(selected_plugins)

    properties = _properties_from_source(_first_record(source) or source)
    selected_analysis = properties.get("selected_analysis")
    if isinstance(selected_analysis, list):
        return build_stat_visibility(selected_analysis)

    explicit_visibility = normalize_stat_visibility(stat_visibility)
    if explicit_visibility is not None:
        return explicit_visibility

    property_visibility = normalize_stat_visibility(properties.get("stat_visibility"))
    if property_visibility is not None:
        return property_visibility

    return default_stat_visibility()


def stat_group_for_field(field_name: str) -> str | None:
    """Return the owning stat group for a serialized/table field."""

    return STAT_FIELD_TO_GROUP.get(field_name)


def is_field_applicable(
    record: Any,
    field_name: str,
    *,
    stat_visibility: Mapping[str, Any] | None = None,
) -> bool:
    """Return whether a field should display its stored value for ``record``."""

    group_name = stat_group_for_field(field_name)
    if group_name is None:
        return True
    visibility = resolve_stat_visibility(record, stat_visibility=stat_visibility)
    return bool(visibility.get(group_name, True))
