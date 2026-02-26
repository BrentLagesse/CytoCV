import cv2, math
import numpy as np
from core.contour_processing import get_largest
from core.image_processing import GrayImage
import scipy.ndimage as ndi
from skimage.segmentation import watershed
from skimage.feature import peak_local_max

def find_contours(images:GrayImage):
    """
    This function finds contours in an image and returns them as a numpy array.
    :param images: Gray scale image list
    :return: Dictionary of contours, best contours
    """
    gray_mcherry_3 = images.get_image('gray_mcherry_3')
    gray_mcherry = images.get_image('gray_mcherry')
    gray_dapi_3 = images.get_image('gray_dapi_3')
    gray_dapi = images.get_image('gray_dapi')
    gray_gfp = images.get_image('GFP')

    dot_contours = []
    if gray_mcherry_3 is not None:
        _, bright_thresh = cv2.threshold(
            gray_mcherry_3,
            0.65,
            1,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
        )
        dot_contours, _ = cv2.findContours(bright_thresh, 1, 2)
        dot_contours = [cnt for cnt in dot_contours if cv2.contourArea(cnt) < 100]  # remove border contour

    # finding threshold
    # ret_mcherry, thresh_mcherry = cv2.threshold(images.get_image('gray_mcherry_3'), 0, 1,
    #                                             cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU)
    # ret, thresh = cv2.threshold(images.get_image('gray_mcherry'), 0, 1,
    #                             cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU)

    thresh_mcherry = None
    thresh = None
    contours = []
    contours_mcherry = []
    bestContours = []
    bestContours_mcherry = []
    if gray_mcherry_3 is not None and gray_mcherry is not None:
        thresh_mcherry = cv2.Canny(gray_mcherry_3, 50, 150)
        thresh = cv2.Canny(gray_mcherry, 50, 150)

        # Try again with less restrictive thresholding if nothing was found
        if np.max(thresh) == 0:
            _, thresh_mcherry = cv2.threshold(
                gray_mcherry_3,
                0,
                1,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU,
            )
            _, thresh = cv2.threshold(
                gray_mcherry,
                0,
                1,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU,
            )

        contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, 2)
        contours_mcherry, _ = cv2.findContours(thresh_mcherry, cv2.RETR_LIST, 2)
        bestContours = get_largest(contours)
        bestContours_mcherry = get_largest(contours_mcherry)

    # finding threshold
    # ret_dapi_3, thresh_dapi_3 = cv2.threshold(images.get_image('gray_dapi_3'), 0, 1,
    #                                             cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU)
    # ret_dapi, thresh_dapi = cv2.threshold(images.get_image('gray_dapi'), 0, 1,
    #                             cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU)
    
    # TODO thresholds need work and the canny edges need to be closed when they aren't. In particular, sometimes chooses wrong brightness of cell
    contours_dapi = []
    contours_dapi_3 = []
    bestContours_dapi = []
    bestContours_dapi_3 = []
    if gray_dapi_3 is not None and gray_dapi is not None:
        thresh_dapi_3 = cv2.Canny(gray_dapi_3, 60, 70)
        thresh_dapi = cv2.Canny(gray_dapi, 60, 70)

        # TODO: Best kernel for closing so far, but better probably exists
        kernel = np.ones((3, 3), np.uint8)
        thresh_dapi_3 = cv2.morphologyEx(thresh_dapi_3, cv2.MORPH_CLOSE, kernel)
        thresh_dapi = cv2.morphologyEx(thresh_dapi, cv2.MORPH_CLOSE, kernel)

        contours_dapi, _ = cv2.findContours(thresh_dapi, cv2.RETR_EXTERNAL, 2)
        contours_dapi_3, _ = cv2.findContours(thresh_dapi_3, cv2.RETR_EXTERNAL, 2)
        contours_dapi_3 = [
            cnt for cnt in contours_dapi_3 if cv2.contourArea(cnt) > 100 and cv2.contourArea(cnt) < 1000
        ]
        bestContours_dapi = get_largest(contours_dapi)
        bestContours_dapi_3 = get_largest(contours_dapi_3) if contours_dapi_3 else []

    contours_gfp = []
    if gray_gfp is not None:
        thresh_gfp = cv2.Canny(gray_gfp, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        thresh_gfp = cv2.morphologyEx(thresh_gfp, cv2.MORPH_CLOSE, kernel)
        contours_gfp, _ = cv2.findContours(thresh_gfp, cv2.RETR_LIST, 2)

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
