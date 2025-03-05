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
from core.dv_channel_parser import extract_channel_config

def upload_images(request):
    """
    Uploads and processes each image in the selected folder individually.
    Generates a unique UUID for each image and applies the same process to each one.
    """
    if request.method == "POST":
        print("POST request received")

        files = request.FILES.getlist('files')
        if not files:
            print("No files received")
            return render(request, 'form/uploadImage.html', {'error': 'No files received.'})

        print(f"Files received: {[file.name for file in files]}")

        # Store all UUIDs of the processed images
        image_uuids = []

        # Iterate through each file and assign a unique UUID
        for image_location in files:
            name = image_location.name
            name = Path(name).stem

            # Generate a UUID for the image
            image_uuid = uuid.uuid4()
            image_uuids.append(image_uuid)

            # Save the image instance with the generated UUID
            instance = UploadedImage(name=name, uuid=image_uuid, file_location=image_location)
            instance.save()

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
            generate_tif_preview_images(stored_dv_path, pre_processed_dir, instance, 4)

        # After processing all files, redirect to pre-process step for the first file
        if image_uuids:
            return redirect(f'/image/preprocess/{",".join(map(str, image_uuids))}/')
        else:
            return render(request, 'form/uploadImage.html', {'error': 'Error processing files.'})
    
    else:
        form = UploadImageForm()
    return render(request, 'form/uploadImage.html', {'form': form})

def generate_tif_preview_images(dv_path :Path, save_path :Path, uploaded_image : UploadedImage, n_layers : int ):
    """
        Converts DV's layers into tif files
    """
    dv_file = DVFile(dv_path)
    is_n_layers_the_same = len(dv_file.asarray()) == n_layers
    if not is_n_layers_the_same :
        # TODO handler if not the same
        # currently changes n_layers to prevent from crashing
        print(f'Uploaded Dv file layers do not match n_layers {n_layers}')
        n_layers = len(dv_file.asarray())
    for i in range(n_layers) :
        dv = DVFile(dv_path).asarray()[i]
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
        dv_file.close()
        jpg_path = tif_to_jpg(output_dir= save_path, tif_path= tif_path)
        # gets path relative to MEDIA ROOT for django
        # Ex. 0c51afb4-d8cb-43e5-a75c-8d4cc0f31a14\preprocessed_images\preprocess-image0.jpg 
        file_location = jpg_path.relative_to(MEDIA_ROOT)
        instance = DVLayerTifPreview(wavelength='', uploaded_image_uuid =uploaded_image, file_location = str(file_location))
        instance.save()