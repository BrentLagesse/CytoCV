from __future__ import annotations

import errno
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.config import DEFAULT_CHANNEL_CONFIG
from core.metadata_processing.error_handling import DVValidationResult
from core.models import AnalysisJob, UploadedImage, UploadPreparationJob
from core.services.analysis_jobs import enqueue_analysis_job
from core.services.upload_preparation import (
    UPLOAD_PREPARATION_STORAGE_FULL_MESSAGE,
    run_upload_preparation_job,
)
from core.services.upload_preparation_jobs import enqueue_upload_preparation_job
from core.tests.test_artifact_storage import temporary_media_root


@override_settings(ANALYSIS_EXECUTION_MODE="worker")
class UploadPreparationTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="upload-prep@example.com",
            password="TestPass123!",
        )
        self.edu_user = user_model.objects.create_user(
            email="upload-prep@campus.edu",
            password="TestPass123!",
        )
        self.other_user = user_model.objects.create_user(
            email="upload-prep-other@example.com",
            password="TestPass123!",
        )
        self.client.login(email=self.user.email, password="TestPass123!")
        self.edu_client = self.client_class()
        self.edu_client.login(email=self.edu_user.email, password="TestPass123!")
        self.other_client = self.client_class()
        self.other_client.login(email=self.other_user.email, password="TestPass123!")

    def _create_uploaded_image(
        self,
        media_root: Path,
        *,
        user=None,
        name: str = "sample",
    ) -> UploadedImage:
        owner = user or self.user
        file_uuid = str(uuid4())
        source_path = media_root / file_uuid / f"{name}.dv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"dv")
        return UploadedImage.objects.create(
            user=owner,
            uuid=file_uuid,
            name=name,
            file_location=f"{file_uuid}/{name}.dv",
        )

    @staticmethod
    def _valid_result() -> DVValidationResult:
        return DVValidationResult(
            is_valid=True,
            layer_count=4,
            missing_channels=set(),
            required_channels={"DIC"},
        )

    @staticmethod
    def _invalid_result(message: str = "not a recognized DV file") -> DVValidationResult:
        return DVValidationResult(
            is_valid=False,
            layer_count=None,
            missing_channels=set(),
            required_channels={"DIC"},
            error_message=message,
        )

    @staticmethod
    def _config_snapshot() -> dict[str, object]:
        return {
            "manual_um_per_px": 0.2,
            "prefer_metadata_scale": True,
            "validation_options": {
                "enforce_layer_count": False,
                "enforce_wavelengths": False,
                "required_channels": ["DIC"],
            },
        }

    def test_upload_preparation_job_prepares_valid_files(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="valid")
            job = enqueue_upload_preparation_job(
                user_id=self.user.id,
                new_run_uuids=[str(uploaded.uuid)],
                restored_run_uuids=[],
                config_snapshot=self._config_snapshot(),
            )

            with patch(
                "core.services.upload_preparation.validate_dv_file",
                return_value=self._valid_result(),
            ), patch(
                "core.services.upload_preparation.extract_dv_scale_metadata",
                return_value={
                    "metadata_um_per_px": 0.11,
                    "status": "ok",
                    "dx": 0.11,
                    "dy": 0.11,
                    "dz": 0.2,
                    "note": "",
                },
            ), patch(
                "core.services.upload_preparation.extract_channel_config",
                return_value=DEFAULT_CHANNEL_CONFIG,
            ), patch(
                "core.services.upload_preparation.generate_preview_assets",
                return_value=[],
            ):
                run_upload_preparation_job(job)

            job.refresh_from_db()
            uploaded.refresh_from_db()
            self.assertEqual(job.status, UploadPreparationJob.Status.SUCCEEDED)
            self.assertEqual(job.valid_run_uuids, [str(uploaded.uuid)])
            self.assertEqual(uploaded.scale_info.get("source"), "metadata")
            self.assertTrue((media_root / str(uploaded.uuid) / "channel_config.json").exists())

    def test_invalid_new_upload_is_deleted(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="invalid_new")
            job = enqueue_upload_preparation_job(
                user_id=self.user.id,
                new_run_uuids=[str(uploaded.uuid)],
                restored_run_uuids=[],
                config_snapshot=self._config_snapshot(),
            )

            with patch(
                "core.services.upload_preparation.validate_dv_file",
                return_value=self._invalid_result(),
            ):
                run_upload_preparation_job(job)

            job.refresh_from_db()
            self.assertEqual(job.status, UploadPreparationJob.Status.FAILED)
            self.assertFalse(UploadedImage.objects.filter(uuid=uploaded.uuid).exists())
            self.assertFalse((media_root / str(uploaded.uuid)).exists())

    def test_invalid_restored_upload_is_skipped_not_deleted(self):
        with temporary_media_root() as media_root:
            restored = self._create_uploaded_image(media_root, name="invalid_restored")
            valid_new = self._create_uploaded_image(media_root, name="valid_new")
            job = enqueue_upload_preparation_job(
                user_id=self.user.id,
                new_run_uuids=[str(valid_new.uuid)],
                restored_run_uuids=[str(restored.uuid)],
                config_snapshot=self._config_snapshot(),
            )

            def validate_side_effect(path, options):
                return self._invalid_result() if "invalid_restored" in str(path) else self._valid_result()

            with patch(
                "core.services.upload_preparation.validate_dv_file",
                side_effect=validate_side_effect,
            ), patch(
                "core.services.upload_preparation.extract_dv_scale_metadata",
                return_value={},
            ), patch(
                "core.services.upload_preparation.extract_channel_config",
                return_value=DEFAULT_CHANNEL_CONFIG,
            ), patch(
                "core.services.upload_preparation.generate_preview_assets",
                return_value=[],
            ):
                run_upload_preparation_job(job)

            job.refresh_from_db()
            self.assertEqual(job.status, UploadPreparationJob.Status.SUCCEEDED)
            self.assertEqual(job.valid_run_uuids, [str(valid_new.uuid)])
            self.assertTrue(UploadedImage.objects.filter(uuid=restored.uuid).exists())
            self.assertTrue(job.error_lines)

    def test_storage_full_cleans_new_uploads_and_sanitizes_failure(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="storage_full")
            job = enqueue_upload_preparation_job(
                user_id=self.user.id,
                new_run_uuids=[str(uploaded.uuid)],
                restored_run_uuids=[],
                config_snapshot=self._config_snapshot(),
            )

            with patch(
                "core.services.upload_preparation.validate_dv_file",
                return_value=self._valid_result(),
            ), patch(
                "core.services.upload_preparation.extract_dv_scale_metadata",
                return_value={},
            ), patch(
                "core.services.upload_preparation.extract_channel_config",
                return_value=DEFAULT_CHANNEL_CONFIG,
            ), patch(
                "core.services.upload_preparation.generate_preview_assets",
                side_effect=OSError(errno.ENOSPC, "No space left on device"),
            ):
                run_upload_preparation_job(job)

            job.refresh_from_db()
            self.assertEqual(job.status, UploadPreparationJob.Status.FAILED)
            self.assertEqual(job.failure_summary, UPLOAD_PREPARATION_STORAGE_FULL_MESSAGE)
            self.assertNotIn("No space left", job.failure_summary)
            self.assertFalse(UploadedImage.objects.filter(uuid=uploaded.uuid).exists())

    def test_upload_batch_endpoint_rejects_non_dv_files(self):
        response = self.client.post(
            reverse("experiment_upload_batch"),
            {"files": [SimpleUploadedFile("sample.txt", b"not-dv")]},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(UploadedImage.objects.exists())

    def test_upload_preparation_status_forbids_other_user(self):
        job = enqueue_upload_preparation_job(
            user_id=self.user.id,
            new_run_uuids=[],
            restored_run_uuids=[],
            config_snapshot=self._config_snapshot(),
        )

        response = self.other_client.get(
            reverse("experiment_upload_prepare_status", args=[str(job.job_uuid)])
        )

        self.assertEqual(response.status_code, 404)

    def test_upload_preparation_status_returns_safe_progress_detail(self):
        job = enqueue_upload_preparation_job(
            user_id=self.user.id,
            new_run_uuids=[],
            restored_run_uuids=[],
            config_snapshot=self._config_snapshot(),
        )
        UploadPreparationJob.objects.filter(pk=job.pk).update(
            status=UploadPreparationJob.Status.RUNNING,
            current_phase="Preparing Previews",
            progress_detail={
                "fileIndex": 2,
                "fileTotal": 4,
                "fileName": "../preview_detail.dv",
                "message": "Preview generation is running.",
                "unsafe": "ignored",
            },
        )

        response = self.client.get(
            reverse("experiment_upload_prepare_status", args=[str(job.job_uuid)])
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["phase"], "Preparing Previews")
        self.assertEqual(
            payload["detail"],
            {
                "fileName": "preview_detail.dv",
                "message": "Preview generation is running.",
                "fileIndex": 2,
                "fileTotal": 4,
            },
        )

    def test_upload_preparation_enqueue_forbids_other_user_uuid_and_cleans_new(self):
        with temporary_media_root() as media_root:
            new_upload = self._create_uploaded_image(media_root, name="new_upload")
            other_upload = self._create_uploaded_image(
                media_root,
                user=self.other_user,
                name="other_upload",
            )

            response = self.client.post(
                reverse("experiment_upload_prepare"),
                {
                    "new_run_uuids": [str(new_upload.uuid)],
                    "existing_uuids": [str(other_upload.uuid)],
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

            self.assertEqual(response.status_code, 403)
            self.assertFalse(UploadedImage.objects.filter(uuid=new_upload.uuid).exists())
            self.assertFalse((media_root / str(new_upload.uuid)).exists())
            self.assertTrue(UploadedImage.objects.filter(uuid=other_upload.uuid).exists())

    def test_upload_preparation_status_returns_redirect_on_success(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="ready")
            job = enqueue_upload_preparation_job(
                user_id=self.user.id,
                new_run_uuids=[str(uploaded.uuid)],
                restored_run_uuids=[],
                config_snapshot=self._config_snapshot(),
            )
            UploadPreparationJob.objects.filter(pk=job.pk).update(
                status=UploadPreparationJob.Status.SUCCEEDED,
                current_phase="Completed",
                valid_run_uuids=[str(uploaded.uuid)],
                finished_at=timezone.now(),
            )

            response = self.client.get(
                reverse("experiment_upload_prepare_status", args=[str(job.job_uuid)])
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "succeeded")
        self.assertIn("/pre-process/", payload["redirect"])
        self.assertEqual(self.client.session["last_experiment_uuids"], [str(uploaded.uuid)])

    def test_upload_preparation_enqueue_endpoint_remembers_recent_job_uuid(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="remembered")

            response = self.client.post(
                reverse("experiment_upload_prepare"),
                {
                    "new_run_uuids": [str(uploaded.uuid)],
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            self.client.session["recent_upload_preparation_job_uuids"],
            [payload["job_uuid"]],
        )

    @override_settings(ANALYSIS_EXECUTION_MODE="sync")
    def test_upload_preparation_enqueue_sync_mode_runs_inline_and_returns_redirect(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="sync_ready")

            with patch(
                "core.services.upload_preparation.validate_dv_file",
                return_value=self._valid_result(),
            ), patch(
                "core.services.upload_preparation.extract_dv_scale_metadata",
                return_value={},
            ), patch(
                "core.services.upload_preparation.extract_channel_config",
                return_value=DEFAULT_CHANNEL_CONFIG,
            ), patch(
                "core.services.upload_preparation.generate_preview_assets",
                return_value=[],
            ):
                response = self.client.post(
                    reverse("experiment_upload_prepare"),
                    {
                        "new_run_uuids": [str(uploaded.uuid)],
                    },
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], UploadPreparationJob.Status.SUCCEEDED)
        self.assertIn("/pre-process/", payload["redirect"])
        self.assertEqual(self.client.session["last_experiment_uuids"], [str(uploaded.uuid)])
        self.assertNotIn("recent_upload_preparation_job_uuids", self.client.session)
        job = UploadPreparationJob.objects.get()
        self.assertEqual(job.status, UploadPreparationJob.Status.SUCCEEDED)
        self.assertIsNotNone(job.started_at)

    @override_settings(ANALYSIS_EXECUTION_MODE="sync")
    def test_upload_preparation_enqueue_sync_mode_returns_validation_failure(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="sync_invalid")

            with patch(
                "core.services.upload_preparation.validate_dv_file",
                return_value=self._invalid_result(),
            ):
                response = self.client.post(
                    reverse("experiment_upload_prepare"),
                    {
                        "new_run_uuids": [str(uploaded.uuid)],
                    },
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

            self.assertFalse(UploadedImage.objects.filter(uuid=uploaded.uuid).exists())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], UploadPreparationJob.Status.FAILED)
        self.assertTrue(payload["errors"])
        self.assertNotIn("recent_upload_preparation_job_uuids", self.client.session)

    @override_settings(
        STORAGE_QUOTA_EDU_SUFFIXES=(".edu",),
        UPLOAD_LIMIT_DEFAULT_MAX_FILES=1,
        UPLOAD_LIMIT_EDU_MAX_FILES=20,
    )
    def test_upload_preparation_enqueue_blocks_default_tier_over_file_cap_and_cleans_new(self):
        with temporary_media_root() as media_root:
            first = self._create_uploaded_image(media_root, name="limit_first")
            second = self._create_uploaded_image(media_root, name="limit_second")

            response = self.client.post(
                reverse("experiment_upload_prepare"),
                {
                    "new_run_uuids": [str(first.uuid), str(second.uuid)],
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

            self.assertEqual(response.status_code, 400)
            payload = response.json()
            self.assertIn("Standard accounts can preprocess 1 file at a time.", payload["errors"])
            self.assertFalse(UploadedImage.objects.filter(uuid=first.uuid).exists())
            self.assertFalse(UploadedImage.objects.filter(uuid=second.uuid).exists())

    @override_settings(
        STORAGE_QUOTA_EDU_SUFFIXES=(".edu",),
        UPLOAD_LIMIT_DEFAULT_MAX_FILES=1,
        UPLOAD_LIMIT_EDU_MAX_FILES=20,
    )
    def test_upload_preparation_enqueue_counts_restored_files_toward_cap(self):
        with temporary_media_root() as media_root:
            new_upload = self._create_uploaded_image(media_root, name="new_limit")
            restored = self._create_uploaded_image(media_root, name="restored_limit")

            response = self.client.post(
                reverse("experiment_upload_prepare"),
                {
                    "new_run_uuids": [str(new_upload.uuid)],
                    "existing_uuids": [str(restored.uuid)],
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

            self.assertEqual(response.status_code, 400)
            payload = response.json()
            self.assertIn("This submission includes 2 files total.", payload["errors"])
            self.assertFalse(UploadedImage.objects.filter(uuid=new_upload.uuid).exists())
            self.assertTrue(UploadedImage.objects.filter(uuid=restored.uuid).exists())

    @override_settings(
        STORAGE_QUOTA_EDU_SUFFIXES=(".edu",),
        UPLOAD_LIMIT_DEFAULT_MAX_FILES=1,
        UPLOAD_LIMIT_EDU_MAX_FILES=20,
    )
    def test_upload_preparation_enqueue_allows_education_tier_up_to_twenty_files(self):
        with temporary_media_root() as media_root:
            uploads = [
                self._create_uploaded_image(
                    media_root,
                    user=self.edu_user,
                    name=f"edu_{index}",
                )
                for index in range(20)
            ]

            response = self.edu_client.post(
                reverse("experiment_upload_prepare"),
                {
                    "new_run_uuids": [str(item.uuid) for item in uploads],
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], UploadPreparationJob.Status.QUEUED)

    @override_settings(
        STORAGE_QUOTA_EDU_SUFFIXES=(".edu",),
        UPLOAD_LIMIT_DEFAULT_MAX_FILES=1,
        UPLOAD_LIMIT_EDU_MAX_FILES=20,
    )
    def test_legacy_experiment_post_blocks_default_tier_over_file_cap_before_saving(self):
        response = self.client.post(
            reverse("experiment"),
            {
                "files": [
                    SimpleUploadedFile("first.dv", b"dv"),
                    SimpleUploadedFile("second.dv", b"dv"),
                ],
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("Standard accounts can preprocess 1 file at a time.", payload["errors"])
        self.assertFalse(UploadedImage.objects.exists())

    def test_experiment_get_injects_active_upload_resume_payload(self):
        job = enqueue_upload_preparation_job(
            user_id=self.user.id,
            new_run_uuids=[],
            restored_run_uuids=[],
            config_snapshot=self._config_snapshot(),
        )
        session = self.client.session
        session["recent_upload_preparation_job_uuids"] = [str(job.job_uuid)]
        session.save()

        response = self.client.get(reverse("experiment"))

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.context["upload_resume_payload_json"])
        self.assertEqual(payload["job_uuid"], str(job.job_uuid))
        self.assertEqual(payload["status"], UploadPreparationJob.Status.QUEUED)
        self.assertEqual(
            self.client.session["recent_upload_preparation_job_uuids"],
            [str(job.job_uuid)],
        )

    def test_experiment_get_injects_completed_upload_resume_payload_and_clears_it(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="resume_ready")
            job = enqueue_upload_preparation_job(
                user_id=self.user.id,
                new_run_uuids=[str(uploaded.uuid)],
                restored_run_uuids=[],
                config_snapshot=self._config_snapshot(),
            )
            UploadPreparationJob.objects.filter(pk=job.pk).update(
                status=UploadPreparationJob.Status.SUCCEEDED,
                current_phase="Completed",
                valid_run_uuids=[str(uploaded.uuid)],
                finished_at=timezone.now(),
            )
            session = self.client.session
            session["recent_upload_preparation_job_uuids"] = [str(job.job_uuid)]
            session.save()

            response = self.client.get(reverse("experiment"))

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.context["upload_resume_payload_json"])
        self.assertEqual(payload["status"], UploadPreparationJob.Status.SUCCEEDED)
        self.assertIn("/pre-process/", payload["redirect"])
        self.assertNotIn("recent_upload_preparation_job_uuids", self.client.session)
        self.assertEqual(self.client.session["last_experiment_uuids"], [str(uploaded.uuid)])

    def test_experiment_get_injects_failed_upload_resume_payload_and_clears_it(self):
        job = enqueue_upload_preparation_job(
            user_id=self.user.id,
            new_run_uuids=[],
            restored_run_uuids=[],
            config_snapshot=self._config_snapshot(),
        )
        UploadPreparationJob.objects.filter(pk=job.pk).update(
            status=UploadPreparationJob.Status.FAILED,
            current_phase="Failed",
            error_lines=["Validation failed."],
            failure_summary="Validation failed.",
            finished_at=timezone.now(),
        )
        session = self.client.session
        session["recent_upload_preparation_job_uuids"] = [str(job.job_uuid)]
        session.save()

        response = self.client.get(reverse("experiment"))

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.context["upload_resume_payload_json"])
        self.assertEqual(payload["status"], UploadPreparationJob.Status.FAILED)
        self.assertEqual(payload["errors"], ["Validation failed."])
        self.assertNotIn("recent_upload_preparation_job_uuids", self.client.session)

    def test_worker_processes_upload_preparation_job_once(self):
        job = enqueue_upload_preparation_job(
            user_id=self.user.id,
            new_run_uuids=[],
            restored_run_uuids=[],
            config_snapshot=self._config_snapshot(),
        )

        with patch(
            "core.management.commands.run_analysis_worker.run_upload_preparation_job",
            return_value=job,
        ) as upload_mock:
            call_command("run_analysis_worker", once=True)

        upload_mock.assert_called_once()

    def test_worker_once_upload_only_processes_upload_preparation_jobs(self):
        analysis_job, _ = enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )
        upload_job = enqueue_upload_preparation_job(
            user_id=self.user.id,
            new_run_uuids=[],
            restored_run_uuids=[],
            config_snapshot=self._config_snapshot(),
        )
        AnalysisJob.objects.filter(pk=analysis_job.pk).update(
            created_at=timezone.now() - timezone.timedelta(seconds=5)
        )
        UploadPreparationJob.objects.filter(pk=upload_job.pk).update(created_at=timezone.now())

        with patch(
            "core.management.commands.run_analysis_worker.run_upload_preparation_job",
            return_value=upload_job,
        ) as upload_mock, patch(
            "core.management.commands.run_analysis_worker.run_analysis_batch",
        ) as analysis_mock:
            call_command("run_analysis_worker", once=True, job_type="upload-preparation")

        upload_mock.assert_called_once()
        analysis_mock.assert_not_called()

    def test_worker_once_analysis_only_processes_analysis_jobs(self):
        enqueue_upload_preparation_job(
            user_id=self.user.id,
            new_run_uuids=[],
            restored_run_uuids=[],
            config_snapshot=self._config_snapshot(),
        )
        enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )

        with patch(
            "core.management.commands.run_analysis_worker.run_upload_preparation_job",
        ) as upload_mock, patch(
            "core.management.commands.run_analysis_worker.run_analysis_batch",
            return_value=SimpleNamespace(storage_warning_message=""),
        ) as analysis_mock:
            call_command("run_analysis_worker", once=True, job_type="analysis")

        upload_mock.assert_not_called()
        analysis_mock.assert_called_once()

    def test_worker_skip_maintenance_suppresses_maintenance_call(self):
        with patch(
            "core.management.commands.run_analysis_worker.run_artifact_maintenance",
        ) as maintenance_mock, patch(
            "core.management.commands.run_analysis_worker.get_oldest_queued_upload_preparation_job",
            side_effect=KeyboardInterrupt,
        ):
            with self.assertRaises(KeyboardInterrupt):
                call_command("run_analysis_worker", skip_maintenance=True)

        maintenance_mock.assert_not_called()

    def test_run_artifact_maintenance_command_runs_once(self):
        with patch(
            "core.management.commands.run_artifact_maintenance.run_artifact_maintenance",
        ) as maintenance_mock:
            call_command("run_artifact_maintenance")

        maintenance_mock.assert_called_once()

    def test_worker_still_processes_older_analysis_job_first(self):
        analysis_job, _ = enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )
        upload_job = enqueue_upload_preparation_job(
            user_id=self.user.id,
            new_run_uuids=[],
            restored_run_uuids=[],
            config_snapshot=self._config_snapshot(),
        )
        AnalysisJob.objects.filter(pk=analysis_job.pk).update(
            created_at=timezone.now() - timezone.timedelta(seconds=5)
        )
        UploadPreparationJob.objects.filter(pk=upload_job.pk).update(created_at=timezone.now())

        with patch(
            "core.management.commands.run_analysis_worker.run_upload_preparation_job",
        ) as upload_mock, patch(
            "core.management.commands.run_analysis_worker.run_analysis_batch",
            return_value=SimpleNamespace(storage_warning_message=""),
        ) as analysis_mock:
            call_command("run_analysis_worker", once=True)

        upload_mock.assert_not_called()
        analysis_mock.assert_called_once()

    @override_settings(UPLOAD_PREPARATION_QUEUE_STALE_SECONDS=1)
    def test_upload_preparation_status_surfaces_stale_queued_job_without_mutating_get(self):
        job = enqueue_upload_preparation_job(
            user_id=self.user.id,
            new_run_uuids=[],
            restored_run_uuids=[],
            config_snapshot=self._config_snapshot(),
        )
        UploadPreparationJob.objects.filter(pk=job.pk).update(
            created_at=timezone.now() - timezone.timedelta(seconds=5),
        )

        response = self.client.get(
            reverse("experiment_upload_prepare_status", args=[str(job.job_uuid)])
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], UploadPreparationJob.Status.FAILED)
        self.assertIn("expired", payload["failure_summary"].lower())
        job.refresh_from_db()
        self.assertEqual(job.status, UploadPreparationJob.Status.QUEUED)
        self.assertIsNone(job.finished_at)

    @override_settings(UPLOAD_PREPARATION_RUNNING_STALE_SECONDS=1)
    def test_upload_preparation_status_surfaces_stale_running_job_without_mutating_get(self):
        job = enqueue_upload_preparation_job(
            user_id=self.user.id,
            new_run_uuids=[],
            restored_run_uuids=[],
            config_snapshot=self._config_snapshot(),
        )
        UploadPreparationJob.objects.filter(pk=job.pk).update(
            status=UploadPreparationJob.Status.RUNNING,
            current_phase="Preparing Previews",
            started_at=timezone.now() - timezone.timedelta(seconds=5),
        )

        response = self.client.get(
            reverse("experiment_upload_prepare_status", args=[str(job.job_uuid)])
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], UploadPreparationJob.Status.FAILED)
        self.assertIn("maximum runtime", payload["failure_summary"].lower())
        job.refresh_from_db()
        self.assertEqual(job.status, UploadPreparationJob.Status.RUNNING)
        self.assertIsNone(job.finished_at)

    @override_settings(UPLOAD_PREPARATION_QUEUE_STALE_SECONDS=1)
    def test_enqueue_upload_preparation_job_reaps_stale_job_outside_get(self):
        stale_job = enqueue_upload_preparation_job(
            user_id=self.user.id,
            new_run_uuids=[],
            restored_run_uuids=[],
            config_snapshot=self._config_snapshot(),
        )
        UploadPreparationJob.objects.filter(pk=stale_job.pk).update(
            created_at=timezone.now() - timezone.timedelta(seconds=5),
        )

        replacement_job = enqueue_upload_preparation_job(
            user_id=self.user.id,
            new_run_uuids=[],
            restored_run_uuids=[],
            config_snapshot=self._config_snapshot(),
        )

        stale_job.refresh_from_db()
        self.assertEqual(stale_job.status, UploadPreparationJob.Status.FAILED)
        self.assertNotEqual(replacement_job.pk, stale_job.pk)
