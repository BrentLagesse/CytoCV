from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.template.response import TemplateResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.urls import reverse
import math
from uuid import UUID
import logging

from core.models import SegmentedImage, UploadedImage, get_guest_user
from core.services.analysis_context import (
    build_analysis_batch_context,
    build_batch_key,
    normalize_execution_mode,
)
from core.services.analysis_exceptions import AnalysisCancelled
from core.services.analysis_jobs import (
    enqueue_analysis_job,
    get_active_analysis_job,
    get_latest_analysis_job,
    reap_stale_analysis_jobs,
)
from core.services.analysis_pipeline import run_analysis_batch
from core.services.analysis_progress import AnalysisProgressHandle, get_progress_snapshot
from core.services.analysis_progress_contract import (
    PROGRESS_PHASE_FAILED,
    PROGRESS_STATUS_FAILED,
    PROGRESS_STATUS_SUCCEEDED,
    SAFE_ANALYSIS_FAILURE_SUMMARY,
    SAFE_PROGRESS_ERROR_MESSAGE,
    SAFE_PROGRESS_WRITE_ERROR_MESSAGE,
    TERMINAL_PROGRESS_STATUSES,
    normalize_progress_phase,
    progress_log_ref,
    validate_progress_status,
)
from core.services.puncta_line_mode import (
    DEFAULT_PUNCTA_LINE_MODE,
    normalize_puncta_line_mode,
)
from .utils import (
    tif_to_jpg,
    prune_experiment_session_state,
    sync_transient_run_session_state,
)
from core.channel_roles import CHANNEL_ROLE_ORDER, channel_display_label
from core.metadata_processing.dv_channel_parser import extract_channel_config
from core.mrcnn.my_inference import predict_images
from core.mrcnn.preprocess_images import preprocess_images

from cytocv.settings import MEDIA_ROOT
from pathlib import Path
import json
import re

from accounts.preferences import get_user_preferences
from core.scale import (
    apply_manual_override_scale,
    clear_manual_override_scale,
    get_scale_sidebar_payload,
    normalize_length_unit,
    normalize_spatial_stats_unit,
)
from core.services.artifact_storage import (
    cleanup_failed_processing_artifacts,
    delete_uploaded_run_by_uuid,
    ensure_preview_assets,
    is_storage_full_error,
    log_storage_capacity_failure,
    sweep_user_run_artifacts,
)

NUCLEAR_CELL_PAIR_MODES = {"green_nucleus", "red_nucleus"}
PROCESSING_STORAGE_FULL_MESSAGE = (
    "Files could not be saved because storage is full. Free up space and try again."
)
logger = logging.getLogger(__name__)
PROGRESS_BATCH_SESSION_KEY = "authorized_progress_batches"


class ProgressRequestError(Exception):
    """Controlled progress request error carrying an HTTP status code."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _current_owner_filter(request) -> dict:
    """Return queryset filter args for the current upload owner."""

    if request.user.is_authenticated:
        return {"user": request.user}
    return {"user_id": get_guest_user()}


def _delete_cancelled_runs(request, uuid_values: list[str]) -> None:
    """Hard-delete the current user's cancelled experiment runs."""

    owner_filter = _current_owner_filter(request)
    owned_uuids = {
        str(value)
        for value in UploadedImage.objects.filter(
            uuid__in=uuid_values,
            **owner_filter,
        ).values_list("uuid", flat=True)
    }
    for run_uuid in owned_uuids:
        delete_uploaded_run_by_uuid(run_uuid)
    prune_experiment_session_state(request, owned_uuids)


def _get_authorized_progress_batches(request) -> set[str]:
    """Return session-tracked progress batches authorized for the current user."""

    return {
        str(value)
        for value in request.session.get(PROGRESS_BATCH_SESSION_KEY, [])
        if str(value)
    }


def _track_progress_batch(request, batch_key: str) -> None:
    """Persist a session-scoped allowlist for in-flight progress lookups."""

    tracked = _get_authorized_progress_batches(request)
    if batch_key in tracked:
        return
    tracked.add(batch_key)
    request.session[PROGRESS_BATCH_SESSION_KEY] = sorted(tracked)
    request.session.modified = True


def _release_progress_batch(request, batch_key: str) -> None:
    """Remove a finished batch from the session-scoped progress allowlist."""

    tracked = _get_authorized_progress_batches(request)
    if batch_key not in tracked:
        return
    tracked.remove(batch_key)
    request.session[PROGRESS_BATCH_SESSION_KEY] = sorted(tracked)
    request.session.modified = True


def _resolve_owned_progress_batch(request, raw_uuids: str) -> tuple[str, list[str]]:
    """Return the canonical owned batch key for progress routes."""

    if not raw_uuids or not re.fullmatch(r"[0-9a-fA-F,-]+", raw_uuids):
        raise ProgressRequestError("Invalid analysis batch.", status_code=400)
    try:
        batch_key = build_batch_key(raw_uuids)
    except (TypeError, ValueError):
        raise ProgressRequestError("Invalid analysis batch.", status_code=400)
    uuid_list = [value for value in batch_key.split(",") if value]
    if not uuid_list:
        raise ProgressRequestError("Invalid analysis batch.", status_code=400)

    owner_filter = _current_owner_filter(request)
    owned_uploads = {
        str(value)
        for value in UploadedImage.objects.filter(
            uuid__in=uuid_list,
            **owner_filter,
        ).values_list("uuid", flat=True)
    }
    owned_segmented = {
        str(value)
        for value in SegmentedImage.objects.filter(
            UUID__in=uuid_list,
            user=request.user,
        ).values_list("UUID", flat=True)
    }
    owned_uuids = owned_uploads | owned_segmented
    if set(uuid_list).issubset(owned_uuids):
        return batch_key, uuid_list

    if batch_key in _get_authorized_progress_batches(request):
        return batch_key, uuid_list

    if get_latest_analysis_job(user_id=request.user.id, batch_key=batch_key) is not None:
        return batch_key, uuid_list

    raise ProgressRequestError("Forbidden", status_code=403)


def _progress_read_error_response(message: str, *, status_code: int) -> JsonResponse:
    """Return a controlled progress-read error payload."""

    return JsonResponse(
        {
            "phase": PROGRESS_PHASE_FAILED,
            "status": PROGRESS_STATUS_FAILED,
            "failure_summary": message,
            "redirect": None,
        },
        status=status_code,
    )


def _progress_write_error_response(message: str, *, status_code: int) -> JsonResponse:
    """Return a controlled progress-write error payload."""

    return JsonResponse({"status": "error", "message": message}, status=status_code)


def _parse_file_scale_map_payload(
    raw_payload: str,
    active_uuid_set: set[str],
) -> tuple[dict[str, float], str | None, int]:
    """Parse and validate per-file scale payload from preprocess form."""

    if not raw_payload:
        return {}, None, 200
    try:
        payload = json.loads(raw_payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}, "Invalid per-file scale payload.", 400
    if not isinstance(payload, dict):
        return {}, "Per-file scale payload must be a JSON object.", 400

    parsed: dict[str, float] = {}
    for raw_uuid, raw_value in payload.items():
        try:
            normalized_uuid = str(UUID(str(raw_uuid)))
        except (TypeError, ValueError, AttributeError):
            return {}, "Per-file scale payload contains an invalid UUID.", 400
        if normalized_uuid not in active_uuid_set:
            return {}, "Per-file scale payload contains unavailable files.", 403

        value = raw_value
        if isinstance(raw_value, dict):
            value = raw_value.get("effective_um_per_px")
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return {}, "Per-file scale values must be numeric.", 400
        if not math.isfinite(numeric) or numeric <= 0:
            return {}, "Per-file scale values must be greater than 0.", 400
        parsed[normalized_uuid] = numeric
    return parsed, None, 200


def _parse_file_scale_revert_payload(
    raw_payload: str,
    active_uuid_set: set[str],
) -> tuple[set[str], str | None, int]:
    """Parse and validate file UUIDs that should revert to auto scale resolution."""

    if not raw_payload:
        return set(), None, 200
    try:
        payload = json.loads(raw_payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return set(), "Invalid scale revert payload.", 400
    if not isinstance(payload, list):
        return set(), "Scale revert payload must be a JSON array.", 400

    parsed: set[str] = set()
    for raw_uuid in payload:
        try:
            normalized_uuid = str(UUID(str(raw_uuid)))
        except (TypeError, ValueError, AttributeError):
            return set(), "Scale revert payload contains an invalid UUID.", 400
        if normalized_uuid not in active_uuid_set:
            return set(), "Scale revert payload contains unavailable files.", 403
        parsed.add(normalized_uuid)
    return parsed, None, 200


@require_GET
def get_progress(request, uuids):
    try:
        batch_key, uuid_list = _resolve_owned_progress_batch(request, uuids)
        snapshot = get_progress_snapshot(batch_key=batch_key, user_id=request.user.id)
        if snapshot.status in TERMINAL_PROGRESS_STATUSES:
            _finalize_terminal_progress_batch(request, batch_key, uuid_list)
        redirect_url = (
            reverse("display", kwargs={"uuids": batch_key})
            if snapshot.status == PROGRESS_STATUS_SUCCEEDED
            else None
        )
        if snapshot.status == PROGRESS_STATUS_SUCCEEDED and not redirect_url:
            logger.warning(
                "Progress endpoint missing redirect for progress ref %s",
                progress_log_ref(batch_key),
            )
        return JsonResponse(
            {
                "phase": snapshot.phase,
                "status": snapshot.status,
                "failure_summary": snapshot.failure_summary,
                "redirect": redirect_url,
            }
        )
    except ProgressRequestError as exc:
        return _progress_read_error_response(
            SAFE_PROGRESS_ERROR_MESSAGE,
            status_code=exc.status_code,
        )
    except Exception:
        logger.exception("Progress read failed")
        return _progress_read_error_response(
            SAFE_PROGRESS_ERROR_MESSAGE,
            status_code=500,
        )


def _finalize_terminal_progress_batch(
    request,
    batch_key: str,
    uuid_list: list[str],
) -> None:
    """Reconcile transient display access and clear progress authorization."""

    sync_transient_run_session_state(request, uuid_list)
    _release_progress_batch(request, batch_key)


def pre_process(request, uuids):
    """
    GET: Render previews + sidebar (with auto-detected channel order).
    POST: Run preprocess + inference on every UUID, then redirect.
    """

    uuid_list = uuids.split(',')
    owner_filter = _current_owner_filter(request)
    total_files = len(uuid_list)
    protected_uuids = {
        str(value)
        for value in request.session.get("transient_experiment_uuids", [])
        if str(value)
    }
    protected_uuids.update(str(value) for value in uuid_list if str(value))
    sweep_user_run_artifacts(request.user, protected_uuids=protected_uuids)
    preferences = get_user_preferences(request.user)
    show_saved_file_channels = bool(preferences.get("show_saved_file_channels", True))
    show_saved_file_scales = bool(preferences.get("show_saved_file_scales", True))
    sidebar_starts_open = bool(preferences.get("sidebar_starts_open", True))
    default_manual_scale = (
        preferences.get("experiment_defaults", {}).get("microns_per_pixel", 0.1)
    )
    default_spatial_stats_unit = normalize_spatial_stats_unit(
        preferences.get("experiment_defaults", {}).get("spatial_stats_unit"),
        default="px",
    )
    analysis_execution_mode = normalize_execution_mode()
    sidebar_spatial_stats_unit = normalize_spatial_stats_unit(
        preferences.get("sidebar_spatial_stats_unit"),
        default=default_spatial_stats_unit,
    )

    # clamp file_index into [0, total_files-1]
    current_file_index = int(request.GET.get('file_index', 0))
    current_file_index = max(0, min(current_file_index, total_files - 1))

    # build sidebar list, including the 4-channel order per file
    file_list = []
    for uid in uuid_list:
        uploaded = get_object_or_404(UploadedImage, uuid=uid, **owner_filter)

        # try reading existing channel_config.json
        cfg_path = Path(MEDIA_ROOT) / uid / 'channel_config.json'
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            detected_channels = [
                channel_display_label(ch) for ch, _ in sorted(cfg.items(), key=lambda t: t[1])
            ]
        else:
            # fallback: parse header of first .dv file
            dv_files = list((Path(MEDIA_ROOT) / uid).glob('*.dv'))
            if dv_files:
                cfg = extract_channel_config(str(dv_files[0]))
                detected_channels = [
                    channel_display_label(ch)
                    for ch, _ in sorted(cfg.items(), key=lambda t: t[1])
                ]
            else:
                detected_channels = []

        scale_payload = get_scale_sidebar_payload(
            uploaded.scale_info,
            manual_default=default_manual_scale,
        )

        file_list.append({
            'uuid': uid,
            'name': uploaded.name,
            'detected_channels': detected_channels,
            'scale': scale_payload,
        })

    # current file previews
    current_uuid = uuid_list[current_file_index]
    uploaded_image = get_object_or_404(UploadedImage, uuid=current_uuid, **owner_filter)
    preview_images = ensure_preview_assets(uploaded_image)

    # POST: preprocess + predict all, then redirect
    if request.method == "POST":
        active_uuid_set: set[str] = set()
        for value in uuid_list:
            if not str(value):
                continue
            try:
                active_uuid_set.add(str(UUID(str(value))))
            except (TypeError, ValueError, AttributeError):
                active_uuid_set.add(str(value))
        scale_map, scale_error, scale_status = _parse_file_scale_map_payload(
            request.POST.get("file_scale_map", ""),
            active_uuid_set=active_uuid_set,
        )
        if scale_error:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": scale_error}, status=scale_status)
            return HttpResponse(scale_error, status=scale_status)
        revert_uuid_set, revert_error, revert_status = _parse_file_scale_revert_payload(
            request.POST.get("file_scale_revert_uuids", ""),
            active_uuid_set=active_uuid_set,
        )
        if revert_error:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": revert_error}, status=revert_status)
            return HttpResponse(revert_error, status=revert_status)
        # Explicit manual overrides take precedence if the same UUID appears in both payloads.
        if scale_map and revert_uuid_set:
            revert_uuid_set.difference_update(scale_map.keys())

        if scale_map or revert_uuid_set:
            uploaded_map = {
                str(item.uuid): item
                for item in UploadedImage.objects.filter(uuid__in=active_uuid_set, **owner_filter)
            }
            if len(uploaded_map) != len(active_uuid_set):
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"error": "Unauthorized"}, status=401)
                return HttpResponse("Unauthorized", status=401)
            updates = []
            for image_uuid in revert_uuid_set:
                uploaded = uploaded_map.get(image_uuid)
                if uploaded is None:
                    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                        return JsonResponse({"error": "Unauthorized"}, status=401)
                    return HttpResponse("Unauthorized", status=401)
                uploaded.scale_info = clear_manual_override_scale(
                    uploaded.scale_info,
                    manual_default=default_manual_scale,
                )
                updates.append(uploaded)
            for image_uuid, effective_scale in scale_map.items():
                uploaded = uploaded_map.get(image_uuid)
                if uploaded is None:
                    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                        return JsonResponse({"error": "Unauthorized"}, status=401)
                    return HttpResponse("Unauthorized", status=401)
                uploaded.scale_info = apply_manual_override_scale(
                    uploaded.scale_info,
                    effective_um_per_px=effective_scale,
                )
                updates.append(uploaded)
            if updates:
                UploadedImage.objects.bulk_update(updates, ["scale_info"])

        # Selection is primarily set during upload step. Keep POST fallback for
        # backward compatibility with older clients.
        selected_analysis = request.POST.getlist('selected_analysis') or request.session.get('selected_analysis', [])
        puncta_line_width_raw = request.POST.get(
            'punctaLineWidth',
            request.POST.get('redLineWidth', request.session.get('punctaLineWidth', request.session.get('redLineWidth', request.session.get('mCherryWidth', 1)))),
        )
        cen_dot_distance_raw = request.POST.get(
            'cenDotDistance',
            request.session.get('cenDotDistance', request.session.get('distance', 37)),
        )
        biorientation_red_min_distance_value_raw = request.POST.get(
            'biorientationRedMinDistance',
            request.session.get('stats_biorientation_red_min_distance_value', 0.0),
        )
        biorientation_red_min_distance_unit_raw = request.POST.get(
            'biorientationRedMinDistanceUnit',
            request.session.get('stats_biorientation_red_min_distance_unit', 'px'),
        )
        biorientation_red_max_distance_value_raw = request.POST.get(
            'biorientationRedMaxDistance',
            request.session.get('stats_biorientation_red_max_distance_value', 37.0),
        )
        biorientation_red_max_distance_unit_raw = request.POST.get(
            'biorientationRedMaxDistanceUnit',
            request.session.get('stats_biorientation_red_max_distance_unit', 'px'),
        )
        biorientation_collinearity_threshold_raw = request.POST.get(
            'biorientationCollinearityThreshold',
            request.session.get('biorientationCollinearityThreshold', 66),
        )
        biorientation_green_split_enabled_raw = request.POST.get(
            'biorientationGreenSplitEnabled',
            request.session.get('biorientationGreenSplitEnabled', 'True'),
        )
        puncta_line_mode = normalize_puncta_line_mode(
            request.POST.get(
                "puncta_line_mode",
                request.session.get("puncta_line_mode", DEFAULT_PUNCTA_LINE_MODE),
            ),
            default=DEFAULT_PUNCTA_LINE_MODE,
        )
        nuclear_cell_pair_mode = request.POST.get(
            "nuclear_cell_pair_mode",
            request.POST.get("nuclear_cellular_mode", request.session.get("nuclear_cell_pair_mode", request.session.get("nuclear_cellular_mode", "green_nucleus"))),
        )
        if nuclear_cell_pair_mode not in NUCLEAR_CELL_PAIR_MODES:
            nuclear_cell_pair_mode = "green_nucleus"
        green_contour_filter_enabled_raw = request.POST.get(
            'greenContourFilterEnabled',
            request.session.get('greenContourFilterEnabled', request.session.get('gfpFilterEnabled', 'False')),
        )
        green_contour_filter_enabled = green_contour_filter_enabled_raw == 'true'
        alternate_red_detection_raw = request.POST.get(
            'alternateRedDetection',
            request.session.get('alternateRedDetection', request.session.get('alternateMCherryDetection', 'False')),
        )
        alternate_red_detection = alternate_red_detection_raw == 'true'
        try:
            puncta_line_width = int(puncta_line_width_raw)
        except (TypeError, ValueError):
            puncta_line_width = 1
        if puncta_line_width < 1:
            puncta_line_width = 1
        try:
            cen_dot_distance = int(cen_dot_distance_raw)
        except (TypeError, ValueError):
            cen_dot_distance = 37
        if cen_dot_distance < 0:
            cen_dot_distance = 37
        try:
            biorientation_red_min_distance_value = float(
                biorientation_red_min_distance_value_raw
            )
        except (TypeError, ValueError):
            biorientation_red_min_distance_value = 0.0
        if biorientation_red_min_distance_value < 0:
            biorientation_red_min_distance_value = 0.0
        try:
            biorientation_red_max_distance_value = float(
                biorientation_red_max_distance_value_raw
            )
        except (TypeError, ValueError):
            biorientation_red_max_distance_value = 37.0
        if biorientation_red_max_distance_value < 0:
            biorientation_red_max_distance_value = 37.0
        biorientation_red_min_distance_unit = normalize_length_unit(
            biorientation_red_min_distance_unit_raw,
            default="px",
        )
        biorientation_red_max_distance_unit = normalize_length_unit(
            biorientation_red_max_distance_unit_raw,
            default="px",
        )
        try:
            biorientation_collinearity_threshold = int(
                biorientation_collinearity_threshold_raw
            )
        except (TypeError, ValueError):
            biorientation_collinearity_threshold = 66
        if biorientation_collinearity_threshold < 0:
            biorientation_collinearity_threshold = 66
        biorientation_green_split_enabled = (
            biorientation_green_split_enabled_raw
            if isinstance(biorientation_green_split_enabled_raw, bool)
            else str(biorientation_green_split_enabled_raw).strip().lower()
            in {"1", "true", "yes", "on"}
        )

        request.session['selected_analysis'] = selected_analysis
        request.session['punctaLineWidth'] = puncta_line_width
        request.session['cenDotDistance'] = cen_dot_distance
        request.session['stats_biorientation_red_min_distance_value'] = biorientation_red_min_distance_value
        request.session['stats_biorientation_red_min_distance_unit'] = biorientation_red_min_distance_unit
        request.session['stats_biorientation_red_max_distance_value'] = biorientation_red_max_distance_value
        request.session['stats_biorientation_red_max_distance_unit'] = biorientation_red_max_distance_unit
        request.session['biorientationCollinearityThreshold'] = biorientation_collinearity_threshold
        request.session['biorientationGreenSplitEnabled'] = biorientation_green_split_enabled
        request.session["puncta_line_mode"] = puncta_line_mode
        request.session["nuclear_cell_pair_mode"] = nuclear_cell_pair_mode
        request.session['greenContourFilterEnabled'] = green_contour_filter_enabled
        request.session['alternateRedDetection'] = alternate_red_detection
        context = build_analysis_batch_context(request, uuid_list)
        batch_key = context.batch_key
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        _track_progress_batch(request, batch_key)

        def cancel_response():
            _delete_cancelled_runs(request, list(context.run_uuids))
            if is_ajax:
                return JsonResponse({"status": "cancelled"}, status=409)
            return HttpResponse("Cancelled", status=409)

        def storage_full_response(exc: Exception):
            log_storage_capacity_failure(
                stage="preprocess_pipeline",
                user=request.user,
                uuids=context.run_uuids,
                exc=exc,
            )
            for cleanup_uuid in context.run_uuids:
                cleanup_failed_processing_artifacts(cleanup_uuid)
            progress = AnalysisProgressHandle(batch_key)
            progress.clear_cancel()
            progress.set_phase("Idle", status="idle")
            _release_progress_batch(request, batch_key)
            messages.error(request, PROCESSING_STORAGE_FULL_MESSAGE)
            if is_ajax:
                return JsonResponse({"error": PROCESSING_STORAGE_FULL_MESSAGE}, status=507)
            return redirect("pre_process", uuids=batch_key)

        if context.execution_mode == "worker":
            transient_uuids = {
                str(value)
                for value in request.session.get("transient_experiment_uuids", [])
                if str(value)
            }
            transient_uuids.update(context.run_uuids)
            request.session["transient_experiment_uuids"] = sorted(transient_uuids)
            request.session.modified = True

            job, created = enqueue_analysis_job(
                user_id=request.user.id,
                raw_uuids=context.run_uuids,
                config_snapshot=context.config_snapshot,
            )
            progress = AnalysisProgressHandle(batch_key, job=job)
            progress.clear_cancel()
            if created:
                progress.set_phase("Queued", status="queued")

            payload = {
                "status": "queued",
                "phase": "Queued",
                "redirect": reverse("display", kwargs={"uuids": batch_key}),
            }
            if is_ajax:
                return JsonResponse(payload)
            return redirect("pre_process", uuids=batch_key)

        progress = AnalysisProgressHandle(batch_key)
        progress.clear_cancel()
        try:
            # Sync mode must complete the full batch in this POST so the UI does not
            # hand off expensive work to a hidden redirect-followed segment request.
            result = run_analysis_batch(
                user=request.user,
                context=context,
                progress=progress,
                preprocess_fn=preprocess_images,
                predict_fn=predict_images,
            )
        except AnalysisCancelled:
            return cancel_response()
        except Exception as exc:
            if is_storage_full_error(exc):
                return storage_full_response(exc)
            logger.exception(
                "Preprocess sync analysis failed for progress ref %s",
                progress_log_ref(batch_key),
            )
            _release_progress_batch(request, batch_key)
            if is_ajax:
                return JsonResponse({"error": SAFE_ANALYSIS_FAILURE_SUMMARY}, status=500)
            messages.error(request, SAFE_ANALYSIS_FAILURE_SUMMARY)
            return redirect("pre_process", uuids=batch_key)

        _finalize_terminal_progress_batch(request, batch_key, list(context.run_uuids))
        payload = {
            "status": PROGRESS_STATUS_SUCCEEDED,
            "phase": "Completed",
            "redirect": reverse("display", kwargs={"uuids": batch_key}),
        }
        if result.storage_warning_message:
            payload["storage_warning_message"] = result.storage_warning_message
            messages.warning(request, result.storage_warning_message)
        if is_ajax:
            return JsonResponse(payload)
        return redirect("display", uuids=batch_key)

    # AJAX navigation
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'images': [
                {'file_location': {'url': img.file_location.url}}
                for img in preview_images
            ],
            'file_name': uploaded_image.name,
            'current_file_index': current_file_index,
        })

    # Normal render
    return TemplateResponse(request, "pre_process.html", {
        'images': preview_images,
        'file_name': uploaded_image.name,
        'current_file_index': current_file_index,
        'total_files': total_files,
        'uuids': uuids,
        'file_list': file_list,
        'show_saved_file_channels': show_saved_file_channels,
        'show_saved_file_scales': show_saved_file_scales,
        'sidebar_starts_open': sidebar_starts_open,
        'default_spatial_stats_unit': default_spatial_stats_unit,
        'analysis_execution_mode': analysis_execution_mode,
        'sidebar_spatial_stats_unit': sidebar_spatial_stats_unit,
        'has_selected_stats': bool(request.session.get('selected_analysis', [])),
        'file_scale_map_json': json.dumps(
            {
                item["uuid"]: item["scale"]["effective_um_per_px"]
                for item in file_list
            }
        ),
    })

@require_POST
def set_progress(request, key):
    try:
        body = json.loads(request.body or '{}')
    except (TypeError, ValueError, json.JSONDecodeError):
        return _progress_write_error_response(
            SAFE_PROGRESS_WRITE_ERROR_MESSAGE,
            status_code=400,
        )
    try:
        batch_key, _ = _resolve_owned_progress_batch(request, key)
        phase = normalize_progress_phase(body.get("phase"))
        status = validate_progress_status(body.get("status"))
        if phase is None:
            raise ProgressRequestError("Invalid progress phase.", status_code=400)
        if body.get("status") is not None and status is None:
            raise ProgressRequestError("Invalid progress status.", status_code=400)
        progress = AnalysisProgressHandle(batch_key)
        progress.set_phase(phase, status=status)
        return JsonResponse({"status": "ok"})
    except ProgressRequestError as exc:
        return _progress_write_error_response(
            SAFE_PROGRESS_WRITE_ERROR_MESSAGE,
            status_code=exc.status_code,
        )
    except Exception:
        logger.exception("Progress write failed")
        return _progress_write_error_response(
            SAFE_PROGRESS_WRITE_ERROR_MESSAGE,
            status_code=500,
        )


@csrf_protect
@require_POST
def cancel_progress(request, uuids):
    try:
        batch_key, uuid_list = _resolve_owned_progress_batch(request, uuids)
        reap_stale_analysis_jobs(user_id=request.user.id, batch_key=batch_key)
        snapshot = get_progress_snapshot(batch_key=batch_key, user_id=request.user.id)
        if snapshot.status in {"idle", "succeeded", "failed", "cancelled"}:
            _delete_cancelled_runs(request, uuid_list)
            progress = AnalysisProgressHandle(batch_key)
            progress.clear_cancel()
            progress.set_phase("Cancelled", status="cancelled")
            return JsonResponse({"status": "cancelled"})
        job = get_active_analysis_job(user_id=request.user.id, batch_key=batch_key)
        progress = AnalysisProgressHandle(batch_key, job=job)
        progress.request_cancel()
        progress.set_phase("Cancelling", status="cancelling")
        return JsonResponse({"status": "cancelling"})
    except ProgressRequestError as exc:
        return _progress_write_error_response(
            SAFE_PROGRESS_WRITE_ERROR_MESSAGE,
            status_code=exc.status_code,
        )
    except Exception:
        logger.exception("Progress cancel failed")
        return _progress_write_error_response(
            SAFE_PROGRESS_WRITE_ERROR_MESSAGE,
            status_code=500,
        )


@require_POST
@csrf_exempt
def update_channel_order(request, uuid):
    """
    POST {order: ["DIC","channel_blue","channel_red","channel_green"]}
    → overwrite channel_config.json in MEDIA_ROOT/<uuid>/
    """
    try:
        data = json.loads(request.body)
        new_order = data.get('order', [])
        expected = set(CHANNEL_ROLE_ORDER)
        if set(new_order) != expected:
            return JsonResponse({'error': 'invalid channel list'}, status=400)

        # new: 0–3 mapping to match your layer filenames
        mapping = {ch: i for i, ch in enumerate(new_order)}


        cfg_path = Path(MEDIA_ROOT) / uuid / 'channel_config.json'
        if not cfg_path.exists():
            return JsonResponse({'error': 'config not found'}, status=404)

        # SAVE: overwrite the JSON file with new mapping
        cfg_path.write_text(json.dumps(mapping))
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
