import cv2, math
import numpy as np
from core.image_processing import GrayImage
from .contour_helper import get_largest
import scipy.ndimage as ndi
from skimage.segmentation import watershed
from skimage.feature import peak_local_max

MCHERRY_DOT_METHOD_CURRENT = "current"
MCHERRY_DOT_METHOD_LEGACY = "legacy"
_MCHERRY_DOT_METHODS = {
    MCHERRY_DOT_METHOD_CURRENT,
    MCHERRY_DOT_METHOD_LEGACY,
}


def normalize_mcherry_dot_method(method):
    """Normalize user-provided mCherry dot method values."""
    if not method:
        return MCHERRY_DOT_METHOD_CURRENT
    normalized = str(method).strip().lower()
    if normalized in _MCHERRY_DOT_METHODS:
        return normalized
    return MCHERRY_DOT_METHOD_CURRENT


def _extract_dot_contours(mask):
    """Extract candidate mCherry dot contours from a binary mask."""
    dot_contours, _ = cv2.findContours(mask, cv2.RETR_LIST, 2)
    return [cnt for cnt in dot_contours if cv2.contourArea(cnt) < 100]


def _legacy_otsu_threshold(image):
    """Legacy threshold call used by the original code path."""
    _, thresh = cv2.threshold(
        image,
        0,
        1,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU,
    )
    return thresh


def _legacy_otsu_threshold_with_bias(image, otsu_bias=0.0):
    """Apply Otsu then shift threshold to tune sensitivity (legacy GFP only)."""
    bias = float(otsu_bias or 0.0)
    otsu_threshold, _ = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adjusted_threshold = int(np.clip(otsu_threshold - bias, 0, 255))
    _, thresh = cv2.threshold(image, adjusted_threshold, 1, cv2.THRESH_BINARY)
    return thresh, float(otsu_threshold), float(adjusted_threshold)


def _find_mcherry_contours_current(images: GrayImage):
    """Current mCherry dot detection based on edge-style contour extraction."""
    _, bright_thresh = cv2.threshold(
        images.get_image("gray_mcherry_3"),
        0.65,
        1,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )
    dot_contours = _extract_dot_contours(bright_thresh)

    thresh_mcherry = cv2.Canny(images.get_image("gray_mcherry_3"), 50, 150)
    thresh = cv2.Canny(images.get_image("gray_mcherry"), 50, 150)

    # Fallback to Otsu when Canny finds no edges.
    if np.max(thresh) == 0:
        _, thresh_mcherry = cv2.threshold(
            images.get_image("gray_mcherry_3"),
            0,
            1,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU,
        )
        _, thresh = cv2.threshold(
            images.get_image("gray_mcherry"),
            0,
            1,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU,
        )

    return dot_contours, thresh, thresh_mcherry


def _find_mcherry_contours_legacy(images: GrayImage):
    """Legacy mCherry dot detection based on Otsu thresholding."""
    thresh_mcherry = _legacy_otsu_threshold(images.get_image("gray_mcherry_3"))
    thresh = _legacy_otsu_threshold(images.get_image("gray_mcherry"))
    dot_contours = _extract_dot_contours(thresh_mcherry)
    return dot_contours, thresh, thresh_mcherry


def find_contours(
    images: GrayImage,
    mcherry_dot_method=MCHERRY_DOT_METHOD_CURRENT,
    legacy_gfp_otsu_bias=0.0,
):
    """
    This function finds contours in an image and returns them as a numpy array.
    :param images: Gray scale image list
    :return: Dictionary of contours, best contours
    """
    method = normalize_mcherry_dot_method(mcherry_dot_method)
    legacy_gfp_otsu_threshold = None
    legacy_gfp_adjusted_threshold = None
    legacy_gfp_otsu_bias = float(legacy_gfp_otsu_bias or 0.0)
    if method == MCHERRY_DOT_METHOD_LEGACY:
        dot_contours, thresh, thresh_mcherry = _find_mcherry_contours_legacy(images)
        thresh_dapi_3 = _legacy_otsu_threshold(images.get_image('gray_dapi_3'))
        thresh_dapi = _legacy_otsu_threshold(images.get_image('gray_dapi'))
        (
            thresh_gfp,
            legacy_gfp_otsu_threshold,
            legacy_gfp_adjusted_threshold,
        ) = _legacy_otsu_threshold_with_bias(images.get_image('GFP'), legacy_gfp_otsu_bias)
    else:
        dot_contours, thresh, thresh_mcherry = _find_mcherry_contours_current(images)
        # TODO thresholds need work and the canny edges need to be closed when they aren't.
        thresh_dapi_3 = cv2.Canny(images.get_image('gray_dapi_3'), 60, 70)
        thresh_dapi = cv2.Canny(images.get_image('gray_dapi'), 60, 70)

        # TODO: Best kernel for closing so far, but better probably exists
        kernel = np.ones((3,3), np.uint8)
        thresh_dapi_3 = cv2.morphologyEx(thresh_dapi_3, cv2.MORPH_CLOSE, kernel)
        thresh_dapi = cv2.morphologyEx(thresh_dapi, cv2.MORPH_CLOSE, kernel)

        thresh_gfp = cv2.Canny(images.get_image('GFP'), 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        thresh_gfp = cv2.morphologyEx(thresh_gfp, cv2.MORPH_CLOSE, kernel)

    #cell_int_ret, cell_int_thresh = cv2.threshold(images.get_image('GFP'), 0, 1,
    #                            cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU)

    #cell_int_cont, cell_int_h = cv2.findContours(cell_int_thresh, 1, 2)

    contours, h = cv2.findContours(thresh, cv2.RETR_LIST, 2)
    contours_mcherry, _ = cv2.findContours(thresh_mcherry, cv2.RETR_LIST, 2)

    if method == MCHERRY_DOT_METHOD_LEGACY:
        # Legacy behavior used list-style contour retrieval.
        contours_dapi, h = cv2.findContours(thresh_dapi, cv2.RETR_LIST, 2)
        contours_dapi_3, _ = cv2.findContours(thresh_dapi_3, cv2.RETR_LIST, 2)
        contours_gfp, _ = cv2.findContours(thresh_gfp, cv2.RETR_LIST, 2)
    else:
        contours_dapi, h = cv2.findContours(thresh_dapi, cv2.RETR_EXTERNAL, 2)
        contours_dapi_3, _ = cv2.findContours(thresh_dapi_3, cv2.RETR_EXTERNAL, 2)
        contours_dapi_3 = [
            cnt for cnt in contours_dapi_3 if cv2.contourArea(cnt) > 100 and cv2.contourArea(cnt) < 1000
        ]
        contours_gfp, _ = cv2.findContours(thresh_gfp,cv2.RETR_LIST,2)

    # Biggest contour for the cellular intensity boundary
    # TODO: In the future, handle multiple large contours more robustly
    """
    largest = 0
    largest_cell_cnt = None
    for i, cnt in enumerate(cell_int_cont):
        area = cv2.contourArea(cnt)
        if area > largest:
            largest = area
            largest_cell_cnt = cnt
    """
    # Identify the two largest contours in each set
    bestContours = get_largest(contours)
    bestContours_mcherry = get_largest(contours_mcherry)

    bestContours_dapi = get_largest(contours_dapi)
    bestContours_dapi_3 = get_largest(contours_dapi_3) if contours_dapi_3 else []

    if method == MCHERRY_DOT_METHOD_LEGACY and bestContours_mcherry:
        # Match the original code path: use the largest two mCherry contours for dot metrics.
        dot_contours = [contours_mcherry[i] for i in bestContours_mcherry if i < len(contours_mcherry)]

    return {
        'bestContours': bestContours,
        'bestContours_mcherry': bestContours_mcherry,
        'contours': contours,
        'contours_mcherry': contours_mcherry,
        'contours_dapi': contours_dapi,
        'contours_dapi_3': contours_dapi_3,
        'bestContours_dapi': bestContours_dapi,
        'bestContours_dapi_3': bestContours_dapi_3,
        'dot_contours': dot_contours,
        'contours_gfp': contours_gfp,
        'mcherry_dot_method': method,
        'legacy_gfp_otsu_bias': legacy_gfp_otsu_bias,
        'legacy_gfp_otsu_threshold': legacy_gfp_otsu_threshold,
        'legacy_gfp_adjusted_threshold': legacy_gfp_adjusted_threshold,
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

            # Merge c2 into c1 at the closest points
            best_contour = []
            for pt1 in c1:
                best_contour.append(pt1)
                if pt1[0].tolist() != smallest_pair[0][0].tolist():
                    continue
                # we are at the closest p1
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

    print("only 1 contour found")
    return best_contour
