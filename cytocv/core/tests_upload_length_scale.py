"""Unit tests for upload-length conversion helpers."""

from types import SimpleNamespace
from django.test import SimpleTestCase
from unittest.mock import patch

from core.cell_analysis import GFPDot
from core.metadata_processing.dv_scale_parser import extract_dv_scale_metadata
from core.scale import (
    apply_manual_override_scale,
    build_scale_info,
    clear_manual_override_scale,
    convert_pixel_delta_to_microns,
    convert_length_to_pixels,
    get_scale_sidebar_payload,
    normalize_scale_info,
    parse_microns_per_pixel,
    resolve_scale_context,
)
from core.views.upload_images import (
    _convert_length_to_pixels,
    _normalize_length_unit,
    _parse_positive_float,
)


class UploadLengthScaleHelperTests(SimpleTestCase):
    def test_normalize_length_unit_defaults_to_px(self):
        self.assertEqual(_normalize_length_unit("bad"), "px")
        self.assertEqual(_normalize_length_unit("UM"), "um")

    def test_parse_positive_float_enforces_minimum(self):
        self.assertEqual(_parse_positive_float("0.25", default=0.1, minimum=0.0001), 0.25)
        self.assertEqual(_parse_positive_float("-1", default=0.1, minimum=0.0001), 0.1)
        self.assertEqual(_parse_positive_float("abc", default=0.1, minimum=0.0001), 0.1)

    def test_convert_length_to_pixels_uses_px_value_directly(self):
        self.assertEqual(
            _convert_length_to_pixels(
                5,
                "px",
                minimum_px=1,
                fallback_px=1,
                microns_per_pixel=0.1,
            ),
            5,
        )

    def test_convert_length_to_pixels_converts_um_using_shared_scale(self):
        self.assertEqual(
            _convert_length_to_pixels(
                1.2,
                "um",
                minimum_px=0,
                fallback_px=37,
                microns_per_pixel=0.1,
            ),
            12,
        )

    def test_convert_length_to_pixels_falls_back_on_invalid_scale(self):
        self.assertEqual(
            _convert_length_to_pixels(
                3.0,
                "um",
                minimum_px=1,
                fallback_px=1,
                microns_per_pixel=0.0,
            ),
            1,
        )

    def test_shared_convert_length_to_pixels_uses_file_specific_um_per_px(self):
        narrower_scale_px = convert_length_to_pixels(
            1.2,
            "um",
            minimum_px=1,
            fallback_px=1,
            um_per_px=0.1,
        )
        wider_scale_px = convert_length_to_pixels(
            1.2,
            "um",
            minimum_px=1,
            fallback_px=1,
            um_per_px=0.2,
        )
        self.assertEqual(narrower_scale_px, 12)
        self.assertEqual(wider_scale_px, 6)


class ScaleInfoNormalizationTests(SimpleTestCase):
    def test_build_scale_info_uses_metadata_when_enabled(self):
        info = build_scale_info(
            manual_um_per_px=0.2,
            prefer_metadata=True,
            metadata_um_per_px=0.11,
            status="ok",
        )
        self.assertEqual(info["source"], "metadata")
        self.assertEqual(info["effective_um_per_px"], 0.11)

    def test_build_scale_info_falls_back_to_manual_when_metadata_missing(self):
        info = build_scale_info(
            manual_um_per_px=0.2,
            prefer_metadata=True,
            metadata_um_per_px=None,
            status="missing",
        )
        self.assertEqual(info["source"], "manual_fallback")
        self.assertEqual(info["effective_um_per_px"], 0.2)
        self.assertIn("manual", info["note"].lower())

    def test_apply_manual_override_marks_source(self):
        info = build_scale_info(
            manual_um_per_px=0.2,
            prefer_metadata=True,
            metadata_um_per_px=0.11,
            status="ok",
        )
        overridden = apply_manual_override_scale(info, effective_um_per_px=0.3)
        self.assertEqual(overridden["source"], "manual_override")
        self.assertEqual(overridden["effective_um_per_px"], 0.3)

    def test_clear_manual_override_restores_metadata_source(self):
        info = apply_manual_override_scale(
            build_scale_info(
                manual_um_per_px=0.2,
                prefer_metadata=True,
                metadata_um_per_px=0.11,
                status="ok",
            ),
            effective_um_per_px=0.3,
        )
        restored = clear_manual_override_scale(info)
        self.assertEqual(restored["source"], "metadata")
        self.assertAlmostEqual(restored["effective_um_per_px"], 0.11, places=6)

    def test_sidebar_payload_includes_warning_for_manual_fallback(self):
        info = build_scale_info(
            manual_um_per_px=0.2,
            prefer_metadata=True,
            metadata_um_per_px=None,
            status="missing",
        )
        payload = get_scale_sidebar_payload(info)
        self.assertTrue(payload["is_warning"])
        self.assertEqual(payload["source_label"], "Manual fallback")

    def test_normalize_scale_info_uses_default_manual_for_invalid_payload(self):
        normalized = normalize_scale_info({"effective_um_per_px": "bad"}, manual_default=0.33)
        self.assertAlmostEqual(normalized["effective_um_per_px"], 0.33, places=6)
        self.assertEqual(normalized["source"], "manual_fallback")

    def test_resolve_scale_context_uses_xy_metadata_when_available(self):
        info = build_scale_info(
            manual_um_per_px=0.2,
            prefer_metadata=True,
            metadata_um_per_px=0.15,
            status="anisotropic_avg",
            dx=0.1,
            dy=0.2,
        )
        resolved = resolve_scale_context(info)
        self.assertEqual(resolved["distance_mode"], "anisotropic_xy")
        self.assertTrue(resolved["is_anisotropic"])
        self.assertAlmostEqual(resolved["x_um_per_px"], 0.1, places=6)
        self.assertAlmostEqual(resolved["y_um_per_px"], 0.2, places=6)
        self.assertAlmostEqual(resolved["line_width_proxy_um_per_px"], (0.1 * 0.2) ** 0.5, places=6)

    def test_resolve_scale_context_manual_override_stays_scalar(self):
        info = apply_manual_override_scale(
            build_scale_info(
                manual_um_per_px=0.2,
                prefer_metadata=True,
                metadata_um_per_px=0.15,
                status="anisotropic_avg",
                dx=0.1,
                dy=0.2,
            ),
            effective_um_per_px=0.3,
        )
        resolved = resolve_scale_context(info)
        self.assertEqual(resolved["distance_mode"], "scalar")
        self.assertFalse(resolved["is_anisotropic"])
        self.assertAlmostEqual(resolved["x_um_per_px"], 0.3, places=6)
        self.assertAlmostEqual(resolved["y_um_per_px"], 0.3, places=6)

    def test_parse_microns_per_pixel_rejects_invalid_values(self):
        self.assertEqual(parse_microns_per_pixel("abc", default=0.2), 0.2)
        self.assertEqual(parse_microns_per_pixel("-1", default=0.2), 0.2)
        self.assertEqual(parse_microns_per_pixel("0.15", default=0.2), 0.15)

    def test_sidebar_payload_labels_anisotropic_metadata_mode(self):
        info = build_scale_info(
            manual_um_per_px=0.2,
            prefer_metadata=True,
            metadata_um_per_px=0.15,
            status="anisotropic_avg",
            dx=0.1,
            dy=0.2,
        )
        payload = get_scale_sidebar_payload(info)
        self.assertEqual(payload["source_label"], "Anisotropic auto")
        self.assertIn("dx", payload["scale_summary_label"])
        self.assertIn("dy", payload["scale_summary_label"])
        self.assertTrue(payload["is_warning"])


class AnisotropicDistanceConversionTests(SimpleTestCase):
    def test_convert_pixel_delta_to_microns_uses_axis_scales(self):
        # 10 px in X + 10 px in Y with dx=0.1, dy=0.2
        value = convert_pixel_delta_to_microns(
            10,
            10,
            x_um_per_px=0.1,
            y_um_per_px=0.2,
        )
        self.assertAlmostEqual(value, (1.0**2 + 2.0**2) ** 0.5, places=6)

    def test_gfpdot_distance_switches_to_physical_um_when_unit_is_um(self):
        plugin = GFPDot()
        plugin.cp = SimpleNamespace(
            properties={
                "stats_gfp_distance_unit": "um",
                "scale_x_um_per_px": 0.1,
                "scale_y_um_per_px": 0.2,
            }
        )
        value = plugin._distance_between_centers((0, 0), (10, 0), threshold_unit="um")
        self.assertAlmostEqual(value, 1.0, places=6)

    def test_gfpdot_distance_remains_pixel_based_for_px_threshold(self):
        plugin = GFPDot()
        plugin.cp = SimpleNamespace(properties={"stats_gfp_distance_unit": "px"})
        value = plugin._distance_between_centers((0, 0), (10, 0), threshold_unit="px")
        self.assertAlmostEqual(value, 10.0, places=6)

    def test_gfpdot_threshold_comparison_changes_with_anisotropic_scale(self):
        plugin = GFPDot()
        plugin.cp = SimpleNamespace(
            properties={
                "stats_gfp_distance_unit": "um",
                "scale_x_um_per_px": 0.2,
                "scale_y_um_per_px": 0.2,
            }
        )
        self.assertTrue(plugin._is_distance_above_threshold((0, 0), (10, 0), 1.5))

        plugin.cp = SimpleNamespace(
            properties={
                "stats_gfp_distance_unit": "um",
                "scale_x_um_per_px": 0.1,
                "scale_y_um_per_px": 0.1,
            }
        )
        self.assertFalse(plugin._is_distance_above_threshold((0, 0), (10, 0), 1.5))


class DVScaleMetadataParserTests(SimpleTestCase):
    @patch("core.metadata_processing.dv_scale_parser.DVFile")
    def test_extract_dv_scale_metadata_ok(self, dv_cls):
        dv = dv_cls.return_value
        dv.metadata = {"header": {"dx": 0.11, "dy": 0.11, "dz": 0.25}}
        payload = extract_dv_scale_metadata("dummy.dv")
        self.assertEqual(payload["status"], "ok")
        self.assertAlmostEqual(payload["metadata_um_per_px"], 0.11, places=6)
        self.assertAlmostEqual(payload["dx"], 0.11, places=6)
        self.assertAlmostEqual(payload["dy"], 0.11, places=6)
        self.assertAlmostEqual(payload["dz"], 0.25, places=6)

    @patch("core.metadata_processing.dv_scale_parser.DVFile")
    def test_extract_dv_scale_metadata_anisotropic_average(self, dv_cls):
        dv = dv_cls.return_value
        dv.metadata = {"header": {"dx": 0.1, "dy": 0.2}}
        payload = extract_dv_scale_metadata("dummy.dv")
        self.assertEqual(payload["status"], "anisotropic_avg")
        self.assertAlmostEqual(payload["metadata_um_per_px"], 0.15, places=6)
        self.assertIn("average", payload["note"].lower())

    @patch("core.metadata_processing.dv_scale_parser.DVFile")
    def test_extract_dv_scale_metadata_missing(self, dv_cls):
        dv = dv_cls.return_value
        dv.metadata = {"header": {}}
        payload = extract_dv_scale_metadata("dummy.dv")
        self.assertEqual(payload["status"], "missing")
        self.assertIsNone(payload["metadata_um_per_px"])

    @patch("core.metadata_processing.dv_scale_parser.DVFile")
    def test_extract_dv_scale_metadata_invalid(self, dv_cls):
        dv = dv_cls.return_value
        dv.metadata = {"header": {"dx": -0.1, "dy": "nan"}}
        payload = extract_dv_scale_metadata("dummy.dv")
        self.assertEqual(payload["status"], "invalid")
        self.assertIsNone(payload["metadata_um_per_px"])
