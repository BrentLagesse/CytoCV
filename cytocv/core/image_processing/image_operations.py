"""Image loading and grayscale preparation shared by statistics plugins."""

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
    # Statistics plugins may mutate PIL images or numpy arrays while drawing and
    # measuring, so cached crop data is always copied before reuse.
    cached_array = np.array(image_array, copy=True)
    return Image.fromarray(cached_array.copy()), cached_array


def _get_mapping_value(mapping, *keys):
    # Measurement images can be keyed by canonical channel role or by older plugin
    # payload names; accepting both keeps saved analysis paths compatible.
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _as_single_channel(image_array):
    # Raw measurement planes are normalized to one grayscale array so downstream
    # plugins receive the same shape regardless of RGB/RGBA/TIFF source layout.
    array = np.asarray(image_array)
    if array.ndim == 2:
        return np.array(array, copy=True)
    if array.ndim == 3 and array.shape[2] == 1:
        return np.array(array[:, :, 0], copy=True)
    if array.ndim == 3 and array.shape[2] == 4:
        return cv2.cvtColor(array, cv2.COLOR_RGBA2GRAY)
    if array.ndim == 3:
        return cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
    return np.array(array, copy=True)


def load_image(cp, output_dir, required_channels=None, cached_images=None):
    """Load segmented channel crops required by the selected statistics plugins."""

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
            # Segmentation already cropped these arrays from the source stack; reusing
            # them avoids round-tripping through PNG files while preserving copy safety.
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
            # A missing optional channel crop should skip that plugin input rather
            # than fail statistics for the whole cell/run.
            continue
        loaded[im_key] = Image.fromarray(np.array(image_array, copy=True))
        loaded[mat_key] = image_array

    return loaded


def preprocess_image_to_gray(images, kdev, ksize, measurement_images=None):
    """Build the grayscale payload consumed by contour statistics plugins."""

    # OpenCV Gaussian kernels must be odd; keep the historical "round up"
    # behavior so saved workflow defaults do not need extra validation here.
    if ksize % 2 == 0:
        ksize += 1
        logger.debug("Adjusted even kernel size to next odd value: %s", ksize)

    gray_payload = {}

    green_image = images.get("green")
    if green_image is not None:
        cell_intensity_gray = cv2.cvtColor(green_image, cv2.COLOR_RGB2GRAY)
        original_gray_green = cv2.cvtColor(green_image, cv2.COLOR_RGB2GRAY)
        # Rolling-ball subtraction is part of the historical red/green contour
        # measurement payload; keep these raw-minus-background keys stable.
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
        # Red payloads expose both a fixed small blur and the user-configured blur
        # because different legacy and modern plugins consume different keys.
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

    measurement_images = measurement_images or {}
    # Raw planes are supplied separately so total/max/average intensity metrics
    # use measurement input data rather than normalized display crops.
    raw_green = _get_mapping_value(measurement_images, CHANNEL_ROLE_GREEN, "green")
    if raw_green is not None:
        gray_payload["raw_green"] = _as_single_channel(raw_green)

    raw_red = _get_mapping_value(measurement_images, CHANNEL_ROLE_RED, "red")
    if raw_red is not None:
        gray_payload["raw_red"] = _as_single_channel(raw_red)

    raw_blue = _get_mapping_value(measurement_images, CHANNEL_ROLE_BLUE, "blue")
    if raw_blue is not None:
        gray_payload["raw_blue"] = _as_single_channel(raw_blue)

    gray_image = GrayImage(img=gray_payload)

    return gray_image
