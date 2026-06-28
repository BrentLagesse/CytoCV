"""Shared full-batch analysis orchestration for sync and worker execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from django.conf import settings

from core.models import UploadedImage
from core.mrcnn.my_inference import predict_images
from core.mrcnn.preprocess_images import preprocess_images
from core.services.analysis_context import AnalysisBatchContext
from core.services.analysis_exceptions import AnalysisCancelled
from core.services.analysis_progress import AnalysisProgressHandle
from core.services.analysis_progress_contract import (
    progress_log_ref,
    safe_analysis_failure_summary,
)
from core.services.artifact_storage import (
    cleanup_failed_processing_artifacts,
    delete_uploaded_run_by_uuid,
    is_storage_full_error,
    log_storage_capacity_failure,
)
from core.services.segmentation_pipeline import run_segmentation_batch

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnalysisBatchResult:
    """Outcome for a completed end-to-end analysis batch."""

    storage_warning_message: str = ""


def _current_owner_filter_for_user(user) -> dict[str, object]:
    if getattr(user, "is_authenticated", False):
        return {"user": user}
    from core.models import get_guest_user

    return {"user_id": get_guest_user()}


def _raise_if_cancelled(progress: AnalysisProgressHandle) -> None:
    if progress.is_cancel_requested():
        raise AnalysisCancelled()


def _phase_with_run_count(phase: str, *, index: int, total: int) -> str:
    if total <= 1:
        return phase
    return f"{phase} ({index}/{total})"


def _display_file_name(uploaded: UploadedImage) -> str:
    file_name = Path(str(uploaded.file_location.name or "")).name
    return file_name or f"{uploaded.name}.dv"


def cleanup_cancelled_batch(run_uuids: tuple[str, ...]) -> None:
    """Delete uploaded runs for a cancelled in-flight batch."""

    for run_uuid in run_uuids:
        delete_uploaded_run_by_uuid(run_uuid)


def cleanup_failed_batch(run_uuids: tuple[str, ...]) -> None:
    """Remove transient preprocessing/inference artifacts after a failed batch."""

    for run_uuid in run_uuids:
        cleanup_failed_processing_artifacts(run_uuid)


def run_preprocess_and_inference_batch(
    *,
    user,
    context: AnalysisBatchContext,
    progress: AnalysisProgressHandle,
    preprocess_fn: Callable[..., Any] = preprocess_images,
    predict_fn: Callable[..., Any] = predict_images,
) -> None:
    """Run preprocess and inference for every uploaded run in a batch."""

    owner_filter = _current_owner_filter_for_user(user)
    total_runs = len(context.run_uuids)

    for index, image_uuid in enumerate(context.run_uuids, start=1):
        _raise_if_cancelled(progress)
        uploaded_image = UploadedImage.objects.get(uuid=image_uuid, **owner_filter)
        output_dir = Path(settings.MEDIA_ROOT) / image_uuid

        # Progress detail keys are shared with the async tooltip and polling UI.
        progress.set_phase(
            _phase_with_run_count(
                "Preprocessing Images",
                index=index,
                total=total_runs,
            ),
            status="running",
            detail={
                "fileIndex": index,
                "fileTotal": total_runs,
                "fileName": _display_file_name(uploaded_image),
            },
        )
        preprocessed_image = preprocess_fn(
            image_uuid,
            uploaded_image,
            output_dir,
            cancel_check=progress.is_cancel_requested,
        )
        if preprocessed_image is None:
            raise AnalysisCancelled()

        _raise_if_cancelled(progress)

        # Inference writes the mask artifacts consumed by the segmentation batch;
        # cancellation between stages should still clean up the whole batch below.
        progress.set_phase(
            _phase_with_run_count(
                "Detecting Cells",
                index=index,
                total=total_runs,
            ),
            status="running",
            detail={
                "fileIndex": index,
                "fileTotal": total_runs,
                "fileName": _display_file_name(uploaded_image),
            },
        )
        prediction_result = predict_fn(
            preprocessed_image,
            output_dir,
            cancel_check=progress.is_cancel_requested,
        )
        if prediction_result is None:
            raise AnalysisCancelled()


def run_analysis_batch(
    *,
    user,
    context: AnalysisBatchContext,
    progress: AnalysisProgressHandle,
    preprocess_fn: Callable[..., Any] = preprocess_images,
    predict_fn: Callable[..., Any] = predict_images,
) -> AnalysisBatchResult:
    """Run the full preprocess, inference, segmentation, and statistics pipeline."""

    try:
        # Keep sync and worker execution on the same orchestration path so failure,
        # cancellation, progress, and cleanup semantics stay identical.
        run_preprocess_and_inference_batch(
            user=user,
            context=context,
            progress=progress,
            preprocess_fn=preprocess_fn,
            predict_fn=predict_fn,
        )
        segmentation_result = run_segmentation_batch(
            user=user,
            batch_key=context.batch_key,
            config_snapshot=context.config_snapshot,
            progress=progress,
        )
        progress.clear_cancel()
        progress.set_phase("Completed", status="succeeded", detail={})
        return AnalysisBatchResult(
            storage_warning_message=segmentation_result.storage_warning_message,
        )
    except AnalysisCancelled:
        cleanup_cancelled_batch(context.run_uuids)
        progress.clear_cancel()
        progress.set_phase("Cancelled", status="cancelled", detail={})
        raise
    except Exception as exc:
        if is_storage_full_error(exc):
            log_storage_capacity_failure(
                stage="analysis_pipeline",
                user=user,
                uuids=context.run_uuids,
                exc=exc,
            )
        cleanup_failed_batch(context.run_uuids)
        progress.clear_cancel()
        progress.set_phase(
            "Failed",
            status="failed",
            failure_summary=safe_analysis_failure_summary(context.batch_key),
            detail={},
        )
        logger.exception(
            "Analysis pipeline failed for progress ref %s",
            progress_log_ref(context.batch_key),
        )
        raise
