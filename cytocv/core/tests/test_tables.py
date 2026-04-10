from types import SimpleNamespace

from django.test import SimpleTestCase

from core.tables import CellTable


class CellTableNuclearCellPairRenderingTests(SimpleTestCase):
    def setUp(self):
        self.table = CellTable([], intensity_mode="green_nucleus", puncta_line_mode="red_puncta")

    @staticmethod
    def _record_with_status(status: str):
        return SimpleNamespace(properties={"nuclear_cell_pair_status": status})

    def test_render_returns_na_for_nuclear_cell_pair_fields_when_no_nucleus_contour(self):
        record = self._record_with_status("no_nucleus_contour")

        self.assertEqual(self.table.render_cell_pair_intensity_sum(123.456, record), "N/A")
        self.assertEqual(self.table.render_nucleus_intensity_sum(234.567, record), "N/A")
        self.assertEqual(self.table.render_cytoplasmic_intensity(345.678, record), "N/A")

    def test_export_value_returns_na_for_nuclear_cell_pair_fields_when_no_nucleus_contour(self):
        record = self._record_with_status("no_nucleus_contour")

        self.assertEqual(self.table.value_cell_pair_intensity_sum(123.456, record), "N/A")
        self.assertEqual(self.table.value_nucleus_intensity_sum(234.567, record), "N/A")
        self.assertEqual(self.table.value_cytoplasmic_intensity(345.678, record), "N/A")

    def test_render_and_export_keep_numeric_values_for_ok_status(self):
        record = self._record_with_status("ok")

        self.assertEqual(self.table.render_cell_pair_intensity_sum(123.456, record), "123.456")
        self.assertEqual(self.table.render_nucleus_intensity_sum(234.567, record), "234.567")
        self.assertEqual(self.table.render_cytoplasmic_intensity(345.678, record), "345.678")

        self.assertEqual(self.table.value_cell_pair_intensity_sum(123.456, record), "123.456")
        self.assertEqual(self.table.value_nucleus_intensity_sum(234.567, record), "234.567")
        self.assertEqual(self.table.value_cytoplasmic_intensity(345.678, record), "345.678")

    def test_render_gfp_dot_category_uses_choice_label(self):
        category_table = CellTable([SimpleNamespace(category_cen_dot=1)], intensity_mode="green_nucleus")
        row = list(category_table.rows)[0]

        self.assertEqual(row.get_cell("category_cen_dot"), "One green dot with each red dot")
        self.assertEqual(list(category_table.as_values())[1][-2], "One green dot with each red dot")

    def test_render_gfp_dot_category_falls_back_to_na_for_invalid_values(self):
        category_table = CellTable([SimpleNamespace(category_cen_dot=999)], intensity_mode="green_nucleus")
        row = list(category_table.rows)[0]

        self.assertEqual(row.get_cell("category_cen_dot"), "N/A")
        self.assertEqual(list(category_table.as_values())[1][-2], "N/A")

    def test_ratio_columns_are_present_with_explicit_compatibility_labels(self):
        header_row = list(self.table.as_values())[0]

        self.assertIn("Measurement/Contour Ratio 1 (Red/Green)", header_row)
        self.assertIn("Measurement/Contour Ratio 2 (Red/Green)", header_row)
        self.assertIn("Measurement/Contour Ratio 3 (Red/Green)", header_row)

    def test_ratio_columns_follow_raw_contour_sums_and_precede_distance_triplet(self):
        header_row = list(self.table.as_values())[0]

        green_in_green_index = header_row.index("Green in Green Intensity 3")
        ratio_1_index = header_row.index("Measurement/Contour Ratio 1 (Red/Green)")
        ratio_2_index = header_row.index("Measurement/Contour Ratio 2 (Red/Green)")
        ratio_3_index = header_row.index("Measurement/Contour Ratio 3 (Red/Green)")
        distance_triplet_index = header_row.index("Distance of Green from Red 1")

        self.assertLess(green_in_green_index, ratio_1_index)
        self.assertLess(ratio_1_index, ratio_2_index)
        self.assertLess(ratio_2_index, ratio_3_index)
        self.assertLess(ratio_3_index, distance_triplet_index)

    def test_ratio_columns_use_mode_driven_headers_for_red_nucleus(self):
        header_row = list(CellTable([], intensity_mode="red_nucleus", puncta_line_mode="red_puncta").as_values())[0]

        self.assertIn("Measurement/Contour Ratio 1 (Green/Red)", header_row)
        self.assertIn("Measurement/Contour Ratio 2 (Green/Red)", header_row)
        self.assertIn("Measurement/Contour Ratio 3 (Green/Red)", header_row)

    def test_line_columns_use_green_puncta_headers_when_requested(self):
        header_row = list(CellTable([], intensity_mode="green_nucleus", puncta_line_mode="green_puncta").as_values())[0]

        self.assertIn("Distance between Green Puncta", header_row)
        self.assertIn("Red Intensity over Green Line", header_row)

    def test_ratio_values_are_derived_from_raw_sums_not_stale_stored_values(self):
        record = SimpleNamespace(
            green_red_intensity_1=99.0,
            green_red_intensity_2=88.0,
            green_red_intensity_3=77.0,
            red_in_green_intensity_1=12.0,
            red_in_green_intensity_2=9.0,
            red_in_green_intensity_3=0.0,
            green_in_green_intensity_1=4.0,
            green_in_green_intensity_2=3.0,
            green_in_green_intensity_3=0.0,
            properties={"nuclear_cell_pair_mode": "green_nucleus"},
            category_cen_dot=0,
        )

        table = CellTable([record], intensity_mode="green_nucleus", puncta_line_mode="red_puncta")
        row = list(table.rows)[0]
        header_row = list(table.as_values())[0]
        value_row = list(table.as_values())[1]

        self.assertEqual(row.get_cell("green_red_intensity_1"), "3.000")
        self.assertEqual(row.get_cell("green_red_intensity_2"), "3.000")
        self.assertEqual(row.get_cell("green_red_intensity_3"), "0.000")
        self.assertEqual(
            value_row[header_row.index("Measurement/Contour Ratio 1 (Red/Green)")],
            "3.000",
        )
        self.assertEqual(
            value_row[header_row.index("Measurement/Contour Ratio 2 (Red/Green)")],
            "3.000",
        )
        self.assertEqual(
            value_row[header_row.index("Measurement/Contour Ratio 3 (Red/Green)")],
            "0.000",
        )

