import cv2, math
import numpy as np
from core.contour_processing import get_largest
from core.image_processing import GrayImage

def find_contours(images:GrayImage):
    """
    This function finds contours in an image and returns them as a numpy array.
    :param images: Gray scale image list
    :return: Dictionary of contours, best contours
    """
    # finding threshold
    ret_mcherry, thresh_mcherry = cv2.threshold(images.get_image('gray_mcherry_3'), 0, 1,
                                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU)
    ret, thresh = cv2.threshold(images.get_image('gray_mcherry'), 0, 1,
                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU)
    cell_int_ret, cell_int_thresh = cv2.threshold(images.get_image('GFP'), 0, 1,
                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU)

    cell_int_cont, cell_int_h = cv2.findContours(cell_int_thresh, 1, 2)

    contours, h = cv2.findContours(thresh, 1, 2)
    contours_mcherry = cv2.findContours(thresh_mcherry, 1, 2) # return list of contours

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
    bestContours_mcherry = get_largest(contours_mcherry[0])

    return {
        'bestContours': bestContours,
        'bestContours_mcherry': bestContours_mcherry,
        'contours': contours,
        'contours_mcherry': contours_mcherry
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