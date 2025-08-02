import numpy as np
from PIL import Image
import os
import skimage.exposure
import skimage.filters
from mrc import DVFile
from yeastweb.settings import MEDIA_ROOT
from core.models import UploadedImage
from pathlib import Path
from core.views.variables import PRE_PROCESS_FOLDER_NAME

import csv
from io import StringIO
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from core.file.azure import temp_blob, upload_image


# Original header
# def preprocess_images(inputdirectory, mask_dir, outputdirectory, outputfile, verbose = False, use_cache=True):
def preprocess_images(
    uuid, uploaded_image: UploadedImage, output_dir: Path
) -> tuple[str, str]:
    """
    Most commented lines are from the old code base. Have kept until we have the entire product working
    """
    # constants, easily can be changed
    print("output_directory", output_dir)

    # Creates csv file and writes in first 2 columns ImageId and EncodedRLE for each image
    csv_buffer = StringIO()
    csv_writer = csv.writer(csv_buffer)
    csv_writer.writerow(["ImageId", "EncodedRLE"])

    # converts windows file path to linux path and joins
    image_path = str(uploaded_image.file_location)  # .replace("/", "\\")
    try:
        with temp_blob(image_path, ".dv") as temp_file:
            f = DVFile(temp_file)
    except Exception as e:
        print(f"Pre-process error: {e}")
    # gets raw image from uploaded dv file
    image = f.asarray()[3]

    if len(image.shape) > 2:
        image = image[:, :, 0]
    height = image.shape[0]
    width = image.shape[1]

    # Preprocessing operations
    image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1))
    image = np.round(image * 255).astype(np.uint8)  # convert to 8 bit
    image = np.expand_dims(image, axis=-1)
    rgb_image = np.tile(image, 3)  # convert to RGB

    rgb_image = Image.fromarray(rgb_image)
    # pre_process_dir_path = os.path.join(output_directory, PRE_PROCESS_FOLDER_NAME)
    pre_process_dir_path = output_dir + "/preprocessed_images"

    # if not pre_process_dir_path.is_dir():
    # os.makedirs(pre_process_dir_path)
    image_name = uploaded_image.name.split(".")[0] + ".tif"
    pre_process_image_path = os.path.join(pre_process_dir_path, image_name)
    pre_process_image_path = upload_image(rgb_image, pre_process_image_path)

    csv_writer.writerow([uploaded_image.name, str(height) + " " + str(width)])
    csv_content = csv_buffer.getvalue().encode("utf-8")
    content = ContentFile(csv_content)
    save_path = output_dir + "/preprocessed_images_list.csv"

    preprocessed_image_list_path = default_storage.save(save_path, content)
    print("Pre-process completed FINISHED")
    return pre_process_image_path, preprocessed_image_list_path

    # except IOError:
    #     pass
