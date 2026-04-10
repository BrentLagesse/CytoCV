from __future__ import annotations

import errno
import json
import re
from contextlib import ExitStack, contextmanager
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import numpy as np
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.preferences import get_user_preferences, update_user_preferences
from core.config import DEFAULT_CHANNEL_CONFIG
from core.models import CellStatistics, DVLayerTifPreview, SegmentedImage, UploadedImage, get_guest_user
from core.mrcnn.preprocess_images import PreprocessedImageArtifact, preprocess_images
from core.services.artifact_storage import (
    PRE_PROCESS_FOLDER_NAME,
    PREVIEW_FOLDER_NAME,
    StorageQuotaExceeded,
    assert_user_can_save_runs,
    cleanup_transient_processing_artifacts,
    ensure_preview_assets,
    generate_preview_assets,
    get_run_storage_bytes,
    get_user_storage_projection,
    is_storage_full_error,
    refresh_user_storage_usage,
    sweep_user_run_artifacts,
)
from core.views.experiment import PROCESSING_STORAGE_FULL_MESSAGE as UPLOAD_STORAGE_FULL_MESSAGE
from core.views.experiment import experiment
from core.views.pre_process import PROCESSING_STORAGE_FULL_MESSAGE as PREPROCESS_STORAGE_FULL_MESSAGE
from core.views.segment_image import (
    AUTOSAVE_STORAGE_FULL_MESSAGE,
    PROCESSING_STORAGE_FULL_MESSAGE as SEGMENT_STORAGE_FULL_MESSAGE,
    finalize_segmented_run_batch,
)


@contextmanager
def temporary_media_root():
    with TemporaryDirectory() as temp_media:
        with ExitStack() as stack:
            stack.enter_context(
                override_settings(
                    MEDIA_ROOT=temp_media,
                    TRANSIENT_RUN_RETENTION_HOURS=1,
                )
            )
            for target in (
                "accounts.views.profile.MEDIA_ROOT",
                "core.config.MEDIA_ROOT",
                "core.mrcnn.preprocess_images.MEDIA_ROOT",
                "core.views.convert_to_image.MEDIA_ROOT",
                "core.views.display.MEDIA_ROOT",
                "core.views.experiment.MEDIA_ROOT",
                "core.views.pre_process.MEDIA_ROOT",
                "core.views.segment_image.MEDIA_ROOT",
                "core.views.utils.MEDIA_ROOT",
            ):
                stack.enter_context(patch(target, temp_media))
            yield Path(temp_media)


class ArtifactStorageTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="artifact-tests@example.com",
            password="TestPass123!",
        )
        self.factory = RequestFactory()
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
        uuid_value: str | None = None,
        name: str = "sample",
        created_at=None,
    ) -> UploadedImage:
        file_uuid = uuid_value or str(uuid4())
        source_path = media_root / file_uuid / f"{name}.dv"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"dv")
        uploaded = UploadedImage.objects.create(
            user=self.user,
            uuid=file_uuid,
            name=name,
            file_location=f"{file_uuid}/{name}.dv",
        )
        if created_at is not None:
            UploadedImage.objects.filter(pk=uploaded.pk).update(created_at=created_at)
            uploaded.refresh_from_db()
        return uploaded

    def _create_segmented_image(
        self,
        *,
        uuid_value: str,
        owner_id,
        name: str = "sample",
    ) -> SegmentedImage:
        return SegmentedImage.objects.create(
            user_id=owner_id,
            UUID=uuid_value,
            file_location=f"user_{uuid_value}/{name}.png",
            ImagePath=f"{uuid_value}/output/{name}_frame_0.png",
            CellPairPrefix=f"{uuid_value}/segmented/cell_",
            NumCells=1,
        )

    @staticmethod
    def _create_png(path: Path, *, color=(12, 34, 56)) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (4, 4), color=color).save(path, format="PNG")

    @staticmethod
    def _build_preprocessed_artifact(path: Path, *, image_id: str = "sample.dv") -> PreprocessedImageArtifact:
        return PreprocessedImageArtifact(
            image_id=image_id,
            preprocessed_path=path,
            original_height=4,
            original_width=4,
        )

    @staticmethod
    def _write_bytes(path: Path, size: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)

    def _create_preview_row(self, media_root: Path, uploaded: UploadedImage, file_name: str) -> DVLayerTifPreview:
        preview_path = media_root / str(uploaded.uuid) / PREVIEW_FOLDER_NAME / file_name
        self._create_png(preview_path)
        return DVLayerTifPreview.objects.create(
            wavelength="DIC",
            uploaded_image_uuid=uploaded,
            file_location=str(preview_path.relative_to(media_root)),
        )

    def _build_request(self, path: str = "/") -> object:
        request = self.factory.get(path)
        request.user = self.user
        middleware = SessionMiddleware(lambda inner_request: None)
        middleware.process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        return request


class PreviewArtifactTests(ArtifactStorageTestCase):
    def test_generate_preview_assets_writes_png_only(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="preview")

            layer_stack = np.arange(4 * 5 * 5, dtype=np.uint16).reshape(4, 5, 5)
            with patch(
                "core.services.artifact_storage._load_dv_layers",
                return_value=layer_stack,
            ):
                preview_rows = generate_preview_assets(uploaded, expected_layers=4)

            preview_dir = media_root / str(uploaded.uuid) / PREVIEW_FOLDER_NAME
            self.assertEqual(len(preview_rows), 4)
            self.assertEqual(DVLayerTifPreview.objects.filter(uploaded_image_uuid=uploaded).count(), 4)
            self.assertEqual(sorted(path.suffix for path in preview_dir.iterdir()), [".png", ".png", ".png", ".png"])
            self.assertFalse(any(preview_dir.glob("*.tif")))
            self.assertFalse(any(preview_dir.glob("*.jpg")))

    def test_ensure_preview_assets_regenerates_missing_preview_files(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="regen")
            DVLayerTifPreview.objects.create(
                wavelength="DIC",
                uploaded_image_uuid=uploaded,
                file_location=f"{uploaded.uuid}/{PREVIEW_FOLDER_NAME}/missing.png",
            )

            layer_stack = np.ones((2, 4, 4), dtype=np.uint16)
            with patch(
                "core.services.artifact_storage._load_dv_layers",
                return_value=layer_stack,
            ):
                preview_rows = ensure_preview_assets(uploaded, expected_layers=4)

            preview_dir = media_root / str(uploaded.uuid) / PREVIEW_FOLDER_NAME
            self.assertEqual(len(preview_rows), 2)
            self.assertEqual(DVLayerTifPreview.objects.filter(uploaded_image_uuid=uploaded).count(), 2)
            self.assertTrue((preview_dir / "preview-layer0.png").exists())
            self.assertTrue((preview_dir / "preview-layer1.png").exists())


class PreprocessEncodingTests(ArtifactStorageTestCase):
    def test_preprocess_images_writes_png_input(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="preprocess_png")
            self._write_channel_config(media_root, str(uploaded.uuid))

            with patch("core.mrcnn.preprocess_images.DVFile") as dv_file_cls:
                dv_file_cls.return_value.asarray.return_value = np.ones((4, 8, 8), dtype=np.uint16)
                artifact = preprocess_images(
                    str(uploaded.uuid),
                    uploaded,
                    media_root / str(uploaded.uuid),
                )

            self.assertIsNotNone(artifact)
            self.assertTrue(str(artifact.preprocessed_path).endswith(".png"))
            self.assertTrue(artifact.preprocessed_path.exists())
            self.assertFalse((media_root / str(uploaded.uuid) / "preprocessed_images_list.csv").exists())
            self.assertFalse(any((media_root / str(uploaded.uuid) / PRE_PROCESS_FOLDER_NAME).glob("*.tif")))


class CleanupHelperTests(ArtifactStorageTestCase):
    def test_cleanup_transient_processing_artifacts_removes_regenerable_files(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="cleanup")
            self._create_preview_row(media_root, uploaded, "preview-layer0.png")

            run_dir = media_root / str(uploaded.uuid)
            self._create_png(run_dir / PRE_PROCESS_FOLDER_NAME / "cleanup.png")
            (run_dir / "compressed_masks.csv").write_text("mask", encoding="utf-8")
            (run_dir / "preprocessed_images_list.csv").write_text("images", encoding="utf-8")
            (run_dir / "logs").mkdir(parents=True, exist_ok=True)
            (run_dir / "logs" / "step.log").write_text("log", encoding="utf-8")
            (run_dir / "cleanup.jpg").write_bytes(b"jpg")

            changed = cleanup_transient_processing_artifacts(
                str(uploaded.uuid),
                remove_preview_assets=True,
            )

            self.assertTrue(changed)
            self.assertFalse((run_dir / PRE_PROCESS_FOLDER_NAME).exists())
            self.assertFalse((run_dir / "compressed_masks.csv").exists())
            self.assertFalse((run_dir / "preprocessed_images_list.csv").exists())
            self.assertFalse((run_dir / "logs").exists())
            self.assertFalse((run_dir / "cleanup.jpg").exists())
            self.assertFalse((run_dir / PREVIEW_FOLDER_NAME).exists())
            self.assertFalse(DVLayerTifPreview.objects.filter(uploaded_image_uuid=uploaded).exists())
            self.assertTrue((run_dir / "cleanup.dv").exists())


class StorageCapacityHelperTests(ArtifactStorageTestCase):
    def test_is_storage_full_error_detects_enospc(self):
        exc = OSError(errno.ENOSPC, "No space left on device")
        self.assertTrue(is_storage_full_error(exc))

    def test_is_storage_full_error_detects_quota_message(self):
        exc = OSError(getattr(errno, "EDQUOT", errno.ENOSPC), "Disk quota exceeded")
        self.assertTrue(is_storage_full_error(exc))

    def test_assert_user_can_save_runs_raises_when_run_exceeds_available_storage(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="quota_run")
            self._create_segmented_image(
                uuid_value=str(uploaded.uuid),
                owner_id=get_guest_user(),
                name="quota_run",
            )
            self._write_bytes(media_root / str(uploaded.uuid) / "output" / "frame.png", 96)
            self.user.total_storage = 64
            self.user.save(update_fields=["total_storage"])

            with self.assertRaises(StorageQuotaExceeded):
                assert_user_can_save_runs(self.user, [str(uploaded.uuid)])

            self.assertEqual(get_run_storage_bytes(str(uploaded.uuid)), 98)

    def test_get_user_storage_projection_returns_average_and_capacity(self):
        with temporary_media_root() as media_root:
            first = self._create_uploaded_image(media_root, name="projection_first")
            second = self._create_uploaded_image(media_root, name="projection_second")
            self._create_segmented_image(
                uuid_value=str(first.uuid),
                owner_id=self.user.id,
                name="projection_first",
            )
            self._create_segmented_image(
                uuid_value=str(second.uuid),
                owner_id=self.user.id,
                name="projection_second",
            )
            self._write_bytes(media_root / str(first.uuid) / "output" / "frame.png", 98)
            self._write_bytes(media_root / str(second.uuid) / "output" / "frame.png", 48)
            self.user.total_storage = 300
            self.user.save(update_fields=["total_storage"])

            projection = get_user_storage_projection(self.user)

            self.assertEqual(projection["used_storage"], 150)
            self.assertEqual(projection["available_storage"], 150)
            self.assertEqual(projection["total_storage"], 300)
            self.assertEqual(projection["average_saved_run_bytes"], 75.0)
            self.assertEqual(projection["additional_files_possible"], 2)
            self.assertTrue(projection["projection_ready"])

            self.user.refresh_from_db()
            self.assertEqual(self.user.used_storage, 150)
            self.assertEqual(self.user.available_storage, 150)

    def test_get_user_storage_projection_returns_zero_capacity_when_full(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="projection_full")
            self._create_segmented_image(
                uuid_value=str(uploaded.uuid),
                owner_id=self.user.id,
                name="projection_full",
            )
            self._write_bytes(media_root / str(uploaded.uuid) / "output" / "frame.png", 98)
            self.user.total_storage = 100
            self.user.save(update_fields=["total_storage"])

            projection = get_user_storage_projection(self.user)

            self.assertEqual(projection["used_storage"], 100)
            self.assertEqual(projection["available_storage"], 0)
            self.assertEqual(projection["additional_files_possible"], 0)
            self.assertTrue(projection["projection_ready"])

    def test_get_user_storage_projection_is_not_ready_without_saved_history(self):
        self.user.total_storage = 2048
        self.user.save(update_fields=["total_storage"])

        projection = get_user_storage_projection(self.user)

        self.assertEqual(projection["used_storage"], 0)
        self.assertEqual(projection["available_storage"], 2048)
        self.assertEqual(projection["average_saved_run_bytes"], 0.0)
        self.assertEqual(projection["additional_files_possible"], 0)
        self.assertFalse(projection["projection_ready"])


class ArtifactSweepTests(ArtifactStorageTestCase):
    def test_sweep_user_run_artifacts_cleans_saved_run_transients_without_deleting_run(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="saved_run")
            self._create_segmented_image(
                uuid_value=str(uploaded.uuid),
                owner_id=self.user.id,
                name="saved_run",
            )
            self._create_preview_row(media_root, uploaded, "preview-layer0.png")

            run_dir = media_root / str(uploaded.uuid)
            self._create_png(run_dir / PRE_PROCESS_FOLDER_NAME / "saved_run.png")
            (run_dir / "compressed_masks.csv").write_text("mask", encoding="utf-8")

            result = sweep_user_run_artifacts(self.user)

            self.assertEqual(result["deleted_uuids"], [])
            self.assertIn(str(uploaded.uuid), result["cleaned_saved_runs"])
            self.assertTrue(UploadedImage.objects.filter(uuid=uploaded.uuid).exists())
            self.assertTrue(SegmentedImage.objects.filter(UUID=uploaded.uuid).exists())
            self.assertFalse((run_dir / PRE_PROCESS_FOLDER_NAME).exists())
            self.assertFalse((run_dir / PREVIEW_FOLDER_NAME).exists())

    def test_sweep_user_run_artifacts_deletes_stale_incomplete_upload(self):
        with temporary_media_root() as media_root:
            stale_time = timezone.now() - timedelta(hours=3)
            uploaded = self._create_uploaded_image(
                media_root,
                name="stale_incomplete",
                created_at=stale_time,
            )
            self._create_preview_row(media_root, uploaded, "preview-layer0.png")

            result = sweep_user_run_artifacts(self.user)

            self.assertIn(str(uploaded.uuid), result["deleted_uuids"])
            self.assertFalse(UploadedImage.objects.filter(uuid=uploaded.uuid).exists())
            self.assertFalse((media_root / str(uploaded.uuid)).exists())

    def test_sweep_user_run_artifacts_deletes_unprotected_stale_unsaved_run(self):
        with temporary_media_root() as media_root:
            stale_time = timezone.now() - timedelta(hours=3)
            uploaded = self._create_uploaded_image(
                media_root,
                name="stale_unsaved",
                created_at=stale_time,
            )
            guest_id = get_guest_user()
            self._create_segmented_image(
                uuid_value=str(uploaded.uuid),
                owner_id=guest_id,
                name="stale_unsaved",
            )
            (media_root / str(uploaded.uuid) / "output").mkdir(parents=True, exist_ok=True)
            self._create_png(media_root / str(uploaded.uuid) / "output" / "stale_unsaved_frame_0.png")

            result = sweep_user_run_artifacts(self.user)

            self.assertIn(str(uploaded.uuid), result["deleted_uuids"])
            self.assertFalse(UploadedImage.objects.filter(uuid=uploaded.uuid).exists())
            self.assertFalse(SegmentedImage.objects.filter(UUID=uploaded.uuid).exists())
            self.assertFalse((media_root / str(uploaded.uuid)).exists())

    def test_sweep_user_run_artifacts_keeps_protected_unsaved_run(self):
        with temporary_media_root() as media_root:
            stale_time = timezone.now() - timedelta(hours=3)
            uploaded = self._create_uploaded_image(
                media_root,
                name="protected_unsaved",
                created_at=stale_time,
            )
            guest_id = get_guest_user()
            self._create_segmented_image(
                uuid_value=str(uploaded.uuid),
                owner_id=guest_id,
                name="protected_unsaved",
            )
            self._create_preview_row(media_root, uploaded, "preview-layer0.png")

            result = sweep_user_run_artifacts(
                self.user,
                protected_uuids=[str(uploaded.uuid)],
            )

            self.assertEqual(result["deleted_uuids"], [])
            self.assertTrue(UploadedImage.objects.filter(uuid=uploaded.uuid).exists())
            self.assertTrue(SegmentedImage.objects.filter(UUID=uploaded.uuid).exists())


class SegmentAutosaveFinalizationTests(ArtifactStorageTestCase):
    def test_finalize_segmented_run_batch_saves_when_quota_allows(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="autosave_ok")
            self._create_segmented_image(
                uuid_value=str(uploaded.uuid),
                owner_id=get_guest_user(),
                name="autosave_ok",
            )
            self._write_bytes(media_root / str(uploaded.uuid) / "output" / "frame.png", 64)
            self.user.total_storage = 512
            self.user.save(update_fields=["total_storage"])

            request = self._build_request("/segment/")
            request.session["transient_experiment_uuids"] = [str(uploaded.uuid)]
            request.session.save()

            finalize_segmented_run_batch(
                request,
                [str(uploaded.uuid)],
                auto_save_experiments=True,
            )

            self.assertEqual(
                SegmentedImage.objects.get(UUID=uploaded.uuid).user_id,
                self.user.id,
            )
            self.assertNotIn(
                str(uploaded.uuid),
                request.session.get("transient_experiment_uuids", []),
            )
            self.assertEqual(list(get_messages(request)), [])
            self.user.refresh_from_db()
            self.assertEqual(self.user.used_storage, 66)

    def test_finalize_segmented_run_batch_keeps_run_transient_when_quota_is_full(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="autosave_full")
            self._create_segmented_image(
                uuid_value=str(uploaded.uuid),
                owner_id=get_guest_user(),
                name="autosave_full",
            )
            self._write_bytes(media_root / str(uploaded.uuid) / "output" / "frame.png", 96)
            self.user.total_storage = 32
            self.user.save(update_fields=["total_storage"])

            request = self._build_request("/segment/")
            request.session["transient_experiment_uuids"] = []
            request.session.save()

            finalize_segmented_run_batch(
                request,
                [str(uploaded.uuid)],
                auto_save_experiments=True,
            )

            self.assertEqual(
                SegmentedImage.objects.get(UUID=uploaded.uuid).user_id,
                get_guest_user(),
            )
            self.assertIn(
                str(uploaded.uuid),
                request.session.get("transient_experiment_uuids", []),
            )
            queued_messages = [message.message for message in get_messages(request)]
            self.assertIn(AUTOSAVE_STORAGE_FULL_MESSAGE, queued_messages)


class UploadQuotaProjectionViewTests(ArtifactStorageTestCase):
    def test_dashboard_uses_shared_storage_projection_summary(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="dashboard_projection")
            segmented = self._create_segmented_image(
                uuid_value=str(uploaded.uuid),
                owner_id=self.user.id,
                name="dashboard_projection",
            )
            CellStatistics.objects.create(
                segmented_image=segmented,
                cell_id=1,
                puncta_distance=1.0,
                puncta_line_intensity=2.0,
                nucleus_intensity_sum=3.0,
                cell_pair_intensity_sum=4.0,
            )

            with patch(
                "accounts.views.profile.get_user_storage_projection",
                return_value={
                    "used_storage": 100,
                    "available_storage": 200,
                    "total_storage": 300,
                    "average_saved_run_bytes": 100.0,
                    "additional_files_possible": 2,
                    "projection_ready": True,
                },
            ):
                response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 out of 3 files saved.")
        self.assertContains(
            response,
            "2 additional files can be saved before quota at your current average file size.",
        )

    def test_experiment_upload_page_includes_quota_projection_for_autosave_users(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="upload_projection")
            self._create_segmented_image(
                uuid_value=str(uploaded.uuid),
                owner_id=self.user.id,
                name="upload_projection",
            )
            self._write_bytes(media_root / str(uploaded.uuid) / "output" / "frame.png", 98)
            self.user.total_storage = 250
            self.user.save(update_fields=["total_storage"])

            response = self.client.get(reverse("experiment"))

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.context["upload_quota_payload_json"])
        self.assertTrue(payload["is_authenticated"])
        self.assertTrue(payload["auto_save_experiments"])
        self.assertEqual(payload["used_storage"], 100)
        self.assertEqual(payload["available_storage"], 150)
        self.assertEqual(payload["additional_files_possible"], 1)
        self.assertTrue(payload["projection_ready"])
        self.assertContains(response, 'id="uploadQuotaStatus"', html=False)
        self.assertContains(response, 'id="uploadQuotaProjection"', html=False)
        self.assertContains(response, "window.clearGlobalMessages", html=False)
        self.assertContains(response, "This queued workflow is estimated not to autosave", html=False)

    def test_experiment_upload_page_disables_quota_warning_when_autosave_is_off(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="upload_projection_off")
            self._create_segmented_image(
                uuid_value=str(uploaded.uuid),
                owner_id=self.user.id,
                name="upload_projection_off",
            )
            self._write_bytes(media_root / str(uploaded.uuid) / "output" / "frame.png", 98)
            preferences = get_user_preferences(self.user)
            preferences["auto_save_experiments"] = False
            update_user_preferences(self.user, preferences)

            response = self.client.get(reverse("experiment"))

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.context["upload_quota_payload_json"])
        self.assertTrue(payload["is_authenticated"])
        self.assertFalse(payload["auto_save_experiments"])
        self.assertContains(response, "Autosave off", html=False)
        self.assertContains(response, "queueExceedsEstimate && autoSaveExperiments", html=False)

    def test_experiment_upload_page_uses_no_warning_payload_for_guests(self):
        request = self.factory.get(reverse("experiment"))
        request.user = AnonymousUser()
        middleware = SessionMiddleware(lambda inner_request: None)
        middleware.process_request(request)
        request.session.save()
        response = experiment(request)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        match = re.search(
            r'<script id="uploadQuotaProjection" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1))
        self.assertFalse(payload["is_authenticated"])
        self.assertTrue(payload["auto_save_experiments"])
        self.assertFalse(payload["projection_ready"])
        self.assertEqual(payload["available_storage"], 0)

    def test_experiment_upload_page_preserves_restored_queue_payload_with_quota_payload(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="restored_queue")

            response = self.client.get(reverse("experiment"), {"restore": str(uploaded.uuid)})

        self.assertEqual(response.status_code, 200)
        restored_payload = json.loads(response.context["restored_queue_payload_json"])
        self.assertEqual(restored_payload, [{"uuid": str(uploaded.uuid), "name": "restored_queue"}])
        quota_payload = json.loads(response.context["upload_quota_payload_json"])
        self.assertTrue(quota_payload["is_authenticated"])
        self.assertContains(response, "restored_queue", html=False)


class ExperimentStorageIntegrationTests(ArtifactStorageTestCase):
    def test_experiment_invalid_upload_removes_saved_source_file(self):
        with temporary_media_root() as media_root:
            invalid_result = patch(
                "core.views.experiment.validate_dv_file",
                return_value=type(
                    "ValidationResult",
                    (),
                    {
                        "is_valid": False,
                        "layer_count": None,
                        "missing_channels": set(),
                        "required_channels": set(),
                        "error_message": "invalid",
                    },
                )(),
            )
            with invalid_result:
                response = self.client.post(
                    reverse("experiment"),
                    {"files": SimpleUploadedFile("invalid.dv", b"invalid")},
                )

            self.assertEqual(response.status_code, 302)
            self.assertFalse(UploadedImage.objects.exists())
            self.assertFalse(any(media_root.rglob("*.dv")))

    def test_cancel_progress_idle_hard_deletes_unsaved_run(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="idle_cancel")
            self._write_channel_config(media_root, str(uploaded.uuid))
            preview_row = self._create_preview_row(media_root, uploaded, "preview-layer0.png")

            response = self.client.post(
                reverse("cancel_progress", args=[str(uploaded.uuid)]),
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "cancelled")
            self.assertFalse(UploadedImage.objects.filter(uuid=uploaded.uuid).exists())
            self.assertFalse(DVLayerTifPreview.objects.filter(pk=preview_row.pk).exists())
            self.assertFalse((media_root / str(uploaded.uuid)).exists())

    def test_pre_process_cancel_hard_deletes_unsaved_run(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="cancelled_pre")
            self._write_channel_config(media_root, str(uploaded.uuid))
            preview_row = self._create_preview_row(media_root, uploaded, "preview-layer0.png")
            run_dir = media_root / str(uploaded.uuid)

            def fake_preprocess(*args, **kwargs):
                prep_dir = run_dir / PRE_PROCESS_FOLDER_NAME
                prep_dir.mkdir(parents=True, exist_ok=True)
                prep_path = prep_dir / "cancelled_pre.png"
                self._create_png(prep_path)
                return self._build_preprocessed_artifact(
                    prep_path,
                    image_id="cancelled_pre.dv",
                )

            with patch("core.views.pre_process.preprocess_images", side_effect=fake_preprocess), patch(
                "core.views.pre_process.predict_images",
                return_value=None,
            ):
                response = self.client.post(
                    reverse("pre_process", args=[str(uploaded.uuid)]),
                    {},
                )

            self.assertEqual(response.status_code, 409)
            self.assertFalse(UploadedImage.objects.filter(uuid=uploaded.uuid).exists())
            self.assertFalse(DVLayerTifPreview.objects.filter(pk=preview_row.pk).exists())
            self.assertFalse((run_dir / PRE_PROCESS_FOLDER_NAME).exists())
            self.assertFalse((run_dir / "preprocessed_images_list.csv").exists())
            self.assertFalse(run_dir.exists())

    def test_experiment_upload_storage_full_cleans_partial_batch_and_reports_error(self):
        with temporary_media_root() as media_root:
            valid_result = type(
                "ValidationResult",
                (),
                {
                    "is_valid": True,
                    "layer_count": 4,
                    "missing_channels": set(),
                    "required_channels": set(),
                    "error_message": "",
                },
            )()

            with patch("core.views.experiment.validate_dv_file", return_value=valid_result), patch(
                "core.views.experiment.extract_channel_config",
                return_value=DEFAULT_CHANNEL_CONFIG,
            ), patch(
                "core.views.experiment.extract_dv_scale_metadata",
                return_value={},
            ), patch(
                "core.views.experiment.generate_preview_assets",
                side_effect=OSError(errno.ENOSPC, "No space left on device"),
            ):
                response = self.client.post(
                    reverse("experiment"),
                    {"files": SimpleUploadedFile("full.dv", b"valid")},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )

            self.assertEqual(response.status_code, 507)
            self.assertEqual(response.json()["errors"], [UPLOAD_STORAGE_FULL_MESSAGE])
            self.assertFalse(UploadedImage.objects.exists())
            self.assertFalse(any(media_root.rglob("*.dv")))

    def test_pre_process_storage_full_redirects_back_with_cleanup(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="preprocess_full")
            self._write_channel_config(media_root, str(uploaded.uuid))
            preview_row = self._create_preview_row(media_root, uploaded, "preview-layer0.png")
            run_dir = media_root / str(uploaded.uuid)

            def fake_preprocess(*args, **kwargs):
                prep_dir = run_dir / PRE_PROCESS_FOLDER_NAME
                prep_dir.mkdir(parents=True, exist_ok=True)
                prep_path = prep_dir / "partial.png"
                self._create_png(prep_path)
                raise OSError(errno.ENOSPC, "No space left on device")

            response = None
            with patch("core.views.pre_process.preprocess_images", side_effect=fake_preprocess):
                response = self.client.post(
                    reverse("pre_process", args=[str(uploaded.uuid)]),
                    {},
                    follow=True,
                )

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, PREPROCESS_STORAGE_FULL_MESSAGE)
            self.assertTrue(UploadedImage.objects.filter(uuid=uploaded.uuid).exists())
            self.assertTrue(DVLayerTifPreview.objects.filter(pk=preview_row.pk).exists())
            self.assertFalse((run_dir / PRE_PROCESS_FOLDER_NAME).exists())
            self.assertFalse((run_dir / "preprocessed_images_list.csv").exists())

    def test_inference_storage_full_redirects_back_with_cleanup(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="inference_full")
            self._write_channel_config(media_root, str(uploaded.uuid))
            preview_row = self._create_preview_row(media_root, uploaded, "preview-layer0.png")
            run_dir = media_root / str(uploaded.uuid)

            def fake_preprocess(*args, **kwargs):
                prep_dir = run_dir / PRE_PROCESS_FOLDER_NAME
                prep_dir.mkdir(parents=True, exist_ok=True)
                prep_path = prep_dir / "prepared.png"
                self._create_png(prep_path)
                return self._build_preprocessed_artifact(
                    prep_path,
                    image_id="sample.dv",
                )

            def fake_predict(*args, **kwargs):
                (run_dir / "logs").mkdir(parents=True, exist_ok=True)
                (run_dir / "output").mkdir(parents=True, exist_ok=True)
                raise OSError(errno.ENOSPC, "No space left on device")

            with patch("core.views.pre_process.preprocess_images", side_effect=fake_preprocess), patch(
                "core.views.pre_process.predict_images",
                side_effect=fake_predict,
            ):
                response = self.client.post(
                    reverse("pre_process", args=[str(uploaded.uuid)]),
                    {},
                    follow=True,
                )

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, PREPROCESS_STORAGE_FULL_MESSAGE)
            self.assertTrue(UploadedImage.objects.filter(uuid=uploaded.uuid).exists())
            self.assertTrue(DVLayerTifPreview.objects.filter(pk=preview_row.pk).exists())
            self.assertFalse((run_dir / PRE_PROCESS_FOLDER_NAME).exists())
            self.assertFalse((run_dir / "output").exists())
            self.assertFalse((run_dir / "logs").exists())

    def test_convert_route_redirects_directly_to_segment(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="convert_redirect")

            response = self.client.get(
                reverse("experiment_convert", args=[str(uploaded.uuid)]),
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("experiment_segment", args=[str(uploaded.uuid)]),
        )

    def test_segment_storage_full_redirects_back_with_cleanup(self):
        with temporary_media_root() as media_root:
            uploaded = self._create_uploaded_image(media_root, name="segment_full")
            self._write_channel_config(media_root, str(uploaded.uuid))
            preview_row = self._create_preview_row(media_root, uploaded, "preview-layer0.png")
            run_dir = media_root / str(uploaded.uuid)
            output_dir = run_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            Image.fromarray(
                np.array(
                    [
                        [1, 1, 0, 0],
                        [1, 1, 0, 0],
                        [0, 0, 0, 0],
                        [0, 0, 0, 0],
                    ],
                    dtype=np.uint8,
                )
            ).save(
                output_dir / "mask.tif",
                format="TIFF",
            )

            class DummyDVFile:
                def __init__(self, *_args, **_kwargs):
                    self._array = np.ones((1, 4, 4), dtype=np.uint8)

                def asarray(self):
                    return self._array

                def close(self):
                    return None

            with patch("core.views.segment_image.DVFile", DummyDVFile), patch(
                "matplotlib.figure.Figure.savefig",
                side_effect=OSError(errno.ENOSPC, "No space left on device"),
            ):
                response = self.client.get(
                    reverse("experiment_segment", args=[str(uploaded.uuid)]),
                    follow=True,
                )

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, SEGMENT_STORAGE_FULL_MESSAGE)
            self.assertTrue(UploadedImage.objects.filter(uuid=uploaded.uuid).exists())
            self.assertTrue(DVLayerTifPreview.objects.filter(pk=preview_row.pk).exists())
            self.assertFalse((run_dir / "output").exists())
            self.assertFalse((run_dir / "segmented").exists())

