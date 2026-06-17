from __future__ import annotations

from core.models import UploadPreparationJob
from core.services.analysis_progress import normalize_progress_detail


def upload_job_detail(job: UploadPreparationJob) -> dict[str, object]:
    return normalize_progress_detail(job.progress_detail)


def build_upload_preparation_payload(
    job: UploadPreparationJob,
    *,
    stale_state: tuple[str, str, str] | None = None,
    redirect_url: str | None = None,
) -> dict[str, object]:
    status = stale_state[0] if stale_state is not None else job.status
    phase = stale_state[1] if stale_state is not None else job.current_phase
    failure_summary = stale_state[2] if stale_state is not None else job.failure_summary
    errors = [str(line) for line in job.error_lines or [] if str(line)]
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
    return {
        "status": job.status,
        "phase": job.current_phase,
        "detail": upload_job_detail(job),
    }
