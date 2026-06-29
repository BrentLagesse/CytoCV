"""Background upload validation, metadata extraction, and preview generation."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from uuid import UUID

from core.metadata_processing.dv_scale_parser import extract_dv_scale_metadata
from core.metadata_processing.error_handling import (
    SourceImageValidationOptions,
    SourceImageValidationResult,
    build_source_image_error_messages,
    validate_source_image_file,
)
from core.channel_ordering import (
    DEFAULT_FALLBACK_CHANNEL_ORDER,
    normalize_channel_order,
)
from core.models import UploadedImage, UploadPreparationJob
from core.scale import DEFAULT_MICRONS_PER_PIXEL, build_scale_info
from core.services.artifact_storage import (
    delete_uploaded_run,
    delete_uploaded_run_by_uuid,
    generate_preview_assets,
    is_storage_full_error,
    log_storage_capacity_failure,
    resolve_uploaded_file_path,
    run_media_path,
)
from core.services.analysis_progress import normalize_progress_detail
from core.services.channel_presence import (
    resolve_channel_config_and_presence_for_source,
    write_channel_presence,
)
from core.services.upload_preparation_jobs import (
    TERMINAL_UPLOAD_PREPARATION_STATUSES,
    finalize_upload_preparation_job,
)

logger = logging.getLogger(__name__)

UPLOAD_PREPARATION_FAILURE_SUMMARY = (
    "Upload preparation failed. Please try again or upload a smaller batch."
)
UPLOAD_PREPARATION_STORAGE_FULL_MESSAGE = (
    "Files could not be prepared because storage is full. Free up space and try again."
)


class UploadPreparationCancelled(Exception):
    """Raised when an upload-preparation job is cancelled."""


def _normalize_config_snapshot(snapshot: dict[str, object] | None) -> dict[str, object]:
    # Jobs persist only a whitelisted snapshot of upload-time options. Rehydrate it
    # defensively because queued work may execute after code or preference changes.
    payload = dict(snapshot or {})
    validation = payload.get("validation_options")
    if not isinstance(validation, dict):
        validation = {}

    required_channels = validation.get("required_channels") or []
    if not isinstance(required_channels, list):
        required_channels = list(required_channels) if isinstance(required_channels, tuple) else []

    payload["validation_options"] = {
        "enforce_layer_count": bool(validation.get("enforce_layer_count", False)),
        "enforce_wavelengths": bool(validation.get("enforce_wavelengths", False)),
        "required_channels": [str(channel) for channel in required_channels if str(channel)],
        "configured_experiment_label": str(
            validation.get("configured_experiment_label")
            or payload.get("configured_experiment_label")
            or "the configured experiment"
        ),
    }
    payload["manual_um_per_px"] = float(
        payload.get("manual_um_per_px") or DEFAULT_MICRONS_PER_PIXEL
    )
    payload["prefer_metadata_scale"] = bool(payload.get("prefer_metadata_scale", True))
    payload["prefer_metadata_channel_order"] = bool(
        payload.get("prefer_metadata_channel_order", True)
    )
    payload["fallback_channel_order"] = normalize_channel_order(
        payload.get("fallback_channel_order"),
        default=DEFAULT_FALLBACK_CHANNEL_ORDER,
    )
    return payload


def _validation_options_from_snapshot(snapshot: dict[str, object]) -> SourceImageValidationOptions:
    validation = snapshot.get("validation_options") or {}
    if not isinstance(validation, dict):
        validation = {}
    return SourceImageValidationOptions(
        enforce_layer_count=bool(validation.get("enforce_layer_count", False)),
        enforce_wavelengths=bool(validation.get("enforce_wavelengths", False)),
        required_channels={str(channel) for channel in validation.get("required_channels", []) if str(channel)},
        prefer_metadata_channel_order=bool(
            snapshot.get("prefer_metadata_channel_order", True)
        ),
        configured_experiment_label=str(
            validation.get("configured_experiment_label")
            or "the configured experiment"
        ),
    )


def _owner_filter_for_job(job: UploadPreparationJob) -> dict[str, object]:
    return {"user_id": job.user_id}


def _media_path_for_uploaded(uploaded: UploadedImage) -> Path:
    return resolve_uploaded_file_path(uploaded)


def _write_channel_config(run_uuid: str, channel_config: dict[str, object]) -> None:
    output_dir = run_media_path(run_uuid)
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / "channel_config.json"
    tmp_path = final_path.with_suffix(f".json.{os.getpid()}.tmp")
    # Write atomically so preprocess never reads a partially written channel map.
    tmp_path.write_text(json.dumps(channel_config), encoding="utf-8")
    tmp_path.replace(final_path)


def _raise_if_cancelled(job: UploadPreparationJob) -> None:
    # Refresh from the database because cancellation can be requested by a
    # separate polling/cancel request while the worker is processing files.
    job.refresh_from_db(fields=["cancellation_requested", "status"])
    if job.cancellation_requested or job.status == UploadPreparationJob.Status.CANCELLING:
        raise UploadPreparationCancelled()


def _display_file_name(uploaded: UploadedImage | None, fallback: str) -> str:
    if uploaded is None:
        return fallback
    file_name = Path(str(uploaded.file_location.name or "")).name
    return file_name or f"{uploaded.name}.dv"


def _set_phase(
    job: UploadPreparationJob,
    phase: str,
    *,
    detail: dict[str, object] | None = None,
) -> None:
    # Persist progress through a queryset update so pollers see changes even when
    # the caller keeps using the in-memory job instance.
    progress_detail = normalize_progress_detail(detail)
    UploadPreparationJob.objects.filter(pk=job.pk).update(
        current_phase=phase,
        progress_detail=progress_detail,
    )
    job.current_phase = phase
    job.progress_detail = progress_detail


def _missing_upload_result(required_channels: set[str]) -> SourceImageValidationResult:
    return SourceImageValidationResult(
        is_valid=False,
        layer_count=None,
        missing_channels=set(),
        required_channels=set(required_channels),
        error_message="no longer available in your upload queue",
    )


def _extract_upload_metadata(
    *,
    uploaded: UploadedImage,
    manual_um_per_px: float,
    prefer_metadata_scale: bool,
    prefer_metadata_channel_order: bool,
    fallback_channel_order: list[str],
) -> None:
    source_image_path = _media_path_for_uploaded(uploaded)
    # Metadata is read from the original source file so scale/channel contracts
    # describe the upload itself rather than any generated preview artifact.
    metadata_scale = extract_dv_scale_metadata(source_image_path)
    # Scale metadata and channel presence are persisted before preview generation
    # because the preprocess page reads them directly from the uploaded run.
    uploaded.scale_info = build_scale_info(
        manual_um_per_px=manual_um_per_px,
        prefer_metadata=prefer_metadata_scale,
        metadata_um_per_px=metadata_scale.get("metadata_um_per_px"),
        status=metadata_scale.get("status"),
        dx=metadata_scale.get("dx"),
        dy=metadata_scale.get("dy"),
        dz=metadata_scale.get("dz"),
        note=metadata_scale.get("note"),
    )
    uploaded.save(update_fields=["scale_info"])

    channel_config, channel_presence = resolve_channel_config_and_presence_for_source(
        source_image_path,
        prefer_metadata=prefer_metadata_channel_order,
        fallback_order=fallback_channel_order,
    )
    # The preprocessing and analysis stages read these sidecars by UUID, so upload
    # preparation is the single point that commits channel-order decisions.
    _write_channel_config(str(uploaded.uuid), channel_config)
    write_channel_presence(str(uploaded.uuid), channel_presence)


def _prepare_upload_preview(*, uploaded: UploadedImage) -> None:
    generate_preview_assets(uploaded, expected_layers=4)


def run_upload_preparation_job(job: UploadPreparationJob) -> UploadPreparationJob:
    """Run validation, metadata extraction, channel config, and preview work."""

    job.refresh_from_db(fields=["status"])
    if job.status in TERMINAL_UPLOAD_PREPARATION_STATUSES:
        return job

    # Normalize the persisted snapshot once at job start; later preference edits
    # should not change validation behavior for this queued batch.
    snapshot = _normalize_config_snapshot(job.config_snapshot)
    validation_options = _validation_options_from_snapshot(snapshot)
    manual_um_per_px = float(snapshot["manual_um_per_px"])
    prefer_metadata_scale = bool(snapshot["prefer_metadata_scale"])
    prefer_metadata_channel_order = bool(snapshot["prefer_metadata_channel_order"])
    fallback_channel_order = list(snapshot["fallback_channel_order"])
    owner_filter = _owner_filter_for_job(job)
    failures: list[tuple[str, SourceImageValidationResult]] = []
    valid_run_uuids: list[str] = []
    new_run_uuids = [str(UUID(str(value))) for value in job.new_run_uuids if str(value)]
    restored_run_uuids = [str(UUID(str(value))) for value in job.restored_run_uuids if str(value)]
    requested_run_uuids = [*restored_run_uuids, *new_run_uuids]
    requested_total = len(requested_run_uuids)

    try:
        _raise_if_cancelled(job)
        _set_phase(job, "Validating Files")
        # Validation runs before metadata and preview work so invalid new uploads
        # can be removed without generating downstream artifacts.
        for index, run_uuid in enumerate(requested_run_uuids, start=1):
            _raise_if_cancelled(job)
            uploaded = UploadedImage.objects.filter(uuid=run_uuid, **owner_filter).first()
            _set_phase(
                job,
                "Validating Files",
                detail={
                    "fileIndex": index,
                    "fileTotal": requested_total,
                    "fileName": _display_file_name(uploaded, run_uuid),
                    "message": "Checking file format, layer count, and required channels.",
                },
            )
            if uploaded is None:
                # Missing restored uploads are reported as validation failures, but
                # missing newly staged uploads are also cleaned from media.
                failures.append(
                    (
                        run_uuid,
                        _missing_upload_result(validation_options.required_channels),
                    )
                )
                if run_uuid in new_run_uuids:
                    delete_uploaded_run_by_uuid(run_uuid)
                continue

            source_image_path = _media_path_for_uploaded(uploaded)
            validation_result = validate_source_image_file(source_image_path, validation_options)
            if not validation_result.is_valid:
                # Invalid new uploads are deleted immediately; invalid restored runs
                # are skipped without deleting the user's existing saved artifact.
                failures.append((_display_file_name(uploaded, run_uuid), validation_result))
                if run_uuid in new_run_uuids:
                    delete_uploaded_run(uploaded)
                continue

            valid_run_uuids.append(run_uuid)

        if not valid_run_uuids:
            # Surface all validation failures in the terminal job payload instead
            # of raising, because the upload page renders these messages inline.
            error_lines = build_source_image_error_messages(failures, validation_options)
            if not error_lines:
                error_lines = [
                    "No valid supported image files were uploaded. Please upload files that pass the selected checks."
                ]
            return finalize_upload_preparation_job(
                job,
                status=UploadPreparationJob.Status.FAILED,
                current_phase="Failed",
                valid_run_uuids=[],
                error_lines=error_lines,
                failure_summary="\n".join(error_lines),
            )

        valid_total = len(valid_run_uuids)
        # Only validated runs reach metadata extraction and preview generation;
        # restored invalid runs remain untouched for the user to inspect later.
        for index, run_uuid in enumerate(valid_run_uuids, start=1):
            _raise_if_cancelled(job)
            uploaded = UploadedImage.objects.get(uuid=run_uuid, **owner_filter)
            _set_phase(
                job,
                "Extracting Image Metadata",
                detail={
                    "fileIndex": index,
                    "fileTotal": valid_total,
                    "fileName": _display_file_name(uploaded, run_uuid),
                    "message": "Reading scale calibration and channel assignments.",
                },
            )
            _extract_upload_metadata(
                uploaded=uploaded,
                manual_um_per_px=manual_um_per_px,
                prefer_metadata_scale=prefer_metadata_scale,
                prefer_metadata_channel_order=prefer_metadata_channel_order,
                fallback_channel_order=fallback_channel_order,
            )
            _raise_if_cancelled(job)
            # Preview generation is intentionally after validation and metadata so
            # the browser only receives preview assets for approved runs.
            _set_phase(
                job,
                "Preparing Previews",
                detail={
                    "fileIndex": index,
                    "fileTotal": valid_total,
                    "fileName": _display_file_name(uploaded, run_uuid),
                    "message": "Rendering browser preview assets.",
                },
            )
            _prepare_upload_preview(uploaded=uploaded)

        error_lines = build_source_image_error_messages(failures, validation_options)
        # Succeeded jobs may still include warnings for skipped restored files, so
        # keep error_lines in the successful payload shape.
        return finalize_upload_preparation_job(
            job,
            status=UploadPreparationJob.Status.SUCCEEDED,
            current_phase="Completed",
            valid_run_uuids=valid_run_uuids,
            error_lines=error_lines,
        )
    except UploadPreparationCancelled:
        # Cancellation deletes only newly staged uploads; restored runs existed
        # before this job and must not be removed by an interrupted prepare step.
        for run_uuid in new_run_uuids:
            delete_uploaded_run_by_uuid(run_uuid)
        return finalize_upload_preparation_job(
            job,
            status=UploadPreparationJob.Status.CANCELLED,
            current_phase="Cancelled",
            valid_run_uuids=[],
            error_lines=[],
        )
    except Exception as exc:
        if is_storage_full_error(exc):
            # Disk-full failures can leave partially written previews or sidecars,
            # so clean new staging runs before returning the stable frontend error.
            log_storage_capacity_failure(
                stage="upload_preparation",
                user=job.user,
                uuids=new_run_uuids,
                exc=exc,
            )
            for run_uuid in new_run_uuids:
                delete_uploaded_run_by_uuid(run_uuid)
            return finalize_upload_preparation_job(
                job,
                status=UploadPreparationJob.Status.FAILED,
                current_phase="Failed",
                valid_run_uuids=[],
                error_lines=[UPLOAD_PREPARATION_STORAGE_FULL_MESSAGE],
                failure_summary=UPLOAD_PREPARATION_STORAGE_FULL_MESSAGE,
            )

        logger.exception("Upload preparation job %s failed", job.job_uuid)
        # Unexpected failures use a generic message because the polling UI exposes
        # this summary to users while the detailed traceback stays in logs.
        return finalize_upload_preparation_job(
            job,
            status=UploadPreparationJob.Status.FAILED,
            current_phase="Failed",
            valid_run_uuids=[],
            error_lines=[UPLOAD_PREPARATION_FAILURE_SUMMARY],
            failure_summary=UPLOAD_PREPARATION_FAILURE_SUMMARY,
        )
