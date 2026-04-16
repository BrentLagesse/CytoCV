"""Post-pair label refinement for bridging narrow gaps and filling holes."""

from __future__ import annotations

import cv2
import numpy as np


def refine_pair_label_image(seg: np.ndarray) -> np.ndarray:
    """Conservative post-pair refinement: close narrow gaps and fill holes.

    For each pair label, applies morphological closing (disk-1) and hole fill.
    Only background pixels claimed by exactly one label are accepted; contested
    pixels remain background.  Existing labeled pixels are never removed.
    """

    labels = np.unique(seg)
    labels = labels[labels != 0]
    if labels.size == 0:
        return seg.copy()

    result = seg.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    claim_count = np.zeros(seg.shape, dtype=np.int32)
    claim_owner = np.zeros(seg.shape, dtype=seg.dtype)

    for label in labels:
        mask = (seg == label).astype(np.uint8) * 255
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        filled = np.zeros_like(closed)
        cv2.drawContours(filled, contours, -1, 255, cv2.FILLED)
        new_pixels = (filled == 255) & (seg == 0)
        claim_count[new_pixels] += 1
        claim_owner[new_pixels] = label

    accept = claim_count == 1
    result[accept] = claim_owner[accept]
    return result
