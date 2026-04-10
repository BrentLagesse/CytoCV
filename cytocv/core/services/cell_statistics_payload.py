"""Serialization helpers for renamed cell statistics payloads."""

from __future__ import annotations

from typing import Any

from core.channel_roles import channel_display_label, normalize_channel_role
from core.models import CellStatistics, get_cen_dot_category_label
from core.services.measurement_contour_ratio import (
    build_measurement_contour_ratio_payload,
    normalize_nuclear_cell_pair_mode,
)
from core.services.puncta_line_mode import get_puncta_line_mode_metadata


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
    nuclear_cell_pair_mode = normalize_nuclear_cell_pair_mode(
        properties.get("nuclear_cell_pair_mode", properties.get("nuclear_cellular_mode"))
    )
    puncta_line_metadata = get_puncta_line_mode_metadata(
        properties.get("puncta_line_mode")
    )

    return {
        "puncta_distance": cell_stat.puncta_distance,
        "puncta_line_intensity": cell_stat.puncta_line_intensity,
        "blue_contour_size": cell_stat.blue_contour_size,
        "red_contour_1_size": cell_stat.red_contour_1_size,
        "red_contour_2_size": cell_stat.red_contour_2_size,
        "red_contour_3_size": cell_stat.red_contour_3_size,
        "red_intensity_1": cell_stat.red_intensity_1,
        "red_intensity_2": cell_stat.red_intensity_2,
        "red_intensity_3": cell_stat.red_intensity_3,
        "green_intensity_1": cell_stat.green_intensity_1,
        "green_intensity_2": cell_stat.green_intensity_2,
        "green_intensity_3": cell_stat.green_intensity_3,
        "red_in_green_intensity_1": cell_stat.red_in_green_intensity_1,
        "red_in_green_intensity_2": cell_stat.red_in_green_intensity_2,
        "red_in_green_intensity_3": cell_stat.red_in_green_intensity_3,
        "green_in_green_intensity_1": cell_stat.green_in_green_intensity_1,
        "green_in_green_intensity_2": cell_stat.green_in_green_intensity_2,
        "green_in_green_intensity_3": cell_stat.green_in_green_intensity_3,
        "green_contour_1_size": cell_stat.green_contour_1_size,
        "green_contour_2_size": cell_stat.green_contour_2_size,
        "green_contour_3_size": cell_stat.green_contour_3_size,
        "distance_of_green_from_red_1": cell_stat.distance_of_green_from_red_1,
        "distance_of_green_from_red_2": cell_stat.distance_of_green_from_red_2,
        "distance_of_green_from_red_3": cell_stat.distance_of_green_from_red_3,
        "puncta_distance_delta_x_px": properties.get("puncta_distance_delta_x_px"),
        "puncta_distance_delta_y_px": properties.get("puncta_distance_delta_y_px"),
        "distance_of_green_from_red_1_delta_x_px": properties.get(
            "distance_of_green_from_red_1_delta_x_px"
        ),
        "distance_of_green_from_red_1_delta_y_px": properties.get(
            "distance_of_green_from_red_1_delta_y_px"
        ),
        "distance_of_green_from_red_2_delta_x_px": properties.get(
            "distance_of_green_from_red_2_delta_x_px"
        ),
        "distance_of_green_from_red_2_delta_y_px": properties.get(
            "distance_of_green_from_red_2_delta_y_px"
        ),
        "distance_of_green_from_red_3_delta_x_px": properties.get(
            "distance_of_green_from_red_3_delta_x_px"
        ),
        "distance_of_green_from_red_3_delta_y_px": properties.get(
            "distance_of_green_from_red_3_delta_y_px"
        ),
        "nucleus_intensity_sum": cell_stat.nucleus_intensity_sum,
        "cell_pair_intensity_sum": cell_stat.cell_pair_intensity_sum,
        "cytoplasmic_intensity": cell_stat.cytoplasmic_intensity,
        "cell_pair_intensity_sum_blue": cell_stat.cell_pair_intensity_sum_blue,
        "nucleus_intensity_sum_blue": cell_stat.nucleus_intensity_sum_blue,
        "cytoplasmic_intensity_blue": cell_stat.cytoplasmic_intensity_blue,
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
        ),
        "nuclear_cell_pair_measurement_channel": normalize_channel_display_name(
            properties.get(
                "nuclear_cell_pair_measurement_channel",
                properties.get("nuclear_cellular_measurement_channel"),
            ),
            default="Red",
        ),
        "nuclear_cell_pair_status": properties.get(
            "nuclear_cell_pair_status",
            properties.get("nuclear_cellular_status", "unknown"),
        ),
        "category_cen_dot": cell_stat.category_cen_dot,
        "category_cen_dot_label": get_cen_dot_category_label(cell_stat.category_cen_dot),
        "biorientation": cell_stat.biorientation,
        **build_measurement_contour_ratio_payload(
            cell_stat,
            mode=nuclear_cell_pair_mode,
        ),
    }
