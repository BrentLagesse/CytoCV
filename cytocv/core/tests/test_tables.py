from types import SimpleNamespace

from django.test import SimpleTestCase

from core.tables import CellTable


class CellTableNuclearCellularRenderingTests(SimpleTestCase):
    def setUp(self):
        self.table = CellTable([], intensity_mode="green_nucleus")

    @staticmethod
    def _record_with_status(status: str):
        return SimpleNamespace(properties={"nuclear_cellular_status": status})

    def test_render_returns_na_for_nuclear_cellular_fields_when_no_nucleus_contour(self):
        record = self._record_with_status("no_nucleus_contour")

        self.assertEqual(self.table.render_cellular_intensity_sum(123.456, record), "N/A")
        self.assertEqual(self.table.render_nucleus_intensity_sum(234.567, record), "N/A")
        self.assertEqual(self.table.render_cytoplasmic_intensity(345.678, record), "N/A")

    def test_export_value_returns_na_for_nuclear_cellular_fields_when_no_nucleus_contour(self):
        record = self._record_with_status("no_nucleus_contour")

        self.assertEqual(self.table.value_cellular_intensity_sum(123.456, record), "N/A")
        self.assertEqual(self.table.value_nucleus_intensity_sum(234.567, record), "N/A")
        self.assertEqual(self.table.value_cytoplasmic_intensity(345.678, record), "N/A")

    def test_render_and_export_keep_numeric_values_for_ok_status(self):
        record = self._record_with_status("ok")

        self.assertEqual(self.table.render_cellular_intensity_sum(123.456, record), "123.456")
        self.assertEqual(self.table.render_nucleus_intensity_sum(234.567, record), "234.567")
        self.assertEqual(self.table.render_cytoplasmic_intensity(345.678, record), "345.678")

        self.assertEqual(self.table.value_cellular_intensity_sum(123.456, record), "123.456")
        self.assertEqual(self.table.value_nucleus_intensity_sum(234.567, record), "234.567")
        self.assertEqual(self.table.value_cytoplasmic_intensity(345.678, record), "345.678")

    def test_render_gfp_dot_category_uses_choice_label(self):
        category_table = CellTable([SimpleNamespace(category_GFP_dot=1)], intensity_mode="green_nucleus")
        row = list(category_table.rows)[0]

        self.assertEqual(row.get_cell("category_GFP_dot"), "One green dot with each red dot")
        self.assertEqual(list(category_table.as_values())[1][-2], "One green dot with each red dot")

    def test_render_gfp_dot_category_falls_back_to_na_for_invalid_values(self):
        category_table = CellTable([SimpleNamespace(category_GFP_dot=999)], intensity_mode="green_nucleus")
        row = list(category_table.rows)[0]

        self.assertEqual(row.get_cell("category_GFP_dot"), "N/A")
        self.assertEqual(list(category_table.as_values())[1][-2], "N/A")
