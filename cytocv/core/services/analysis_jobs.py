"""Database-backed helpers for background analysis jobs."""

from __future__ import annotations

from typing import Iterable

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from core.models import AnalysisJob
from core.services.analysis_context import build_batch_key, normalize_analysis_config_snapshot
from core.services.analysis_progress_contract import (
    STALE_QUEUE_FAILURE_SUMMARY,
    STALE_RUNNING_FAILURE_SUMMARY,
)

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
    reap_stale_analysis_jobs(user_id=user_id, batch_key=batch_key)

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

    reap_stale_analysis_jobs()
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


def get_stale_job_terminal_state(job: AnalysisJob) -> tuple[str, str, str] | None:
    """Return a terminal state for a stale job without mutating persistence."""

    if job.status in TERMINAL_ANALYSIS_JOB_STATUSES:
        return None

    now = timezone.now()
    queue_stale_seconds = max(
        int(getattr(settings, "ANALYSIS_QUEUE_STALE_SECONDS", 300)),
        1,
    )
    running_stale_seconds = max(
        int(getattr(settings, "ANALYSIS_RUNNING_STALE_SECONDS", 7200)),
        1,
    )

    if job.status == AnalysisJob.Status.QUEUED:
        age_seconds = (now - job.created_at).total_seconds()
        if age_seconds < queue_stale_seconds:
            return None
        return (
            AnalysisJob.Status.FAILED,
            "Failed",
            STALE_QUEUE_FAILURE_SUMMARY,
        )

    if job.status in {AnalysisJob.Status.RUNNING, AnalysisJob.Status.CANCELLING}:
        started_at = job.started_at or job.created_at
        age_seconds = (now - started_at).total_seconds()
        if age_seconds < running_stale_seconds:
            return None
        terminal_status = (
            AnalysisJob.Status.CANCELLED
            if job.status == AnalysisJob.Status.CANCELLING
            else AnalysisJob.Status.FAILED
        )
        terminal_phase = "Cancelled" if terminal_status == AnalysisJob.Status.CANCELLED else "Failed"
        failure_summary = (
            ""
            if terminal_status == AnalysisJob.Status.CANCELLED
            else STALE_RUNNING_FAILURE_SUMMARY
        )
        return (
            terminal_status,
            terminal_phase,
            failure_summary,
        )

    return None


def reap_stale_analysis_jobs(
    *,
    user_id: int | None = None,
    batch_key: str | None = None,
) -> int:
    """Persist terminal state for stale active jobs from explicit non-GET code paths."""

    queryset = AnalysisJob.objects.filter(status__in=ACTIVE_ANALYSIS_JOB_STATUSES)
    if user_id is not None:
        queryset = queryset.filter(user_id=user_id)
    if batch_key is not None:
        queryset = queryset.filter(batch_key=batch_key)

    finalized = 0
    for job in queryset.order_by("created_at"):
        stale_state = get_stale_job_terminal_state(job)
        if stale_state is None:
            continue
        status, current_phase, failure_summary = stale_state
        finalize_job(
            job,
            status=status,
            current_phase=current_phase,
            failure_summary=failure_summary,
        )
        finalized += 1
    return finalized
