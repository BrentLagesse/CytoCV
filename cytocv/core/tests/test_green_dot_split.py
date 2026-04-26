"""Tests for Green dot contour splitting."""

from __future__ import annotations

import cv2
import numpy as np
from django.test import SimpleTestCase

from core.contour_processing.contour_operations import (
    _split_merged_green_contours,
    _split_params,
    compute_contour_shape_metrics,
    find_convexity_defect_neck_candidates,
    postprocess_gfp_contours_for_neck_splits,
)


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


def _contours_from_mask(mask: np.ndarray) -> list[np.ndarray]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return list(contours)


def _contour_list_count(contours: list[np.ndarray], *, min_area: float = 8.0) -> int:
    return sum(1 for contour in contours if cv2.contourArea(contour) >= min_area)


def _gaussian_pair_image(
    *,
    center_a=(48, 48),
    center_b=(66, 48),
    sigma: float = 4.0,
    bridge_intensity: float = 45.0,
    amplitude_a: float = 220.0,
    amplitude_b: float = 220.0,
    shape=(96, 128),
) -> np.ndarray:
    y_grid, x_grid = np.mgrid[0 : shape[0], 0 : shape[1]]
    dot_a = amplitude_a * np.exp(
        -(
            ((x_grid - center_a[0]) ** 2 + (y_grid - center_a[1]) ** 2)
            / (2.0 * sigma * sigma)
        )
    )
    dot_b = amplitude_b * np.exp(
        -(
            ((x_grid - center_b[0]) ** 2 + (y_grid - center_b[1]) ** 2)
            / (2.0 * sigma * sigma)
        )
    )
    image = np.maximum(dot_a, dot_b)
    cv2.line(image, center_a, center_b, bridge_intensity, 3)
    return np.clip(image, 0, 255).astype(np.uint8)


def _one_sided_notch_mask(shape=(96, 128)) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.circle(mask, (54, 48), 13, 255, -1)
    cv2.circle(mask, (74, 48), 13, 255, -1)
    # Fill the upper waist so only the lower side has a real inward bite.
    cv2.rectangle(mask, (54, 35), (74, 48), 255, -1)
    return mask


def _single_gaussian_image(*, center=(50, 40), sigma: float = 4.5, shape=(80, 100)) -> np.ndarray:
    y_grid, x_grid = np.mgrid[0 : shape[0], 0 : shape[1]]
    image = 220.0 * np.exp(
        -(
            ((x_grid - center[0]) ** 2 + (y_grid - center[1]) ** 2)
            / (2.0 * sigma * sigma)
        )
    )
    return np.clip(image, 0, 255).astype(np.uint8)


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

    def test_aggressive_postprocessor_splits_gaussian_pair_with_dim_bridge(self):
        image = _gaussian_pair_image(bridge_intensity=40.0)
        mask = (image > 32).astype(np.uint8) * 255
        contours = _contours_from_mask(mask)

        split = postprocess_gfp_contours_for_neck_splits(
            contours,
            image,
            {"mode": "aggressive"},
        )

        self.assertEqual(len(contours), 1)
        self.assertEqual(_contour_list_count(split), 2)

    def test_aggressive_postprocessor_splits_binary_peanut_shape(self):
        mask = np.zeros((96, 128), dtype=np.uint8)
        cv2.circle(mask, (54, 48), 13, 255, -1)
        cv2.circle(mask, (74, 48), 13, 255, -1)
        contours = _contours_from_mask(mask)

        split = postprocess_gfp_contours_for_neck_splits(
            contours,
            mask,
            {"mode": "aggressive"},
        )

        self.assertEqual(len(contours), 1)
        self.assertEqual(_contour_list_count(split), 2)

    def test_aggressive_postprocessor_keeps_slightly_irregular_single_dot(self):
        mask = np.zeros((80, 100), dtype=np.uint8)
        cv2.circle(mask, (50, 40), 11, 255, -1)
        cv2.circle(mask, (58, 37), 3, 0, -1)
        cv2.circle(mask, (44, 45), 2, 0, -1)
        contours = _contours_from_mask(mask)

        split = postprocess_gfp_contours_for_neck_splits(
            contours,
            mask,
            {"mode": "aggressive"},
        )

        self.assertEqual(_contour_list_count(split), 1)

    def test_aggressive_postprocessor_splits_close_pair_with_strong_bridge(self):
        image = _gaussian_pair_image(bridge_intensity=90.0)
        mask = (image > 30).astype(np.uint8) * 255
        contours = _contours_from_mask(mask)

        split = postprocess_gfp_contours_for_neck_splits(
            contours,
            image,
            {"mode": "aggressive"},
        )

        self.assertEqual(len(contours), 1)
        self.assertEqual(_contour_list_count(split), 2)

    def test_aggressive_fallback_splits_one_sided_notch_that_has_no_paired_neck(self):
        mask = _one_sided_notch_mask()
        image = _gaussian_pair_image(
            center_a=(54, 48),
            center_b=(74, 48),
            bridge_intensity=42.0,
            shape=mask.shape,
        )
        contours = _contours_from_mask(mask)
        contour = max(contours, key=cv2.contourArea)
        params = _split_params("aggressive")
        metrics = compute_contour_shape_metrics(
            contour,
            mask.shape,
            min_defect_depth_px=params["min_defect_depth_px"],
        )

        self.assertIsNotNone(metrics)
        self.assertEqual(
            find_convexity_defect_neck_candidates(metrics.contour, metrics.mask, params),
            [],
        )

        balanced = postprocess_gfp_contours_for_neck_splits(
            contours,
            image,
            {"mode": "balanced"},
        )
        aggressive = postprocess_gfp_contours_for_neck_splits(
            contours,
            image,
            {"mode": "aggressive"},
        )

        self.assertEqual(_contour_list_count(balanced), 1)
        self.assertEqual(_contour_list_count(aggressive), 2)

    def test_aggressive_fallback_splits_asymmetric_two_gaussian_pair(self):
        image = _gaussian_pair_image(
            center_a=(48, 48),
            center_b=(66, 48),
            bridge_intensity=38.0,
            amplitude_a=230.0,
            amplitude_b=130.0,
        )
        mask = (image > 28).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours = _contours_from_mask(mask)

        split = postprocess_gfp_contours_for_neck_splits(
            contours,
            image,
            {"mode": "aggressive"},
        )

        self.assertEqual(len(contours), 1)
        self.assertEqual(_contour_list_count(split), 2)

    def test_aggressive_fallback_keeps_single_crescent_dot_with_one_peak(self):
        mask = np.zeros((80, 100), dtype=np.uint8)
        cv2.circle(mask, (50, 40), 12, 255, -1)
        cv2.circle(mask, (58, 40), 7, 0, -1)
        contours = _contours_from_mask(mask)
        image = _single_gaussian_image(center=(47, 40), shape=mask.shape)

        split = postprocess_gfp_contours_for_neck_splits(
            contours,
            image,
            {"mode": "aggressive"},
        )

        self.assertEqual(len(contours), 1)
        self.assertEqual(_contour_list_count(split), 1)

    def test_two_bright_spots_inside_broad_convex_background_are_not_split(self):
        shape = (120, 140)
        mask = np.zeros(shape, dtype=np.uint8)
        cv2.ellipse(mask, (70, 60), (38, 24), 0, 0, 360, 255, -1)
        image = np.zeros(shape, dtype=np.float32)
        image[mask > 0] = 28.0
        y_grid, x_grid = np.mgrid[0 : shape[0], 0 : shape[1]]
        image += 120.0 * np.exp(-(((x_grid - 54) ** 2 + (y_grid - 56) ** 2) / 32.0))
        image += 110.0 * np.exp(-(((x_grid - 86) ** 2 + (y_grid - 64) ** 2) / 32.0))
        image = np.clip(image, 0, 255).astype(np.uint8)
        contours = _contours_from_mask(mask)

        split = postprocess_gfp_contours_for_neck_splits(
            contours,
            image,
            {"mode": "aggressive"},
        )

        self.assertEqual(_contour_list_count(split), 1)
