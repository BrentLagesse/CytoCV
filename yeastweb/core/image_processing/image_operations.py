import cv2
from PIL import Image
import numpy as np
from cv2_rolling_ball import subtract_background_rolling_ball
from core.image_processing import GrayImage



def load_image(cp, output_dir):
    """
    This function loads an image from a file path and returns it as a numpy array.
    :param cp: A CellStatistics object
    :return: A dictionary consist of mCherry, GFP, DAPI image along with their version in numpy array
    """
    # outlines screw up the cell_analysis
    cp_mCherry = cp.get_image('mCherry',use_id=True, outline=False)
    cp_GFP = cp.get_image('GFP',use_id=True, outline=False)
    cp_DAPI = cp.get_image('DAPI',use_id=True, outline=False)

    # opening the image from the saved segmented directory
    print("test123", 'segmented/' + cp_mCherry)
    im_mCherry = Image.open(output_dir + '/segmented/' + cp_mCherry)
    im_GFP = Image.open(output_dir + '/segmented/' + cp_GFP)
    im_DAPI = Image.open(output_dir + '/segmented/' + cp_DAPI)

    # convert image to matrix
    im_mCherry_mat = np.array(im_mCherry)
    GFP_img_mat = np.array(im_GFP)
    im_DAPI_mat = np.array(im_DAPI)

    return {
        'im_mCherry': im_mCherry,
        'im_GFP': im_GFP,
        'im_DAPI': im_DAPI,
        "mCherry": im_mCherry_mat,
        "GFP":GFP_img_mat,
        "DAPI": im_DAPI_mat,}


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

    # was RGBA2GRAY
    # converting to gray scale
    cell_intensity_gray = cv2.cvtColor(images["GFP"], cv2.COLOR_RGB2GRAY)
    orig_gray_GFP = cv2.cvtColor(images['GFP'], cv2.COLOR_RGB2GRAY)
    orig_gray_GFP_no_bg, background = subtract_background_rolling_ball(orig_gray_GFP, 50, light_background=False,
                                                                       use_paraboloid=False, do_presmooth=True)
    original_gray_mcherry = cv2.cvtColor(images['mCherry'], cv2.COLOR_RGB2GRAY)
    original_gray_dapi = cv2.cvtColor(images['DAPI'], cv2.COLOR_RGB2GRAY)

    # blurring the boundaries
    gray_mcherry_3 = cv2.GaussianBlur(original_gray_mcherry, (3, 3), 1)

    gray_mcherry = cv2.GaussianBlur(original_gray_mcherry, (ksize, ksize), kdev)  # need to save gray

    # blurring the boundaries
    gray_dapi_3 = cv2.GaussianBlur(original_gray_dapi, (3, 3), 1)

    gray_dapi = cv2.GaussianBlur(original_gray_dapi, (ksize, ksize), kdev)  # need to save gray

    # Some of the cell outlines are split into two circles. Blur so that the contour covers both
    cell_intensity_gray = cv2.GaussianBlur(cell_intensity_gray, (3,3), 1)

    gray_image = GrayImage(img={
        'gray_mcherry_3': gray_mcherry_3,
        'gray_mcherry': gray_mcherry,
        'gray_dapi_3': gray_dapi_3,
        'gray_dapi': gray_dapi,
        'GFP': cell_intensity_gray,
        'GFP_no_bg': orig_gray_GFP_no_bg,
    })

    return gray_image
