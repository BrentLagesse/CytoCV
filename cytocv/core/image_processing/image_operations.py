import cv2
from PIL import Image
import numpy as np
from cv2_rolling_ball import subtract_background_rolling_ball
from core.image_processing import GrayImage



def load_image(cp, output_dir, required_channels=None):
    """
    This function loads an image from a file path and returns it as a numpy array.
    :param cp: A CellStatistics object
    :return: A dictionary consist of mCherry, GFP, DAPI image along with their version in numpy array
    """
    requested = set(required_channels or {"mCherry", "GFP", "DAPI"})
    channel_map = {
        "mCherry": ("im_mCherry", "mCherry"),
        "GFP": ("im_GFP", "GFP"),
        "DAPI": ("im_DAPI", "DAPI"),
        "DIC": ("im_DIC", "DIC"),
    }
    loaded = {}

    for channel in requested:
        mapping = channel_map.get(channel)
        if not mapping:
            continue
        im_key, mat_key = mapping
        image_name = cp.get_image(channel, use_id=True, outline=False)
        if not image_name or "None" in str(image_name):
            continue
        image_path = output_dir + '/segmented/' + image_name
        try:
            image = Image.open(image_path)
        except FileNotFoundError:
            continue
        loaded[im_key] = image
        loaded[mat_key] = np.array(image)

    return loaded


def preprocess_image_to_gray(images, kdev, ksize):
    """
    This function preprocesses an image and returns a gray scale of images and blurred version of it.
    :param images: A dictionary consist of mCherry, GFP image along with their version in numpy array
    :param kdev: Kernel deviation for blurring
    :param ksize: Kernel size for blurring
    :return: A dictionary containing grayscale and background-subtracted image data
    """
    # ksize must be odd
    if ksize % 2 == 0:
        ksize += 1
        print("You used an even ksize, updating to odd number +1")

    gray_payload = {}

    gfp_image = images.get("GFP")
    if gfp_image is not None:
        cell_intensity_gray = cv2.cvtColor(gfp_image, cv2.COLOR_RGB2GRAY)
        orig_gray_GFP = cv2.cvtColor(gfp_image, cv2.COLOR_RGB2GRAY)
        orig_gray_GFP_no_bg, _ = subtract_background_rolling_ball(
            orig_gray_GFP,
            50,
            light_background=False,
            use_paraboloid=False,
            do_presmooth=True,
        )
        # Some of the cell outlines are split into two circles. Blur so the contour covers both.
        cell_intensity_gray = cv2.GaussianBlur(cell_intensity_gray, (3, 3), 1)
        gray_payload["GFP"] = cell_intensity_gray
        gray_payload["GFP_no_bg"] = orig_gray_GFP_no_bg

    mcherry_image = images.get("mCherry")
    if mcherry_image is not None:
        original_gray_mcherry = cv2.cvtColor(mcherry_image, cv2.COLOR_RGB2GRAY)
        gray_payload["gray_mcherry_3"] = cv2.GaussianBlur(original_gray_mcherry, (3, 3), 1)
        gray_payload["gray_mcherry"] = cv2.GaussianBlur(original_gray_mcherry, (ksize, ksize), kdev)

    dapi_image = images.get("DAPI")
    if dapi_image is not None:
        original_gray_dapi = cv2.cvtColor(dapi_image, cv2.COLOR_RGB2GRAY)
        gray_payload["gray_dapi_3"] = cv2.GaussianBlur(original_gray_dapi, (3, 3), 1)
        gray_payload["gray_dapi"] = cv2.GaussianBlur(original_gray_dapi, (ksize, ksize), kdev)

    gray_image = GrayImage(img=gray_payload)

    return gray_image
