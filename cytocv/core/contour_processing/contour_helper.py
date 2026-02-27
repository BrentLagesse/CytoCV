import cv2

def get_contour_center(contour_list):
    """
    This function calculate the center of the contours
    :param contour_list: list of contours
    :return: Dictionary with x,y coordinates of centers
    """
    coordinates = {}
    for i in range(len(contour_list)):
        contour = contour_list[i]
        moment = cv2.moments(contour)
        if moment['m00'] != 0:
            x = int(moment['m10'] / moment['m00'])
            y = int(moment['m01'] / moment['m00'])
        else: # divide by 0
            print(f"Warning contour {i} has zero moment, skipping")
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
    """
    This function output the number of neighbors between center and radius
    :param seg_image: 2D matrix represent a cell segmented image
    :param center: coordinate of the center of the cell in (y,x)
    :param radius: radius of searching for neighbor
    :param loss:
    :return: list of cell's id of cell that is within the radius
    """
    #TODO:  account for loss as distance gets larger
    neighbor_list = list()
    center_y = center[0]
    center_x = center[1]
    # select a square segment that is a radius away from the center
    neighbors = seg_image[center_y - radius:center_y + radius + 1, center_x - radius:center_x + radius + 1]
    for x, row in enumerate(neighbors):
        for y, val in enumerate(row):
            if ((x, y) != (radius, radius) and # check for pixel that are in the circumference
                    int(val) != 0 and # not a cell pixel
                    int(val) != int(seg_image[center_y, center_x])): # not part of the same cell
                neighbor_list.append(val)
    return neighbor_list
