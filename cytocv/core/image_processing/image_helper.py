"""Small mask and intensity primitives used by statistics plugins."""

import cv2
import numpy as np

def create_circular_mask(image_shape, contour, index):
    """Rasterize one contour into a uint8 mask matching the source image shape.

    Statistics plugins pass OpenCV contour lists and expect a 0/255 mask that can
    index grayscale intensity arrays without changing the original image.
    """

    mask = np.zeros(image_shape, dtype=np.uint8)
    cv2.drawContours(mask, contour, index, 255, -1)
    return mask

def calculate_intensity_mask(image, mask):
    """Return the summed grayscale intensity inside a positive mask.

    Empty masks intentionally report zero so missing or filtered contours do not
    force every caller to special-case unavailable measurements.
    """

    masked_pixel = image[mask > 0]
    return np.sum(masked_pixel) if len(masked_pixel) > 0 else 0

def calculate_masked_intensity_stats(image, mask):
    """Return total, max, and mean grayscale intensity for a masked region.

    The tuple shape is consumed by red/green contour summaries and must remain
    stable even when the mask has no foreground pixels.
    """

    masked_pixel = image[mask > 0]
    if len(masked_pixel) == 0:
        return 0.0, 0.0, 0.0
    return (
        float(np.sum(masked_pixel)),
        float(np.max(masked_pixel)),
        float(np.mean(masked_pixel)),
    )

def ensure_3channel_bgr(img_array):
    """Return a 3-channel OpenCV-compatible image for contour drawing.

    Overlay/debug drawing uses OpenCV's BGR conventions.  Single-channel and
    RGBA inputs are normalized here so callers can draw contours without
    repeating channel-shape checks.
    """

    if len(img_array.shape) == 2:
        return cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
    elif img_array.shape[2] == 4:
        return cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
    return img_array
