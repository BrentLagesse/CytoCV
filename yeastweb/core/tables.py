"""Table definitions for rendering and exporting cell statistics."""

from __future__ import annotations

import django_tables2 as tables
from django_tables2 import SingleTableView
from django_tables2.export.views import ExportMixin

from core.models import CellStatistics


class NumberColumn(tables.Column):
    """Format numeric values for display with fixed precision."""

    def render(self, value: float) -> str:
        """Render a numeric value with three decimal places."""
        return "{:0.3f}".format(value)

class CellTable(tables.Table):
    """Table layout for per-cell statistics.

    The table focuses on distance metrics, contour sizes, and intensity
    summaries needed for downstream analysis and export.
    """
    cell_id = tables.Column(verbose_name='Cell ID')
    distance = NumberColumn(verbose_name='MCherry Line Distance')
    line_gfp_intensity = tables.Column(verbose_name='Line GFP Intensity')
    blue_contour_size = tables.Column(verbose_name='Blue Contour Size')

    red_contour_1_size = tables.Column(verbose_name='Red Contour 1 Size')
    red_contour_2_size = tables.Column(verbose_name='Red Contour 2 Size')
    red_contour_3_size = tables.Column(verbose_name='Red Contour 3 Size')

    #red_blue_intensity_1 = NumberColumn(verbose_name='Red in Blue Intensity 1')
    #red_blue_intensity_2 = NumberColumn(verbose_name='Red in Blue Intensity 2')
    #red_blue_intensity_3 = NumberColumn(verbose_name='Red in Blue Intensity 3')

    red_intensity_1 = NumberColumn(verbose_name='Red in Red Intensity 1')
    red_intensity_2 = NumberColumn(verbose_name='Red in Red Intensity 2')
    red_intensity_3 = NumberColumn(verbose_name='Red in Red Intensity 3')

    green_intensity_1 = NumberColumn(verbose_name='Green in Red Intensity 1')
    green_intensity_2 = NumberColumn(verbose_name='Green in Red Intensity 2')
    green_intensity_3 = NumberColumn(verbose_name='Green in Red Intensity 3')

    #green_red_intensity_1 = NumberColumn(verbose_name='Green Red Intensity 1')
    #green_red_intensity_2 = NumberColumn(verbose_name='Green Red Intensity 2')
    #green_red_intensity_3 = NumberColumn(verbose_name='Green Red Intensity 3')

    nucleus_intensity_sum = tables.Column(verbose_name='Nucleus Intensity')

    cellular_intensity_sum_DAPI = tables.Column(verbose_name='Cellular Intensity DAPI')

    category_GFP_dot = tables.Column(verbose_name='GFP Dot Category')

    biorientation = tables.Column(verbose_name="Biorientation")

    class Meta:
        attrs = {"class": "celltable","id":"celltable"}
        model = CellStatistics
        fields = ('cell_id','distance','line_gfp_intensity','blue_contour_size',
                  'red_contour_1_size','red_contour_2_size','red_contour_3_size',
                  #'red_blue_intensity_1','red_blue_intensity_2','red_blue_intensity_3',
                  'red_intensity_1','red_intensity_2','red_intensity_3',
                  'green_intensity_1','green_intensity_2','green_intensity_3',
                  #'green_red_intensity_1','green_red_intensity_2','green_red_intensity_3','nucleus_intensity_sum',
                'cellular_intensity_sum_DAPI', 'category_GFP_dot')
        template_name = "django_tables2/semantic.html"


class CellTableView(ExportMixin, SingleTableView):
    """Table view with CSV/XLSX export support for cell statistics."""

    model = CellStatistics
    table_class = CellTable
    export_formats = ["csv", "xlsx"]
