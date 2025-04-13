from core.models import UploadedImage, SegmentedImage, CellStatistics
from django.shortcuts import render
from pathlib import Path
from yeastweb.settings import MEDIA_URL
import json
from django.contrib.auth import get_user_model
import os
from django.http import HttpResponse
from core.config import get_channel_config_for_uuid

def display_cell(request, uuids):
    # Split the comma-separated UUIDs into a list
    uuid_list = uuids.split(',')

    # Dictionary to store data for all files (UUIDs)
    all_files_data = {}

    # List to store file information for sidebar navigation
    file_list = []

    # Define the channel order that matches your HTML template:
    # Order: DIC, DAPI, mCherry, GFP
    channel_order = ["DIC", "DAPI", "mCherry", "GFP"]

    # Loop through each UUID and retrieve associated data
    for uuid in uuid_list:
        try:
            # Get the uploaded image details, including the file name
            uploaded_image = UploadedImage.objects.get(uuid=uuid)
            image_name = uploaded_image.name
            # get your channel-to-index mapping
            channel_config = get_channel_config_for_uuid(uuid)
            # sort by the saved index → this yields e.g. ["DIC","DAPI","mCherry","GFP"]
            detected = [ch for ch, _ in sorted(channel_config.items(), key=lambda t: t[1])]

            # Append file info for the sidebar, INCLUDING the channel pills
            file_list.append({
                'uuid': uuid,
                'name': image_name,
                'detected_channels': detected,
            })
            image_name_stem = Path(image_name).stem
            full_outlined = f"{MEDIA_URL}{uuid}/output/{image_name_stem}.png"
            
            # Get the segmented image details
            cell_image = SegmentedImage.objects.get(UUID=uuid)

            if ((cell_image.user_id != request.user.id and request.user.id) or # this is not your image OR
                    (not request.user.id and cell_image.user_id != get_user_model().objects.get(username='guest').id)): # you viewing your guest image
                print(cell_image.user_id)
                print(request.user.id)
                return HttpResponse('Unauthorized', status=401)


            channel_config = get_channel_config_for_uuid(uuid)

            # Build the images for each cell based on the dynamic channel configuration
            images = {}
            statistics = {}
            for i in range(1, cell_image.NumCells + 1):
                images[str(i)] = []
                for channel_name in channel_order:
                    channel_index = channel_config.get(channel_name)
                    # For mCherry and GFP, use the debug filename pattern
                    if channel_name in ["mCherry", "GFP"]:
                        image_url = f"{MEDIA_URL}{uuid}/segmented/{image_name_stem}-{i}-{channel_name}_debug.png"
                    else:
                        image_url = f"{MEDIA_URL}{uuid}/segmented/{image_name_stem}-{channel_index}-{i}.png"
                    images[str(i)].append(image_url)
                
                # Retrieve statistics for the cell
                try:
                    cell_stat = CellStatistics.objects.get(segmented_image=cell_image, cell_id=i)
                    statistics[str(i)] = {
                        'distance': cell_stat.distance,
                        'line_gfp_intensity': cell_stat.line_gfp_intensity,
                        'nucleus_intensity_sum': cell_stat.nucleus_intensity_sum,
                        'cellular_intensity_sum': cell_stat.cellular_intensity_sum,
                    }
                except CellStatistics.DoesNotExist:
                    statistics[str(i)] = None  # In case statistics are missing for a cell

            # Store all image details and statistics for this UUID
            all_files_data[str(uuid)] = {
                'MainImagePath': full_outlined,
                'NumberOfCells': cell_image.NumCells,
                'CellPairImages': images,
                'Image_Name': image_name,
                'Statistics': statistics
            }

        except UploadedImage.DoesNotExist:
            return HttpResponse(f"Uploaded image not found for UUID {uuid}", status=404)
        except SegmentedImage.DoesNotExist:
            return HttpResponse(f"Segmented image not found for UUID {uuid}", status=404)

    # Convert the files_data to JSON to be used in the template
    json_files_data = json.dumps(all_files_data)

    return render(request, "display_cell.html", {
        'files_data': json_files_data,  # Pass all file data to the template
        'file_list': file_list,         # Pass sidebar file list data to the template
    })
