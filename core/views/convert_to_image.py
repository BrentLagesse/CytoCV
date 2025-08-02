from django.http import HttpResponse
from django.shortcuts import redirect
from core.file.azure import read_blob_file, temp_blob, upload_image
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
    rleNumbers = [int(numstring) for numstring in rleString.split(" ")]
    rlePairs = np.array(rleNumbers).reshape(-1, 2)
    img = np.zeros(rows * cols, dtype=np.uint8)

    for index, length in rlePairs:
        index -= 1
        img[index : index + length] = 255

    img = img.reshape(cols, rows)
    img = img.T

    return img


def convert_to_image(request, uuids):
    rescale = False
    scale_factor = 2
    verbose = True  # Set verbose to True for debugging

    # Split the `uuids` string into a list of individual UUIDs
    uuid_list = uuids.split(",")

    for uuid in uuid_list:
        # Define paths for each UUID
        # Read the RLE and image list files
        try:
            with temp_blob(
                path=str(uuid) + "/compressed_masks.csv", suffix=".csv"
            ) as tempfile:
                rle = csv.reader(open(tempfile), delimiter=",")
                rle = np.array([row for row in rle])[1:, :]
        except Exception as e:
            print(f"Error reading compressd_mask.csv: {e}")
            continue

        try:
            with temp_blob(
                path=str(uuid) + "/preprocessed_images_list.csv", suffix=".csv"
            ) as tempfile:
                image_list = csv.reader(open(tempfile), delimiter=",")
                image_list = np.array([row for row in image_list])[1:, :]
        except Exception as e:
            logging.error(f"Error reading image list file for UUID {uuid}: {e}")
            continue

        outputdirectory = str(uuid) + "/output"

        files = np.unique(rle[:, 0])
        for f in files:
            if verbose:
                start_time = time.time()
            logging.info(f"Converting {f} to mask for UUID {uuid}...")

            try:
                list_index = np.where(image_list[:, 0] == f)[0][0]
            except IndexError:
                logging.error(f"Image {f} not found in image list for UUID {uuid}.")
                continue

            file_string = image_list[list_index, 1]
            size = file_string.split(" ")
            height = int(size[0])
            width = int(size[1])

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
                logging.info(f"Processing RLE data for object {currobj} in UUID {uuid}")
                try:
                    currimg = rleToMask(rle[i, 1], new_height, new_width)
                    currimg = currimg > 1
                    image = image + (currimg * currobj)
                    currobj += 1
                except Exception as e:
                    logging.error(f"Error generating mask for {f} in UUID {uuid}: {e}")
                    continue

            if rescale:
                image = skimage.transform.resize(
                    image, output_shape=(height, width), order=0, preserve_range=True
                )

            # Save the image
            mask_path = outputdirectory + "/mask.tif"
            try:
                image = Image.fromarray(image.astype(np.uint8))
                upload_image(image, mask_path)
                logging.info(f"Saved mask for UUID {uuid} to: {mask_path}")
            except Exception as e:
                logging.error(f"Error saving mask for UUID {uuid}: {e}")
                continue

            if verbose:
                logging.info(
                    f"Completed conversion for {f} in UUID {uuid} in {time.time() - start_time} seconds"
                )

    # Redirect after processing all UUIDs
    return redirect(f"/image/{uuids}/segment/")
