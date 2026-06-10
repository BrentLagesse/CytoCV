"""Run the database-backed analysis worker loop."""

from __future__ import annotations

import logging
import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import AnalysisJob
from core.services.analysis_context import AnalysisBatchContext, normalize_analysis_config_snapshot
from core.services.analysis_exceptions import AnalysisCancelled
from core.services.analysis_jobs import (
    claim_next_analysis_job,
    finalize_job,
    get_oldest_queued_analysis_job,
)
from core.services.analysis_pipeline import run_analysis_batch
from core.services.analysis_progress import AnalysisProgressHandle
from core.services.analysis_progress_contract import safe_analysis_failure_summary
from core.services.artifact_maintenance import run_artifact_maintenance
from core.services.upload_preparation import run_upload_preparation_job
from core.services.upload_preparation_jobs import (
    claim_next_upload_preparation_job,
    get_oldest_queued_upload_preparation_job,
)

logger = logging.getLogger(__name__)


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
            "--job-type",
            choices=("all", "upload-preparation", "analysis"),
            default="all",
            help="Restrict the worker to upload-preparation jobs, analysis jobs, or both.",
        )
        parser.add_argument(
            "--maintenance-interval",
            type=float,
            default=300.0,
            help="Seconds between stale artifact maintenance sweeps.",
        )
        parser.add_argument(
            "--skip-maintenance",
            action="store_true",
            help="Skip periodic artifact maintenance while running the worker loop.",
        )

    def handle(self, *args, **options):
        poll_interval = max(float(options["poll_interval"]), 0.1)
        run_once = bool(options["once"])
        job_type = str(options["job_type"])
        maintenance_interval = max(float(options["maintenance_interval"]), 1.0)
        skip_maintenance = bool(options["skip_maintenance"])
        last_maintenance_at = 0.0
        user_model = get_user_model()

        self.stdout.write(self.style.SUCCESS("Analysis worker started"))

        while True:
            if (
                not skip_maintenance
                and not run_once
                and time.monotonic() - last_maintenance_at >= maintenance_interval
            ):
                last_maintenance_at = time.monotonic()
                try:
                    run_artifact_maintenance()
                except Exception:
                    logger.exception("Worker maintenance sweep failed")

            upload_candidate = None
            analysis_candidate = None
            should_claim_upload = False

            if job_type in {"all", "upload-preparation"}:
                upload_candidate = get_oldest_queued_upload_preparation_job()
            if job_type in {"all", "analysis"}:
                analysis_candidate = get_oldest_queued_analysis_job()

            if job_type == "upload-preparation":
                should_claim_upload = upload_candidate is not None
            elif job_type == "all":
                should_claim_upload = (
                    upload_candidate is not None
                    and (
                        analysis_candidate is None
                        or upload_candidate.created_at <= analysis_candidate.created_at
                    )
                )

            if should_claim_upload and upload_candidate is not None:
                upload_job = claim_next_upload_preparation_job()
                if upload_job is not None:
                    run_upload_preparation_job(upload_job)
                    if run_once:
                        return
                    continue

            if job_type == "upload-preparation":
                if run_once:
                    return
                time.sleep(poll_interval)
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
                    failure_summary=safe_analysis_failure_summary(job.batch_key),
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
