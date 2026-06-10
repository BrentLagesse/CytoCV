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
    AnalysisJobLimitExceeded,
    enqueue_analysis_job,
    get_active_analysis_job,
    get_latest_analysis_job,
    reap_stale_analysis_jobs,
)
from core.services.analysis_pipeline import run_analysis_batch
from core.services.analysis_progress import (
    AnalysisProgressHandle,
    get_progress_snapshot,
)
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
    safe_analysis_failure_summary,
    validate_progress_status,
)
from core.services.biorientation_config import (
    DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX,
)
from core.services.puncta_line_mode import (
    DEFAULT_PUNCTA_LINE_MODE,
    normalize_puncta_line_mode,
)
from core.services.dot_split import (
    DEFAULT_DOT_SPLIT_MODE,
    normalize_dot_split_mode,
)
from core.services.nuclear_cell_pair_contour_mode import (
    DEFAULT_NUCLEAR_CELL_PAIR_CONTOUR_MODE,
    normalize_nuclear_cell_pair_contour_mode,
)
from core.services.signal_quantification import (
    resolve_signal_quantification_selection,
)
from .utils import (
    tif_to_jpg,
    prune_experiment_session_state,
    sync_transient_run_session_state,
)
from core.channel_roles import (
    CHANNEL_ROLE_ORDER,
    channel_display_label,
    normalize_channel_role,
)
from core.channel_ordering import (
    DEFAULT_FALLBACK_CHANNEL_ORDER,
    normalize_channel_order,
)
from core.config import DEFAULT_CHANNEL_CONFIG
from core.image_sources import TIFF_IMAGE_EXTENSIONS, source_image_extension
from core.metadata_processing.dv_channel_parser import extract_channel_config
from core.metadata_processing.tiff_channel_parser import (
    extract_tiff_metadata_channel_config,
)
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


def _normalize_channel_config(config: dict[str, object]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for channel, index in (config or {}).items():
        role = normalize_channel_role(channel)
        if role is None:
            continue
        try:
            normalized[role] = int(index)
        except (TypeError, ValueError):
            continue
    return normalized


def _write_channel_config(path: Path, config: dict[str, int]) -> None:
    path.write_text(json.dumps(config), encoding="utf-8")


def _refresh_default_tiff_channel_config(
    uploaded: UploadedImage,
    config_path: Path,
    config: dict[str, object],
    *,
    prefer_metadata: bool = True,
) -> dict[str, int]:
    """Refresh old default TIFF configs when complete metadata is available."""

    normalized_config = _normalize_channel_config(config)
    if not prefer_metadata:
        return normalized_config
    if normalized_config != DEFAULT_CHANNEL_CONFIG:
        return normalized_config

    source_path = Path(MEDIA_ROOT) / str(uploaded.file_location)
    if source_image_extension(source_path) not in TIFF_IMAGE_EXTENSIONS:
        return normalized_config

    metadata_config = extract_tiff_metadata_channel_config(source_path)
    if metadata_config is None or metadata_config == normalized_config:
        return normalized_config

    _write_channel_config(config_path, metadata_config)
    return metadata_config


def _channel_labels_from_config(config: dict[str, int]) -> list[str]:
    return [
        channel_display_label(channel)
        for channel, _ in sorted(config.items(), key=lambda item: item[1])
    ]


PROGRESS_BATCH_SESSION_KEY = "authorized_progress_batches"


class ProgressRequestError(Exception):
    """Controlled progress request error carrying an HTTP status code."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _parse_bool(value, default: bool = False) -> bool:
    """Parse common truthy/falsy request/session values."""

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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

    if (
        get_latest_analysis_job(user_id=request.user.id, batch_key=batch_key)
        is not None
    ):
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
                "detail": snapshot.detail or {},
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

    uuid_list = uuids.split(",")
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
    default_manual_scale = preferences.get("experiment_defaults", {}).get(
        "microns_per_pixel", 0.1
    )
    prefer_metadata_channel_order = bool(
        preferences.get("experiment_defaults", {}).get(
            "use_metadata_channel_order", True
        )
    )
    fallback_channel_order = normalize_channel_order(
        preferences.get("experiment_defaults", {}).get("fallback_channel_order"),
        default=DEFAULT_FALLBACK_CHANNEL_ORDER,
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
    current_file_index = int(request.GET.get("file_index", 0))
    current_file_index = max(0, min(current_file_index, total_files - 1))

    # build sidebar list, including the 4-channel order per file
    file_list = []
    for uid in uuid_list:
        uploaded = get_object_or_404(UploadedImage, uuid=uid, **owner_filter)

        # try reading existing channel_config.json
        cfg_path = Path(MEDIA_ROOT) / uid / "channel_config.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            cfg = _refresh_default_tiff_channel_config(
                uploaded,
                cfg_path,
                cfg,
                prefer_metadata=prefer_metadata_channel_order,
            )
            detected_channels = _channel_labels_from_config(cfg)
        else:
            # fallback: parse the stored source image file
            source_path = Path(MEDIA_ROOT) / str(uploaded.file_location)
            if source_path.exists():
                cfg = extract_channel_config(
                    str(source_path),
                    prefer_metadata=prefer_metadata_channel_order,
                    fallback_order=fallback_channel_order,
                )
                detected_channels = _channel_labels_from_config(cfg)
            else:
                detected_channels = []

        scale_payload = get_scale_sidebar_payload(
            uploaded.scale_info,
            manual_default=default_manual_scale,
        )

        file_list.append(
            {
                "uuid": uid,
                "name": uploaded.name,
                "detected_channels": detected_channels,
                "scale": scale_payload,
            }
        )

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
                for item in UploadedImage.objects.filter(
                    uuid__in=active_uuid_set, **owner_filter
                )
            }
            if len(uploaded_map) != len(active_uuid_set):
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {"error": "You do not have access to this experiment."},
                        status=401,
                    )
                return HttpResponse(
                    "You do not have access to this experiment.", status=401
                )
            updates = []
            for image_uuid in revert_uuid_set:
                uploaded = uploaded_map.get(image_uuid)
                if uploaded is None:
                    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                        return JsonResponse(
                            {"error": "You do not have access to this experiment."},
                            status=401,
                        )
                    return HttpResponse(
                        "You do not have access to this experiment.", status=401
                    )
                uploaded.scale_info = clear_manual_override_scale(
                    uploaded.scale_info,
                    manual_default=default_manual_scale,
                )
                updates.append(uploaded)
            for image_uuid, effective_scale in scale_map.items():
                uploaded = uploaded_map.get(image_uuid)
                if uploaded is None:
                    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                        return JsonResponse(
                            {"error": "You do not have access to this experiment."},
                            status=401,
                        )
                    return HttpResponse(
                        "You do not have access to this experiment.", status=401
                    )
                uploaded.scale_info = apply_manual_override_scale(
                    uploaded.scale_info,
                    effective_um_per_px=effective_scale,
                )
                updates.append(uploaded)
            if updates:
                UploadedImage.objects.bulk_update(updates, ["scale_info"])

        # Selection is primarily set during upload step. Keep POST fallback for
        # backward compatibility with older clients.
        selected_analysis = request.POST.getlist(
            "selected_analysis"
        ) or request.session.get("selected_analysis", [])
        puncta_line_width_raw = request.POST.get(
            "punctaLineWidth",
            request.POST.get(
                "redLineWidth",
                request.session.get(
                    "punctaLineWidth",
                    request.session.get(
                        "redLineWidth", request.session.get("mCherryWidth", 1)
                    ),
                ),
            ),
        )
        cen_dot_distance_raw = request.POST.get(
            "cenDotDistance",
            request.session.get("cenDotDistance", request.session.get("distance", 37)),
        )
        biorientation_red_min_distance_value_raw = request.POST.get(
            "biorientationRedMinDistance",
            request.session.get("stats_biorientation_red_min_distance_value", 0.0),
        )
        biorientation_red_min_distance_unit_raw = request.POST.get(
            "biorientationRedMinDistanceUnit",
            request.session.get("stats_biorientation_red_min_distance_unit", "px"),
        )
        biorientation_red_max_distance_value_raw = request.POST.get(
            "biorientationRedMaxDistance",
            request.session.get("stats_biorientation_red_max_distance_value", 37.0),
        )
        biorientation_red_max_distance_unit_raw = request.POST.get(
            "biorientationRedMaxDistanceUnit",
            request.session.get("stats_biorientation_red_max_distance_unit", "px"),
        )
        biorientation_collinearity_threshold_raw = request.POST.get(
            "biorientationCollinearityThreshold",
            request.session.get(
                "biorientationCollinearityThreshold",
                DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX,
            ),
        )
        green_dot_split_enabled_raw = request.POST.get(
            "greenDotSplitEnabled",
            request.POST.get(
                "biorientationGreenSplitEnabled",
                request.session.get(
                    "greenDotSplitEnabled",
                    request.session.get("biorientationGreenSplitEnabled", "True"),
                ),
            ),
        )
        green_dot_split_mode = normalize_dot_split_mode(
            request.POST.get(
                "greenDotSplitMode",
                request.session.get("greenDotSplitMode", DEFAULT_DOT_SPLIT_MODE),
            )
        )
        red_dot_split_enabled_raw = request.POST.get(
            "redDotSplitEnabled",
            request.session.get("redDotSplitEnabled", "True"),
        )
        red_dot_split_mode = normalize_dot_split_mode(
            request.POST.get(
                "redDotSplitMode",
                request.session.get("redDotSplitMode", DEFAULT_DOT_SPLIT_MODE),
            )
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
            request.POST.get(
                "nuclear_cellular_mode",
                request.session.get(
                    "nuclear_cell_pair_mode",
                    request.session.get("nuclear_cellular_mode", "green_nucleus"),
                ),
            ),
        )
        if nuclear_cell_pair_mode not in NUCLEAR_CELL_PAIR_MODES:
            nuclear_cell_pair_mode = "green_nucleus"
        nuclear_cell_pair_contour_mode = normalize_nuclear_cell_pair_contour_mode(
            request.POST.get(
                "nuclear_cell_pair_contour_mode",
                request.POST.get(
                    "nuclearCellPairContourMode",
                    request.session.get(
                        "nuclear_cell_pair_contour_mode",
                        DEFAULT_NUCLEAR_CELL_PAIR_CONTOUR_MODE,
                    ),
                ),
            )
        )
        use_legacy_nuclear_cell_pair_pipeline = _parse_bool(
            request.POST.get(
                "use_legacy_nuclear_cell_pair_pipeline",
                request.session.get("use_legacy_nuclear_cell_pair_pipeline", False),
            ),
            default=False,
        )
        green_contour_filter_enabled_raw = request.POST.get(
            "greenContourFilterEnabled",
            request.session.get(
                "greenContourFilterEnabled",
                request.session.get("gfpFilterEnabled", "False"),
            ),
        )
        green_contour_filter_enabled = _parse_bool(
            green_contour_filter_enabled_raw, default=False
        )
        signal_selection = resolve_signal_quantification_selection(
            payload={
                "signalQuantificationEnabled": request.POST.get(
                    "signalQuantificationEnabled",
                    request.session.get(
                        "signalQuantificationEnabled",
                        request.session.get("signal_quantification_enabled"),
                    ),
                ),
                "signalQuantificationMode": request.POST.get(
                    "signalQuantificationMode",
                    request.session.get(
                        "signalQuantificationMode",
                        request.session.get("signal_quantification_mode"),
                    ),
                ),
                "punctaContourIntensityEnabled": request.POST.get(
                    "punctaContourIntensityEnabled",
                    request.session.get(
                        "punctaContourIntensityEnabled",
                        request.session.get("puncta_contour_intensity_enabled"),
                    ),
                ),
                "alternateNucleusDetectionEnabled": request.POST.get(
                    "alternateNucleusDetectionEnabled",
                    request.POST.get(
                        "alternateRedDetection",
                        request.session.get(
                            "alternateNucleusDetectionEnabled",
                            request.session.get(
                                "alternate_nucleus_detection_enabled",
                                request.session.get(
                                    "alternateRedDetection",
                                    request.session.get(
                                        "alternateMCherryDetection", False
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            },
            selected_plugins=selected_analysis,
            nuclear_cell_pair_mode=nuclear_cell_pair_mode,
            puncta_line_mode=puncta_line_mode,
            default_alternate_nucleus_detection_enabled=_parse_bool(
                request.session.get(
                    "alternateNucleusDetectionEnabled",
                    request.session.get(
                        "alternate_nucleus_detection_enabled",
                        request.session.get(
                            "alternateRedDetection",
                            request.session.get("alternateMCherryDetection", False),
                        ),
                    ),
                ),
                default=False,
            ),
        )
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
            biorientation_collinearity_threshold = (
                DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX
            )
        if biorientation_collinearity_threshold < 0:
            biorientation_collinearity_threshold = (
                DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX
            )
        green_dot_split_enabled = (
            green_dot_split_enabled_raw
            if isinstance(green_dot_split_enabled_raw, bool)
            else str(green_dot_split_enabled_raw).strip().lower()
            in {"1", "true", "yes", "on"}
        )
        red_dot_split_enabled = (
            red_dot_split_enabled_raw
            if isinstance(red_dot_split_enabled_raw, bool)
            else str(red_dot_split_enabled_raw).strip().lower()
            in {"1", "true", "yes", "on"}
        )

        request.session["selected_analysis"] = list(signal_selection.selected_plugins)
        request.session["punctaLineWidth"] = puncta_line_width
        request.session["cenDotDistance"] = cen_dot_distance
        request.session["stats_biorientation_red_min_distance_value"] = (
            biorientation_red_min_distance_value
        )
        request.session["stats_biorientation_red_min_distance_unit"] = (
            biorientation_red_min_distance_unit
        )
        request.session["stats_biorientation_red_max_distance_value"] = (
            biorientation_red_max_distance_value
        )
        request.session["stats_biorientation_red_max_distance_unit"] = (
            biorientation_red_max_distance_unit
        )
        request.session["biorientationCollinearityThreshold"] = (
            biorientation_collinearity_threshold
        )
        request.session["greenDotSplitEnabled"] = green_dot_split_enabled
        request.session["greenDotSplitMode"] = green_dot_split_mode
        request.session["redDotSplitEnabled"] = red_dot_split_enabled
        request.session["redDotSplitMode"] = red_dot_split_mode
        request.session["puncta_line_mode"] = puncta_line_mode
        request.session["nuclear_cell_pair_mode"] = nuclear_cell_pair_mode
        request.session["nuclear_cell_pair_contour_mode"] = (
            nuclear_cell_pair_contour_mode
        )
        request.session["use_legacy_nuclear_cell_pair_pipeline"] = (
            use_legacy_nuclear_cell_pair_pipeline
        )
        request.session["greenContourFilterEnabled"] = green_contour_filter_enabled
        request.session["alternateRedDetection"] = (
            signal_selection.alternate_nucleus_detection_enabled
        )
        request.session["alternateNucleusDetectionEnabled"] = (
            signal_selection.alternate_nucleus_detection_enabled
        )
        request.session["alternateNucleusDetectionChannel"] = (
            signal_selection.alternate_nucleus_detection_channel
        )
        request.session["signalQuantificationEnabled"] = signal_selection.enabled
        request.session["signalQuantificationMode"] = signal_selection.mode
        request.session["punctaContourIntensityEnabled"] = (
            signal_selection.puncta_contour_intensity_enabled
        )
        context = build_analysis_batch_context(request, uuid_list)
        batch_key = context.batch_key
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
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
            progress.set_phase("Idle", status="idle", detail={})
            _release_progress_batch(request, batch_key)
            messages.error(request, PROCESSING_STORAGE_FULL_MESSAGE)
            if is_ajax:
                return JsonResponse(
                    {"error": PROCESSING_STORAGE_FULL_MESSAGE}, status=507
                )
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

            try:
                job, created = enqueue_analysis_job(
                    user_id=request.user.id,
                    raw_uuids=context.run_uuids,
                    config_snapshot=context.config_snapshot,
                )
            except AnalysisJobLimitExceeded as exc:
                _release_progress_batch(request, batch_key)
                if is_ajax:
                    return JsonResponse({"error": str(exc)}, status=429)
                messages.error(request, str(exc))
                return redirect("pre_process", uuids=batch_key)
            progress = AnalysisProgressHandle(batch_key, job=job)
            progress.clear_cancel()
            if created:
                progress.set_phase(
                    "Queued",
                    status="queued",
                    detail={"message": "Waiting for analysis worker."},
                )

            payload = {
                "status": "queued",
                "phase": "Queued",
                "detail": {"message": "Waiting for analysis worker."},
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
            failure_summary = safe_analysis_failure_summary(batch_key)
            if is_ajax:
                return JsonResponse({"error": failure_summary}, status=500)
            messages.error(request, failure_summary)
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
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "images": [
                    {"file_location": {"url": img.file_location.url}}
                    for img in preview_images
                ],
                "file_name": uploaded_image.name,
                "current_file_index": current_file_index,
            }
        )

    # Normal render
    return TemplateResponse(
        request,
        "pre_process.html",
        {
            "images": preview_images,
            "file_name": uploaded_image.name,
            "current_file_index": current_file_index,
            "total_files": total_files,
            "uuids": uuids,
            "file_list": file_list,
            "show_saved_file_channels": show_saved_file_channels,
            "show_saved_file_scales": show_saved_file_scales,
            "sidebar_starts_open": sidebar_starts_open,
            "default_spatial_stats_unit": default_spatial_stats_unit,
            "analysis_execution_mode": analysis_execution_mode,
            "sidebar_spatial_stats_unit": sidebar_spatial_stats_unit,
            "has_selected_stats": bool(request.session.get("selected_analysis", [])),
            "file_scale_map_json": json.dumps(
                {
                    item["uuid"]: item["scale"]["effective_um_per_px"]
                    for item in file_list
                }
            ),
        },
    )


@require_POST
def set_progress(request, key):
    try:
        body = json.loads(request.body or "{}")
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
            progress.set_phase("Cancelled", status="cancelled", detail={})
            return JsonResponse(
                {"status": "cancelled", "phase": "Cancelled", "detail": {}}
            )
        job = get_active_analysis_job(user_id=request.user.id, batch_key=batch_key)
        progress = AnalysisProgressHandle(batch_key, job=job)
        progress.request_cancel()
        progress.set_phase(
            "Cancelling",
            status="cancelling",
            detail={"message": "Cancelling analysis and cleaning up."},
        )
        return JsonResponse(
            {
                "status": "cancelling",
                "phase": "Cancelling",
                "detail": {"message": "Cancelling analysis and cleaning up."},
            }
        )
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
    """Persist a user-selected channel order for one uploaded source image."""

    try:
        data = json.loads(request.body)
        new_order = data.get("order", [])
        if not isinstance(new_order, list):
            return JsonResponse({"error": "Invalid channel order."}, status=400)

        normalized_order = [normalize_channel_role(channel) for channel in new_order]
        expected = set(CHANNEL_ROLE_ORDER)
        if (
            any(channel is None for channel in normalized_order)
            or len(normalized_order) != len(CHANNEL_ROLE_ORDER)
            or set(normalized_order) != expected
        ):
            return JsonResponse({"error": "Invalid channel order."}, status=400)

        mapping = {
            str(channel): index for index, channel in enumerate(normalized_order)
        }

        if not UploadedImage.objects.filter(
            uuid=uuid,
            **_current_owner_filter(request),
        ).exists():
            return JsonResponse(
                {"error": "Channel information for this file could not be loaded."},
                status=404,
            )

        cfg_path = Path(MEDIA_ROOT) / uuid / "channel_config.json"
        if not cfg_path.exists():
            return JsonResponse(
                {"error": "Channel information for this file could not be loaded."},
                status=404,
            )

        _write_channel_config(cfg_path, mapping)
        return JsonResponse({"status": "ok"})

    except Exception:
        return JsonResponse(
            {"error": "The channel order could not be updated. Try again."},
            status=500,
        )
