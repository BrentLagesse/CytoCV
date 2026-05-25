from django.test import SimpleTestCase
import cv2
import numpy as np

from core.channel_roles import CHANNEL_ROLE_RED
from core.contour_processing import find_contours
from core.image_processing import GrayImage
from core.services.red_nucleus_speckle_mask import (
    RED_NUCLEUS_MASK_PAYLOAD_KEY,
    build_red_nucleus_speckle_mask,
)


class RedNucleusSpeckleMaskTests(SimpleTestCase):
    @staticmethod
    def _cell_mask(shape=(64, 64), margin=5):
        mask = np.zeros(shape, dtype=np.uint8)
        mask[margin : shape[0] - margin, margin : shape[1] - margin] = 255
        return mask

    @staticmethod
    def _component_count(mask: np.ndarray) -> int:
        count, _ = cv2.connectedComponents((mask > 0).astype(np.uint8), 8)
        return count - 1

    def test_compact_red_nucleus_stays_tight(self):
        red = np.zeros((64, 64), dtype=np.uint8)
        cv2.circle(red, (32, 32), 5, 220, -1)
        expected = np.zeros_like(red)
        cv2.circle(expected, (32, 32), 5, 255, -1)

        result = build_red_nucleus_speckle_mask(red, cell_mask=self._cell_mask())

        expected_area = int(np.count_nonzero(expected))
        final_area = int(np.count_nonzero(result.final_mask))
        self.assertGreaterEqual(final_area, int(expected_area * 0.6))
        self.assertLessEqual(final_area, int(expected_area * 1.4))

    def test_sparse_red_speckles_are_preserved_without_filling_between_them(self):
        red = np.zeros((64, 64), dtype=np.uint8)
        cv2.circle(red, (18, 18), 2, 230, -1)
        cv2.circle(red, (46, 44), 2, 230, -1)

        result = build_red_nucleus_speckle_mask(red, cell_mask=self._cell_mask())

        self.assertEqual(self._component_count(result.final_mask), 2)
        self.assertEqual(result.final_mask[31, 32], 0)
        self.assertLess(int(np.count_nonzero(result.final_mask)), 80)

    def test_faint_red_background_is_rejected_while_speckles_remain(self):
        red = np.zeros((64, 64), dtype=np.uint8)
        red[self._cell_mask() > 0] = 15
        red[12:52, 12:52] = 22
        cv2.circle(red, (24, 24), 2, 95, -1)
        cv2.circle(red, (41, 39), 2, 90, -1)

        result = build_red_nucleus_speckle_mask(red, cell_mask=self._cell_mask())

        self.assertGreater(int(np.count_nonzero(result.final_mask)), 0)
        self.assertLess(int(np.count_nonzero(result.final_mask)), 100)
        self.assertEqual(result.final_mask[16, 16], 0)

    def test_nearby_supported_speckles_may_connect(self):
        red = np.zeros((64, 64), dtype=np.uint8)
        cv2.circle(red, (29, 32), 2, 220, -1)
        cv2.circle(red, (35, 32), 2, 220, -1)
        cv2.line(red, (31, 32), (33, 32), 180, 1)

        result = build_red_nucleus_speckle_mask(
            red,
            cell_mask=self._cell_mask(),
            bridge_distance_px=8,
        )

        self.assertEqual(self._component_count(result.final_mask), 1)

    def test_distant_red_speckles_do_not_merge_into_one_giant_mask(self):
        red = np.zeros((64, 64), dtype=np.uint8)
        cv2.circle(red, (16, 16), 2, 220, -1)
        cv2.circle(red, (50, 48), 2, 220, -1)

        result = build_red_nucleus_speckle_mask(red, cell_mask=self._cell_mask())

        self.assertEqual(self._component_count(result.final_mask), 2)
        self.assertEqual(result.final_mask[32, 32], 0)

    def test_final_mask_is_clipped_inside_cell_boundary(self):
        red = np.zeros((64, 64), dtype=np.uint8)
        cv2.circle(red, (8, 8), 5, 230, -1)
        cell_mask = self._cell_mask(margin=10)

        result = build_red_nucleus_speckle_mask(red, cell_mask=cell_mask)

        self.assertFalse(np.any(result.final_mask[cell_mask == 0]))

    def test_find_contours_aggressive_red_keeps_standard_red_contours_unchanged(self):
        red = np.zeros((48, 48), dtype=np.uint8)
        cv2.circle(red, (24, 24), 5, 255, -1)
        images = GrayImage(
            img={
                "red_no_bg": red,
                "gray_red": red,
                "gray_red_3": red,
                "green": np.zeros_like(red),
                "green_no_bg": np.zeros_like(red),
                "gray_blue": np.zeros_like(red),
                "gray_blue_3": np.zeros_like(red),
            }
        )

        standard = find_contours(images)
        balanced = find_contours(
            images,
            alternate_red_detection=True,
            alternate_detection_channel=CHANNEL_ROLE_RED,
            nuclear_cell_pair_contour_mode="balanced",
        )
        aggressive = find_contours(
            images,
            alternate_red_detection=True,
            alternate_detection_channel=CHANNEL_ROLE_RED,
            nuclear_cell_pair_contour_mode="aggressive",
        )

        self.assertEqual(len(balanced["dot_contours"]), len(standard["dot_contours"]))
        self.assertEqual(len(aggressive["dot_contours"]), len(standard["dot_contours"]))
        self.assertTrue(balanced["alternate_nucleus_contours_red"])
        self.assertIsNone(balanced[RED_NUCLEUS_MASK_PAYLOAD_KEY])
        self.assertTrue(aggressive["alternate_nucleus_contours_red"])
        self.assertIsNotNone(aggressive[RED_NUCLEUS_MASK_PAYLOAD_KEY])
