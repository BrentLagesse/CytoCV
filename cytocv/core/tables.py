"""Table definitions for rendering and exporting cell statistics."""

from __future__ import annotations

import django_tables2 as tables
from django_tables2 import SingleTableView
from django_tables2.export.views import ExportMixin

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
from core.services.signal_quantification import build_stat_visibility


NUCLEAR_CELL_PAIR_LABELS = {
    "red_nucleus": ("Green Cell-Pair Intensity", "Green Nuclear Intensity"),
    "green_nucleus": ("Red Cell-Pair Intensity", "Red Nuclear Intensity"),
}
FALLBACK_NUCLEAR_CELL_PAIR_LABELS = ("Measured Cell-Pair Intensity", "Measured Nuclear Intensity")


class NumberColumn(tables.Column):
    """Format numeric values for display with fixed precision."""

    def render(self, value: float) -> str:
        """Render a numeric value with three decimal places."""
        try:
            return "{:0.3f}".format(float(value))
        except (TypeError, ValueError):
            return "N/A"


class ChoiceLabelColumn(tables.Column):
    """Render stored choice codes using their human-readable labels."""

    @staticmethod
    def _schema_version(record) -> int | None:
        properties = getattr(record, "properties", {}) or {}
        return properties.get("cen_dot_schema_version")

    def render(self, value: int, record=None) -> str:
        return get_cen_dot_category_label(value, schema_version=self._schema_version(record))

    def value(self, value: int, record=None) -> str:
        return self.render(value, record=record)


class CellTable(tables.Table):
    """Table layout for per-cell statistics used in UI and export."""

    SPATIAL_FIELDS = {
        "puncta_distance": "distance",
        "blue_contour_size": "area",
        "red_contour_1_size": "area",
        "red_contour_2_size": "area",
        "red_contour_3_size": "area",
        "green_contour_1_size": "area",
        "green_contour_2_size": "area",
        "green_contour_3_size": "area",
        "distance_of_green_from_red_1": "distance",
        "distance_of_green_from_red_2": "distance",
        "distance_of_green_from_red_3": "distance",
    }
    STAT_COLUMN_GROUPS = {
        "puncta_distance": (
            "puncta_distance",
            "puncta_line_intensity",
        ),
        "red_green_intensity": (
            "red_contour_1_size",
            "red_contour_2_size",
            "red_contour_3_size",
            "green_contour_1_size",
            "green_contour_2_size",
            "green_contour_3_size",
            "red_intensity_1",
            "red_intensity_2",
            "red_intensity_3",
            "green_intensity_1",
            "green_intensity_2",
            "green_intensity_3",
            "red_in_green_intensity_1",
            "red_in_green_intensity_2",
            "red_in_green_intensity_3",
            "green_in_green_intensity_1",
            "green_in_green_intensity_2",
            "green_in_green_intensity_3",
            "green_red_intensity_1",
            "green_red_intensity_2",
            "green_red_intensity_3",
            "distance_of_green_from_red_1",
            "distance_of_green_from_red_2",
            "distance_of_green_from_red_3",
        ),
        "nuclear_cell_pair_intensity": (
            "nuclear_cell_pair_contour_source",
            "cell_pair_intensity_sum",
            "nucleus_intensity_sum",
            "cytoplasmic_intensity",
        ),
        "cen_dot": ("cell_parentage", "category_cen_dot"),
        "biorientation": ("colinear_dots", "off_axis_dots"),
        "legacy_blue_intensity": ("blue_contour_size",),
    }

    cell_id = tables.Column(verbose_name="Cell ID")
    puncta_distance = NumberColumn(verbose_name="Distance Between Red Puncta")
    puncta_line_intensity = NumberColumn(verbose_name="Green Intensity Over Red Line")
    blue_contour_size = NumberColumn(verbose_name="Blue Contour Size")

    red_contour_1_size = NumberColumn(verbose_name="Red Contour 1 Size")
    red_contour_2_size = NumberColumn(verbose_name="Red Contour 2 Size")
    red_contour_3_size = NumberColumn(verbose_name="Red Contour 3 Size")

    green_contour_1_size = NumberColumn(verbose_name="Green Contour 1 Size")
    green_contour_2_size = NumberColumn(verbose_name="Green Contour 2 Size")
    green_contour_3_size = NumberColumn(verbose_name="Green Contour 3 Size")

    red_intensity_1 = NumberColumn(verbose_name="Red In Red Intensity 1")
    red_intensity_2 = NumberColumn(verbose_name="Red In Red Intensity 2")
    red_intensity_3 = NumberColumn(verbose_name="Red In Red Intensity 3")

    green_intensity_1 = NumberColumn(verbose_name="Green In Red Intensity 1")
    green_intensity_2 = NumberColumn(verbose_name="Green In Red Intensity 2")
    green_intensity_3 = NumberColumn(verbose_name="Green In Red Intensity 3")

    red_in_green_intensity_1 = NumberColumn(verbose_name="Red In Green Intensity 1")
    red_in_green_intensity_2 = NumberColumn(verbose_name="Red In Green Intensity 2")
    red_in_green_intensity_3 = NumberColumn(verbose_name="Red In Green Intensity 3")

    green_in_green_intensity_1 = NumberColumn(verbose_name="Green In Green Intensity 1")
    green_in_green_intensity_2 = NumberColumn(verbose_name="Green In Green Intensity 2")
    green_in_green_intensity_3 = NumberColumn(verbose_name="Green In Green Intensity 3")

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

    cell_parentage = tables.Column(verbose_name="Cell Parentage", empty_values=())
    category_cen_dot = ChoiceLabelColumn(verbose_name="Cen Dot Location")
    colinear_dots = tables.Column(verbose_name="Colinear Dots")
    off_axis_dots = tables.Column(verbose_name="Off Axis Dots")

    class Meta:
        attrs = {"class": "celltable", "id": "celltable"}
        model = CellStatistics
        orderable = False
        fields = (
            "cell_id",
            "puncta_distance",
            "puncta_line_intensity",
            "blue_contour_size",
            "red_contour_1_size",
            "red_contour_2_size",
            "red_contour_3_size",
            "green_contour_1_size",
            "green_contour_2_size",
            "green_contour_3_size",
            "red_intensity_1",
            "red_intensity_2",
            "red_intensity_3",
            "green_intensity_1",
            "green_intensity_2",
            "green_intensity_3",
            "red_in_green_intensity_1",
            "red_in_green_intensity_2",
            "red_in_green_intensity_3",
            "green_in_green_intensity_1",
            "green_in_green_intensity_2",
            "green_in_green_intensity_3",
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
        resolved_visibility = self._resolve_stat_visibility(
            args[0] if args else kwargs.get("data"),
            stat_visibility=stat_visibility,
            selected_plugins=selected_plugins,
        )
        hidden_stat_columns: set[str] = set()
        for visibility_key, field_names in self.STAT_COLUMN_GROUPS.items():
            if resolved_visibility.get(visibility_key, True):
                continue
            for field_name in field_names:
                if field_name in self.columns:
                    self.columns.hide(field_name)
                    hidden_stat_columns.add(field_name)
        self._hidden_stat_columns = hidden_stat_columns
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

    def as_values(self, exclude_columns=None):
        hidden = set(getattr(self, "_hidden_stat_columns", set()))
        if exclude_columns is not None:
            hidden.update(exclude_columns)
        yield from super().as_values(exclude_columns=hidden)

    @classmethod
    def _resolve_stat_visibility(
        cls,
        data,
        *,
        stat_visibility: dict[str, bool] | None = None,
        selected_plugins: list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, bool]:
        if isinstance(stat_visibility, dict):
            return {
                key: bool(stat_visibility.get(key, True))
                for key in cls.STAT_COLUMN_GROUPS
            }
        if selected_plugins is not None:
            return build_stat_visibility(selected_plugins)
        first_record = None
        if hasattr(data, "first"):
            try:
                first_record = data.first()
            except Exception:
                first_record = None
        elif isinstance(data, (list, tuple)) and data:
            first_record = data[0]
        properties = getattr(first_record, "properties", {}) or {}
        property_visibility = properties.get("stat_visibility")
        if isinstance(property_visibility, dict):
            return {
                key: bool(property_visibility.get(key, True))
                for key in cls.STAT_COLUMN_GROUPS
            }
        selected = properties.get("selected_analysis")
        if isinstance(selected, list):
            return build_stat_visibility(selected)
        return {key: True for key in cls.STAT_COLUMN_GROUPS}

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

    def render_cell_parentage(self, record: CellStatistics) -> str:
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
        return self._format_number(self._converted_spatial_value(field_name, value, record))

    def _render_nuclear_cell_pair_value(self, record: CellStatistics, value: float) -> str:
        if self._has_no_nucleus_contour(record):
            return "N/A"
        return self._format_number(value)

    @staticmethod
    def _nuclear_cell_pair_contour_source(record: CellStatistics) -> str:
        properties = getattr(record, "properties", {}) or {}
        value = properties.get("nuclear_cell_pair_contour_source")
        return str(value or "N/A")

    def render_nuclear_cell_pair_contour_source(self, record: CellStatistics) -> str:
        return self._nuclear_cell_pair_contour_source(record)

    def value_nuclear_cell_pair_contour_source(self, record: CellStatistics) -> str:
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
        return self._format_number(self._measurement_contour_ratio_value(record, 1))

    def value_green_red_intensity_1(self, record: CellStatistics) -> str:
        return self._format_number(self._measurement_contour_ratio_value(record, 1))

    def render_green_red_intensity_2(self, record: CellStatistics) -> str:
        return self._format_number(self._measurement_contour_ratio_value(record, 2))

    def value_green_red_intensity_2(self, record: CellStatistics) -> str:
        return self._format_number(self._measurement_contour_ratio_value(record, 2))

    def render_green_red_intensity_3(self, record: CellStatistics) -> str:
        return self._format_number(self._measurement_contour_ratio_value(record, 3))

    def value_green_red_intensity_3(self, record: CellStatistics) -> str:
        return self._format_number(self._measurement_contour_ratio_value(record, 3))

    def render_puncta_distance(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("puncta_distance", value, record)

    def value_puncta_distance(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("puncta_distance", value, record)

    def render_blue_contour_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("blue_contour_size", value, record)

    def value_blue_contour_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("blue_contour_size", value, record)

    def render_red_contour_1_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("red_contour_1_size", value, record)

    def value_red_contour_1_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("red_contour_1_size", value, record)

    def render_red_contour_2_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("red_contour_2_size", value, record)

    def value_red_contour_2_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("red_contour_2_size", value, record)

    def render_red_contour_3_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("red_contour_3_size", value, record)

    def value_red_contour_3_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("red_contour_3_size", value, record)

    def render_green_contour_1_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("green_contour_1_size", value, record)

    def value_green_contour_1_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("green_contour_1_size", value, record)

    def render_green_contour_2_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("green_contour_2_size", value, record)

    def value_green_contour_2_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("green_contour_2_size", value, record)

    def render_green_contour_3_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("green_contour_3_size", value, record)

    def value_green_contour_3_size(self, value: float, record: CellStatistics) -> str:
        return self._render_spatial_value("green_contour_3_size", value, record)

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

class CellTableView(ExportMixin, SingleTableView):
    """Table view with CSV/XLSX export support for cell statistics."""

    model = CellStatistics
    table_class = CellTable
    export_formats = ["csv", "xlsx"]
