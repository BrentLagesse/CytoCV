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
from django.utils import timezone
from PIL import Image

from accounts.preferences import update_user_preferences
from core.config import DEFAULT_CHANNEL_CONFIG
from core.models import AnalysisJob, SegmentedImage, UploadedImage, get_guest_user
from core.services.analysis_exceptions import AnalysisCancelled
from core.services.analysis_context import AnalysisBatchContext
from core.services.analysis_jobs import AnalysisJobLimitExceeded, enqueue_analysis_job
from core.services.analysis_pipeline import run_preprocess_and_inference_batch
from core.services.analysis_progress_contract import (
    SAFE_ANALYSIS_FAILURE_SUMMARY,
    SAFE_PROGRESS_WRITE_ERROR_MESSAGE,
)
from core.services.analysis_progress import (
    AnalysisProgressHandle,
    get_progress_snapshot,
    write_file_progress,
)
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
        self.edu_user = user_model.objects.create_user(
            email="analysis-async@campus.edu",
            password="TestPass123!",
        )
        self.other_user = user_model.objects.create_user(
            email="analysis-async-other@example.com",
            password="TestPass123!",
        )
        self.client.login(email=self.user.email, password="TestPass123!")
        self.edu_client = self.client_class()
        self.edu_client.login(email=self.edu_user.email, password="TestPass123!")
        self.other_client = self.client_class()
        self.other_client.login(
            email=self.other_user.email,
            password="TestPass123!",
        )

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

    @staticmethod
    def _create_segmented_image(
        media_root: Path,
        *,
        uploaded: UploadedImage,
        owner_id: int,
    ) -> SegmentedImage:
        file_uuid = str(uploaded.uuid)
        run_dir = media_root / file_uuid
        output_dir = run_dir / "output"
        segmented_dir = run_dir / "segmented"
        output_dir.mkdir(parents=True, exist_ok=True)
        segmented_dir.mkdir(parents=True, exist_ok=True)
        frame_path = output_dir / f"{Path(uploaded.name).stem}_frame_1.png"
        Image.new("RGB", (2, 2), color=(1, 2, 3)).save(frame_path)
        return SegmentedImage.objects.create(
            user_id=owner_id,
            UUID=file_uuid,
            file_location=f"user_{file_uuid}/segmented.png",
            ImagePath=str(frame_path),
            CellPairPrefix=str(segmented_dir / "cell"),
            NumCells=0,
        )

    @override_settings(ANALYSIS_EXECUTION_MODE="worker")
    def test_pre_process_worker_mode_enqueues_job_without_running_inline(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_enqueue")

            with patch(
                "core.views.pre_process.run_analysis_batch",
                side_effect=AssertionError("worker mode should not run full analysis inline"),
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
            self.assertEqual(
                progress.json()["detail"],
                {"message": "Waiting for analysis worker."},
            )

    @override_settings(
        ANALYSIS_EXECUTION_MODE="worker",
        STORAGE_QUOTA_EDU_SUFFIXES=(".edu",),
        ANALYSIS_LIMIT_DEFAULT_MAX_ACTIVE_JOBS=1,
    )
    def test_pre_process_worker_mode_returns_queue_cap_error_for_second_distinct_job(self):
        with temporary_media_root() as media_root:
            first = self._create_uploaded_image(media_root, name="cap_first")
            second = self._create_uploaded_image(media_root, name="cap_second")

            with patch(
                "core.views.pre_process.ensure_preview_assets",
                return_value=[],
            ):
                first_response = self.client.post(
                    reverse("pre_process", args=[str(first.uuid)]),
                    {},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                second_response = self.client.post(
                    reverse("pre_process", args=[str(second.uuid)]),
                    {},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

            self.assertEqual(first_response.status_code, 200)
            self.assertEqual(second_response.status_code, 429)
            payload = second_response.json()
            self.assertIn(
                "Standard accounts can have 1 active analysis job at a time.",
                payload["error"],
            )

    @override_settings(ANALYSIS_EXECUTION_MODE="sync")
    def test_pre_process_sync_mode_runs_full_batch_and_redirects_to_display(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="sync_success")

            with patch(
                "core.views.pre_process.ensure_preview_assets",
                return_value=[],
            ), patch(
                "core.views.pre_process.run_analysis_batch",
                return_value=SimpleNamespace(storage_warning_message=""),
            ) as run_batch_mock:
                response = self.client.post(
                    reverse("pre_process", args=[str(uploaded.uuid)]),
                    {},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "succeeded")
            self.assertEqual(
                payload["redirect"],
                reverse("display", args=[str(uploaded.uuid)]),
            )
            self.assertNotIn("/segment/", payload["redirect"])
            run_batch_mock.assert_called_once()

    @override_settings(ANALYSIS_EXECUTION_MODE="sync")
    def test_pre_process_post_preserves_signal_quantification_alternate_detection(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="sync_signal_quant")

            def run_batch_side_effect(*, user, context, progress, **_kwargs):
                self.assertEqual(
                    context.config_snapshot["selected_analysis"],
                    ["NuclearCellPairIntensity"],
                )
                self.assertTrue(context.config_snapshot["signalQuantificationEnabled"])
                self.assertEqual(
                    context.config_snapshot["signalQuantificationMode"],
                    "nuclear_cell_pair",
                )
                self.assertTrue(
                    context.config_snapshot["alternateNucleusDetectionEnabled"]
                )
                self.assertEqual(
                    context.config_snapshot["alternateNucleusDetectionChannel"],
                    "channel_red",
                )
                self.assertEqual(
                    context.config_snapshot["nuclear_cell_pair_mode"],
                    "red_nucleus",
                )
                return SimpleNamespace(storage_warning_message="")

            with patch(
                "core.views.pre_process.ensure_preview_assets",
                return_value=[],
            ), patch(
                "core.views.pre_process.run_analysis_batch",
                side_effect=run_batch_side_effect,
            ):
                response = self.client.post(
                    reverse("pre_process", args=[str(uploaded.uuid)]),
                    {
                        "selected_analysis": [
                            "PunctaDistance",
                            "GreenRedIntensity",
                            "CENDot",
                        ],
                        "signalQuantificationEnabled": "true",
                        "signalQuantificationMode": "nuclear_cell_pair",
                        "punctaContourIntensityEnabled": "true",
                        "alternateNucleusDetectionEnabled": "true",
                        "nuclear_cell_pair_mode": "red_nucleus",
                    },
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "succeeded")
            self.assertEqual(
                self.client.session.get("selected_analysis"),
                ["NuclearCellPairIntensity"],
            )
            self.assertTrue(
                self.client.session.get("alternateNucleusDetectionEnabled")
            )
            self.assertEqual(
                self.client.session.get("alternateNucleusDetectionChannel"),
                "channel_red",
            )

    @override_settings(ANALYSIS_EXECUTION_MODE="sync")
    def test_pre_process_sync_mode_cancel_returns_cancelled_without_segment_redirect(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="sync_cancel")

            with patch(
                "core.views.pre_process.ensure_preview_assets",
                return_value=[],
            ), patch(
                "core.views.pre_process.run_analysis_batch",
                side_effect=AnalysisCancelled(),
            ):
                response = self.client.post(
                    reverse("pre_process", args=[str(uploaded.uuid)]),
                    {},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

            self.assertEqual(response.status_code, 409)
            payload = response.json()
            self.assertEqual(payload["status"], "cancelled")

    @override_settings(ANALYSIS_EXECUTION_MODE="sync")
    def test_pre_process_sync_mode_non_ajax_redirects_directly_to_display(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="sync_redirect")

            with patch(
                "core.views.pre_process.ensure_preview_assets",
                return_value=[],
            ), patch(
                "core.views.pre_process.run_analysis_batch",
                return_value=SimpleNamespace(storage_warning_message=""),
            ):
                response = self.client.post(
                    reverse("pre_process", args=[str(uploaded.uuid)]),
                    {},
                )

            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                response["Location"],
                reverse("display", args=[str(uploaded.uuid)]),
            )
            self.assertNotIn("/segment/", response["Location"])

    @override_settings(ANALYSIS_EXECUTION_MODE="sync")
    def test_pre_process_sync_mode_ajax_keeps_transient_quota_fallback_displayable(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="sync_quota_ajax")
            warning_message = "Storage quota prevented autosave."

            def run_batch_side_effect(*, user, context, progress, **_kwargs):
                self._create_segmented_image(
                    media_root,
                    uploaded=uploaded,
                    owner_id=get_guest_user(),
                )
                return SimpleNamespace(storage_warning_message=warning_message)

            with patch(
                "core.views.pre_process.ensure_preview_assets",
                return_value=[],
            ), patch(
                "core.views.pre_process.run_analysis_batch",
                side_effect=run_batch_side_effect,
            ):
                response = self.client.post(
                    reverse("pre_process", args=[str(uploaded.uuid)]),
                    {},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "succeeded")
            self.assertEqual(payload["storage_warning_message"], warning_message)
            self.assertIn(
                str(uploaded.uuid),
                self.client.session.get("transient_experiment_uuids", []),
            )

            display_response = self.client.get(reverse("display", args=[str(uploaded.uuid)]))
            self.assertEqual(display_response.status_code, 200)
            self.assertContains(display_response, warning_message)

    @override_settings(ANALYSIS_EXECUTION_MODE="sync")
    def test_pre_process_sync_mode_non_ajax_keeps_transient_quota_fallback_displayable(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="sync_quota_html")
            warning_message = "Storage quota prevented autosave."

            def run_batch_side_effect(*, user, context, progress, **_kwargs):
                self._create_segmented_image(
                    media_root,
                    uploaded=uploaded,
                    owner_id=get_guest_user(),
                )
                return SimpleNamespace(storage_warning_message=warning_message)

            with patch(
                "core.views.pre_process.ensure_preview_assets",
                return_value=[],
            ), patch(
                "core.views.pre_process.run_analysis_batch",
                side_effect=run_batch_side_effect,
            ):
                response = self.client.post(
                    reverse("pre_process", args=[str(uploaded.uuid)]),
                    {},
                )

            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                response["Location"],
                reverse("display", args=[str(uploaded.uuid)]),
            )
            self.assertIn(
                str(uploaded.uuid),
                self.client.session.get("transient_experiment_uuids", []),
            )

            display_response = self.client.get(reverse("display", args=[str(uploaded.uuid)]))
            self.assertEqual(display_response.status_code, 200)
            self.assertContains(display_response, warning_message)

    @override_settings(ANALYSIS_EXECUTION_MODE="sync")
    def test_pre_process_sync_mode_keeps_autosave_disabled_run_displayable(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="sync_autosave_disabled")
            update_user_preferences(self.user, {"auto_save_experiments": False})

            def run_batch_side_effect(*, user, context, progress, **_kwargs):
                self.assertFalse(context.config_snapshot["auto_save_experiments"])
                self._create_segmented_image(
                    media_root,
                    uploaded=uploaded,
                    owner_id=get_guest_user(),
                )
                return SimpleNamespace(storage_warning_message="")

            with patch(
                "core.views.pre_process.ensure_preview_assets",
                return_value=[],
            ), patch(
                "core.views.pre_process.run_analysis_batch",
                side_effect=run_batch_side_effect,
            ):
                response = self.client.post(
                    reverse("pre_process", args=[str(uploaded.uuid)]),
                    {},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "succeeded")
            self.assertIn(
                str(uploaded.uuid),
                self.client.session.get("transient_experiment_uuids", []),
            )

            display_response = self.client.get(reverse("display", args=[str(uploaded.uuid)]))
            self.assertEqual(display_response.status_code, 200)

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
    def test_progress_endpoint_forbids_other_user_batch(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_forbidden_progress")

            response = self.other_client.get(
                reverse("analysis_progress", args=[str(uploaded.uuid)]),
            )

            self.assertEqual(response.status_code, 403)

    @override_settings(ANALYSIS_EXECUTION_MODE="worker")
    def test_cancel_progress_forbids_other_user_batch(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_forbidden_cancel")

            response = self.other_client.post(
                reverse("cancel_progress", args=[str(uploaded.uuid)]),
            )

            self.assertEqual(response.status_code, 403)

    @override_settings(ANALYSIS_EXECUTION_MODE="worker")
    def test_set_progress_forbids_other_user_batch(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_forbidden_set")

            response = self.other_client.post(
                reverse("set_progress", args=[str(uploaded.uuid)]),
                data=json.dumps({"phase": "Queued"}),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["message"], SAFE_PROGRESS_WRITE_ERROR_MESSAGE)

    @override_settings(ANALYSIS_EXECUTION_MODE="worker")
    def test_set_progress_rejects_invalid_status(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_invalid_set")

            response = self.client.post(
                reverse("set_progress", args=[str(uploaded.uuid)]),
                data=json.dumps({"phase": "Queued", "status": "definitely-not-valid"}),
                content_type="application/json",
            )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["message"], SAFE_PROGRESS_WRITE_ERROR_MESSAGE)

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
            self.assertIsNone(response.json()["redirect"])
            self.assertEqual(
                response.json()["detail"],
                {"message": "Waiting for analysis worker."},
            )

    @override_settings(
        STORAGE_QUOTA_EDU_SUFFIXES=(".edu",),
        ANALYSIS_LIMIT_DEFAULT_MAX_ACTIVE_JOBS=1,
    )
    def test_enqueue_analysis_job_blocks_default_tier_second_distinct_active_job(self):
        enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )

        with self.assertRaises(AnalysisJobLimitExceeded):
            enqueue_analysis_job(
                user_id=self.user.id,
                raw_uuids=[str(uuid4())],
                config_snapshot={"execution_mode": "worker"},
            )

    @override_settings(
        STORAGE_QUOTA_EDU_SUFFIXES=(".edu",),
        ANALYSIS_LIMIT_DEFAULT_MAX_ACTIVE_JOBS=1,
    )
    def test_enqueue_analysis_job_counts_cancelling_jobs_toward_cap(self):
        first_job, _ = enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )
        AnalysisJob.objects.filter(pk=first_job.pk).update(
            status=AnalysisJob.Status.CANCELLING,
            cancellation_requested=True,
        )

        with self.assertRaises(AnalysisJobLimitExceeded):
            enqueue_analysis_job(
                user_id=self.user.id,
                raw_uuids=[str(uuid4())],
                config_snapshot={"execution_mode": "worker"},
            )

    @override_settings(
        STORAGE_QUOTA_EDU_SUFFIXES=(".edu",),
        ANALYSIS_LIMIT_DEFAULT_MAX_ACTIVE_JOBS=1,
    )
    def test_enqueue_analysis_job_reuses_same_batch_even_when_at_cap(self):
        batch_uuid = str(uuid4())
        first_job, first_created = enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[batch_uuid],
            config_snapshot={"execution_mode": "worker"},
        )

        second_job, second_created = enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[batch_uuid],
            config_snapshot={"execution_mode": "worker"},
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_job.pk, second_job.pk)

    @override_settings(
        STORAGE_QUOTA_EDU_SUFFIXES=(".edu",),
        ANALYSIS_LIMIT_DEFAULT_MAX_ACTIVE_JOBS=1,
        ANALYSIS_LIMIT_EDU_MAX_ACTIVE_JOBS=2,
    )
    def test_enqueue_analysis_job_allows_education_tier_two_active_jobs(self):
        first_job, _ = enqueue_analysis_job(
            user_id=self.edu_user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )
        second_job, _ = enqueue_analysis_job(
            user_id=self.edu_user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )

        self.assertNotEqual(first_job.pk, second_job.pk)
        with self.assertRaises(AnalysisJobLimitExceeded):
            enqueue_analysis_job(
                user_id=self.edu_user.id,
                raw_uuids=[str(uuid4())],
                config_snapshot={"execution_mode": "worker"},
            )

    @override_settings(
        ACCESS_UNRESTRICTED_EMAILS=("analysis-async@example.com",),
        STORAGE_QUOTA_EDU_SUFFIXES=(".edu",),
        ANALYSIS_LIMIT_DEFAULT_MAX_ACTIVE_JOBS=1,
    )
    def test_enqueue_analysis_job_unrestricted_email_bypasses_cap(self):
        first_job, _ = enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )
        second_job, _ = enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )

        self.assertNotEqual(first_job.pk, second_job.pk)

    @override_settings(
        STORAGE_QUOTA_EDU_SUFFIXES=(".edu",),
        ANALYSIS_LIMIT_DEFAULT_MAX_ACTIVE_JOBS=1,
    )
    def test_enqueue_analysis_job_terminal_jobs_do_not_count_toward_cap(self):
        first_job, _ = enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )
        AnalysisJob.objects.filter(pk=first_job.pk).update(
            status=AnalysisJob.Status.SUCCEEDED,
            finished_at=timezone.now(),
        )

        second_job, created = enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )

        self.assertTrue(created)
        self.assertNotEqual(first_job.pk, second_job.pk)

    @override_settings(ANALYSIS_EXECUTION_MODE="worker")
    def test_progress_handle_persists_safe_job_detail(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_detail")
            job, _ = enqueue_analysis_job(
                user_id=self.user.id,
                raw_uuids=[str(uploaded.uuid)],
                config_snapshot={"execution_mode": "worker"},
            )
            progress = AnalysisProgressHandle(str(uploaded.uuid), job=job)

            progress.set_phase(
                "Detecting Cells",
                status=AnalysisJob.Status.RUNNING,
                detail={
                    "fileIndex": 1,
                    "fileTotal": 2,
                    "fileName": "../worker_detail.dv",
                    "cellIndex": -1,
                    "message": "Running detection.",
                    "unsafe": "ignored",
                },
            )

            response = self.client.get(reverse("analysis_progress", args=[str(uploaded.uuid)]))

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["phase"], "Detecting Cells")
            self.assertEqual(
                payload["detail"],
                {
                    "fileName": "worker_detail.dv",
                    "message": "Running detection.",
                    "fileIndex": 1,
                    "fileTotal": 2,
                },
            )

    def test_progress_snapshot_includes_safe_file_detail(self):
        batch_key = str(uuid4())
        write_file_progress(
            batch_key,
            phase="Calculating Statistics",
            status="running",
            detail={
                "fileIndex": 3,
                "fileTotal": 5,
                "fileName": r"C:\tmp\cell_detail.dv",
                "cellIndex": 25,
                "cellTotal": 108,
                "message": "Statistics are running.",
            },
        )

        snapshot = get_progress_snapshot(batch_key=batch_key, user_id=self.user.id)

        self.assertEqual(snapshot.phase, "Calculating Statistics")
        self.assertEqual(
            snapshot.detail,
            {
                "fileName": "cell_detail.dv",
                "message": "Statistics are running.",
                "fileIndex": 3,
                "fileTotal": 5,
                "cellIndex": 25,
                "cellTotal": 108,
            },
        )

    def test_progress_snapshot_normalizes_legacy_file_progress_completed(self):
        batch_key = str(uuid4())
        write_file_progress(
            batch_key,
            phase="Completed",
            status=None,
        )

        snapshot = get_progress_snapshot(batch_key=batch_key, user_id=self.user.id)

        self.assertEqual(snapshot.status, "succeeded")
        self.assertEqual(snapshot.phase, "Completed")

    @override_settings(ANALYSIS_EXECUTION_MODE="worker")
    def test_progress_endpoint_includes_redirect_only_for_success(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_success")
            job, _ = enqueue_analysis_job(
                user_id=self.user.id,
                raw_uuids=[str(uploaded.uuid)],
                config_snapshot={"execution_mode": "worker"},
            )
            AnalysisJob.objects.filter(pk=job.pk).update(
                status=AnalysisJob.Status.SUCCEEDED,
                current_phase="Completed",
                finished_at=timezone.now(),
            )

            response = self.client.get(reverse("analysis_progress", args=[str(uploaded.uuid)]))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "succeeded")
            self.assertTrue(response.json()["redirect"])

    @override_settings(
        ANALYSIS_EXECUTION_MODE="worker",
        ANALYSIS_QUEUE_STALE_SECONDS=1,
    )
    def test_progress_endpoint_surfaces_stale_queued_job_without_mutating_get(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_stale_queue")
            job, _ = enqueue_analysis_job(
                user_id=self.user.id,
                raw_uuids=[str(uploaded.uuid)],
                config_snapshot={"execution_mode": "worker"},
            )
            AnalysisJob.objects.filter(pk=job.pk).update(
                created_at=timezone.now() - timezone.timedelta(seconds=5),
            )

            response = self.client.get(reverse("analysis_progress", args=[str(uploaded.uuid)]))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "failed")
            self.assertIn("expired", response.json()["failure_summary"].lower())
            self.assertIsNone(response.json()["redirect"])
            job.refresh_from_db()
            self.assertEqual(job.status, AnalysisJob.Status.QUEUED)
            self.assertIsNone(job.finished_at)

    @override_settings(
        ANALYSIS_EXECUTION_MODE="worker",
        ANALYSIS_RUNNING_STALE_SECONDS=1,
    )
    def test_progress_endpoint_surfaces_stale_running_job_without_mutating_get(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_stale_running")
            job, _ = enqueue_analysis_job(
                user_id=self.user.id,
                raw_uuids=[str(uploaded.uuid)],
                config_snapshot={"execution_mode": "worker"},
            )
            AnalysisJob.objects.filter(pk=job.pk).update(
                status=AnalysisJob.Status.RUNNING,
                current_phase="Detecting Cells",
                started_at=timezone.now() - timezone.timedelta(seconds=5),
            )

            response = self.client.get(reverse("analysis_progress", args=[str(uploaded.uuid)]))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "failed")
            self.assertIn("maximum runtime", response.json()["failure_summary"].lower())
            self.assertIsNone(response.json()["redirect"])
            job.refresh_from_db()
            self.assertEqual(job.status, AnalysisJob.Status.RUNNING)
            self.assertIsNone(job.finished_at)

    @override_settings(
        ANALYSIS_EXECUTION_MODE="worker",
        ANALYSIS_QUEUE_STALE_SECONDS=1,
    )
    def test_enqueue_analysis_job_reaps_stale_job_outside_get(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="worker_reap_queue")
            stale_job, _ = enqueue_analysis_job(
                user_id=self.user.id,
                raw_uuids=[str(uploaded.uuid)],
                config_snapshot={"execution_mode": "worker"},
            )
            AnalysisJob.objects.filter(pk=stale_job.pk).update(
                created_at=timezone.now() - timezone.timedelta(seconds=5),
            )

            replacement_job, created = enqueue_analysis_job(
                user_id=self.user.id,
                raw_uuids=[str(uploaded.uuid)],
                config_snapshot={"execution_mode": "worker"},
            )

            self.assertTrue(created)
            stale_job.refresh_from_db()
            self.assertEqual(stale_job.status, AnalysisJob.Status.FAILED)
            self.assertNotEqual(replacement_job.pk, stale_job.pk)

    @override_settings(ANALYSIS_EXECUTION_MODE="sync")
    def test_pre_process_sync_mode_sanitizes_internal_failures(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="sync_sanitized_failure")

            with patch(
                "core.views.pre_process.ensure_preview_assets",
                return_value=[],
            ), patch(
                "core.views.pre_process.run_analysis_batch",
                side_effect=RuntimeError("database password leaked"),
            ):
                response = self.client.post(
                    reverse("pre_process", args=[str(uploaded.uuid)]),
                    {},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

            self.assertEqual(response.status_code, 500)
            payload = response.json()
            self.assertTrue(payload["error"].startswith(SAFE_ANALYSIS_FAILURE_SUMMARY))
            self.assertIn("contact support with reference", payload["error"])
            self.assertNotIn("database password leaked", payload["error"])

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

    def test_run_analysis_worker_once_sanitizes_failure_summary(self):
        job, _ = enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[str(uuid4())],
            config_snapshot={"execution_mode": "worker"},
        )

        with patch(
            "core.management.commands.run_analysis_worker.run_analysis_batch",
            side_effect=RuntimeError("secret credentials"),
        ):
            call_command("run_analysis_worker", once=True)

        job.refresh_from_db()
        self.assertEqual(job.status, AnalysisJob.Status.FAILED)
        self.assertTrue(job.failure_summary.startswith(SAFE_ANALYSIS_FAILURE_SUMMARY))
        self.assertIn("contact support with reference", job.failure_summary)
        self.assertNotIn("secret credentials", job.failure_summary)

    def test_multi_file_analysis_progress_includes_run_counts(self):
        with temporary_media_root() as media_root:
            first = self._create_uploaded_image(media_root, name="counted_first")
            second = self._create_uploaded_image(media_root, name="counted_second")
            run_uuids = (str(first.uuid), str(second.uuid))
            batch_key = ",".join(run_uuids)
            context = AnalysisBatchContext(
                batch_key=batch_key,
                run_uuids=run_uuids,
                user_id=self.user.id,
                config_snapshot={"execution_mode": "sync"},
                execution_mode="sync",
            )
            progress = AnalysisProgressHandle(batch_key)
            observed_snapshots: list[tuple[str, dict[str, object]]] = []

            def preprocess_fn(image_uuid, uploaded_image, output_dir, cancel_check):
                snapshot = get_progress_snapshot(
                    batch_key=batch_key,
                    user_id=self.user.id,
                )
                observed_snapshots.append((snapshot.phase, snapshot.detail or {}))
                return Path(output_dir) / f"{image_uuid}.png"

            def predict_fn(preprocessed_image, output_dir, cancel_check):
                snapshot = get_progress_snapshot(
                    batch_key=batch_key,
                    user_id=self.user.id,
                )
                observed_snapshots.append((snapshot.phase, snapshot.detail or {}))
                return object()

            run_preprocess_and_inference_batch(
                user=self.user,
                context=context,
                progress=progress,
                preprocess_fn=preprocess_fn,
                predict_fn=predict_fn,
            )

        self.assertEqual(
            [phase for phase, _detail in observed_snapshots],
            [
                "Preprocessing Images (1/2)",
                "Detecting Cells (1/2)",
                "Preprocessing Images (2/2)",
                "Detecting Cells (2/2)",
            ],
        )
        self.assertEqual(
            [detail for _phase, detail in observed_snapshots],
            [
                {
                    "fileName": "counted_first.dv",
                    "fileIndex": 1,
                    "fileTotal": 2,
                },
                {
                    "fileName": "counted_first.dv",
                    "fileIndex": 1,
                    "fileTotal": 2,
                },
                {
                    "fileName": "counted_second.dv",
                    "fileIndex": 2,
                    "fileTotal": 2,
                },
                {
                    "fileName": "counted_second.dv",
                    "fileIndex": 2,
                    "fileTotal": 2,
                },
            ],
        )

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
