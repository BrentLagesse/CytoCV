"""Regression tests for shared masked-intensity helper calculations."""

import numpy as np
from django.test import SimpleTestCase

from core.image_processing.image_helper import calculate_masked_intensity_stats


class MaskedIntensityStatsTests(SimpleTestCase):
    def test_calculates_total_max_and_average_from_masked_pixels(self):
        image = np.array(
            [
                [1, 2, 3],
                [4, 5, 6],
                [7, 8, 9],
            ],
            dtype=np.uint16,
        )
        mask = np.array(
            [
                [0, 255, 0],
                [255, 255, 0],
                [0, 0, 0],
            ],
            dtype=np.uint8,
        )

        total, maximum, average = calculate_masked_intensity_stats(image, mask)

        self.assertEqual(total, 11.0)
        self.assertEqual(maximum, 5.0)
        self.assertAlmostEqual(average, 11.0 / 3.0)

    def test_empty_mask_is_safe(self):
        image = np.array([[1, 2], [3, 4]], dtype=np.uint16)
        mask = np.zeros_like(image, dtype=np.uint8)

        self.assertEqual(
            calculate_masked_intensity_stats(image, mask),
            (0.0, 0.0, 0.0),
        )

    def test_one_pixel_mask_is_safe(self):
        image = np.array([[1, 2], [3, 4]], dtype=np.uint16)
        mask = np.array([[0, 0], [0, 255]], dtype=np.uint8)

        self.assertEqual(
            calculate_masked_intensity_stats(image, mask),
            (4.0, 4.0, 4.0),
        )
