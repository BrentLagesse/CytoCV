from pathlib import Path
import tempfile

import cv2
import numpy as np
from django.test import SimpleTestCase

from core.services.canonical_contours import (
    CANONICAL_GREEN_SLOTS_KEY,
    CANONICAL_RED_SLOTS_KEY,
    CELL_MASK_KEY,
    build_canonical_contour_payload,
    build_canonical_contour_slots,
)


class CanonicalContourHelpersTests(SimpleTestCase):
    @staticmethod
    def _rect_contour(x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        return np.array(
            [[[x1, y1]], [[x2, y1]], [[x2, y2]], [[x1, y2]]],
            dtype=np.int32,
        )

    def test_build_canonical_contour_slots_clips_to_cell_mask(self):
        shape = (14, 14)
        raw_contour = self._rect_contour(1, 1, 10, 10)
        cell_mask = np.zeros(shape, np.uint8)
        cell_mask[4:11, 4:11] = 255

        slots = build_canonical_contour_slots([raw_contour], cell_mask, shape)

        self.assertEqual(len(slots), 1)
        raw_mask = np.zeros(shape, np.uint8)
        cv2.drawContours(raw_mask, [raw_contour], -1, 255, thickness=-1)
        expected_mask = cv2.bitwise_and(raw_mask, cell_mask)
        self.assertTrue(np.array_equal(slots[0].mask, expected_mask))
        self.assertEqual(int(np.count_nonzero(slots[0].mask[cell_mask == 0])), 0)

    def test_build_canonical_contour_slots_discards_empty_clipped_contours(self):
        shape = (12, 12)
        raw_contour = self._rect_contour(1, 1, 4, 4)
        cell_mask = np.zeros(shape, np.uint8)
        cell_mask[7:11, 7:11] = 255

        slots = build_canonical_contour_slots([raw_contour], cell_mask, shape)

        self.assertEqual(slots, [])

    def test_build_canonical_contour_slots_ranks_by_area_then_center(self):
        shape = (20, 20)
        cell_mask = np.full(shape, 255, np.uint8)
        contours = [
            self._rect_contour(9, 2, 13, 6),
            self._rect_contour(2, 2, 7, 7),
            self._rect_contour(2, 10, 6, 14),
        ]

        slots = build_canonical_contour_slots(contours, cell_mask, shape, limit=3)

        self.assertEqual([slot.source_index for slot in slots], [1, 2, 0])

    def test_build_canonical_contour_slots_computes_center_from_clipped_mask(self):
        shape = (14, 14)
        raw_contour = self._rect_contour(1, 1, 10, 10)
        cell_mask = np.zeros(shape, np.uint8)
        cell_mask[4:11, 6:11] = 255

        slots = build_canonical_contour_slots([raw_contour], cell_mask, shape)

        expected_mask = slots[0].mask
        points = np.column_stack(np.nonzero(expected_mask))
        expected_center = (float(np.mean(points[:, 1])), float(np.mean(points[:, 0])))
        self.assertAlmostEqual(slots[0].center[0], expected_center[0], places=4)
        self.assertAlmostEqual(slots[0].center[1], expected_center[1], places=4)

    def test_build_canonical_contour_payload_reads_outline_pixels_into_cell_mask(self):
        raw_red = self._rect_contour(1, 1, 9, 9)
        raw_green = self._rect_contour(2, 2, 8, 8)
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            outline_path = output_dir / "test-1.outline"
            with outline_path.open("w", encoding="utf-8") as handle:
                for y in range(3, 9):
                    for x in range(4, 10):
                        handle.write(f"{y},{x}\n")

            payload = build_canonical_contour_payload(
                {"dot_contours": [raw_red], "contours_green": [raw_green]},
                image_name="test.dv",
                cell_id=1,
                output_dir=temp_dir,
                shape=(12, 12),
            )

        cell_mask = payload[CELL_MASK_KEY]
        self.assertEqual(int(cell_mask[3, 4]), 255)
        self.assertEqual(int(cell_mask[8, 9]), 255)
        self.assertEqual(int(cell_mask[1, 1]), 0)
        self.assertEqual(len(payload[CANONICAL_RED_SLOTS_KEY]), 1)
        self.assertEqual(len(payload[CANONICAL_GREEN_SLOTS_KEY]), 1)
