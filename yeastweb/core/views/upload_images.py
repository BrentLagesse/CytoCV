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

def upload_images(request):
    """
    To avoid the issue when files have the same name, we generate a uuid4 as the folder name to store all files
    """
    if request.method == "POST":
        form = UploadImageForm(request.POST, request.FILES)
        if form.is_valid():
            name = form.cleaned_data['name']
            files = request.FILES.getlist('files') 
            
            for image in files:
                image_uuid= uuid.uuid4()
                instance = UploadedImage(name=name, uuid=image_uuid, file_location=image)
                instance.save()

                output_dir = Path(MEDIA_ROOT, str(image_uuid))
                print("output dir: ",str(output_dir))

                pre_processed_dir = output_dir / PRE_PROCESS_FOLDER_NAME
                stored_dv_path = Path(str(MEDIA_ROOT), str(instance.file_location))
                generate_tif_preview_images(stored_dv_path, pre_processed_dir, instance, 4)
            return redirect(f'/image/{image_uuid}/')
            return HttpResponse("Image successfully uploaded")
    else:
        form = UploadImageForm()
    form = UploadImageForm()
    return render(request, 'form/uploadImage.html', {'form' : form})



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