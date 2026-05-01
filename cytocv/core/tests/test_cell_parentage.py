import cv2
import numpy as np
from django.test import SimpleTestCase

from core.services.cell_parentage import (
    CELL_PARENTAGE_METHOD_NECK_SPLIT,
    CELL_PARENTAGE_METHOD_PRINCIPAL_AXIS,
    CELL_PARENTAGE_MODE_BEST_EFFORT,
    CELL_PARENTAGE_STATUS_IDENTIFIED,
    CELL_PARENTAGE_STATUS_NOT_IDENTIFIED,
    derive_cell_parentage,
)
from core.services.neck_split import NeckSplit


class CellParentageGeometryTests(SimpleTestCase):
    def test_clean_neck_split_is_used_when_available(self):
        cell_mask = np.zeros((30, 30), dtype=np.uint8)
        cell_mask[2:28, 10:20] = 255
        split = NeckSplit(x1=10, y1=17, x2=19, y2=17, status="ok")

        result = derive_cell_parentage(cell_mask, split)
        payload = result.to_payload()

        self.assertEqual(result.status, CELL_PARENTAGE_STATUS_IDENTIFIED)
        self.assertEqual(result.method, CELL_PARENTAGE_METHOD_NECK_SPLIT)
        self.assertGreater(result.mother_area_px, result.daughter_area_px)
        self.assertIsNotNone(result.mother_mask)
        self.assertIsNotNone(result.daughter_mask)
        self.assertEqual(payload["label"], "Mother/Daughter identified")
        self.assertEqual(payload["mode"], CELL_PARENTAGE_MODE_BEST_EFFORT)
        self.assertEqual(payload["mode_label"], "Best Effort")
        self.assertTrue(payload["has_neck_split"])
        self.assertIsNotNone(payload["mother_label_position"])
        self.assertIsNotNone(payload["daughter_label_position"])

    def test_without_neck_split_uses_principal_axis_best_effort(self):
        cell_mask = np.zeros((80, 120), dtype=np.uint8)
        cv2.circle(cell_mask, (35, 40), 25, 255, -1)
        cv2.circle(cell_mask, (85, 40), 14, 255, -1)

        result = derive_cell_parentage(cell_mask, None)

        self.assertEqual(result.status, CELL_PARENTAGE_STATUS_IDENTIFIED)
        self.assertEqual(result.method, CELL_PARENTAGE_METHOD_PRINCIPAL_AXIS)
        self.assertGreater(result.mother_area_px, result.daughter_area_px)
        self.assertLess(result.mother_label_position[0], result.daughter_label_position[0])
        overlap = cv2.bitwise_and(result.mother_mask, result.daughter_mask)
        self.assertEqual(int(np.count_nonzero(overlap)), 0)
        self.assertEqual(
            int(np.count_nonzero(cv2.bitwise_or(result.mother_mask, result.daughter_mask))),
            int(np.count_nonzero(cell_mask)),
        )

    def test_malformed_geometry_does_not_identify_parentage(self):
        result = derive_cell_parentage(
            np.zeros((10, 10), dtype=np.uint8),
            NeckSplit(x1=1, y1=1, x2=8, y2=8, status="ok"),
        )

        self.assertEqual(result.status, CELL_PARENTAGE_STATUS_NOT_IDENTIFIED)
        self.assertEqual(result.reason, "empty_cell_mask")
        self.assertIsNone(result.mother_mask)
        self.assertIsNone(result.daughter_mask)

    def test_single_pixel_mask_does_not_identify_parentage(self):
        cell_mask = np.zeros((10, 10), dtype=np.uint8)
        cell_mask[5, 5] = 255

        result = derive_cell_parentage(cell_mask, None)

        self.assertEqual(result.status, CELL_PARENTAGE_STATUS_NOT_IDENTIFIED)
        self.assertEqual(result.method, CELL_PARENTAGE_METHOD_PRINCIPAL_AXIS)
        self.assertEqual(result.reason, "too_few_cell_pixels")
        self.assertIsNone(result.mother_mask)
        self.assertIsNone(result.daughter_mask)
