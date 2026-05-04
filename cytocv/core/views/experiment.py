from django.shortcuts import render, redirect
import logging
from core.forms import UploadImageForm
from core.models import UploadedImage, UploadPreparationJob, get_guest_user
from pathlib import Path
import uuid
import json
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from ..stats_plugins import (
    CHANNEL_ORDER,
    build_plugin_ui_payload,
    build_requirement_summary,
    normalize_selected_plugins,
)
import uuid as uuid_lib
from accounts.access_policy import (
    build_upload_limit_error_lines,
    get_access_policy_for_user,
)
from accounts.preferences import (
    PreferenceValidationError,
    build_experiment_defaults_from_popup_payload,
    get_user_preferences,
    update_user_preferences,
)
from core.scale import (
    DEFAULT_MICRONS_PER_PIXEL,
    convert_length_to_pixels,
    normalize_length_unit,
    parse_microns_per_pixel,
)
from core.services.biorientation_config import (
    DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX,
)
from core.services.puncta_line_mode import (
    DEFAULT_PUNCTA_LINE_MODE,
    normalize_puncta_line_mode,
)
from core.services.green_dot_split import (
    DEFAULT_GREEN_DOT_SPLIT_MODE,
    normalize_green_dot_split_mode,
)
from core.services.signal_quantification import (
    resolve_signal_quantification_selection,
)
from core.services.artifact_storage import (
    delete_uploaded_run_by_uuid,
    get_user_storage_projection,
    is_storage_full_error,
    log_storage_capacity_failure,
    sweep_user_run_artifacts,
)
from core.services.analysis_context import normalize_execution_mode
from core.services.analysis_progress import normalize_progress_detail
from core.services.upload_preparation import run_upload_preparation_job
from core.services.upload_preparation_jobs import (
    ACTIVE_UPLOAD_PREPARATION_STATUSES,
    enqueue_upload_preparation_job,
    finalize_upload_preparation_job,
    get_stale_upload_preparation_terminal_state,
    get_upload_preparation_job_for_user,
    get_upload_preparation_jobs_for_user,
    reap_stale_upload_preparation_jobs,
    request_upload_preparation_cancellation,
    start_inline_upload_preparation_job,
)

NUCLEAR_CELL_PAIR_MODES = {"green_nucleus", "red_nucleus"}
PROCESSING_STORAGE_FULL_MESSAGE = (
    "Files could not be saved because storage is full. Free up space and try again."
)
RECENT_UPLOAD_PREPARATION_SESSION_KEY = "recent_upload_preparation_job_uuids"
RECENT_UPLOAD_PREPARATION_SESSION_LIMIT = 10
logger = logging.getLogger(__name__)


def _parse_bool(value, default=False):
    """Parse a POST boolean value with a safe default."""

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _upload_job_detail(job: UploadPreparationJob) -> dict[str, object]:
    return normalize_progress_detail(job.progress_detail)


def _recent_upload_preparation_job_uuids(request) -> list[str]:
    """Return the normalized recent upload-preparation job UUID list for this session."""

    return _parse_restore_uuids(request.session.get(RECENT_UPLOAD_PREPARATION_SESSION_KEY, []))


def _set_recent_upload_preparation_job_uuids(request, job_uuids: list[str]) -> None:
    """Persist recent upload-preparation job UUIDs back into the session."""

    normalized = _parse_restore_uuids(job_uuids)
    if normalized:
        request.session[RECENT_UPLOAD_PREPARATION_SESSION_KEY] = normalized[
            -RECENT_UPLOAD_PREPARATION_SESSION_LIMIT:
        ]
    else:
        request.session.pop(RECENT_UPLOAD_PREPARATION_SESSION_KEY, None)
    request.session.modified = True


def _remember_upload_preparation_job(request, job_uuid: str) -> None:
    """Append one upload-preparation job UUID to the recent session list."""

    existing = [value for value in _recent_upload_preparation_job_uuids(request) if value != job_uuid]
    existing.append(job_uuid)
    _set_recent_upload_preparation_job_uuids(request, existing)


def _forget_upload_preparation_job(request, job_uuid: str) -> None:
    """Remove one upload-preparation job UUID from the recent session list."""

    existing = _recent_upload_preparation_job_uuids(request)
    next_values = [value for value in existing if value != job_uuid]
    if next_values == existing:
        return
    _set_recent_upload_preparation_job_uuids(request, next_values)


def _build_upload_preparation_payload(
    request,
    job: UploadPreparationJob,
    *,
    stale_state: tuple[str, str, str] | None = None,
) -> dict[str, object]:
    """Serialize one upload-preparation job for APIs and resume bootstrapping."""

    status = stale_state[0] if stale_state is not None else job.status
    phase = stale_state[1] if stale_state is not None else job.current_phase
    failure_summary = stale_state[2] if stale_state is not None else job.failure_summary
    errors = [str(line) for line in job.error_lines or [] if str(line)]
    if failure_summary and not errors and status == UploadPreparationJob.Status.FAILED:
        errors = [failure_summary]

    redirect_url = None
    if status == UploadPreparationJob.Status.SUCCEEDED and job.valid_run_uuids:
        valid_uuids = [str(value) for value in job.valid_run_uuids if str(value)]
        request.session["last_experiment_uuids"] = valid_uuids
        request.session.modified = True
        redirect_url = reverse("pre_process", kwargs={"uuids": ",".join(valid_uuids)})

    return {
        "job_uuid": str(job.job_uuid),
        "status": status,
        "phase": phase,
        "detail": _upload_job_detail(job),
        "errors": errors,
        "failure_summary": failure_summary,
        "redirect": redirect_url,
    }


def _resolve_upload_preparation_resume_payload(request) -> dict[str, object] | None:
    """Return the newest resumable upload-preparation payload for this session."""

    recent_job_uuids = _recent_upload_preparation_job_uuids(request)
    if not recent_job_uuids:
        return None

    jobs_by_uuid = {
        str(job.job_uuid): job
        for job in get_upload_preparation_jobs_for_user(
            user_id=request.user.id,
            job_uuids=recent_job_uuids,
        )
    }
    existing_job_uuids = [value for value in recent_job_uuids if value in jobs_by_uuid]

    selected_payload = None
    consume_job_uuid = None
    for job_uuid in reversed(existing_job_uuids):
        job = jobs_by_uuid[job_uuid]
        stale_state = get_stale_upload_preparation_terminal_state(job)
        selected_payload = _build_upload_preparation_payload(
            request,
            job,
            stale_state=stale_state,
        )
        effective_status = selected_payload["status"]
        if effective_status in {
            UploadPreparationJob.Status.QUEUED,
            UploadPreparationJob.Status.RUNNING,
            UploadPreparationJob.Status.CANCELLING,
        }:
            break
        consume_job_uuid = job_uuid
        break

    if existing_job_uuids != recent_job_uuids or consume_job_uuid is not None:
        next_job_uuids = [
            value for value in existing_job_uuids if value != consume_job_uuid
        ]
        _set_recent_upload_preparation_job_uuids(request, next_job_uuids)

    return selected_payload


def _parse_positive_float(value, default: float, minimum: float = 0.0) -> float:
    """Parse a positive float with default fallback."""

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum:
        return default
    return parsed


def _normalize_length_unit(value, default: str = "px") -> str:
    """Normalize incoming length unit to px/um."""

    return normalize_length_unit(value, default=default)


def _convert_length_to_pixels(
    raw_value: float,
    unit: str,
    *,
    minimum_px: int,
    fallback_px: int,
    microns_per_pixel: float,
) -> int:
    """Convert a length value to pixels with validation and fallback."""
    return convert_length_to_pixels(
        raw_value,
        unit,
        minimum_px=minimum_px,
        fallback_px=fallback_px,
        um_per_px=microns_per_pixel,
    )


def _parse_channels(raw_values) -> set[str]:
    """Parse channel values from either list or comma-delimited payload."""

    if raw_values is None:
        return set()
    if isinstance(raw_values, str):
        values = [part.strip() for part in raw_values.split(",")]
    else:
        values = []
        for item in raw_values:
            if not isinstance(item, str):
                continue
            values.extend(part.strip() for part in item.split(","))
    allowed = set(CHANNEL_ORDER)
    return {value for value in values if value in allowed}


def _parse_nuclear_cell_pair_mode(value: str | None, default: str = "green_nucleus") -> str:
    """Parse nucleus contour mode for Nuclear/Cell-Pair intensity analysis."""

    raw = str(value or "").strip()
    return raw if raw in NUCLEAR_CELL_PAIR_MODES else default


def _parse_puncta_line_mode(
    value: str | None,
    default: str = DEFAULT_PUNCTA_LINE_MODE,
) -> str:
    """Parse puncta-line mode for PunctaDistance."""

    return normalize_puncta_line_mode(value, default=default)


def _parse_restore_uuids(raw_values) -> list[str]:
    """Parse UUID values from list or comma-delimited payload preserving order."""

    if raw_values is None:
        return []
    if isinstance(raw_values, str):
        values = [part.strip() for part in raw_values.split(",")]
    else:
        values = []
        for item in raw_values:
            if not isinstance(item, str):
                continue
            values.extend(part.strip() for part in item.split(","))

    parsed: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        try:
            normalized = str(uuid_lib.UUID(value))
        except (TypeError, ValueError, AttributeError):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        parsed.append(normalized)
    return parsed


def _current_owner_filter(request) -> dict:
    """Return queryset filter args for the current upload owner."""

    if request.user.is_authenticated:
        return {"user": request.user}
    return {"user_id": get_guest_user()}


def _upload_view_context(
    *,
    form,
    progress_key,
    error=None,
    restored_queue_items=None,
    user_preference_defaults=None,
    upload_quota_payload=None,
    upload_access_policy_payload=None,
    upload_resume_payload=None,
):
    """Build template context for the upload page."""

    context = {
        "form": form,
        "progress_key": progress_key,
        "stats_plugin_payload_json": json.dumps(build_plugin_ui_payload()),
        "restored_queue_payload_json": json.dumps(restored_queue_items or []),
        "user_preference_defaults_json": json.dumps(user_preference_defaults or {}),
        "upload_quota_payload_json": json.dumps(upload_quota_payload or {}),
        "upload_access_policy_payload_json": json.dumps(upload_access_policy_payload or {}),
        "upload_resume_payload_json": json.dumps(upload_resume_payload or {}),
        "upload_batch_target_bytes": int(getattr(settings, "UPLOAD_BATCH_TARGET_BYTES", 80 * 1024 * 1024)),
        "upload_preparation_execution_mode": normalize_execution_mode(),
    }
    if error:
        context["error"] = error
    return context


def _create_upload_preparation_job_for_mode(
    *,
    user_id: int,
    new_run_uuids: list[str],
    restored_run_uuids: list[str],
    config_snapshot: dict[str, object],
) -> UploadPreparationJob:
    """Create or run upload preparation according to CYTOCV_ANALYSIS_EXECUTION_MODE."""

    execution_mode = normalize_execution_mode()
    snapshot = {
        **config_snapshot,
        "upload_preparation_execution_mode": execution_mode,
    }
    if execution_mode == "sync":
        job = start_inline_upload_preparation_job(
            user_id=user_id,
            new_run_uuids=new_run_uuids,
            restored_run_uuids=restored_run_uuids,
            config_snapshot=snapshot,
        )
        return run_upload_preparation_job(job)

    return enqueue_upload_preparation_job(
        user_id=user_id,
        new_run_uuids=new_run_uuids,
        restored_run_uuids=restored_run_uuids,
        config_snapshot=snapshot,
    )


def _track_active_upload_preparation_job(request, job: UploadPreparationJob) -> None:
    if job.status in ACTIVE_UPLOAD_PREPARATION_STATUSES:
        _remember_upload_preparation_job(request, str(job.job_uuid))
    else:
        _forget_upload_preparation_job(request, str(job.job_uuid))


def _build_upload_quota_payload(user, user_preferences: dict | None = None) -> dict[str, object]:
    """Build predictive autosave quota data for the upload queue UI."""

    preferences = user_preferences or {}
    storage_projection = get_user_storage_projection(user)
    return {
        "is_authenticated": bool(getattr(user, "is_authenticated", False)),
        "auto_save_experiments": bool(preferences.get("auto_save_experiments", True)),
        "used_storage": int(storage_projection.get("used_storage", 0) or 0),
        "available_storage": int(storage_projection.get("available_storage", 0) or 0),
        "total_storage": int(storage_projection.get("total_storage", 0) or 0),
        "average_saved_run_bytes": float(
            storage_projection.get("average_saved_run_bytes", 0.0) or 0.0
        ),
        "additional_files_possible": int(
            storage_projection.get("additional_files_possible", 0) or 0
        ),
        "projection_ready": bool(storage_projection.get("projection_ready", False)),
    }


def _build_upload_access_policy_payload(user) -> dict[str, object]:
    """Build upload/access tier data for browser-side preflight validation."""

    access_policy = get_access_policy_for_user(user)
    return {
        "tier": access_policy.tier,
        "is_unrestricted": access_policy.is_unrestricted,
        "upload_max_files": access_policy.upload_max_files,
        "analysis_max_active_jobs": access_policy.analysis_max_active_jobs,
        "upload_limit_message": access_policy.upload_limit_message,
        "analysis_limit_message": access_policy.analysis_limit_message,
    }


def _upload_limit_error_response(
    request,
    *,
    access_policy,
    requested_files: int,
    is_ajax: bool,
    redirect_path: str,
):
    """Return a user-facing response for a blocked upload-preparation submission."""

    errors = build_upload_limit_error_lines(
        access_policy,
        requested_files=requested_files,
    )
    if is_ajax:
        return JsonResponse({"errors": errors}, status=400)
    for line in errors:
        messages.error(request, line)
    return redirect(redirect_path)


def _getlist(payload, key: str) -> list[str]:
    if hasattr(payload, "getlist"):
        return list(payload.getlist(key))
    value = payload.get(key) if isinstance(payload, dict) else None
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _has_payload_key(payload, key: str) -> bool:
    try:
        return key in payload
    except TypeError:
        return False


def _parse_experiment_submission(payload, user_preferences: dict) -> tuple[dict[str, object], dict[str, object]]:
    """Parse upload settings once for session persistence and worker execution."""

    experiment_defaults = user_preferences.get("experiment_defaults", {})
    default_microns_per_pixel = parse_microns_per_pixel(
        experiment_defaults.get("microns_per_pixel"),
        default=DEFAULT_MICRONS_PER_PIXEL,
    )
    default_use_metadata_scale = bool(experiment_defaults.get("use_metadata_scale", True))

    has_selected_analysis_payload = _has_payload_key(payload, "selected_analysis")
    raw_selected_analysis = normalize_selected_plugins(_getlist(payload, "selected_analysis"))

    posted_microns_per_pixel = parse_microns_per_pixel(
        payload.get("stats_microns_per_pixel"),
        default=default_microns_per_pixel,
    )
    stats_use_metadata_scale = _parse_bool(
        payload.get("stats_use_metadata_scale"),
        default=default_use_metadata_scale,
    )
    puncta_line_width_unit = _normalize_length_unit(
        payload.get(
            "stats_puncta_line_width_unit",
            payload.get("stats_red_line_width_unit", payload.get("stats_mcherry_width_unit")),
        ),
        default="px",
    )
    cen_dot_distance_unit = _normalize_length_unit(
        payload.get("stats_cen_dot_distance_unit", payload.get("stats_gfp_distance_unit")),
        default="px",
    )
    cen_dot_proximity_radius_unit = _normalize_length_unit(
        payload.get("stats_cen_dot_proximity_radius_unit"),
        default="px",
    )

    has_raw_puncta_line_width = (
        "stats_puncta_line_width_value" in payload
        or "stats_red_line_width_value" in payload
        or "stats_mcherry_width_value" in payload
    )
    has_raw_cen_dot_distance = (
        "stats_cen_dot_distance_value" in payload
        or "stats_gfp_distance_value" in payload
    )
    has_raw_cen_dot_proximity_radius = "stats_cen_dot_proximity_radius_value" in payload
    puncta_line_source_unit = puncta_line_width_unit if has_raw_puncta_line_width else "px"
    cen_dot_source_unit = cen_dot_distance_unit if has_raw_cen_dot_distance else "px"
    cen_dot_proximity_radius_source_unit = cen_dot_proximity_radius_unit if has_raw_cen_dot_proximity_radius else "px"

    puncta_line_width_value = _parse_positive_float(
        payload.get(
            "stats_puncta_line_width_value",
            payload.get(
                "stats_red_line_width_value",
                payload.get("punctaLineWidth", payload.get("redLineWidth", payload.get("mCherryWidth", "1"))),
            ),
        ),
        default=1,
        minimum=0,
    )
    cen_dot_distance_value = _parse_positive_float(
        payload.get(
            "stats_cen_dot_distance_value",
            payload.get("stats_gfp_distance_value", payload.get("cenDotDistance", payload.get("distance", "37"))),
        ),
        default=37,
        minimum=0,
    )
    cen_dot_proximity_radius_value = _parse_positive_float(
        payload.get(
            "stats_cen_dot_proximity_radius_value",
            payload.get("cenDotProximityRadius", "13"),
        ),
        default=13,
        minimum=0,
    )

    puncta_line_width = _convert_length_to_pixels(
        puncta_line_width_value,
        puncta_line_source_unit,
        minimum_px=1,
        fallback_px=1,
        microns_per_pixel=posted_microns_per_pixel,
    )
    cen_dot_distance = _convert_length_to_pixels(
        cen_dot_distance_value,
        cen_dot_source_unit,
        minimum_px=0,
        fallback_px=37,
        microns_per_pixel=posted_microns_per_pixel,
    )
    cen_dot_proximity_radius = _convert_length_to_pixels(
        cen_dot_proximity_radius_value,
        cen_dot_proximity_radius_source_unit,
        minimum_px=0,
        fallback_px=13,
        microns_per_pixel=posted_microns_per_pixel,
    )

    def _parse_float_value(key: str, default: float) -> float:
        try:
            parsed = float(payload.get(key, default))
        except (TypeError, ValueError):
            return default
        return parsed if parsed >= 0 else default

    biorientation_red_min_distance_value = _parse_float_value("biorientationRedMinDistance", 0.0)
    biorientation_red_max_distance_value = _parse_float_value("biorientationRedMaxDistance", 37.0)
    biorientation_red_min_distance_unit = _normalize_length_unit(
        payload.get("biorientationRedMinDistanceUnit", "px")
    )
    biorientation_red_max_distance_unit = _normalize_length_unit(
        payload.get("biorientationRedMaxDistanceUnit", "px")
    )
    try:
        biorientation_collinearity_threshold = int(
            payload.get(
                "biorientationCollinearityThreshold",
                str(DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX),
            )
        )
    except (TypeError, ValueError):
        biorientation_collinearity_threshold = DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX
    if biorientation_collinearity_threshold < 0:
        biorientation_collinearity_threshold = DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX

    green_dot_split_enabled = _parse_bool(
        payload.get("greenDotSplitEnabled", payload.get("biorientationGreenSplitEnabled")),
        default=True,
    )
    green_dot_split_mode = normalize_green_dot_split_mode(
        payload.get("greenDotSplitMode", DEFAULT_GREEN_DOT_SPLIT_MODE)
    )
    green_contour_filter_enabled = _parse_bool(
        payload.get(
            "greenContourFilterEnabled",
            payload.get("gfpFilterEnabled", False),
        ),
        default=False,
    )
    puncta_line_mode = _parse_puncta_line_mode(
        payload.get("puncta_line_mode"),
        default=DEFAULT_PUNCTA_LINE_MODE,
    )
    nuclear_cell_pair_mode = _parse_nuclear_cell_pair_mode(
        payload.get("nuclear_cell_pair_mode", payload.get("nuclear_cellular_mode")),
        default="green_nucleus",
    )
    signal_selection = resolve_signal_quantification_selection(
        payload={
            "signal_quantification_enabled": payload.get(
                "signalQuantificationEnabled",
                payload.get("signal_quantification_enabled"),
            ),
            "signal_quantification_mode": payload.get(
                "signalQuantificationMode",
                payload.get("signal_quantification_mode"),
            ),
            "puncta_contour_intensity_enabled": payload.get(
                "punctaContourIntensityEnabled",
                payload.get("puncta_contour_intensity_enabled"),
            ),
            "alternate_nucleus_detection_enabled": payload.get(
                "alternateNucleusDetectionEnabled",
                payload.get(
                    "alternate_nucleus_detection_enabled",
                    payload.get(
                        "alternateRedDetection",
                        payload.get("alternateMCherryDetection"),
                    ),
                ),
            ),
        },
        selected_plugins=raw_selected_analysis,
        nuclear_cell_pair_mode=nuclear_cell_pair_mode,
        puncta_line_mode=puncta_line_mode,
        default_enabled=(
            None
            if has_selected_analysis_payload
            else experiment_defaults.get("signal_quantification_enabled")
        ),
        default_mode=(
            None
            if has_selected_analysis_payload
            else experiment_defaults.get("signal_quantification_mode")
        ),
        default_puncta_contour_intensity_enabled=(
            None
            if has_selected_analysis_payload
            else experiment_defaults.get("puncta_contour_intensity_enabled")
        ),
        default_alternate_nucleus_detection_enabled=experiment_defaults.get(
            "alternate_nucleus_detection_enabled",
            experiment_defaults.get("alternate_red_detection", False),
        ),
    )
    selected_analysis = list(signal_selection.selected_plugins)
    requirement_summary = build_requirement_summary(selected_analysis)

    module_enabled = _parse_bool(payload.get("cytocv_analysis_enabled"), default=False)
    enforce_layer_count = module_enabled and _parse_bool(
        payload.get("enforce_layer_count"),
        default=False,
    )
    enforce_wavelengths = module_enabled and _parse_bool(
        payload.get("enforce_wavelengths"),
        default=False,
    )
    extra_required_channels = _parse_channels(_getlist(payload, "extra_required_channels"))
    required_channels = set(requirement_summary["required_channels"])
    if module_enabled:
        required_channels.update(extra_required_channels)

    session_values = {
        "selected_analysis": requirement_summary["selected_plugins"],
        "punctaLineWidth": puncta_line_width,
        "cenDotDistance": cen_dot_distance,
        "cenDotProximityRadius": cen_dot_proximity_radius,
        "stats_puncta_line_width_unit": puncta_line_width_unit,
        "stats_cen_dot_distance_unit": cen_dot_distance_unit,
        "stats_cen_dot_proximity_radius_unit": cen_dot_proximity_radius_unit,
        "stats_microns_per_pixel": posted_microns_per_pixel,
        "stats_use_metadata_scale": stats_use_metadata_scale,
        "stats_puncta_line_width_value": puncta_line_width_value,
        "stats_cen_dot_distance_value": cen_dot_distance_value,
        "stats_cen_dot_proximity_radius_value": cen_dot_proximity_radius_value,
        "biorientationRedMinDistance": biorientation_red_min_distance_value,
        "biorientationRedMaxDistance": biorientation_red_max_distance_value,
        "biorientationCollinearityThreshold": biorientation_collinearity_threshold,
        "greenDotSplitEnabled": green_dot_split_enabled,
        "greenDotSplitMode": green_dot_split_mode,
        "stats_biorientation_red_min_distance_value": biorientation_red_min_distance_value,
        "stats_biorientation_red_min_distance_unit": biorientation_red_min_distance_unit,
        "stats_biorientation_red_max_distance_value": biorientation_red_max_distance_value,
        "stats_biorientation_red_max_distance_unit": biorientation_red_max_distance_unit,
        "puncta_line_mode": puncta_line_mode,
        "nuclear_cell_pair_mode": nuclear_cell_pair_mode,
        "greenContourFilterEnabled": green_contour_filter_enabled,
        "alternateRedDetection": signal_selection.alternate_nucleus_detection_enabled,
        "alternateNucleusDetectionEnabled": signal_selection.alternate_nucleus_detection_enabled,
        "alternateNucleusDetectionChannel": signal_selection.alternate_nucleus_detection_channel,
        "signalQuantificationEnabled": signal_selection.enabled,
        "signalQuantificationMode": signal_selection.mode,
        "punctaContourIntensityEnabled": signal_selection.puncta_contour_intensity_enabled,
    }
    config_snapshot = {
        **session_values,
        "selected_analysis": requirement_summary["selected_plugins"],
        "manual_um_per_px": posted_microns_per_pixel,
        "prefer_metadata_scale": stats_use_metadata_scale,
        "validation_options": {
            "enforce_layer_count": enforce_layer_count,
            "enforce_wavelengths": enforce_wavelengths,
            "required_channels": sorted(required_channels),
        },
    }
    return session_values, config_snapshot


def _persist_experiment_session(request, session_values: dict[str, object]) -> None:
    for key, value in session_values.items():
        request.session[key] = value
    request.session.modified = True


def experiment(request):
    """
    Uploads and processes each image in the selected folder individually.
    Generates a unique UUID for each image and applies the same process to each one.
    """
    # Ensure session exists to derive a stable progress key
    if not request.session.session_key:
        request.session.save()
    progress_key = request.session.session_key
    owner_filter = _current_owner_filter(request)
    owner_id = request.user.id if request.user.is_authenticated else get_guest_user()
    user_preferences = get_user_preferences(request.user)
    access_policy = get_access_policy_for_user(request.user)

    if request.method == "POST":
        logger.debug("POST request received")

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        files = request.FILES.getlist('files')
        existing_uuids = _parse_restore_uuids(request.POST.getlist("existing_uuids"))
        if not files and not existing_uuids:
            logger.debug("No files received")
            if is_ajax:
                return JsonResponse({"errors": ["No files were uploaded."]}, status=400)
            return render(
                request,
                'form/experiment.html',
                _upload_view_context(
                    form=UploadImageForm(),
                    progress_key=progress_key,
                    error='No files were uploaded.',
                    user_preference_defaults=user_preferences.get("experiment_defaults", {}),
                    upload_quota_payload=_build_upload_quota_payload(request.user, user_preferences),
                    upload_access_policy_payload=_build_upload_access_policy_payload(request.user),
                ),
            )

        session_values, config_snapshot = _parse_experiment_submission(
            request.POST,
            user_preferences,
        )
        _persist_experiment_session(request, session_values)

        invalid_names = [
            file.name for file in files if Path(str(file.name)).suffix.lower() != ".dv"
        ]
        if invalid_names:
            return JsonResponse(
                {"errors": ["Only DeltaVision .dv files can be uploaded."]},
                status=400,
            )

        requested_file_count = len(files) + len(existing_uuids)
        if (
            access_policy.upload_max_files is not None
            and requested_file_count > access_policy.upload_max_files
        ):
            return _upload_limit_error_response(
                request,
                access_policy=access_policy,
                requested_files=requested_file_count,
                is_ajax=is_ajax,
                redirect_path=request.path,
            )

        new_upload_uuids: list[str] = []
        try:
            for image_location in files:
                name = Path(str(image_location.name)).stem or "upload"
                image_uuid = uuid.uuid4()
                instance = UploadedImage(
                    name=name,
                    uuid=image_uuid,
                    file_location=image_location,
                    user_id=owner_id,
                )
                instance.save()
                new_upload_uuids.append(str(image_uuid))
        except Exception as exc:
            for cleanup_uuid in new_upload_uuids:
                delete_uploaded_run_by_uuid(cleanup_uuid)
            if is_storage_full_error(exc):
                log_storage_capacity_failure(
                    stage="experiment_upload_save",
                    user=request.user,
                    uuids=new_upload_uuids,
                    exc=exc,
                )
                if is_ajax:
                    return JsonResponse({"errors": [PROCESSING_STORAGE_FULL_MESSAGE]}, status=507)
                messages.error(request, PROCESSING_STORAGE_FULL_MESSAGE)
                return redirect(request.path)
            logger.exception("Experiment upload save failed")
            if is_ajax:
                return JsonResponse({"errors": ["Upload failed. Please try again."]}, status=500)
            messages.error(request, "Upload failed. Please try again.")
            return redirect(request.path)

        requested_uuids = [*new_upload_uuids, *existing_uuids]
        owner_filter = _current_owner_filter(request)
        owned_uuids = set(
            str(value)
            for value in UploadedImage.objects.filter(
                uuid__in=requested_uuids,
                **owner_filter,
            ).values_list("uuid", flat=True)
        )
        if set(requested_uuids) - owned_uuids:
            for cleanup_uuid in new_upload_uuids:
                delete_uploaded_run_by_uuid(cleanup_uuid)
            return JsonResponse(
                {"errors": ["One or more files are no longer available. Refresh and try again."]},
                status=403,
            )

        job = _create_upload_preparation_job_for_mode(
            user_id=request.user.id,
            new_run_uuids=new_upload_uuids,
            restored_run_uuids=existing_uuids,
            config_snapshot=config_snapshot,
        )
        _track_active_upload_preparation_job(request, job)
        payload = _build_upload_preparation_payload(request, job)
        if is_ajax:
            return JsonResponse(payload)
        if job.status == UploadPreparationJob.Status.SUCCEEDED and payload.get("redirect"):
            messages.info(request, "Files uploaded and prepared.")
            return redirect(payload["redirect"])
        if job.status == UploadPreparationJob.Status.FAILED:
            for line in payload.get("errors") or ["Upload preparation failed. Please try again."]:
                messages.error(request, line)
            return redirect(request.path)
        messages.info(request, "Files uploaded and queued for preparation.")
        return redirect("experiment")
    else:
        form = UploadImageForm()
        upload_quota_payload = _build_upload_quota_payload(request.user, user_preferences)
        upload_access_policy_payload = _build_upload_access_policy_payload(request.user)
        restore_param = request.GET.get("restore", "")
        restore_uuids = _parse_restore_uuids(restore_param)
        protected_uuids = set(restore_uuids)
        protected_uuids.update(
            str(value)
            for value in request.session.get("transient_experiment_uuids", [])
            if str(value)
        )
        sweep_user_run_artifacts(request.user, protected_uuids=protected_uuids)
        restored_map = {
            str(item.uuid): item
            for item in UploadedImage.objects.filter(uuid__in=restore_uuids, **owner_filter)
        }
        restored_queue_items = []
        for uid in restore_uuids:
            item = restored_map.get(uid)
            if not item:
                continue
            restored_queue_items.append(
                {
                    "uuid": uid,
                    "name": item.name,
                }
            )
        upload_resume_payload = _resolve_upload_preparation_resume_payload(request)
    return render(
        request,
        'form/experiment.html',
        _upload_view_context(
            form=form,
            progress_key=progress_key,
            restored_queue_items=restored_queue_items if request.method != "POST" else None,
            user_preference_defaults=user_preferences.get("experiment_defaults", {}),
            upload_quota_payload=upload_quota_payload,
            upload_access_policy_payload=upload_access_policy_payload,
            upload_resume_payload=upload_resume_payload if request.method != "POST" else None,
        ),
    )


@require_POST
def save_experiment_workflow_defaults(request):
    """Persist experiment-popup settings as the user's workflow defaults."""

    try:
        raw_payload = json.loads(request.body.decode("utf-8") or "{}")
    except (TypeError, ValueError, UnicodeDecodeError):
        return JsonResponse(
            {"errors": ["Your request could not be processed. Please try again."]},
            status=400,
        )

    preferences = get_user_preferences(request.user)
    try:
        next_defaults = build_experiment_defaults_from_popup_payload(
            raw_payload,
            current_defaults=preferences.get("experiment_defaults", {}),
        )
    except PreferenceValidationError as exc:
        return JsonResponse({"errors": [str(exc)]}, status=400)

    next_payload = dict(preferences)
    next_payload["experiment_defaults"] = next_defaults
    updated_preferences = update_user_preferences(request.user, next_payload)
    return JsonResponse(
        {
            "message": (
                "Workflow default saved. Future experiments will start with these settings."
            ),
            "defaults": updated_preferences.get("experiment_defaults", {}),
        }
    )


@require_POST
def upload_file_batch(request):
    """Save a small batch of DV files and return queued upload UUIDs."""

    files = request.FILES.getlist("files")
    if not files:
        return JsonResponse({"errors": ["No files were uploaded."]}, status=400)
    access_policy = get_access_policy_for_user(request.user)
    if access_policy.upload_max_files is not None and len(files) > access_policy.upload_max_files:
        return JsonResponse(
            {
                "errors": build_upload_limit_error_lines(
                    access_policy,
                    requested_files=len(files),
                )
            },
            status=400,
        )

    owner_id = request.user.id if request.user.is_authenticated else get_guest_user()
    created_uuids: list[str] = []
    uploaded_items: list[dict[str, str]] = []
    invalid_names = [
        file.name for file in files if Path(str(file.name)).suffix.lower() != ".dv"
    ]
    if invalid_names:
        return JsonResponse(
            {"errors": ["Only DeltaVision .dv files can be uploaded."]},
            status=400,
        )

    try:
        for image_location in files:
            name = Path(str(image_location.name)).stem or "upload"
            image_uuid = uuid.uuid4()
            instance = UploadedImage(
                name=name,
                uuid=image_uuid,
                file_location=image_location,
                user_id=owner_id,
            )
            instance.save()
            created_uuids.append(str(image_uuid))
            uploaded_items.append({"uuid": str(image_uuid), "name": name})
    except Exception as exc:
        for cleanup_uuid in created_uuids:
            delete_uploaded_run_by_uuid(cleanup_uuid)
        if is_storage_full_error(exc):
            log_storage_capacity_failure(
                stage="experiment_upload_save",
                user=request.user,
                uuids=created_uuids,
                exc=exc,
            )
            return JsonResponse({"errors": [PROCESSING_STORAGE_FULL_MESSAGE]}, status=507)
        logger.exception("Upload batch save failed")
        return JsonResponse({"errors": ["Upload failed. Please try again."]}, status=500)

    return JsonResponse({"uploads": uploaded_items})


@require_POST
def enqueue_upload_preparation(request):
    """Queue worker-owned upload validation and preview preparation."""

    reap_stale_upload_preparation_jobs(user_id=request.user.id)
    user_preferences = get_user_preferences(request.user)
    session_values, config_snapshot = _parse_experiment_submission(
        request.POST,
        user_preferences,
    )
    _persist_experiment_session(request, session_values)

    new_run_uuids = _parse_restore_uuids(request.POST.getlist("new_run_uuids"))
    restored_run_uuids = _parse_restore_uuids(request.POST.getlist("existing_uuids"))
    owner_filter = _current_owner_filter(request)
    requested_uuids = [*new_run_uuids, *restored_run_uuids]
    if not requested_uuids:
        return JsonResponse({"errors": ["No files were uploaded."]}, status=400)

    owned_uuids = set(
        str(value)
        for value in UploadedImage.objects.filter(
            uuid__in=requested_uuids,
            **owner_filter,
        ).values_list("uuid", flat=True)
    )
    if set(requested_uuids) - owned_uuids:
        for cleanup_uuid in new_run_uuids:
            if cleanup_uuid in owned_uuids:
                delete_uploaded_run_by_uuid(cleanup_uuid)
        return JsonResponse(
            {"errors": ["One or more files are no longer available. Refresh and try again."]},
            status=403,
        )
    access_policy = get_access_policy_for_user(request.user)
    if (
        access_policy.upload_max_files is not None
        and len(requested_uuids) > access_policy.upload_max_files
    ):
        for cleanup_uuid in new_run_uuids:
            if cleanup_uuid in owned_uuids:
                delete_uploaded_run_by_uuid(cleanup_uuid)
        return JsonResponse(
            {
                "errors": build_upload_limit_error_lines(
                    access_policy,
                    requested_files=len(requested_uuids),
                )
            },
            status=400,
        )

    job = _create_upload_preparation_job_for_mode(
        user_id=request.user.id,
        new_run_uuids=new_run_uuids,
        restored_run_uuids=restored_run_uuids,
        config_snapshot=config_snapshot,
    )
    _track_active_upload_preparation_job(request, job)
    return JsonResponse(_build_upload_preparation_payload(request, job))


@require_GET
def upload_preparation_status(request, job_uuid):
    """Return upload-preparation job status for the owning user."""

    job = get_upload_preparation_job_for_user(
        user_id=request.user.id,
        job_uuid=job_uuid,
    )
    if job is None:
        _forget_upload_preparation_job(request, str(job_uuid))
        return JsonResponse({"errors": ["That upload session is no longer available."]}, status=404)
    stale_state = get_stale_upload_preparation_terminal_state(job)
    payload = _build_upload_preparation_payload(
        request,
        job,
        stale_state=stale_state,
    )
    if payload["status"] in {
        UploadPreparationJob.Status.SUCCEEDED,
        UploadPreparationJob.Status.FAILED,
        UploadPreparationJob.Status.CANCELLED,
    }:
        _forget_upload_preparation_job(request, str(job.job_uuid))
    return JsonResponse(payload)


@require_POST
def cancel_upload_preparation(request, job_uuid):
    """Cancel a queued or running upload-preparation job owned by the user."""

    reap_stale_upload_preparation_jobs(user_id=request.user.id)
    job = get_upload_preparation_job_for_user(
        user_id=request.user.id,
        job_uuid=job_uuid,
    )
    if job is None:
        return JsonResponse({"errors": ["That upload session is no longer available."]}, status=404)
    if job.status in {
        UploadPreparationJob.Status.SUCCEEDED,
        UploadPreparationJob.Status.FAILED,
        UploadPreparationJob.Status.CANCELLED,
    }:
        return JsonResponse(
            {
                "status": job.status,
                "phase": job.current_phase,
                "detail": _upload_job_detail(job),
            }
        )

    if job.status == UploadPreparationJob.Status.QUEUED:
        for run_uuid in job.new_run_uuids:
            delete_uploaded_run_by_uuid(str(run_uuid))
        job = finalize_upload_preparation_job(
            job,
            status=UploadPreparationJob.Status.CANCELLED,
            current_phase="Cancelled",
            valid_run_uuids=[],
            error_lines=[],
        )
        _forget_upload_preparation_job(request, str(job.job_uuid))
    else:
        job = request_upload_preparation_cancellation(job)
    return JsonResponse(
        {
            "status": job.status,
            "phase": job.current_phase,
            "detail": _upload_job_detail(job),
        }
    )
