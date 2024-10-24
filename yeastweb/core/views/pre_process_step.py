from django.shortcuts import  get_object_or_404, render, get_list_or_404, redirect
from django.http import JsonResponse, HttpResponse
from core.models import DVLayerTifPreview, UploadedImage
from django.template.response import TemplateResponse
from core.mrcnn.my_inference import predict_images
from core.mrcnn.preprocess_images import preprocess_images
import os
from .utils import tif_to_jpg
from yeastweb.settings import MEDIA_ROOT
from pathlib import Path
# chose function because https://spookylukey.github.io/django-views-the-right-way/context-data.html

def pre_process_step(request, uuids):
    """
    Handles the display and processing of multiple images using UUIDs.
    Displays current images based on the file index for GET requests,
    and processes all UUIDs for POST requests.
    """
    uuid_list = uuids.split(',')

    # Get the total number of files
    total_files = len(uuid_list)

    # Get the current file index from the request query (default is 0 if not provided)
    current_file_index = int(request.GET.get('file_index', 0))

    # Ensure the current file index is within bounds
    current_file_index = max(0, min(current_file_index, total_files - 1))

    # Retrieve the current UUID based on file index
    current_uuid = uuid_list[current_file_index]

    # Get the image and its preview images for the current UUID
    uploaded_image = get_object_or_404(UploadedImage, uuid=current_uuid)
    preview_images = get_list_or_404(DVLayerTifPreview, uploaded_image_uuid=current_uuid)

    # If the request is POST, process all the UUIDs
    if request.method == "POST":
        for image_uuid in uuid_list:
            uploaded_image = get_object_or_404(UploadedImage, uuid=image_uuid)
            output_directory = Path(MEDIA_ROOT) / str(image_uuid)

            # Preprocess and run the model on the image
            preprocess_image_path, preprocessed_image_list_path = preprocess_images(image_uuid, uploaded_image, output_directory)
            tif_to_jpg(Path(preprocess_image_path), Path(output_directory))
            rle_file = predict_images(preprocess_image_path, preprocessed_image_list_path, output_directory)

        # After processing all images, redirect to conversion page
        return redirect(f'/image/{uuids}/convert/')

    # Handle AJAX request to load images dynamically
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'images': [{'file_location': {'url': image.file_location.url}} for image in preview_images],
            'file_name': uploaded_image.name,
            'current_file_index': current_file_index,
        })

    # Render the template for standard (non-AJAX) requests
    return TemplateResponse(request, "pre-process.html", {
        'images': preview_images,
        'file_name': uploaded_image.name,
        'current_file_index': current_file_index,
        'total_files': total_files,
        'uuids': uuids,
    })