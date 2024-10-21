from django.http import HttpResponse
from django.shortcuts import redirect
from pathlib import Path
from PIL import Image
from yeastweb.settings import MEDIA_ROOT

import csv
import numpy as np
import os
import skimage.transform
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

def rleToMask(rleString, height, width):
    rows, cols = height, width
    rleNumbers = [int(numstring) for numstring in rleString.split(' ')]
    rlePairs = np.array(rleNumbers).reshape(-1, 2)
    img = np.zeros(rows * cols, dtype=np.uint8)

    for index, length in rlePairs:
        index -= 1
        img[index:index+length] = 255

    img = img.reshape(cols, rows)
    img = img.T

    return img

def convert_to_image(request, uuid):
    rescale = False
    scale_factor = 2
    verbose = True  # Set verbose to True for debugging

    # Define paths
    rle_file = Path(MEDIA_ROOT) / str(uuid) / "compressed_masks.csv"
    image_list_file = Path(MEDIA_ROOT) / str(uuid) / "preprocessed_images_list.csv"
    outputdirectory = Path(MEDIA_ROOT) / str(uuid) / "output"

    # Debugging log for file paths
    logging.info(f"Checking paths for UUID: {uuid}")
    logging.info(f"RLE file path: {rle_file}")
    logging.info(f"Image list file path: {image_list_file}")
    logging.info(f"Output directory: {outputdirectory}")

    # Check if files exist
    if not rle_file.exists():
        logging.error(f"RLE file not found: {rle_file}")
        return HttpResponse("RLE file not found", status=404)

    if not image_list_file.exists():
        logging.error(f"Image list file not found: {image_list_file}")
        return HttpResponse("Image list file not found", status=404)

    logging.info("Both RLE and image list files found, proceeding...")

    # Create output directory if it doesn't exist
    outputdirectory.mkdir(parents=True, exist_ok=True)

    # Check if output directory is writable
    if not os.access(outputdirectory, os.W_OK):
        logging.error(f"Cannot write to output directory: {outputdirectory}")
        return HttpResponse("Output directory is not writable", status=500)

    # Read the RLE and image list files
    try:
        rle = csv.reader(open(rle_file), delimiter=',')
        rle = np.array([row for row in rle])[1:, :]
    except Exception as e:
        logging.error(f"Error reading RLE file: {e}")
        return HttpResponse("Error reading RLE file", status=500)

    try:
        image_list = csv.reader(open(image_list_file), delimiter=',')
        image_list = np.array([row for row in image_list])[1:, :]
    except Exception as e:
        logging.error(f"Error reading image list file: {e}")
        return HttpResponse("Error reading image list file", status=500)

    files = np.unique(rle[:, 0])
    for f in files:
        if verbose:
            start_time = time.time()
        logging.info(f"Converting {f} to mask...")

        try:
            list_index = np.where(image_list[:, 0] == f)[0][0]
        except IndexError:
            logging.error(f"Image {f} not found in image list.")
            continue

        file_string = image_list[list_index, 1]
        size = file_string.split(" ")
        height = int(size[1])
        width = int(size[2])

        logging.info(f"Image size for {f}: height={height}, width={width}")

        new_height = height
        new_width = width
        if rescale:
            new_height = height // scale_factor
            new_width = width // scale_factor

        image = np.zeros((new_height, new_width)).astype(np.float32)
        columns = np.where(rle[:, 0] == f)
        currobj = 1
        for i in columns[0]:
            logging.info(f"Processing RLE data for object {currobj}")
            try:
                currimg = rleToMask(rle[i, 1], new_height, new_width)
                currimg = currimg > 1
                image = image + (currimg * currobj)
                currobj += 1
            except Exception as e:
                logging.error(f"Error generating mask for {f}: {e}")
                continue

        if rescale:
            image = skimage.transform.resize(image, output_shape=(height, width), order=0, preserve_range=True)

        # Save the image
        mask_path = outputdirectory / "mask.tif"
        try:
            image = Image.fromarray(image.astype(np.uint8))
            image.save(mask_path)
            logging.info(f"Saved mask to: {mask_path}")
        except Exception as e:
            logging.error(f"Error saving mask: {e}")
            return HttpResponse("Error saving mask", status=500)

        if verbose:
            logging.info(f"Completed conversion for {f} in {time.time() - start_time} seconds")

    return redirect(f'/image/{uuid}/segment/')
