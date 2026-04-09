from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.template.response import TemplateResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.urls import reverse
import math
from uuid import UUID

from core.models import UploadedImage, get_guest_user
from core.services.analysis_context import build_analysis_batch_context, build_batch_key
from core.services.analysis_exceptions import AnalysisCancelled
from core.services.analysis_jobs import enqueue_analysis_job, get_active_analysis_job
from core.services.analysis_pipeline import run_preprocess_and_inference_batch
from core.services.analysis_progress import AnalysisProgressHandle, get_progress_snapshot
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

from cytocv.settings import MEDIA_ROOT
from pathlib import Path
import json
import re

from accounts.preferences import get_user_preferences
from core.scale import (
    apply_manual_override_scale,
    clear_manual_override_scale,
    get_scale_sidebar_payload,
)
from core.mrcnn.my_inference import predict_images
from core.mrcnn.preprocess_images import preprocess_images
from core.services.artifact_storage import (
    cleanup_failed_processing_artifacts,
    delete_uploaded_run_by_uuid,
    ensure_preview_assets,
    is_storage_full_error,
    log_storage_capacity_failure,
    sweep_user_run_artifacts,
)

NUCLEAR_CELLULAR_MODES = {"green_nucleus", "red_nucleus"}
PROCESSING_STORAGE_FULL_MESSAGE = (
    "Files could not be saved because storage is full. Free up space and try again."
)


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
        # Basic validation: non-empty and only hex/commas/dashes
        if not uuids or not re.fullmatch(r"[0-9a-fA-F,-]+", uuids):
            return JsonResponse({"phase": "Idle", "status": "idle"})
        batch_key = build_batch_key(uuids)
        snapshot = get_progress_snapshot(batch_key=batch_key, user_id=request.user.id)
        if snapshot.status in {"succeeded", "failed", "cancelled"}:
            sync_transient_run_session_state(request, batch_key.split(","))
        return JsonResponse(
            {
                "phase": snapshot.phase,
                "status": snapshot.status,
                "failure_summary": snapshot.failure_summary,
                "redirect": reverse("display", kwargs={"uuids": batch_key}),
            }
        )
    except Exception:
        return JsonResponse({"phase": "Idle", "status": "idle"})


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
        red_line_width_raw = request.POST.get(
            'redLineWidth',
            request.session.get('redLineWidth', request.session.get('mCherryWidth', 1)),
        )
        cen_dot_distance_raw = request.POST.get(
            'cenDotDistance',
            request.session.get('cenDotDistance', request.session.get('distance', 37)),
        )
        cen_dot_collinearity_threshold_raw = request.POST.get(
            'cenDotCollinearityThreshold',
            request.session.get(
                'cenDotCollinearityThreshold',
                request.session.get('threshold', 66),
            ),
        )
        puncta_line_mode = normalize_puncta_line_mode(
            request.POST.get(
                "puncta_line_mode",
                request.session.get("puncta_line_mode", DEFAULT_PUNCTA_LINE_MODE),
            ),
            default=DEFAULT_PUNCTA_LINE_MODE,
        )
        nuclear_cellular_mode = request.POST.get(
            "nuclear_cellular_mode",
            request.session.get("nuclear_cellular_mode", "green_nucleus"),
        )
        if nuclear_cellular_mode not in NUCLEAR_CELLULAR_MODES:
            nuclear_cellular_mode = "green_nucleus"
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
            red_line_width = int(red_line_width_raw)
        except (TypeError, ValueError):
            red_line_width = 1
        if red_line_width < 1:
            red_line_width = 1
        try:
            cen_dot_distance = int(cen_dot_distance_raw)
        except (TypeError, ValueError):
            cen_dot_distance = 37
        if cen_dot_distance < 0:
            cen_dot_distance = 37
        try:
            cen_dot_collinearity_threshold = int(cen_dot_collinearity_threshold_raw)
        except (TypeError, ValueError):
            cen_dot_collinearity_threshold = 66
        if cen_dot_collinearity_threshold < 0:
            cen_dot_collinearity_threshold = 66

        request.session['selected_analysis'] = selected_analysis
        request.session['redLineWidth'] = red_line_width
        request.session['cenDotDistance'] = cen_dot_distance
        request.session['cenDotCollinearityThreshold'] = cen_dot_collinearity_threshold
        request.session["puncta_line_mode"] = puncta_line_mode
        request.session["nuclear_cellular_mode"] = nuclear_cellular_mode
        request.session['greenContourFilterEnabled'] = green_contour_filter_enabled
        request.session['alternateRedDetection'] = alternate_red_detection
        context = build_analysis_batch_context(request, uuid_list)
        batch_key = context.batch_key
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

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
            run_preprocess_and_inference_batch(
                user=request.user,
                context=context,
                progress=progress,
                preprocess_fn=preprocess_images,
                predict_fn=predict_images,
            )
        except AnalysisCancelled:
            return cancel_response()
        except Exception as exc:
            if not is_storage_full_error(exc):
                raise
            return storage_full_response(exc)

        return redirect("experiment_segment", uuids=batch_key)

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
    except Exception:
        body = {}
    phase = body.get('phase', 'idle')
    status = body.get('status')
    try:
        batch_key = build_batch_key(key) if re.fullmatch(r"[0-9a-fA-F,-]+", key) else key
        progress = AnalysisProgressHandle(batch_key)
        progress.set_phase(str(phase), status=str(status) if status else None)
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_protect
@require_POST
def cancel_progress(request, uuids):
    try:
        if not uuids or not re.fullmatch(r"[0-9a-fA-F,-]+", uuids):
            return JsonResponse({"status": "invalid"}, status=400)
        batch_key = build_batch_key(uuids)
        uuid_list = [value for value in batch_key.split(",") if value]
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
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


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
