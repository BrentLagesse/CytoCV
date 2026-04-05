"""Run the database-backed analysis worker loop."""

from __future__ import annotations

import logging
import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.services.analysis_context import AnalysisBatchContext, normalize_analysis_config_snapshot
from core.services.analysis_exceptions import AnalysisCancelled
from core.services.analysis_jobs import claim_next_analysis_job, finalize_job
from core.services.analysis_pipeline import run_analysis_batch
from core.services.analysis_progress import AnalysisProgressHandle

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

    def handle(self, *args, **options):
        poll_interval = max(float(options["poll_interval"]), 0.1)
        run_once = bool(options["once"])
        user_model = get_user_model()

        self.stdout.write(self.style.SUCCESS("Analysis worker started"))

        while True:
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
                logger.info("Cancelled analysis job %s", job.job_uuid)
            except Exception as exc:
                finalize_job(
                    job,
                    status=job.Status.FAILED,
                    current_phase="Failed",
                    failure_summary=str(exc),
                )
                logger.exception("Analysis worker failed job %s", job.job_uuid)
            else:
                finalize_job(
                    job,
                    status=job.Status.SUCCEEDED,
                    current_phase="Completed",
                    failure_summary=result.storage_warning_message,
                )
                logger.info("Completed analysis job %s", job.job_uuid)

            if run_once:
                return
