from core.models import UploadedImage, SegmentedImage, CellStatistics, get_guest_user
from core.tables import CellTable
from django.shortcuts import render
from pathlib import Path
from cytocv.settings import MEDIA_ROOT, MEDIA_URL
import json
import math
import re
from django.http import HttpResponse, JsonResponse
from core.config import get_channel_config_for_uuid
from django_tables2.export.export import TableExport


def _resolve_nuclear_cellular_mode(stats_iterable):
    modes = set()
    for stat in stats_iterable:
        props = stat.properties or {}
        mode = props.get("nuclear_cellular_mode")
        if mode in {"green_nucleus", "red_nucleus"}:
            modes.add(mode)
    return modes.pop() if len(modes) == 1 else None


def _sanitize_for_json(value):
    """Convert nested values to strict JSON-safe equivalents."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_for_json(item) for item in value]
    return value


def _scan_output_frames(uuid: str):
    output_dir = Path(MEDIA_ROOT) / str(uuid) / "output"
    frames = {}
    if not output_dir.exists():
        return frames
    frame_pattern = re.compile(r"^.+_frame_(\d+)\.png$")
    for path in output_dir.glob("*_frame_*.png"):
        match = frame_pattern.match(path.name)
        if not match:
            continue
        frame_idx = int(match.group(1))
        frames[frame_idx] = f"{MEDIA_URL}{uuid}/output/{path.name}"
    return frames


def _current_transient_uuid_set(request):
    return {
        str(value)
        for value in request.session.get("transient_experiment_uuids", [])
        if str(value)
    }


def _can_access_display_uuid(request, uploaded_image, segmented_image) -> bool:
    if request.user.is_authenticated:
        if uploaded_image.user_id != request.user.id:
            return False
        if segmented_image.user_id == request.user.id:
            return True
        return (
            segmented_image.user_id == get_guest_user()
            and str(uploaded_image.uuid) in _current_transient_uuid_set(request)
        )

    guest_id = get_guest_user()
    return uploaded_image.user_id == guest_id and segmented_image.user_id == guest_id


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
            cell_image = SegmentedImage.objects.get(UUID=uuid)
            if not _can_access_display_uuid(request, uploaded_image, cell_image):
                return HttpResponse('Unauthorized', status=401)
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

            # Build the images for each cell based on the dynamic channel configuration
            images = {}
            statistics = {}
            cell_stats_qs = CellStatistics.objects.filter(segmented_image=cell_image).order_by('cell_id')
            stats_by_id = {cell.cell_id: cell for cell in cell_stats_qs}
            if stats_by_id and first_table_uuid is None:
                first_table_uuid = uuid
                table_mode = _resolve_nuclear_cellular_mode(stats_by_id.values())
                cell_table = CellTable(cell_stats_qs, intensity_mode=table_mode)
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
                        'red_in_green_intensity_1': cell_stat.red_in_green_intensity_1,
                        'red_in_green_intensity_2': cell_stat.red_in_green_intensity_2,
                        'red_in_green_intensity_3': cell_stat.red_in_green_intensity_3,
                        'green_in_green_intensity_1': cell_stat.green_in_green_intensity_1,
                        'green_in_green_intensity_2': cell_stat.green_in_green_intensity_2,
                        'green_in_green_intensity_3': cell_stat.green_in_green_intensity_3,
                        'gfp_contour_1_size': cell_stat.gfp_contour_1_size,
                        'gfp_contour_2_size': cell_stat.gfp_contour_2_size,
                        'gfp_contour_3_size': cell_stat.gfp_contour_3_size,
                        'gfp_to_mcherry_distance_1': cell_stat.gfp_to_mcherry_distance_1,
                        'gfp_to_mcherry_distance_2': cell_stat.gfp_to_mcherry_distance_2,
                        'gfp_to_mcherry_distance_3': cell_stat.gfp_to_mcherry_distance_3,
                        'nucleus_intensity_sum': cell_stat.nucleus_intensity_sum,
                        'cellular_intensity_sum': cell_stat.cellular_intensity_sum,
                        'green_red_intensity_1': cell_stat.green_red_intensity_1,
                        'green_red_intensity_2': cell_stat.green_red_intensity_2,
                        'green_red_intensity_3': cell_stat.green_red_intensity_3,
                        'cytoplasmic_intensity': cell_stat.cytoplasmic_intensity,
                        'cellular_intensity_sum_DAPI': cell_stat.cellular_intensity_sum_DAPI,
                        'nucleus_intensity_sum_DAPI': cell_stat.nucleus_intensity_sum_DAPI,
                        'cytoplasmic_intensity_DAPI': cell_stat.cytoplasmic_intensity_DAPI,
                        'nuclear_cellular_mode': (cell_stat.properties or {}).get("nuclear_cellular_mode", "green_nucleus"),
                        'nuclear_cellular_contour_channel': (cell_stat.properties or {}).get(
                            "nuclear_cellular_contour_channel",
                            "GFP",
                        ),
                        'nuclear_cellular_measurement_channel': (cell_stat.properties or {}).get(
                            "nuclear_cellular_measurement_channel",
                            "mCherry",
                        ),
                        'nuclear_cellular_status': (cell_stat.properties or {}).get(
                            "nuclear_cellular_status",
                            "unknown",
                        ),
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
        cell_table = CellTable(CellStatistics.objects.none(), intensity_mode=None)

    # Convert the files_data to JSON to be used in the template
    json_files_data = json.dumps(_sanitize_for_json(all_files_data), allow_nan=False)

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
    channel_to_config_key = {
        'mcherry': 'mCherry',
        'gfp': 'GFP',
        'dapi': 'DAPI',
        'dic': 'DIC',
    }
    fallback_frame_map = {
        'mcherry': 0,
        'gfp': 1,
        'dapi': 2,
        'dic': 3,
    }
    if channel not in channel_to_config_key:
        return JsonResponse({'error': 'Unknown channel'}, status=400)

    try:
        uploaded_image = UploadedImage.objects.get(uuid=uuid)
    except UploadedImage.DoesNotExist:
        return JsonResponse({'error': 'Uploaded image not found'}, status=404)

    try:
        cell_image = SegmentedImage.objects.get(UUID=uuid)
    except SegmentedImage.DoesNotExist:
        return JsonResponse({'error': 'Segmented image not found'}, status=404)

    if not _can_access_display_uuid(request, uploaded_image, cell_image):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    channel_config = get_channel_config_for_uuid(str(uuid))
    configured_frame_idx = channel_config.get(
        channel_to_config_key[channel],
        fallback_frame_map[channel],
    )
    available_frames = _scan_output_frames(str(uuid))
    full_outlined = available_frames.get(configured_frame_idx)
    if not full_outlined:
        full_outlined = available_frames.get(fallback_frame_map[channel])
    if not full_outlined and available_frames:
        first_idx = sorted(available_frames.keys())[0]
        full_outlined = available_frames[first_idx]
    if not full_outlined:
        image_name_stem = Path(uploaded_image.name).stem
        image_file_name = f"{image_name_stem}_frame_{fallback_frame_map[channel]}"
        full_outlined = f"{MEDIA_URL}{uuid}/output/{image_file_name}.png"

    return JsonResponse({
        'image_url': full_outlined,
        'channel': channel,
    })
