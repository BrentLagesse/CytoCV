import django_tables2 as tables
from core.models import CellStatistics


class NumberColumn(tables.Column):
    def render(self, value):
        return '{:0.3f}'.format(value)

class CellTable(tables.Table):
    cell_id = tables.Column(verbose_name='Cell ID')
    distance = NumberColumn(verbose_name='MCherry Line Distance')
    line_gfp_intensity = tables.Column(verbose_name='Line GFP Intensity')
    green_red_intensity = NumberColumn(verbose_name='Green Red Intensity')
    nucleus_intensity_sum = tables.Column(verbose_name='Nucleus Intensity')
    cellular_intensity_sum = tables.Column(verbose_name='Cellular Intensity')
    cytoplasmic_intensity = tables.Column(verbose_name='Cytoplasmic Intensity')
    cellular_intensity_sum_DAPI = tables.Column(verbose_name='Cellular Intensity DAPI')
    nucleus_intensity_sum_DAPI = tables.Column(verbose_name='Nucleus Intensity DAPI')
    cytoplasmic_intensity_DAPI = tables.Column(verbose_name='Cytoplasmic Intensity DAPI')

    class Meta:
        attrs = {"class": "celltable","id":"celltable"}
        model = CellStatistics
        fields = ('cell_id','distance','line_gfp_intensity','green_red_intensity','nucleus_intensity_sum',
                  'cellular_intensity_sum','cytoplasmic_intensity', 'cellular_intensity_sum_DAPI',
                    'nucleus_intensity_sum_DAPI', 'cytoplasmic_intensity_DAPI')
        template_name = "django_tables2/semantic.html"


