from core.models import UploadedImage, SegmentedImage
from django.shortcuts import render
from pathlib import Path
from yeastweb.settings import MEDIA_URL
import json
import os

from django.http import HttpResponse

def display_cell(request, uuids):
    # Split the comma-separated UUIDs into a list
    uuid_list = uuids.split(',')

    # Dictionary to store data for all files (UUIDs)
    all_files_data = {}

    # Loop through each UUID and retrieve associated data
    for uuid in uuid_list:
        try:
            # Get the uploaded image details, including the file name
            uploaded_image = UploadedImage.objects.get(uuid=uuid)
            image_name = uploaded_image.name
            image_name_stem = Path(image_name).stem
            full_outlined = f"{MEDIA_URL}{uuid}/output/{image_name_stem}.png"
            
            # Get the segmented image details
            cell_image = SegmentedImage.objects.get(UUID=uuid)

            # Store the images for each cell across 4 channels
            images = {}
            for i in range(1, cell_image.NumCells + 1):
                images[str(i)] = []
                for channel in range(4):
                    image_url = f"{MEDIA_URL}{uuid}/segmented/{image_name_stem}-{channel}-{i}.png"
                    images[str(i)].append(image_url)

            # Store all image details for this UUID
            all_files_data[str(uuid)] = {
                'MainImagePath': full_outlined,
                'NumberOfCells': cell_image.NumCells,
                'CellPairImages': images,
                'Image_Name': image_name
            }

        except UploadedImage.DoesNotExist:
            return HttpResponse(f"Uploaded image not found for UUID {uuid}", status=404)
        except SegmentedImage.DoesNotExist:
            return HttpResponse(f"Segmented image not found for UUID {uuid}", status=404)

    # Convert the files_data to JSON to be used in the template
    json_files_data = json.dumps(all_files_data)

    return render(request, "display_cell.html", {
        'files_data': json_files_data  # Pass all file data to the template
    })