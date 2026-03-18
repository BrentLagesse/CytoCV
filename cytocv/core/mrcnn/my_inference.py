from __future__ import annotations

import numpy as np

import random
import pandas as pd
import skimage.transform
from pathlib import Path
from PIL import Image
from skimage import img_as_ubyte

from ..mrcnn import my_functions as f
from .inference_runtime import INFERENCE_RANDOM_SEED, get_inference_runtime

import time

np.random.seed(INFERENCE_RANDOM_SEED)
random.seed(INFERENCE_RANDOM_SEED)

'''Run images through the pre-trained neural network.

Arguments:
preprocess_image_path: Path where the images are stored (preprocess these using preprocess_images.py)
preprocessed_image_list_path: Path of the comma-delimited file of images names.
outputfile: Path to write the comma-delimited run-length file to.
rescale: Set to True if rescale images before processing (saves time)
scale_factor: Multiplier to downsample images by
verbose: Verbose or not (true/false)'''
# def predict_images(test_path, sample_submission, outputfilename, rescale = False, scale_factor = 2, verbose = True):


def _initialize_rle_output(output_dir: Path) -> Path:
    """Create a fresh run-length output file for the current UUID."""

    rle_file_path = Path(output_dir, "compressed_masks.csv")
    with rle_file_path.open("w", encoding="utf-8") as rle_file:
        rle_file.write("ImageId, EncodedPixels\n")
    return rle_file_path


def _load_preprocessed_image_index(preprocessed_image_list_path: Path) -> pd.DataFrame:
    """Load the CSV index produced by preprocess_images()."""

    return pd.read_csv(preprocessed_image_list_path)


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


def predict_images(
    preprocess_image_path,
    preprocessed_image_list_path: Path,
    output_dir: Path,
    rescale=False,
    scale_factor=2,
    verbose=True,
    cancel_check=None,
) -> Path | None:
    if cancel_check and cancel_check():
        return None

    output_dir = Path(output_dir)
    print("output_directory", output_dir)
    rle_file_path = _initialize_rle_output(output_dir)

    preprocessed_image_index = _load_preprocessed_image_index(preprocessed_image_list_path)
    n_images = len(preprocessed_image_index.index)
    if n_images == 0:
        print("NO IMAGES WERE DETECTED")
        return None
    if cancel_check and cancel_check():
        return None

    runtime = get_inference_runtime()
    if cancel_check and cancel_check():
        return None

    for i in range(n_images):
        if cancel_check and cancel_check():
            return None
        start_time = time.time()
        image_id = str(preprocessed_image_index.iloc[i]["ImageId"])
        if verbose:
            print("Start detect", i, "  ", image_id)

        original_image = _load_inference_image(
            preprocess_image_path,
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
        class_ids = results[0]["class_ids"]

        if len(class_ids):
            ImageId_batch, EncodedPixels_batch, _ = f.numpy2encoding(
                pred_masks,
                image_id,
                scores=scores_masks,
                dilation=True,
            )
            f.write2csv(rle_file_path, ImageId_batch, EncodedPixels_batch)

        if verbose:
            print("Completed in", time.time() - start_time)
    
    print("predict_images FINISHED")
    return rle_file_path
