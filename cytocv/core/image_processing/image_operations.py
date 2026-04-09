import os

import cv2
from PIL import Image
import numpy as np
import logging
from cv2_rolling_ball import subtract_background_rolling_ball
from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
)
from .grey_image import GrayImage

logger = logging.getLogger(__name__)


def _copy_cached_image(image_array):
    cached_array = np.array(image_array, copy=True)
    return Image.fromarray(cached_array.copy()), cached_array


def load_image(cp, output_dir, required_channels=None, cached_images=None):
    """
    This function loads an image from a file path and returns it as a numpy array.
    :param cp: A CellStatistics object
    :return: A dictionary containing red, green, blue, and DIC image arrays
    """
    requested = set(required_channels or {CHANNEL_ROLE_RED, CHANNEL_ROLE_GREEN, CHANNEL_ROLE_BLUE})
    cached_images = cached_images or {}
    channel_map = {
        CHANNEL_ROLE_RED: ("im_red", "red"),
        CHANNEL_ROLE_GREEN: ("im_green", "green"),
        CHANNEL_ROLE_BLUE: ("im_blue", "blue"),
        CHANNEL_ROLE_DIC: ("im_dic", "dic"),
    }
    loaded = {}

    for channel in requested:
        mapping = channel_map.get(channel)
        if not mapping:
            continue
        im_key, mat_key = mapping
        if channel in cached_images and cached_images[channel] is not None:
            cached_image, cached_array = _copy_cached_image(cached_images[channel])
            loaded[im_key] = cached_image
            loaded[mat_key] = cached_array
            continue
        image_name = cp.get_image(channel, use_id=True, outline=False)
        if not image_name or "None" in str(image_name):
            continue
        image_path = os.path.join(output_dir, "segmented", image_name)
        try:
            with Image.open(image_path) as image:
                image_array = np.array(image)
        except FileNotFoundError:
            continue
        loaded[im_key] = Image.fromarray(np.array(image_array, copy=True))
        loaded[mat_key] = image_array

    return loaded


def preprocess_image_to_gray(images, kdev, ksize):
    """
    This function preprocesses an image and returns a gray scale of images and blurred version of it.
    :param images: A dictionary containing red, green, and blue image arrays
    :param kdev: Kernel deviation for blurring
    :param ksize: Kernel size for blurring
    :return: A dictionary containing grayscale and background-subtracted image data
    """
    # ksize must be odd
    if ksize % 2 == 0:
        ksize += 1
        logger.debug("Adjusted even kernel size to next odd value: %s", ksize)

    gray_payload = {}

    green_image = images.get("green")
    if green_image is not None:
        cell_intensity_gray = cv2.cvtColor(green_image, cv2.COLOR_RGB2GRAY)
        original_gray_green = cv2.cvtColor(green_image, cv2.COLOR_RGB2GRAY)
        original_gray_green_no_bg, _ = subtract_background_rolling_ball(
            original_gray_green,
            50,
            light_background=False,
            use_paraboloid=False,
            do_presmooth=True,
        )
        # Some of the cell outlines are split into two circles. Blur so the contour covers both.
        cell_intensity_gray = cv2.GaussianBlur(cell_intensity_gray, (3, 3), 1)
        gray_payload["green"] = cell_intensity_gray
        gray_payload["green_no_bg"] = original_gray_green_no_bg

    red_image = images.get("red")
    if red_image is not None:
        original_gray_red = cv2.cvtColor(red_image, cv2.COLOR_RGB2GRAY)
        red_no_bg, _ = subtract_background_rolling_ball(
            original_gray_red,
            50,
            light_background=False,
            use_paraboloid=False,
            do_presmooth=True,
        )
        gray_payload["gray_red_3"] = cv2.GaussianBlur(original_gray_red, (3, 3), 1)
        gray_payload["gray_red"] = cv2.GaussianBlur(original_gray_red, (ksize, ksize), kdev)
        gray_payload["red_no_bg"] = red_no_bg

    blue_image = images.get("blue")
    if blue_image is not None:
        original_gray_blue = cv2.cvtColor(blue_image, cv2.COLOR_RGB2GRAY)
        gray_payload["gray_blue_3"] = cv2.GaussianBlur(original_gray_blue, (3, 3), 1)
        gray_payload["gray_blue"] = cv2.GaussianBlur(original_gray_blue, (ksize, ksize), kdev)

    gray_image = GrayImage(img=gray_payload)

    return gray_image
