from django.shortcuts import render, redirect
import logging
from core.forms import UploadImageForm
from core.models import UploadedImage, get_guest_user
from .utils import write_progress
from pathlib import Path    
from cytocv.settings import MEDIA_ROOT
import uuid
import json
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from ..metadata_processing.dv_channel_parser import extract_channel_config
from ..metadata_processing.dv_scale_parser import extract_dv_scale_metadata
from ..metadata_processing.error_handling import (
    DVValidationOptions,
    DVValidationResult,
    build_dv_error_messages,
    validate_dv_file,
)
from ..stats_plugins import (
    CHANNEL_ORDER,
    build_plugin_ui_payload,
    build_requirement_summary,
    normalize_selected_plugins,
)
import uuid as uuid_lib
from accounts.preferences import get_user_preferences
from core.scale import (
    DEFAULT_MICRONS_PER_PIXEL,
    build_scale_info,
    convert_length_to_pixels,
    normalize_length_unit,
    parse_microns_per_pixel,
)
from core.services.puncta_line_mode import (
    DEFAULT_PUNCTA_LINE_MODE,
    normalize_puncta_line_mode,
)
from core.services.artifact_storage import (
    delete_uploaded_run,
    delete_uploaded_run_by_uuid,
    generate_preview_assets,
    get_user_storage_projection,
    is_storage_full_error,
    log_storage_capacity_failure,
    sweep_user_run_artifacts,
)

NUCLEAR_CELL_PAIR_MODES = {"green_nucleus", "red_nucleus"}
PROCESSING_STORAGE_FULL_MESSAGE = (
    "Files could not be saved because storage is full. Free up space and try again."
)
logger = logging.getLogger(__name__)


def _parse_bool(value, default=False):
    """Parse a POST boolean value with a safe default."""

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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
):
    """Build template context for the upload page."""

    context = {
        "form": form,
        "progress_key": progress_key,
        "stats_plugin_payload_json": json.dumps(build_plugin_ui_payload()),
        "restored_queue_payload_json": json.dumps(restored_queue_items or []),
        "user_preference_defaults_json": json.dumps(user_preference_defaults or {}),
        "upload_quota_payload_json": json.dumps(upload_quota_payload or {}),
    }
    if error:
        context["error"] = error
    return context


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
    experiment_defaults = user_preferences.get("experiment_defaults", {})
    upload_quota_payload = _build_upload_quota_payload(request.user, user_preferences)
    default_microns_per_pixel = parse_microns_per_pixel(
        experiment_defaults.get("microns_per_pixel"),
        default=DEFAULT_MICRONS_PER_PIXEL,
    )
    default_use_metadata_scale = bool(experiment_defaults.get("use_metadata_scale", True))

    if request.method == "POST":
        logger.debug("POST request received")
        
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        files = request.FILES.getlist('files')
        existing_uuids = _parse_restore_uuids(request.POST.getlist("existing_uuids"))
        protected_uuids = set(existing_uuids)
        protected_uuids.update(
            str(value)
            for value in request.session.get("transient_experiment_uuids", [])
            if str(value)
        )
        sweep_user_run_artifacts(request.user, protected_uuids=protected_uuids)

        if not files and not existing_uuids:
            logger.debug("No files received")
            return render(
                request,
                'form/experiment.html',
                _upload_view_context(
                    form=UploadImageForm(),
                    progress_key=progress_key,
                    error='No files received.',
                    user_preference_defaults=user_preferences.get("experiment_defaults", {}),
                    upload_quota_payload=upload_quota_payload,
                ),
            )

        logger.debug("Files received: %s", [file.name for file in files])

        selected_analysis = normalize_selected_plugins(request.POST.getlist("selected_analysis"))
        requirement_summary = build_requirement_summary(selected_analysis)

        posted_microns_per_pixel = parse_microns_per_pixel(
            request.POST.get("stats_microns_per_pixel"),
            default=default_microns_per_pixel,
        )
        stats_use_metadata_scale = _parse_bool(
            request.POST.get("stats_use_metadata_scale"),
            default=default_use_metadata_scale,
        )
        puncta_line_width_unit = _normalize_length_unit(
            request.POST.get(
                "stats_puncta_line_width_unit",
                request.POST.get("stats_red_line_width_unit", request.POST.get("stats_mcherry_width_unit")),
            ),
            default="px",
        )
        cen_dot_distance_unit = _normalize_length_unit(
            request.POST.get("stats_cen_dot_distance_unit", request.POST.get("stats_gfp_distance_unit")),
            default="px",
        )
        cen_dot_proximity_radius_unit = _normalize_length_unit(
            request.POST.get("stats_cen_dot_proximity_radius_unit"),
            default="px",
        )

        # Backward compatibility: if raw-value fields are absent, treat submitted
        # legacy width/distance fields as already pixel-normalized.
        has_raw_puncta_line_width = (
            "stats_puncta_line_width_value" in request.POST
            or "stats_red_line_width_value" in request.POST
            or "stats_mcherry_width_value" in request.POST
        )
        has_raw_cen_dot_distance = (
            "stats_cen_dot_distance_value" in request.POST
            or "stats_gfp_distance_value" in request.POST
        )
        has_raw_cen_dot_proximity_radius = "stats_cen_dot_proximity_radius_value" in request.POST
        puncta_line_source_unit = puncta_line_width_unit if has_raw_puncta_line_width else "px"
        cen_dot_source_unit = cen_dot_distance_unit if has_raw_cen_dot_distance else "px"
        cen_dot_proximity_radius_source_unit = cen_dot_proximity_radius_unit if has_raw_cen_dot_proximity_radius else "px"

        puncta_line_width_value = _parse_positive_float(
            request.POST.get(
                "stats_puncta_line_width_value",
                request.POST.get(
                    "stats_red_line_width_value",
                    request.POST.get("punctaLineWidth", request.POST.get("redLineWidth", request.POST.get("mCherryWidth", "1"))),
                ),
            ),
            default=1,
            minimum=0,
        )
        cen_dot_distance_value = _parse_positive_float(
            request.POST.get(
                "stats_cen_dot_distance_value",
                request.POST.get("stats_gfp_distance_value", request.POST.get("cenDotDistance", request.POST.get("distance", "37"))),
            ),
            default=37,
            minimum=0,
        )
        cen_dot_proximity_radius_value = _parse_positive_float(
            request.POST.get(
                "stats_cen_dot_proximity_radius_value",
                request.POST.get("cenDotProximityRadius", "13"),
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

        cen_dot_collinearity_threshold_raw = request.POST.get(
            "cenDotCollinearityThreshold",
            request.POST.get("threshold", "66"),
        )
        try:
            cen_dot_collinearity_threshold = int(cen_dot_collinearity_threshold_raw)
        except (TypeError, ValueError):
            cen_dot_collinearity_threshold = 66
        if cen_dot_collinearity_threshold < 0:
            cen_dot_collinearity_threshold = 66

        green_contour_filter_enabled = request.POST.get(
            "greenContourFilterEnabled",
            request.POST.get("gfpFilterEnabled", False),
        )
        alternate_red_detection = request.POST.get(
            "alternateRedDetection",
            request.POST.get("alternateMCherryDetection", False),
        )

        # Persist user analysis choices now so preprocess step no longer owns selection.
        request.session["selected_analysis"] = requirement_summary["selected_plugins"]
        request.session["punctaLineWidth"] = puncta_line_width
        request.session["cenDotDistance"] = cen_dot_distance
        request.session["cenDotCollinearityThreshold"] = cen_dot_collinearity_threshold
        request.session["cenDotProximityRadius"] = cen_dot_proximity_radius
        request.session["stats_puncta_line_width_unit"] = puncta_line_width_unit
        request.session["stats_cen_dot_distance_unit"] = cen_dot_distance_unit
        request.session["stats_cen_dot_proximity_radius_unit"] = cen_dot_proximity_radius_unit
        request.session["stats_microns_per_pixel"] = posted_microns_per_pixel
        request.session["stats_use_metadata_scale"] = stats_use_metadata_scale
        request.session["stats_puncta_line_width_value"] = puncta_line_width_value
        request.session["stats_cen_dot_distance_value"] = cen_dot_distance_value
        request.session["stats_cen_dot_proximity_radius_value"] = cen_dot_proximity_radius_value
        request.session["puncta_line_mode"] = _parse_puncta_line_mode(
            request.POST.get("puncta_line_mode"),
            default=DEFAULT_PUNCTA_LINE_MODE,
        )
        request.session["nuclear_cell_pair_mode"] = _parse_nuclear_cell_pair_mode(
            request.POST.get("nuclear_cell_pair_mode", request.POST.get("nuclear_cellular_mode")),
            default="green_nucleus",
        )
        request.session["greenContourFilterEnabled"] = green_contour_filter_enabled
        request.session["alternateRedDetection"] = alternate_red_detection

        module_enabled = _parse_bool(request.POST.get("cytocv_analysis_enabled"), default=False)
        enforce_layer_count = module_enabled and _parse_bool(
            request.POST.get("enforce_layer_count"),
            default=False,
        )
        enforce_wavelengths = module_enabled and _parse_bool(
            request.POST.get("enforce_wavelengths"),
            default=False,
        )

        # Optional per-channel toggles from advanced settings. Stats-required channels
        # are always enforced server-side regardless of these optional toggles.
        extra_required_channels = _parse_channels(request.POST.getlist("extra_required_channels"))
        required_channels = set(requirement_summary["required_channels"])
        if module_enabled:
            required_channels.update(extra_required_channels)

        validation_options = DVValidationOptions(
            enforce_layer_count=enforce_layer_count,
            enforce_wavelengths=enforce_wavelengths,
            required_channels=required_channels,
        )

        # Store all UUIDs of the processed images
        image_uuids = []
        validation_failures = []

        # Validate any restored queue UUIDs first to preserve order.
        for existing_uuid in existing_uuids:
            try:
                existing_image = UploadedImage.objects.get(uuid=existing_uuid, **owner_filter)
            except UploadedImage.DoesNotExist:
                validation_failures.append(
                    (
                        existing_uuid,
                        DVValidationResult(
                            is_valid=False,
                            layer_count=None,
                            missing_channels=set(),
                            required_channels=set(required_channels),
                            error_message="no longer available in your upload queue",
                        ),
                    )
                )
                continue

            existing_dv_path = Path(MEDIA_ROOT) / str(existing_image.file_location)
            validation_result = validate_dv_file(existing_dv_path, validation_options)
            if not validation_result.is_valid:
                validation_failures.append((existing_image.name, validation_result))
                continue

            metadata_scale = extract_dv_scale_metadata(existing_dv_path)
            existing_image.scale_info = build_scale_info(
                manual_um_per_px=posted_microns_per_pixel,
                prefer_metadata=stats_use_metadata_scale,
                metadata_um_per_px=metadata_scale.get("metadata_um_per_px"),
                status=metadata_scale.get("status"),
                dx=metadata_scale.get("dx"),
                dy=metadata_scale.get("dy"),
                dz=metadata_scale.get("dz"),
                note=metadata_scale.get("note"),
            )
            existing_image.save(update_fields=["scale_info"])
            image_uuids.append(str(existing_uuid))

        def storage_full_response():
            if is_ajax:
                return JsonResponse({"errors": [PROCESSING_STORAGE_FULL_MESSAGE]}, status=507)
            messages.error(request, PROCESSING_STORAGE_FULL_MESSAGE)
            return redirect(request.path)

        # Iterate through each newly uploaded file and assign a unique UUID
        preprocess_marked = False
        new_upload_uuids: list[str] = []
        for image_location in files:
            name = image_location.name
            name = Path(name).stem

            # Generate a UUID for the image
            image_uuid = uuid.uuid4()
            try:
                # Save the image instance with the generated UUID
                instance = UploadedImage(name=name, uuid=image_uuid, file_location=image_location, user_id=owner_id)
                instance.save()
                new_upload_uuids.append(str(image_uuid))

                # Validate metadata before any preprocessing setup.
                dv_file_path = Path(MEDIA_ROOT) / str(instance.file_location)
                validation_result = validate_dv_file(dv_file_path, validation_options)
                if not validation_result.is_valid:
                    validation_failures.append((name, validation_result))
                    delete_uploaded_run(instance)
                    new_upload_uuids.remove(str(image_uuid))
                    continue

                metadata_scale = extract_dv_scale_metadata(dv_file_path)
                instance.scale_info = build_scale_info(
                    manual_um_per_px=posted_microns_per_pixel,
                    prefer_metadata=stats_use_metadata_scale,
                    metadata_um_per_px=metadata_scale.get("metadata_um_per_px"),
                    status=metadata_scale.get("status"),
                    dx=metadata_scale.get("dx"),
                    dy=metadata_scale.get("dy"),
                    dz=metadata_scale.get("dz"),
                    note=metadata_scale.get("note"),
                )
                instance.save(update_fields=["scale_info"])

                # only valid files make it into the queue
                image_uuids.append(str(image_uuid))

                # Create a directory for each image based on its UUID
                output_dir = Path(MEDIA_ROOT, str(image_uuid))
                output_dir.mkdir(parents=True, exist_ok=True)

                # Extract and save the per-file channel configuration
                dv_file_path = Path(MEDIA_ROOT) / str(instance.file_location)
                channel_config = extract_channel_config(dv_file_path)
                config_json_path = output_dir / "channel_config.json"
                with open(config_json_path, "w", encoding="utf-8") as config_file:
                    json.dump(channel_config, config_file)

                logger.debug("Processing file: %s, UUID: %s", name, image_uuid)

                # Apply the preprocessing step to each image
                if not preprocess_marked:
                    write_progress(progress_key, "Preprocessing Images")
                    preprocess_marked = True
                generate_preview_assets(instance, expected_layers=4)
            except Exception as exc:
                if not is_storage_full_error(exc):
                    raise
                log_storage_capacity_failure(
                    stage="experiment_upload",
                    user=request.user,
                    uuids=new_upload_uuids,
                    exc=exc,
                )
                for cleanup_uuid in list(new_upload_uuids):
                    delete_uploaded_run_by_uuid(cleanup_uuid)
                return storage_full_response()

        error_lines = build_dv_error_messages(validation_failures, validation_options)
        preprocess_url = None
        if image_uuids:
            request.session["last_experiment_uuids"] = image_uuids
            preprocess_url = reverse(
                "pre_process",
                kwargs={"uuids": ",".join(map(str, image_uuids))},
            )

        # Case 3: no valid files
        if not image_uuids:
            if error_lines:
                if is_ajax:
                    return JsonResponse({'errors': error_lines}, status=400)
                messages.error(request, "\n".join(error_lines))
                return redirect(request.path)
            msg = 'No valid DV files were uploaded. Please upload files that pass the selected checks.'
            if is_ajax:
                return JsonResponse({'errors': [msg]}, status=400)
            messages.error(request, msg)
            return redirect(request.path)

        # Case 2: some invalid files
        if error_lines:
            if is_ajax:
                return JsonResponse({'errors': error_lines, 'redirect': preprocess_url})
            messages.error(request, "\n".join(error_lines))

        # Case 1: all valid (or mixed after pushing messages)
        if is_ajax:
            return JsonResponse({'redirect': preprocess_url})
        return redirect(preprocess_url)
    else:
        form = UploadImageForm()
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
    return render(
        request,
        'form/experiment.html',
        _upload_view_context(
            form=form,
            progress_key=progress_key,
            restored_queue_items=restored_queue_items if request.method != "POST" else None,
            user_preference_defaults=user_preferences.get("experiment_defaults", {}),
            upload_quota_payload=upload_quota_payload,
        ),
    )
