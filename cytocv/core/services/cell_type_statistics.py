"""Cell-type-specific statistics cleanup helpers."""

from __future__ import annotations

from core.models import CategoryCENDot, CellStatistics


def mark_single_cell_pair_specific_statistics_na(cell_stat: CellStatistics) -> None:
    """Clear pair-specific derived fields for a retained single-cell row."""

    cell_stat.category_cen_dot = CategoryCENDot.NONE
    cell_stat.colinear_dots = 0
    cell_stat.off_axis_dots = 0
    cell_stat.nucleus_intensity_sum = 0.0
    cell_stat.cell_pair_intensity_sum = 0.0
    cell_stat.cytoplasmic_intensity = 0.0
    cell_stat.nuclear_cytoplasmic_ratio = None
    cell_stat.properties = dict(cell_stat.properties or {})
    cell_stat.properties["cell_parentage"] = {
        "label": "N/A",
        "status": "not_applicable",
        "mode": None,
        "method": None,
    }
    cell_stat.properties["nuclear_cell_pair_status"] = "not_applicable"
    visibility = dict(cell_stat.properties.get("stat_visibility") or {})
    for group_name in ("nuclear_cell_pair_intensity", "cen_dot", "biorientation"):
        visibility[group_name] = False
    cell_stat.properties["stat_visibility"] = visibility
