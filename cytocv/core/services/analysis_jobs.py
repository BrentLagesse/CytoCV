"""Database-backed helpers for background analysis jobs."""

from __future__ import annotations

from typing import Iterable

from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from core.models import AnalysisJob
from core.services.analysis_context import build_batch_key, normalize_analysis_config_snapshot

ACTIVE_ANALYSIS_JOB_STATUSES = (
    AnalysisJob.Status.QUEUED,
    AnalysisJob.Status.RUNNING,
    AnalysisJob.Status.CANCELLING,
)
TERMINAL_ANALYSIS_JOB_STATUSES = (
    AnalysisJob.Status.SUCCEEDED,
    AnalysisJob.Status.FAILED,
    AnalysisJob.Status.CANCELLED,
)


def get_active_analysis_job(*, user_id: int, batch_key: str) -> AnalysisJob | None:
    """Return the active queued/running job for a user batch, if any."""

    return (
        AnalysisJob.objects.filter(
            user_id=user_id,
            batch_key=batch_key,
            status__in=ACTIVE_ANALYSIS_JOB_STATUSES,
        )
        .order_by("-created_at")
        .first()
    )


def get_latest_analysis_job(*, user_id: int, batch_key: str) -> AnalysisJob | None:
    """Return the most recent job for a user batch, including terminal jobs."""

    return (
        AnalysisJob.objects.filter(user_id=user_id, batch_key=batch_key)
        .order_by("-created_at")
        .first()
    )


def enqueue_analysis_job(
    *,
    user_id: int,
    raw_uuids: Iterable[str] | str,
    config_snapshot: dict[str, object],
) -> tuple[AnalysisJob, bool]:
    """Create a queued job for a batch, or reuse an already-active job."""

    batch_key = build_batch_key(raw_uuids)
    normalized_uuids = list(batch_key.split(",")) if batch_key else []
    normalized_snapshot = normalize_analysis_config_snapshot(config_snapshot)

    with transaction.atomic():
        existing = get_active_analysis_job(user_id=user_id, batch_key=batch_key)
        if existing is not None:
            return existing, False
        try:
            job = AnalysisJob.objects.create(
                batch_key=batch_key,
                user_id=user_id,
                run_uuids=normalized_uuids,
                status=AnalysisJob.Status.QUEUED,
                current_phase="Queued",
                config_snapshot=normalized_snapshot,
            )
        except IntegrityError:
            existing = get_active_analysis_job(user_id=user_id, batch_key=batch_key)
            if existing is None:
                raise
            return existing, False
    return job, True


def claim_next_analysis_job() -> AnalysisJob | None:
    """Claim the next queued analysis job for a worker process."""

    with transaction.atomic():
        queryset = AnalysisJob.objects.filter(status=AnalysisJob.Status.QUEUED).order_by(
            "created_at"
        )
        if connection.vendor == "postgresql":
            queryset = queryset.select_for_update(skip_locked=True)
        else:
            queryset = queryset.select_for_update()
        job = queryset.first()
        if job is None:
            return None
        job.status = AnalysisJob.Status.RUNNING
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


def request_job_cancellation(job: AnalysisJob) -> AnalysisJob:
    """Mark a job as cancellation-requested."""

    if job.status in TERMINAL_ANALYSIS_JOB_STATUSES:
        return job
    next_status = (
        AnalysisJob.Status.CANCELLING
        if job.status == AnalysisJob.Status.RUNNING
        else job.status
    )
    AnalysisJob.objects.filter(pk=job.pk).update(
        cancellation_requested=True,
        status=next_status,
        current_phase="Cancelling",
    )
    job.refresh_from_db(fields=["cancellation_requested", "status", "current_phase"])
    return job


def finalize_job(
    job: AnalysisJob,
    *,
    status: str,
    current_phase: str,
    failure_summary: str = "",
) -> AnalysisJob:
    """Persist the terminal state for a completed job."""

    finished_at = timezone.now()
    AnalysisJob.objects.filter(pk=job.pk).update(
        status=status,
        current_phase=current_phase,
        failure_summary=failure_summary,
        finished_at=finished_at,
    )
    job.refresh_from_db(
        fields=[
            "status",
            "current_phase",
            "failure_summary",
            "finished_at",
        ]
    )
    return job
