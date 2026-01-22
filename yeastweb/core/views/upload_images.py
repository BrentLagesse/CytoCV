from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from core.forms import UploadImageForm
from core.models import UploadedImage, DVLayerTifPreview
from .utils import tif_to_jpg, write_progress
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
from ..metadata_processing.dv_channel_parser import extract_channel_config
from ..metadata_processing.error_handling import (
    DVValidationOptions,
    build_dv_error_messages,
    validate_dv_file,
)


def _parse_bool(value, default=False):
    """Parse a POST boolean value with a safe default."""

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def upload_images(request):
    """
    Uploads and processes each image in the selected folder individually.
    Generates a unique UUID for each image and applies the same process to each one.
    """
    # Ensure session exists to derive a stable progress key
    if not request.session.session_key:
        request.session.save()
    progress_key = request.session.session_key

    if request.method == "POST":
        print("POST request received")
        
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        files = request.FILES.getlist('files')
        
        if not files:
            print("No files received")
            return render(request, 'form/uploadImage.html', {'error': 'No files received.'})

        print(f"Files received: {[file.name for file in files]}")

        enforce_layer_count = _parse_bool(request.POST.get("enforce_layer_count"), default=True)
        enforce_wavelengths = _parse_bool(request.POST.get("enforce_wavelengths"), default=True)
        validation_options = DVValidationOptions(
            enforce_layer_count=enforce_layer_count,
            enforce_wavelengths=enforce_wavelengths,
        )

        # Store all UUIDs of the processed images
        image_uuids = []

        # Iterate through each file and assign a unique UUID
        preprocess_marked = False
        validation_failures = []
        for image_location in files:
            name = image_location.name
            name = Path(name).stem

            # Generate a UUID for the image
            image_uuid = uuid.uuid4()

            # Save the image instance with the generated UUID
            instance = UploadedImage(name=name, uuid=image_uuid, file_location=image_location)
            instance.save()


            # Validate metadata before any preprocessing setup.
            dv_file_path = Path(MEDIA_ROOT) / str(instance.file_location)
            validation_result = validate_dv_file(dv_file_path, validation_options)
            if not validation_result.is_valid:
                validation_failures.append((name, validation_result))
                instance.delete()
                continue

            # only valid files make it into the queue
            image_uuids.append(image_uuid)

            # Create a directory for each image based on its UUID
            output_dir = Path(MEDIA_ROOT, str(image_uuid))
            output_dir.mkdir(parents=True, exist_ok=True)

            # Extract and save the per-file channel configuration
            dv_file_path = Path(MEDIA_ROOT) / str(instance.file_location)
            channel_config = extract_channel_config(dv_file_path)
            config_json_path = output_dir / "channel_config.json"
            with open(config_json_path, "w") as config_file:
                json.dump(channel_config, config_file)

            # Define the directory for storing preprocessed images
            pre_processed_dir = output_dir / PRE_PROCESS_FOLDER_NAME
            stored_dv_path = Path(str(MEDIA_ROOT), str(instance.file_location))

            print(f"Processing file: {name}, UUID: {image_uuid}")

            # Apply the preprocessing step to each image
            if not preprocess_marked:
                write_progress(progress_key, "Preprocessing Images")
                preprocess_marked = True
            generate_tif_preview_images(stored_dv_path, pre_processed_dir, instance, 4)

        error_lines = build_dv_error_messages(validation_failures, validation_options)
        preprocess_url = None
        if image_uuids:
            preprocess_url = f'/image/preprocess/{",".join(map(str, image_uuids))}/'

        # Case 3: no valid files
        if not image_uuids:
            if error_lines:
                if is_ajax:
                    return JsonResponse({'errors': error_lines}, status=400)
                messages.error(request, "\n".join(error_lines))
                return redirect(request.path)
            msg = 'No valid DV files were uploaded. Please upload files that pass the selected checks.'
            if is_ajax:
                return JsonResponse({'errors': [msg]}, status=400)
            messages.error(request, msg)
            return redirect(request.path)

        # Case 2: some invalid files
        if error_lines:
            if is_ajax:
                return JsonResponse({'errors': error_lines, 'redirect': preprocess_url})
            messages.error(request, "\n".join(error_lines))

        # Case 1: all valid (or mixed after pushing messages)
        if is_ajax:
            return JsonResponse({'redirect': preprocess_url})
        return redirect(preprocess_url)
    else:
        form = UploadImageForm()
    return render(request, 'form/uploadImage.html', {'form': form, 'progress_key': progress_key})

def generate_tif_preview_images(dv_path :Path, save_path :Path, uploaded_image : UploadedImage, n_layers : int ):
    """
        Converts DV's layers into tif files
    """
    dv_file = DVFile(dv_path)
    try:
        arr = dv_file.asarray()
    finally:
        dv_file.close()

    if arr.ndim == 2:
        layers = np.expand_dims(arr, axis=0)
    elif arr.ndim == 3:
        # Use the smallest axis as the Z dimension for layer extraction.
        z_axis = int(np.argmin(arr.shape))
        layers = np.moveaxis(arr, z_axis, 0)
    else:
        print(f"Unexpected DV array rank {arr.ndim} for {dv_path}")
        return

    actual_layers = layers.shape[0]
    if actual_layers != n_layers:
        # Prevent huge loops when DV files don't match the expected layer count.
        print(f'Uploaded Dv file layers do not match n_layers {n_layers}')
        n_layers = actual_layers

    for i in range(n_layers):
        dv = layers[i]
        # using the pre_preprocess methods from mrcnn because else the dv layers are essentially entirely black to the eye
        image = Image.fromarray(dv)
        # Preprocessing operations
        image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1))
        image = np.round(image * 255).astype(np.uint8)        #convert to 8 bit
        image = np.expand_dims(image, axis=-1)
        rgb_image = np.tile(image, 3)                          #convert to RGB
        #rgbimage = skimage.filters.gaussian(rgbimage, sigma=(1,1))   # blur it first?

        rgb_image = Image.fromarray(rgb_image)
        save_path.mkdir(parents=True, exist_ok=True)
        tif_path = save_path / f"preprocess-image{i}.tif"
        rgb_image.save(str(tif_path))
        jpg_path = tif_to_jpg(output_dir=save_path, tif_path=tif_path)
        # gets path relative to MEDIA ROOT for django
        # Ex. 0c51afb4-d8cb-43e5-a75c-8d4cc0f31a14\preprocessed_images\preprocess-image0.jpg
        file_location = jpg_path.relative_to(MEDIA_ROOT)
        instance = DVLayerTifPreview(
            wavelength='',
            uploaded_image_uuid=uploaded_image,
            file_location=str(file_location),
        )
        instance.save()
