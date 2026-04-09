from django.test import SimpleTestCase
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import cv2
import numpy as np

from core.cell_analysis import GreenRedIntensity
from core.image_processing import GrayImage
from core.metadata_processing.error_handling.dv_validation import (
    DVValidationOptions,
    DVValidationResult,
    build_dv_error_messages,
    get_effective_required_channels,
    validate_dv_file,
)
from core.metadata_processing.dv_channel_parser import extract_channel_config
from core.stats_plugins import build_plugin_ui_payload, build_requirement_summary, normalize_selected_plugins


class StatsRequirementTests(SimpleTestCase):
    def test_default_required_channel_is_dic_only(self):
        summary = build_requirement_summary([])
        self.assertEqual(summary["required_channels"], ["DIC"])

    def test_dapi_nucleus_requires_dapi_plus_dic(self):
        summary = build_requirement_summary(["BlueNucleusIntensity"])
        self.assertEqual(summary["required_channels"], ["DIC", "channel_blue"])

    def test_nuclear_cellular_requires_dic_mcherry_gfp(self):
        summary = build_requirement_summary(["NuclearCellularIntensity"])
        self.assertEqual(summary["required_channels"], ["DIC", "channel_red", "channel_green"])

    def test_exclusive_group_keeps_first_plugin_in_order(self):
        selected = normalize_selected_plugins(["NucleusIntensity", "NuclearCellularIntensity", "BlueNucleusIntensity"])
        self.assertIn("NuclearCellularIntensity", selected)
        self.assertNotIn("NucleusIntensity", selected)
        self.assertNotIn("BlueNucleusIntensity", selected)

    def test_plugin_payload_includes_legacy_metadata(self):
        payload = build_plugin_ui_payload()
        plugins = {item["id"]: item for item in payload["plugins"]}
        self.assertEqual(plugins["NuclearCellularIntensity"]["exclusive_group"], "nuclear_cellular")
        self.assertFalse(plugins["NuclearCellularIntensity"]["is_legacy"])
        self.assertTrue(plugins["NucleusIntensity"]["is_legacy"])
        description = plugins["NuclearCellularIntensity"]["description"].lower()
        self.assertIn("selected channel", description)
        self.assertIn("opposite", description)


class DVErrorMessageTests(SimpleTestCase):
    def test_missing_channels_are_grouped_by_combination(self):
        options = DVValidationOptions(
            enforce_layer_count=True,
            enforce_wavelengths=False,
            required_channels={"DIC", "channel_blue"},
        )
        failures = [
            ("file_a", DVValidationResult(False, 4, {"channel_blue"}, required_channels={"DIC", "channel_blue"})),
            ("file_b", DVValidationResult(False, 4, {"channel_blue"}, required_channels={"DIC", "channel_blue"})),
            ("file_c", DVValidationResult(False, 4, {"DIC", "channel_blue"}, required_channels={"DIC", "channel_blue"})),
        ]

        lines = build_dv_error_messages(failures, options)
        message_blob = "\n".join(lines)
        self.assertIn("The following wavelengths are required: DIC, Blue.", message_blob)
        self.assertIn("- file_a.dv, file_b.dv: missing Blue", message_blob)
        self.assertIn("- file_c.dv: missing all required wavelengths", message_blob)

    def test_effective_required_channels_include_advanced_full_toggle(self):
        options = DVValidationOptions(
            enforce_layer_count=True,
            enforce_wavelengths=True,
            required_channels={"DIC"},
        )
        required = get_effective_required_channels(options)
        self.assertEqual(required, {"DIC", "channel_blue", "channel_red", "channel_green"})

    def test_layer_count_errors_not_reported_when_layer_enforcement_is_disabled(self):
        options = DVValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC", "channel_green"},
        )
        failures = [
            ("file_a", DVValidationResult(False, 1, {"channel_green"}, required_channels={"DIC", "channel_green"})),
        ]

        lines = build_dv_error_messages(failures, options)
        message_blob = "\n".join(lines)
        self.assertIn("missing required wavelengths", message_blob)
        self.assertNotIn("invalid layer counts", message_blob)

    def test_single_required_channel_message_does_not_use_all_required_phrase(self):
        options = DVValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC"},
        )
        failures = [
            ("file_a", DVValidationResult(False, 1, {"DIC"}, required_channels={"DIC"})),
        ]
        lines = build_dv_error_messages(failures, options)
        message_blob = "\n".join(lines)
        self.assertIn("- file_a.dv: missing DIC", message_blob)
        self.assertNotIn("missing all required wavelengths", message_blob)


class DVValidationPresenceTests(SimpleTestCase):
    @patch("core.metadata_processing.error_handling.dv_validation.is_recognized_dv_file", return_value=True)
    @patch("core.metadata_processing.error_handling.dv_validation.get_dv_layer_count", return_value=1)
    @patch(
        "core.metadata_processing.error_handling.dv_validation.extract_channel_config",
        return_value={"DIC": 0, "mCherry": 1, "GFP": 2},
    )
    def test_required_channels_must_exist_in_actual_layer_indices(self, _cfg, _layers, _recognized):
        options = DVValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC", "channel_red", "channel_green"},
        )

        result = validate_dv_file(Path("dummy.dv"), options)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.missing_channels, {"channel_red", "channel_green"})

    @patch("core.metadata_processing.error_handling.dv_validation.is_recognized_dv_file", return_value=True)
    @patch("core.metadata_processing.error_handling.dv_validation.get_dv_layer_count", return_value=3)
    @patch(
        "core.metadata_processing.error_handling.dv_validation.extract_channel_config",
        return_value={"DIC": 0, "red": 1, "GFP": 2},
    )
    def test_channel_name_aliases_are_accepted(self, _cfg, _layers, _recognized):
        options = DVValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC", "channel_red", "channel_green"},
        )

        result = validate_dv_file(Path("dummy.dv"), options)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.missing_channels, set())


class DVChannelParserTests(SimpleTestCase):
    @patch("core.metadata_processing.dv_channel_parser.DVFile")
    def test_header_channel_count_precedence_for_dic_only(self, dv_file_cls):
        dv = dv_file_cls.return_value
        dv.metadata = {"header": {"nc": 1, "wave1": -50}}

        config = extract_channel_config(Path("dummy.dv"))

        self.assertEqual(config, {"DIC": 0})
        dv.close.assert_called_once()

    @patch("core.metadata_processing.dv_channel_parser.DVFile")
    def test_header_wave_order_maps_indices_correctly(self, dv_file_cls):
        dv = dv_file_cls.return_value
        dv.metadata = {"header": {"nc": 4, "wave1": 525, "wave2": 625, "wave3": 435, "wave4": -50}}

        config = extract_channel_config(Path("dummy.dv"))

        self.assertEqual(
            config,
            {
                "channel_green": 0,
                "channel_red": 1,
                "channel_blue": 2,
                "DIC": 3,
            },
        )

    @patch("core.metadata_processing.error_handling.dv_validation.is_recognized_dv_file", return_value=True)
    @patch("core.metadata_processing.error_handling.dv_validation.get_dv_layer_count", return_value=1)
    @patch(
        "core.metadata_processing.error_handling.dv_validation.extract_channel_config",
        return_value={"w1DIC": 0},
    )
    def test_dic_name_variants_are_accepted(self, _cfg, _layers, _recognized):
        options = DVValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC"},
        )

        result = validate_dv_file(Path("dummy.dv"), options)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.missing_channels, set())


class AnalysisRegressionTests(SimpleTestCase):
    def test_green_red_intensity_does_not_bool_evaluate_numpy_arrays(self):
        plugin = GreenRedIntensity()
        cp = SimpleNamespace(properties={"nuclear_cellular_mode": "red_nucleus"})
        preprocessed = GrayImage(
            img={
                "red_no_bg": np.ones((8, 8), dtype=np.uint8),
                "gray_red": None,
                "green_no_bg": np.ones((8, 8), dtype=np.uint8),
                "green": None,
            }
        )
        plugin.setting_up(cp, preprocessed, output_dir="")

        plugin.calculate_statistics(
            best_contours={},
            contours_data={"dot_contours": [], "contours_green": []},
            red_image=None,
            green_image=None,
            red_line_width_input=1,
            cen_dot_distance=37,
            cen_dot_collinearity_threshold=66,
        )

        self.assertEqual(cp.red_intensity_1, 0.0)
        self.assertEqual(cp.green_in_green_intensity_1, 0.0)

    def test_green_red_intensity_uses_red_mode_ratio_when_toggle_targets_red_contours(self):
        plugin = GreenRedIntensity()
        cp = SimpleNamespace(properties={"nuclear_cellular_mode": "red_nucleus"})
        red_image = np.array(
            [
                [0, 0, 0, 0, 0],
                [0, 2, 3, 0, 0],
                [0, 5, 7, 0, 0],
                [0, 0, 0, 11, 13],
                [0, 0, 0, 17, 19],
            ],
            dtype=np.uint8,
        )
        green_image = np.array(
            [
                [0, 0, 0, 0, 0],
                [0, 23, 29, 0, 0],
                [0, 31, 37, 0, 0],
                [0, 0, 0, 41, 43],
                [0, 0, 0, 47, 53],
            ],
            dtype=np.uint8,
        )
        preprocessed = GrayImage(
            img={
                "red_no_bg": red_image,
                "gray_red": None,
                "green_no_bg": green_image,
                "green": None,
            }
        )
        plugin.setting_up(cp, preprocessed, output_dir="")

        red_contour = np.array([[[1, 1]], [[1, 2]], [[2, 2]], [[2, 1]]], dtype=np.int32)
        green_contour = np.array([[[3, 3]], [[3, 4]], [[4, 4]], [[4, 3]]], dtype=np.int32)

        plugin.calculate_statistics(
            best_contours={},
            contours_data={
                "dot_contours": [red_contour],
                "contours_green": [green_contour],
            },
            red_image=None,
            green_image=None,
            red_line_width_input=1,
            cen_dot_distance=37,
            cen_dot_collinearity_threshold=66,
        )

        red_mask = np.zeros(red_image.shape, dtype=np.uint8)
        cv2.drawContours(red_mask, [red_contour], 0, 255, -1)
        green_mask = np.zeros(green_image.shape, dtype=np.uint8)
        cv2.drawContours(green_mask, [green_contour], 0, 255, -1)

        expected_red_in_red = float(np.sum(red_image[red_mask > 0]))
        expected_green_in_red = float(np.sum(green_image[red_mask > 0]))
        expected_red_in_green = float(np.sum(red_image[green_mask > 0]))
        expected_green_in_green = float(np.sum(green_image[green_mask > 0]))

        self.assertEqual(cp.red_intensity_1, expected_red_in_red)
        self.assertEqual(cp.green_intensity_1, expected_green_in_red)
        self.assertEqual(cp.red_in_green_intensity_1, expected_red_in_green)
        self.assertEqual(cp.green_in_green_intensity_1, expected_green_in_green)
        self.assertEqual(
            cp.green_red_intensity_1,
            expected_green_in_red / expected_red_in_red,
        )
        self.assertEqual(cp.red_intensity_2, 0.0)
        self.assertEqual(cp.green_red_intensity_2, 0.0)

    def test_green_red_intensity_uses_green_mode_ratio_when_toggle_targets_green_contours(self):
        plugin = GreenRedIntensity()
        cp = SimpleNamespace(properties={"nuclear_cellular_mode": "green_nucleus"})
        red_image = np.array(
            [
                [0, 0, 0, 0, 0],
                [0, 2, 3, 0, 0],
                [0, 5, 7, 0, 0],
                [0, 0, 0, 11, 13],
                [0, 0, 0, 17, 19],
            ],
            dtype=np.uint8,
        )
        green_image = np.array(
            [
                [0, 0, 0, 0, 0],
                [0, 23, 29, 0, 0],
                [0, 31, 37, 0, 0],
                [0, 0, 0, 41, 43],
                [0, 0, 0, 47, 53],
            ],
            dtype=np.uint8,
        )
        preprocessed = GrayImage(
            img={
                "red_no_bg": red_image,
                "gray_red": None,
                "green_no_bg": green_image,
                "green": None,
            }
        )
        plugin.setting_up(cp, preprocessed, output_dir="")

        red_contour = np.array([[[1, 1]], [[1, 2]], [[2, 2]], [[2, 1]]], dtype=np.int32)
        green_contour = np.array([[[3, 3]], [[3, 4]], [[4, 4]], [[4, 3]]], dtype=np.int32)

        plugin.calculate_statistics(
            best_contours={},
            contours_data={
                "dot_contours": [red_contour],
                "contours_green": [green_contour],
            },
            red_image=None,
            green_image=None,
            red_line_width_input=1,
            cen_dot_distance=37,
            cen_dot_collinearity_threshold=66,
        )

        green_mask = np.zeros(green_image.shape, dtype=np.uint8)
        cv2.drawContours(green_mask, [green_contour], 0, 255, -1)
        expected_red_in_green = float(np.sum(red_image[green_mask > 0]))
        expected_green_in_green = float(np.sum(green_image[green_mask > 0]))

        self.assertEqual(cp.red_in_green_intensity_1, expected_red_in_green)
        self.assertEqual(cp.green_in_green_intensity_1, expected_green_in_green)
        self.assertEqual(
            cp.green_red_intensity_1,
            expected_red_in_green / expected_green_in_green,
        )
        self.assertEqual(cp.green_red_intensity_2, 0.0)

