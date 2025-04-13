from django.contrib.auth.models import User
from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from core.models import SegmentedImage, UploadedImage
from .cache import get_cache_image
import json
from core.config import DEFAULT_CHANNEL_CONFIG  # Import your channel configuration
from yeastweb.settings import MEDIA_URL
from pathlib import Path


@login_required
def profile_view(request):
    username = request.user.username
    first_name = request.user.first_name
    last_name = request.user.last_name
    email = request.user.email

    available_storage = request.user.available_storage
    used_storage = request.user.used_storage
    total_storage = request.user.total_storage
    percentage_used = used_storage / total_storage * 100

    user_id = request.user.id
    images_saved = []; # use to hold images' uuid
    for image in SegmentedImage.objects.filter(user=user_id):
        image_id = image.UUID
        image_name = UploadedImage.objects.get(uuid=image_id).name
        images_saved.append(dict(id=image.UUID, name=image_name,date=image.uploaded_date,cell=image.NumCells))


    # Everything down here is cache session
    recent = get_cache_image(user_id)

    if not recent:
        return TemplateResponse(request, "profile.html", {"username": username, "first_name": first_name,
                                                          "last_name": last_name, "email": email,
                                                          "available_storage": available_storage,
                                                          "used_storage": used_storage,
                                                          "percentage_used": percentage_used,
                                                          "total_storage": total_storage})
    # Dictionary to store data for all files (UUIDs)
    all_files_data = {}

    # Define the channel order that matches your HTML template:
    # Order: DIC, DAPI, mCherry, GFP
    channel_order = ["DIC", "DAPI", "mCherry", "GFP"]

    uploaded_image = recent['uploaded']
    uuid = uploaded_image.uuid
    image_name = uploaded_image.name
    image_name_stem = Path(image_name).stem
    full_outlined = f"{MEDIA_URL}{uuid}/output/{image_name_stem}.png"

    # Get the segmented image details
    cell_image = recent['segmented']

    # Build the images for each cell based on the dynamic channel configuration
    images = {}
    statistics = {}
    for i in range(0, cell_image.NumCells - 1):
        images[str(i)] = []
        for channel_name in channel_order:
            channel_index = DEFAULT_CHANNEL_CONFIG.get(channel_name)
            # For mCherry and GFP, use the debug filename pattern
            if channel_name in ["mCherry", "GFP"]:
                image_url = f"{MEDIA_URL}{uuid}/segmented/{image_name_stem}-{i}-{channel_name}_debug.png"
            else:
                image_url = f"{MEDIA_URL}{uuid}/segmented/{image_name_stem}-{channel_index}-{i}.png"
            images[str(i)].append(image_url)

        # Retrieve statistics for the cell
        cell_stat = recent['cell'][i]
        statistics[str(i)] = {
            'distance': cell_stat.distance,
            'line_gfp_intensity': cell_stat.line_gfp_intensity,
            'nucleus_intensity_sum': cell_stat.nucleus_intensity_sum,
            'cellular_intensity_sum': cell_stat.cellular_intensity_sum,
        }


    # Store all image details and statistics for this UUID
    all_files_data[str(uuid)] = {
        'MainImagePath': full_outlined,
        'NumberOfCells': cell_image.NumCells,
        'CellPairImages': images,
        'Image_Name': image_name,
        'Statistics': statistics
    }

    # Convert the files_data to JSON to be used in the template
    json_files_data = json.dumps(all_files_data)

    return TemplateResponse(request,"profile.html",{"username":username,"first_name":first_name,
                                                    "last_name":last_name,"email":email,"available_storage":available_storage,
                                                    "used_storage":used_storage, "percentage_used":percentage_used,
                                                    "total_storage":total_storage, "images":images_saved, 'files_data': json_files_data})




