"""Shared short-dash drawing primitives for debug overlays."""

from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np


DEFAULT_DASH_PX = 2
DEFAULT_GAP_PX = 2


def draw_dashed_line(
    image: np.ndarray,
    p1: Sequence[float],
    p2: Sequence[float],
    color,
    *,
    dash_px: int = DEFAULT_DASH_PX,
    gap_px: int = DEFAULT_GAP_PX,
    thickness: int = 1,
    line_type: int = cv2.LINE_AA,
) -> None:
    """Draw a short-dash segment from ``p1`` to ``p2`` onto ``image`` in place."""

    if image is None or p1 is None or p2 is None:
        return
    dash_px = max(int(dash_px), 1)
    gap_px = max(int(gap_px), 0)

    start = np.asarray(p1, dtype=np.float32).reshape(-1)[:2]
    end = np.asarray(p2, dtype=np.float32).reshape(-1)[:2]
    segment = end - start
    segment_length = float(np.linalg.norm(segment))
    if segment_length <= 0:
        return
    direction = segment / segment_length

    traversed = 0.0
    spacing = float(dash_px + gap_px)
    while traversed <= segment_length:
        seg_start = start + direction * traversed
        seg_end = start + direction * min(traversed + float(dash_px), segment_length)
        p_a = (int(round(float(seg_start[0]))), int(round(float(seg_start[1]))))
        p_b = (int(round(float(seg_end[0]))), int(round(float(seg_end[1]))))
        cv2.line(image, p_a, p_b, color, thickness=thickness, lineType=line_type)
        traversed += spacing


def draw_dashed_polyline(
    image: np.ndarray,
    points: np.ndarray,
    color,
    *,
    closed: bool = True,
    dash_px: int = DEFAULT_DASH_PX,
    gap_px: int = DEFAULT_GAP_PX,
    thickness: int = 1,
    line_type: int = cv2.LINE_AA,
) -> None:
    """Draw a short-dash polyline that preserves spacing across vertices."""

    if image is None or points is None:
        return
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    if pts.shape[0] < 2:
        return
    if closed:
        pts = np.vstack([pts, pts[0]])

    dash_px = max(int(dash_px), 1)
    gap_px = max(int(gap_px), 0)
    spacing = float(dash_px + gap_px)
    next_dash_at = 0.0

    for idx in range(pts.shape[0] - 1):
        start = pts[idx]
        end = pts[idx + 1]
        segment = end - start
        segment_length = float(np.linalg.norm(segment))
        if segment_length <= 0:
            continue
        direction = segment / segment_length
        traversed = float(next_dash_at)
        while traversed <= segment_length:
            seg_start = start + direction * traversed
            seg_end = start + direction * min(traversed + float(dash_px), segment_length)
            p_a = (int(round(float(seg_start[0]))), int(round(float(seg_start[1]))))
            p_b = (int(round(float(seg_end[0]))), int(round(float(seg_end[1]))))
            cv2.line(image, p_a, p_b, color, thickness=thickness, lineType=line_type)
            traversed += spacing
        next_dash_at = traversed - segment_length
