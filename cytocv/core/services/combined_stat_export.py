"""Build combined statistics exports for multiple files."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.http import HttpResponse
from django_tables2.export.export import TableExport
from tablib import Dataset

from core.models import CellStatistics
from core.scale import (
    format_spatial_stat_header,
    get_scale_context_payload,
    normalize_spatial_stats_unit,
)
from core.services.stat_export_selection import (
    export_exclude_columns,
    export_included_columns,
)
from core.services.export_filenames import build_statistics_export_filename
from core.tables import CellTable


EXPORT_FORMATS = {"csv", "xlsx"}


class CombinedStatisticsExportError(ValueError):
    """Raised when a combined export request cannot produce a file."""


@dataclass(frozen=True)
class StatisticsExportFile:
    """Source metadata needed to export one selected file."""

    uuid: str
    file_name: str
    segmented_image: Any
    scale_info: Any = None


def _generic_headers_for_fields(
    field_names: tuple[str, ...],
    *,
    spatial_stats_unit: str,
) -> list[str]:
    table = CellTable(
        [],
        intensity_mode=None,
        puncta_line_mode=None,
        spatial_stats_unit=spatial_stats_unit,
        scale_context=None,
    )
    labels = {
        field_name: str(table.columns[field_name].column.verbose_name)
        for field_name in field_names
        if field_name in table.columns
    }

    labels.update(
        {
            "cell_id": "Cell ID",
            "puncta_distance": format_spatial_stat_header(
                "Puncta Distance",
                spatial_kind="distance",
                unit=spatial_stats_unit,
            ),
            "puncta_line_intensity": "Puncta Line Intensity",
            "green_red_intensity_1": "Measurement/Contour Ratio 1",
            "green_red_intensity_2": "Measurement/Contour Ratio 2",
            "green_red_intensity_3": "Measurement/Contour Ratio 3",
            "cell_pair_intensity_sum": "Measured Cell-Pair Intensity",
            "nucleus_intensity_sum": "Measured Nuclear Intensity",
        }
    )
    return [labels.get(field_name, field_name.replace("_", " ").title()) for field_name in field_names]


def _table_rows_for_file(
    source: StatisticsExportFile,
    *,
    exclude_columns: tuple[str, ...],
    spatial_stats_unit: str,
    default_manual_scale: float,
) -> list[list[Any]]:
    stats_qs = CellStatistics.objects.filter(
        segmented_image=source.segmented_image,
    ).order_by("cell_id")
    if not stats_qs.exists():
        return []

    table = CellTable(
        stats_qs,
        intensity_mode=None,
        puncta_line_mode=None,
        spatial_stats_unit=spatial_stats_unit,
        scale_context=get_scale_context_payload(
            source.scale_info,
            manual_default=default_manual_scale,
        ),
    )
    rows = list(table.as_values(exclude_columns=exclude_columns))
    return [list(row) for row in rows[1:]]


def build_combined_statistics_export_response(
    sources: list[StatisticsExportFile],
    *,
    export_format: str,
    raw_columns: Any,
    spatial_stats_unit: str,
    default_manual_scale: float,
    export_scope: str = "selected",
) -> HttpResponse:
    """Return one CSV/XLSX attachment for the selected files."""

    if export_format not in EXPORT_FORMATS:
        raise CombinedStatisticsExportError("Choose CSV or Excel for this download.")
    if not sources:
        raise CombinedStatisticsExportError("Select at least one file to download.")

    unit = normalize_spatial_stats_unit(spatial_stats_unit, default="px")
    included_columns = export_included_columns(raw_columns, columns_present=True)
    if included_columns is None:
        raise CombinedStatisticsExportError("Select at least one statistic to export.")
    exclude_columns = export_exclude_columns(raw_columns, columns_present=True) or ()

    dataset = Dataset()
    dataset.headers = [
        "File Name",
        *_generic_headers_for_fields(included_columns, spatial_stats_unit=unit),
    ]
    row_count = 0
    for source in sources:
        rows = _table_rows_for_file(
            source,
            exclude_columns=exclude_columns,
            spatial_stats_unit=unit,
            default_manual_scale=default_manual_scale,
        )
        for row_index, row in enumerate(rows):
            file_name_cell = source.file_name if row_index == 0 else ""
            dataset.append([file_name_cell, *row])
            row_count += 1

    if row_count == 0:
        raise CombinedStatisticsExportError(
            "Selected files do not have statistics available to download."
        )

    filename = build_statistics_export_filename(
        scope=export_scope,
        file_count=len(sources),
        export_format=export_format,
    )
    response = HttpResponse(content_type=TableExport.FORMATS[export_format])
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write(dataset.export(export_format))
    return response
