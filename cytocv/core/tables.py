"""Table definitions for rendering and exporting cell statistics."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import django_tables2 as tables
from django_tables2 import SingleTableView
from django_tables2.export.views import ExportMixin

from core.cell_types import cell_type_from_statistics, cell_type_label
from core.models import CellStatistics, get_cen_dot_category_label
from core.scale import (
    convert_area_pixels_to_display_units,
    convert_distance_pixels_to_display_units,
    format_spatial_stat_header,
    normalize_spatial_stats_unit,
)
from core.services.measurement_contour_ratio import (
    calculate_measurement_contour_ratio_value,
    get_measurement_contour_ratio_headers,
    normalize_nuclear_cell_pair_mode,
)
from core.services.puncta_line_mode import get_puncta_line_mode_metadata
from core.services.cell_parentage import cell_parentage_payload_from_properties
from core.services.contour_coordinates import (
    BLUE_CONTOUR_PREFIX,
    GREEN_CONTOUR_PREFIXES,
    RED_CONTOUR_PREFIXES,
    format_contour_center_from_properties,
)
from core.services.stat_applicability import (
    STAT_FIELD_GROUPS,
    is_field_applicable,
    resolve_stat_visibility,
)


NUCLEAR_CELL_PAIR_LABELS = {
    "red_nucleus": ("Green Cell-Pair Intensity", "Green Nuclear Intensity"),
    "green_nucleus": ("Red Cell-Pair Intensity", "Red Nuclear Intensity"),
}
FALLBACK_NUCLEAR_CELL_PAIR_LABELS = ("Measured Cell-Pair Intensity", "Measured Nuclear Intensity")
EXPORT_DECIMAL_PLACES = Decimal("0.001")


class NumberColumn(tables.Column):
    """Format numeric values for display with fixed precision."""

    def __init__(self, *args, stat_field: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.stat_field = stat_field
        self.stat_visibility = None

    def render(self, value: float, record=None) -> str:
        """Render a numeric value with three decimal places."""
        if self.stat_field and record is not None and not is_field_applicable(
            record,
            self.stat_field,
            stat_visibility=self.stat_visibility,
        ):
            return "N/A"
        try:
            return "{:0.3f}".format(float(value))
        except (TypeError, ValueError):
            return "N/A"

    def value(self, value: float, record=None) -> str:
        return self.render(value, record=record)


class ChoiceLabelColumn(tables.Column):
    """Render stored choice codes using their human-readable labels."""

    def __init__(self, *args, stat_field: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.stat_field = stat_field
        self.stat_visibility = None

    @staticmethod
    def _schema_version(record) -> int | None:
        properties = getattr(record, "properties", {}) or {}
        return properties.get("cen_dot_schema_version")

    def render(self, value: int, record=None) -> str:
        if self.stat_field and record is not None and not is_field_applicable(
            record,
            self.stat_field,
            stat_visibility=self.stat_visibility,
        ):
            return "N/A"
        return get_cen_dot_category_label(value, schema_version=self._schema_version(record))

    def value(self, value: int, record=None) -> str:
        return self.render(value, record=record)


class CellTable(tables.Table):
    """Table layout for per-cell statistics used in UI and export."""

    # These field groups drive both browser rendering and export omission rules.
    # Keep names aligned with CellStatistics fields and serialized payload keys.
    SPATIAL_FIELDS = {
        "puncta_distance": "distance",
        "blue_contour_size": "area",
        "blue_contour_center_xy": "coordinate",
        "red_contour_1_size": "area",
        "red_contour_2_size": "area",
        "red_contour_3_size": "area",
        "red_contour_1_center_xy": "coordinate",
        "red_contour_2_center_xy": "coordinate",
        "red_contour_3_center_xy": "coordinate",
        "green_contour_1_size": "area",
        "green_contour_2_size": "area",
        "green_contour_3_size": "area",
        "green_contour_1_center_xy": "coordinate",
        "green_contour_2_center_xy": "coordinate",
        "green_contour_3_center_xy": "coordinate",
        "distance_of_green_from_red_1": "distance",
        "distance_of_green_from_red_2": "distance",
        "distance_of_green_from_red_3": "distance",
    }
    STAT_COLUMN_GROUPS = STAT_FIELD_GROUPS

    cell_id = tables.Column(verbose_name="Cell ID")
    cell_type = tables.Column(verbose_name="Cell Type", empty_values=())
    puncta_distance = NumberColumn(verbose_name="Distance Between Red Puncta")
    puncta_line_intensity = NumberColumn(verbose_name="Green Intensity Over Red Line")
    blue_contour_size = NumberColumn(verbose_name="Blue Contour Size")
    blue_contour_center_xy = tables.Column(
        verbose_name="Blue Contour Center (x,y)",
        empty_values=(),
    )

    red_contour_1_size = NumberColumn(verbose_name="Red Contour 1 Size")
    red_contour_1_center_xy = tables.Column(
        verbose_name="Red Contour 1 Center (x,y)",
        empty_values=(),
    )
    red_contour_2_size = NumberColumn(verbose_name="Red Contour 2 Size")
    red_contour_2_center_xy = tables.Column(
        verbose_name="Red Contour 2 Center (x,y)",
        empty_values=(),
    )
    red_contour_3_size = NumberColumn(verbose_name="Red Contour 3 Size")
    red_contour_3_center_xy = tables.Column(
        verbose_name="Red Contour 3 Center (x,y)",
        empty_values=(),
    )

    green_contour_1_size = NumberColumn(verbose_name="Green Contour 1 Size")
    green_contour_1_center_xy = tables.Column(
        verbose_name="Green Contour 1 Center (x,y)",
        empty_values=(),
    )
    green_contour_2_size = NumberColumn(verbose_name="Green Contour 2 Size")
    green_contour_2_center_xy = tables.Column(
        verbose_name="Green Contour 2 Center (x,y)",
        empty_values=(),
    )
    green_contour_3_size = NumberColumn(verbose_name="Green Contour 3 Size")
    green_contour_3_center_xy = tables.Column(
        verbose_name="Green Contour 3 Center (x,y)",
        empty_values=(),
    )

    red_in_red_total_intensity_1 = NumberColumn(verbose_name="Red In Red Total Intensity 1")
    red_in_red_max_intensity_1 = NumberColumn(verbose_name="Red In Red Max Intensity 1")
    red_in_red_average_intensity_1 = NumberColumn(verbose_name="Red In Red Average Intensity 1")
    red_in_red_total_intensity_2 = NumberColumn(verbose_name="Red In Red Total Intensity 2")
    red_in_red_max_intensity_2 = NumberColumn(verbose_name="Red In Red Max Intensity 2")
    red_in_red_average_intensity_2 = NumberColumn(verbose_name="Red In Red Average Intensity 2")
    red_in_red_total_intensity_3 = NumberColumn(verbose_name="Red In Red Total Intensity 3")
    red_in_red_max_intensity_3 = NumberColumn(verbose_name="Red In Red Max Intensity 3")
    red_in_red_average_intensity_3 = NumberColumn(verbose_name="Red In Red Average Intensity 3")

    green_in_red_total_intensity_1 = NumberColumn(verbose_name="Green In Red Total Intensity 1")
    green_in_red_max_intensity_1 = NumberColumn(verbose_name="Green In Red Max Intensity 1")
    green_in_red_average_intensity_1 = NumberColumn(verbose_name="Green In Red Average Intensity 1")
    green_in_red_total_intensity_2 = NumberColumn(verbose_name="Green In Red Total Intensity 2")
    green_in_red_max_intensity_2 = NumberColumn(verbose_name="Green In Red Max Intensity 2")
    green_in_red_average_intensity_2 = NumberColumn(verbose_name="Green In Red Average Intensity 2")
    green_in_red_total_intensity_3 = NumberColumn(verbose_name="Green In Red Total Intensity 3")
    green_in_red_max_intensity_3 = NumberColumn(verbose_name="Green In Red Max Intensity 3")
    green_in_red_average_intensity_3 = NumberColumn(verbose_name="Green In Red Average Intensity 3")

    red_in_green_total_intensity_1 = NumberColumn(verbose_name="Red In Green Total Intensity 1")
    red_in_green_max_intensity_1 = NumberColumn(verbose_name="Red In Green Max Intensity 1")
    red_in_green_average_intensity_1 = NumberColumn(verbose_name="Red In Green Average Intensity 1")
    red_in_green_total_intensity_2 = NumberColumn(verbose_name="Red In Green Total Intensity 2")
    red_in_green_max_intensity_2 = NumberColumn(verbose_name="Red In Green Max Intensity 2")
    red_in_green_average_intensity_2 = NumberColumn(verbose_name="Red In Green Average Intensity 2")
    red_in_green_total_intensity_3 = NumberColumn(verbose_name="Red In Green Total Intensity 3")
    red_in_green_max_intensity_3 = NumberColumn(verbose_name="Red In Green Max Intensity 3")
    red_in_green_average_intensity_3 = NumberColumn(verbose_name="Red In Green Average Intensity 3")

    green_in_green_total_intensity_1 = NumberColumn(verbose_name="Green In Green Total Intensity 1")
    green_in_green_max_intensity_1 = NumberColumn(verbose_name="Green In Green Max Intensity 1")
    green_in_green_average_intensity_1 = NumberColumn(verbose_name="Green In Green Average Intensity 1")
    green_in_green_total_intensity_2 = NumberColumn(verbose_name="Green In Green Total Intensity 2")
    green_in_green_max_intensity_2 = NumberColumn(verbose_name="Green In Green Max Intensity 2")
    green_in_green_average_intensity_2 = NumberColumn(verbose_name="Green In Green Average Intensity 2")
    green_in_green_total_intensity_3 = NumberColumn(verbose_name="Green In Green Total Intensity 3")
    green_in_green_max_intensity_3 = NumberColumn(verbose_name="Green In Green Max Intensity 3")
    green_in_green_average_intensity_3 = NumberColumn(verbose_name="Green In Green Average Intensity 3")

    green_red_intensity_1 = NumberColumn(verbose_name="Measurement/Contour Ratio 1")
    green_red_intensity_2 = NumberColumn(verbose_name="Measurement/Contour Ratio 2")
    green_red_intensity_3 = NumberColumn(verbose_name="Measurement/Contour Ratio 3")

    distance_of_green_from_red_1 = NumberColumn(verbose_name="Distance Of Green From Red 1")
    distance_of_green_from_red_2 = NumberColumn(verbose_name="Distance Of Green From Red 2")
    distance_of_green_from_red_3 = NumberColumn(verbose_name="Distance Of Green From Red 3")

    nuclear_cell_pair_contour_source = tables.Column(
        verbose_name="Nucleus Contour Source",
        empty_values=(),
    )
    cell_pair_intensity_sum = NumberColumn(verbose_name=FALLBACK_NUCLEAR_CELL_PAIR_LABELS[0])
    nucleus_intensity_sum = NumberColumn(verbose_name=FALLBACK_NUCLEAR_CELL_PAIR_LABELS[1])
    cytoplasmic_intensity = NumberColumn(verbose_name="Cytoplasmic Intensity")
    nuclear_cytoplasmic_ratio = NumberColumn(
        verbose_name="Nuclear / Cytoplasmic Ratio",
        empty_values=(),
    )

    cell_parentage = tables.Column(verbose_name="Cell Parentage", empty_values=())
    category_cen_dot = ChoiceLabelColumn(
        verbose_name="Cen Dot Location",
        stat_field="category_cen_dot",
    )
    colinear_dots = tables.Column(verbose_name="Colinear Dots")
    off_axis_dots = tables.Column(verbose_name="Off Axis Dots")

    class Meta:
        attrs = {"class": "celltable", "id": "celltable"}
        model = CellStatistics
        orderable = False
        fields = (
            "cell_id",
            "cell_type",
            "puncta_distance",
            "puncta_line_intensity",
            "blue_contour_size",
            "blue_contour_center_xy",
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
            "distance_of_green_from_red_1",
            "distance_of_green_from_red_2",
            "distance_of_green_from_red_3",
            "nuclear_cell_pair_contour_source",
            "cell_pair_intensity_sum",
            "nucleus_intensity_sum",
            "cytoplasmic_intensity",
            "nuclear_cytoplasmic_ratio",
            "cell_parentage",
            "category_cen_dot",
            "colinear_dots",
            "off_axis_dots",
        )
        template_name = "django_tables2/semantic.html"

    def __init__(
        self,
        *args,
        intensity_mode: str | None = None,
        puncta_line_mode: str | None = None,
        stat_visibility: dict[str, bool] | None = None,
        selected_plugins: list[str] | tuple[str, ...] | None = None,
        spatial_stats_unit: str = "px",
        scale_context: dict[str, object] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        # Resolve visibility once per table instance so hidden plugin groups render
        # as N/A consistently across HTML cells and export values.
        self._resolved_stat_visibility = self._resolve_stat_visibility(
            args[0] if args else kwargs.get("data"),
            stat_visibility=stat_visibility,
            selected_plugins=selected_plugins,
        )
        for field_names in self.STAT_COLUMN_GROUPS.values():
            for field_name in field_names:
                if field_name in self.columns and isinstance(
                    self.columns[field_name].column,
                    NumberColumn,
                ):
                    self.columns[field_name].column.stat_field = field_name
                    self.columns[field_name].column.stat_visibility = (
                        self._resolved_stat_visibility
                    )
        self.columns["category_cen_dot"].column.stat_visibility = (
            self._resolved_stat_visibility
        )
        self._spatial_stats_unit = normalize_spatial_stats_unit(spatial_stats_unit, default="px")
        resolved_scale_context = dict(scale_context or {})
        self._scale_context = {
            "effective_um_per_px": resolved_scale_context.get("effective_um_per_px", 0.1),
            "x_um_per_px": resolved_scale_context.get("x_um_per_px", 0.1),
            "y_um_per_px": resolved_scale_context.get("y_um_per_px", 0.1),
        }
        self._intensity_mode = (
            normalize_nuclear_cell_pair_mode(intensity_mode)
            if intensity_mode in NUCLEAR_CELL_PAIR_LABELS
            else None
        )
        cellular_label, nuclear_label = NUCLEAR_CELL_PAIR_LABELS.get(
            self._intensity_mode,
            FALLBACK_NUCLEAR_CELL_PAIR_LABELS,
        )
        # Column labels are user-facing contract text in exports, so mode-specific
        # labels are applied without reordering fields.
        ratio_headers = get_measurement_contour_ratio_headers(self._intensity_mode)
        puncta_headers = get_puncta_line_mode_metadata(puncta_line_mode)
        self.columns["cell_pair_intensity_sum"].column.verbose_name = cellular_label
        self.columns["nucleus_intensity_sum"].column.verbose_name = nuclear_label
        self.columns["puncta_distance"].column.verbose_name = puncta_headers["distance_label"]
        self.columns["puncta_line_intensity"].column.verbose_name = puncta_headers["intensity_label"]
        self.columns["green_red_intensity_1"].column.verbose_name = ratio_headers[0]
        self.columns["green_red_intensity_2"].column.verbose_name = ratio_headers[1]
        self.columns["green_red_intensity_3"].column.verbose_name = ratio_headers[2]
        for field_name, spatial_kind in self.SPATIAL_FIELDS.items():
            if field_name not in self.columns:
                continue
            column = self.columns[field_name].column
            column.verbose_name = format_spatial_stat_header(
                str(column.verbose_name),
                spatial_kind=spatial_kind,
                unit=self._spatial_stats_unit,
            )

    @classmethod
    def _resolve_stat_visibility(
        cls,
        data,
        *,
        stat_visibility: dict[str, bool] | None = None,
        selected_plugins: list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, bool]:
        return resolve_stat_visibility(
            data,
            stat_visibility=stat_visibility,
            selected_plugins=selected_plugins,
        )

    def _field_is_applicable(self, record: CellStatistics, field_name: str) -> bool:
        return is_field_applicable(
            record,
            field_name,
            stat_visibility=self._resolved_stat_visibility,
        )

    @staticmethod
    def _has_no_nucleus_contour(record: CellStatistics) -> bool:
        properties = getattr(record, "properties", {}) or {}
        return properties.get(
            "nuclear_cell_pair_status",
            properties.get("nuclear_cellular_status"),
        ) == "no_nucleus_contour"

    @staticmethod
    def _format_number(value: float) -> str:
        try:
            return "{:0.3f}".format(float(value))
        except (TypeError, ValueError):
            return "N/A"

    @staticmethod
    def _export_decimal(value: float) -> Decimal | str:
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return "N/A"
        if not decimal_value.is_finite():
            return "N/A"
        return decimal_value.quantize(EXPORT_DECIMAL_PLACES)

    @staticmethod
    def _export_int(value: int) -> int | str:
        try:
            return int(value)
        except (TypeError, ValueError):
            return "N/A"

    def _export_spatial_value(
        self,
        field_name: str,
        value: float,
        record: CellStatistics,
    ) -> Decimal | str:
        if not self._field_is_applicable(record, field_name):
            return "N/A"
        return self._export_decimal(
            self._converted_spatial_value(field_name, value, record)
        )

    def _export_nuclear_cell_pair_value(
        self,
        record: CellStatistics,
        value: float,
    ) -> Decimal | str:
        if not self._field_is_applicable(record, "cell_pair_intensity_sum"):
            return "N/A"
        if self._has_no_nucleus_contour(record):
            return "N/A"
        return self._export_decimal(value)

    def _export_measurement_contour_ratio_value(
        self,
        record: CellStatistics,
        index: int,
        field_name: str,
    ) -> Decimal | str:
        if not self._field_is_applicable(record, field_name):
            return "N/A"
        return self._export_decimal(self._measurement_contour_ratio_value(record, index))

    def _export_generic_number(
        self,
        field_name: str,
        value: float,
        record: CellStatistics,
    ) -> Decimal | str:
        column = self.columns[field_name].column
        if (
            isinstance(column, NumberColumn)
            and column.stat_field
            and not self._field_is_applicable(record, column.stat_field)
        ):
            return "N/A"
        return self._export_decimal(value)

    def _export_cell_value(self, field_name: str, row, record: CellStatistics):
        # Export values intentionally route through the same applicability and unit
        # conversion helpers as table rendering while preserving field order.
        if field_name == "cell_id":
            return self._export_int(getattr(record, field_name, None))
        if field_name == "cell_type":
            return cell_type_label(cell_type_from_statistics(record))

        if (
            field_name in self.SPATIAL_FIELDS
            and self.SPATIAL_FIELDS[field_name] != "coordinate"
        ):
            return self._export_spatial_value(
                field_name,
                getattr(record, field_name, None),
                record,
            )

        if field_name in {
            "cell_pair_intensity_sum",
            "nucleus_intensity_sum",
            "cytoplasmic_intensity",
            "nuclear_cytoplasmic_ratio",
        }:
            return self._export_nuclear_cell_pair_value(
                record,
                getattr(record, field_name, None),
            )

        ratio_fields = {
            "green_red_intensity_1": 1,
            "green_red_intensity_2": 2,
            "green_red_intensity_3": 3,
        }
        if field_name in ratio_fields:
            return self._export_measurement_contour_ratio_value(
                record,
                ratio_fields[field_name],
                field_name,
            )

        if field_name in {"colinear_dots", "off_axis_dots"}:
            if not self._field_is_applicable(record, field_name):
                return "N/A"
            return self._export_int(getattr(record, field_name, None))

        if field_name in self.columns and isinstance(
            self.columns[field_name].column,
            NumberColumn,
        ):
            return self._export_generic_number(
                field_name,
                getattr(record, field_name, None),
                record,
            )

        return row.get_cell_value(field_name)

    def render_cell_type(self, record: CellStatistics) -> str:
        return cell_type_label(cell_type_from_statistics(record))

    def value_cell_type(self, record: CellStatistics) -> str:
        return self.render_cell_type(record)

    def render_cell_parentage(self, record: CellStatistics) -> str:
        if not self._field_is_applicable(record, "cell_parentage"):
            return "N/A"
        return cell_parentage_payload_from_properties(
            getattr(record, "properties", {}) or {}
        ).get("label", "Not identified")

    def value_cell_parentage(self, record: CellStatistics) -> str:
        return self.render_cell_parentage(record)

    def _converted_spatial_value(
        self,
        field_name: str,
        value: float,
        record: CellStatistics,
    ) -> float | None:
        spatial_kind = self.SPATIAL_FIELDS.get(field_name)
        if spatial_kind == "area":
            return convert_area_pixels_to_display_units(
                value,
                unit=self._spatial_stats_unit,
                x_um_per_px=self._scale_context["x_um_per_px"],
                y_um_per_px=self._scale_context["y_um_per_px"],
            )

        if spatial_kind == "distance":
            properties = getattr(record, "properties", {}) or {}
            return convert_distance_pixels_to_display_units(
                value,
                unit=self._spatial_stats_unit,
                effective_um_per_px=self._scale_context["effective_um_per_px"],
                x_um_per_px=self._scale_context["x_um_per_px"],
                y_um_per_px=self._scale_context["y_um_per_px"],
                delta_x_px=properties.get(f"{field_name}_delta_x_px"),
                delta_y_px=properties.get(f"{field_name}_delta_y_px"),
            )

        return value

    def _render_spatial_value(self, field_name: str, value: float, record: CellStatistics) -> str:
        if not self._field_is_applicable(record, field_name):
            return "N/A"
        return self._format_number(self._converted_spatial_value(field_name, value, record))

    def _render_contour_center_value(
        self,
        field_name: str,
        contour_prefix: str,
        record: CellStatistics,
    ) -> str:
        if not self._field_is_applicable(record, field_name):
            return "N/A"
        return format_contour_center_from_properties(
            getattr(record, "properties", {}) or {},
            contour_prefix,
            unit=self._spatial_stats_unit,
            x_um_per_px=self._scale_context["x_um_per_px"],
            y_um_per_px=self._scale_context["y_um_per_px"],
        )

    def _render_nuclear_cell_pair_value(self, record: CellStatistics, value: float) -> str:
        if not self._field_is_applicable(record, "cell_pair_intensity_sum"):
            return "N/A"
        if self._has_no_nucleus_contour(record):
            return "N/A"
        return self._format_number(value)

    @staticmethod
    def _nuclear_cell_pair_contour_source(record: CellStatistics) -> str:
        properties = getattr(record, "properties", {}) or {}
        value = properties.get("nuclear_cell_pair_contour_source")
        return str(value or "N/A")

    def render_nuclear_cell_pair_contour_source(self, record: CellStatistics) -> str:
        if not self._field_is_applicable(record, "nuclear_cell_pair_contour_source"):
            return "N/A"
        return self._nuclear_cell_pair_contour_source(record)

    def value_nuclear_cell_pair_contour_source(self, record: CellStatistics) -> str:
        if not self._field_is_applicable(record, "nuclear_cell_pair_contour_source"):
            return "N/A"
        return self._nuclear_cell_pair_contour_source(record)

    def render_cell_pair_intensity_sum(self, value: float, record: CellStatistics) -> str:
        return self._render_nuclear_cell_pair_value(record, value)

    def value_cell_pair_intensity_sum(self, value: float, record: CellStatistics) -> str:
        return self._render_nuclear_cell_pair_value(record, value)

    def render_nucleus_intensity_sum(self, value: float, record: CellStatistics) -> str:
        return self._render_nuclear_cell_pair_value(record, value)

    def value_nucleus_intensity_sum(self, value: float, record: CellStatistics) -> str:
        return self._render_nuclear_cell_pair_value(record, value)

    def render_cytoplasmic_intensity(self, value: float, record: CellStatistics) -> str:
        return self._render_nuclear_cell_pair_value(record, value)

    def value_cytoplasmic_intensity(self, value: float, record: CellStatistics) -> str:
        return self._render_nuclear_cell_pair_value(record, value)

    def render_nuclear_cytoplasmic_ratio(self, value: float, record: CellStatistics) -> str:
        return self._render_nuclear_cell_pair_value(record, value)

    def value_nuclear_cytoplasmic_ratio(self, value: float, record: CellStatistics) -> str:
        return self._render_nuclear_cell_pair_value(record, value)

    def _measurement_contour_ratio_value(self, record: CellStatistics, index: int) -> float:
        properties = getattr(record, "properties", {}) or {}
        record_mode = properties.get(
            "nuclear_cell_pair_mode",
            properties.get("nuclear_cellular_mode"),
        )
        return calculate_measurement_contour_ratio_value(
            record,
            index,
            mode=record_mode or self._intensity_mode,
        )

    def render_green_red_intensity_1(self, record: CellStatistics) -> str:
        if not self._field_is_applicable(record, "green_red_intensity_1"):
            return "N/A"
        return self._format_number(self._measurement_contour_ratio_value(record, 1))

    def value_green_red_intensity_1(self, record: CellStatistics) -> str:
        if not self._field_is_applicable(record, "green_red_intensity_1"):
            return "N/A"
        return self._format_number(self._measurement_contour_ratio_value(record, 1))

    def render_green_red_intensity_2(self, record: CellStatistics) -> str:
        if not self._field_is_applicable(record, "green_red_intensity_2"):
            return "N/A"
        return self._format_number(self._measurement_contour_ratio_value(record, 2))

    def value_green_red_intensity_2(self, record: CellStatistics) -> str:
        if not self._field_is_applicable(record, "green_red_intensity_2"):
            return "N/A"
        return self._format_number(self._measurement_contour_ratio_value(record, 2))

    def render_green_red_intensity_3(self, record: CellStatistics) -> str:
        if not self._field_is_applicable(record, "green_red_intensity_3"):
            return "N/A"
        return self._format_number(self._measurement_contour_ratio_value(record, 3))

    def value_green_red_intensity_3(self, record: CellStatistics) -> str:
        if not self._field_is_applicable(record, "green_red_intensity_3"):
            return "N/A"
        return self._format_number(self._measurement_contour_ratio_value(record, 3))

    def render_puncta_distance(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("puncta_distance", value, record)

    def value_puncta_distance(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("puncta_distance", value, record)

    def render_blue_contour_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("blue_contour_size", value, record)

    def value_blue_contour_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("blue_contour_size", value, record)

    def render_blue_contour_center_xy(self, record: CellStatistics) -> str:
        return self._render_contour_center_value(
            "blue_contour_center_xy",
            BLUE_CONTOUR_PREFIX,
            record,
        )

    def value_blue_contour_center_xy(self, record: CellStatistics) -> str:
        return self.render_blue_contour_center_xy(record)

    def render_red_contour_1_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("red_contour_1_size", value, record)

    def value_red_contour_1_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("red_contour_1_size", value, record)

    def render_red_contour_1_center_xy(self, record: CellStatistics) -> str:
        return self._render_contour_center_value(
            "red_contour_1_center_xy",
            RED_CONTOUR_PREFIXES[0],
            record,
        )

    def value_red_contour_1_center_xy(self, record: CellStatistics) -> str:
        return self.render_red_contour_1_center_xy(record)

    def render_red_contour_2_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("red_contour_2_size", value, record)

    def value_red_contour_2_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("red_contour_2_size", value, record)

    def render_red_contour_2_center_xy(self, record: CellStatistics) -> str:
        return self._render_contour_center_value(
            "red_contour_2_center_xy",
            RED_CONTOUR_PREFIXES[1],
            record,
        )

    def value_red_contour_2_center_xy(self, record: CellStatistics) -> str:
        return self.render_red_contour_2_center_xy(record)

    def render_red_contour_3_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("red_contour_3_size", value, record)

    def value_red_contour_3_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("red_contour_3_size", value, record)

    def render_red_contour_3_center_xy(self, record: CellStatistics) -> str:
        return self._render_contour_center_value(
            "red_contour_3_center_xy",
            RED_CONTOUR_PREFIXES[2],
            record,
        )

    def value_red_contour_3_center_xy(self, record: CellStatistics) -> str:
        return self.render_red_contour_3_center_xy(record)

    def render_green_contour_1_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("green_contour_1_size", value, record)

    def value_green_contour_1_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("green_contour_1_size", value, record)

    def render_green_contour_1_center_xy(self, record: CellStatistics) -> str:
        return self._render_contour_center_value(
            "green_contour_1_center_xy",
            GREEN_CONTOUR_PREFIXES[0],
            record,
        )

    def value_green_contour_1_center_xy(self, record: CellStatistics) -> str:
        return self.render_green_contour_1_center_xy(record)

    def render_green_contour_2_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("green_contour_2_size", value, record)

    def value_green_contour_2_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("green_contour_2_size", value, record)

    def render_green_contour_2_center_xy(self, record: CellStatistics) -> str:
        return self._render_contour_center_value(
            "green_contour_2_center_xy",
            GREEN_CONTOUR_PREFIXES[1],
            record,
        )

    def value_green_contour_2_center_xy(self, record: CellStatistics) -> str:
        return self.render_green_contour_2_center_xy(record)

    def render_green_contour_3_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("green_contour_3_size", value, record)

    def value_green_contour_3_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("green_contour_3_size", value, record)

    def render_green_contour_3_center_xy(self, record: CellStatistics) -> str:
        return self._render_contour_center_value(
            "green_contour_3_center_xy",
            GREEN_CONTOUR_PREFIXES[2],
            record,
        )

    def value_green_contour_3_center_xy(self, record: CellStatistics) -> str:
        return self.render_green_contour_3_center_xy(record)

    def render_distance_of_green_from_red_1(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("distance_of_green_from_red_1", value, record)

    def value_distance_of_green_from_red_1(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("distance_of_green_from_red_1", value, record)

    def render_distance_of_green_from_red_2(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("distance_of_green_from_red_2", value, record)

    def value_distance_of_green_from_red_2(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("distance_of_green_from_red_2", value, record)

    def render_distance_of_green_from_red_3(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("distance_of_green_from_red_3", value, record)

    def value_distance_of_green_from_red_3(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("distance_of_green_from_red_3", value, record)

    def render_colinear_dots(self, value: int, record: CellStatistics) -> str:
        if not self._field_is_applicable(record, "colinear_dots"):
            return "N/A"
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return "N/A"

    def value_colinear_dots(self, value: int, record: CellStatistics) -> str:
        return self.render_colinear_dots(value, record)

    def render_off_axis_dots(self, value: int, record: CellStatistics) -> str:
        if not self._field_is_applicable(record, "off_axis_dots"):
            return "N/A"
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return "N/A"

    def value_off_axis_dots(self, value: int, record: CellStatistics) -> str:
        return self.render_off_axis_dots(value, record)

    def as_values(self, exclude_columns=None):
        if exclude_columns is None:
            exclude_columns = ()

        columns = [
            column
            for column in self.columns.iterall()
            if not (column.column.exclude_from_export or column.name in exclude_columns)
        ]

        yield [str(column.header) for column in columns]

        for row in self.rows:
            yield [
                self._export_cell_value(column.name, row, row.record)
                for column in columns
            ]

class CellTableView(ExportMixin, SingleTableView):
    """Table view with CSV/XLSX export support for cell statistics."""

    model = CellStatistics
    table_class = CellTable
    export_formats = ["csv", "xlsx"]
