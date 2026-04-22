from __future__ import annotations

from types import SimpleNamespace

import cv2
import numpy as np
from django.test import SimpleTestCase

from core.cell_analysis.biorientation import Biorientation
from core.image_processing import GrayImage
from core.services.canonical_contours import (
    CANONICAL_BLUE_SLOTS_KEY,
    CANONICAL_GREEN_SLOTS_KEY,
    CANONICAL_RED_SLOTS_KEY,
    CELL_MASK_KEY,
    CanonicalContourSlot,
)


SHAPE = (80, 80)


def _disk_slot(source_index: int, center_xy, radius: int = 2) -> CanonicalContourSlot:
    mask = np.zeros(SHAPE, dtype=np.uint8)
    cv2.circle(
        mask,
        (int(round(center_xy[0])), int(round(center_xy[1]))),
        radius,
        255,
        -1,
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return CanonicalContourSlot(
        source_index=source_index,
        mask=mask,
        contours=tuple(contours),
        area=float(np.count_nonzero(mask)),
        center=(float(center_xy[0]), float(center_xy[1])),
    )


def _images() -> GrayImage:
    red_gray = np.zeros(SHAPE, dtype=np.uint8)
    green_gray = np.zeros(SHAPE, dtype=np.uint8)
    blue_gray = np.zeros(SHAPE, dtype=np.uint8)
    return GrayImage(
        img={
            "gray_red": red_gray,
            "red_no_bg": red_gray,
            "green": green_gray,
            "green_no_bg": green_gray,
            "gray_blue": blue_gray,
            "gray_blue_3": blue_gray,
        }
    )


class BiorientationTests(SimpleTestCase):
    def _run(
        self,
        *,
        red_centers,
        green_centers,
        cell_mask: np.ndarray | None = None,
        min_distance: float = 0.0,
        max_distance: float = 37.0,
        threshold: int = 66,
    ):
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={
                "stats_biorientation_red_min_distance_value": min_distance,
                "stats_biorientation_red_min_distance_unit": "px",
                "stats_biorientation_red_max_distance_value": max_distance,
                "stats_biorientation_red_max_distance_unit": "px",
                "stats_biorientation_collinearity_threshold": threshold,
            },
        )
        images = _images()
        analysis = Biorientation(cp=cp, image=images, output_dir="/tmp")
        contours_data = {
            CELL_MASK_KEY: cell_mask if cell_mask is not None else np.full(SHAPE, 255, dtype=np.uint8),
            CANONICAL_RED_SLOTS_KEY: [
                _disk_slot(index, center) for index, center in enumerate(red_centers)
            ],
            CANONICAL_GREEN_SLOTS_KEY: [
                _disk_slot(index, center) for index, center in enumerate(green_centers)
            ],
            CANONICAL_BLUE_SLOTS_KEY: [],
        }
        rgb = np.zeros((*SHAPE, 3), dtype=np.uint8)
        analysis.calculate_statistics(
            best_contours=[],
            contours_data=contours_data,
            red_image=rgb,
            green_image=rgb,
            puncta_line_width_input=1,
            cen_dot_distance=37,
        )
        return cp

    def test_red_count_not_equal_to_two_reports_zeroes(self):
        cp = self._run(red_centers=[(10, 20)], green_centers=[(15, 20)])

        self.assertEqual(cp.colinear_dots, 0)
        self.assertEqual(cp.off_axis_dots, 0)

    def test_red_distance_outside_range_reports_zeroes(self):
        below = self._run(
            red_centers=[(10, 20), (20, 20)],
            green_centers=[(15, 20)],
            min_distance=20,
            max_distance=40,
        )
        above = self._run(
            red_centers=[(10, 20), (70, 20)],
            green_centers=[(30, 20)],
            min_distance=0,
            max_distance=40,
        )

        self.assertEqual((below.colinear_dots, below.off_axis_dots), (0, 0))
        self.assertEqual((above.colinear_dots, above.off_axis_dots), (0, 0))

    def test_colinear_inside_cell_dots_are_counted(self):
        cp = self._run(
            red_centers=[(10, 20), (30, 20)],
            green_centers=[(15, 20), (25, 20)],
        )

        self.assertEqual(cp.colinear_dots, 2)
        self.assertEqual(cp.off_axis_dots, 0)

    def test_off_axis_inside_cell_dots_are_counted(self):
        cp = self._run(
            red_centers=[(10, 20), (30, 20)],
            green_centers=[(15, 35), (25, 35)],
        )

        self.assertEqual(cp.colinear_dots, 0)
        self.assertEqual(cp.off_axis_dots, 2)

    def test_green_dots_outside_cell_mask_are_excluded(self):
        mask = np.zeros(SHAPE, dtype=np.uint8)
        mask[0:30, 0:40] = 255

        cp = self._run(
            red_centers=[(10, 20), (30, 20)],
            green_centers=[(15, 20), (25, 50)],
            cell_mask=mask,
        )

        self.assertEqual(cp.colinear_dots, 1)
        self.assertEqual(cp.off_axis_dots, 0)

    def test_counts_are_clamped_to_two(self):
        cp = self._run(
            red_centers=[(10, 20), (40, 20)],
            green_centers=[(15, 20), (25, 20), (35, 20)],
            max_distance=40,
        )

        self.assertEqual(cp.colinear_dots, 2)
        self.assertEqual(cp.off_axis_dots, 0)
