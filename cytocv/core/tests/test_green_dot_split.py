"""Tests for Green dot contour splitting."""

from __future__ import annotations

import cv2
import numpy as np
from django.test import SimpleTestCase
from unittest.mock import patch

from core.contour_processing.contour_operations import (
    _split_merged_green_contours,
    _markers_from_neck,
    _split_params,
    _split_contour_with_neck_chord,
    compute_contour_shape_metrics,
    find_contours,
    find_convexity_defect_neck_candidates,
    find_intensity_peaks_in_contour,
    postprocess_gfp_contours_for_neck_splits,
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


def _tip_connected_pair_image(shape=(72, 96)) -> np.ndarray:
    image = np.zeros(shape, dtype=np.float32)
    cv2.circle(image, (46, 40), 7, 230.0, -1)
    cv2.circle(image, (56, 35), 4, 130.0, -1)
    cv2.line(image, (50, 38), (53, 36), 70.0, 1)
    image = cv2.GaussianBlur(image, (0, 0), 1.0)
    return np.clip(image, 0, 255).astype(np.uint8)


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
