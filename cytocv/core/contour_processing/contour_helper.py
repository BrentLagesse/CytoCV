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
    """
    This function output the two largest contours index in the list of contours
    :param contours: List of contours
    :return: List of indexes of the largest contour in descending order
    """
    best_contour = []
    best_area = []
    for i, contour in enumerate(contours):
        if len(contour) == 0: # if no contour found
            # print(i, "none")
            continue
        # if i == len(contours) - 1:  # not robust #TODO fix it
        if len(contours) > 1 and i == len(contours) - 1:  
            # print(i, "last")
            continue
        area = cv2.contourArea(contour)
        if len(best_contour) == 0: # first contour
            # print(area, i, "first")
            best_contour.append(i)
            best_area.append(area)
            continue
        if len(best_contour) == 1: # second contour
            # print(area, i, "second")
            best_contour.append(i)
            best_area.append(area)

        if area > best_area[0]: # check if current contour area is bigger than biggest
            # print(area, i, "new best")
            # swapping 1st to 2nd and new one to 1st
            best_area[1] = best_area[0]
            best_area[0] = area
            best_contour[1] = best_contour[0]
            best_contour[0] = i
        elif area > best_area[1]: # check if current contour area is bigger than second biggest
            # print(area, i, "new second best")
            best_area[1] = area
            best_contour[1] = i
    return best_contour

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
