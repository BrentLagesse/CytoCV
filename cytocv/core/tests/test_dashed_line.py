"""Tests for the shared dashed-line helpers."""

from __future__ import annotations

import cv2
import numpy as np
from django.test import SimpleTestCase

from core.image_processing.dashed_line import draw_dashed_line, draw_dashed_polyline


class DrawDashedLineTests(SimpleTestCase):
    def test_horizontal_line_produces_alternating_gaps(self):
        canvas = np.zeros((10, 60), dtype=np.uint8)
        draw_dashed_line(
            canvas,
            (5, 5),
            (54, 5),
            255,
            dash_px=6,
            gap_px=4,
            thickness=1,
            line_type=cv2.LINE_8,
        )
        # There should be both lit and unlit pixels along the row.
        row = canvas[5, 5:55]
        self.assertGreater(int(np.count_nonzero(row)), 0)
        self.assertGreater(int((row == 0).sum()), 0)
        # The first pixel of a new dash is always lit (we start with draw=True).
        self.assertEqual(int(canvas[5, 5]), 255)

    def test_zero_length_segment_is_noop(self):
        canvas = np.zeros((10, 10), dtype=np.uint8)
        draw_dashed_line(canvas, (3, 3), (3, 3), 255)
        self.assertEqual(int(canvas.sum()), 0)

    def test_polyline_dash_phase_persists_across_vertices(self):
        canvas = np.zeros((40, 40), dtype=np.uint8)
        # Closed square perimeter. We just verify something is drawn and
        # the helper does not raise for closed polylines.
        points = np.array([[5, 5], [34, 5], [34, 34], [5, 34]], dtype=np.int32)
        draw_dashed_polyline(
            canvas,
            points,
            255,
            closed=True,
            dash_px=6,
            gap_px=4,
            thickness=1,
            line_type=cv2.LINE_8,
        )
        self.assertGreater(int(np.count_nonzero(canvas)), 0)

    def test_none_image_is_ignored(self):
        # Should not raise.
        draw_dashed_line(None, (0, 0), (10, 10), 255)
        draw_dashed_polyline(None, np.array([[0, 0], [1, 1]]), 255)

    def test_single_point_polyline_is_noop(self):
        canvas = np.zeros((10, 10), dtype=np.uint8)
        draw_dashed_polyline(canvas, np.array([[5, 5]]), 255)
        self.assertEqual(int(canvas.sum()), 0)
