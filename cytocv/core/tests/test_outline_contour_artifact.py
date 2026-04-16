"""Tests for the canonical `.outline` contour artifact and its round-trip."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import cv2
import numpy as np
from django.test import SimpleTestCase

from core.services.canonical_contours import load_cell_mask


def _write_outline(output_dir: Path, contours: list[list[tuple[int, int]]], *, image_stem: str = "test", cell_id: int = 1) -> Path:
    out = output_dir / "output"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{image_stem}-{cell_id}.outline"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        for idx, contour in enumerate(contours):
            if idx > 0:
                writer.writerow([])
            for (y, x) in contour:
                writer.writerow([y, x])
    return path


class OutlineContourArtifactTests(SimpleTestCase):
    def test_contour_roundtrip_reconstructs_support_mask(self):
        shape = (40, 40)
        pair_mask = np.zeros(shape, np.uint8)
        pair_mask[10:25, 8:30] = 255

        contours, _ = cv2.findContours(pair_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        self.assertEqual(len(contours), 1)
        points = [(int(p[0][1]), int(p[0][0])) for p in contours[0]]

        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outline(Path(temp_dir), [points])
            reconstructed = load_cell_mask("test.dv", 1, temp_dir, shape)

        self.assertTrue(np.array_equal(reconstructed > 0, pair_mask > 0))

    def test_multi_contour_blank_row_separator(self):
        shape = (30, 40)
        with tempfile.TemporaryDirectory() as temp_dir:
            _write_outline(
                Path(temp_dir),
                [
                    [(2, 2), (2, 8), (8, 8), (8, 2)],
                    [(12, 20), (12, 30), (22, 30), (22, 20)],
                ],
            )
            mask = load_cell_mask("test.dv", 1, temp_dir, shape)

        self.assertGreater(int(mask[5, 5]), 0)
        self.assertGreater(int(mask[17, 25]), 0)
        self.assertEqual(int(mask[5, 25]), 0)
        self.assertEqual(int(mask[17, 5]), 0)

    def test_symmetric_crop_margin_all_sides(self):
        seg = np.zeros((60, 60), dtype=np.int32)
        seg[20:30, 20:30] = 1

        a = np.where(seg == 1)
        min_x = max(int(np.min(a[0])) - 4, 0)
        max_x = min(int(np.max(a[0])) + 4 + 1, seg.shape[0])
        min_y = max(int(np.min(a[1])) - 4, 0)
        max_y = min(int(np.max(a[1])) + 4 + 1, seg.shape[1])

        self.assertEqual(min_x, 16)
        self.assertEqual(max_x, 34)
        self.assertEqual(min_y, 16)
        self.assertEqual(max_y, 34)
        self.assertEqual(20 - min_x, max_x - 30)
        self.assertEqual(20 - min_y, max_y - 30)

    def test_rendering_uses_external_contour_not_erosion(self):
        seg = np.zeros((30, 30), dtype=np.int32)
        seg[10:20, 10:20] = 1
        image = np.zeros((30, 30, 3), dtype=np.uint8)

        for i in range(1, int(np.max(seg) + 1)):
            cell_mask_full = (seg == i).astype(np.uint8) * 255
            contours, _ = cv2.findContours(
                cell_mask_full, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
            )
            cv2.drawContours(image, contours, -1, (0, 255, 255), 1)

        # Boundary pixels receive cyan.
        self.assertTrue(np.array_equal(image[10, 10], np.array([0, 255, 255], dtype=np.uint8)))
        self.assertTrue(np.array_equal(image[19, 19], np.array([0, 255, 255], dtype=np.uint8)))
        # Interior is untouched (no inward erosion ring).
        self.assertTrue(np.array_equal(image[15, 15], np.array([0, 0, 0], dtype=np.uint8)))
        # Exterior is untouched.
        self.assertTrue(np.array_equal(image[5, 5], np.array([0, 0, 0], dtype=np.uint8)))
