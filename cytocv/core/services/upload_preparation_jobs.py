"""Database-backed helpers for background upload-preparation jobs."""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from core.models import UploadPreparationJob

ACTIVE_UPLOAD_PREPARATION_STATUSES = (
    UploadPreparationJob.Status.QUEUED,
    UploadPreparationJob.Status.RUNNING,
    UploadPreparationJob.Status.CANCELLING,
)
TERMINAL_UPLOAD_PREPARATION_STATUSES = (
    UploadPreparationJob.Status.SUCCEEDED,
    UploadPreparationJob.Status.FAILED,
    UploadPreparationJob.Status.CANCELLED,
)
STALE_UPLOAD_PREPARATION_QUEUE_FAILURE_SUMMARY = (
    "Upload preparation expired while waiting for a worker. Please upload again."
)
STALE_UPLOAD_PREPARATION_RUNNING_FAILURE_SUMMARY = (
    "Upload preparation exceeded the maximum runtime and was marked failed."
)


def normalize_uuid_values(values: Iterable[object] | None) -> list[str]:
    """Return valid UUID strings while preserving order and removing duplicates."""

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        try:
            parsed = str(UUID(str(value)))
        except (TypeError, ValueError, AttributeError):
            continue
        if parsed in seen:
            continue
        seen.add(parsed)
        normalized.append(parsed)
    return normalized


def enqueue_upload_preparation_job(
    *,
    user_id: int,
    new_run_uuids: Iterable[object],
    restored_run_uuids: Iterable[object],
    config_snapshot: dict[str, object],
) -> UploadPreparationJob:
    """Create a queued upload-preparation job."""

    # Reaping stale rows before enqueue keeps a dead worker from permanently
    # blocking a user-visible upload attempt or quota-related retry.
    reap_stale_upload_preparation_jobs(user_id=user_id)
    return UploadPreparationJob.objects.create(
        user_id=user_id,
        new_run_uuids=normalize_uuid_values(new_run_uuids),
        restored_run_uuids=normalize_uuid_values(restored_run_uuids),
        valid_run_uuids=[],
        config_snapshot=dict(config_snapshot),
        error_lines=[],
        status=UploadPreparationJob.Status.QUEUED,
        current_phase="Queued",
        progress_detail={"message": "Waiting for upload-preparation worker."},
        failure_summary="",
    )


def start_inline_upload_preparation_job(
    *,
    user_id: int,
    new_run_uuids: Iterable[object],
    restored_run_uuids: Iterable[object],
    config_snapshot: dict[str, object],
) -> UploadPreparationJob:
    """Create an upload-preparation job already owned by the request thread."""

    # Inline mode still persists a job row so the frontend uses the same polling
    # and terminal payload contract as worker mode.
    reap_stale_upload_preparation_jobs(user_id=user_id)
    return UploadPreparationJob.objects.create(
        user_id=user_id,
        new_run_uuids=normalize_uuid_values(new_run_uuids),
        restored_run_uuids=normalize_uuid_values(restored_run_uuids),
        valid_run_uuids=[],
        config_snapshot=dict(config_snapshot),
        error_lines=[],
        status=UploadPreparationJob.Status.RUNNING,
        current_phase="Validating Files",
        progress_detail={"message": "Preparing upload in this request."},
        failure_summary="",
        started_at=timezone.now(),
    )


def get_upload_preparation_job_for_user(
    *,
    user_id: int,
    job_uuid: str,
) -> UploadPreparationJob | None:
    """Return a user-owned upload-preparation job by public UUID."""

    try:
        normalized = UUID(str(job_uuid))
    except (TypeError, ValueError, AttributeError):
        return None
    return UploadPreparationJob.objects.filter(
        user_id=user_id,
        job_uuid=normalized,
    ).first()


def get_upload_preparation_jobs_for_user(
    *,
    user_id: int,
    job_uuids: Iterable[object],
) -> list[UploadPreparationJob]:
    """Return user-owned upload-preparation jobs matching the provided UUIDs."""

    normalized_job_uuids: list[UUID] = []
    seen: set[UUID] = set()
    for value in job_uuids:
        try:
            parsed = UUID(str(value))
        except (TypeError, ValueError, AttributeError):
            continue
        if parsed in seen:
            continue
        seen.add(parsed)
        normalized_job_uuids.append(parsed)
    if not normalized_job_uuids:
        return []
    return list(
        UploadPreparationJob.objects.filter(
            user_id=user_id,
            job_uuid__in=normalized_job_uuids,
        )
    )


def get_oldest_queued_upload_preparation_job() -> UploadPreparationJob | None:
    """Return the oldest queued upload-preparation job without claiming it."""

    return (
        UploadPreparationJob.objects.filter(status=UploadPreparationJob.Status.QUEUED)
        .order_by("created_at")
        .only("pk", "created_at")
        .first()
    )


def claim_next_upload_preparation_job() -> UploadPreparationJob | None:
    """Claim the next queued upload-preparation job for a worker process."""

    reap_stale_upload_preparation_jobs()
    with transaction.atomic():
        # Select and transition within one transaction so two workers cannot
        # process the same staged upload batch.
        queryset = UploadPreparationJob.objects.filter(
            status=UploadPreparationJob.Status.QUEUED
        ).order_by("created_at")
        if connection.vendor == "postgresql":
            # Production can skip rows locked by another worker; SQLite test/local
            # paths use a regular lock because skip_locked is unavailable.
            queryset = queryset.select_for_update(skip_locked=True)
        else:
            queryset = queryset.select_for_update()
        job = queryset.first()
        if job is None:
            return None
        job.status = UploadPreparationJob.Status.RUNNING
        job.current_phase = "Queued"
        job.progress_detail = {"message": "Waiting for upload-preparation worker."}
        job.started_at = timezone.now()
        job.failure_summary = ""
        job.save(
            update_fields=[
                "status",
                "current_phase",
                "progress_detail",
                "started_at",
                "failure_summary",
            ]
        )
        return job


def request_upload_preparation_cancellation(
    job: UploadPreparationJob,
) -> UploadPreparationJob:
    """Mark an upload-preparation job as cancellation-requested."""

    if job.status in TERMINAL_UPLOAD_PREPARATION_STATUSES:
        return job
    # Queued jobs keep their queued status but carry the cancellation flag; running
    # jobs move to CANCELLING so pollers can show immediate feedback while the
    # worker reaches its next cooperative cancellation check.
    next_status = (
        UploadPreparationJob.Status.CANCELLING
        if job.status == UploadPreparationJob.Status.RUNNING
        else job.status
    )
    UploadPreparationJob.objects.filter(pk=job.pk).update(
        cancellation_requested=True,
        status=next_status,
        current_phase="Cancelling",
        progress_detail={"message": "Cancelling upload preparation."},
    )
    job.refresh_from_db(
        fields=["cancellation_requested", "status", "current_phase", "progress_detail"]
    )
    return job


def finalize_upload_preparation_job(
    job: UploadPreparationJob,
    *,
    status: str,
    current_phase: str,
    valid_run_uuids: Iterable[object] | None = None,
    error_lines: Iterable[object] | None = None,
    failure_summary: str = "",
    progress_detail: dict[str, object] | None = None,
) -> UploadPreparationJob:
    """Persist the terminal state for a completed upload-preparation job."""

    update_fields: dict[str, object] = {
        "status": status,
        "current_phase": current_phase,
        "progress_detail": progress_detail or {},
        "failure_summary": failure_summary,
        "finished_at": timezone.now(),
    }
    if valid_run_uuids is not None:
        # Terminal payloads expose approved UUIDs to the preprocess redirect, so
        # normalize them here rather than trusting worker-local lists.
        update_fields["valid_run_uuids"] = normalize_uuid_values(valid_run_uuids)
    if error_lines is not None:
        # Error lines are rendered directly by upload-page UI code; stringify and
        # drop blanks to keep the frontend payload predictable.
        update_fields["error_lines"] = [str(line) for line in error_lines if str(line)]

    UploadPreparationJob.objects.filter(pk=job.pk).update(**update_fields)
    job.refresh_from_db(fields=list(update_fields.keys()))
    return job


def get_stale_upload_preparation_terminal_state(
    job: UploadPreparationJob,
) -> tuple[str, str, str] | None:
    """Return a synthetic terminal state for stale jobs without mutating persistence."""

    if job.status in TERMINAL_UPLOAD_PREPARATION_STATUSES:
        return None

    now = timezone.now()
    queue_stale_seconds = max(
        int(getattr(settings, "UPLOAD_PREPARATION_QUEUE_STALE_SECONDS", 300)),
        1,
    )
    running_stale_seconds = max(
        int(getattr(settings, "UPLOAD_PREPARATION_RUNNING_STALE_SECONDS", 1800)),
        1,
    )

    if job.status == UploadPreparationJob.Status.QUEUED:
        age_seconds = (now - job.created_at).total_seconds()
        if age_seconds < queue_stale_seconds:
            return None
        # GET status endpoints can surface this synthetic failure without mutating
        # persistence; non-GET queue code later calls the reaper to commit it.
        return (
            UploadPreparationJob.Status.FAILED,
            "Failed",
            STALE_UPLOAD_PREPARATION_QUEUE_FAILURE_SUMMARY,
        )

    if job.status in {
        UploadPreparationJob.Status.RUNNING,
        UploadPreparationJob.Status.CANCELLING,
    }:
        started_at = job.started_at or job.created_at
        age_seconds = (now - started_at).total_seconds()
        if age_seconds < running_stale_seconds:
            return None
        # A stale CANCELLING job is treated as cancelled because the user already
        # requested cancellation; stale RUNNING without that flag is a failure.
        terminal_status = (
            UploadPreparationJob.Status.CANCELLED
            if job.status == UploadPreparationJob.Status.CANCELLING
            else UploadPreparationJob.Status.FAILED
        )
        terminal_phase = (
            "Cancelled"
            if terminal_status == UploadPreparationJob.Status.CANCELLED
            else "Failed"
        )
        failure_summary = (
            ""
            if terminal_status == UploadPreparationJob.Status.CANCELLED
            else STALE_UPLOAD_PREPARATION_RUNNING_FAILURE_SUMMARY
        )
        return (
            terminal_status,
            terminal_phase,
            failure_summary,
        )

    return None


def reap_stale_upload_preparation_jobs(
    *,
    user_id: int | None = None,
) -> int:
    """Persist terminal state for stale active upload-preparation jobs."""

    queryset = UploadPreparationJob.objects.filter(
        status__in=ACTIVE_UPLOAD_PREPARATION_STATUSES
    )
    if user_id is not None:
        queryset = queryset.filter(user_id=user_id)

    finalized = 0
    for job in queryset.order_by("created_at"):
        stale_state = get_stale_upload_preparation_terminal_state(job)
        if stale_state is None:
            continue
        # The reaper is intentionally explicit and called from mutating paths or
        # workers, avoiding hidden writes from read-only polling endpoints.
        status, current_phase, failure_summary = stale_state
        finalize_upload_preparation_job(
            job,
            status=status,
            current_phase=current_phase,
            valid_run_uuids=job.valid_run_uuids,
            error_lines=[failure_summary] if failure_summary else [],
            failure_summary=failure_summary,
        )
        finalized += 1
    return finalized
