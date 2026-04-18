"""Tests for the canonical `.outline` contour artifact and its round-trip."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import cv2
import numpy as np
from django.test import SimpleTestCase

from core.services.canonical_contours import load_cell_mask
from core.services.neck_split import manifest_path, sidecar_path
from core.services.segmentation_pipeline import (
    CYAN_DEBUG_COLOR,
    _build_pair_geometry_cache,
    _build_neck_split_manifest_pairs,
    _crop_bounds_for_label_mask,
    _draw_pair_parentage_labels,
    _draw_pair_geometry_overlay,
    _write_neck_split_manifest_for_run,
)


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
    @staticmethod
    def _cyan_like_mask(image: np.ndarray) -> np.ndarray:
        return (
            (image[:, :, 0] < 80)
            & (image[:, :, 1] > 150)
            & (image[:, :, 2] > 150)
        )

    @staticmethod
    def _bright_label_mask(image: np.ndarray) -> np.ndarray:
        return (
            (image[:, :, 0] > 200)
            & (image[:, :, 1] > 200)
            & (image[:, :, 2] > 200)
        )

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

        bounds = _crop_bounds_for_label_mask((seg == 1).astype(np.uint8) * 255)
        self.assertIsNotNone(bounds)
        min_x, max_x, min_y, max_y = bounds

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

    def test_pair_geometry_overlay_draws_dashed_neck_seam_on_full_frame_and_crop(self):
        seg = np.zeros((80, 100), dtype=np.int32)
        binary = np.zeros(seg.shape, dtype=np.uint8)
        cv2.circle(binary, (38, 40), 18, 255, -1)
        cv2.circle(binary, (58, 40), 18, 255, -1)
        seg[binary > 0] = 1

        cache = _build_pair_geometry_cache(seg)
        entry = cache[1]

        self.assertIsNotNone(entry.local_split)
        self.assertIsNotNone(entry.full_split)

        contour_only = np.zeros((80, 100, 3), dtype=np.uint8)
        cv2.drawContours(contour_only, list(entry.full_contours), -1, CYAN_DEBUG_COLOR, 1)

        outlined = np.zeros((80, 100, 3), dtype=np.uint8)
        _draw_pair_geometry_overlay(outlined, cache)

        contour_mask = self._cyan_like_mask(contour_only)
        outlined_mask = self._cyan_like_mask(outlined)
        seam_mask = outlined_mask & ~contour_mask

        self.assertGreater(int(np.count_nonzero(seam_mask)), 0)

        outlined_crop = outlined[entry.min_x:entry.max_x, entry.min_y:entry.max_y]
        contour_only_crop = contour_only[entry.min_x:entry.max_x, entry.min_y:entry.max_y]
        crop_seam_mask = self._cyan_like_mask(outlined_crop) & ~self._cyan_like_mask(contour_only_crop)
        self.assertGreater(int(np.count_nonzero(crop_seam_mask)), 0)

        no_outline_crop = np.zeros_like(outlined_crop)
        self.assertEqual(int(np.count_nonzero(self._cyan_like_mask(no_outline_crop))), 0)

    def test_per_cell_crop_overlay_is_applied_only_to_dic_like_image(self):
        seg = np.zeros((80, 100), dtype=np.int32)
        binary = np.zeros(seg.shape, dtype=np.uint8)
        cv2.circle(binary, (38, 40), 18, 255, -1)
        cv2.circle(binary, (58, 40), 18, 255, -1)
        seg[binary > 0] = 1

        cache = _build_pair_geometry_cache(seg)
        entry = cache[1]

        dic_canvas = np.zeros((80, 100, 3), dtype=np.uint8)
        _draw_pair_geometry_overlay(dic_canvas, cache)
        dic_crop = dic_canvas[entry.min_x:entry.max_x, entry.min_y:entry.max_y]

        fluorescence_canvas = np.zeros((80, 100, 3), dtype=np.uint8)
        fluorescence_crop = fluorescence_canvas[entry.min_x:entry.max_x, entry.min_y:entry.max_y]

        self.assertGreater(int(np.count_nonzero(self._cyan_like_mask(dic_crop))), 0)
        self.assertEqual(int(np.count_nonzero(self._cyan_like_mask(fluorescence_crop))), 0)

    def test_parentage_labels_are_applied_only_to_dic_like_crop(self):
        seg = np.zeros((80, 100), dtype=np.int32)
        binary = np.zeros(seg.shape, dtype=np.uint8)
        cv2.circle(binary, (38, 40), 18, 255, -1)
        cv2.circle(binary, (58, 40), 18, 255, -1)
        seg[binary > 0] = 1

        cache = _build_pair_geometry_cache(seg)
        entry = cache[1]

        self.assertIsNotNone(entry.local_split)
        self.assertIsNotNone(entry.mother_label_position)
        self.assertIsNotNone(entry.daughter_label_position)

        dic_crop = np.zeros((entry.max_x - entry.min_x, entry.max_y - entry.min_y, 3), dtype=np.uint8)
        fluorescence_crop = np.zeros_like(dic_crop)

        _draw_pair_parentage_labels(dic_crop, entry)

        self.assertGreater(int(np.count_nonzero(self._bright_label_mask(dic_crop))), 0)
        self.assertEqual(int(np.count_nonzero(self._bright_label_mask(fluorescence_crop))), 0)

    def test_neck_split_manifest_writer_persists_one_run_file(self):
        seg = np.zeros((80, 100), dtype=np.int32)
        binary = np.zeros(seg.shape, dtype=np.uint8)
        cv2.circle(binary, (38, 40), 18, 255, -1)
        cv2.circle(binary, (58, 40), 18, 255, -1)
        seg[binary > 0] = 1

        cache = _build_pair_geometry_cache(seg)
        manifest_pairs = _build_neck_split_manifest_pairs(cache)

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = _write_neck_split_manifest_for_run(
                temp_dir,
                image_name="test.dv",
                pair_geometry_cache=cache,
                use_cache=False,
            )

            self.assertEqual(manifest, manifest_path(temp_dir))
            self.assertTrue(manifest.exists())
            self.assertFalse(sidecar_path(temp_dir, "test.dv", 1).exists())

            payload = manifest.read_text(encoding="utf-8")

        self.assertIn('"image_name": "test.dv"', payload)
        self.assertIn('"pairs"', payload)
        self.assertIn('"1"', payload)
        self.assertEqual(manifest_pairs[1]["status"], "ok")
        self.assertIn("side_area_large_px", manifest_pairs[1])
        self.assertIn("side_area_small_px", manifest_pairs[1])
