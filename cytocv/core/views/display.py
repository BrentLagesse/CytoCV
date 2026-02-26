from core.models import UploadedImage, SegmentedImage, CellStatistics
from core.tables import CellTable
from django.shortcuts import render
from pathlib import Path
from cytocv.settings import MEDIA_ROOT, MEDIA_URL
import json
from django.contrib.auth import get_user_model
import os
from django.http import HttpResponse, JsonResponse
from core.config import get_channel_config_for_uuid
from django_tables2.config import RequestConfig
from django_tables2.export.export import TableExport


def display_cell(request, uuids):
    """Render cell display data for one or more uploaded image UUIDs.

    Args:
        request: Incoming HTTP request.
        uuids: Comma-separated UUIDs for images to display.

    Returns:
        An HTML response with image previews and statistics, or an error.
    """
    # Split the comma-separated UUIDs into a list
    uuid_list = uuids.split(',')

    # Keep table output bound to the first UUID that has statistics.
    first_table_uuid = None

    # Dictionary to store data for all files (UUIDs)
    all_files_data = {}

    # List to store file information for sidebar navigation
    file_list = []
    cell_table = None
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
            image_index = 0

            if request.method == 'POST':
                if 'delete' in request.POST:
                    cell_id = request.POST.get('cell_id')
                    cell_image = SegmentedImage.objects.get(UUID=uuid)
                    delete_cell = CellStatistics.objects.get(segmented_image=cell_image,cell_id=cell_id)
                    delete_cell.delete()
                elif 'gfp' in request.POST:
                    image_index = 1
                elif 'mCherry' in request.POST:
                    image_index = 0
                elif 'dic' in request.POST:
                    image_index = 3
                else:
                    image_index = 2
            image_file_name = image_name_stem + "_frame_" + str(image_index)
            full_outlined = f"{MEDIA_URL}{uuid}/output/{image_file_name}.png"

            # Get the segmented image details
            cell_image = SegmentedImage.objects.get(UUID=uuid)

            if ((cell_image.user_id != request.user.id and request.user.id) or  # this is not your image OR
                    (not request.user.id and cell_image.user_id != get_user_model().objects.get(
                        email='guest@local.invalid').id)):  # you viewing your guest image
                print(cell_image.user_id)
                print(request.user.id)
                return HttpResponse('Unauthorized', status=401)

            channel_config = get_channel_config_for_uuid(uuid)

            # Build the images for each cell based on the dynamic channel configuration
            images = {}
            statistics = {}
            cell_stats_qs = CellStatistics.objects.filter(segmented_image=cell_image).order_by('cell_id')
            stats_by_id = {cell.cell_id: cell for cell in cell_stats_qs}
            if stats_by_id and first_table_uuid is None:
                first_table_uuid = uuid
                cell_table = CellTable(cell_stats_qs)
            if stats_by_id:
                cell_ids = list(stats_by_id.keys())
            else:
                segmented_dir = Path(MEDIA_ROOT) / str(uuid) / 'segmented'
                cell_ids = sorted(
                    int(path.stem.split('_', 1)[1])
                    for path in segmented_dir.glob('cell_*.png')
                    if path.stem.split('_', 1)[1].isdigit()
                )
            number_of_cells = len(cell_ids)
            no_cells_warning = None
            if number_of_cells == 0:
                no_cells_warning = (
                    'No segmented cells were produced for this file. '
                    'Check channel mapping (DIC/DAPI/mCherry/GFP) and try again.'
                )

            for i in cell_ids:
                images[str(i)] = []
                for channel_name in channel_order:
                    channel_index = channel_config.get(channel_name)
                    # For mCherry and GFP, use the debug filename pattern
                    no_outline = f"{MEDIA_URL}{uuid}/segmented/{image_name_stem}-{channel_index}-{i}-no_outline.png"
                    if channel_name in ["mCherry", "GFP", "DAPI"]:
                        image_url = f"{MEDIA_URL}{uuid}/segmented/{image_name_stem}-{i}-{channel_name}_debug.png"
                    else:
                        image_url = f"{MEDIA_URL}{uuid}/segmented/{image_name_stem}-{channel_index}-{i}.png"
                    images[str(i)].append(image_url)
                    images[str(i)].append(no_outline)

                # Retrieve statistics for the cell
                cell_stat = stats_by_id.get(i)
                if cell_stat:
                    statistics[str(i)] = {
                        'distance': cell_stat.distance,
                        'line_gfp_intensity': cell_stat.line_gfp_intensity,
                        'blue_contour_size': cell_stat.blue_contour_size,
                        'red_contour_1_size': cell_stat.red_contour_1_size,
                        'red_contour_2_size': cell_stat.red_contour_2_size,
                        'red_contour_3_size': cell_stat.red_contour_3_size,
                        'red_intensity_1': cell_stat.red_intensity_1,
                        'red_intensity_2': cell_stat.red_intensity_2,
                        'red_intensity_3': cell_stat.red_intensity_3,
                        'green_intensity_1': cell_stat.green_intensity_1,
                        'green_intensity_2': cell_stat.green_intensity_2,
                        'green_intensity_3': cell_stat.green_intensity_3,
                        'nucleus_intensity_sum': cell_stat.nucleus_intensity_sum,
                        'cellular_intensity_sum': cell_stat.cellular_intensity_sum,
                        'green_red_intensity_1': cell_stat.green_red_intensity_1,
                        'green_red_intensity_2': cell_stat.green_red_intensity_2,
                        'green_red_intensity_3': cell_stat.green_red_intensity_3,
                        'cytoplasmic_intensity': cell_stat.cytoplasmic_intensity,
                        'cellular_intensity_sum_DAPI': cell_stat.cellular_intensity_sum_DAPI,
                        'nucleus_intensity_sum_DAPI': cell_stat.nucleus_intensity_sum_DAPI,
                        'cytoplasmic_intensity_DAPI': cell_stat.cytoplasmic_intensity_DAPI,
                        'category_GFP_dot': cell_stat.category_GFP_dot,
                        'biorientation': cell_stat.biorientation,
                    }
                else:
                    statistics[str(i)] = None  # In case statistics are missing for a cell

            export_format = request.GET.get('_export', None)
            if TableExport.is_valid_format(export_format) and cell_table is not None:
                exporter = TableExport(export_format,cell_table)
                return exporter.response(f"table.{export_format}")

            # Store all image details and statistics for this UUID
            all_files_data[str(uuid)] = {
                'MainImagePath': full_outlined,
                'NumberOfCells': number_of_cells,
                'CellPairImages': images,
                'Image_Name': image_name,
                'Statistics': statistics,
                'NoCellsWarning': no_cells_warning,
            }

        except UploadedImage.DoesNotExist:
            return HttpResponse(f"Uploaded image not found for UUID {uuid}", status=404)
        except SegmentedImage.DoesNotExist:
            return HttpResponse(f"Segmented image not found for UUID {uuid}", status=404)

    if cell_table is None:
        cell_table = CellTable(CellStatistics.objects.none())

    # Convert the files_data to JSON to be used in the template
    json_files_data = json.dumps(all_files_data)

    return render(request, "display_cell.html", {
        'files_data': json_files_data,  # Pass all file data to the template
        'file_list': file_list,  # Pass sidebar file list data to the template
        'cell_table': cell_table,
        'table_uuid': first_table_uuid or '',
    })


def main_image_channel(request, uuid):
    """Return the main image URL for a given channel without a full page reload."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    channel = (request.GET.get('channel') or '').strip().lower()
    channel_map = {
        'mcherry': 0,
        'gfp': 1,
        'dapi': 2,
        'dic': 3,
    }
    if channel not in channel_map:
        return JsonResponse({'error': 'Unknown channel'}, status=400)

    try:
        uploaded_image = UploadedImage.objects.get(uuid=uuid)
    except UploadedImage.DoesNotExist:
        return JsonResponse({'error': 'Uploaded image not found'}, status=404)

    try:
        cell_image = SegmentedImage.objects.get(UUID=uuid)
    except SegmentedImage.DoesNotExist:
        return JsonResponse({'error': 'Segmented image not found'}, status=404)

    if ((cell_image.user_id != request.user.id and request.user.id) or
            (not request.user.id and cell_image.user_id != get_user_model().objects.get(
                email='guest@local.invalid').id)):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    image_name_stem = Path(uploaded_image.name).stem
    image_index = channel_map[channel]
    image_file_name = f"{image_name_stem}_frame_{image_index}"
    full_outlined = f"{MEDIA_URL}{uuid}/output/{image_file_name}.png"

    return JsonResponse({
        'image_url': full_outlined,
        'channel': channel,
    })
