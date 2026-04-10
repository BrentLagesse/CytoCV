import cv2
import math
import numpy as np
import logging

from core.contour_processing import get_largest
from core.image_processing import GrayImage

logger = logging.getLogger(__name__)


def find_contours(
    images: GrayImage,
    green_contour_filter_enabled: bool = False,
    alternate_red_detection: bool = False,
):
    """
    Find red dot contours, blue nucleus contours, and green signal contours.
    """

    gray_red_3 = images.get_image("gray_red_3")
    gray_red = images.get_image("gray_red")
    gray_blue_3 = images.get_image("gray_blue_3")
    gray_blue = images.get_image("gray_blue")
    gray_green = images.get_image("green")

    dot_contours = []
    contours = []
    contours_red = []
    best_contours = []
    best_contours_red = []

    if not alternate_red_detection:
        if gray_red_3 is not None:
            low_val, _ = cv2.threshold(
                gray_red_3,
                0.65,
                255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            )
            _, bright_thresh = cv2.threshold(
                gray_red_3,
                low_val + 11,
                255,
                cv2.THRESH_BINARY,
            )
            dot_contours, _ = cv2.findContours(
                bright_thresh,
                cv2.RETR_LIST,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            dot_contours = [cnt for cnt in dot_contours if cv2.contourArea(cnt) < 100]

        thresh_red = None
        thresh = None
        if gray_red_3 is not None and gray_red is not None:
            thresh_red = cv2.Canny(gray_red_3, 50, 150)
            thresh = cv2.Canny(gray_red, 50, 150)

            if np.max(thresh) == 0:
                _, thresh = cv2.threshold(
                    gray_red,
                    0,
                    1,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU,
                )

            if np.max(thresh_red) == 0:
                _, thresh_red = cv2.threshold(
                    gray_red_3,
                    0,
                    1,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU,
                )

            contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            contours_red, _ = cv2.findContours(
                thresh_red,
                cv2.RETR_LIST,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            best_contours = get_largest(contours)
            best_contours_red = get_largest(contours_red)
    else:
        gray_red_3 = cv2.GaussianBlur(gray_red_3, (9, 9), 0)
        if gray_red_3 is not None:
            _, bright_thresh = cv2.threshold(
                gray_red_3,
                3,
                255,
                cv2.THRESH_BINARY,
            )
            dot_contours, _ = cv2.findContours(
                bright_thresh,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )

        if gray_red_3 is not None and gray_red is not None:
            _, thresh = cv2.threshold(
                gray_red,
                5,
                255,
                cv2.THRESH_BINARY,
            )
            thresh_red = bright_thresh
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours_red, _ = cv2.findContours(
                thresh_red,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            best_contours = get_largest(contours)
            best_contours_red = get_largest(contours_red)

    contours_blue = []
    contours_blue_3 = []
    best_contours_blue = []
    best_contours_blue_3 = []
    if gray_blue_3 is not None and gray_blue is not None:
        low_val, _ = cv2.threshold(
            gray_blue,
            0.65,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        _, thresh_blue = cv2.threshold(
            gray_blue,
            low_val + 20,
            255,
            cv2.THRESH_BINARY,
        )

        low_val, _ = cv2.threshold(
            gray_blue_3,
            0.65,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        _, thresh_blue_3 = cv2.threshold(
            gray_blue_3,
            low_val + 17,
            255,
            cv2.THRESH_BINARY,
        )

        contours_blue, _ = cv2.findContours(
            thresh_blue,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        contours_blue_3, _ = cv2.findContours(
            thresh_blue_3,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        best_contours_blue = get_largest(contours_blue)
        best_contours_blue_3 = get_largest(contours_blue_3) if contours_blue_3 else []

    contours_green = []
    if gray_green is not None:
        low_val, _ = cv2.threshold(
            gray_green,
            0.65,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        _, thresh_green = cv2.threshold(
            gray_green,
            low_val + 13,
            255,
            cv2.THRESH_BINARY,
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        thresh_green = cv2.morphologyEx(thresh_green, cv2.MORPH_CLOSE, kernel)
        contours_green, _ = cv2.findContours(
            thresh_green,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        if green_contour_filter_enabled:
            contours_green = filterContours(contours_green)

    return {
        "best_contours": best_contours,
        "best_contours_red": best_contours_red,
        "contours": contours,
        "contours_red": contours_red,
        "contours_blue": contours_blue,
        "contours_blue_3": contours_blue_3,
        "best_contours_blue": best_contours_blue,
        "best_contours_blue_3": best_contours_blue_3,
        "dot_contours": dot_contours,
        "contours_green": contours_green,
    }


def merge_contour(bestContours, contours):
    """
    This function merges contours into a single contour.
    :param bestContours: List of best contours
    :param contours: List of contours
    :return: bestContours merged list
    """
    best_contour = None
    if len(bestContours) == 2:
        c1 = contours[bestContours[0]]
        c2 = contours[bestContours[1]]
        MERGE_CLOSEST = True
        if MERGE_CLOSEST:
            smallest_distance = 999999999
            second_smallest_distance = 999999999
            smallest_pair = (-1, -1)

            for pt1 in c1:
                for i, pt2 in enumerate(c2):
                    d = math.sqrt((pt1[0][0] - pt2[0][0]) ** 2 + (pt1[0][1] - pt2[0][1]) ** 2)
                    if d < smallest_distance:
                        second_smallest_distance = smallest_distance
                        second_smallest_pair = smallest_pair
                        smallest_distance = d
                        smallest_pair = (pt1, pt2, i)
                    elif d < second_smallest_distance:
                        second_smallest_distance = d
                        second_smallest_pair = (pt1, pt2, i)

            best_contour = []
            for pt1 in c1:
                best_contour.append(pt1)
                if pt1[0].tolist() != smallest_pair[0][0].tolist():
                    continue
                start_loc = smallest_pair[2]
                finish_loc = start_loc - 1
                if start_loc == 0:
                    finish_loc = len(c2) - 1
                current_loc = start_loc
                while current_loc != finish_loc:
                    best_contour.append(c2[current_loc])
                    current_loc += 1
                    if current_loc >= len(c2):
                        current_loc = 0
                best_contour.append(c2[finish_loc])

            best_contour = np.array(best_contour).reshape((-1, 1, 2)).astype(np.int32)

    if len(bestContours) == 1:
        best_contour = contours[bestContours[0]]

    if len(bestContours) == 1:
        logger.debug("Only one contour found while merging contour candidates")
    return best_contour


def filterContours(contours):
    """Remove small or obviously invalid contours from the green contour set."""

    contours = [cnt for cnt in contours if cv2.contourArea(cnt) >= 8]
    ret = []
    for cnt in contours:
        closed = cv2.arcLength(cnt, True)
        opened = cv2.arcLength(cnt, False)
        if (closed / opened) <= 0.9 or (closed / opened) >= 1.06:
            ret.append(cnt)
    return ret
