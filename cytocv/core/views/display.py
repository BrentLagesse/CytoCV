"""Transient Display views, saved-state sync, cell deletion, and exports."""

import json
import re
from pathlib import Path

from django.db import transaction
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    JsonResponse,
)
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.preferences import (
    get_user_preferences,
    normalize_main_image_channel,
    resolve_initial_puncta_source_contour_count_filter,
)
from core.cell_types import (
    filter_statistics_by_cell_type,
    normalize_cell_type_filter,
    resolve_effective_cell_type_filter,
)
from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
    channel_role_from_slug,
)
from core.config import get_channel_config_for_uuid
from core.models import (
    UploadedImage,
    SegmentedImage,
    CellStatistics,
    get_guest_user,
)
from core.services.artifact_storage import (
    StorageQuotaExceeded,
    assert_user_can_save_runs,
    log_storage_capacity_failure,
    refresh_user_storage_usage,
    sweep_user_run_artifacts,
)
from core.services.cell_deletion import delete_multiple_cells, delete_single_cell
from core.services.cell_statistics_payload import serialize_cell_statistics_payload
from core.services.combined_stat_export import (
    CombinedStatisticsExportError,
    build_combined_statistics_export_response,
)
from core.services.export_filenames import (
    build_statistics_export_filename,
)
from core.services.artifact_paths import (
    media_url,
    output_frame_url,
    segmented_cell_image_url,
)
from core.services.main_image_urls import build_main_image_paths
from core.services.channel_presence import get_channel_presence
from core.services.overlay_rendering import (
    build_overlay_image_url,
    build_overlay_layer_contract,
    overlay_image_available,
)
from core.services.result_view_payloads import (
    RESULT_CHANNEL_ORDER,
    channel_config_payload,
    detected_channel_labels,
    resolve_cell_table_modes,
    sanitize_for_json,
)
from core.services.puncta_source_contour_count_filter import (
    filter_statistics_by_puncta_source_contour_count,
    resolve_effective_puncta_source_contour_count_filter,
)
from core.services.stat_export_selection import (
    ExportColumnSelectionError,
    export_exclude_columns,
    export_metric_scope,
    export_selection_config,
)
from core.services.stat_export_requests import (
    build_statistics_export_sources,
    normalize_uuid_list,
)
from core.scale import (
    get_scale_context_payload,
    get_scale_sidebar_payload,
    normalize_spatial_stats_unit,
)
from core.tables import CellTable
from cytocv.settings import MEDIA_ROOT
from django_tables2.export.export import TableExport


def _scan_output_frames(uuid: str):
    """Return available full-frame output URLs keyed by channel frame index."""

    output_dir = Path(MEDIA_ROOT) / str(uuid) / "output"
    frames = {}
    if not output_dir.exists():
        return frames
    frame_pattern = re.compile(r"^.+_frame_(\d+)\.png$")
    for path in output_dir.glob("*_frame_*.png"):
        match = frame_pattern.match(path.name)
        if not match:
            continue
        # Frame indexes are channel-layer indexes used by main-image preference
        # selection, not display ordering.
        frame_idx = int(match.group(1))
        frames[frame_idx] = media_url(uuid, "output", path.name)
    return frames


def _current_transient_uuid_set(request):
    """Return transient run UUIDs that remain visible in this session."""

    return {
        str(value)
        for value in request.session.get("transient_experiment_uuids", [])
        if str(value)
    }


MANUAL_SAVE_STORAGE_FULL_MESSAGE = (
    "Selected files could not be saved because your storage is full. Free up space and try again."
)


def _storage_full_json_response(exc: StorageQuotaExceeded) -> JsonResponse:
    """Return the manual-save quota response expected by display JS."""

    return JsonResponse(
        {
            "error": MANUAL_SAVE_STORAGE_FULL_MESSAGE,
            "code": "storage_full",
            "required_bytes": exc.required_bytes,
            "available_bytes": exc.available_bytes,
        },
        status=507,
    )


def _can_access_display_uuid(request, uploaded_image, segmented_image) -> bool:
    """Return whether a user may view a saved or session-transient run."""

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


@never_cache
def display(request, uuids):
    """Render one or more transient/saved runs for the Display viewer."""

    uuid_list = [value for value in uuids.split(',') if value]
    protected_uuids = _current_transient_uuid_set(request)
    protected_uuids.update(uuid_list)
    # Display may show newly generated transient runs before the user saves them,
    # so the stale-artifact sweep must protect both URL and session UUIDs.
    sweep_user_run_artifacts(request.user, protected_uuids=protected_uuids)

    # Keep table output bound to the first UUID that has statistics so the
    # server-rendered table and ``displayFilesData`` agree on the active file.
    first_table_uuid = None

    all_files_data = {}
    file_list = []
    cell_table = None
    channel_order = RESULT_CHANNEL_ORDER

    preferences = get_user_preferences(request.user)
    show_saved_file_channels = bool(preferences.get("show_saved_file_channels", True))
    show_saved_file_scales = bool(preferences.get("show_saved_file_scales", True))
    sidebar_starts_open = bool(preferences.get("sidebar_starts_open", True))
    confirm_cell_deletion = bool(preferences.get("confirm_cell_deletion", True))
    confirm_multi_cell_deletion = bool(
        preferences.get("confirm_multi_cell_deletion", True)
    )
    default_manual_scale = (
        preferences.get("experiment_defaults", {}).get("microns_per_pixel", 0.1)
    )
    default_spatial_stats_unit = normalize_spatial_stats_unit(
        preferences.get("experiment_defaults", {}).get("spatial_stats_unit"),
        default="px",
    )
    sidebar_spatial_stats_unit = normalize_spatial_stats_unit(
        preferences.get("sidebar_spatial_stats_unit"),
        default=default_spatial_stats_unit,
    )
    main_image_channel = normalize_main_image_channel(
        preferences.get("main_image_channel"),
        default="",
    )
    initial_puncta_source_contour_count_filter = (
        resolve_initial_puncta_source_contour_count_filter(request, preferences)
    )
    initial_cell_type_filter = normalize_cell_type_filter(request.GET.get("_cell_type"))
    effective_initial_puncta_source_contour_count_filter = (
        initial_puncta_source_contour_count_filter
    )
    effective_initial_cell_type_filter = initial_cell_type_filter

    for uuid in uuid_list:
        try:
            uploaded_image = UploadedImage.objects.get(uuid=uuid)
            cell_image = SegmentedImage.objects.get(UUID=uuid)
            if not _can_access_display_uuid(request, uploaded_image, cell_image):
                return HttpResponse("You do not have access to this result.", status=401)
            image_name = uploaded_image.name
            channel_config = get_channel_config_for_uuid(uuid)
            presence = get_channel_presence(str(uuid))
            present_channels = (
                set(presence.present_channels)
                if presence.present_channels or presence.source != "ambiguous"
                else None
            )
            # Ambiguous channel presence means legacy all-present display; explicit
            # sidecars hide missing channel slots by emitting empty image pairs.
            # Sidebar channel labels follow the channel_config written during upload
            # preparation, not hard-coded Red/Green/Blue/DIC order.
            detected = detected_channel_labels(channel_config)

            # The sidebar payload is kept separate from displayFilesData because it
            # includes saved/transient state and compact scale summaries.
            scale_payload = get_scale_sidebar_payload(
                uploaded_image.scale_info,
                manual_default=default_manual_scale,
            )
            scale_context = get_scale_context_payload(
                uploaded_image.scale_info,
                manual_default=default_manual_scale,
            )
            file_list.append({
                'uuid': uuid,
                'name': image_name,
                'detected_channels': detected,
                'uploaded_date': cell_image.uploaded_date,
                'num_cells': int(cell_image.NumCells or 0),
                'is_saved': bool(request.user.is_authenticated and cell_image.user_id == request.user.id),
                'scale': scale_payload,
            })
            image_name_stem = Path(image_name).stem
            image_index = 0

            if request.method == 'POST':
                if 'green' in request.POST or 'gfp' in request.POST:
                    image_index = channel_config.get(CHANNEL_ROLE_GREEN, 2)
                elif 'red' in request.POST or 'mCherry' in request.POST:
                    image_index = channel_config.get(CHANNEL_ROLE_RED, 3)
                elif 'dic' in request.POST:
                    image_index = channel_config.get(CHANNEL_ROLE_DIC, 0)
                else:
                    image_index = channel_config.get(CHANNEL_ROLE_BLUE, 1)
            full_outlined = output_frame_url(
                uuid=uuid,
                image_name=image_name,
                frame_index=image_index,
            )
            available_frames = _scan_output_frames(str(uuid))
            main_image_paths = build_main_image_paths(
                uuid=str(uuid),
                image_name=image_name,
                channel_config=channel_config,
                available_frames=available_frames,
            )
            # Cell images are emitted in RESULT_CHANNEL_ORDER with outline/no-outline
            # pairs so the static viewer can switch channels without new requests.
            images = {}
            statistics = {}
            cell_stats_qs = CellStatistics.objects.filter(segmented_image=cell_image).order_by('cell_id')
            stats_by_id = {cell.cell_id: cell for cell in cell_stats_qs}
            if stats_by_id and first_table_uuid is None:
                first_table_uuid = uuid
                effective_initial_cell_type_filter = resolve_effective_cell_type_filter(
                    cell_stats_qs,
                    initial_cell_type_filter,
                )
                effective_initial_puncta_source_contour_count_filter = (
                    resolve_effective_puncta_source_contour_count_filter(
                        cell_stats_qs,
                        initial_puncta_source_contour_count_filter,
                    )
                )
                initial_table_stats = filter_statistics_by_cell_type(
                    cell_stats_qs,
                    effective_initial_cell_type_filter,
                )
                initial_table_stats = filter_statistics_by_puncta_source_contour_count(
                    initial_table_stats,
                    effective_initial_puncta_source_contour_count_filter,
                )
                table_mode, puncta_line_mode = resolve_cell_table_modes(
                    initial_table_stats
                )
                cell_table = CellTable(
                    initial_table_stats,
                    intensity_mode=table_mode,
                    puncta_line_mode=puncta_line_mode,
                    spatial_stats_unit=sidebar_spatial_stats_unit,
                    scale_context=scale_context,
                )
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
            segmented_dir = Path(MEDIA_ROOT) / str(uuid) / 'segmented'
            available_result_channels = {
                channel_name
                for channel_name in channel_order
                if channel_config.get(channel_name) is not None
                and (
                    present_channels is None
                    or channel_name in present_channels
                )
                and any(
                    (
                        segmented_dir
                        / (
                            f"{image_name_stem}-{channel_config[channel_name]}-"
                            f"{cell_id}-no_outline.png"
                        )
                    ).exists()
                    for cell_id in cell_ids
                )
            }
            dic_channel_index = channel_config.get(CHANNEL_ROLE_DIC)
            cell_boundary_available = (
                dic_channel_index is not None
                and any(
                    (
                        segmented_dir
                        / f"{image_name_stem}-{dic_channel_index}-{cell_id}.png"
                    ).exists()
                    and (
                        segmented_dir
                        / (
                            f"{image_name_stem}-{dic_channel_index}-{cell_id}"
                            "-no_outline.png"
                        )
                    ).exists()
                    for cell_id in cell_ids
                )
            )
            no_cells_warning = None
            if number_of_cells == 0:
                no_cells_warning = (
                    'No segmented cells were produced for this file. '
                    'Check channel mapping (DIC/Blue/Red/Green) and try again.'
                )

            for i in cell_ids:
                images[str(i)] = []
                cell_stat = stats_by_id.get(i)
                for channel_name in channel_order:
                    if present_channels is not None and channel_name not in present_channels:
                        images[str(i)].extend(["", ""])
                        continue
                    channel_index = channel_config.get(channel_name)
                    if channel_index is None:
                        images[str(i)].extend(["", ""])
                        continue
                    no_outline = segmented_cell_image_url(
                        uuid=uuid,
                        image_name=image_name_stem,
                        channel_index=channel_index,
                        cell_id=i,
                        outline=False,
                    )
                    if (
                        channel_name in [CHANNEL_ROLE_RED, CHANNEL_ROLE_GREEN, CHANNEL_ROLE_BLUE]
                        and cell_stat is not None
                        and overlay_image_available(uuid, i, channel_name)
                    ):
                        # Fluorescence overlay URLs replay exact server-side contours
                        # when cache/config data exists; DIC still uses stored crops.
                        image_url = build_overlay_image_url(uuid, i, channel_name)
                    else:
                        image_url = segmented_cell_image_url(
                            uuid=uuid,
                            image_name=image_name_stem,
                            channel_index=channel_index,
                            cell_id=i,
                        )
                    images[str(i)].append(image_url)
                    images[str(i)].append(no_outline)

                if cell_stat is not None:
                    statistics[str(i)] = serialize_cell_statistics_payload(cell_stat)

            export_format = request.GET.get('_export', None)
            export_unit = normalize_spatial_stats_unit(request.GET.get('_unit'), default="px")
            if TableExport.is_valid_format(export_format) and cell_table is not None:
                # Direct Display export reuses the currently authorized table data
                # and applies query-string column/filter options before streaming.
                raw_columns = request.GET.getlist("_columns")
                columns_present = "_columns" in request.GET
                export_puncta_source_contour_count_filter = request.GET.get(
                    "_puncta_source_contour_count",
                    request.GET.get("_red_contour_count"),
                )
                export_cell_type_filter = normalize_cell_type_filter(
                    request.GET.get("_cell_type")
                )
                try:
                    exclude_columns = export_exclude_columns(
                        raw_columns,
                        columns_present=columns_present,
                    )
                    metric_scope = export_metric_scope(
                        raw_columns,
                        columns_present=columns_present,
                    )
                except ExportColumnSelectionError as exc:
                    return HttpResponse(str(exc), status=400)
                if first_table_uuid == uuid:
                    effective_export_cell_type_filter = resolve_effective_cell_type_filter(
                        cell_stats_qs,
                        export_cell_type_filter,
                    )
                    effective_export_puncta_source_contour_count_filter = (
                        resolve_effective_puncta_source_contour_count_filter(
                            cell_stats_qs,
                            export_puncta_source_contour_count_filter,
                        )
                    )
                    export_stats = filter_statistics_by_cell_type(
                        cell_stats_qs,
                        effective_export_cell_type_filter,
                    )
                    export_stats = filter_statistics_by_puncta_source_contour_count(
                        export_stats,
                        effective_export_puncta_source_contour_count_filter,
                    )
                    export_table_mode, export_puncta_line_mode = resolve_cell_table_modes(
                        export_stats
                    )
                    cell_table = CellTable(
                        export_stats,
                        intensity_mode=export_table_mode,
                        puncta_line_mode=export_puncta_line_mode,
                        spatial_stats_unit=export_unit,
                        scale_context=scale_context,
                    )
                exporter = TableExport(
                    export_format,
                    cell_table,
                    exclude_columns=exclude_columns,
                )
                return exporter.response(
                    build_statistics_export_filename(
                        scope=metric_scope,
                        file_count=1,
                        export_format=export_format,
                    )
                )

            # Keep this JSON shape stable for display-viewer.js and export modal
            # tests; dashboard emits the same primitives with saved-run semantics.
            all_files_data[str(uuid)] = {
                'MainImagePath': full_outlined,
                'MainImagePaths': main_image_paths,
                'NumberOfCells': number_of_cells,
                'CellPairImages': images,
                'OverlayLayers': build_overlay_layer_contract(
                    str(uuid),
                    available_channels=available_result_channels,
                    aggregate_available=number_of_cells > 0,
                    cell_boundary_available=cell_boundary_available,
                ),
                'Image_Name': image_name,
                'ScaleContext': scale_context,
                'ChannelConfig': channel_config_payload(channel_config),
                'Statistics': statistics,
                'NoCellsWarning': no_cells_warning,
            }

        except UploadedImage.DoesNotExist:
            return HttpResponse("The uploaded image could not be found.", status=404)
        except SegmentedImage.DoesNotExist:
            return HttpResponse("The segmented results could not be found.", status=404)

    if cell_table is None:
        cell_table = CellTable(
            CellStatistics.objects.none(),
            intensity_mode=None,
            puncta_line_mode=None,
            spatial_stats_unit=sidebar_spatial_stats_unit,
            scale_context=None,
        )

    # The template writes this into displayFilesData for static JS to parse.
    json_files_data = json.dumps(sanitize_for_json(all_files_data), allow_nan=False)

    return render(request, "display.html", {
        'files_data': json_files_data,  # Pass all file data to the template
        'file_list': file_list,  # Pass sidebar file list data to the template
        'cell_table': cell_table,
        'table_uuid': first_table_uuid or '',
        'show_saved_file_channels': show_saved_file_channels,
        'show_saved_file_scales': show_saved_file_scales,
        'sidebar_starts_open': sidebar_starts_open,
        'confirm_cell_deletion': confirm_cell_deletion,
        'confirm_multi_cell_deletion': confirm_multi_cell_deletion,
        'default_spatial_stats_unit': default_spatial_stats_unit,
        'sidebar_spatial_stats_unit': sidebar_spatial_stats_unit,
        'main_image_channel': main_image_channel,
        'cell_type_filter': effective_initial_cell_type_filter,
        'puncta_source_contour_count_filter': effective_initial_puncta_source_contour_count_filter,
        'export_selection_config': export_selection_config(),
    })


@require_POST
def save_display_files(request):
    """Persist selected display files to account history."""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Your request could not be processed. Please try again."},
            status=400,
        )

    requested_uuids = normalize_uuid_list(payload.get("uuids", []))
    if not requested_uuids:
        return JsonResponse({"error": "Select at least one file to continue."}, status=400)

    # The upload row proves the current user owns the source upload; missing rows
    # usually mean the display sidebar is stale after cleanup or another tab.
    uploaded_map = {
        str(item.uuid): item
        for item in UploadedImage.objects.filter(
            user=request.user,
            uuid__in=requested_uuids,
        )
    }
    if len(uploaded_map) != len(set(requested_uuids)):
        return JsonResponse(
            {"error": "One or more selected files are no longer available. Refresh and try again."},
            status=403,
        )

    segmented_map = {
        str(item.UUID): item
        for item in SegmentedImage.objects.filter(UUID__in=requested_uuids)
    }
    if len(segmented_map) != len(set(requested_uuids)):
        return JsonResponse(
            {"error": "One or more selected files are no longer available. Refresh and try again."},
            status=403,
        )

    transient_uuids = _current_transient_uuid_set(request)
    guest_id = get_guest_user()
    already_saved = []
    to_save = []
    # Saving is an ownership transition from guest/transient to the authenticated
    # user; UUIDs outside the current display session are rejected generically.
    for uuid in requested_uuids:
        segmented = segmented_map.get(uuid)
        if segmented is None:
            return JsonResponse(
                {"error": "One or more selected files are no longer available. Refresh and try again."},
                status=403,
            )
        if segmented.user_id == request.user.id:
            already_saved.append(uuid)
            continue
        if segmented.user_id == guest_id and uuid in transient_uuids:
            to_save.append(uuid)
            continue
        return JsonResponse(
            {"error": "One or more selected files are no longer available. Refresh and try again."},
            status=403,
        )

    try:
        # Quota is checked before the ownership update so a failed save leaves the
        # run transient and visible in the current display session.
        assert_user_can_save_runs(request.user, to_save)
    except StorageQuotaExceeded as exc:
        log_storage_capacity_failure(
            stage="display_save",
            user=request.user,
            uuids=to_save,
            required_bytes=exc.required_bytes,
            available_bytes=exc.available_bytes,
            exc=exc,
        )
        return _storage_full_json_response(exc)

    if to_save:
        with transaction.atomic():
            # The DB transition is isolated from the later session update; if it
            # fails, the browser still has the same transient selection state.
            SegmentedImage.objects.filter(UUID__in=to_save, user_id=guest_id).update(
                user=request.user
            )

    if to_save:
        # Once ownership has moved to the user, remove those UUIDs from the
        # transient session set so stale-artifact sweeps can treat them as saved.
        transient_uuids.difference_update(to_save)
        request.session["transient_experiment_uuids"] = sorted(transient_uuids)

    # The response mirrors dashboard quota fields so shared frontend controls can
    # update counters without a full page reload.
    refresh_user_storage_usage(request.user)
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
        return JsonResponse(
            {"error": "Your request could not be processed. Please try again."},
            status=400,
        )

    requested_uuids = normalize_uuid_list(payload.get("uuids", []))
    if not requested_uuids:
        return JsonResponse({"error": "Select at least one file to continue."}, status=400)

    # UploadedImage ownership is still required because unsaving should only move
    # the user's own saved analysis back into this session's transient set.
    uploaded_map = {
        str(item.uuid): item
        for item in UploadedImage.objects.filter(
            user=request.user,
            uuid__in=requested_uuids,
        )
    }
    if len(uploaded_map) != len(set(requested_uuids)):
        return JsonResponse(
            {"error": "One or more selected files are no longer available. Refresh and try again."},
            status=403,
        )

    segmented_map = {
        str(item.UUID): item
        for item in SegmentedImage.objects.filter(UUID__in=requested_uuids)
    }
    if len(segmented_map) != len(set(requested_uuids)):
        return JsonResponse(
            {"error": "One or more selected files are no longer available. Refresh and try again."},
            status=403,
        )

    transient_uuids = _current_transient_uuid_set(request)
    guest_id = get_guest_user()
    already_unsaved = []
    to_unsave = []
    # Unsaving moves a run back to the guest owner while keeping it visible in the
    # current session so users do not lose the active display page.
    for uuid in requested_uuids:
        segmented = segmented_map.get(uuid)
        if segmented is None:
            return JsonResponse(
                {"error": "One or more selected files are no longer available. Refresh and try again."},
                status=403,
            )
        if segmented.user_id == request.user.id:
            to_unsave.append(uuid)
            continue
        if segmented.user_id == guest_id and uuid in transient_uuids:
            already_unsaved.append(uuid)
            continue
        return JsonResponse(
            {"error": "One or more selected files are no longer available. Refresh and try again."},
            status=403,
        )

    if to_unsave:
        with transaction.atomic():
            # Only saved rows owned by this user are moved back to guest ownership;
            # stale or already-transient rows were classified before this update.
            SegmentedImage.objects.filter(
                UUID__in=to_unsave,
                user=request.user,
            ).update(user_id=guest_id)

    if to_unsave:
        # Keeping unsaved UUIDs in session preserves the current Display page while
        # allowing the dashboard to drop them from retained storage.
        transient_uuids.update(to_unsave)
        request.session["transient_experiment_uuids"] = sorted(transient_uuids)

    # Recalculate after ownership changes because retained storage is derived from
    # saved SegmentedImage rows, not from the Display selection alone.
    refresh_user_storage_usage(request.user)
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
    """Apply Display selection state: selected means saved, unselected transient."""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Your request could not be processed. Please try again."},
            status=400,
        )

    visible_uuids = normalize_uuid_list(payload.get("visible_uuids", []))
    selected_uuids = normalize_uuid_list(payload.get("selected_uuids", []))
    if not visible_uuids:
        return JsonResponse({"error": "Select at least one file to continue."}, status=400)

    visible_set = set(visible_uuids)
    selected_set = set(selected_uuids)
    # The browser posts both the visible file order and selected subset; the
    # backend treats the visible list as the authorization boundary for the page.
    if not selected_set.issubset(visible_set):
        return JsonResponse(
            {"error": "Selected files must be part of the current display list."},
            status=400,
        )

    # Source rows are checked for every visible file, not only selected files, so
    # stale sidebars cannot silently preserve unavailable saved state.
    uploaded_map = {
        str(item.uuid): item
        for item in UploadedImage.objects.filter(
            user=request.user,
            uuid__in=visible_uuids,
        )
    }
    if len(uploaded_map) != len(visible_set):
        return JsonResponse(
            {"error": "One or more selected files are no longer available. Refresh and try again."},
            status=403,
        )

    segmented_map = {
        str(item.UUID): item
        for item in SegmentedImage.objects.filter(UUID__in=visible_uuids)
    }
    if len(segmented_map) != len(visible_set):
        return JsonResponse(
            {"error": "One or more selected files are no longer available. Refresh and try again."},
            status=403,
        )

    transient_uuids = _current_transient_uuid_set(request)
    guest_id = get_guest_user()
    current_saved = set()
    # Classify current ownership before calculating the delta. Anything outside
    # user-owned or current-session transient runs is treated as unavailable.
    for uuid in visible_uuids:
        segmented = segmented_map.get(uuid)
        if segmented is None:
            return JsonResponse(
                {"error": "One or more selected files are no longer available. Refresh and try again."},
                status=403,
            )
        if segmented.user_id == request.user.id:
            current_saved.add(uuid)
            continue
        if segmented.user_id == guest_id and uuid in transient_uuids:
            continue
        return JsonResponse(
            {"error": "One or more selected files are no longer available. Refresh and try again."},
            status=403,
        )

    to_save = sorted(selected_set.difference(current_saved))
    to_unsave = sorted(current_saved.difference(selected_set))

    try:
        # Selection sync can swap saved and unsaved runs in one request; quota
        # enforcement credits the bytes that will be reclaimed by to_unsave.
        assert_user_can_save_runs(request.user, to_save, to_unsave)
    except StorageQuotaExceeded as exc:
        log_storage_capacity_failure(
            stage="display_sync_selection",
            user=request.user,
            uuids=[*to_save, *to_unsave],
            required_bytes=exc.required_bytes,
            available_bytes=exc.available_bytes,
            exc=exc,
        )
        return _storage_full_json_response(exc)

    with transaction.atomic():
        # Apply both sides of the ownership transition in one DB transaction so
        # saved counts cannot observe only half of a sidebar sync.
        if to_save:
            SegmentedImage.objects.filter(UUID__in=to_save, user_id=guest_id).update(
                user=request.user
            )
        if to_unsave:
            SegmentedImage.objects.filter(UUID__in=to_unsave, user=request.user).update(
                user_id=guest_id
            )

    if to_save or to_unsave:
        # The transient session set is the Display page's protection list for
        # unsaved files, so update it only after the database transition succeeds.
        transient_uuids.difference_update(to_save)
        transient_uuids.update(to_unsave)
        request.session["transient_experiment_uuids"] = sorted(transient_uuids)

    # Return storage counters after the DB transition because the frontend updates
    # saved badges and quota meters from this payload.
    refresh_user_storage_usage(request.user)
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


@require_POST
def export_display_files(request):
    """Download one combined statistics export for selected visible files."""

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Your request could not be processed. Please try again."},
            status=400,
        )

    visible_uuids = normalize_uuid_list(payload.get("visible_uuids", []))
    requested_uuids = normalize_uuid_list(payload.get("uuids", []))
    if not requested_uuids:
        return JsonResponse({"error": "Select at least one file to continue."}, status=400)
    if not visible_uuids:
        return JsonResponse(
            {"error": "Visible files are no longer available. Refresh and try again."},
            status=400,
        )

    visible_set = set(visible_uuids)
    selected_set = set(requested_uuids)
    if not selected_set.issubset(visible_set):
        return JsonResponse(
            {"error": "One or more selected files are no longer available. Refresh and try again."},
            status=403,
        )
    ordered_uuids = [uuid for uuid in visible_uuids if uuid in selected_set]
    # Preserve visible sidebar order in multi-file exports; metric selection is
    # handled later by the shared export service.

    uploaded_map = {
        str(item.uuid): item
        for item in UploadedImage.objects.filter(
            user=request.user,
            uuid__in=ordered_uuids,
        )
    }
    segmented_map = {
        str(item.UUID): item
        for item in SegmentedImage.objects.filter(UUID__in=ordered_uuids)
    }
    if (
        len(uploaded_map) != len(set(ordered_uuids))
        or len(segmented_map) != len(set(ordered_uuids))
    ):
        # Export fails closed on stale selections so the downloaded file cannot
        # silently omit rows that the modal claimed were selected.
        return JsonResponse(
            {"error": "One or more selected files are no longer available. Refresh and try again."},
            status=403,
        )

    for uuid in ordered_uuids:
        uploaded = uploaded_map[uuid]
        segmented = segmented_map[uuid]
        # Access checks are repeated per UUID because Display can mix saved and
        # transient runs that have different ownership rules.
        if not _can_access_display_uuid(request, uploaded, segmented):
            return JsonResponse(
                {"error": "One or more selected files are no longer available. Refresh and try again."},
                status=403,
            )
    sources = build_statistics_export_sources(
        ordered_uuids,
        uploaded_map=uploaded_map,
        segmented_map=segmented_map,
    )

    preferences = get_user_preferences(request.user)
    default_manual_scale = (
        preferences.get("experiment_defaults", {}).get("microns_per_pixel", 0.1)
    )
    try:
        return build_combined_statistics_export_response(
            sources,
            export_format=str(payload.get("_export") or ""),
            raw_columns=payload.get("_columns"),
            spatial_stats_unit=str(payload.get("_unit") or "px"),
            default_manual_scale=default_manual_scale,
            cell_type_filter=payload.get("_cell_type"),
            puncta_source_contour_count_filter=payload.get(
                "_puncta_source_contour_count",
                payload.get("_red_contour_count"),
            ),
        )
    except (CombinedStatisticsExportError, ExportColumnSelectionError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)


def main_image_channel(request, uuid):
    """Return one main-image URL without a full Display page reload."""

    if request.method != 'GET':
        return JsonResponse({'error': 'This action is not available.'}, status=405)

    # The channel slug is normalized before any filesystem path is built so the
    # endpoint cannot be used to request arbitrary output filenames.
    channel = (request.GET.get('channel') or '').strip().lower()
    channel_role = channel_role_from_slug(channel)
    if not channel_role:
        return JsonResponse({'error': 'That image channel is not available for this file.'}, status=400)

    try:
        uploaded_image = UploadedImage.objects.get(uuid=uuid)
    except UploadedImage.DoesNotExist:
        return JsonResponse({'error': 'The uploaded image could not be found.'}, status=404)

    try:
        cell_image = SegmentedImage.objects.get(UUID=uuid)
    except SegmentedImage.DoesNotExist:
        return JsonResponse({'error': 'The segmented results could not be found.'}, status=404)

    if not _can_access_display_uuid(request, uploaded_image, cell_image):
        return JsonResponse({'error': 'You do not have access to this result.'}, status=401)

    # Main-image URLs come from the same helper used during full page rendering,
    # keeping AJAX channel switches aligned with template JSON payloads.
    channel_config = get_channel_config_for_uuid(str(uuid))
    available_frames = _scan_output_frames(str(uuid))
    main_image_paths = build_main_image_paths(
        uuid=str(uuid),
        image_name=uploaded_image.name,
        channel_config=channel_config,
        available_frames=available_frames,
    )
    full_outlined = main_image_paths.get(channel) or ""

    return JsonResponse({
        'image_url': full_outlined,
        'channel': channel,
    })


@require_POST
def delete_cell_view(request, uuid, cell_id):
    """Delete a single cell's row and on-disk artifacts for a run."""
    try:
        uploaded_image = UploadedImage.objects.get(uuid=uuid)
    except UploadedImage.DoesNotExist:
        return HttpResponseNotFound("The uploaded image could not be found.")

    try:
        segmented_image = SegmentedImage.objects.get(UUID=uuid)
    except SegmentedImage.DoesNotExist:
        return HttpResponseNotFound("The segmented results could not be found.")

    if not _can_access_display_uuid(request, uploaded_image, segmented_image):
        return HttpResponseForbidden("You do not have access to this result.")

    try:
        # Cell artifact deletion and NumCells updates live in the service layer so
        # single and bulk endpoints preserve the same cleanup contract.
        delete_single_cell(segmented_image, int(cell_id))
    except CellStatistics.DoesNotExist:
        return HttpResponseNotFound("That cell has already been removed.")

    # Refresh from the database after service cleanup because NumCells is updated
    # as part of deletion, and the viewer uses this response to prune UI state.
    segmented_image.refresh_from_db(fields=["NumCells"])
    remaining_ids = list(
        CellStatistics.objects
        .filter(segmented_image=segmented_image)
        .order_by("cell_id")
        .values_list("cell_id", flat=True)
    )

    return JsonResponse({
        "ok": True,
        "uuid": str(uuid),
        "cell_id": int(cell_id),
        "num_cells": int(segmented_image.NumCells or 0),
        "remaining_cells": remaining_ids,
    })


@require_POST
def delete_cells_view(request, uuid):
    """Delete multiple cells' rows and on-disk artifacts for a run."""
    try:
        uploaded_image = UploadedImage.objects.get(uuid=uuid)
    except UploadedImage.DoesNotExist:
        return HttpResponseNotFound("The uploaded image could not be found.")

    try:
        segmented_image = SegmentedImage.objects.get(UUID=uuid)
    except SegmentedImage.DoesNotExist:
        return HttpResponseNotFound("The segmented results could not be found.")

    if not _can_access_display_uuid(request, uploaded_image, segmented_image):
        return HttpResponseForbidden("You do not have access to this result.")

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    raw_cell_ids = payload.get("cell_ids")
    if not isinstance(raw_cell_ids, list) or not raw_cell_ids:
        return JsonResponse({"error": "Select at least one cell to delete."}, status=400)

    cell_ids: list[int] = []
    seen_ids: set[int] = set()
    # Normalize and deduplicate client IDs before hitting the service so repeated
    # clicks or stale modal state cannot produce partial validation surprises.
    for raw_cell_id in raw_cell_ids:
        if isinstance(raw_cell_id, bool):
            return JsonResponse({"error": "Cell IDs must be positive integers."}, status=400)
        try:
            cell_id_int = int(raw_cell_id)
        except (TypeError, ValueError):
            return JsonResponse({"error": "Cell IDs must be positive integers."}, status=400)
        if cell_id_int <= 0 or str(raw_cell_id).strip() != str(cell_id_int):
            return JsonResponse({"error": "Cell IDs must be positive integers."}, status=400)
        if cell_id_int in seen_ids:
            continue
        seen_ids.add(cell_id_int)
        cell_ids.append(cell_id_int)

    deleted_ids = delete_multiple_cells(segmented_image, cell_ids)
    if not deleted_ids:
        return HttpResponseNotFound("Selected cells have already been removed.")

    # The response carries the remaining IDs so the frontend can reconcile table,
    # image, and multi-select state after service-layer artifact cleanup.
    segmented_image.refresh_from_db(fields=["NumCells"])
    remaining_ids = list(
        CellStatistics.objects
        .filter(segmented_image=segmented_image)
        .order_by("cell_id")
        .values_list("cell_id", flat=True)
    )

    return JsonResponse({
        "ok": True,
        "uuid": str(uuid),
        "deleted_cells": deleted_ids,
        "num_cells": int(segmented_image.NumCells or 0),
        "remaining_cells": remaining_ids,
    })
