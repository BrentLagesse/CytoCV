from decimal import Decimal
from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase

from core.tables import CellTable


def _stats_record(**overrides):
    defaults = {
        "cell_id": 1,
        "puncta_distance": 10.0,
        "puncta_line_intensity": 20.0,
        "blue_contour_size": 30.0,
        "red_contour_1_size": 11.0,
        "red_contour_2_size": 12.0,
        "red_contour_3_size": 13.0,
        "green_contour_1_size": 21.0,
        "green_contour_2_size": 22.0,
        "green_contour_3_size": 23.0,
        "red_in_red_total_intensity_1": 2.0,
        "red_in_red_total_intensity_2": 3.0,
        "red_in_red_total_intensity_3": 4.0,
        "green_in_red_total_intensity_1": 6.0,
        "green_in_red_total_intensity_2": 9.0,
        "green_in_red_total_intensity_3": 16.0,
        "red_in_green_total_intensity_1": 5.0,
        "red_in_green_total_intensity_2": 10.0,
        "red_in_green_total_intensity_3": 15.0,
        "green_in_green_total_intensity_1": 1.0,
        "green_in_green_total_intensity_2": 2.0,
        "green_in_green_total_intensity_3": 3.0,
        "green_red_intensity_1": 99.0,
        "green_red_intensity_2": 99.0,
        "green_red_intensity_3": 99.0,
        "distance_of_green_from_red_1": 7.0,
        "distance_of_green_from_red_2": 8.0,
        "distance_of_green_from_red_3": 9.0,
        "nucleus_intensity_sum": 100.0,
        "cell_pair_intensity_sum": 150.0,
        "cytoplasmic_intensity": 50.0,
        "nuclear_cytoplasmic_ratio": 2.0,
        "category_cen_dot": 1,
        "colinear_dots": 0,
        "off_axis_dots": 0,
        "properties": {
            "nuclear_cell_pair_mode": "green_nucleus",
            "nuclear_cell_pair_status": "ok",
            "nuclear_cell_pair_contour_source": "canonical_slot_1",
            "cen_dot_schema_version": 3,
            "cell_parentage": {
                "status": "identified",
                "mode": "best_effort",
                "method": "principal_axis_median",
                "label": "Mother/Daughter identified",
                "reason": "ok",
            },
        },
    }
    for prefix in (
        "red_in_red",
        "green_in_red",
        "red_in_green",
        "green_in_green",
    ):
        for index in range(1, 4):
            total = defaults[f"{prefix}_total_intensity_{index}"]
            defaults.setdefault(f"{prefix}_max_intensity_{index}", total + 100.0)
            defaults.setdefault(f"{prefix}_average_intensity_{index}", total / 2.0)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


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
        self.assertEqual(self.table.render_nuclear_cytoplasmic_ratio(2.5, record), "N/A")

    def test_export_value_returns_na_for_nuclear_cell_pair_fields_when_no_nucleus_contour(self):
        record = self._record_with_status("no_nucleus_contour")

        self.assertEqual(self.table.value_cell_pair_intensity_sum(123.456, record), "N/A")
        self.assertEqual(self.table.value_nucleus_intensity_sum(234.567, record), "N/A")
        self.assertEqual(self.table.value_cytoplasmic_intensity(345.678, record), "N/A")
        self.assertEqual(self.table.value_nuclear_cytoplasmic_ratio(2.5, record), "N/A")

    def test_render_and_export_keep_numeric_values_for_ok_status(self):
        record = self._record_with_status("ok")

        self.assertEqual(self.table.render_cell_pair_intensity_sum(123.456, record), "123.456")
        self.assertEqual(self.table.render_nucleus_intensity_sum(234.567, record), "234.567")
        self.assertEqual(self.table.render_cytoplasmic_intensity(345.678, record), "345.678")
        self.assertEqual(self.table.render_nuclear_cytoplasmic_ratio(2.5, record), "2.500")

        self.assertEqual(self.table.value_cell_pair_intensity_sum(123.456, record), "123.456")
        self.assertEqual(self.table.value_nucleus_intensity_sum(234.567, record), "234.567")
        self.assertEqual(self.table.value_cytoplasmic_intensity(345.678, record), "345.678")
        self.assertEqual(self.table.value_nuclear_cytoplasmic_ratio(2.5, record), "2.500")

    def test_render_cen_dot_location_uses_schema_aware_choice_label(self):
        record = SimpleNamespace(
            category_cen_dot=1,
            properties={"cen_dot_schema_version": 3},
        )
        category_table = CellTable([record], intensity_mode="green_nucleus")
        row = list(category_table.rows)[0]

        self.assertEqual(row.get_cell("category_cen_dot"), "Mother and daughter")
        values = list(category_table.as_values())
        header = values[0]
        self.assertEqual(values[1][header.index("Cen Dot Location")], "Mother and daughter")

    def test_render_cen_dot_location_falls_back_to_na_for_invalid_values(self):
        record = SimpleNamespace(
            category_cen_dot=999,
            properties={"cen_dot_schema_version": 3},
        )
        category_table = CellTable([record], intensity_mode="green_nucleus")
        row = list(category_table.rows)[0]

        self.assertEqual(row.get_cell("category_cen_dot"), "N/A")
        values = list(category_table.as_values())
        header = values[0]
        self.assertEqual(values[1][header.index("Cen Dot Location")], "N/A")

    def test_legacy_rows_render_rerun_required_label_for_non_na_cen_values(self):
        record = SimpleNamespace(category_cen_dot=1, properties={})
        category_table = CellTable([record], intensity_mode="green_nucleus")
        row = list(category_table.rows)[0]

        self.assertEqual(row.get_cell("category_cen_dot"), "Rerun analysis for CEN location")

    def test_schema_2_rows_render_rerun_required_label_for_non_na_cen_values(self):
        record = SimpleNamespace(
            category_cen_dot=1,
            properties={"cen_dot_schema_version": 2},
        )
        category_table = CellTable([record], intensity_mode="green_nucleus")
        row = list(category_table.rows)[0]

        self.assertEqual(row.get_cell("category_cen_dot"), "Rerun analysis for CEN location")

    def test_cen_dot_location_header_replaces_legacy_category_header(self):
        header_row = list(self.table.as_values())[0]

        self.assertIn("Cen Dot Location", header_row)
        self.assertNotIn("Cen Dot Category", header_row)

    def test_cell_parentage_header_and_export_value_are_separate_from_cen_dot(self):
        record = SimpleNamespace(
            category_cen_dot=4,
            properties={
                "cen_dot_schema_version": 3,
                "cell_parentage": {
                    "status": "identified",
                    "mode": "best_effort",
                    "method": "principal_axis_median",
                    "label": "Mother/Daughter identified",
                    "reason": "ok",
                },
            },
        )
        category_table = CellTable([record], intensity_mode="green_nucleus")
        row = list(category_table.rows)[0]
        values = list(category_table.as_values())
        header = values[0]

        self.assertEqual(row.get_cell("cell_parentage"), "Mother/Daughter identified")
        self.assertEqual(row.get_cell("category_cen_dot"), "N/A")
        self.assertIn("Cell Parentage", header)
        self.assertLess(header.index("Cell Parentage"), header.index("Cen Dot Location"))
        self.assertEqual(values[1][header.index("Cell Parentage")], "Mother/Daughter identified")
        self.assertEqual(values[1][header.index("Cen Dot Location")], "N/A")

    def test_ratio_columns_are_present_with_explicit_compatibility_labels(self):
        header_row = list(self.table.as_values())[0]

        self.assertIn("Measurement/Contour Ratio 1 (Red/Green)", header_row)
        self.assertIn("Measurement/Contour Ratio 2 (Red/Green)", header_row)
        self.assertIn("Measurement/Contour Ratio 3 (Red/Green)", header_row)

    def test_ratio_columns_follow_raw_contour_sums_and_precede_distance_triplet(self):
        header_row = list(self.table.as_values())[0]

        green_in_green_index = header_row.index("Green In Green Average Intensity 3")
        ratio_1_index = header_row.index("Measurement/Contour Ratio 1 (Red/Green)")
        ratio_2_index = header_row.index("Measurement/Contour Ratio 2 (Red/Green)")
        ratio_3_index = header_row.index("Measurement/Contour Ratio 3 (Red/Green)")
        distance_triplet_index = header_row.index("Distance Of Green From Red 1 (px)")

        self.assertLess(green_in_green_index, ratio_1_index)
        self.assertLess(ratio_1_index, ratio_2_index)
        self.assertLess(ratio_2_index, ratio_3_index)
        self.assertLess(ratio_3_index, distance_triplet_index)

    def test_contour_intensity_columns_use_slot_local_total_max_average_order(self):
        header_row = list(self.table.as_values())[0]
        start = header_row.index("Red In Red Total Intensity 1")
        end = header_row.index("Measurement/Contour Ratio 1 (Red/Green)")

        self.assertEqual(
            list(header_row[start:end]),
            [
                "Red In Red Total Intensity 1",
                "Red In Red Max Intensity 1",
                "Red In Red Average Intensity 1",
                "Red In Red Total Intensity 2",
                "Red In Red Max Intensity 2",
                "Red In Red Average Intensity 2",
                "Red In Red Total Intensity 3",
                "Red In Red Max Intensity 3",
                "Red In Red Average Intensity 3",
                "Green In Red Total Intensity 1",
                "Green In Red Max Intensity 1",
                "Green In Red Average Intensity 1",
                "Green In Red Total Intensity 2",
                "Green In Red Max Intensity 2",
                "Green In Red Average Intensity 2",
                "Green In Red Total Intensity 3",
                "Green In Red Max Intensity 3",
                "Green In Red Average Intensity 3",
                "Red In Green Total Intensity 1",
                "Red In Green Max Intensity 1",
                "Red In Green Average Intensity 1",
                "Red In Green Total Intensity 2",
                "Red In Green Max Intensity 2",
                "Red In Green Average Intensity 2",
                "Red In Green Total Intensity 3",
                "Red In Green Max Intensity 3",
                "Red In Green Average Intensity 3",
                "Green In Green Total Intensity 1",
                "Green In Green Max Intensity 1",
                "Green In Green Average Intensity 1",
                "Green In Green Total Intensity 2",
                "Green In Green Max Intensity 2",
                "Green In Green Average Intensity 2",
                "Green In Green Total Intensity 3",
                "Green In Green Max Intensity 3",
                "Green In Green Average Intensity 3",
            ],
        )

    def test_ratio_columns_use_mode_driven_headers_for_red_nucleus(self):
        header_row = list(CellTable([], intensity_mode="red_nucleus", puncta_line_mode="red_puncta").as_values())[0]

        self.assertIn("Measurement/Contour Ratio 1 (Green/Red)", header_row)
        self.assertIn("Measurement/Contour Ratio 2 (Green/Red)", header_row)
        self.assertIn("Measurement/Contour Ratio 3 (Green/Red)", header_row)

    def test_line_columns_use_green_puncta_headers_when_requested(self):
        header_row = list(CellTable([], intensity_mode="green_nucleus", puncta_line_mode="green_puncta").as_values())[0]

        self.assertIn("Distance Between Green Puncta (px)", header_row)
        self.assertIn("Red Intensity Over Green Line", header_row)

    def test_nuclear_mode_keeps_puncta_contour_cen_and_biorientation_columns_visible(self):
        header_row = list(
            CellTable(
                [],
                intensity_mode="green_nucleus",
                selected_plugins=["NuclearCellPairIntensity"],
            ).as_values()
        )[0]

        self.assertIn("Nucleus Contour Source", header_row)
        self.assertIn("Red Cell-Pair Intensity", header_row)
        self.assertIn("Red Nuclear Intensity", header_row)
        self.assertIn("Cytoplasmic Intensity", header_row)
        self.assertIn("Nuclear / Cytoplasmic Ratio", header_row)
        self.assertIn("Distance Between Red Puncta (px)", header_row)
        self.assertIn("Green Intensity Over Red Line", header_row)
        self.assertIn("Red In Red Total Intensity 1", header_row)
        self.assertIn("Measurement/Contour Ratio 1 (Red/Green)", header_row)
        self.assertIn("Distance Of Green From Red 1 (px)", header_row)
        self.assertIn("Cell Parentage", header_row)
        self.assertIn("Cen Dot Location", header_row)
        self.assertIn("Colinear Dots", header_row)
        self.assertIn("Blue Contour Size (px²)", header_row)

    def test_puncta_mode_without_contour_intensity_keeps_raw_sums_and_ratios_visible(self):
        header_row = list(
            CellTable(
                [],
                puncta_line_mode="red_puncta",
                selected_plugins=["PunctaDistance"],
            ).as_values()
        )[0]

        self.assertIn("Distance Between Red Puncta (px)", header_row)
        self.assertIn("Green Intensity Over Red Line", header_row)
        self.assertIn("Red In Red Total Intensity 1", header_row)
        self.assertIn("Measurement/Contour Ratio 1 (Red/Green)", header_row)
        self.assertIn("Distance Of Green From Red 1 (px)", header_row)
        self.assertIn("Nucleus Contour Source", header_row)
        self.assertIn("Measured Cell-Pair Intensity", header_row)

    def test_nuclear_mode_outputs_na_for_uncomputed_stat_groups(self):
        record = _stats_record(
            properties={
                "selected_analysis": ["NuclearCellPairIntensity"],
                "nuclear_cell_pair_mode": "green_nucleus",
                "nuclear_cell_pair_status": "ok",
                "nuclear_cell_pair_contour_source": "canonical_slot_1",
                "cen_dot_schema_version": 3,
                "cell_parentage": {
                    "status": "identified",
                    "mode": "best_effort",
                    "method": "principal_axis_median",
                    "label": "Mother/Daughter identified",
                    "reason": "ok",
                },
            },
        )
        table = CellTable([record], intensity_mode="green_nucleus", puncta_line_mode="red_puncta")
        row = list(table.rows)[0]
        values = list(table.as_values())
        header = values[0]
        value_row = values[1]

        self.assertEqual(row.get_cell("nuclear_cell_pair_contour_source"), "canonical_slot_1")
        self.assertEqual(row.get_cell("cell_pair_intensity_sum"), "150.000")
        self.assertEqual(row.get_cell("nucleus_intensity_sum"), "100.000")
        self.assertEqual(row.get_cell("cytoplasmic_intensity"), "50.000")
        self.assertEqual(row.get_cell("nuclear_cytoplasmic_ratio"), "2.000")
        self.assertEqual(row.get_cell("puncta_distance"), "N/A")
        self.assertEqual(row.get_cell("puncta_line_intensity"), "N/A")
        self.assertEqual(row.get_cell("red_in_red_total_intensity_1"), "N/A")
        self.assertEqual(row.get_cell("green_red_intensity_1"), "N/A")
        self.assertEqual(row.get_cell("distance_of_green_from_red_1"), "N/A")
        self.assertEqual(row.get_cell("cell_parentage"), "N/A")
        self.assertEqual(row.get_cell("category_cen_dot"), "N/A")
        self.assertEqual(row.get_cell("colinear_dots"), "N/A")
        self.assertEqual(row.get_cell("blue_contour_size"), "N/A")
        self.assertEqual(value_row[header.index("Distance Between Red Puncta (px)")], "N/A")
        self.assertEqual(
            value_row[header.index("Red Cell-Pair Intensity")],
            Decimal("150.000"),
        )
        self.assertEqual(
            value_row[header.index("Nuclear / Cytoplasmic Ratio")],
            Decimal("2.000"),
        )

    def test_puncta_mode_outputs_na_for_uncomputed_contour_and_nuclear_groups(self):
        record = _stats_record(
            properties={
                "selected_analysis": ["PunctaDistance"],
                "puncta_line_mode": "red_puncta",
                "nuclear_cell_pair_mode": "green_nucleus",
                "nuclear_cell_pair_status": "ok",
                "nuclear_cell_pair_contour_source": "canonical_slot_1",
                "cen_dot_schema_version": 3,
            },
        )
        table = CellTable([record], intensity_mode="green_nucleus", puncta_line_mode="red_puncta")
        row = list(table.rows)[0]

        self.assertEqual(row.get_cell("puncta_distance"), "10.000")
        self.assertEqual(row.get_cell("puncta_line_intensity"), "20.000")
        self.assertEqual(row.get_cell("red_in_red_total_intensity_1"), "N/A")
        self.assertEqual(row.get_cell("green_red_intensity_1"), "N/A")
        self.assertEqual(row.get_cell("distance_of_green_from_red_1"), "N/A")
        self.assertEqual(row.get_cell("nuclear_cell_pair_contour_source"), "N/A")
        self.assertEqual(row.get_cell("cell_pair_intensity_sum"), "N/A")
        self.assertEqual(row.get_cell("nuclear_cytoplasmic_ratio"), "N/A")

    def test_cen_dot_disabled_outputs_na_despite_stored_values(self):
        record = _stats_record(
            properties={
                "selected_analysis": ["PunctaDistance"],
                "cen_dot_schema_version": 3,
                "cell_parentage": {
                    "status": "identified",
                    "mode": "best_effort",
                    "method": "principal_axis_median",
                    "label": "Mother/Daughter identified",
                    "reason": "ok",
                },
            },
        )
        table = CellTable([record], intensity_mode="green_nucleus")
        row = list(table.rows)[0]

        self.assertEqual(row.get_cell("cell_parentage"), "N/A")
        self.assertEqual(row.get_cell("category_cen_dot"), "N/A")

    def test_biorientation_disabled_is_na_but_selected_zero_is_displayed(self):
        disabled = _stats_record(
            properties={"selected_analysis": ["PunctaDistance"]},
            colinear_dots=0,
            off_axis_dots=0,
        )
        selected = _stats_record(
            properties={"selected_analysis": ["Biorientation"]},
            colinear_dots=0,
            off_axis_dots=0,
        )

        disabled_row = list(CellTable([disabled]).rows)[0]
        selected_row = list(CellTable([selected]).rows)[0]

        self.assertEqual(disabled_row.get_cell("colinear_dots"), "N/A")
        self.assertEqual(disabled_row.get_cell("off_axis_dots"), "N/A")
        self.assertEqual(selected_row.get_cell("colinear_dots"), "0")
        self.assertEqual(selected_row.get_cell("off_axis_dots"), "0")

    def test_nuclear_contour_source_exports_from_record_properties(self):
        record = _stats_record(
            category_cen_dot=0,
            properties={
                "selected_analysis": ["NuclearCellPairIntensity"],
                "nuclear_cell_pair_contour_source": "alternate_green_nucleus_slot_1",
                "nuclear_cell_pair_status": "ok",
            },
        )

        table = CellTable([record], intensity_mode="green_nucleus")
        row = list(table.rows)[0]
        values = list(table.as_values())
        header = values[0]

        self.assertEqual(row.get_cell("nuclear_cell_pair_contour_source"), "alternate_green_nucleus_slot_1")
        self.assertEqual(
            values[1][header.index("Nucleus Contour Source")],
            "alternate_green_nucleus_slot_1",
        )

    def test_ratio_values_are_derived_from_raw_sums_not_stale_stored_values(self):
        record = _stats_record(
            green_red_intensity_1=99.0,
            green_red_intensity_2=88.0,
            green_red_intensity_3=77.0,
            red_in_green_total_intensity_1=12.0,
            red_in_green_total_intensity_2=9.0,
            red_in_green_total_intensity_3=0.0,
            green_in_green_total_intensity_1=4.0,
            green_in_green_total_intensity_2=3.0,
            green_in_green_total_intensity_3=0.0,
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
            Decimal("3.000"),
        )
        self.assertEqual(
            value_row[header_row.index("Measurement/Contour Ratio 2 (Red/Green)")],
            Decimal("3.000"),
        )
        self.assertEqual(
            value_row[header_row.index("Measurement/Contour Ratio 3 (Red/Green)")],
            Decimal("0.000"),
        )

    def test_spatial_headers_include_default_pixel_units(self):
        header_row = list(self.table.as_values())[0]

        self.assertIn("Distance Between Red Puncta (px)", header_row)
        self.assertIn("Blue Contour Size (px²)", header_row)
        self.assertIn("Blue Contour Center (x,y) (px)", header_row)
        self.assertIn("Distance Of Green From Red 1 (px)", header_row)

    def test_spatial_headers_switch_to_microns_when_requested(self):
        header_row = list(
            CellTable(
                [],
                intensity_mode="green_nucleus",
                puncta_line_mode="red_puncta",
                spatial_stats_unit="um",
                scale_context={"effective_um_per_px": 0.5, "x_um_per_px": 0.5, "y_um_per_px": 0.5},
            ).as_values()
        )[0]

        self.assertIn("Distance Between Red Puncta (µm)", header_row)
        self.assertIn("Blue Contour Size (µm²)", header_row)
        self.assertIn("Blue Contour Center (x,y) (µm)", header_row)
        self.assertIn("Distance Of Green From Red 1 (µm)", header_row)

    def test_contour_center_columns_follow_grouped_size_columns(self):
        header_row = list(self.table.as_values())[0]

        self.assertEqual(
            header_row[
                header_row.index("Red Contour 1 Size (px²)") :
                header_row.index("Red In Red Total Intensity 1")
            ],
            [
                "Red Contour 1 Size (px²)",
                "Red Contour 2 Size (px²)",
                "Red Contour 3 Size (px²)",
                "Red Contour 1 Center (x,y) (px)",
                "Red Contour 2 Center (x,y) (px)",
                "Red Contour 3 Center (x,y) (px)",
                "Green Contour 1 Size (px²)",
                "Green Contour 2 Size (px²)",
                "Green Contour 3 Size (px²)",
                "Green Contour 1 Center (x,y) (px)",
                "Green Contour 2 Center (x,y) (px)",
                "Green Contour 3 Center (x,y) (px)",
            ],
        )
        self.assertLess(
            header_row.index("Blue Contour Size (px²)"),
            header_row.index("Blue Contour Center (x,y) (px)"),
        )

    def test_rendered_header_html_does_not_include_sort_links(self):
        request = RequestFactory().get("/dashboard/")
        rendered = self.table.as_html(request)

        self.assertIn("Cell ID", rendered)
        self.assertNotIn("sort=cell_id", rendered)
        self.assertNotIn("<th ><a ", rendered)

    def test_spatial_values_convert_for_render_and_export(self):
        record = SimpleNamespace(
            puncta_distance=4.0,
            blue_contour_size=10.0,
            distance_of_green_from_red_1=6.0,
            properties={
                "puncta_distance_delta_x_px": 3.0,
                "puncta_distance_delta_y_px": 4.0,
                "distance_of_green_from_red_1_delta_x_px": 6.0,
                "distance_of_green_from_red_1_delta_y_px": 0.0,
            },
        )
        table = CellTable(
            [record],
            intensity_mode="green_nucleus",
            puncta_line_mode="red_puncta",
            spatial_stats_unit="um",
            scale_context={"effective_um_per_px": 0.5, "x_um_per_px": 0.5, "y_um_per_px": 0.25},
        )

        self.assertEqual(table.render_puncta_distance(4.0, record), "1.803")
        self.assertEqual(table.value_puncta_distance(4.0, record), "1.803")
        self.assertEqual(table.render_blue_contour_size(10.0, record), "1.250")
        self.assertEqual(table.value_blue_contour_size(10.0, record), "1.250")
        self.assertEqual(table.render_distance_of_green_from_red_1(6.0, record), "3.000")
        self.assertEqual(table.value_distance_of_green_from_red_1(6.0, record), "3.000")

    def test_contour_center_values_convert_for_render_and_export(self):
        record = _stats_record(
            properties={
                "blue_contour_center_x_px": 10.0,
                "blue_contour_center_y_px": 20.0,
                "red_contour_1_center_x_px": 12.0,
                "red_contour_1_center_y_px": 24.0,
                "green_contour_1_center_x_px": 14.0,
                "green_contour_1_center_y_px": 28.0,
            },
        )
        table = CellTable(
            [record],
            spatial_stats_unit="um",
            scale_context={
                "effective_um_per_px": 1.0,
                "x_um_per_px": 0.5,
                "y_um_per_px": 0.25,
            },
        )
        values = list(table.as_values())
        header = values[0]

        self.assertEqual(table.render_blue_contour_center_xy(record), "5.000, 5.000")
        self.assertEqual(table.value_blue_contour_center_xy(record), "5.000, 5.000")
        self.assertEqual(
            values[1][header.index("Red Contour 1 Center (x,y) (µm)")],
            "6.000, 6.000",
        )
        self.assertEqual(
            values[1][header.index("Green Contour 1 Center (x,y) (µm)")],
            "7.000, 7.000",
        )

    def test_contour_center_values_are_na_when_missing_or_group_disabled(self):
        missing = _stats_record(properties={})
        disabled = _stats_record(
            properties={
                "selected_analysis": ["NuclearCellPairIntensity"],
                "red_contour_1_center_x_px": 12.0,
                "red_contour_1_center_y_px": 24.0,
            },
        )

        self.assertEqual(
            CellTable([missing]).render_red_contour_1_center_xy(missing),
            "N/A",
        )
        self.assertEqual(
            CellTable([disabled]).render_red_contour_1_center_xy(disabled),
            "N/A",
        )

    def test_distance_conversion_falls_back_to_scalar_scale_for_legacy_rows(self):
        record = SimpleNamespace(puncta_distance=8.0, properties={})
        table = CellTable(
            [record],
            intensity_mode="green_nucleus",
            puncta_line_mode="red_puncta",
            spatial_stats_unit="um",
            scale_context={"effective_um_per_px": 0.25, "x_um_per_px": 0.1, "y_um_per_px": 0.2},
        )

        self.assertEqual(table.render_puncta_distance(8.0, record), "2.000")
