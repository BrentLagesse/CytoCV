from django.test import SimpleTestCase
from pathlib import Path
from unittest.mock import patch

from core.metadata_processing.error_handling.dv_validation import (
    DVValidationOptions,
    DVValidationResult,
    build_dv_error_messages,
    get_effective_required_channels,
    validate_dv_file,
)
from core.metadata_processing.dv_channel_parser import extract_channel_config
from core.stats_plugins import build_requirement_summary


class StatsRequirementTests(SimpleTestCase):
    def test_default_required_channel_is_dic_only(self):
        summary = build_requirement_summary([])
        self.assertEqual(summary["required_channels"], ["DIC"])

    def test_dapi_nucleus_requires_dapi_plus_dic(self):
        summary = build_requirement_summary(["DAPI_NucleusIntensity"])
        self.assertEqual(summary["required_channels"], ["DIC", "DAPI"])


class DVErrorMessageTests(SimpleTestCase):
    def test_missing_channels_are_grouped_by_combination(self):
        options = DVValidationOptions(
            enforce_layer_count=True,
            enforce_wavelengths=False,
            required_channels={"DIC", "DAPI"},
        )
        failures = [
            ("file_a", DVValidationResult(False, 4, {"DAPI"}, required_channels={"DIC", "DAPI"})),
            ("file_b", DVValidationResult(False, 4, {"DAPI"}, required_channels={"DIC", "DAPI"})),
            ("file_c", DVValidationResult(False, 4, {"DIC", "DAPI"}, required_channels={"DIC", "DAPI"})),
        ]

        lines = build_dv_error_messages(failures, options)
        message_blob = "\n".join(lines)
        self.assertIn("The following wavelengths are required: DIC, DAPI.", message_blob)
        self.assertIn("- file_a.dv, file_b.dv: missing DAPI", message_blob)
        self.assertIn("- file_c.dv: missing all required wavelengths", message_blob)

    def test_effective_required_channels_include_advanced_full_toggle(self):
        options = DVValidationOptions(
            enforce_layer_count=True,
            enforce_wavelengths=True,
            required_channels={"DIC"},
        )
        required = get_effective_required_channels(options)
        self.assertEqual(required, {"DIC", "DAPI", "mCherry", "GFP"})

    def test_layer_count_errors_not_reported_when_layer_enforcement_is_disabled(self):
        options = DVValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC", "GFP"},
        )
        failures = [
            ("file_a", DVValidationResult(False, 1, {"GFP"}, required_channels={"DIC", "GFP"})),
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
            required_channels={"DIC", "mCherry", "GFP"},
        )

        result = validate_dv_file(Path("dummy.dv"), options)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.missing_channels, {"mCherry", "GFP"})

    @patch("core.metadata_processing.error_handling.dv_validation.is_recognized_dv_file", return_value=True)
    @patch("core.metadata_processing.error_handling.dv_validation.get_dv_layer_count", return_value=3)
    @patch(
        "core.metadata_processing.error_handling.dv_validation.extract_channel_config",
        return_value={"DIC": 0, "mcherry": 1, "GFP": 2},
    )
    def test_channel_name_aliases_are_accepted(self, _cfg, _layers, _recognized):
        options = DVValidationOptions(
            enforce_layer_count=False,
            enforce_wavelengths=False,
            required_channels={"DIC", "mCherry", "GFP"},
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
                "GFP": 0,
                "mCherry": 1,
                "DAPI": 2,
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
