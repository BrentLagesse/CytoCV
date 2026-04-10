from __future__ import annotations

import math
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase

from core.image_processing import GrayImage
from core.stats_plugins import build_stats_execution_plan
from core.views.segment_image import get_stats


class ModernContourStatisticsTests(SimpleTestCase):
    @staticmethod
    def _rect_contour(x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        return np.array(
            [[[x1, y1]], [[x2, y1]], [[x2, y2]], [[x1, y2]]],
            dtype=np.int32,
        )

    @staticmethod
    def _rgb(image: np.ndarray) -> np.ndarray:
        return np.dstack([image, image, image]).astype(np.uint8)

    @staticmethod
    def _write_outline(output_dir: Path, *, image_stem: str = "test", cell_id: int = 1, y_range=range(0), x_range=range(0)) -> None:
        output_path = output_dir / "output"
        output_path.mkdir(parents=True, exist_ok=True)
        outline_path = output_path / f"{image_stem}-{cell_id}.outline"
        with outline_path.open("w", encoding="utf-8") as handle:
            for y in y_range:
                for x in x_range:
                    handle.write(f"{y},{x}\n")

    @staticmethod
    def _conf(
        output_dir: str,
        *,
        mode: str,
        analysis: list[str],
        puncta_line_mode: str = "red_puncta",
    ) -> dict:
        return {
            "input_dir": output_dir,
            "output_dir": output_dir,
            "kernel_size": 3,
            "puncta_line_width": 1,
            "kernel_deviation": 1,
            "arrested": "Metaphase Arrested",
            "analysis": analysis,
            "puncta_line_mode": puncta_line_mode,
            "nuclear_cell_pair_mode": mode,
        }

    def _run_get_stats(
        self,
        *,
        mode: str,
        selected_analysis: list[str],
        red_gray: np.ndarray,
        green_gray: np.ndarray,
        contours_data: dict,
        y_range,
        x_range,
        puncta_line_mode: str = "red_puncta",
        cen_dot_distance: float = 37.0,
        cen_dot_collinearity_threshold: int = 66,
    ):
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={},
        )
        images = {
            "red": self._rgb(red_gray),
            "green": self._rgb(green_gray),
            "blue": self._rgb(np.zeros_like(red_gray)),
        }
        preprocessed = GrayImage(
            img={
                "red_no_bg": red_gray,
                "gray_red": red_gray,
                "green_no_bg": green_gray,
                "green": green_gray,
                "gray_blue": np.zeros_like(red_gray),
                "gray_blue_3": np.zeros_like(red_gray),
            }
        )
        execution_plan = build_stats_execution_plan(selected_analysis)

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_outline(
                output_dir,
                y_range=y_range,
                x_range=x_range,
            )
            with patch("core.views.segment_image.load_image", return_value=images), patch(
                "core.views.segment_image.preprocess_image_to_gray",
                return_value=preprocessed,
            ), patch(
                "core.views.segment_image.find_contours",
                return_value=contours_data,
            ):
                debug_red, debug_green, debug_blue = get_stats(
                    cp,
                    self._conf(
                        temp_dir,
                        mode=mode,
                        analysis=selected_analysis,
                        puncta_line_mode=puncta_line_mode,
                    ),
                    execution_plan,
                    puncta_line_width=1,
                    cen_dot_distance=cen_dot_distance,
                    cen_dot_collinearity_threshold=cen_dot_collinearity_threshold,
                )

        return cp, np.array(debug_red), np.array(debug_green), np.array(debug_blue)

    def test_red_nucleus_uses_same_clipped_slot_for_green_in_red_and_green_nuclear(self):
        shape = (16, 16)
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        green_gray[4:12, 4:12] = 3
        raw_red_contour = self._rect_contour(2, 2, 10, 10)
        contours_data = {"dot_contours": [raw_red_contour], "contours_green": []}

        cp, debug_red, _, _ = self._run_get_stats(
            mode="red_nucleus",
            selected_analysis=["GreenRedIntensity", "NuclearCellPairIntensity"],
            red_gray=red_gray,
            green_gray=green_gray,
            contours_data=contours_data,
            y_range=range(4, 12),
            x_range=range(4, 12),
        )

        raw_mask = np.zeros(shape, np.uint8)
        raw_mask[4:11, 4:11] = 255
        expected_green = float(np.sum(green_gray[raw_mask > 0]))
        self.assertEqual(cp.green_intensity_1, expected_green)
        self.assertEqual(cp.nucleus_intensity_sum, expected_green)
        self.assertEqual(cp.properties["nuclear_cell_pair_contour_source"], "canonical_slot_1")
        self.assertTrue(np.array_equal(debug_red[2, 5], np.array([0, 0, 0], dtype=np.uint8)))
        self.assertTrue(np.array_equal(debug_red[4, 5], np.array([255, 0, 0], dtype=np.uint8)))

    def test_green_nucleus_ranks_green_slots_and_matches_red_nuclear_to_slot_one(self):
        shape = (20, 20)
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        red_gray[10:18, 10:18] = 4
        red_gray[2:6, 2:6] = 1
        raw_red_contour = self._rect_contour(1, 1, 18, 18)
        small_green = self._rect_contour(2, 2, 5, 5)
        large_green = self._rect_contour(10, 10, 17, 17)
        contours_data = {
            "dot_contours": [raw_red_contour],
            "contours_green": [small_green, large_green],
        }

        cp, _, _, _ = self._run_get_stats(
            mode="green_nucleus",
            selected_analysis=["GreenRedIntensity", "NuclearCellPairIntensity"],
            red_gray=red_gray,
            green_gray=green_gray,
            contours_data=contours_data,
            y_range=range(1, 19),
            x_range=range(1, 19),
        )

        expected_red = float(np.sum(red_gray[10:18, 10:18]))
        self.assertGreater(cp.green_contour_1_size, cp.green_contour_2_size)
        self.assertEqual(cp.red_in_green_intensity_1, expected_red)
        self.assertEqual(cp.nucleus_intensity_sum, expected_red)
        self.assertLess(cp.red_in_green_intensity_2, cp.red_in_green_intensity_1)

    def test_reversed_red_contour_order_aligns_sizes_intensities_line_distance_and_cen_dot(self):
        shape = (80, 80)
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        tiny_red = self._rect_contour(5, 5, 8, 8)
        huge_red = self._rect_contour(50, 10, 64, 24)
        medium_red = self._rect_contour(10, 50, 20, 60)
        green_near_huge = self._rect_contour(55, 15, 58, 18)
        green_near_medium = self._rect_contour(13, 53, 16, 56)

        red_gray[5:9, 5:9] = 10
        red_gray[10:25, 50:65] = 10
        red_gray[50:61, 10:21] = 10
        green_gray[15:19, 55:59] = 10
        green_gray[53:57, 13:17] = 10

        contours_data = {
            "dot_contours": [tiny_red, huge_red, medium_red],
            "contours_green": [green_near_medium, green_near_huge],
        }

        cp, _, _, _ = self._run_get_stats(
            mode="red_nucleus",
            selected_analysis=["PunctaDistance", "CENDot", "GreenRedIntensity"],
            red_gray=red_gray,
            green_gray=green_gray,
            contours_data=contours_data,
            y_range=range(0, 80),
            x_range=range(0, 80),
            cen_dot_distance=5.0,
        )

        self.assertGreater(cp.red_contour_1_size, cp.red_contour_2_size)
        self.assertGreater(cp.red_contour_2_size, cp.red_contour_3_size)
        self.assertGreater(cp.red_intensity_1, cp.red_intensity_2)
        self.assertGreater(cp.red_intensity_2, cp.red_intensity_3)
        self.assertAlmostEqual(cp.puncta_distance, math.dist((57.0, 17.0), (15.0, 55.0)), places=4)
        self.assertEqual(cp.category_cen_dot, 1)

    def test_green_puncta_mode_measures_red_intensity_over_green_line(self):
        shape = (16, 16)
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        red_gray[5, 3:10] = 2
        green_left = self._rect_contour(2, 4, 4, 6)
        green_right = self._rect_contour(8, 4, 10, 6)
        contours_data = {
            "dot_contours": [],
            "contours_green": [green_left, green_right],
        }

        cp, _, _, _ = self._run_get_stats(
            mode="green_nucleus",
            selected_analysis=["PunctaDistance"],
            red_gray=red_gray,
            green_gray=green_gray,
            contours_data=contours_data,
            y_range=range(0, 16),
            x_range=range(0, 16),
            puncta_line_mode="green_puncta",
        )

        self.assertEqual(cp.properties["puncta_line_mode"], "green_puncta")
        self.assertEqual(cp.properties["puncta_line_source_channel"], "channel_green")
        self.assertEqual(cp.properties["puncta_line_measurement_channel"], "channel_red")
        self.assertAlmostEqual(cp.puncta_distance, 6.0, places=4)
        self.assertEqual(cp.puncta_line_intensity, 14.0)
