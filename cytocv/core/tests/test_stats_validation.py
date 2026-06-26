from django.test import SimpleTestCase
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import cv2
import numpy as np
import tifffile

from core.cell_analysis import (
    BlueNucleusIntensity,
    GreenRedIntensity,
    NucleusIntensity,
    PunctaDistance,
    RedBlueIntensity,
)
from core.channel_ordering import (
    channel_order_to_config,
    normalize_channel_order,
    validate_channel_order,
)
from core.config import DEFAULT_CHANNEL_CONFIG
from core.image_processing import GrayImage
from core.metadata_processing.error_handling.source_image_validation import (
    SourceImageValidationOptions,
    SourceImageValidationResult,
    build_source_image_error_messages,
    get_effective_required_channels,
    validate_source_image_file,
)
from core.metadata_processing.dv_channel_parser import (
    extract_channel_config,
    extract_dv_metadata_channel_config,
)
from core.services.channel_presence import resolve_channel_config_and_presence_for_source
from core.stats_plugins import build_plugin_ui_payload, build_requirement_summary, normalize_selected_plugins


class ChannelOrderingHelperTests(SimpleTestCase):
    def test_normalize_channel_order_accepts_display_labels(self):
        self.assertEqual(
            normalize_channel_order(["Green", "DIC", "Red", "Blue"]),
            ["channel_green", "DIC", "channel_red", "channel_blue"],
        )

    def test_validate_channel_order_rejects_duplicates(self):
        self.assertIsNone(validate_channel_order(["DIC", "Blue", "Blue", "Red"]))

    def test_channel_order_to_config_maps_image_plane_indices(self):
        self.assertEqual(
            channel_order_to_config(["DIC", "Blue", "Green", "Red"]),
            {
                "DIC": 0,
                "channel_blue": 1,
                "channel_green": 2,
                "channel_red": 3,
            },
        )


class StatsRequirementTests(SimpleTestCase):
    def test_default_required_channel_is_dic_only(self):
        summary = build_requirement_summary([])
        self.assertEqual(summary["required_channels"], ["DIC"])

    def test_dapi_nucleus_requires_dapi_plus_dic(self):
        summary = build_requirement_summary(["BlueNucleusIntensity"])
        self.assertEqual(summary["required_channels"], ["DIC", "channel_blue"])

    def test_nuclear_cell_pair_requires_dic_red_green(self):
        summary = build_requirement_summary(["NuclearCellPairIntensity"])
        self.assertEqual(summary["required_channels"], ["DIC", "channel_red", "channel_green"])

    def test_puncta_single_channel_modes_require_only_source_color_plus_dic(self):
        red_only = build_requirement_summary(
            ["PunctaDistance"],
            puncta_line_mode="red_puncta_only",
        )
        green_only = build_requirement_summary(
            ["PunctaDistance"],
            puncta_line_mode="green_puncta_only",
        )

        self.assertEqual(red_only["required_channels"], ["DIC", "channel_red"])
        self.assertEqual(green_only["required_channels"], ["DIC", "channel_green"])

    def test_exclusive_group_keeps_first_plugin_in_order(self):
        selected = normalize_selected_plugins(["NucleusIntensity", "NuclearCellPairIntensity", "BlueNucleusIntensity"])
        self.assertIn("NuclearCellPairIntensity", selected)
        self.assertNotIn("NucleusIntensity", selected)
        self.assertNotIn("BlueNucleusIntensity", selected)

    def test_plugin_payload_includes_legacy_metadata(self):
        payload = build_plugin_ui_payload()
        self.assertEqual(
            [item["id"] for item in payload["plugins"][:5]],
            [
                "NuclearCellPairIntensity",
                "PunctaDistance",
                "GreenRedIntensity",
                "CENDot",
                "Biorientation",
            ],
        )
        plugins = {item["id"]: item for item in payload["plugins"]}
        self.assertEqual(plugins["NuclearCellPairIntensity"]["exclusive_group"], "nuclear_cell_pair")
        self.assertFalse(plugins["NuclearCellPairIntensity"]["is_legacy"])
        self.assertTrue(plugins["NucleusIntensity"]["is_legacy"])
        description = plugins["NuclearCellPairIntensity"]["description"].lower()
        self.assertIn("selected channel", description)
        self.assertIn("opposite", description)

    def test_plugin_payload_exposes_all_puncta_line_modes(self):
        payload = build_plugin_ui_payload()
        plugins = {item["id"]: item for item in payload["plugins"]}
        expected_modes = [
            ("red_puncta", "Red Puncta (Measure Green)", {"channel_red", "channel_green"}),
            ("green_puncta", "Green Puncta (Measure Red)", {"channel_red", "channel_green"}),
            ("red_puncta_only", "Red Puncta Only", {"channel_red"}),
            ("green_puncta_only", "Green Puncta Only", {"channel_green"}),
        ]

        for mode_options in (payload["puncta_line_modes"], plugins["PunctaDistance"]["puncta_line_modes"]):
            with self.subTest(mode_options=mode_options):
                self.assertEqual(
                    [(item["value"], item["text"]) for item in mode_options],
                    [(value, label) for value, label, _required in expected_modes],
                )
                for item, (_value, _label, required_channels) in zip(mode_options, expected_modes):
                    self.assertEqual(set(item["required_channels"]), required_channels)

        self.assertEqual(plugins["GreenRedIntensity"]["puncta_line_modes"], [])


class SourceImageErrorMessageTests(SimpleTestCase):
    def test_missing_channels_are_grouped_by_combination(self):
        options = SourceImageValidationOptions(
            enforce_layer_count=True,
            enforce_wavelengths=False,
            required_channels={"DIC", "channel_blue"},
        )
        failures = [
            ("file_a", SourceImageValidationResult(False, 4, {"channel_blue"}, required_channels={"DIC", "channel_blue"})),
            ("file_b", SourceImageValidationResult(False, 4, {"channel_blue"}, required_channels={"DIC", "channel_blue"})),
            ("file_c", SourceImageValidationResult(False, 4, {"DIC", "channel_blue"}, required_channels={"DIC", "channel_blue"})),
        ]

        lines = build_source_image_error_messages(failures, options)
        message_blob = "\n".join(lines)
        self.assertIn("The following wavelengths are required: DIC, Blue.", message_blob)
        self.assertIn("- file_a.dv, file_b.dv: missing Blue", message_blob)
        self.assertIn("- file_c.dv: missing all required wavelengths", message_blob)

    def test_effective_required_channels_include_advanced_full_toggle(self):
        options = SourceImageValidationOptions(
            enforce_layer_count=True,
            enforce_wavelengths=True,
            required_channels={"DIC"},
        )
        required = get_effective_required_channels(options)
        self.assertEqual(required, {"DIC", "channel_blue", "channel_red", "channel_green"})

    def test_layer_count_errors_not_reported_when_layer_enforcement_is_disabled(self):
        options = SourceImageValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC", "channel_green"},
        )
        failures = [
            ("file_a", SourceImageValidationResult(False, 1, {"channel_green"}, required_channels={"DIC", "channel_green"})),
        ]

        lines = build_source_image_error_messages(failures, options)
        message_blob = "\n".join(lines)
        self.assertIn("missing required wavelengths", message_blob)
        self.assertNotIn("invalid layer counts", message_blob)

    def test_single_required_channel_message_does_not_use_all_required_phrase(self):
        options = SourceImageValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC"},
        )
        failures = [
            ("file_a", SourceImageValidationResult(False, 1, {"DIC"}, required_channels={"DIC"})),
        ]
        lines = build_source_image_error_messages(failures, options)
        message_blob = "\n".join(lines)
        self.assertIn("- file_a.dv: missing DIC", message_blob)
        self.assertNotIn("missing all required wavelengths", message_blob)


class SourceImageValidationPresenceTests(SimpleTestCase):
    def _validate_three_layer_metadata(
        self,
        metadata_config,
        *,
        required_channels,
        configured_experiment_label="Puncta Distance - Red Puncta (Measure Green)",
    ):
        with patch(
            "core.metadata_processing.error_handling.source_image_validation.is_recognized_image_file",
            return_value=True,
        ), patch(
            "core.metadata_processing.error_handling.source_image_validation.get_image_layer_count",
            return_value=3,
        ), patch(
            "core.metadata_processing.error_handling.source_image_validation.extract_reliable_metadata_channel_config",
            return_value=metadata_config,
        ):
            return validate_source_image_file(
                Path("dummy.dv"),
                SourceImageValidationOptions(
                    enforce_layer_count=False,
                    enforce_wavelengths=False,
                    required_channels=set(required_channels),
                    configured_experiment_label=configured_experiment_label,
                ),
            )

    @patch("core.metadata_processing.error_handling.source_image_validation.is_recognized_image_file", return_value=True)
    @patch("core.metadata_processing.error_handling.source_image_validation.get_image_layer_count", return_value=4)
    @patch(
        "core.metadata_processing.error_handling.source_image_validation.extract_channel_config",
        return_value={"DIC": 0, "mCherry": 4, "GFP": 2},
    )
    def test_required_channels_must_exist_in_actual_layer_indices(self, _cfg, _layers, _recognized):
        options = SourceImageValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC", "channel_red", "channel_green"},
        )

        result = validate_source_image_file(Path("dummy.dv"), options)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.missing_channels, {"channel_red"})

    @patch("core.metadata_processing.error_handling.source_image_validation.is_recognized_image_file", return_value=True)
    @patch("core.metadata_processing.error_handling.source_image_validation.get_image_layer_count", return_value=4)
    @patch(
        "core.metadata_processing.error_handling.source_image_validation.extract_channel_config",
        return_value={"DIC": 0, "red": 1, "GFP": 2},
    )
    def test_channel_name_aliases_are_accepted(self, _cfg, _layers, _recognized):
        options = SourceImageValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC", "channel_red", "channel_green"},
        )

        result = validate_source_image_file(Path("dummy.dv"), options)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.missing_channels, set())

    def test_three_layer_metadata_missing_green_accepts_red_only_requirements(self):
        result = self._validate_three_layer_metadata(
            {"DIC": 0, "channel_blue": 1, "channel_red": 2},
            required_channels={"DIC", "channel_red"},
            configured_experiment_label="Puncta Distance - Red Puncta Only",
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.layer_count, 3)
        self.assertEqual(result.missing_channels, set())
        self.assertEqual(result.identified_channels, {"DIC", "channel_blue", "channel_red"})

    def test_three_layer_metadata_missing_green_rejects_paired_requirements(self):
        result = self._validate_three_layer_metadata(
            {"DIC": 0, "channel_blue": 1, "channel_red": 2},
            required_channels={"DIC", "channel_red", "channel_green"},
            configured_experiment_label="Puncta Distance - Red Puncta (Measure Green)",
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(result.missing_channels, {"channel_green"})
        self.assertIn("has 3 layers", result.error_message)
        self.assertIn("Metadata identified: DIC, Blue, Red", result.error_message)
        self.assertIn("requires: DIC, Red, Green", result.error_message)
        self.assertIn("Missing required channel(s): Green", result.error_message)
        self.assertIn("Red Puncta Only", result.error_message)
        self.assertNotIn("select which non-DIC channel is missing", result.error_message)

    def test_three_layer_metadata_missing_red_accepts_green_only_requirements(self):
        result = self._validate_three_layer_metadata(
            {"DIC": 0, "channel_blue": 1, "channel_green": 2},
            required_channels={"DIC", "channel_green"},
            configured_experiment_label="Puncta Distance - Green Puncta Only",
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.identified_channels, {"DIC", "channel_blue", "channel_green"})

    def test_three_layer_metadata_missing_red_rejects_paired_requirements(self):
        result = self._validate_three_layer_metadata(
            {"DIC": 0, "channel_blue": 1, "channel_green": 2},
            required_channels={"DIC", "channel_red", "channel_green"},
            configured_experiment_label="Puncta Distance - Green Puncta (Measure Red)",
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.missing_channels, {"channel_red"})
        self.assertIn("Missing required channel(s): Red", result.error_message)
        self.assertIn("Green Puncta Only", result.error_message)

    def test_three_layer_metadata_missing_blue_accepts_red_green_requirements(self):
        result = self._validate_three_layer_metadata(
            {"DIC": 0, "channel_red": 1, "channel_green": 2},
            required_channels={"DIC", "channel_red", "channel_green"},
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.identified_channels, {"DIC", "channel_red", "channel_green"})

    def test_three_layer_metadata_missing_blue_rejects_blue_dependent_requirements(self):
        result = self._validate_three_layer_metadata(
            {"DIC": 0, "channel_red": 1, "channel_green": 2},
            required_channels={"DIC", "channel_blue"},
            configured_experiment_label="Blue Nucleus Intensity",
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.missing_channels, {"channel_blue"})
        self.assertIn("Missing required channel(s): Blue", result.error_message)
        self.assertIn("Disable Blue-dependent analyses", result.error_message)

    def test_three_layer_metadata_missing_dic_is_rejected_for_segmentation(self):
        result = self._validate_three_layer_metadata(
            {"channel_blue": 0, "channel_red": 1, "channel_green": 2},
            required_channels={"DIC", "channel_red"},
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.missing_channels, {"DIC"})
        self.assertIn("Metadata identified: Blue, Red, Green", result.error_message)
        self.assertIn("DIC is required for cell segmentation", result.error_message)

    @patch("core.metadata_processing.error_handling.source_image_validation.is_recognized_image_file", return_value=True)
    @patch("core.metadata_processing.error_handling.source_image_validation.get_image_layer_count", return_value=3)
    def test_three_layer_without_metadata_or_declaration_is_ambiguous(self, _layers, _recognized):
        options = SourceImageValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC", "channel_red"},
            prefer_metadata_channel_order=False,
            configured_experiment_label="Puncta Distance - Red Puncta Only",
        )

        result = validate_source_image_file(Path("dummy.dv"), options)

        self.assertFalse(result.is_valid)
        self.assertIn("has 3 layers", result.error_message)
        self.assertIn("could not identify the present channels from file metadata", result.error_message)
        self.assertIn("requires: DIC, Red", result.error_message)
        self.assertNotIn("select which non-DIC channel is missing", result.error_message)

    @patch("core.services.channel_presence.get_image_layer_count", return_value=3)
    @patch(
        "core.services.channel_presence.extract_reliable_metadata_channel_config",
        return_value={"DIC": 0, "channel_blue": 1, "channel_red": 2},
    )
    def test_three_layer_channel_config_and_presence_use_metadata_only(self, _metadata_config, _layers):
        channel_config, presence = resolve_channel_config_and_presence_for_source(
            Path("dummy.dv"),
            fallback_order=["DIC", "channel_blue", "channel_green", "channel_red"],
        )

        self.assertEqual(
            channel_config,
            {"DIC": 0, "channel_blue": 1, "channel_red": 2},
        )
        self.assertEqual(presence.present_channels, frozenset({"DIC", "channel_blue", "channel_red"}))
        self.assertEqual(presence.missing_channels, frozenset({"channel_green"}))
        self.assertEqual(presence.source, "metadata")
        self.assertEqual(presence.layer_count, 3)
        self.assertTrue(presence.confirmed)


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

    @patch("core.metadata_processing.dv_channel_parser.DVFile")
    def test_header_three_channel_metadata_maps_missing_green_stack(self, dv_file_cls):
        dv = dv_file_cls.return_value
        dv.metadata = {"header": {"nc": 3, "wave1": -50, "wave2": 435, "wave3": 625}}

        config = extract_dv_metadata_channel_config(Path("dummy.dv"))

        self.assertEqual(
            config,
            {
                "DIC": 0,
                "channel_blue": 1,
                "channel_red": 2,
            },
        )

    @patch("core.metadata_processing.dv_channel_parser.DVFile")
    def test_header_duplicate_channel_roles_are_not_reliable_metadata(self, dv_file_cls):
        dv = dv_file_cls.return_value
        dv.metadata = {"header": {"nc": 3, "wave1": -50, "wave2": 625, "wave3": 625}}

        config = extract_dv_metadata_channel_config(Path("dummy.dv"))

        self.assertEqual(config, {})

    @patch("core.metadata_processing.dv_channel_parser.extract_dv_metadata_channel_config", return_value={})
    def test_dv_uses_fallback_order_when_metadata_unavailable(self, _metadata_config):
        config = extract_channel_config(
            Path("dummy.dv"),
            fallback_order=["Green", "DIC", "Red", "Blue"],
        )

        self.assertEqual(
            config,
            {
                "channel_green": 0,
                "DIC": 1,
                "channel_red": 2,
                "channel_blue": 3,
            },
        )

    @patch("core.metadata_processing.dv_channel_parser.extract_dv_metadata_channel_config")
    def test_dv_skips_metadata_when_disabled(self, metadata_config):
        config = extract_channel_config(
            Path("dummy.dv"),
            prefer_metadata=False,
            fallback_order=["DIC", "Blue", "Green", "Red"],
        )

        metadata_config.assert_not_called()
        self.assertEqual(config, DEFAULT_CHANNEL_CONFIG)

    @patch("core.metadata_processing.error_handling.source_image_validation.is_recognized_image_file", return_value=True)
    @patch("core.metadata_processing.error_handling.source_image_validation.get_image_layer_count", return_value=4)
    @patch(
        "core.metadata_processing.error_handling.source_image_validation.extract_channel_config",
        return_value={"w1DIC": 0},
    )
    def test_dic_name_variants_are_accepted(self, _cfg, _layers, _recognized):
        options = SourceImageValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC"},
        )

        result = validate_source_image_file(Path("dummy.dv"), options)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.missing_channels, set())

    def test_tiff_uses_default_channel_mapping_for_required_channels(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "default_channels.tif"
            tifffile.imwrite(
                path,
                np.ones((4, 5, 6), dtype=np.uint16),
                photometric="minisblack",
            )
            options = SourceImageValidationOptions(
                enforce_layer_count=False,
                enforce_wavelengths=False,
                required_channels={"DIC", "channel_blue", "channel_red", "channel_green"},
            )

            config = extract_channel_config(path)
            result = validate_source_image_file(path, options)

        self.assertEqual(config, DEFAULT_CHANNEL_CONFIG)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.missing_channels, set())

    def test_tiff_layer_count_enforcement_uses_stack_pages(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "three_layers.tiff"
            tifffile.imwrite(
                path,
                np.ones((3, 5, 6), dtype=np.uint16),
                photometric="minisblack",
            )
            options = SourceImageValidationOptions(
                enforce_layer_count=True,
                enforce_wavelengths=False,
                required_channels=set(),
            )

            result = validate_source_image_file(path, options)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.layer_count, 3)


class AnalysisRegressionTests(SimpleTestCase):
    @staticmethod
    def _rect_contour(x1: int, y1: int, x2: int, y2: int):
        return np.array(
            [[[x1, y1]], [[x2, y1]], [[x2, y2]], [[x1, y2]]],
            dtype=np.int32,
        )

    def test_green_red_intensity_does_not_bool_evaluate_numpy_arrays(self):
        plugin = GreenRedIntensity()
        cp = SimpleNamespace(properties={"nuclear_cell_pair_mode": "red_nucleus"})
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
            puncta_line_width_input=1,
            cen_dot_distance=37,
        )

        self.assertEqual(cp.red_in_red_total_intensity_1, 0.0)
        self.assertEqual(cp.red_in_red_max_intensity_1, 0.0)
        self.assertEqual(cp.red_in_red_average_intensity_1, 0.0)
        self.assertEqual(cp.green_in_green_total_intensity_1, 0.0)
        self.assertEqual(cp.green_in_green_max_intensity_1, 0.0)
        self.assertEqual(cp.green_in_green_average_intensity_1, 0.0)

    def test_green_red_intensity_uses_red_mode_ratio_when_toggle_targets_red_contours(self):
        plugin = GreenRedIntensity()
        cp = SimpleNamespace(properties={"nuclear_cell_pair_mode": "red_nucleus"})
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
            puncta_line_width_input=1,
            cen_dot_distance=37,
        )

        red_mask = np.zeros(red_image.shape, dtype=np.uint8)
        cv2.drawContours(red_mask, [red_contour], 0, 255, -1)
        green_mask = np.zeros(green_image.shape, dtype=np.uint8)
        cv2.drawContours(green_mask, [green_contour], 0, 255, -1)

        red_in_red_pixels = red_image[red_mask > 0]
        green_in_red_pixels = green_image[red_mask > 0]
        red_in_green_pixels = red_image[green_mask > 0]
        green_in_green_pixels = green_image[green_mask > 0]
        expected_red_in_red = float(np.sum(red_in_red_pixels))
        expected_green_in_red = float(np.sum(green_in_red_pixels))
        expected_red_in_green = float(np.sum(red_in_green_pixels))
        expected_green_in_green = float(np.sum(green_in_green_pixels))

        self.assertEqual(cp.red_in_red_total_intensity_1, expected_red_in_red)
        self.assertEqual(cp.red_in_red_max_intensity_1, float(np.max(red_in_red_pixels)))
        self.assertEqual(cp.red_in_red_average_intensity_1, float(np.mean(red_in_red_pixels)))
        self.assertEqual(cp.green_in_red_total_intensity_1, expected_green_in_red)
        self.assertEqual(cp.green_in_red_max_intensity_1, float(np.max(green_in_red_pixels)))
        self.assertEqual(cp.green_in_red_average_intensity_1, float(np.mean(green_in_red_pixels)))
        self.assertEqual(cp.red_in_green_total_intensity_1, expected_red_in_green)
        self.assertEqual(cp.red_in_green_max_intensity_1, float(np.max(red_in_green_pixels)))
        self.assertEqual(cp.red_in_green_average_intensity_1, float(np.mean(red_in_green_pixels)))
        self.assertEqual(cp.green_in_green_total_intensity_1, expected_green_in_green)
        self.assertEqual(cp.green_in_green_max_intensity_1, float(np.max(green_in_green_pixels)))
        self.assertEqual(cp.green_in_green_average_intensity_1, float(np.mean(green_in_green_pixels)))
        self.assertEqual(
            cp.green_red_intensity_1,
            expected_green_in_red / expected_red_in_red,
        )
        self.assertEqual(cp.red_in_red_total_intensity_2, 0.0)
        self.assertEqual(cp.red_in_red_max_intensity_2, 0.0)
        self.assertEqual(cp.red_in_red_average_intensity_2, 0.0)
        self.assertEqual(cp.green_red_intensity_2, 0.0)

    def test_green_red_intensity_uses_green_mode_ratio_when_toggle_targets_green_contours(self):
        plugin = GreenRedIntensity()
        cp = SimpleNamespace(properties={"nuclear_cell_pair_mode": "green_nucleus"})
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
            puncta_line_width_input=1,
            cen_dot_distance=37,
        )

        green_mask = np.zeros(green_image.shape, dtype=np.uint8)
        cv2.drawContours(green_mask, [green_contour], 0, 255, -1)
        red_in_green_pixels = red_image[green_mask > 0]
        green_in_green_pixels = green_image[green_mask > 0]
        expected_red_in_green = float(np.sum(red_in_green_pixels))
        expected_green_in_green = float(np.sum(green_in_green_pixels))

        self.assertEqual(cp.red_in_green_total_intensity_1, expected_red_in_green)
        self.assertEqual(cp.red_in_green_max_intensity_1, float(np.max(red_in_green_pixels)))
        self.assertEqual(cp.red_in_green_average_intensity_1, float(np.mean(red_in_green_pixels)))
        self.assertEqual(cp.green_in_green_total_intensity_1, expected_green_in_green)
        self.assertEqual(cp.green_in_green_max_intensity_1, float(np.max(green_in_green_pixels)))
        self.assertEqual(cp.green_in_green_average_intensity_1, float(np.mean(green_in_green_pixels)))
        self.assertEqual(
            cp.green_red_intensity_1,
            expected_red_in_green / expected_green_in_green,
        )
        self.assertEqual(cp.green_red_intensity_2, 0.0)

    def test_puncta_distance_prefers_raw_measurement_channel_for_line_sum(self):
        plugin = PunctaDistance()
        cp = SimpleNamespace(properties={"puncta_line_mode": "red_puncta"})
        shape = (10, 10)
        raw_green = np.zeros(shape, dtype=np.uint16)
        processed_green = np.zeros(shape, dtype=np.uint8)
        red_gray = np.zeros(shape, dtype=np.uint8)
        left_red = self._rect_contour(1, 1, 3, 3)
        right_red = self._rect_contour(6, 1, 8, 3)
        line_mask = np.zeros(shape, dtype=np.uint8)
        cv2.line(line_mask, (2, 2), (7, 2), 255, thickness=1)
        raw_green[line_mask > 0] = 1234
        preprocessed = GrayImage(
            img={
                "gray_red": red_gray,
                "red_no_bg": red_gray,
                "green": processed_green,
                "green_no_bg": processed_green,
                "raw_green": raw_green,
            }
        )
        plugin.setting_up(cp, preprocessed, output_dir="")

        plugin.calculate_statistics(
            best_contours={},
            contours_data={"dot_contours": [left_red, right_red], "contours_green": []},
            red_image=np.zeros((*shape, 3), dtype=np.uint8),
            green_image=np.zeros((*shape, 3), dtype=np.uint8),
            puncta_line_width_input=1,
            cen_dot_distance=37,
        )

        self.assertEqual(cp.puncta_line_intensity, float(np.sum(raw_green[line_mask > 0])))

    def test_red_only_puncta_distance_does_not_require_green_measurement_image(self):
        plugin = PunctaDistance()
        cp = SimpleNamespace(
            properties={
                "puncta_line_mode": "red_puncta_only",
                "puncta_contour_intensity_enabled": True,
            }
        )
        shape = (10, 10)
        red_gray = np.zeros(shape, dtype=np.uint8)
        left_red = self._rect_contour(1, 1, 3, 3)
        right_red = self._rect_contour(6, 1, 8, 3)
        red_gray[1:4, 1:4] = 5
        red_gray[1:4, 6:9] = 7
        preprocessed = GrayImage(
            img={
                "gray_red": red_gray,
                "red_no_bg": red_gray,
                "raw_red": red_gray,
            }
        )
        plugin.setting_up(cp, preprocessed, output_dir="")

        points = plugin.calculate_statistics(
            best_contours={},
            contours_data={"dot_contours": [left_red, right_red], "contours_green": []},
            red_image=np.zeros((*shape, 3), dtype=np.uint8),
            green_image=None,
            puncta_line_width_input=1,
            cen_dot_distance=37,
        )

        self.assertGreater(len(points), 0)
        self.assertEqual(cp.puncta_distance, 5.0)
        self.assertFalse(hasattr(cp, "puncta_line_intensity"))
        self.assertGreater(cp.red_contour_1_size, 0.0)
        self.assertGreater(cp.red_in_red_total_intensity_1, 0.0)
        self.assertIn("puncta_line_intensity", cp.properties["unavailable_stat_fields"])
        self.assertIn("green_contour_1_size", cp.properties["unavailable_stat_fields"])
        self.assertIn(
            "measurement_contour_ratio_1",
            cp.properties["unavailable_stat_fields"],
        )

    def test_green_only_puncta_distance_does_not_require_red_measurement_image(self):
        plugin = PunctaDistance()
        cp = SimpleNamespace(
            properties={
                "puncta_line_mode": "green_puncta_only",
                "puncta_contour_intensity_enabled": True,
            }
        )
        shape = (10, 10)
        green_gray = np.zeros(shape, dtype=np.uint8)
        left_green = self._rect_contour(1, 1, 3, 3)
        right_green = self._rect_contour(6, 1, 8, 3)
        green_gray[1:4, 1:4] = 5
        green_gray[1:4, 6:9] = 7
        preprocessed = GrayImage(
            img={
                "green": green_gray,
                "green_no_bg": green_gray,
                "raw_green": green_gray,
            }
        )
        plugin.setting_up(cp, preprocessed, output_dir="")

        points = plugin.calculate_statistics(
            best_contours={},
            contours_data={"dot_contours": [], "contours_green": [left_green, right_green]},
            red_image=None,
            green_image=np.zeros((*shape, 3), dtype=np.uint8),
            puncta_line_width_input=1,
            cen_dot_distance=37,
        )

        self.assertGreater(len(points), 0)
        self.assertEqual(cp.puncta_distance, 5.0)
        self.assertFalse(hasattr(cp, "puncta_line_intensity"))
        self.assertGreater(cp.green_contour_1_size, 0.0)
        self.assertGreater(cp.green_in_green_total_intensity_1, 0.0)
        self.assertIn("puncta_line_intensity", cp.properties["unavailable_stat_fields"])
        self.assertIn("red_contour_1_size", cp.properties["unavailable_stat_fields"])

    def test_legacy_green_nucleus_intensity_prefers_raw_green_values(self):
        plugin = NucleusIntensity()
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={},
            nucleus_intensity={},
        )
        shape = (12, 12)
        raw_green = np.zeros(shape, dtype=np.uint16)
        processed_green = np.ones(shape, dtype=np.uint8)
        blue = np.zeros(shape, dtype=np.uint8)
        contour = self._rect_contour(3, 3, 7, 7)
        mask = np.zeros(shape, dtype=np.uint8)
        cv2.drawContours(mask, [contour], 0, 255, -1)
        raw_green[mask > 0] = 2000
        cell_mask = np.full(shape, 255, dtype=np.uint8)
        preprocessed = GrayImage(
            img={
                "green": processed_green,
                "green_no_bg": processed_green,
                "raw_green": raw_green,
                "gray_blue": blue,
                "gray_blue_3": blue,
            }
        )
        plugin.setting_up(cp, preprocessed, output_dir="")

        plugin.calculate_statistics(
            best_contours={},
            contours_data={"contours_blue": [contour], "cell_mask": cell_mask},
            red_image=None,
            green_image=None,
            puncta_line_width_input=1,
            cen_dot_distance=37,
        )

        self.assertEqual(cp.nucleus_intensity_sum, float(np.sum(raw_green[mask > 0])))
        self.assertEqual(cp.cell_pair_intensity_sum, float(np.sum(raw_green[cell_mask > 0])))

    def test_blue_intensity_plugins_prefer_raw_blue_values(self):
        shape = (12, 12)
        raw_blue = np.zeros(shape, dtype=np.uint16)
        processed_blue = np.ones(shape, dtype=np.uint8)
        contour = self._rect_contour(3, 3, 7, 7)
        mask = np.zeros(shape, dtype=np.uint8)
        cv2.drawContours(mask, [contour], 0, 255, -1)
        raw_blue[mask > 0] = 3000
        cell_mask = np.full(shape, 255, dtype=np.uint8)

        blue_nucleus = BlueNucleusIntensity()
        cp_blue = SimpleNamespace(image_name="test.dv", cell_id=1, properties={})
        preprocessed = GrayImage(
            img={
                "gray_blue": processed_blue,
                "gray_blue_3": processed_blue,
                "raw_blue": raw_blue,
            }
        )
        blue_nucleus.setting_up(cp_blue, preprocessed, output_dir="")
        blue_nucleus.calculate_statistics(
            best_contours={},
            contours_data={"contours_blue": [contour], "cell_mask": cell_mask},
            red_image=None,
            green_image=None,
            puncta_line_width_input=1,
            cen_dot_distance=37,
        )

        red_blue = RedBlueIntensity()
        cp_red_blue = SimpleNamespace(properties={})
        red_blue.setting_up(cp_red_blue, preprocessed, output_dir="")
        red_blue.calculate_statistics(
            best_contours={},
            contours_data={"dot_contours": [contour]},
            red_image=None,
            green_image=None,
            puncta_line_width_input=1,
            cen_dot_distance=37,
        )

        expected_nucleus = float(np.sum(raw_blue[mask > 0]))
        self.assertEqual(cp_blue.nucleus_intensity_sum_blue, expected_nucleus)
        self.assertEqual(cp_blue.cell_pair_intensity_sum_blue, float(np.sum(raw_blue[cell_mask > 0])))
        self.assertEqual(cp_red_blue.red_blue_intensity_1, expected_nucleus)
