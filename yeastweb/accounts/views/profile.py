"""Profile view for displaying user data and recent analysis results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

from core.config import DEFAULT_CHANNEL_CONFIG
from core.models import SegmentedImage, UploadedImage
from yeastweb.settings import MEDIA_URL
from .cache import get_cache_image


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """Render the profile page with user stats and latest analysis."""
    first_name = request.user.first_name
    last_name = request.user.last_name
    email = request.user.email

    available_storage = request.user.available_storage
    used_storage = request.user.used_storage
    total_storage = request.user.total_storage
    percentage_used = used_storage / total_storage * 100

    user_id = request.user.id
    images_saved = []
    for image in SegmentedImage.objects.filter(user=user_id).order_by("-uploaded_date"):
        image_id = image.UUID
        image_name = UploadedImage.objects.get(uuid=image_id).name
        images_saved.append(
            dict(
                id=image.UUID,
                name=image_name,
                date=image.uploaded_date,
                cell=image.NumCells,
            )
        )


    # Everything down here is cache session
    recent = get_cache_image(user_id)

    if not recent:
        return TemplateResponse(
            request,
            "profile.html",
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "available_storage": available_storage,
                "used_storage": used_storage,
                "percentage_used": percentage_used,
                "total_storage": total_storage,
            },
        )

    all_files_data: dict[str, Any] = {}
    channel_order = ["DIC", "DAPI", "mCherry", "GFP"]

    uploaded_image = recent["uploaded"]
    uuid = uploaded_image.uuid
    image_name = uploaded_image.name
    image_name_stem = Path(image_name).stem
    image_file_name = image_name_stem + "_frame_" + "0"
    full_outlined = f"{MEDIA_URL}{uuid}/output/{image_file_name}.png"

    cell_image = recent["segmented"]

    images = {}
    statistics = {}
    for i in range(1, cell_image.NumCells + 1):
        images[str(i)] = []
        for channel_name in channel_order:
            channel_index = DEFAULT_CHANNEL_CONFIG.get(channel_name)
            # For mCherry and GFP, use the debug filename pattern
            if channel_name in ["mCherry", "GFP"]:
                image_url = f"{MEDIA_URL}{uuid}/segmented/{image_name_stem}-{i}-{channel_name}_debug.png"
            else:
                image_url = f"{MEDIA_URL}{uuid}/segmented/{image_name_stem}-{channel_index}-{i}.png"
            images[str(i)].append(image_url)

        try:
            cell_stat = recent["cell"][i]
            print(cell_stat)
            statistics[str(i)] = {
                "distance": cell_stat.distance,
                "line_gfp_intensity": cell_stat.line_gfp_intensity,
                "nucleus_intensity_sum": cell_stat.nucleus_intensity_sum,
                "cellular_intensity_sum": cell_stat.cellular_intensity_sum,
                "green_red_intensity": cell_stat.green_red_intensity,
                "cytoplasmic_intensity": cell_stat.cytoplasmic_intensity,
                "cellular_intensity_sum_DAPI": cell_stat.cellular_intensity_sum_DAPI,
                "nucleus_intensity_sum_DAPI": cell_stat.nucleus_intensity_sum_DAPI,
                "cytoplasmic_intensity_DAPI": cell_stat.cytoplasmic_intensity_DAPI,
            }
        except Exception:
            statistics[str(i)] = None


    all_files_data[str(uuid)] = {
        "MainImagePath": full_outlined,
        "NumberOfCells": cell_image.NumCells,
        "CellPairImages": images,
        "Image_Name": image_name,
        "Statistics": statistics,
    }

    json_files_data = json.dumps(all_files_data)

    return TemplateResponse(
        request,
        "profile.html",
        {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "available_storage": available_storage,
            "used_storage": used_storage,
            "percentage_used": percentage_used,
            "total_storage": total_storage,
            "images": images_saved,
            "files_data": json_files_data,
        },
    )



