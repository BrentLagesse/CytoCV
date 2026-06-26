"""Tests for the post-pair label refinement helper."""

from __future__ import annotations

import cv2
import numpy as np
from django.test import SimpleTestCase

from core.services.pair_refinement import refine_pair_label_image


class RefinePairLabelImageTests(SimpleTestCase):
    def test_narrow_gap_bridged(self):
        """A single label split by a 1px background slit gets bridged."""
        seg = np.zeros((20, 20), dtype=np.float64)
        seg[5:10, 5:9] = 1.0
        seg[5:10, 10:15] = 1.0
        # Column 9 is a 1px gap between the two blobs of label 1.
        self.assertTrue(np.all(seg[5:10, 9] == 0))

        result = refine_pair_label_image(seg)

        # Interior gap rows are bridged by the 3x3 closing.
        self.assertTrue(np.all(result[6:9, 9] == 1.0))

    def test_nearby_pairs_independent(self):
        """Two distinct labels are refined independently; label count preserved."""
        seg = np.zeros((30, 30), dtype=np.float64)
        seg[2:8, 2:8] = 1.0
        seg[20:26, 20:26] = 2.0

        result = refine_pair_label_image(seg)

        unique_labels = set(np.unique(result)) - {0}
        self.assertEqual(unique_labels, {1.0, 2.0})
        # Original pixels unchanged.
        self.assertTrue(np.all(result[2:8, 2:8] == 1.0))
        self.assertTrue(np.all(result[20:26, 20:26] == 2.0))

    def test_conflicting_claims_stay_background(self):
        """Two labels whose closings overlap on the same pixel leave it as 0."""
        seg = np.zeros((20, 20), dtype=np.float64)
        seg[5:10, 5:9] = 1.0
        seg[5:10, 10:15] = 2.0
        # Column 9 is background, 1px from label 1 and 1px from label 2.
        # Both closings will try to claim it.

        result = refine_pair_label_image(seg)

        # Contested pixels must remain background.
        self.assertTrue(np.all(result[5:10, 9] == 0))

    def test_existing_pixels_preserved(self):
        """Every original nonzero pixel retains its value after refinement."""
        seg = np.zeros((30, 30), dtype=np.float64)
        seg[3:12, 3:12] = 1.0
        seg[18:27, 18:27] = 2.0
        original_nonzero = seg.copy()

        result = refine_pair_label_image(seg)

        mask = original_nonzero != 0
        self.assertTrue(np.array_equal(result[mask], original_nonzero[mask]))

    def test_single_label_survives_refinement(self):
        """A retained single-cell label is not removed by pair refinement."""
        seg = np.zeros((20, 20), dtype=np.float64)
        seg[5:12, 5:12] = 1.0

        result = refine_pair_label_image(seg)

        self.assertEqual(set(np.unique(result)) - {0}, {1.0})
        self.assertTrue(np.all(result[5:12, 5:12] == 1.0))

    def test_empty_image_noop(self):
        """An all-zeros input returns an all-zeros output."""
        seg = np.zeros((10, 10), dtype=np.float64)

        result = refine_pair_label_image(seg)

        self.assertTrue(np.all(result == 0))

    def test_hole_filled(self):
        """A label forming a ring (hollow center) gets the interior filled."""
        seg = np.zeros((20, 20), dtype=np.float64)
        # Create a ring: outer block with a hollow center.
        seg[4:16, 4:16] = 1.0
        seg[7:13, 7:13] = 0.0

        result = refine_pair_label_image(seg)

        # The interior hole should now be filled with label 1.
        self.assertTrue(np.all(result[7:13, 7:13] == 1.0))
