from __future__ import annotations

import numpy as np

import random
import skimage.transform
from pathlib import Path
from PIL import Image
from skimage import img_as_ubyte
import logging

from .inference_runtime import INFERENCE_RANDOM_SEED, get_inference_runtime
from .mask_processing import build_labeled_mask_image, save_mask_tiff
from .preprocess_images import PreprocessedImageArtifact

import time

logger = logging.getLogger(__name__)

np.random.seed(INFERENCE_RANDOM_SEED)
random.seed(INFERENCE_RANDOM_SEED)

'''Run images through the pre-trained neural network.

Arguments:
preprocessed_image: metadata describing the preprocessed image produced by preprocess_images.py
output_dir: output directory for inference artifacts
rescale: Set to True if rescale images before processing (saves time)
scale_factor: Multiplier to downsample images by
verbose: Verbose or not (true/false)'''
# def predict_images(test_path, sample_submission, outputfilename, rescale = False, scale_factor = 2, verbose = True):


def _load_inference_image(
    preprocess_image_path: str | Path,
    *,
    rescale: bool,
    scale_factor: int,
) -> np.ndarray:
    """Load one preprocessed image and normalize it to the model's RGB input shape."""

    with Image.open(preprocess_image_path) as image_file:
        original_image = np.array(image_file)

    if rescale:
        if scale_factor <= 0:
            raise ValueError("scale_factor must be greater than 0 when rescale is enabled.")
        height, width = original_image.shape[:2]
        original_image = skimage.transform.resize(
            original_image,
            output_shape=(
                max(1, height // scale_factor),
                max(1, width // scale_factor),
            ),
            preserve_range=True,
        )

    if original_image.ndim < 3:
        original_image = img_as_ubyte(original_image)
        original_image = np.expand_dims(original_image, 2)
        original_image = original_image[:, :, [0, 0, 0]]

    return original_image[:, :, :3]


def _resolved_output_shape(
    preprocessed_image: PreprocessedImageArtifact,
    *,
    rescale: bool,
) -> tuple[int, int] | None:
    if not rescale:
        return None
    return (
        int(preprocessed_image.original_height),
        int(preprocessed_image.original_width),
    )


def _write_prediction_mask(
    pred_masks: np.ndarray,
    scores_masks: np.ndarray | None,
    *,
    preprocessed_image: PreprocessedImageArtifact,
    output_dir: Path,
    rescale: bool,
) -> Path:
    output_mask = build_labeled_mask_image(
        pred_masks,
        scores=scores_masks,
        dilation=True,
        output_shape=_resolved_output_shape(preprocessed_image, rescale=rescale),
    )
    return save_mask_tiff(output_mask, Path(output_dir) / "output" / "mask.tif")


def predict_images(
    preprocessed_image: PreprocessedImageArtifact,
    output_dir: Path,
    rescale=False,
    scale_factor=2,
    verbose=True,
    cancel_check=None,
) -> Path | None:
    if cancel_check and cancel_check():
        return None

    output_dir = Path(output_dir)
    logger.debug("Inference output directory: %s", output_dir)
    if cancel_check and cancel_check():
        return None

    runtime = get_inference_runtime()
    if cancel_check and cancel_check():
        return None

    start_time = time.time()
    if verbose:
        logger.debug("Starting detection for %s", preprocessed_image.image_id)

    original_image = _load_inference_image(
        preprocessed_image.preprocessed_path,
        rescale=rescale,
        scale_factor=scale_factor,
    )
    if cancel_check and cancel_check():
        return None

    with runtime.detect_lock:
        random.seed(INFERENCE_RANDOM_SEED)
        np.random.seed(INFERENCE_RANDOM_SEED)
        runtime.tensorflow.random.set_seed(INFERENCE_RANDOM_SEED)
        results = runtime.model.detect([original_image], verbose=0)

    pred_masks = results[0]["masks"]
    scores_masks = results[0]["scores"]
    mask_path = _write_prediction_mask(
        pred_masks,
        scores_masks,
        preprocessed_image=preprocessed_image,
        output_dir=output_dir,
        rescale=rescale,
    )

    if verbose:
        logger.debug(
            "Completed detection for %s in %.3fs",
            preprocessed_image.image_id,
            time.time() - start_time,
        )

    logger.debug("predict_images finished for %s", preprocessed_image.image_id)
    return mask_path
