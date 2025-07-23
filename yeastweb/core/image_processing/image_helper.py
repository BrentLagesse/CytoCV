import cv2
import numpy as np

def create_circular_mask(image_shape, center, radius):
    """
    Draw a circular mask around the center
    :param image_shape: Gray scale image
    :param center: Coordinates of the center of the mask
    :param radius: Radius of the mask
    :return: Masked image
    """
    mask = np.zeros(image_shape, dtype=np.uint8)
    cv2.circle(mask, center, radius, 255, -1)
    return mask

def calculate_intensity_mask(image, mask):
    """
    :param image: Gray scale image
    :param mask: Contour mask
    :return: Sum of values in the mask from the image
    """
    masked_pixel = image[mask > 0]
    return np.sum(masked_pixel) if len(masked_pixel) > 0 else 0

def ensure_3channel_bgr(img_array):
    """
    This function ensures that the image has 3 channels
    :param img_array: an image in matrix form
    :return: 3 channel image
    """
    # If single channel (shape: H x W), convert to BGR
    if len(img_array.shape) == 2:
        return cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
    # If RGBA (shape: H x W x 4), convert to BGR
    elif img_array.shape[2] == 4:
        return cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
    # If already H x W x 3, we assume it's BGR or RGB, but let's treat as BGR
    return img_array
