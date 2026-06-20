from types import SimpleNamespace

from django.test import SimpleTestCase

from core.services.cell_statistics_payload import serialize_cell_statistics_payload


def _cell_stat(**overrides):
    defaults = {
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
        "distance_of_green_from_red_1": 7.0,
        "distance_of_green_from_red_2": 8.0,
        "distance_of_green_from_red_3": 9.0,
        "nucleus_intensity_sum": 100.0,
        "cell_pair_intensity_sum": 150.0,
        "cytoplasmic_intensity": 50.0,
        "nuclear_cytoplasmic_ratio": 2.0,
        "red_blue_intensity_1": 1.0,
        "red_blue_intensity_2": 2.0,
        "red_blue_intensity_3": 3.0,
        "cell_pair_intensity_sum_blue": 4.0,
        "nucleus_intensity_sum_blue": 5.0,
        "cytoplasmic_intensity_blue": 6.0,
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


class CellStatisticsPayloadApplicabilityTests(SimpleTestCase):
    def test_nuclear_only_payload_nulls_uncomputed_groups(self):
        payload = serialize_cell_statistics_payload(
            _cell_stat(
                properties={
                    "selected_analysis": ["NuclearCellPairIntensity"],
                    "nuclear_cell_pair_mode": "green_nucleus",
                    "nuclear_cell_pair_status": "ok",
                    "nuclear_cell_pair_contour_source": "canonical_slot_1",
                    "cen_dot_schema_version": 3,
                },
            )
        )

        self.assertTrue(payload["stat_visibility"]["nuclear_cell_pair_intensity"])
        self.assertFalse(payload["stat_visibility"]["puncta_distance"])
        self.assertIsNone(payload["puncta_distance"])
        self.assertIsNone(payload["puncta_line_intensity"])
        self.assertIsNone(payload["red_in_red_total_intensity_1"])
        self.assertIsNone(payload["measurement_contour_ratio_1"])
        self.assertEqual(payload["measurement_contour_ratio_display_text"], "N/A")
        self.assertIsNone(payload["category_cen_dot"])
        self.assertEqual(payload["category_cen_dot_label"], "N/A")
        self.assertEqual(payload["cell_parentage_label"], "N/A")
        self.assertIsNone(payload["colinear_dots"])
        self.assertIsNone(payload["blue_contour_size"])
        self.assertEqual(payload["cell_pair_intensity_sum"], 150.0)
        self.assertEqual(payload["nucleus_intensity_sum"], 100.0)
        self.assertEqual(payload["nuclear_cytoplasmic_ratio"], 2.0)
        self.assertEqual(payload["nuclear_cell_pair_contour_source"], "canonical_slot_1")

    def test_puncta_plus_contour_payload_keeps_computed_zero_ratios(self):
        payload = serialize_cell_statistics_payload(
            _cell_stat(
                green_in_green_total_intensity_3=0.0,
                red_in_green_total_intensity_3=0.0,
                properties={
                    "selected_analysis": ["PunctaDistance", "GreenRedIntensity"],
                    "nuclear_cell_pair_mode": "green_nucleus",
                    "puncta_line_mode": "red_puncta",
                },
            )
        )

        self.assertEqual(payload["puncta_distance"], 10.0)
        self.assertEqual(payload["puncta_line_intensity"], 20.0)
        self.assertEqual(payload["red_in_red_total_intensity_1"], 2.0)
        self.assertEqual(payload["red_in_red_max_intensity_1"], 102.0)
        self.assertEqual(payload["red_in_red_average_intensity_1"], 1.0)
        self.assertEqual(payload["green_in_red_total_intensity_1"], 6.0)
        self.assertEqual(payload["red_in_green_total_intensity_1"], 5.0)
        self.assertEqual(payload["green_in_green_total_intensity_1"], 1.0)
        self.assertNotIn("red_intensity_1", payload)
        self.assertNotIn("green_intensity_1", payload)
        self.assertNotIn("red_in_green_intensity_1", payload)
        self.assertNotIn("green_in_green_intensity_1", payload)
        self.assertEqual(payload["measurement_contour_ratio_3"], 0.0)
        self.assertIsNone(payload["cell_pair_intensity_sum"])
        self.assertIsNone(payload["nuclear_cytoplasmic_ratio"])
        self.assertEqual(payload["nuclear_cell_pair_status"], "N/A")
        self.assertIsNone(payload["category_cen_dot"])
        self.assertIsNone(payload["colinear_dots"])

    def test_selected_biorientation_payload_preserves_computed_zero(self):
        payload = serialize_cell_statistics_payload(
            _cell_stat(
                colinear_dots=0,
                off_axis_dots=0,
                properties={"selected_analysis": ["Biorientation"]},
            )
        )

        self.assertEqual(payload["colinear_dots"], 0)
        self.assertEqual(payload["off_axis_dots"], 0)
        self.assertIsNone(payload["puncta_distance"])
        self.assertIsNone(payload["cell_pair_intensity_sum"])

    def test_contour_center_payloads_are_serialized_from_properties(self):
        payload = serialize_cell_statistics_payload(
            _cell_stat(
                properties={
                    "selected_analysis": ["GreenRedIntensity"],
                    "blue_contour_center_x_px": 1.0,
                    "blue_contour_center_y_px": 2.0,
                    "red_contour_1_center_x_px": 3.0,
                    "red_contour_1_center_y_px": 4.0,
                    "green_contour_1_center_x_px": 5.0,
                    "green_contour_1_center_y_px": 6.0,
                },
            )
        )

        self.assertIsNone(payload["blue_contour_center_xy"])
        self.assertEqual(payload["red_contour_1_center_xy"], {"x_px": 3.0, "y_px": 4.0})
        self.assertEqual(payload["green_contour_1_center_xy"], {"x_px": 5.0, "y_px": 6.0})
        self.assertIsNone(payload["red_contour_2_center_xy"])

    def test_disabled_contour_center_groups_are_null(self):
        payload = serialize_cell_statistics_payload(
            _cell_stat(
                properties={
                    "selected_analysis": ["NuclearCellPairIntensity"],
                    "nuclear_cell_pair_mode": "green_nucleus",
                    "nuclear_cell_pair_status": "ok",
                    "blue_contour_center_x_px": 1.0,
                    "blue_contour_center_y_px": 2.0,
                    "red_contour_1_center_x_px": 3.0,
                    "red_contour_1_center_y_px": 4.0,
                },
            )
        )

        self.assertIsNone(payload["blue_contour_center_xy"])
        self.assertIsNone(payload["red_contour_1_center_xy"])
