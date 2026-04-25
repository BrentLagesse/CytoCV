"""Tests for Green dot contour splitting."""

from __future__ import annotations

import cv2
import numpy as np
from django.test import SimpleTestCase

from core.contour_processing.contour_operations import _split_merged_green_contours


def _dumbbell(radius_a: int, radius_b: int, center_distance: int, shape=(80, 100)) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cy = shape[0] // 2
    cx = shape[1] // 2
    cv2.circle(mask, (cx - center_distance // 2, cy), radius_a, 255, -1)
    cv2.circle(mask, (cx + center_distance // 2, cy), radius_b, 255, -1)
    return mask


def _contour_count(mask: np.ndarray, *, min_area: float = 8.0) -> int:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return sum(1 for contour in contours if cv2.contourArea(contour) >= min_area)


class GreenDotSplitTests(SimpleTestCase):
    def test_balanced_mode_splits_overlapping_green_dots(self):
        mask = _dumbbell(8, 8, center_distance=10)

        split = _split_merged_green_contours(mask, split_mode="balanced")

        self.assertEqual(_contour_count(split), 2)

    def test_single_round_green_dot_is_not_split(self):
        mask = np.zeros((80, 100), dtype=np.uint8)
        cv2.circle(mask, (50, 40), 10, 255, -1)

        split = _split_merged_green_contours(mask, split_mode="aggressive")

        self.assertEqual(_contour_count(split), 1)

    def test_convex_elongated_blob_is_not_split_despite_multiple_peaks(self):
        mask = np.zeros((80, 100), dtype=np.uint8)
        cv2.ellipse(mask, (50, 40), (16, 6), 0, 0, 360, 255, -1)

        split = _split_merged_green_contours(mask, split_mode="aggressive")

        self.assertEqual(_contour_count(split), 1)

    def test_aggressive_mode_splits_close_unequal_pair_that_balanced_keeps_merged(self):
        mask = _dumbbell(8, 5, center_distance=8)

        balanced = _split_merged_green_contours(mask, split_mode="balanced")
        aggressive = _split_merged_green_contours(mask, split_mode="aggressive")

        self.assertEqual(_contour_count(balanced), 1)
        self.assertEqual(_contour_count(aggressive), 2)
