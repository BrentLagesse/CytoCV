"""Tests for Green dot contour splitting."""

from __future__ import annotations

import cv2
import numpy as np
from django.test import SimpleTestCase
from unittest.mock import patch

from core.contour_processing.contour_operations import (
    _best_peak_pair,
    _choose_split_peak_pair,
    _find_distance_peaks_in_contour,
    _filter_green_contours_with_image,
    _markers_from_neck,
    _split_merged_green_contours,
    _split_params,
    _split_contour_with_neck_chord,
    compute_contour_shape_metrics,
    find_contours,
    find_convexity_defect_neck_candidates,
    find_intensity_peaks_in_contour,
    postprocess_gfp_contours_for_neck_splits,
    split_contour_with_geometry_first_watershed,
    split_contour_with_watershed,
    validate_geometry_first_split,
    validate_split_contours,
)
from core.image_processing import GrayImage


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
    cv2.ellipse(mask, (64, 48), (26, 10), 0, 0, 360, 255, -1)
    cv2.circle(mask, (63, 38), 1, 0, -1)
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


def _geometry_first_neck_mask(shape=(96, 128)) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.circle(mask, (55, 48), 11, 255, -1)
    cv2.circle(mask, (72, 48), 8, 255, -1)
    cv2.rectangle(mask, (55, 43), (72, 51), 255, -1)
    cv2.circle(mask, (63, 56), 3, 0, -1)
    return mask


def _geometry_first_single_peak_image(mask: np.ndarray) -> np.ndarray:
    y_grid, x_grid = np.mgrid[0 : mask.shape[0], 0 : mask.shape[1]]
    image = 220.0 * np.exp(
        -(
            ((x_grid - 54) ** 2 + (y_grid - 48) ** 2)
            / (2.0 * 3.2 * 3.2)
        )
    )
    image += 18.0 * (mask > 0)
    return np.clip(image, 0, 255).astype(np.uint8)


def _wide_neck_guard_mask(shape=(96, 128)) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.ellipse(mask, (60, 48), (24, 8), 0, 0, 360, 255, -1)
    cv2.circle(mask, (54, 36), 4, 0, -1)
    return mask


def _wide_neck_guard_single_peak_image(mask: np.ndarray) -> np.ndarray:
    y_grid, x_grid = np.mgrid[0 : mask.shape[0], 0 : mask.shape[1]]
    image = 235.0 * np.exp(
        -(
            ((x_grid - 48) ** 2 + (y_grid - 48) ** 2)
            / (2.0 * 3.4 * 3.4)
        )
    )
    image += 22.0 * (mask > 0)
    return np.clip(image, 0, 255).astype(np.uint8)


def _moderate_aspect_two_peak_neck_mask() -> np.ndarray:
    return np.array(
        [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 255, 255, 255, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 255, 255, 255, 255, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255, 255, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 255, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ],
        dtype=np.uint8,
    )


def _moderate_aspect_two_peak_neck_image() -> np.ndarray:
    return np.array(
        [
            [9, 10, 10, 10, 10, 10, 10, 10, 11, 12, 13, 12, 12, 11, 11, 11, 11, 11, 10, 10],
            [10, 10, 10, 10, 10, 9, 9, 10, 11, 12, 13, 13, 12, 11, 11, 11, 11, 11, 10, 10],
            [10, 10, 9, 10, 10, 10, 10, 11, 12, 13, 13, 13, 13, 13, 12, 12, 12, 12, 11, 11],
            [10, 10, 10, 10, 11, 12, 13, 14, 14, 14, 14, 14, 15, 14, 14, 13, 13, 12, 12, 12],
            [10, 10, 10, 11, 15, 22, 26, 23, 19, 17, 16, 15, 15, 15, 14, 14, 13, 12, 11, 11],
            [10, 11, 12, 14, 22, 36, 46, 42, 30, 21, 18, 16, 16, 15, 15, 14, 13, 11, 11, 11],
            [12, 13, 14, 16, 24, 40, 55, 56, 42, 27, 20, 20, 20, 19, 17, 15, 14, 12, 11, 11],
            [13, 14, 15, 17, 22, 32, 46, 53, 45, 31, 25, 30, 38, 39, 29, 20, 16, 13, 11, 11],
            [13, 14, 14, 16, 18, 23, 30, 38, 37, 32, 31, 44, 66, 71, 50, 27, 17, 12, 11, 11],
            [12, 13, 13, 14, 15, 18, 22, 27, 30, 31, 35, 50, 78, 88, 65, 33, 17, 12, 11, 10],
            [10, 11, 12, 12, 13, 16, 20, 23, 27, 29, 32, 42, 61, 72, 58, 33, 17, 12, 12, 11],
            [10, 11, 12, 12, 14, 16, 18, 20, 22, 25, 26, 29, 36, 41, 37, 25, 16, 13, 12, 12],
            [11, 12, 12, 13, 15, 17, 18, 18, 19, 20, 20, 21, 22, 22, 20, 17, 13, 12, 12, 11],
            [12, 13, 14, 15, 16, 17, 18, 17, 17, 17, 17, 16, 16, 15, 14, 13, 12, 12, 11, 10],
            [12, 13, 15, 16, 16, 16, 16, 17, 16, 16, 15, 14, 13, 13, 13, 12, 11, 11, 10, 9],
            [11, 13, 14, 15, 15, 15, 15, 16, 15, 14, 14, 13, 13, 13, 13, 11, 10, 10, 10, 9],
            [11, 12, 12, 13, 13, 14, 15, 14, 14, 13, 13, 13, 13, 13, 12, 10, 9, 9, 9, 9],
        ],
        dtype=np.uint8,
    )


def _tip_connected_pair_image(shape=(72, 96)) -> np.ndarray:
    image = np.zeros(shape, dtype=np.float32)
    cv2.circle(image, (46, 40), 7, 230.0, -1)
    cv2.circle(image, (56, 35), 4, 130.0, -1)
    cv2.line(image, (50, 38), (53, 36), 70.0, 1)
    image = cv2.GaussianBlur(image, (0, 0), 1.0)
    return np.clip(image, 0, 255).astype(np.uint8)


def _add_gaussian(
    image: np.ndarray,
    *,
    center: tuple[int, int],
    amplitude: float,
    sigma: float,
) -> np.ndarray:
    y_grid, x_grid = np.mgrid[0 : image.shape[0], 0 : image.shape[1]]
    blob = amplitude * np.exp(
        -(
            ((x_grid - center[0]) ** 2 + (y_grid - center[1]) ** 2)
            / (2.0 * sigma * sigma)
        )
    )
    return image + blob


def _real_failure_like_green_image(shape=(80, 96)) -> np.ndarray:
    image = np.zeros(shape, dtype=np.float32)
    image = _add_gaussian(image, center=(46, 38), amplitude=248.0, sigma=2.6)
    image = _add_gaussian(image, center=(57, 37), amplitude=255.0, sigma=2.4)
    image = _add_gaussian(image, center=(61, 49), amplitude=80.0, sigma=4.0)
    image = _add_gaussian(image, center=(30, 41), amplitude=35.0, sigma=7.5)
    cv2.line(image, (47, 38), (56, 37), 52.0, 3)
    image = cv2.GaussianBlur(image, (0, 0), 0.9)
    return np.clip(image, 0, 255).astype(np.uint8)


def _contour_centroid(contour: np.ndarray) -> tuple[float, float]:
    moments = cv2.moments(contour)
    if moments["m00"] == 0:
        x, y, width, height = cv2.boundingRect(contour)
        return x + width / 2.0, y + height / 2.0
    return moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]


def _green_only_images(image: np.ndarray) -> GrayImage:
    return GrayImage(
        {
            "gray_red_3": None,
            "gray_red": None,
            "gray_blue_3": None,
            "gray_blue": None,
            "green": image,
            "green_no_bg": None,
            "red_no_bg": None,
        }
    )


def _green_pre_postprocess_contours_from_image(image: np.ndarray) -> list[np.ndarray]:
    low_val, _ = cv2.threshold(
        image,
        0.65,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )
    _, thresh_green = cv2.threshold(
        image,
        low_val + 13,
        255,
        cv2.THRESH_BINARY,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    thresh_green = cv2.morphologyEx(thresh_green, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(
        thresh_green,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    return list(contours)


def _split_green_contours_from_image(
    image: np.ndarray,
    split_mode: str,
    *,
    green_contour_filter_enabled: bool = False,
) -> list[np.ndarray]:
    contours_data = find_contours(
        _green_only_images(image),
        green_contour_filter_enabled=green_contour_filter_enabled,
        alternate_red_detection=False,
        green_dot_split_enabled=True,
        green_dot_split_mode=split_mode,
    )
    return list(contours_data.get("contours_green", []))


class GreenDotSplitTests(SimpleTestCase):
    def test_balanced_mode_splits_overlapping_green_dots(self):
        mask = _dumbbell(8, 8, center_distance=10)

        split = _split_merged_green_contours(mask, split_mode="balanced")

        self.assertEqual(_contour_count(split), 2)

    def test_single_round_green_dot_is_not_split(self):
        mask = np.zeros((80, 100), dtype=np.uint8)
        cv2.circle(mask, (50, 40), 10, 255, -1)

        for split_mode in ("balanced", "aggressive"):
            split = _split_merged_green_contours(mask, split_mode=split_mode)
            self.assertEqual(_contour_count(split), 1)

    def test_convex_elongated_blob_is_not_split_despite_multiple_peaks(self):
        mask = np.zeros((80, 100), dtype=np.uint8)
        cv2.ellipse(mask, (50, 40), (16, 6), 0, 0, 360, 255, -1)

        for split_mode in ("balanced", "aggressive"):
            split = _split_merged_green_contours(mask, split_mode=split_mode)
            self.assertEqual(_contour_count(split), 1)

    def test_balanced_and_aggressive_split_close_unequal_pair(self):
        mask = _dumbbell(8, 5, center_distance=8)

        balanced = _split_merged_green_contours(mask, split_mode="balanced")
        aggressive = _split_merged_green_contours(mask, split_mode="aggressive")

        self.assertEqual(_contour_count(balanced), 2)
        self.assertEqual(_contour_count(aggressive), 2)

    def test_balanced_and_aggressive_postprocessor_split_gaussian_pair_with_dim_bridge(self):
        image = _gaussian_pair_image(bridge_intensity=40.0)
        mask = (image > 32).astype(np.uint8) * 255
        contours = _contours_from_mask(mask)

        self.assertEqual(len(contours), 1)
        for split_mode in ("balanced", "aggressive"):
            split = postprocess_gfp_contours_for_neck_splits(
                contours,
                image,
                {"mode": split_mode},
            )
            self.assertEqual(_contour_list_count(split), 2)

    def test_balanced_and_aggressive_postprocessor_split_binary_peanut_shape(self):
        mask = np.zeros((96, 128), dtype=np.uint8)
        cv2.circle(mask, (54, 48), 13, 255, -1)
        cv2.circle(mask, (74, 48), 13, 255, -1)
        contours = _contours_from_mask(mask)

        self.assertEqual(len(contours), 1)
        for split_mode in ("balanced", "aggressive"):
            split = postprocess_gfp_contours_for_neck_splits(
                contours,
                mask,
                {"mode": split_mode},
            )
            self.assertEqual(_contour_list_count(split), 2)

    def test_postprocessor_keeps_slightly_irregular_single_dot(self):
        mask = np.zeros((80, 100), dtype=np.uint8)
        cv2.circle(mask, (50, 40), 11, 255, -1)
        cv2.circle(mask, (58, 37), 3, 0, -1)
        cv2.circle(mask, (44, 45), 2, 0, -1)
        contours = _contours_from_mask(mask)

        for split_mode in ("balanced", "aggressive"):
            split = postprocess_gfp_contours_for_neck_splits(
                contours,
                mask,
                {"mode": split_mode},
            )
            self.assertEqual(_contour_list_count(split), 1)

    def test_balanced_and_aggressive_postprocessor_split_close_pair_with_strong_bridge(self):
        image = _gaussian_pair_image(bridge_intensity=90.0)
        mask = (image > 30).astype(np.uint8) * 255
        contours = _contours_from_mask(mask)

        self.assertEqual(len(contours), 1)
        for split_mode in ("balanced", "aggressive"):
            split = postprocess_gfp_contours_for_neck_splits(
                contours,
                image,
                {"mode": split_mode},
            )
            self.assertEqual(_contour_list_count(split), 2)

    def test_geometry_first_aggressive_splits_necked_single_peak_shape_that_balanced_keeps_merged(self):
        mask = _geometry_first_neck_mask()
        image = _geometry_first_single_peak_image(mask)
        contours = _contours_from_mask(mask)

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

    def test_wide_neck_single_peak_shape_splits_in_aggressive_but_balanced_keeps_merged(self):
        mask = _wide_neck_guard_mask()
        image = _wide_neck_guard_single_peak_image(mask)
        contours = _contours_from_mask(mask)

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

    def test_moderate_aspect_two_peak_necked_contour_splits_in_aggressive_but_balanced_keeps_merged(self):
        mask = _moderate_aspect_two_peak_neck_mask()
        image = _moderate_aspect_two_peak_neck_image()
        contours = _contours_from_mask(mask)

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

    def test_balanced_and_aggressive_fallback_split_asymmetric_two_gaussian_pair(self):
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

        self.assertEqual(len(contours), 1)
        for split_mode in ("balanced", "aggressive"):
            split = postprocess_gfp_contours_for_neck_splits(
                contours,
                image,
                {"mode": split_mode},
            )
            self.assertEqual(_contour_list_count(split), 2)

    def test_fallback_keeps_single_crescent_dot_with_one_peak(self):
        mask = np.zeros((80, 100), dtype=np.uint8)
        cv2.circle(mask, (50, 40), 12, 255, -1)
        cv2.circle(mask, (58, 40), 7, 0, -1)
        contours = _contours_from_mask(mask)
        image = _single_gaussian_image(center=(47, 40), shape=mask.shape)

        self.assertEqual(len(contours), 1)
        for split_mode in ("balanced", "aggressive"):
            split = postprocess_gfp_contours_for_neck_splits(
                contours,
                image,
                {"mode": split_mode},
            )
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

        for split_mode in ("balanced", "aggressive"):
            split = postprocess_gfp_contours_for_neck_splits(
                contours,
                image,
                {"mode": split_mode},
            )
            self.assertEqual(_contour_list_count(split), 1)

    def test_geometry_first_fixture_neck_markers_and_chord_fail_but_aggressive_still_splits(self):
        mask = _geometry_first_neck_mask()
        image = _geometry_first_single_peak_image(mask)
        contours = _contours_from_mask(mask)
        contour = max(contours, key=cv2.contourArea)
        params = _split_params("aggressive")
        metrics = compute_contour_shape_metrics(
            contour,
            mask.shape,
            min_defect_depth_px=params["min_defect_depth_px"],
        )

        self.assertIsNotNone(metrics)
        neck_candidates = find_convexity_defect_neck_candidates(
            metrics.contour,
            metrics.mask,
            params,
        )
        self.assertTrue(neck_candidates)
        self.assertEqual(len(find_intensity_peaks_in_contour(metrics.mask, image, params)), 1)
        self.assertIsNone(_markers_from_neck(metrics.mask, neck_candidates[0], params))
        self.assertIsNone(_split_contour_with_neck_chord(metrics.mask, neck_candidates[0], params))
        split = postprocess_gfp_contours_for_neck_splits(
            contours,
            image,
            {"mode": "aggressive"},
        )

        self.assertEqual(_contour_list_count(split), 2)

    def test_wide_neck_single_peak_fixture_would_have_hit_old_aggressive_guards_but_now_splits(self):
        mask = _wide_neck_guard_mask()
        image = _wide_neck_guard_single_peak_image(mask)
        contours = _contours_from_mask(mask)
        contour = max(contours, key=cv2.contourArea)
        params = _split_params("aggressive")
        metrics = compute_contour_shape_metrics(
            contour,
            mask.shape,
            min_defect_depth_px=params["min_defect_depth_px"],
        )

        self.assertIsNotNone(metrics)
        neck_candidates = find_convexity_defect_neck_candidates(
            metrics.contour,
            metrics.mask,
            params,
        )
        self.assertTrue(neck_candidates)
        best_neck = neck_candidates[0]

        intensity_peaks = find_intensity_peaks_in_contour(metrics.mask, image, params)
        distance_peaks, distance_image = _find_distance_peaks_in_contour(
            metrics.mask,
            params,
        )
        intensity_pair = _best_peak_pair(
            intensity_peaks,
            image.astype(np.float32),
            params,
            max_valley_ratio_key="max_intensity_valley_ratio",
        )
        distance_pair = _best_peak_pair(
            distance_peaks,
            distance_image,
            params,
            max_valley_ratio_key="max_distance_valley_ratio",
        )

        self.assertGreaterEqual(metrics.aspect_ratio, 2.0)
        self.assertGreaterEqual(metrics.solidity, 0.94)
        self.assertGreaterEqual(metrics.max_defect_depth_px, 1.0)
        self.assertGreater(best_neck.neck_ratio, 0.60)
        self.assertLessEqual(best_neck.neck_ratio, 0.80)
        self.assertIsNone(
            _choose_split_peak_pair(intensity_pair, distance_pair, params)
        )

        aggressive = postprocess_gfp_contours_for_neck_splits(
            contours,
            image,
            {"mode": "aggressive"},
        )
        self.assertEqual(_contour_list_count(aggressive), 2)

    def test_moderate_aspect_two_peak_neck_fixture_reaches_geometry_split_after_peak_split_fails(self):
        mask = _moderate_aspect_two_peak_neck_mask()
        image = _moderate_aspect_two_peak_neck_image()
        contour = max(_contours_from_mask(mask), key=cv2.contourArea)
        params = _split_params("aggressive")
        metrics = compute_contour_shape_metrics(
            contour,
            mask.shape,
            min_defect_depth_px=params["min_defect_depth_px"],
        )

        self.assertIsNotNone(metrics)
        self.assertGreater(metrics.aspect_ratio, float(params["max_single_dot_aspect_ratio"]))
        self.assertLess(metrics.aspect_ratio, 1.35)
        self.assertGreaterEqual(metrics.deep_defect_count, 2)
        self.assertGreaterEqual(metrics.max_defect_depth_px, 1.0)

        neck_candidates = find_convexity_defect_neck_candidates(
            metrics.contour,
            metrics.mask,
            params,
        )
        self.assertTrue(neck_candidates)
        best_neck = neck_candidates[0]
        self.assertLessEqual(best_neck.neck_ratio, 0.80)

        intensity_peaks = find_intensity_peaks_in_contour(metrics.mask, image, params)
        distance_peaks, distance_image = _find_distance_peaks_in_contour(
            metrics.mask,
            params,
        )
        intensity_pair = _best_peak_pair(
            intensity_peaks,
            cv2.GaussianBlur(image.astype(np.float32), (3, 3), 0),
            params,
            max_valley_ratio_key="max_intensity_valley_ratio",
        )
        distance_pair = _best_peak_pair(
            distance_peaks,
            distance_image,
            params,
            max_valley_ratio_key="max_distance_valley_ratio",
        )
        split_peak_pair = _choose_split_peak_pair(intensity_pair, distance_pair, params)

        self.assertIsNotNone(split_peak_pair)

        split_labels = split_contour_with_watershed(
            metrics.mask,
            image,
            split_peak_pair,
            params,
            neck_candidate=best_neck,
        )
        self.assertEqual(
            len(
                validate_split_contours(
                    metrics.mask,
                    split_labels,
                    image,
                    params,
                    peak_pair=split_peak_pair,
                    neck_candidate=best_neck,
                )
            ),
            0,
        )

        geometry_labels = split_contour_with_geometry_first_watershed(
            metrics.mask,
            image,
            best_neck,
            params,
        )
        geometry_children = validate_geometry_first_split(
            metrics.mask,
            geometry_labels,
            params,
            best_neck,
        )
        self.assertEqual(len(geometry_children), 2)

        aggressive = postprocess_gfp_contours_for_neck_splits(
            [contour],
            image,
            {"mode": "aggressive"},
        )
        self.assertEqual(_contour_list_count(aggressive), 2)

    def test_aggressive_find_contours_splits_tiny_tip_connected_merge_that_balanced_keeps_merged(self):
        image = _tip_connected_pair_image()

        balanced = _split_green_contours_from_image(image, "balanced")
        aggressive = _split_green_contours_from_image(image, "aggressive")

        self.assertEqual(_contour_list_count(balanced, min_area=4.0), 1)
        self.assertEqual(_contour_list_count(aggressive, min_area=4.0), 2)

    def test_find_contours_passes_identical_pre_postprocess_green_contours_to_balanced_and_aggressive(self):
        image = _tip_connected_pair_image()
        captured: dict[str, list[np.ndarray]] = {}

        def capture(contours, gfp_image, config=None):
            del gfp_image
            mode = (config or {}).get("mode", "balanced")
            captured[mode] = [contour.copy() for contour in contours]
            return list(contours)

        with patch(
            "core.contour_processing.contour_operations.postprocess_gfp_contours_for_neck_splits",
            side_effect=capture,
        ):
            _split_green_contours_from_image(image, "balanced")
            _split_green_contours_from_image(image, "aggressive")

        expected = _green_pre_postprocess_contours_from_image(image)
        self.assertEqual(len(captured["balanced"]), len(expected))
        self.assertEqual(len(captured["aggressive"]), len(expected))
        for expected_contour, balanced_contour, aggressive_contour in zip(
            expected,
            captured["balanced"],
            captured["aggressive"],
        ):
            self.assertTrue(np.array_equal(expected_contour, balanced_contour))
            self.assertTrue(np.array_equal(expected_contour, aggressive_contour))

    def test_aggressive_filtered_find_contours_restores_original_when_filter_would_drop_one_child(self):
        image = _tip_connected_pair_image()

        aggressive = _split_green_contours_from_image(image, "aggressive")
        aggressive_filtered = _split_green_contours_from_image(
            image,
            "aggressive",
            green_contour_filter_enabled=True,
        )
        original = _green_pre_postprocess_contours_from_image(image)

        self.assertEqual(_contour_list_count(aggressive, min_area=4.0), 2)
        self.assertEqual(len(original), 1)
        self.assertEqual(_contour_list_count(aggressive_filtered, min_area=4.0), 1)
        self.assertEqual(cv2.contourArea(aggressive_filtered[0]), cv2.contourArea(original[0]))

    def test_aggressive_filtered_find_contours_preserves_clean_two_child_split(self):
        image = _gaussian_pair_image(bridge_intensity=90.0)

        aggressive = _split_green_contours_from_image(image, "aggressive")
        aggressive_filtered = _split_green_contours_from_image(
            image,
            "aggressive",
            green_contour_filter_enabled=True,
        )

        self.assertEqual(_contour_list_count(aggressive, min_area=4.0), 2)
        self.assertEqual(_contour_list_count(aggressive_filtered, min_area=4.0), 2)
        self.assertEqual(
            sorted(cv2.contourArea(contour) for contour in aggressive),
            sorted(cv2.contourArea(contour) for contour in aggressive_filtered),
        )

    def test_real_failure_like_geometry_keeps_two_bright_children_and_lower_blob(self):
        image = _real_failure_like_green_image()

        preprocessed = _green_pre_postprocess_contours_from_image(image)
        aggressive = _split_green_contours_from_image(image, "aggressive")
        aggressive_filtered = _split_green_contours_from_image(
            image,
            "aggressive",
            green_contour_filter_enabled=True,
        )

        self.assertEqual(len(preprocessed), 2)
        self.assertEqual(len(aggressive), 3)
        self.assertEqual(len(aggressive_filtered), 3)

        centroids = [_contour_centroid(contour) for contour in aggressive_filtered]
        self.assertTrue(any(x < 52 and y < 42 for x, y in centroids))
        self.assertTrue(any(x > 52 and y < 42 for x, y in centroids))
        self.assertTrue(any(x > 54 and y > 44 for x, y in centroids))

    def test_green_filter_rescues_strong_peak_that_fails_legacy_shape_rule(self):
        mask = np.zeros((64, 64), dtype=np.uint8)
        cv2.circle(mask, (32, 32), 8, 255, -1)
        contour = _contours_from_mask(mask)[0]
        image = np.zeros(mask.shape, dtype=np.float32)
        image = _add_gaussian(image, center=(32, 32), amplitude=210.0, sigma=3.0)
        image = np.clip(image, 0, 255).astype(np.uint8)

        accepted, decisions = _filter_green_contours_with_image([contour], image)

        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(decisions), 1)
        decision = decisions[0]
        self.assertEqual(decision.decision_reason, "accepted_strong_peak")
        self.assertIsNotNone(decision.closed_open_ratio)
        self.assertGreater(decision.closed_open_ratio, 0.9)
        self.assertLess(decision.closed_open_ratio, 1.06)
        self.assertGreaterEqual(decision.max_over_ring_p90, 3.0)
        self.assertGreaterEqual(decision.p90_over_ring_p90, 2.5)

    def test_green_filter_rejects_weak_shape_failed_contour_without_strong_peak(self):
        mask = np.zeros((64, 64), dtype=np.uint8)
        cv2.circle(mask, (32, 32), 8, 255, -1)
        contour = _contours_from_mask(mask)[0]
        image = np.full(mask.shape, 35, dtype=np.float32)
        image = _add_gaussian(image, center=(32, 32), amplitude=25.0, sigma=4.0)
        image = np.clip(image, 0, 255).astype(np.uint8)

        accepted, decisions = _filter_green_contours_with_image([contour], image)

        self.assertEqual(len(accepted), 0)
        self.assertEqual(decisions[0].decision_reason, "rejected_shape")
        self.assertLess(decisions[0].max_over_ring_p90, 3.0)
        self.assertLess(decisions[0].p90_over_ring_p90, 2.5)

    def test_green_filter_uses_ring_floor_when_ring_percentile_is_zero(self):
        mask = np.zeros((64, 64), dtype=np.uint8)
        cv2.circle(mask, (32, 32), 8, 255, -1)
        contour = _contours_from_mask(mask)[0]
        image = np.zeros(mask.shape, dtype=np.uint8)
        image[mask > 0] = 160

        accepted, decisions = _filter_green_contours_with_image([contour], image)

        self.assertEqual(len(accepted), 1)
        self.assertEqual(decisions[0].decision_reason, "accepted_strong_peak")
        self.assertEqual(decisions[0].ring_p90, 0.0)
        self.assertTrue(np.isfinite(decisions[0].max_over_ring_p90))
        self.assertTrue(np.isfinite(decisions[0].p90_over_ring_p90))

    def test_green_filter_handles_contour_touching_image_edge(self):
        mask = np.zeros((48, 48), dtype=np.uint8)
        cv2.circle(mask, (4, 4), 6, 255, -1)
        contour = _contours_from_mask(mask)[0]
        image = np.zeros(mask.shape, dtype=np.float32)
        image = _add_gaussian(image, center=(4, 4), amplitude=190.0, sigma=2.5)
        image = np.clip(image, 0, 255).astype(np.uint8)

        accepted, decisions = _filter_green_contours_with_image([contour], image)

        self.assertEqual(len(accepted), 1)
        self.assertIn(
            decisions[0].decision_reason,
            {"accepted_shape", "accepted_strong_peak"},
        )
        self.assertLessEqual(decisions[0].bbox[0], 1)
        self.assertLessEqual(decisions[0].bbox[1], 1)
        if decisions[0].decision_reason == "accepted_strong_peak":
            self.assertGreater(decisions[0].ring_pixel_count, 0)

    def test_green_filter_stays_conservative_when_neighbor_contaminates_ring(self):
        mask = np.zeros((72, 72), dtype=np.uint8)
        cv2.circle(mask, (28, 36), 8, 255, -1)
        contour = _contours_from_mask(mask)[0]
        image = np.full(mask.shape, 8, dtype=np.float32)
        image = _add_gaussian(image, center=(28, 36), amplitude=70.0, sigma=3.0)
        image = _add_gaussian(image, center=(39, 36), amplitude=120.0, sigma=3.0)
        image = np.clip(image, 0, 255).astype(np.uint8)

        accepted, decisions = _filter_green_contours_with_image([contour], image)

        self.assertEqual(len(accepted), 0)
        self.assertEqual(decisions[0].decision_reason, "rejected_shape")
        self.assertLess(decisions[0].max_over_ring_p90, 3.0)
