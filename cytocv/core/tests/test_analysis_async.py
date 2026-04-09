from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.config import DEFAULT_CHANNEL_CONFIG
from core.models import AnalysisJob, UploadedImage
from core.services.analysis_jobs import enqueue_analysis_job
from core.services.analysis_progress import write_file_progress
from core.services.artifact_storage import (
    PNG_PROFILE_ANALYSIS_FAST,
    save_png_image,
)
from core.tests.test_artifact_storage import temporary_media_root


class AnalysisAsyncTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="analysis-async@example.com",
            password="TestPass123!",
        )
        self.client.login(email=self.user.email, password="TestPass123!")

    @staticmethod
    def _write_channel_config(media_root: Path, uuid_value: str) -> None:
        run_dir = media_root / uuid_value
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "channel_config.json").write_text(
            json.dumps(DEFAULT_CHANNEL_CONFIG),
            encoding="utf-8",
        )

    def _create_uploaded_image(
        self,
        media_root: Path,
        *,
        name: str = "queued_sample",
    ) -> UploadedImage:
        file_uuid = str(uuid4())
        source_path = media_root / file_uuid / f"{name}.dv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"dv")
        uploaded = UploadedImage.objects.create(
            user=self.user,
            uuid=file_uuid,
            name=name,
            file_location=f"{file_uuid}/{name}.dv",
        )
        self._write_channel_config(media_root, file_uuid)
        return uploaded

    @override_settings(ANALYSIS_EXECUTION_MODE="worker")
    def test_pre_process_worker_mode_enqueues_job_without_running_inline(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_enqueue")

            with patch(
                "core.views.pre_process.preprocess_images",
                side_effect=AssertionError("worker mode should not preprocess inline"),
            ), patch(
                "core.views.pre_process.predict_images",
                side_effect=AssertionError("worker mode should not infer inline"),
            ), patch(
                "core.views.pre_process.ensure_preview_assets",
                return_value=[],
            ):
                response = self.client.post(
                    reverse("pre_process", args=[str(uploaded.uuid)]),
                    {},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "queued")
            job = AnalysisJob.objects.get(batch_key=str(uploaded.uuid))
            self.assertEqual(job.status, AnalysisJob.Status.QUEUED)
            self.assertEqual(job.current_phase, "Queued")

            progress = self.client.get(reverse("analysis_progress", args=[str(uploaded.uuid)]))
            self.assertEqual(progress.status_code, 200)
            self.assertEqual(progress.json()["status"], "queued")
            self.assertEqual(progress.json()["phase"], "Queued")

    @override_settings(ANALYSIS_EXECUTION_MODE="worker")
    def test_cancel_progress_marks_worker_job_cancelling(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_cancel")
            job, _ = enqueue_analysis_job(
                user_id=self.user.id,
                raw_uuids=[str(uploaded.uuid)],
                config_snapshot={"execution_mode": "worker"},
            )

            response = self.client.post(
                reverse("cancel_progress", args=[str(uploaded.uuid)]),
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "cancelling")
            job.refresh_from_db()
            self.assertTrue(job.cancellation_requested)
            self.assertEqual(job.status, AnalysisJob.Status.CANCELLING)
            self.assertEqual(job.current_phase, "Cancelling")

    @override_settings(ANALYSIS_EXECUTION_MODE="worker")
    def test_progress_endpoint_prefers_job_state_over_file_progress(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_progress")
            enqueue_analysis_job(
                user_id=self.user.id,
                raw_uuids=[str(uploaded.uuid)],
                config_snapshot={"execution_mode": "worker"},
            )
            write_file_progress(
                str(uploaded.uuid),
                phase="Completed",
                status="succeeded",
                failure_summary="stale progress payload",
            )

            response = self.client.get(reverse("analysis_progress", args=[str(uploaded.uuid)]))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "queued")
            self.assertEqual(response.json()["phase"], "Queued")
            self.assertEqual(response.json()["failure_summary"], "")

    def test_run_analysis_worker_once_finalizes_claimed_job(self):
        job, _ = enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )

        with patch(
            "core.management.commands.run_analysis_worker.run_analysis_batch",
            return_value=SimpleNamespace(storage_warning_message=""),
        ):
            call_command("run_analysis_worker", once=True)

        job.refresh_from_db()
        self.assertEqual(job.status, AnalysisJob.Status.SUCCEEDED)
        self.assertEqual(job.current_phase, "Completed")
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.finished_at)

    def test_save_png_image_fast_profile_uses_low_cost_options(self):
        with TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "fast-profile.png"
            image = Image.new("RGB", (2, 2), color=(1, 2, 3))

            with patch.object(Image.Image, "save", autospec=True) as save_mock:
                save_png_image(
                    image,
                    destination,
                    profile=PNG_PROFILE_ANALYSIS_FAST,
                )

            _, args, kwargs = save_mock.mock_calls[0]
            self.assertEqual(args[1], destination)
            self.assertEqual(kwargs["format"], "PNG")
            self.assertFalse(kwargs["optimize"])
            self.assertEqual(kwargs["compress_level"], 1)

