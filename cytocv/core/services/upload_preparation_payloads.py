"""Stable JSON payload builders for upload-preparation polling endpoints."""

from __future__ import annotations

from core.models import UploadPreparationJob
from core.services.analysis_progress import normalize_progress_detail


def upload_job_detail(job: UploadPreparationJob) -> dict[str, object]:
    """Return the sanitized progress detail shape shared with analysis polling."""

    return normalize_progress_detail(job.progress_detail)


def build_upload_preparation_payload(
    job: UploadPreparationJob,
    *,
    stale_state: tuple[str, str, str] | None = None,
    redirect_url: str | None = None,
) -> dict[str, object]:
    """Serialize an upload-preparation job for the frontend polling UI.

    The response keys are intentionally narrow and stable because
    ``experiment.js`` uses the same shape for queued worker jobs, inline sync
    completion, stale-job reporting, and resumable upload-preparation state.
    """

    status = stale_state[0] if stale_state is not None else job.status
    phase = stale_state[1] if stale_state is not None else job.current_phase
    failure_summary = stale_state[2] if stale_state is not None else job.failure_summary
    errors = [str(line) for line in job.error_lines or [] if str(line)]
    # Failed jobs must still surface a user-facing error list when the worker
    # only recorded a summary; the frontend renders ``errors`` as the durable
    # validation/failure collection.
    if failure_summary and not errors and status == UploadPreparationJob.Status.FAILED:
        errors = [failure_summary]

    return {
        "job_uuid": str(job.job_uuid),
        "status": status,
        "phase": phase,
        "detail": upload_job_detail(job),
        "errors": errors,
        "failure_summary": failure_summary,
        "redirect": redirect_url,
    }


def build_upload_preparation_cancel_payload(
    job: UploadPreparationJob,
) -> dict[str, object]:
    """Return the compact cancel response consumed by upload-prep polling."""

    return {
        "status": job.status,
        "phase": job.current_phase,
        "detail": upload_job_detail(job),
    }
