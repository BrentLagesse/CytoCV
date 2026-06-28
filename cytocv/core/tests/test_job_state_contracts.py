"""Protect analysis/upload-preparation job status and safe error contracts."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import AnalysisJob, UploadPreparationJob


EXPECTED_JOB_STATUSES = (
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelling",
    "cancelled",
)


class JobStateContractTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="job-state@example.com",
            password="TestPass123!",
        )

    def test_analysis_job_status_values_and_defaults_are_stable(self):
        self.assertEqual(tuple(AnalysisJob.Status.values), EXPECTED_JOB_STATUSES)
        self.assertEqual(AnalysisJob._meta.get_field("status").max_length, 16)

        job = AnalysisJob.objects.create(batch_key="analysis-batch", user=self.user)

        self.assertEqual(job.status, AnalysisJob.Status.QUEUED)
        self.assertEqual(job.current_phase, "Queued")
        self.assertEqual(job.progress_detail, {})
        self.assertEqual(job.run_uuids, [])
        self.assertEqual(job.config_snapshot, {})
        self.assertFalse(job.cancellation_requested)
        self.assertEqual(job.failure_summary, "")

    def test_upload_preparation_job_status_values_and_defaults_are_stable(self):
        self.assertEqual(tuple(UploadPreparationJob.Status.values), EXPECTED_JOB_STATUSES)
        self.assertEqual(UploadPreparationJob._meta.get_field("status").max_length, 16)

        job = UploadPreparationJob.objects.create(user=self.user)

        self.assertEqual(job.status, UploadPreparationJob.Status.QUEUED)
        self.assertEqual(job.current_phase, "Queued")
        self.assertEqual(job.progress_detail, {})
        self.assertEqual(job.new_run_uuids, [])
        self.assertEqual(job.restored_run_uuids, [])
        self.assertEqual(job.valid_run_uuids, [])
        self.assertEqual(job.config_snapshot, {})
        self.assertEqual(job.error_lines, [])
        self.assertFalse(job.cancellation_requested)
        self.assertEqual(job.failure_summary, "")
