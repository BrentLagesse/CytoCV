from core.models import UploadedImage, SegmentedImage
from django.shortcuts import render
from pathlib import Path
from yeastweb.settings import MEDIA_URL
import json
import os

def display_cell(request, uuid):
    # Get the uploaded image details, including the file name
    uploaded_image = UploadedImage.objects.get(pk=uuid)
    image_name = uploaded_image.name 
    full_outlined = f"{MEDIA_URL}{uuid}/output/{image_name}.png"
    cell_image = SegmentedImage.objects.get(pk=uuid)
    
    # Dictionary to store the cell images across different channels (0, 1, 2, 3)
    images = {}

    # Example hardcoded values
    distance = 1
    nucleus_intensity_sum = 1
    line_gfp_intensity = 1
    cellular_intensity_sum = 1

    # For each cell, generate image URLs for the four different channels
    for i in range(1, cell_image.NumCells + 1):
        images[str(i)] = []
        for channel in range(4):  # Channels 0-3
            image_url = f"{MEDIA_URL}{uuid}/segmented/{image_name}-{channel}-{i}.png"
            images[str(i)].append(image_url)

    # Convert the images dictionary to JSON to be used in JavaScript
    json_images = json.dumps(images)

    # Pass the images and other information to the template
    content = {
        'MainImagePath': full_outlined,
        'NumberOfCells': cell_image.NumCells,
        'CellPairImages': json_images,
        'Image_Name': image_name,
        'distance': distance,  
        'nucleus_intensity_sum': nucleus_intensity_sum, 
        'line_gfp_intensity': line_gfp_intensity, 
        'cellular_intensity_sum': cellular_intensity_sum  
    }

    return render(request, "display_cell.html", content)
