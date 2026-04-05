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
    preprocess_marked = False
    detection_marked = False

    for image_uuid in context.run_uuids:
        _raise_if_cancelled(progress)
        uploaded_image = UploadedImage.objects.get(uuid=image_uuid, **owner_filter)
        output_dir = Path(settings.MEDIA_ROOT) / image_uuid

        if not preprocess_marked:
            progress.set_phase("Preprocessing Images", status="running")
            preprocess_marked = True
        preprocessed_image = preprocess_fn(
            image_uuid,
            uploaded_image,
            output_dir,
            cancel_check=progress.is_cancel_requested,
        )
        if preprocessed_image is None:
            raise AnalysisCancelled()

        _raise_if_cancelled(progress)

        if not detection_marked:
            progress.set_phase("Detecting Cells", status="running")
            detection_marked = True
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
        progress.set_phase("Completed", status="succeeded")
        return AnalysisBatchResult(
            storage_warning_message=segmentation_result.storage_warning_message,
        )
    except AnalysisCancelled:
        cleanup_cancelled_batch(context.run_uuids)
        progress.clear_cancel()
        progress.set_phase("Cancelled", status="cancelled")
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
            failure_summary=str(exc),
        )
        logger.exception("Analysis pipeline failed for batch %s", context.batch_key)
        raise
