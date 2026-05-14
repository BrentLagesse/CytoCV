from __future__ import annotations

import math
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
from django.test import SimpleTestCase

from core.channel_roles import CHANNEL_ROLE_BLUE, CHANNEL_ROLE_GREEN, CHANNEL_ROLE_RED
from core.contour_processing.contour_operations import find_contours
from core.image_processing import GrayImage
from core.services.canonical_contours import (
    build_canonical_contour_payload,
    flatten_slot_contours,
)
from core.services.signal_quantification import (
    SIGNAL_MODE_NUCLEAR_CELL_PAIR,
    SIGNAL_MODE_PUNCTA_DISTANCE,
)
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
    def _dominant_red_pixel_count(image: np.ndarray) -> int:
        return int(np.count_nonzero((image[:, :, 0] > image[:, :, 1]) & (image[:, :, 0] > image[:, :, 2])))

    @staticmethod
    def _dominant_green_pixel_count(image: np.ndarray) -> int:
        return int(np.count_nonzero((image[:, :, 1] > image[:, :, 0]) & (image[:, :, 1] > image[:, :, 2])))

    @staticmethod
    def _colored_outline_pixel_count(
        image: np.ndarray,
        contour: np.ndarray,
        rgb_color: tuple[int, int, int],
    ) -> int:
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, 1)
        color = np.array(rgb_color, dtype=np.uint8)
        return int(np.count_nonzero((mask > 0) & np.all(image == color, axis=2)))

    @staticmethod
    def _write_outline(output_dir: Path, *, image_stem: str = "test", cell_id: int = 1, y_range=range(0), x_range=range(0)) -> None:
        output_path = output_dir / "output"
        output_path.mkdir(parents=True, exist_ok=True)
        outline_path = output_path / f"{image_stem}-{cell_id}.outline"
        ys = list(y_range)
        xs = list(x_range)
        with outline_path.open("w", encoding="utf-8") as handle:
            if not ys or not xs:
                return
            y_min, y_max = ys[0], ys[-1]
            x_min, x_max = xs[0], xs[-1]
            for vy, vx in (
                (y_min, x_min),
                (y_min, x_max),
                (y_max, x_max),
                (y_max, x_min),
            ):
                handle.write(f"{vy},{vx}\n")

    @staticmethod
    def _conf(
        output_dir: str,
        *,
        mode: str,
        analysis: list[str],
        puncta_line_mode: str = "red_puncta",
        signal_quantification_mode: str | None = None,
    ) -> dict:
        conf = {
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
        if signal_quantification_mode is not None:
            conf["signal_quantification_mode"] = signal_quantification_mode
        return conf

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
        green_no_bg_gray: np.ndarray | None = None,
        puncta_line_mode: str = "red_puncta",
        cen_dot_distance: float = 37.0,
        alternate_enabled: bool = False,
        alternate_channel: str | None = None,
        signal_quantification_mode: str | None = None,
        contour_crop_origin=None,
        contour_main_image_shape=None,
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
                "green_no_bg": green_gray if green_no_bg_gray is None else green_no_bg_gray,
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
                        signal_quantification_mode=signal_quantification_mode,
                    ),
                    execution_plan,
                    puncta_line_width=1,
                    cen_dot_distance=cen_dot_distance,
                    alternate_red_detection=alternate_enabled,
                    alternate_detection_channel=alternate_channel,
                    contour_crop_origin=contour_crop_origin,
                    contour_main_image_shape=contour_main_image_shape,
                )

        return cp, np.array(debug_red), np.array(debug_green), np.array(debug_blue)

    def _run_live_get_stats(
        self,
        *,
        mode: str,
        selected_analysis: list[str],
        preprocessed: GrayImage,
        y_range,
        x_range,
        puncta_line_mode: str = "red_puncta",
        alternate_enabled: bool = False,
        alternate_channel: str | None = None,
    ):
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={},
        )
        red_gray = preprocessed.get_image("gray_red")
        green_gray = preprocessed.get_image("green")
        assert red_gray is not None
        assert green_gray is not None
        images = {
            "red": self._rgb(red_gray),
            "green": self._rgb(green_gray),
            "blue": self._rgb(np.zeros_like(red_gray)),
        }
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
                    cen_dot_distance=37.0,
                    alternate_red_detection=alternate_enabled,
                    alternate_detection_channel=alternate_channel,
                )

        return cp, np.array(debug_red), np.array(debug_green), np.array(debug_blue)

    @staticmethod
    def _build_live_alternate_detection_images(shape: tuple[int, int] = (40, 40)) -> GrayImage:
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        raw_red = np.zeros(shape, dtype=np.uint16)
        raw_green = np.zeros(shape, dtype=np.uint16)

        red_gray[10:25, 10:25] = 20
        red_gray[13:19, 13:19] = 255
        green_gray[10:25, 10:25] = 20
        green_gray[13:19, 13:19] = 255
        raw_red[10:25, 10:25] = 90
        raw_green[10:25, 10:25] = 60

        return GrayImage(
            img={
                "red_no_bg": red_gray,
                "gray_red": red_gray,
                "gray_red_3": red_gray,
                "green": green_gray,
                "green_no_bg": green_gray,
                "raw_red": raw_red,
                "raw_green": raw_green,
                "gray_blue": np.zeros(shape, dtype=np.uint8),
                "gray_blue_3": np.zeros(shape, dtype=np.uint8),
            }
        )

    @staticmethod
    def _build_live_puncta_images(shape: tuple[int, int] = (36, 36)) -> GrayImage:
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        raw_red = np.zeros(shape, dtype=np.uint16)
        raw_green = np.zeros(shape, dtype=np.uint16)

        red_gray[8:12, 8:12] = 255
        red_gray[22:26, 22:26] = 255
        green_gray[9:25, 9:25] = 30
        raw_red[8:12, 8:12] = 50
        raw_red[22:26, 22:26] = 60
        raw_green[9:25, 9:25] = 30

        return GrayImage(
            img={
                "red_no_bg": red_gray,
                "gray_red": red_gray,
                "gray_red_3": red_gray,
                "green": green_gray,
                "green_no_bg": green_gray,
                "raw_red": raw_red,
                "raw_green": raw_green,
                "gray_blue": np.zeros(shape, dtype=np.uint8),
                "gray_blue_3": np.zeros(shape, dtype=np.uint8),
            }
        )

    @staticmethod
    def _tightening_support_and_core_images(
        shape: tuple[int, int] = (96, 128),
    ) -> tuple[np.ndarray, np.ndarray]:
        y_grid, x_grid = np.mgrid[0 : shape[0], 0 : shape[1]]

        def pair(*, sigma: float, bridge_intensity: float, amplitude_a: float, amplitude_b: float):
            dot_a = amplitude_a * np.exp(
                -(
                    ((x_grid - 46) ** 2 + (y_grid - 48) ** 2)
                    / (2.0 * sigma * sigma)
                )
            )
            dot_b = amplitude_b * np.exp(
                -(
                    ((x_grid - 66) ** 2 + (y_grid - 48) ** 2)
                    / (2.0 * sigma * sigma)
                )
            )
            image = np.maximum(dot_a, dot_b)
            cv2.line(image, (46, 48), (66, 48), bridge_intensity, 3)
            return np.clip(image, 0, 255).astype(np.uint8)

        support = pair(
            sigma=5.0,
            bridge_intensity=88.0,
            amplitude_a=238.0,
            amplitude_b=224.0,
        )
        tightening = pair(
            sigma=2.7,
            bridge_intensity=8.0,
            amplitude_a=248.0,
            amplitude_b=236.0,
        )
        return support, tightening

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
        self.assertEqual(cp.category_cen_dot, 4)
        self.assertEqual(cp.properties["cen_dot_location"]["status"], "too_many_reds")

    def test_contour_centers_use_same_ranked_slots_and_full_image_bottom_left_origin(self):
        shape = (30, 30)
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        small_red = self._rect_contour(2, 3, 5, 6)
        large_red = self._rect_contour(10, 4, 18, 12)
        small_green = self._rect_contour(3, 20, 6, 23)
        large_green = self._rect_contour(14, 16, 22, 24)
        red_gray[3:13, 2:19] = 10
        green_gray[16:25, 14:23] = 10

        cp, _, _, _ = self._run_get_stats(
            mode="green_nucleus",
            selected_analysis=["GreenRedIntensity"],
            red_gray=red_gray,
            green_gray=green_gray,
            contours_data={
                "dot_contours": [small_red, large_red],
                "contours_green": [small_green, large_green],
            },
            y_range=range(0, shape[0]),
            x_range=range(0, shape[1]),
            contour_crop_origin=(40, 50),
            contour_main_image_shape=(120, 140),
        )

        self.assertGreater(cp.red_contour_1_size, cp.red_contour_2_size)
        self.assertGreater(cp.green_contour_1_size, cp.green_contour_2_size)
        self.assertAlmostEqual(cp.properties["red_contour_1_center_x_px"], 64.0, places=4)
        self.assertAlmostEqual(cp.properties["red_contour_1_center_y_px"], 71.0, places=4)
        self.assertAlmostEqual(cp.properties["green_contour_1_center_x_px"], 68.0, places=4)
        self.assertAlmostEqual(cp.properties["green_contour_1_center_y_px"], 59.0, places=4)
        self.assertEqual(cp.properties["contour_center_origin"], "main_image_bottom_left")
        self.assertEqual(
            cp.properties["contour_center_method"],
            "filled_mask_geometric_centroid",
        )

    def test_blue_contour_center_uses_same_slot_as_blue_size(self):
        shape = (60, 60)
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        blue_contour = self._rect_contour(10, 12, 20, 22)

        cp, _, _, _ = self._run_get_stats(
            mode="green_nucleus",
            selected_analysis=["GreenRedIntensity"],
            red_gray=red_gray,
            green_gray=green_gray,
            contours_data={
                "dot_contours": [],
                "contours_green": [],
                "contours_blue": [blue_contour],
            },
            y_range=range(0, shape[0]),
            x_range=range(0, shape[1]),
            contour_crop_origin=(4, 6),
            contour_main_image_shape=(80, 90),
        )

        self.assertGreater(cp.blue_contour_size, 0.0)
        self.assertAlmostEqual(cp.properties["blue_contour_center_x_px"], 21.0, places=4)
        self.assertAlmostEqual(cp.properties["blue_contour_center_y_px"], 58.0, places=4)

    def test_best_effort_parentage_can_be_identified_when_cen_dot_is_na(self):
        shape = (60, 60)
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        red_left = self._rect_contour(18, 27, 21, 30)
        red_right = self._rect_contour(28, 27, 31, 30)
        green = self._rect_contour(19, 28, 21, 30)
        red_gray[27:31, 18:22] = 10
        red_gray[27:31, 28:32] = 10
        green_gray[28:31, 19:22] = 10

        cp, _, _, _ = self._run_get_stats(
            mode="green_nucleus",
            selected_analysis=["CENDot"],
            red_gray=red_gray,
            green_gray=green_gray,
            contours_data={
                "dot_contours": [red_left, red_right],
                "contours_green": [green],
            },
            y_range=range(5, 55),
            x_range=range(5, 55),
            cen_dot_distance=50.0,
        )

        self.assertEqual(cp.properties["cell_parentage"]["status"], "identified")
        self.assertEqual(cp.properties["cell_parentage"]["mode"], "best_effort")
        self.assertEqual(cp.category_cen_dot, 4)
        self.assertEqual(cp.properties["cen_dot_location"]["status"], "reds_below_threshold")
        self.assertEqual(cp.properties["cen_dot_location"]["cell_parentage_status"], "identified")

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

    def test_live_nuclear_mode_red_nucleus_alternate_detection_uses_alternate_red_source(self):
        preprocessed = self._build_live_alternate_detection_images()
        cp_off, debug_red_off, _, _ = self._run_live_get_stats(
            mode="red_nucleus",
            selected_analysis=["NuclearCellPairIntensity"],
            preprocessed=preprocessed,
            y_range=range(8, 28),
            x_range=range(8, 28),
            alternate_enabled=False,
            alternate_channel=CHANNEL_ROLE_RED,
        )
        cp_on, debug_red_on, _, _ = self._run_live_get_stats(
            mode="red_nucleus",
            selected_analysis=["NuclearCellPairIntensity"],
            preprocessed=preprocessed,
            y_range=range(8, 28),
            x_range=range(8, 28),
            alternate_enabled=True,
            alternate_channel=CHANNEL_ROLE_RED,
        )

        self.assertEqual(cp_on.properties["selected_analysis"], ["NuclearCellPairIntensity"])
        self.assertTrue(cp_on.properties["alternate_nucleus_detection_enabled"])
        self.assertEqual(cp_on.properties["alternate_nucleus_detection_channel"], CHANNEL_ROLE_RED)
        self.assertEqual(cp_off.properties["nuclear_cell_pair_contour_source"], "canonical_slot_1")
        self.assertEqual(
            cp_on.properties["nuclear_cell_pair_contour_source"],
            "alternate_red_nucleus_slot_1",
        )
        self.assertGreater(cp_on.nucleus_intensity_sum, cp_off.nucleus_intensity_sum)
        self.assertGreater(
            self._dominant_red_pixel_count(debug_red_on),
            self._dominant_red_pixel_count(debug_red_off),
        )

    def test_live_nuclear_mode_derives_alternate_channel_from_nucleus_source(self):
        preprocessed = self._build_live_alternate_detection_images()
        cp_on, _, _, _ = self._run_live_get_stats(
            mode="red_nucleus",
            selected_analysis=["NuclearCellPairIntensity"],
            preprocessed=preprocessed,
            y_range=range(8, 28),
            x_range=range(8, 28),
            alternate_enabled=True,
            alternate_channel=None,
        )

        self.assertTrue(cp_on.properties["alternate_nucleus_detection_enabled"])
        self.assertEqual(cp_on.properties["alternate_nucleus_detection_channel"], CHANNEL_ROLE_RED)
        self.assertEqual(
            cp_on.properties["nuclear_cell_pair_contour_source"],
            "alternate_red_nucleus_slot_1",
        )

    def test_live_nuclear_mode_green_nucleus_alternate_detection_uses_alternate_green_source(self):
        preprocessed = self._build_live_alternate_detection_images()
        cp_off, debug_red_off, _, _ = self._run_live_get_stats(
            mode="green_nucleus",
            selected_analysis=["NuclearCellPairIntensity"],
            preprocessed=preprocessed,
            y_range=range(8, 28),
            x_range=range(8, 28),
            alternate_enabled=False,
            alternate_channel=CHANNEL_ROLE_GREEN,
        )
        cp_on, debug_red_on, _, _ = self._run_live_get_stats(
            mode="green_nucleus",
            selected_analysis=["NuclearCellPairIntensity"],
            preprocessed=preprocessed,
            y_range=range(8, 28),
            x_range=range(8, 28),
            alternate_enabled=True,
            alternate_channel=CHANNEL_ROLE_GREEN,
        )

        self.assertEqual(cp_on.properties["selected_analysis"], ["NuclearCellPairIntensity"])
        self.assertTrue(cp_on.properties["alternate_nucleus_detection_enabled"])
        self.assertEqual(cp_on.properties["alternate_nucleus_detection_channel"], CHANNEL_ROLE_GREEN)
        self.assertEqual(cp_off.properties["nuclear_cell_pair_contour_source"], "canonical_slot_1")
        self.assertEqual(
            cp_on.properties["nuclear_cell_pair_contour_source"],
            "alternate_green_nucleus_slot_1",
        )
        self.assertGreater(cp_on.nucleus_intensity_sum, cp_off.nucleus_intensity_sum)
        self.assertGreater(
            self._dominant_green_pixel_count(debug_red_on),
            self._dominant_green_pixel_count(debug_red_off),
        )

    def test_find_contours_skips_standard_red_when_alternate_red_is_requested(self):
        contours_data = find_contours(
            self._build_live_alternate_detection_images(),
            alternate_red_detection=True,
            alternate_detection_channel=CHANNEL_ROLE_RED,
            skip_standard_contour_channels={CHANNEL_ROLE_RED},
        )

        self.assertEqual(contours_data["dot_contours"], [])
        self.assertEqual(contours_data["contours"], [])
        self.assertTrue(contours_data["alternate_nucleus_contours_red"])

    def test_find_contours_skips_standard_green_when_alternate_green_is_requested(self):
        contours_data = find_contours(
            self._build_live_alternate_detection_images(),
            alternate_red_detection=True,
            alternate_detection_channel=CHANNEL_ROLE_GREEN,
            skip_standard_contour_channels={CHANNEL_ROLE_GREEN},
        )

        self.assertEqual(contours_data["contours_green"], [])
        self.assertTrue(contours_data["alternate_nucleus_contours_green"])

    def test_nuclear_only_alternate_red_requests_standard_red_skip(self):
        shape = (32, 32)
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        cp = SimpleNamespace(image_name="test.dv", cell_id=1, properties={})
        images = {
            "red": self._rgb(red_gray),
            "green": self._rgb(green_gray),
            "blue": self._rgb(np.zeros_like(red_gray)),
        }
        preprocessed = GrayImage(
            img={
                "red_no_bg": red_gray,
                "gray_red": red_gray,
                "gray_red_3": red_gray,
                "green": green_gray,
                "green_no_bg": green_gray,
                "raw_green": green_gray,
                "gray_blue": np.zeros_like(red_gray),
                "gray_blue_3": np.zeros_like(red_gray),
            }
        )
        alternate_contour = self._rect_contour(8, 8, 24, 24)

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_outline(output_dir, y_range=range(0, shape[0]), x_range=range(0, shape[1]))
            with patch("core.views.segment_image.load_image", return_value=images), patch(
                "core.views.segment_image.preprocess_image_to_gray",
                return_value=preprocessed,
            ), patch(
                "core.views.segment_image.find_contours",
                return_value={
                    "dot_contours": [],
                    "contours_green": [],
                    "alternate_nucleus_contours_red": [alternate_contour],
                },
            ) as find_mock:
                get_stats(
                    cp,
                    self._conf(
                        temp_dir,
                        mode="red_nucleus",
                        analysis=["NuclearCellPairIntensity"],
                        signal_quantification_mode=SIGNAL_MODE_NUCLEAR_CELL_PAIR,
                    ),
                    build_stats_execution_plan(["NuclearCellPairIntensity"]),
                    puncta_line_width=1,
                    cen_dot_distance=37.0,
                    alternate_red_detection=True,
                    alternate_detection_channel=CHANNEL_ROLE_RED,
                )

        self.assertEqual(
            set(find_mock.call_args.kwargs["skip_standard_contour_channels"]),
            {CHANNEL_ROLE_RED},
        )

    def test_nuclear_only_alternate_green_requests_standard_green_skip(self):
        shape = (32, 32)
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        cp = SimpleNamespace(image_name="test.dv", cell_id=1, properties={})
        images = {
            "red": self._rgb(red_gray),
            "green": self._rgb(green_gray),
            "blue": self._rgb(np.zeros_like(red_gray)),
        }
        preprocessed = GrayImage(
            img={
                "red_no_bg": red_gray,
                "gray_red": red_gray,
                "gray_red_3": red_gray,
                "green": green_gray,
                "green_no_bg": green_gray,
                "raw_red": red_gray,
                "gray_blue": np.zeros_like(red_gray),
                "gray_blue_3": np.zeros_like(red_gray),
            }
        )
        alternate_contour = self._rect_contour(8, 8, 24, 24)

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_outline(
                output_dir,
                y_range=range(0, shape[0]),
                x_range=range(0, shape[1]),
            )
            with patch("core.views.segment_image.load_image", return_value=images), patch(
                "core.views.segment_image.preprocess_image_to_gray",
                return_value=preprocessed,
            ), patch(
                "core.views.segment_image.find_contours",
                return_value={
                    "dot_contours": [],
                    "contours_green": [],
                    "alternate_nucleus_contours_green": [alternate_contour],
                },
            ) as find_mock:
                get_stats(
                    cp,
                    self._conf(
                        temp_dir,
                        mode="green_nucleus",
                        analysis=["NuclearCellPairIntensity"],
                        signal_quantification_mode=SIGNAL_MODE_NUCLEAR_CELL_PAIR,
                    ),
                    build_stats_execution_plan(["NuclearCellPairIntensity"]),
                    puncta_line_width=1,
                    cen_dot_distance=37.0,
                    alternate_red_detection=True,
                    alternate_detection_channel=CHANNEL_ROLE_GREEN,
                )

        self.assertEqual(
            set(find_mock.call_args.kwargs["skip_standard_contour_channels"]),
            {CHANNEL_ROLE_GREEN},
        )

    def test_nuclear_with_cen_dot_keeps_standard_contours_for_independent_stats(self):
        shape = (32, 32)
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        cp = SimpleNamespace(image_name="test.dv", cell_id=1, properties={})
        images = {
            "red": self._rgb(red_gray),
            "green": self._rgb(green_gray),
            "blue": self._rgb(np.zeros_like(red_gray)),
        }
        preprocessed = GrayImage(
            img={
                "red_no_bg": red_gray,
                "gray_red": red_gray,
                "gray_red_3": red_gray,
                "green": green_gray,
                "green_no_bg": green_gray,
                "raw_green": green_gray,
                "gray_blue": np.zeros_like(red_gray),
                "gray_blue_3": np.zeros_like(red_gray),
            }
        )
        standard_contour = self._rect_contour(13, 13, 17, 17)
        alternate_contour = self._rect_contour(8, 8, 24, 24)

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_outline(output_dir, y_range=range(0, shape[0]), x_range=range(0, shape[1]))
            with patch("core.views.segment_image.load_image", return_value=images), patch(
                "core.views.segment_image.preprocess_image_to_gray",
                return_value=preprocessed,
            ), patch(
                "core.views.segment_image.find_contours",
                return_value={
                    "dot_contours": [standard_contour],
                    "contours_green": [],
                    "alternate_nucleus_contours_red": [alternate_contour],
                },
            ) as find_mock:
                get_stats(
                    cp,
                    self._conf(
                        temp_dir,
                        mode="red_nucleus",
                        analysis=["NuclearCellPairIntensity", "CENDot"],
                        signal_quantification_mode=SIGNAL_MODE_NUCLEAR_CELL_PAIR,
                    ),
                    build_stats_execution_plan(["NuclearCellPairIntensity", "CENDot"]),
                    puncta_line_width=1,
                    cen_dot_distance=37.0,
                    alternate_red_detection=True,
                    alternate_detection_channel=CHANNEL_ROLE_RED,
                )

        self.assertEqual(
            cp.properties["nuclear_cell_pair_contour_source"],
            "alternate_red_nucleus_slot_1",
        )
        self.assertEqual(cp.properties["selected_analysis"], ["CENDot", "NuclearCellPairIntensity"])
        self.assertEqual(
            set(find_mock.call_args.kwargs["skip_standard_contour_channels"]),
            set(),
        )

    def test_nuclear_red_alternate_suppresses_standard_red_overlay(self):
        shape = (32, 32)
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        standard_contour = self._rect_contour(13, 13, 17, 17)
        alternate_contour = self._rect_contour(8, 8, 24, 24)

        cp, debug_red, _, _ = self._run_get_stats(
            mode="red_nucleus",
            selected_analysis=["NuclearCellPairIntensity"],
            red_gray=red_gray,
            green_gray=green_gray,
            contours_data={
                "dot_contours": [standard_contour],
                "contours_green": [],
                "alternate_nucleus_contours_red": [alternate_contour],
            },
            y_range=range(0, shape[0]),
            x_range=range(0, shape[1]),
            alternate_enabled=True,
            alternate_channel=CHANNEL_ROLE_RED,
            signal_quantification_mode=SIGNAL_MODE_NUCLEAR_CELL_PAIR,
        )

        self.assertEqual(
            cp.properties["nuclear_cell_pair_contour_source"],
            "alternate_red_nucleus_slot_1",
        )
        self.assertGreater(
            self._colored_outline_pixel_count(debug_red, alternate_contour, (255, 0, 0)),
            0,
        )
        self.assertEqual(
            self._colored_outline_pixel_count(debug_red, standard_contour, (255, 0, 0)),
            0,
        )

    def test_nuclear_green_alternate_suppresses_standard_green_overlay(self):
        shape = (32, 32)
        red_gray = np.zeros(shape, dtype=np.uint8)
        green_gray = np.zeros(shape, dtype=np.uint8)
        standard_contour = self._rect_contour(13, 13, 17, 17)
        alternate_contour = self._rect_contour(8, 8, 24, 24)

        cp, debug_red, _, _ = self._run_get_stats(
            mode="green_nucleus",
            selected_analysis=["NuclearCellPairIntensity"],
            red_gray=red_gray,
            green_gray=green_gray,
            contours_data={
                "dot_contours": [],
                "contours_green": [standard_contour],
                "alternate_nucleus_contours_green": [alternate_contour],
            },
            y_range=range(0, shape[0]),
            x_range=range(0, shape[1]),
            alternate_enabled=True,
            alternate_channel=CHANNEL_ROLE_GREEN,
            signal_quantification_mode=SIGNAL_MODE_NUCLEAR_CELL_PAIR,
        )

        self.assertEqual(
            cp.properties["nuclear_cell_pair_contour_source"],
            "alternate_green_nucleus_slot_1",
        )
        self.assertGreater(
            self._colored_outline_pixel_count(debug_red, alternate_contour, (0, 255, 0)),
            0,
        )
        self.assertEqual(
            self._colored_outline_pixel_count(debug_red, standard_contour, (0, 255, 0)),
            0,
        )

    def test_live_puncta_mode_is_unchanged_by_alternate_nucleus_detection_and_gates_red_green_intensity(self):
        preprocessed = self._build_live_puncta_images()
        cp_off, _, _, _ = self._run_live_get_stats(
            mode="red_nucleus",
            selected_analysis=["PunctaDistance"],
            preprocessed=preprocessed,
            y_range=range(0, 36),
            x_range=range(0, 36),
            alternate_enabled=False,
            alternate_channel=CHANNEL_ROLE_RED,
        )
        cp_on, _, _, _ = self._run_live_get_stats(
            mode="red_nucleus",
            selected_analysis=["PunctaDistance"],
            preprocessed=preprocessed,
            y_range=range(0, 36),
            x_range=range(0, 36),
            alternate_enabled=True,
            alternate_channel=CHANNEL_ROLE_RED,
        )
        cp_with_intensity, _, _, _ = self._run_live_get_stats(
            mode="red_nucleus",
            selected_analysis=["PunctaDistance", "GreenRedIntensity"],
            preprocessed=preprocessed,
            y_range=range(0, 36),
            x_range=range(0, 36),
            alternate_enabled=True,
            alternate_channel=CHANNEL_ROLE_RED,
        )

        self.assertAlmostEqual(cp_off.puncta_distance, cp_on.puncta_distance, places=4)
        self.assertAlmostEqual(cp_off.puncta_line_intensity, cp_on.puncta_line_intensity, places=4)
        self.assertNotIn("nuclear_cell_pair_contour_source", cp_on.properties)
        self.assertEqual(getattr(cp_on, "red_intensity_1", 0.0), 0.0)
        self.assertEqual(getattr(cp_on, "green_intensity_1", 0.0), 0.0)
        self.assertGreater(getattr(cp_with_intensity, "red_intensity_1", 0.0), 0.0)
        self.assertGreater(getattr(cp_with_intensity, "green_intensity_1", 0.0), 0.0)

    def test_live_puncta_mode_with_alternate_enabled_does_not_use_legacy_alternate_red_detection(self):
        preprocessed = self._build_live_puncta_images()

        with patch(
            "core.contour_processing.contour_operations._alternate_channel_contour_family",
            side_effect=AssertionError("alternate contour family should stay nuclear-only"),
        ):
            cp, _, _, _ = self._run_live_get_stats(
                mode="red_nucleus",
                selected_analysis=["PunctaDistance"],
                preprocessed=preprocessed,
                y_range=range(0, 36),
                x_range=range(0, 36),
                alternate_enabled=True,
                alternate_channel=None,
            )

        self.assertFalse(cp.properties["alternate_nucleus_detection_enabled"])
        self.assertIsNone(cp.properties["alternate_nucleus_detection_channel"])
        self.assertGreater(cp.puncta_distance, 0.0)
        self.assertEqual(cp.properties["signal_quantification_mode"], SIGNAL_MODE_PUNCTA_DISTANCE)

    def test_aggressive_tightened_green_slots_drive_stats_and_debug_contours(self):
        shape = (96, 128)
        red_gray = np.zeros(shape, dtype=np.uint8)
        support_green, tightening_green = self._tightening_support_and_core_images(shape)
        preprocessed = GrayImage(
            img={
                "red_no_bg": red_gray,
                "gray_red": red_gray,
                "gray_red_3": red_gray,
                "green": support_green,
                "green_no_bg": tightening_green,
                "gray_blue": np.zeros_like(red_gray),
                "gray_blue_3": np.zeros_like(red_gray),
            }
        )
        contours_data = find_contours(
            preprocessed,
            green_contour_filter_enabled=False,
            alternate_red_detection=False,
            green_dot_split_enabled=True,
            green_dot_split_mode="aggressive",
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_outline(
                output_dir,
                y_range=range(0, shape[0]),
                x_range=range(0, shape[1]),
            )
            expected_payload = build_canonical_contour_payload(
                contours_data,
                image_name="test.dv",
                cell_id=1,
                output_dir=temp_dir,
                shape=shape,
            )
            expected_slots = expected_payload["canonical_green_slots"]
            expected_contours = flatten_slot_contours(expected_slots)

            cp, _, debug_green, _ = self._run_get_stats(
                mode="green_nucleus",
                selected_analysis=["GreenRedIntensity"],
                red_gray=red_gray,
                green_gray=support_green,
                green_no_bg_gray=tightening_green,
                contours_data=contours_data,
                y_range=range(0, shape[0]),
                x_range=range(0, shape[1]),
            )

        self.assertEqual(len(expected_slots), 2)
        self.assertAlmostEqual(cp.green_contour_1_size, float(expected_slots[0].area), places=4)
        self.assertAlmostEqual(cp.green_contour_2_size, float(expected_slots[1].area), places=4)

        expected_debug_green = self._rgb(support_green)
        cv2.drawContours(expected_debug_green, expected_contours, -1, (0, 255, 0), 1)
        self.assertTrue(np.array_equal(debug_green, expected_debug_green))

    def test_get_stats_sums_raw_measurement_images_not_normalized_display_crops(self):
        shape = (12, 12)
        display_red = np.zeros(shape, dtype=np.uint8)
        display_green = np.zeros(shape, dtype=np.uint8)
        display_red[3:8, 3:8] = 255
        display_green[3:8, 3:8] = 255
        raw_red = np.zeros(shape, dtype=np.uint16)
        raw_green = np.zeros(shape, dtype=np.uint16)
        raw_red[3:8, 3:8] = 4000
        raw_green[3:8, 3:8] = 1000

        contour = self._rect_contour(3, 3, 7, 7)
        contours_data = {"dot_contours": [contour], "contours_green": [contour]}
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={"nuclear_cell_pair_mode": "red_nucleus"},
        )
        images = {
            "red": self._rgb(display_red),
            "green": self._rgb(display_green),
            "blue": self._rgb(np.zeros(shape, dtype=np.uint8)),
        }
        measurement_images = {
            CHANNEL_ROLE_RED: raw_red,
            CHANNEL_ROLE_GREEN: raw_green,
            CHANNEL_ROLE_BLUE: np.zeros(shape, dtype=np.uint16),
        }
        execution_plan = build_stats_execution_plan(["GreenRedIntensity"])

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_outline(
                output_dir,
                y_range=range(0, shape[0]),
                x_range=range(0, shape[1]),
            )
            with patch("core.views.segment_image.load_image", return_value=images), patch(
                "core.views.segment_image.find_contours",
                return_value=contours_data,
            ):
                get_stats(
                    cp,
                    self._conf(
                        temp_dir,
                        mode="red_nucleus",
                        analysis=["GreenRedIntensity"],
                    ),
                    execution_plan,
                    puncta_line_width=1,
                    cen_dot_distance=37,
                    cached_measurement_images=measurement_images,
                )

        mask = np.zeros(shape, np.uint8)
        cv2.drawContours(mask, [contour], 0, 255, -1)
        self.assertEqual(cp.red_intensity_1, float(np.sum(raw_red[mask > 0])))
        self.assertEqual(cp.green_intensity_1, float(np.sum(raw_green[mask > 0])))
        self.assertEqual(cp.green_red_intensity_1, 0.25)
        self.assertEqual(cp.properties["intensity_pixel_source"], "raw_dv_v1")
        self.assertFalse(cp.properties["intensity_display_scaled"])
        self.assertFalse(cp.properties["intensity_background_subtracted"])
