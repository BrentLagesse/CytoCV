"""Small mask and intensity primitives used by statistics plugins."""

import cv2
import numpy as np

def create_circular_mask(image_shape, contour, index):
    """Rasterize one contour into a uint8 mask matching the source image shape."""

    mask = np.zeros(image_shape, dtype=np.uint8)
    cv2.drawContours(mask, contour, index, 255, -1)
    return mask

def calculate_intensity_mask(image, mask):
    """Return the summed grayscale intensity inside a positive mask."""

    masked_pixel = image[mask > 0]
    return np.sum(masked_pixel) if len(masked_pixel) > 0 else 0

def calculate_masked_intensity_stats(image, mask):
    """Return total, max, and mean grayscale intensity for a masked region."""

    masked_pixel = image[mask > 0]
    if len(masked_pixel) == 0:
        return 0.0, 0.0, 0.0
    return (
        float(np.sum(masked_pixel)),
        float(np.max(masked_pixel)),
        float(np.mean(masked_pixel)),
    )

def ensure_3channel_bgr(img_array):
    """Return a 3-channel OpenCV-compatible image for contour drawing."""

    if len(img_array.shape) == 2:
        return cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
    elif img_array.shape[2] == 4:
        return cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
    return img_array
