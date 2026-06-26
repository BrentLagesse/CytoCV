from types import SimpleNamespace

from django.test import SimpleTestCase

from core.services.cell_statistics_payload import serialize_cell_statistics_payload


CONTOUR_INTENSITY_PREFIXES = (
    "red_in_red",
    "green_in_red",
    "red_in_green",
    "green_in_green",
)
CONTOUR_INTENSITY_STATISTICS = ("total", "max", "average")


def _contour_intensity_fields(statistic: str | None = None):
    statistics = (statistic,) if statistic else CONTOUR_INTENSITY_STATISTICS
    return [
        f"{prefix}_{stat}_intensity_{index}"
        for prefix in CONTOUR_INTENSITY_PREFIXES
        for stat in statistics
        for index in range(1, 4)
    ]


def _cell_stat(**overrides):
    defaults = {
        "cell_type": "cell_pair",
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
    def test_payload_serializes_cell_type_and_label(self):
        payload = serialize_cell_statistics_payload(_cell_stat(cell_type="single_cell"))

        self.assertEqual(payload["cell_type"], "single_cell")
        self.assertEqual(payload["cell_type_label"], "Single Cell")

    def test_payload_without_cell_type_serializes_unknown(self):
        stat = _cell_stat()
        delattr(stat, "cell_type")

        payload = serialize_cell_statistics_payload(stat)

        self.assertEqual(payload["cell_type"], "unknown")
        self.assertEqual(payload["cell_type_label"], "Unknown")

    def test_nuclear_payload_exposes_mode_and_applicability_for_cell_card(self):
        payload = serialize_cell_statistics_payload(
            _cell_stat(
                properties={
                    "selected_analysis": ["NuclearCellPairIntensity"],
                    "signal_quantification_mode": "nuclear_cell_pair",
                    "nuclear_cell_pair_mode": "green_nucleus",
                    "nuclear_cell_pair_status": "ok",
                    "nuclear_cell_pair_contour_source": "canonical_slot_1",
                },
            )
        )

        self.assertEqual(payload["signal_quantification_mode"], "nuclear_cell_pair")
        self.assertEqual(payload["selected_analysis"], ["NuclearCellPairIntensity"])
        self.assertTrue(payload["stat_visibility"]["nuclear_cell_pair_intensity"])
        self.assertFalse(payload["stat_visibility"]["puncta_distance"])
        self.assertFalse(payload["stat_visibility"]["red_green_intensity"])
        self.assertFalse(payload["stat_visibility"]["cen_dot"])
        self.assertFalse(payload["stat_visibility"]["biorientation"])
        self.assertEqual(payload["nuclear_cell_pair_contour_source"], "canonical_slot_1")
        self.assertEqual(payload["nuclear_cell_pair_measurement_channel"], "Red")
        self.assertEqual(payload["cell_pair_intensity_sum"], 150.0)
        self.assertEqual(payload["nucleus_intensity_sum"], 100.0)
        self.assertEqual(payload["cytoplasmic_intensity"], 50.0)
        self.assertEqual(payload["nuclear_cytoplasmic_ratio"], 2.0)

    def test_puncta_payload_exposes_mode_applicability_and_concrete_intensity_fields(self):
        selected_analysis = [
            "PunctaDistance",
            "CENDot",
            "Biorientation",
            "GreenRedIntensity",
        ]
        payload = serialize_cell_statistics_payload(
            _cell_stat(
                properties={
                    "selected_analysis": selected_analysis,
                    "signal_quantification_mode": "puncta_distance",
                    "puncta_line_mode": "red_puncta",
                    "red_contour_count": 2,
                    "green_contour_count": 1,
                },
            )
        )

        self.assertEqual(payload["signal_quantification_mode"], "puncta_distance")
        self.assertEqual(payload["selected_analysis"], selected_analysis)
        self.assertTrue(payload["stat_visibility"]["puncta_distance"])
        self.assertTrue(payload["stat_visibility"]["red_green_intensity"])
        self.assertTrue(payload["stat_visibility"]["cen_dot"])
        self.assertTrue(payload["stat_visibility"]["biorientation"])
        self.assertFalse(payload["stat_visibility"]["nuclear_cell_pair_intensity"])
        self.assertEqual(payload["puncta_distance"], 10.0)
        self.assertEqual(payload["puncta_line_intensity"], 20.0)
        self.assertIsNone(payload["cell_pair_intensity_sum"])
        self.assertIsNone(payload["nucleus_intensity_sum"])
        for field_name in _contour_intensity_fields():
            with self.subTest(field=field_name):
                self.assertIn(field_name, payload)
                self.assertIsNotNone(payload[field_name])
        self.assertNotIn("red_in_red_intensity_1", payload)
        self.assertNotIn("green_in_red_intensity_1", payload)

    def test_green_red_disabled_payload_does_not_imply_contour_card_visibility(self):
        payload = serialize_cell_statistics_payload(
            _cell_stat(
                properties={
                    "selected_analysis": ["PunctaDistance"],
                    "signal_quantification_mode": "puncta_distance",
                    "puncta_line_mode": "red_puncta",
                },
            )
        )

        self.assertEqual(payload["signal_quantification_mode"], "puncta_distance")
        self.assertTrue(payload["stat_visibility"]["puncta_distance"])
        self.assertFalse(payload["stat_visibility"]["red_green_intensity"])
        for field_name in _contour_intensity_fields():
            with self.subTest(field=field_name):
                self.assertIn(field_name, payload)
                self.assertIsNone(payload[field_name])
        self.assertIsNone(payload["measurement_contour_ratio_1"])
        self.assertIsNone(payload["measurement_contour_ratio_2"])
        self.assertIsNone(payload["measurement_contour_ratio_3"])
        self.assertEqual(payload["measurement_contour_ratio_display_text"], "N/A")

    def test_unavailable_fields_are_null_without_hiding_valid_same_channel_values(self):
        payload = serialize_cell_statistics_payload(
            _cell_stat(
                properties={
                    "selected_analysis": ["PunctaDistance", "GreenRedIntensity"],
                    "signal_quantification_mode": "puncta_distance",
                    "puncta_line_mode": "red_puncta_only",
                    "unavailable_stat_fields": [
                        "puncta_line_intensity",
                        "green_contour_1_size",
                        "green_in_red_total_intensity_1",
                        "measurement_contour_ratio_1",
                        "measurement_contour_ratio_2",
                        "measurement_contour_ratio_3",
                    ],
                },
            )
        )

        self.assertEqual(payload["puncta_distance"], 10.0)
        self.assertIsNone(payload["puncta_line_intensity"])
        self.assertEqual(payload["red_contour_1_size"], 11.0)
        self.assertEqual(payload["red_in_red_total_intensity_1"], 2.0)
        self.assertIsNone(payload["green_contour_1_size"])
        self.assertIsNone(payload["green_in_red_total_intensity_1"])
        self.assertIsNone(payload["measurement_contour_ratio_1"])
        self.assertIsNone(payload["measurement_contour_ratio_2"])
        self.assertIsNone(payload["measurement_contour_ratio_3"])
        self.assertEqual(payload["measurement_contour_ratio_display_text"], "N/A")

    def test_independent_cen_dot_and_biorientation_visibility_follow_selected_analysis(self):
        cen_payload = serialize_cell_statistics_payload(
            _cell_stat(
                properties={
                    "selected_analysis": ["PunctaDistance", "CENDot"],
                    "signal_quantification_mode": "puncta_distance",
                    "cen_dot_schema_version": 3,
                    "cell_parentage": {
                        "status": "identified",
                        "mode": "best_effort",
                        "method": "principal_axis_median",
                        "label": "Mother/Daughter identified",
                    },
                },
            )
        )
        self.assertTrue(cen_payload["stat_visibility"]["cen_dot"])
        self.assertFalse(cen_payload["stat_visibility"]["biorientation"])
        self.assertEqual(cen_payload["category_cen_dot"], 1)
        self.assertEqual(cen_payload["cell_parentage_label"], "Mother/Daughter identified")
        self.assertIsNone(cen_payload["colinear_dots"])
        self.assertIsNone(cen_payload["off_axis_dots"])

        biorientation_payload = serialize_cell_statistics_payload(
            _cell_stat(
                properties={
                    "selected_analysis": ["PunctaDistance", "Biorientation"],
                    "signal_quantification_mode": "puncta_distance",
                },
            )
        )
        self.assertFalse(biorientation_payload["stat_visibility"]["cen_dot"])
        self.assertTrue(biorientation_payload["stat_visibility"]["biorientation"])
        self.assertIsNone(biorientation_payload["category_cen_dot"])
        self.assertEqual(biorientation_payload["category_cen_dot_label"], "N/A")
        self.assertEqual(biorientation_payload["colinear_dots"], 0)
        self.assertEqual(biorientation_payload["off_axis_dots"], 0)

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
                    "red_contour_count": 2,
                    "green_contour_count": 1,
                    "red_contour_count_source": "standard_canonical_slots_v1",
                    "green_contour_count_source": "standard_canonical_slots_v1",
                    "puncta_source_contour_count": 2,
                    "puncta_source_contour_count_channel": "red",
                    "puncta_source_contour_count_source": "standard_canonical_slots_v1",
                },
            )
        )

        self.assertEqual(payload["red_contour_count"], 2)
        self.assertEqual(payload["green_contour_count"], 1)
        self.assertEqual(
            payload["red_contour_count_source"],
            "standard_canonical_slots_v1",
        )
        self.assertEqual(payload["puncta_source_contour_count"], 2)
        self.assertEqual(payload["puncta_source_contour_count_channel"], "red")
        self.assertEqual(
            payload["puncta_source_contour_count_source"],
            "standard_canonical_slots_v1",
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

    def test_old_payload_without_contour_count_metadata_still_serializes(self):
        payload = serialize_cell_statistics_payload(
            _cell_stat(
                properties={
                    "selected_analysis": ["PunctaDistance", "GreenRedIntensity"],
                    "nuclear_cell_pair_mode": "green_nucleus",
                    "puncta_line_mode": "red_puncta",
                },
            )
        )

        self.assertIn("red_contour_count", payload)
        self.assertIn("green_contour_count", payload)
        self.assertIn("puncta_source_contour_count", payload)
        self.assertIsNone(payload["red_contour_count"])
        self.assertIsNone(payload["green_contour_count"])
        self.assertIsNone(payload["puncta_source_contour_count"])
        self.assertNotIn("Puncta Source Contour Count", payload)

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
