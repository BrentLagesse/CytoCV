import json
import math
import re
from pathlib import Path
from uuid import UUID

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from accounts.preferences import get_user_preferences
from core.config import get_channel_config_for_uuid
from core.models import UploadedImage, SegmentedImage, CellStatistics, get_guest_user
from core.tables import CellTable
from cytocv.settings import MEDIA_ROOT, MEDIA_URL
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


def _normalize_uuid_list(raw_values):
    if not isinstance(raw_values, list):
        return []
    normalized = []
    seen = set()
    for value in raw_values:
        try:
            value_uuid = str(UUID(str(value)))
        except (TypeError, ValueError, AttributeError):
            return []
        if value_uuid in seen:
            continue
        seen.add(value_uuid)
        normalized.append(value_uuid)
    return normalized


def _media_path_size(path: Path):
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return int(path.stat().st_size)
        except OSError:
            return 0

    total = 0
    try:
        for candidate in path.rglob("*"):
            if not candidate.is_file():
                continue
            try:
                total += int(candidate.stat().st_size)
            except OSError:
                continue
    except OSError:
        return total
    return total


def _recalculate_user_storage_usage(user):
    if not getattr(user, "is_authenticated", False):
        return
    saved_uuids = {
        str(value)
        for value in SegmentedImage.objects.filter(user=user).values_list("UUID", flat=True)
    }
    media_root = Path(MEDIA_ROOT)
    used_storage = 0
    for uuid_value in saved_uuids:
        used_storage += _media_path_size(media_root / uuid_value)
        used_storage += _media_path_size(media_root / f"user_{uuid_value}")

    total_storage = max(int(getattr(user, "total_storage", 0) or 0), 0)
    user.used_storage = max(0, int(used_storage))
    user.available_storage = max(0, int(total_storage - user.used_storage))
    user.save(update_fields=["used_storage", "available_storage"])


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
    uuid_list = [value for value in uuids.split(',') if value]

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

    preferences = get_user_preferences(request.user)
    show_saved_file_channels = bool(preferences.get("show_saved_file_channels", True))

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
                'uploaded_date': cell_image.uploaded_date,
                'num_cells': int(cell_image.NumCells or 0),
                'is_saved': bool(request.user.is_authenticated and cell_image.user_id == request.user.id),
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
        'show_saved_file_channels': show_saved_file_channels,
    })


@require_POST
def save_display_files(request):
    """Persist selected display files to account history."""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request payload."}, status=400)

    requested_uuids = _normalize_uuid_list(payload.get("uuids", []))
    if not requested_uuids:
        return JsonResponse({"error": "No valid files were selected."}, status=400)

    uploaded_map = {
        str(item.uuid): item
        for item in UploadedImage.objects.filter(
            user=request.user,
            uuid__in=requested_uuids,
        )
    }
    if len(uploaded_map) != len(set(requested_uuids)):
        return JsonResponse(
            {"error": "One or more selected files are unavailable."},
            status=403,
        )

    segmented_map = {
        str(item.UUID): item
        for item in SegmentedImage.objects.filter(UUID__in=requested_uuids)
    }
    if len(segmented_map) != len(set(requested_uuids)):
        return JsonResponse(
            {"error": "One or more selected files are unavailable."},
            status=403,
        )

    transient_uuids = _current_transient_uuid_set(request)
    guest_id = get_guest_user()
    already_saved = []
    to_save = []
    for uuid in requested_uuids:
        segmented = segmented_map.get(uuid)
        if segmented is None:
            return JsonResponse(
                {"error": "One or more selected files are unavailable."},
                status=403,
            )
        if segmented.user_id == request.user.id:
            already_saved.append(uuid)
            continue
        if segmented.user_id == guest_id and uuid in transient_uuids:
            to_save.append(uuid)
            continue
        return JsonResponse(
            {"error": "One or more selected files are unavailable."},
            status=403,
        )

    if to_save:
        with transaction.atomic():
            SegmentedImage.objects.filter(UUID__in=to_save, user_id=guest_id).update(
                user=request.user
            )

    if to_save:
        transient_uuids.difference_update(to_save)
        request.session["transient_experiment_uuids"] = sorted(transient_uuids)

    _recalculate_user_storage_usage(request.user)
    saved_file_count = SegmentedImage.objects.filter(user=request.user).count()
    total_storage = max(int(getattr(request.user, "total_storage", 0) or 0), 1)
    used_storage = max(int(getattr(request.user, "used_storage", 0) or 0), 0)

    return JsonResponse(
        {
            "saved_count": len(to_save),
            "already_saved_count": len(already_saved),
            "saved_uuids": to_save,
            "already_saved_uuids": already_saved,
            "saved_file_count": saved_file_count,
            "used_storage_mb": round(used_storage / (1024 * 1024), 3),
            "storage_percentage": round(min(100, max(0, (used_storage / total_storage) * 100)), 2),
        }
    )


@require_POST
def unsave_display_files(request):
    """Remove selected files from account-saved history for the current session."""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request payload."}, status=400)

    requested_uuids = _normalize_uuid_list(payload.get("uuids", []))
    if not requested_uuids:
        return JsonResponse({"error": "No valid files were selected."}, status=400)

    uploaded_map = {
        str(item.uuid): item
        for item in UploadedImage.objects.filter(
            user=request.user,
            uuid__in=requested_uuids,
        )
    }
    if len(uploaded_map) != len(set(requested_uuids)):
        return JsonResponse(
            {"error": "One or more selected files are unavailable."},
            status=403,
        )

    segmented_map = {
        str(item.UUID): item
        for item in SegmentedImage.objects.filter(UUID__in=requested_uuids)
    }
    if len(segmented_map) != len(set(requested_uuids)):
        return JsonResponse(
            {"error": "One or more selected files are unavailable."},
            status=403,
        )

    transient_uuids = _current_transient_uuid_set(request)
    guest_id = get_guest_user()
    already_unsaved = []
    to_unsave = []
    for uuid in requested_uuids:
        segmented = segmented_map.get(uuid)
        if segmented is None:
            return JsonResponse(
                {"error": "One or more selected files are unavailable."},
                status=403,
            )
        if segmented.user_id == request.user.id:
            to_unsave.append(uuid)
            continue
        if segmented.user_id == guest_id and uuid in transient_uuids:
            already_unsaved.append(uuid)
            continue
        return JsonResponse(
            {"error": "One or more selected files are unavailable."},
            status=403,
        )

    if to_unsave:
        with transaction.atomic():
            SegmentedImage.objects.filter(
                UUID__in=to_unsave,
                user=request.user,
            ).update(user_id=guest_id)

    if to_unsave:
        transient_uuids.update(to_unsave)
        request.session["transient_experiment_uuids"] = sorted(transient_uuids)

    _recalculate_user_storage_usage(request.user)
    saved_file_count = SegmentedImage.objects.filter(user=request.user).count()
    total_storage = max(int(getattr(request.user, "total_storage", 0) or 0), 1)
    used_storage = max(int(getattr(request.user, "used_storage", 0) or 0), 0)

    return JsonResponse(
        {
            "unsaved_count": len(to_unsave),
            "already_unsaved_count": len(already_unsaved),
            "unsaved_uuids": to_unsave,
            "already_unsaved_uuids": already_unsaved,
            "saved_file_count": saved_file_count,
            "used_storage_mb": round(used_storage / (1024 * 1024), 3),
            "storage_percentage": round(min(100, max(0, (used_storage / total_storage) * 100)), 2),
        }
    )


@require_POST
def sync_display_file_selection(request):
    """Apply display selection state: selected => saved, unselected => unsaved."""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request payload."}, status=400)

    visible_uuids = _normalize_uuid_list(payload.get("visible_uuids", []))
    selected_uuids = _normalize_uuid_list(payload.get("selected_uuids", []))
    if not visible_uuids:
        return JsonResponse({"error": "No valid files were provided."}, status=400)

    visible_set = set(visible_uuids)
    selected_set = set(selected_uuids)
    if not selected_set.issubset(visible_set):
        return JsonResponse(
            {"error": "Selected files must be part of the current display list."},
            status=400,
        )

    uploaded_map = {
        str(item.uuid): item
        for item in UploadedImage.objects.filter(
            user=request.user,
            uuid__in=visible_uuids,
        )
    }
    if len(uploaded_map) != len(visible_set):
        return JsonResponse(
            {"error": "One or more selected files are unavailable."},
            status=403,
        )

    segmented_map = {
        str(item.UUID): item
        for item in SegmentedImage.objects.filter(UUID__in=visible_uuids)
    }
    if len(segmented_map) != len(visible_set):
        return JsonResponse(
            {"error": "One or more selected files are unavailable."},
            status=403,
        )

    transient_uuids = _current_transient_uuid_set(request)
    guest_id = get_guest_user()
    current_saved = set()
    for uuid in visible_uuids:
        segmented = segmented_map.get(uuid)
        if segmented is None:
            return JsonResponse(
                {"error": "One or more selected files are unavailable."},
                status=403,
            )
        if segmented.user_id == request.user.id:
            current_saved.add(uuid)
            continue
        if segmented.user_id == guest_id and uuid in transient_uuids:
            continue
        return JsonResponse(
            {"error": "One or more selected files are unavailable."},
            status=403,
        )

    to_save = sorted(selected_set.difference(current_saved))
    to_unsave = sorted(current_saved.difference(selected_set))

    with transaction.atomic():
        if to_save:
            SegmentedImage.objects.filter(UUID__in=to_save, user_id=guest_id).update(
                user=request.user
            )
        if to_unsave:
            SegmentedImage.objects.filter(UUID__in=to_unsave, user=request.user).update(
                user_id=guest_id
            )

    if to_save or to_unsave:
        transient_uuids.difference_update(to_save)
        transient_uuids.update(to_unsave)
        request.session["transient_experiment_uuids"] = sorted(transient_uuids)

    _recalculate_user_storage_usage(request.user)
    saved_file_count = SegmentedImage.objects.filter(user=request.user).count()
    total_storage = max(int(getattr(request.user, "total_storage", 0) or 0), 1)
    used_storage = max(int(getattr(request.user, "used_storage", 0) or 0), 0)

    return JsonResponse(
        {
            "saved_count": len(to_save),
            "unsaved_count": len(to_unsave),
            "saved_uuids": to_save,
            "unsaved_uuids": to_unsave,
            "saved_file_count": saved_file_count,
            "used_storage_mb": round(used_storage / (1024 * 1024), 3),
            "storage_percentage": round(min(100, max(0, (used_storage / total_storage) * 100)), 2),
        }
    )


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
