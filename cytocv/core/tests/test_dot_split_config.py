"""Tests for Red/Green dot split mode configuration plumbing."""

from __future__ import annotations

from django.test import SimpleTestCase

from core.config import DEFAULT_CHANNEL_CONFIG
from core.services.analysis_context import normalize_analysis_config_snapshot
from core.services.overlay_rendering import build_overlay_render_config


class DotSplitConfigTests(SimpleTestCase):
    def test_analysis_snapshot_preserves_green_dot_split_mode(self):
        normalized = normalize_analysis_config_snapshot(
            {
                "greenDotSplitEnabled": True,
                "greenDotSplitMode": "aggressive",
            }
        )

        self.assertTrue(normalized["greenDotSplitEnabled"])
        self.assertEqual(normalized["greenDotSplitMode"], "aggressive")

    def test_analysis_snapshot_defaults_invalid_green_dot_split_mode(self):
        normalized = normalize_analysis_config_snapshot({"greenDotSplitMode": "bad"})

        self.assertEqual(normalized["greenDotSplitMode"], "aggressive")

    def test_analysis_snapshot_preserves_red_dot_split_mode(self):
        normalized = normalize_analysis_config_snapshot(
            {
                "redDotSplitEnabled": False,
                "redDotSplitMode": "aggressive",
            }
        )

        self.assertFalse(normalized["redDotSplitEnabled"])
        self.assertEqual(normalized["redDotSplitMode"], "aggressive")

    def test_analysis_snapshot_defaults_invalid_red_dot_split_mode(self):
        normalized = normalize_analysis_config_snapshot({"redDotSplitMode": "bad"})

        self.assertEqual(normalized["redDotSplitMode"], "aggressive")

    def test_analysis_snapshot_preserves_nuclear_cell_pair_contour_mode(self):
        normalized = normalize_analysis_config_snapshot(
            {"nuclear_cell_pair_contour_mode": "aggressive"}
        )

        self.assertEqual(normalized["nuclear_cell_pair_contour_mode"], "aggressive")

    def test_analysis_snapshot_defaults_invalid_nuclear_cell_pair_contour_mode(self):
        normalized = normalize_analysis_config_snapshot(
            {"nuclear_cell_pair_contour_mode": "bad"}
        )

        self.assertEqual(normalized["nuclear_cell_pair_contour_mode"], "balanced")

    def test_analysis_snapshot_derives_puncta_without_contour_intensity(self):
        normalized = normalize_analysis_config_snapshot(
            {
                "selected_analysis": ["PunctaDistance"],
                "puncta_line_mode": "green_puncta",
            }
        )

        self.assertEqual(normalized["selected_analysis"], ["PunctaDistance"])
        self.assertTrue(normalized["signalQuantificationEnabled"])
        self.assertEqual(normalized["signalQuantificationMode"], "puncta_distance")
        self.assertFalse(normalized["punctaContourIntensityEnabled"])

    def test_analysis_snapshot_derives_nuclear_mode_and_alternate_target(self):
        normalized = normalize_analysis_config_snapshot(
            {
                "selected_analysis": ["PunctaDistance", "GreenRedIntensity", "CENDot"],
                "signalQuantificationEnabled": True,
                "signalQuantificationMode": "nuclear_cell_pair",
                "alternateNucleusDetectionEnabled": True,
                "nuclear_cell_pair_mode": "red_nucleus",
            }
        )

        self.assertEqual(
            normalized["selected_analysis"],
            ["NuclearCellPairIntensity"],
        )
        self.assertEqual(normalized["signalQuantificationMode"], "nuclear_cell_pair")
        self.assertTrue(normalized["alternateNucleusDetectionEnabled"])
        self.assertEqual(normalized["alternateNucleusDetectionChannel"], "channel_red")

    def test_overlay_render_config_preserves_green_dot_split_mode(self):
        config = build_overlay_render_config(
            image_stem="sample",
            channel_config=DEFAULT_CHANNEL_CONFIG,
            kernel_size=3,
            kernel_deviation=1,
            puncta_line_width=1,
            arrested="Metaphase Arrested",
            selected_analysis=["Biorientation"],
            puncta_line_mode="red_puncta",
            nuclear_cell_pair_mode="green_nucleus",
            puncta_line_width_px=1,
            cen_dot_distance_value_used=37.0,
            green_contour_filter_enabled=False,
            alternate_red_detection=False,
            green_dot_split_enabled=True,
            green_dot_split_mode="aggressive",
            red_dot_split_enabled=False,
            red_dot_split_mode="aggressive",
            nuclear_cell_pair_contour_mode="aggressive",
        )

        self.assertTrue(config["green_dot_split_enabled"])
        self.assertEqual(config["green_dot_split_mode"], "aggressive")
        self.assertFalse(config["red_dot_split_enabled"])
        self.assertEqual(config["red_dot_split_mode"], "aggressive")
        self.assertEqual(config["nuclear_cell_pair_contour_mode"], "aggressive")
