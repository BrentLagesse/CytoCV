"""Table definitions for rendering and exporting cell statistics."""

from __future__ import annotations

import django_tables2 as tables
from django_tables2 import SingleTableView
from django_tables2.export.views import ExportMixin

from core.models import CellStatistics, get_cen_dot_category_label
from core.services.measurement_contour_ratio import (
    calculate_measurement_contour_ratio_value,
    get_measurement_contour_ratio_headers,
    normalize_nuclear_cell_pair_mode,
)
from core.services.puncta_line_mode import get_puncta_line_mode_metadata


NUCLEAR_CELL_PAIR_LABELS = {
    "red_nucleus": ("Green cell-pair intensity", "Green nuclear intensity"),
    "green_nucleus": ("Red cell-pair intensity", "Red nuclear intensity"),
}
FALLBACK_NUCLEAR_CELL_PAIR_LABELS = ("Measured cell-pair intensity", "Measured nuclear intensity")


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

    def render(self, value: int) -> str:
        return get_cen_dot_category_label(value)

    def value(self, value: int) -> str:
        return self.render(value)


class CellTable(tables.Table):
    """Table layout for per-cell statistics used in UI and export."""

    cell_id = tables.Column(verbose_name="Cell ID")
    puncta_distance = NumberColumn(verbose_name="Distance between Red Puncta")
    puncta_line_intensity = NumberColumn(verbose_name="Green Intensity over Red Line")
    blue_contour_size = NumberColumn(verbose_name="Blue Contour Size")

    red_contour_1_size = NumberColumn(verbose_name="Red Contour 1 Size")
    red_contour_2_size = NumberColumn(verbose_name="Red Contour 2 Size")
    red_contour_3_size = NumberColumn(verbose_name="Red Contour 3 Size")

    green_contour_1_size = NumberColumn(verbose_name="Green Contour 1 Size")
    green_contour_2_size = NumberColumn(verbose_name="Green Contour 2 Size")
    green_contour_3_size = NumberColumn(verbose_name="Green Contour 3 Size")

    red_intensity_1 = NumberColumn(verbose_name="Red in Red Intensity 1")
    red_intensity_2 = NumberColumn(verbose_name="Red in Red Intensity 2")
    red_intensity_3 = NumberColumn(verbose_name="Red in Red Intensity 3")

    green_intensity_1 = NumberColumn(verbose_name="Green in Red Intensity 1")
    green_intensity_2 = NumberColumn(verbose_name="Green in Red Intensity 2")
    green_intensity_3 = NumberColumn(verbose_name="Green in Red Intensity 3")

    red_in_green_intensity_1 = NumberColumn(verbose_name="Red in Green Intensity 1")
    red_in_green_intensity_2 = NumberColumn(verbose_name="Red in Green Intensity 2")
    red_in_green_intensity_3 = NumberColumn(verbose_name="Red in Green Intensity 3")

    green_in_green_intensity_1 = NumberColumn(verbose_name="Green in Green Intensity 1")
    green_in_green_intensity_2 = NumberColumn(verbose_name="Green in Green Intensity 2")
    green_in_green_intensity_3 = NumberColumn(verbose_name="Green in Green Intensity 3")

    green_red_intensity_1 = NumberColumn(verbose_name="Measurement/Contour Ratio 1")
    green_red_intensity_2 = NumberColumn(verbose_name="Measurement/Contour Ratio 2")
    green_red_intensity_3 = NumberColumn(verbose_name="Measurement/Contour Ratio 3")

    distance_of_green_from_red_1 = NumberColumn(verbose_name="Distance of Green from Red 1")
    distance_of_green_from_red_2 = NumberColumn(verbose_name="Distance of Green from Red 2")
    distance_of_green_from_red_3 = NumberColumn(verbose_name="Distance of Green from Red 3")

    cell_pair_intensity_sum = NumberColumn(verbose_name=FALLBACK_NUCLEAR_CELL_PAIR_LABELS[0])
    nucleus_intensity_sum = NumberColumn(verbose_name=FALLBACK_NUCLEAR_CELL_PAIR_LABELS[1])
    cytoplasmic_intensity = NumberColumn(verbose_name="Cytoplasmic Intensity")

    category_cen_dot = ChoiceLabelColumn(verbose_name="CEN dot Category")
    biorientation = tables.Column(verbose_name="Biorientation")

    class Meta:
        attrs = {"class": "celltable", "id": "celltable"}
        model = CellStatistics
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
            "cell_pair_intensity_sum",
            "nucleus_intensity_sum",
            "cytoplasmic_intensity",
            "category_cen_dot",
            "biorientation",
        )
        template_name = "django_tables2/semantic.html"

    def __init__(
        self,
        *args,
        intensity_mode: str | None = None,
        puncta_line_mode: str | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
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

    def _render_nuclear_cell_pair_value(self, record: CellStatistics, value: float) -> str:
        if self._has_no_nucleus_contour(record):
            return "N/A"
        return self._format_number(value)

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

class CellTableView(ExportMixin, SingleTableView):
    """Table view with CSV/XLSX export support for cell statistics."""

    model = CellStatistics
    table_class = CellTable
    export_formats = ["csv", "xlsx"]
