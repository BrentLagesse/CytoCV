from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
import skimage.exposure
from mrc import DVFile
import logging

from cytocv.settings import MEDIA_ROOT
from core.artifact_constants import PRE_PROCESS_FOLDER_NAME
from core.config import get_channel_config_for_uuid
from core.models import UploadedImage
from core.services.artifact_storage import PNG_PROFILE_ANALYSIS_FAST, save_png_image

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PreprocessedImageArtifact:
    image_id: str
    preprocessed_path: Path
    original_height: int
    original_width: int


def _select_dic_image_layer(image_stack: np.ndarray, dic_index: int) -> np.ndarray | None:
    """Return the DIC layer to use for preprocessing."""

    if image_stack.ndim == 2:
        return image_stack
    if image_stack.ndim != 3:
        return None
    if dic_index >= image_stack.shape[0]:
        dic_index = 0
    return image_stack[dic_index]


def _preprocess_grayscale_image(image: np.ndarray) -> Image.Image:
    """Normalize the grayscale DIC image to an RGB PNG-ready preview."""

    if image.ndim > 2:
        image = image[:, :, 0]
    image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1))
    image = np.round(image * 255).astype(np.uint8)
    image = np.expand_dims(image, axis=-1)
    rgb_image = np.tile(image, 3)
    return Image.fromarray(rgb_image)


#Original header
# def preprocess_images(inputdirectory, mask_dir, outputdirectory, outputfile, verbose = False, use_cache=True):
def preprocess_images(
    uuid,
    uploaded_image: UploadedImage,
    output_dir: Path,
    cancel_check=None,
) -> PreprocessedImageArtifact | None:
    """
        Most commented lines are from the old code base. Have kept until we have the entire product working
    """
    if cancel_check and cancel_check():
        return None

    # constants, easily can be changed 
    logger.debug("Preprocess output directory: %s", output_dir)
    
    #converts windows file path to linux path and joins 
    image_path = Path(MEDIA_ROOT, str(uploaded_image.file_location)) #.replace("/", "\\")
    f = DVFile(image_path)
    try:
        image_stack = f.asarray()
    finally:
        f.close()

    # gets raw image from uploaded dv file
    channel_config = get_channel_config_for_uuid(str(uuid))
    dic_index = channel_config.get("DIC", 3)
    image = _select_dic_image_layer(image_stack, dic_index)
    if image is None:
        return None
    # fileSize = os.path.getsize(uploaded_image.file_location)
    # if fileSize > 8230000:
        #File is a live cell imaging that has more than 4 images
    #     f = DVFile(uploaded_image)
    #     image = f.asarray()[0]
    # if extspl[1] == '.dv':
    #     f = DVFile(uploaded_image)
    #     image = f.asarray()[0]
        #if we don't have .dv files, see if there are tifs in the directory with the proper name structure

        # elif len(extspl) != 2 or extspl[1] != '.tif':  # ignore files that aren't tifs
        #     continue
        # else:
        #     image = np.array(Image.open(inputdirectory + imagename))
    # try:
        # if verbose:
        # print ("Preprocessing ", imagename)
        # existing_files = os.listdir(mask_dir)
        # if imagename in existing_files and use_cache:   #skip this if we have a mask already
            # continue
    # outputdirectory = imagePath
    # grabs only file name
 
    height = image.shape[0]
    width = image.shape[1]

    # Preprocessing operations
    rgb_image = _preprocess_grayscale_image(image)
    #rgbimage = skimage.filters.gaussian(rgbimage, sigma=(1,1))   # blur it first?

    # if not os.path.exists(outputdirectory + imagename) or not use_cache:
    # if not os.path.exists(outputdirectory + imagename):
    # os.makedirs(outputdirectory + imagename)
    # os.makedirs(outputdirectory + imagename + "/images/")
    # pre_process_dir_path = os.path.join(output_directory, PRE_PROCESS_FOLDER_NAME)
    pre_process_dir_path = Path(output_dir / PRE_PROCESS_FOLDER_NAME)
    # makes dir if it already doesn't exist
    pre_process_dir_path.mkdir(parents=True, exist_ok=True)
    # if not pre_process_dir_path.is_dir():
    # os.makedirs(pre_process_dir_path)
    if cancel_check and cancel_check():
        return None

    image_name = Path(uploaded_image.name).stem + ".png"
    pre_process_image_path = pre_process_dir_path / image_name
    save_png_image(
        rgb_image,
        pre_process_image_path,
        profile=PNG_PROFILE_ANALYSIS_FAST,
    )
    logger.debug("Preprocess completed for %s", uploaded_image.uuid)
    return PreprocessedImageArtifact(
        image_id=uploaded_image.name,
        preprocessed_path=pre_process_image_path,
        original_height=int(height),
        original_width=int(width),
    )
    # except IOError:
    #     pass
