"""Small contour-list helpers shared by segmentation and statistics code.

The helpers in this module operate on OpenCV contour arrays and labeled
segmentation images. They intentionally return simple Python containers because
callers pass the results into JSON/debug payloads and table-building code.
"""

import cv2
import logging

logger = logging.getLogger(__name__)

def get_contour_center(contour_list):
    """Return contour centroids keyed by original contour index.

    Zero-area contours are skipped because OpenCV moments cannot produce a
    stable centroid for them and downstream pairing code treats absence as a
    safer signal than a fabricated coordinate.
    """
    coordinates = {}
    for i in range(len(contour_list)):
        contour = contour_list[i]
        moment = cv2.moments(contour)
        if moment['m00'] != 0:
            x = int(moment['m10'] / moment['m00'])
            y = int(moment['m01'] / moment['m00'])
        else: # divide by 0
            logger.debug("Skipping contour %s because it has zero moment", i)
            continue
        coordinates[i] = (x, y)
    return coordinates

def get_largest(contours):
    """Return up to two contour indices sorted by descending area."""

    ranked = []
    for i, contour in enumerate(contours):
        if contour is None or len(contour) == 0:
            continue
        ranked.append((i, cv2.contourArea(contour)))

    ranked.sort(key=lambda item: item[1], reverse=True)
    return [idx for idx, _ in ranked[:2]]

def get_neighbor_count(seg_image, center, radius=1, loss=0):
    """Return labels surrounding a cell center within a square search radius.

    ``seg_image`` is a 2D label image and ``center`` is interpreted as ``(y, x)``.
    The current cell label and background are excluded so callers receive only
    neighboring cell identifiers.
    """
    #TODO:  account for loss as distance gets larger
    neighbor_list = list()
    center_y = center[0]
    center_x = center[1]
    min_y = max(center_y - radius, 0)
    max_y = min(center_y + radius + 1, seg_image.shape[0])
    min_x = max(center_x - radius, 0)
    max_x = min(center_x + radius + 1, seg_image.shape[1])
    neighbors = seg_image[min_y:max_y, min_x:max_x]
    for y_offset, row in enumerate(neighbors):
        for x_offset, val in enumerate(row):
            y = min_y + y_offset
            x = min_x + x_offset
            if ((y, x) != (center_y, center_x) and
                    int(val) != 0 and
                    int(val) != int(seg_image[center_y, center_x])):
                neighbor_list.append(val)
    return neighbor_list
