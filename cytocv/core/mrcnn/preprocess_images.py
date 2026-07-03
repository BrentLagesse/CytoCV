"""Prepare DIC source frames for Mask R-CNN inference."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
import skimage.exposure
import logging

from core.artifact_constants import PRE_PROCESS_FOLDER_NAME
from core.config import get_channel_config_for_uuid
from core.image_sources import load_image_stack
from core.models import UploadedImage
from core.services.artifact_storage import (
    PNG_PROFILE_ANALYSIS_FAST,
    resolve_uploaded_file_path,
    save_png_image,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PreprocessedImageArtifact:
    """Paths and source dimensions passed from preprocessing to inference."""

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


def preprocess_images(
    uuid,
    uploaded_image: UploadedImage,
    output_dir: Path,
    cancel_check=None,
) -> PreprocessedImageArtifact | None:
    """Write the DIC preprocessing PNG expected by the inference pipeline."""

    if cancel_check and cancel_check():
        return None

    logger.debug("Preprocess output directory: %s", output_dir)

    # Channel configuration is written during upload preparation; falling back to
    # index 3 preserves the earlier DIC-default assumption for older runs.
    image_path = resolve_uploaded_file_path(uploaded_image)
    image_stack = load_image_stack(image_path)

    channel_config = get_channel_config_for_uuid(str(uuid))
    dic_index = channel_config.get("DIC", 3)
    image = _select_dic_image_layer(image_stack, dic_index)
    if image is None:
        return None
    height = image.shape[0]
    width = image.shape[1]

    # The inference model consumes RGB PNGs even though the source signal is a
    # single DIC plane, so grayscale intensity is normalized and tiled.
    rgb_image = _preprocess_grayscale_image(image)

    pre_process_dir_path = Path(output_dir / PRE_PROCESS_FOLDER_NAME)
    pre_process_dir_path.mkdir(parents=True, exist_ok=True)
    if cancel_check and cancel_check():
        return None

    # The PNG filename is derived from the original upload stem because inference
    # and cleanup helpers still discover preprocessed assets by that convention.
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
