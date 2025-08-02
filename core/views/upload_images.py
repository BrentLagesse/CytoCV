from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from core.forms import UploadImageForm
from core.models import UploadedImage, DVLayerTifPreview
from .utils import tif_to_jpg
from pathlib import Path
from yeastweb.settings import MEDIA_ROOT
from .variables import PRE_PROCESS_FOLDER_NAME
from mrc import DVFile
from PIL import Image
import uuid, os
import numpy as np
import skimage.exposure
from django.http import HttpResponseNotAllowed
import json
from django.contrib import messages
from django.http import JsonResponse
from ..metadata_processing.dv_channel_parser import (
    extract_channel_config,
    is_valid_dv_file,
    get_dv_layer_count,
)
from core.file.azure import upload_config, temp_blob, upload_image


def upload_images(request):
    """
    Uploads and processes each image in the selected folder individually.
    Generates a unique UUID for each image and applies the same process to each one.
    """
    if request.method == "POST":
        print("POST request received")

        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        files = request.FILES.getlist("files")

        # collect any bad files here
        invalid_files = []

        if not files:
            print("No files received")
            return render(
                request, "form/uploadImage.html", {"error": "No files received."}
            )

        print(f"Files received: {[file.name for file in files]}")

        # Store all UUIDs of the processed images
        image_uuids = []

        # Iterate through each file and assign a unique UUID
        for image_location in files:
            name = image_location.name
            name = Path(name).stem

            # Generate a UUID for the image
            image_uuid = uuid.uuid4()

            # Save the image instance with the generated UUID
            instance = UploadedImage(
                name=name, uuid=image_uuid, file_location=image_location
            )
            instance.save()

            # Validate actual layer count before any preview work
            dv_file_path = str(instance.file_location)
            if not is_valid_dv_file(str(dv_file_path)):
                # record name and actual layer count
                count = get_dv_layer_count(str(dv_file_path))
                invalid_files.append((name, count))
                instance.delete()
                continue

            # only valid files make it into the queue
            image_uuids.append(image_uuid)

            # Extract and save the per-file channel configuration
            dv_file_path = str(instance.file_location)
            channel_config = extract_channel_config(dv_file_path)
            config_json_path = str(image_uuid) + "/channel_config.json"

            upload_config(channel_config, config_json_path)

            # Define the directory for storing preprocessed images
            pre_processed_dir = str(image_uuid) + "/preprocessed_images"
            stored_dv_path = str(instance.file_location)

            print(f"Processing file: {name}, UUID: {image_uuid}")

            # Apply the preprocessing step to each image
            generate_tif_preview_images(stored_dv_path, pre_processed_dir, instance, 4)

        preprocess_url = f'/image/preprocess/{",".join(map(str, image_uuids))}/'

        # Case 3: no valid files
        if not image_uuids:
            msg = "No valid DV files were uploaded. Please upload files with exactly 4 image layers."
            if is_ajax:
                return JsonResponse({"errors": [msg]}, status=400)
            messages.error(request, msg)
            return redirect(request.path)

        # Case 2: some invalid files
        if invalid_files:
            header = "Could not process the following files due to invalid layer counts (expected 4 layers):"
            lines = [header] + [
                f"- {nm}.dv has {cnt} layer{'s' if cnt!=1 else ''}"
                for nm, cnt in invalid_files
            ]
            if is_ajax:
                return JsonResponse({"errors": lines, "redirect": preprocess_url})
            messages.error(request, "\n".join(lines))

        # Case 1: all valid (or mixed after pushing messages)
        if is_ajax:
            return JsonResponse({"redirect": preprocess_url})
        return redirect(preprocess_url)
    else:
        form = UploadImageForm()
    return render(request, "form/uploadImage.html", {"form": form})


def generate_tif_preview_images(
    dv_path, save_path, uploaded_image: UploadedImage, n_layers: int
):
    """
    Converts DV's layers into tif files
    """
    try:
        with temp_blob(dv_path, ".dv") as temp_file_path:
            dv_file = DVFile(temp_file_path)
            is_n_layers_the_same = len(dv_file.asarray()) == n_layers
            if not is_n_layers_the_same:
                # TODO handler if not the same
                # currently changes n_layers to prevent from crashing
                print(f"Uploaded Dv file layers do not match n_layers {n_layers}")
                n_layers = len(dv_file.asarray())
            for i in range(n_layers):
                dv = dv_file.asarray()[i]
                # using the pre_preprocess methods from mrcnn because else the dv layers are essentially entirely black to the eye
                image = Image.fromarray(dv)
                # Preprocessing operations
                image = skimage.exposure.rescale_intensity(
                    np.float32(image), out_range=(0, 1)
                )
                image = np.round(image * 255).astype(np.uint8)  # convert to 8 bit
                image = np.expand_dims(image, axis=-1)
                rgb_image = np.tile(image, 3)  # convert to RGB
                # rgbimage = skimage.filters.gaussian(rgbimage, sigma=(1,1))   # blur it first?

                rgb_image = Image.fromarray(rgb_image)
                tif_path = save_path + f"/preprocess-image{i}.tif"
                saved_path = upload_image(rgb_image, tif_path)

                jpg_path = tif_to_jpg(output_dir=save_path, tif_path=saved_path)
                # gets path relative to MEDIA ROOT for django
                # Ex. 0c51afb4-d8cb-43e5-a75c-8d4cc0f31a14\preprocessed_images\preprocess-image0.jpg
                file_location = jpg_path
                instance = DVLayerTifPreview(
                    wavelength="",
                    uploaded_image_uuid=uploaded_image,
                    file_location=str(file_location),
                )
                instance.save()
            dv_file.close()

    except Exception as e:
        print(f"Error procesing {e}")
        return None
