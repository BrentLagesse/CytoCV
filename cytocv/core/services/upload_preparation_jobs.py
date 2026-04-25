"""Database-backed helpers for background upload-preparation jobs."""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

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

    return UploadPreparationJob.objects.create(
        user_id=user_id,
        new_run_uuids=normalize_uuid_values(new_run_uuids),
        restored_run_uuids=normalize_uuid_values(restored_run_uuids),
        valid_run_uuids=[],
        config_snapshot=dict(config_snapshot),
        error_lines=[],
        status=UploadPreparationJob.Status.QUEUED,
        current_phase="Queued",
        failure_summary="",
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

    with transaction.atomic():
        queryset = UploadPreparationJob.objects.filter(
            status=UploadPreparationJob.Status.QUEUED
        ).order_by("created_at")
        if connection.vendor == "postgresql":
            queryset = queryset.select_for_update(skip_locked=True)
        else:
            queryset = queryset.select_for_update()
        job = queryset.first()
        if job is None:
            return None
        job.status = UploadPreparationJob.Status.RUNNING
        job.current_phase = "Queued"
        job.started_at = timezone.now()
        job.failure_summary = ""
        job.save(
            update_fields=[
                "status",
                "current_phase",
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
    next_status = (
        UploadPreparationJob.Status.CANCELLING
        if job.status == UploadPreparationJob.Status.RUNNING
        else job.status
    )
    UploadPreparationJob.objects.filter(pk=job.pk).update(
        cancellation_requested=True,
        status=next_status,
        current_phase="Cancelling",
    )
    job.refresh_from_db(fields=["cancellation_requested", "status", "current_phase"])
    return job


def finalize_upload_preparation_job(
    job: UploadPreparationJob,
    *,
    status: str,
    current_phase: str,
    valid_run_uuids: Iterable[object] | None = None,
    error_lines: Iterable[object] | None = None,
    failure_summary: str = "",
) -> UploadPreparationJob:
    """Persist the terminal state for a completed upload-preparation job."""

    update_fields: dict[str, object] = {
        "status": status,
        "current_phase": current_phase,
        "failure_summary": failure_summary,
        "finished_at": timezone.now(),
    }
    if valid_run_uuids is not None:
        update_fields["valid_run_uuids"] = normalize_uuid_values(valid_run_uuids)
    if error_lines is not None:
        update_fields["error_lines"] = [str(line) for line in error_lines if str(line)]

    UploadPreparationJob.objects.filter(pk=job.pk).update(**update_fields)
    job.refresh_from_db(fields=list(update_fields.keys()))
    return job
