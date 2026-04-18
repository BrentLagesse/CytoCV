"""Tests for `core.services.neck_split`."""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np
from django.test import SimpleTestCase

from core.services.neck_split import (
    STATUS_OK,
    NeckSplit,
    compute_side_areas,
    detect_neck_split,
    read_neck_split,
    sidecar_path,
    write_neck_split,
)


def _dumbbell(radius_a: int, radius_b: int, center_distance: int, shape=(120, 160)) -> np.ndarray:
    """Binary mask containing two overlapping circles on a horizontal axis."""

    mask = np.zeros(shape, dtype=np.uint8)
    cy = shape[0] // 2
    cx_a = shape[1] // 2 - center_distance // 2
    cx_b = shape[1] // 2 + center_distance // 2
    cv2.circle(mask, (cx_a, cy), radius_a, 255, -1)
    cv2.circle(mask, (cx_b, cy), radius_b, 255, -1)
    return mask


def _outer_contour(mask: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(contours, key=len)


class DetectNeckSplitTests(SimpleTestCase):
    def test_symmetric_dumbbell_returns_ok_split_near_midline(self):
        mask = _dumbbell(25, 25, center_distance=40)
        contour = _outer_contour(mask)

        split = detect_neck_split(contour, mask)

        self.assertIsNotNone(split)
        self.assertEqual(split.status, STATUS_OK)
        midline_x = mask.shape[1] // 2
        self.assertLess(abs(split.x1 - midline_x), 4)
        self.assertLess(abs(split.x2 - midline_x), 4)
        # Chord runs vertically across the neck with meaningful length.
        self.assertGreater(abs(split.y1 - split.y2), 10)

    def test_single_circle_returns_none(self):
        mask = np.zeros((80, 80), dtype=np.uint8)
        cv2.circle(mask, (40, 40), 25, 255, -1)
        contour = _outer_contour(mask)

        self.assertIsNone(detect_neck_split(contour, mask))

    def test_multi_component_mask_returns_none(self):
        mask = np.zeros((80, 120), dtype=np.uint8)
        cv2.circle(mask, (25, 40), 15, 255, -1)
        cv2.circle(mask, (95, 40), 15, 255, -1)
        # Use the first circle's contour; the multi-component guard should
        # still reject the mask before convex-hull analysis runs.
        contour = _outer_contour(mask)

        self.assertIsNone(detect_neck_split(contour, mask))

    def test_asymmetric_dumbbell_side_areas_ordered(self):
        mask = _dumbbell(25, 12, center_distance=30)
        contour = _outer_contour(mask)

        split = detect_neck_split(contour, mask)
        self.assertIsNotNone(split)

        larger_px, smaller_px, larger_mask, smaller_mask = compute_side_areas(mask, split)
        self.assertGreater(larger_px, smaller_px)
        self.assertEqual(larger_mask.shape, mask.shape)
        self.assertEqual(smaller_mask.shape, mask.shape)
        self.assertGreater(int(np.count_nonzero(larger_mask)), 0)
        self.assertGreater(int(np.count_nonzero(smaller_mask)), 0)

    def test_symmetric_dumbbell_side_areas_roughly_equal(self):
        mask = _dumbbell(25, 25, center_distance=40)
        contour = _outer_contour(mask)

        split = detect_neck_split(contour, mask)
        self.assertIsNotNone(split)

        larger_px, smaller_px, _, _ = compute_side_areas(mask, split)
        total = larger_px + smaller_px
        # Allow 10 % asymmetry for pixelization of the chord.
        self.assertLess(abs(larger_px - smaller_px) / max(total, 1), 0.10)

    def test_compute_side_areas_does_not_mutate_input(self):
        mask = _dumbbell(25, 25, center_distance=40)
        contour = _outer_contour(mask)
        split = detect_neck_split(contour, mask)
        self.assertIsNotNone(split)

        snapshot = mask.copy()
        compute_side_areas(mask, split)
        self.assertTrue(np.array_equal(mask, snapshot))

    def test_degenerate_short_contour_returns_none(self):
        mask = np.zeros((20, 20), dtype=np.uint8)
        mask[5:7, 5:8] = 255
        contour = _outer_contour(mask)

        self.assertIsNone(detect_neck_split(contour, mask))


class SidecarRoundTripTests(SimpleTestCase):
    def test_write_then_read_equal(self):
        split = NeckSplit(x1=10, y1=20, x2=30, y2=40, defect_depth_1=512, defect_depth_2=400)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = sidecar_path(temp_dir, "image.dv", 7)
            write_neck_split(path, split)
            loaded = read_neck_split(path)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.to_dict(), split.to_dict())

    def test_sidecar_path_mirrors_outline_naming(self):
        path = sidecar_path("/tmp/run", "sample.dv", 3)
        self.assertTrue(str(path).endswith("output/sample-3.neck_split") or str(path).endswith("output\\sample-3.neck_split"))

    def test_missing_sidecar_returns_none(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "output" / "missing-1.neck_split"
            self.assertIsNone(read_neck_split(path))

    def test_malformed_sidecar_returns_none(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "output" / "bad-1.neck_split"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("garbage", encoding="utf-8")
            self.assertIsNone(read_neck_split(path))
