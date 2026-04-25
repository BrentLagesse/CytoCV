"""Run the database-backed analysis worker loop."""

from __future__ import annotations

import logging
import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import AnalysisJob, UploadPreparationJob, UploadedImage
from core.services.analysis_context import AnalysisBatchContext, normalize_analysis_config_snapshot
from core.services.analysis_exceptions import AnalysisCancelled
from core.services.analysis_jobs import (
    ACTIVE_ANALYSIS_JOB_STATUSES,
    claim_next_analysis_job,
    finalize_job,
    get_oldest_queued_analysis_job,
)
from core.services.analysis_pipeline import run_analysis_batch
from core.services.analysis_progress import AnalysisProgressHandle
from core.services.analysis_progress_contract import SAFE_ANALYSIS_FAILURE_SUMMARY
from core.services.artifact_storage import sweep_user_run_artifacts
from core.services.upload_preparation import run_upload_preparation_job
from core.services.upload_preparation_jobs import (
    ACTIVE_UPLOAD_PREPARATION_STATUSES,
    claim_next_upload_preparation_job,
    get_oldest_queued_upload_preparation_job,
)

logger = logging.getLogger(__name__)


def _protected_run_uuids_by_user() -> dict[int, set[str]]:
    protected: dict[int, set[str]] = {}

    for row in AnalysisJob.objects.filter(
        status__in=ACTIVE_ANALYSIS_JOB_STATUSES
    ).values("user_id", "run_uuids"):
        user_id = int(row["user_id"])
        protected.setdefault(user_id, set()).update(
            str(value) for value in row.get("run_uuids", []) if str(value)
        )

    for row in UploadPreparationJob.objects.filter(
        status__in=ACTIVE_UPLOAD_PREPARATION_STATUSES
    ).values("user_id", "new_run_uuids", "restored_run_uuids"):
        user_id = int(row["user_id"])
        protected.setdefault(user_id, set()).update(
            str(value)
            for value in [
                *(row.get("new_run_uuids") or []),
                *(row.get("restored_run_uuids") or []),
            ]
            if str(value)
        )

    return protected


def _run_periodic_maintenance(user_model) -> None:
    protected_by_user = _protected_run_uuids_by_user()
    user_ids = set(
        int(value)
        for value in UploadedImage.objects.values_list("user_id", flat=True).distinct()
        if value is not None
    )
    user_ids.update(protected_by_user.keys())

    for user in user_model.objects.filter(id__in=user_ids).only("id"):
        summary = sweep_user_run_artifacts(
            user,
            protected_uuids=protected_by_user.get(int(user.id), set()),
        )
        if any(summary.get(key) for key in summary):
            logger.info(
                "Worker maintenance swept artifacts for user %s: %s",
                user.id,
                summary,
            )


class Command(BaseCommand):
    help = "Run the CytoCV database-backed analysis worker."

    def add_arguments(self, parser):
        parser.add_argument(
            "--poll-interval",
            type=float,
            default=1.0,
            help="Seconds to sleep between queue polls when no jobs are available.",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process at most one available job, then exit.",
        )
        parser.add_argument(
            "--maintenance-interval",
            type=float,
            default=300.0,
            help="Seconds between stale artifact maintenance sweeps.",
        )

    def handle(self, *args, **options):
        poll_interval = max(float(options["poll_interval"]), 0.1)
        run_once = bool(options["once"])
        maintenance_interval = max(float(options["maintenance_interval"]), 1.0)
        last_maintenance_at = 0.0
        user_model = get_user_model()

        self.stdout.write(self.style.SUCCESS("Analysis worker started"))

        while True:
            if not run_once and time.monotonic() - last_maintenance_at >= maintenance_interval:
                last_maintenance_at = time.monotonic()
                try:
                    _run_periodic_maintenance(user_model)
                except Exception:
                    logger.exception("Worker maintenance sweep failed")

            upload_candidate = get_oldest_queued_upload_preparation_job()
            analysis_candidate = get_oldest_queued_analysis_job()
            should_claim_upload = (
                upload_candidate is not None
                and (
                    analysis_candidate is None
                    or upload_candidate.created_at <= analysis_candidate.created_at
                )
            )

            if should_claim_upload:
                upload_job = claim_next_upload_preparation_job()
                if upload_job is not None:
                    run_upload_preparation_job(upload_job)
                    if run_once:
                        return
                    continue

            job = claim_next_analysis_job()
            if job is None:
                if run_once:
                    return
                time.sleep(poll_interval)
                continue

            progress = AnalysisProgressHandle(job.batch_key, job=job)
            context = AnalysisBatchContext(
                batch_key=job.batch_key,
                run_uuids=tuple(str(value) for value in job.run_uuids if str(value)),
                user_id=int(job.user_id),
                config_snapshot=normalize_analysis_config_snapshot(job.config_snapshot),
                execution_mode="worker",
            )
            user = user_model.objects.get(pk=job.user_id)

            try:
                result = run_analysis_batch(user=user, context=context, progress=progress)
            except AnalysisCancelled:
                finalize_job(
                    job,
                    status=job.Status.CANCELLED,
                    current_phase="Cancelled",
                )
                logger.info(
                    "Cancelled analysis job %s for user %s (%s runs) at %s",
                    job.job_uuid,
                    job.user_id,
                    len(job.run_uuids),
                    timezone.now().isoformat(),
                )
            except Exception:
                finalize_job(
                    job,
                    status=job.Status.FAILED,
                    current_phase="Failed",
                    failure_summary=SAFE_ANALYSIS_FAILURE_SUMMARY,
                )
                logger.exception(
                    "Analysis worker failed job %s for user %s (%s runs) at %s",
                    job.job_uuid,
                    job.user_id,
                    len(job.run_uuids),
                    timezone.now().isoformat(),
                )
            else:
                finalize_job(
                    job,
                    status=job.Status.SUCCEEDED,
                    current_phase="Completed",
                    failure_summary=result.storage_warning_message,
                )
                logger.info(
                    "Completed analysis job %s for user %s (%s runs) at %s",
                    job.job_uuid,
                    job.user_id,
                    len(job.run_uuids),
                    timezone.now().isoformat(),
                )

            if run_once:
                return
