"""Serialization helpers for renamed cell statistics payloads."""

from __future__ import annotations

from typing import Any

from core.channel_roles import channel_display_label, normalize_channel_role
from core.models import CellStatistics, get_cen_dot_category_label
from core.services.contour_coordinates import contour_center_payloads_from_properties
from core.services.measurement_contour_ratio import (
    build_measurement_contour_ratio_payload,
    normalize_nuclear_cell_pair_mode,
)
from core.services.puncta_line_mode import get_puncta_line_mode_metadata
from core.services.cell_parentage import cell_parentage_payload_from_properties
from core.services.stat_applicability import resolve_stat_visibility, stat_group_for_field


def normalize_channel_display_name(value: Any, default: str = "") -> str:
    """Return a canonical user-facing channel label."""

    raw = str(value or "").strip()
    if not raw:
        return default
    normalized = normalize_channel_role(raw)
    if normalized:
        return channel_display_label(normalized)
    return raw


def serialize_cell_statistics_payload(
    cell_stat: CellStatistics | None,
) -> dict[str, Any] | None:
    """Serialize a cell-statistics record for display/dashboard/profile views."""

    if not cell_stat:
        return None

    properties = cell_stat.properties or {}
    cell_parentage = cell_parentage_payload_from_properties(properties)
    nuclear_cell_pair_mode = normalize_nuclear_cell_pair_mode(
        properties.get("nuclear_cell_pair_mode", properties.get("nuclear_cellular_mode"))
    )
    puncta_line_metadata = get_puncta_line_mode_metadata(
        properties.get("puncta_line_mode")
    )
    selected_analysis = properties.get("selected_analysis")
    stat_visibility = resolve_stat_visibility(cell_stat)
    puncta_enabled = stat_visibility.get("puncta_distance", True)
    red_green_enabled = stat_visibility.get("red_green_intensity", True)
    nuclear_enabled = stat_visibility.get("nuclear_cell_pair_intensity", True)
    cen_dot_enabled = stat_visibility.get("cen_dot", True)
    biorientation_enabled = stat_visibility.get("biorientation", True)
    measurement_contour_ratio_mode = properties.get(
        "measurement_contour_ratio_mode",
        nuclear_cell_pair_mode,
    )
    cell_parentage = (
        cell_parentage
        if cen_dot_enabled
        else {
            "label": "N/A",
            "status": "not_calculated",
            "mode": None,
            "method": None,
        }
    )
    ratio_payload = build_measurement_contour_ratio_payload(
        cell_stat,
        mode=measurement_contour_ratio_mode,
    )
    if not red_green_enabled:
        ratio_payload.update(
            {
                "measurement_contour_ratio_1": None,
                "measurement_contour_ratio_2": None,
                "measurement_contour_ratio_3": None,
                "measurement_contour_ratio_pair_label": None,
                "measurement_contour_ratio_formula": None,
                "measurement_contour_ratio_display_text": "N/A",
            }
        )
    contour_center_payloads = contour_center_payloads_from_properties(properties)

    def stat_value(field_name: str, value: Any) -> Any:
        group_name = stat_group_for_field(field_name)
        if group_name is not None and not stat_visibility.get(group_name, True):
            return None
        return value

    intensity_payload = {}
    for prefix in (
        "red_in_red",
        "green_in_red",
        "red_in_green",
        "green_in_green",
    ):
        for index in range(1, 4):
            for statistic in ("total", "max", "average"):
                field_name = f"{prefix}_{statistic}_intensity_{index}"
                intensity_payload[field_name] = stat_value(
                    field_name,
                    getattr(cell_stat, field_name),
                )

    return {
        "selected_analysis": selected_analysis if isinstance(selected_analysis, list) else [],
        "stat_visibility": stat_visibility,
        "signal_quantification_enabled": properties.get("signal_quantification_enabled"),
        "signal_quantification_mode": properties.get("signal_quantification_mode"),
        "puncta_contour_intensity_enabled": properties.get("puncta_contour_intensity_enabled"),
        "alternate_nucleus_detection_enabled": properties.get(
            "alternate_nucleus_detection_enabled"
        ),
        "alternate_nucleus_detection_channel": properties.get(
            "alternate_nucleus_detection_channel"
        ),
        "red_contour_count": properties.get("red_contour_count"),
        "green_contour_count": properties.get("green_contour_count"),
        "red_contour_count_source": properties.get("red_contour_count_source"),
        "green_contour_count_source": properties.get("green_contour_count_source"),
        "puncta_source_contour_count": properties.get("puncta_source_contour_count"),
        "puncta_source_contour_count_channel": properties.get(
            "puncta_source_contour_count_channel"
        ),
        "puncta_source_contour_count_source": properties.get(
            "puncta_source_contour_count_source"
        ),
        "puncta_distance": stat_value("puncta_distance", cell_stat.puncta_distance),
        "puncta_line_intensity": stat_value(
            "puncta_line_intensity",
            cell_stat.puncta_line_intensity,
        ),
        "blue_contour_size": stat_value("blue_contour_size", cell_stat.blue_contour_size),
        "blue_contour_center_xy": stat_value(
            "blue_contour_center_xy",
            contour_center_payloads["blue_contour_center_xy"],
        ),
        "red_contour_1_size": stat_value(
            "red_contour_1_size",
            cell_stat.red_contour_1_size,
        ),
        "red_contour_1_center_xy": stat_value(
            "red_contour_1_center_xy",
            contour_center_payloads["red_contour_1_center_xy"],
        ),
        "red_contour_2_size": stat_value(
            "red_contour_2_size",
            cell_stat.red_contour_2_size,
        ),
        "red_contour_2_center_xy": stat_value(
            "red_contour_2_center_xy",
            contour_center_payloads["red_contour_2_center_xy"],
        ),
        "red_contour_3_size": stat_value(
            "red_contour_3_size",
            cell_stat.red_contour_3_size,
        ),
        "red_contour_3_center_xy": stat_value(
            "red_contour_3_center_xy",
            contour_center_payloads["red_contour_3_center_xy"],
        ),
        **intensity_payload,
        "green_contour_1_size": stat_value(
            "green_contour_1_size",
            cell_stat.green_contour_1_size,
        ),
        "green_contour_1_center_xy": stat_value(
            "green_contour_1_center_xy",
            contour_center_payloads["green_contour_1_center_xy"],
        ),
        "green_contour_2_size": stat_value(
            "green_contour_2_size",
            cell_stat.green_contour_2_size,
        ),
        "green_contour_2_center_xy": stat_value(
            "green_contour_2_center_xy",
            contour_center_payloads["green_contour_2_center_xy"],
        ),
        "green_contour_3_size": stat_value(
            "green_contour_3_size",
            cell_stat.green_contour_3_size,
        ),
        "green_contour_3_center_xy": stat_value(
            "green_contour_3_center_xy",
            contour_center_payloads["green_contour_3_center_xy"],
        ),
        "distance_of_green_from_red_1": stat_value(
            "distance_of_green_from_red_1",
            cell_stat.distance_of_green_from_red_1,
        ),
        "distance_of_green_from_red_2": stat_value(
            "distance_of_green_from_red_2",
            cell_stat.distance_of_green_from_red_2,
        ),
        "distance_of_green_from_red_3": stat_value(
            "distance_of_green_from_red_3",
            cell_stat.distance_of_green_from_red_3,
        ),
        "puncta_distance_delta_x_px": properties.get("puncta_distance_delta_x_px")
        if puncta_enabled
        else None,
        "puncta_distance_delta_y_px": properties.get("puncta_distance_delta_y_px")
        if puncta_enabled
        else None,
        "distance_of_green_from_red_1_delta_x_px": properties.get(
            "distance_of_green_from_red_1_delta_x_px"
        )
        if red_green_enabled
        else None,
        "distance_of_green_from_red_1_delta_y_px": properties.get(
            "distance_of_green_from_red_1_delta_y_px"
        )
        if red_green_enabled
        else None,
        "distance_of_green_from_red_2_delta_x_px": properties.get(
            "distance_of_green_from_red_2_delta_x_px"
        )
        if red_green_enabled
        else None,
        "distance_of_green_from_red_2_delta_y_px": properties.get(
            "distance_of_green_from_red_2_delta_y_px"
        )
        if red_green_enabled
        else None,
        "distance_of_green_from_red_3_delta_x_px": properties.get(
            "distance_of_green_from_red_3_delta_x_px"
        )
        if red_green_enabled
        else None,
        "distance_of_green_from_red_3_delta_y_px": properties.get(
            "distance_of_green_from_red_3_delta_y_px"
        )
        if red_green_enabled
        else None,
        "nucleus_intensity_sum": stat_value(
            "nucleus_intensity_sum",
            cell_stat.nucleus_intensity_sum,
        ),
        "cell_pair_intensity_sum": stat_value(
            "cell_pair_intensity_sum",
            cell_stat.cell_pair_intensity_sum,
        ),
        "cytoplasmic_intensity": stat_value(
            "cytoplasmic_intensity",
            cell_stat.cytoplasmic_intensity,
        ),
        "nuclear_cytoplasmic_ratio": stat_value(
            "nuclear_cytoplasmic_ratio",
            cell_stat.nuclear_cytoplasmic_ratio,
        ),
        "cell_pair_intensity_sum_blue": stat_value(
            "cell_pair_intensity_sum_blue",
            cell_stat.cell_pair_intensity_sum_blue,
        ),
        "nucleus_intensity_sum_blue": stat_value(
            "nucleus_intensity_sum_blue",
            cell_stat.nucleus_intensity_sum_blue,
        ),
        "cytoplasmic_intensity_blue": stat_value(
            "cytoplasmic_intensity_blue",
            cell_stat.cytoplasmic_intensity_blue,
        ),
        "puncta_line_mode": puncta_line_metadata["mode"],
        "puncta_line_source_channel": normalize_channel_display_name(
            properties.get("puncta_line_source_channel"),
            default=puncta_line_metadata["source_label"],
        ),
        "puncta_line_measurement_channel": normalize_channel_display_name(
            properties.get("puncta_line_measurement_channel"),
            default=puncta_line_metadata["measurement_label"],
        ),
        "puncta_distance_label": puncta_line_metadata["distance_label"],
        "puncta_line_intensity_label": puncta_line_metadata["intensity_label"],
        "nuclear_cell_pair_mode": nuclear_cell_pair_mode,
        "nuclear_cell_pair_contour_channel": normalize_channel_display_name(
            properties.get(
                "nuclear_cell_pair_contour_channel",
                properties.get("nuclear_cellular_contour_channel"),
            ),
            default="Green",
        )
        if nuclear_enabled
        else "N/A",
        "nuclear_cell_pair_measurement_channel": normalize_channel_display_name(
            properties.get(
                "nuclear_cell_pair_measurement_channel",
                properties.get("nuclear_cellular_measurement_channel"),
            ),
            default="Red",
        )
        if nuclear_enabled
        else "N/A",
        "nuclear_cell_pair_contour_source": stat_value(
            "nuclear_cell_pair_contour_source",
            properties.get("nuclear_cell_pair_contour_source"),
        ),
        "nuclear_cell_pair_status": properties.get(
            "nuclear_cell_pair_status",
            properties.get("nuclear_cellular_status", "unknown"),
        )
        if nuclear_enabled
        else "N/A",
        "category_cen_dot": cell_stat.category_cen_dot if cen_dot_enabled else None,
        "cell_parentage": cell_parentage,
        "cell_parentage_label": cell_parentage.get("label", "Not identified"),
        "cell_parentage_status": cell_parentage.get("status", "not_identified"),
        "cell_parentage_mode": cell_parentage.get("mode"),
        "cell_parentage_method": cell_parentage.get("method"),
        "category_cen_dot_label": get_cen_dot_category_label(
            cell_stat.category_cen_dot,
            schema_version=properties.get("cen_dot_schema_version"),
        )
        if cen_dot_enabled
        else "N/A",
        "cen_dot_schema_version": properties.get("cen_dot_schema_version")
        if cen_dot_enabled
        else None,
        "cen_dot_location": properties.get("cen_dot_location") if cen_dot_enabled else None,
        "colinear_dots": cell_stat.colinear_dots if biorientation_enabled else None,
        "off_axis_dots": cell_stat.off_axis_dots if biorientation_enabled else None,
        **ratio_payload,
    }
