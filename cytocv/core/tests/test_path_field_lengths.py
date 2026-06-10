"""Regression tests for DB-backed generated artifact path lengths."""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.test import TestCase, override_settings

from core.models import DVLayerTifPreview, SegmentedImage, UploadedImage
from core.services.analysis_progress_contract import (
    progress_log_ref,
    safe_analysis_failure_summary,
)
from core.services.artifact_paths import (
    cell_pair_prefix_url,
    media_url,
    normalize_media_field_path,
    output_frame_url,
    segmented_image_file_location,
    segmented_image_path_url,
)
from core.services.artifact_storage import _safe_remove_path


LONG_STEM = "m8523_2h_auxin_10microgpermlNOC_01_P4_PRJ"
LONGER_STEM = f"{LONG_STEM}_capacity_regression_suffix"
SHORT_STEM = "m8523_7"


class PathFieldLengthRegressionTests(TestCase):
    """Ensure long user-derived artifact paths are not capped at 100 chars."""

    def test_path_backed_model_fields_use_expanded_capacity(self):
        self.assertEqual(UploadedImage._meta.get_field("file_location").max_length, 512)
        self.assertEqual(SegmentedImage._meta.get_field("file_location").max_length, 512)
        self.assertEqual(SegmentedImage._meta.get_field("ImagePath").max_length, 512)
        self.assertEqual(SegmentedImage._meta.get_field("CellPairPrefix").max_length, 512)
        self.assertEqual(DVLayerTifPreview._meta.get_field("file_location").max_length, 512)

    def test_artifact_path_helpers_preserve_current_storage_semantics(self):
        run_uuid = UUID("cef22bb0-b838-47f3-ab96-387cfb559b0b")
        image_path = output_frame_url(
            uuid=run_uuid,
            image_name=LONG_STEM,
            frame_index=0,
        )

        self.assertEqual(
            image_path,
            f"{settings.MEDIA_URL}{run_uuid}/output/{LONG_STEM}_frame_0.png",
        )
        self.assertEqual(len(LONG_STEM), 41)
        self.assertGreater(len(image_path), 100)
        self.assertEqual(len(image_path), 104)
        self.assertEqual(
            segmented_image_file_location(uuid=run_uuid, image_name=LONG_STEM),
            f"user_{run_uuid}/{LONG_STEM}.png",
        )
        self.assertEqual(
            segmented_image_path_url(uuid=run_uuid, image_name=LONG_STEM),
            image_path,
        )
        self.assertEqual(
            cell_pair_prefix_url(uuid=run_uuid),
            f"{settings.MEDIA_URL}{run_uuid}/segmented/cell_",
        )
        self.assertEqual(
            media_url(run_uuid, "output", f"{LONG_STEM}_frame_0.png"),
            image_path,
        )

    def test_segmented_image_accepts_generated_image_path_longer_than_100(self):
        run_uuid = UUID("cef22bb0-b838-47f3-ab96-387cfb559b0b")
        file_location = segmented_image_file_location(
            uuid=run_uuid,
            image_name=LONG_STEM,
        )
        image_path = segmented_image_path_url(uuid=run_uuid, image_name=LONG_STEM)
        cell_pair_prefix = cell_pair_prefix_url(uuid=run_uuid)

        self.assertEqual(len(LONG_STEM), 41)
        self.assertGreater(len(image_path), 100)
        self.assertEqual(len(image_path), 104)
        self.assertLessEqual(len(image_path), SegmentedImage._meta.get_field("ImagePath").max_length)

        segmented = SegmentedImage(
            UUID=run_uuid,
            file_location=file_location,
            ImagePath=image_path,
            CellPairPrefix=cell_pair_prefix,
            NumCells=0,
        )
        segmented.full_clean()
        segmented.save()
        segmented.refresh_from_db()

        self.assertEqual(segmented.ImagePath, image_path)
        self.assertEqual(segmented.file_location.name, file_location)
        self.assertEqual(segmented.CellPairPrefix, cell_pair_prefix)

    def test_all_expanded_path_fields_validate_values_longer_than_100(self):
        run_uuid = UUID("d1d825d9-74a2-483c-af29-ea12f4bd245d")
        upload_path = f"{run_uuid}/{LONGER_STEM}.dv"
        preview_path = f"{run_uuid}/previews/{LONGER_STEM}/preview-layer0.png"
        segmented_file_location = segmented_image_file_location(
            uuid=run_uuid,
            image_name=LONGER_STEM,
        )
        segmented_image_path = segmented_image_path_url(
            uuid=run_uuid,
            image_name=LONGER_STEM,
        )
        segmented_cell_pair_prefix = media_url(
            run_uuid,
            "segmented",
            LONGER_STEM,
            "cell_",
        )

        self.assertGreater(len(upload_path), 100)
        self.assertGreater(len(preview_path), 100)
        self.assertGreater(len(segmented_file_location), 100)
        self.assertGreater(len(segmented_image_path), 100)
        self.assertGreater(len(segmented_cell_pair_prefix), 100)

        uploaded = UploadedImage(
            uuid=run_uuid,
            name=LONGER_STEM,
            file_location=upload_path,
        )
        uploaded.full_clean()
        uploaded.save()

        segmented = SegmentedImage(
            UUID=run_uuid,
            file_location=segmented_file_location,
            ImagePath=segmented_image_path,
            CellPairPrefix=segmented_cell_pair_prefix,
            NumCells=0,
        )
        segmented.full_clean()
        segmented.save()

        preview = DVLayerTifPreview(
            uploaded_image_uuid=uploaded,
            wavelength="488",
            file_location=preview_path,
        )
        preview.full_clean()
        preview.save()

        uploaded.refresh_from_db()
        segmented.refresh_from_db()
        preview.refresh_from_db()

        self.assertEqual(uploaded.file_location.name, upload_path)
        self.assertEqual(segmented.file_location.name, segmented_file_location)
        self.assertEqual(segmented.ImagePath, segmented_image_path)
        self.assertEqual(segmented.CellPairPrefix, segmented_cell_pair_prefix)
        self.assertEqual(preview.file_location.name, preview_path)

    def test_short_generated_paths_still_validate_and_save(self):
        run_uuid = UUID("7e34b758-4252-46db-a8e6-6d449124f720")
        file_location = segmented_image_file_location(
            uuid=run_uuid,
            image_name=SHORT_STEM,
        )
        image_path = segmented_image_path_url(uuid=run_uuid, image_name=SHORT_STEM)
        cell_pair_prefix = cell_pair_prefix_url(uuid=run_uuid)

        self.assertLessEqual(len(image_path), 100)

        segmented = SegmentedImage(
            UUID=run_uuid,
            file_location=file_location,
            ImagePath=image_path,
            CellPairPrefix=cell_pair_prefix,
            NumCells=0,
        )
        segmented.full_clean()
        segmented.save()
        segmented.refresh_from_db()

        self.assertEqual(segmented.ImagePath, image_path)
        self.assertEqual(segmented.file_location.name, file_location)
        self.assertEqual(segmented.CellPairPrefix, cell_pair_prefix)

    def test_segmented_image_update_or_create_defaults_accept_long_generated_path(self):
        run_uuid = UUID("cef22bb0-b838-47f3-ab96-387cfb559b0b")
        defaults = {
            "file_location": segmented_image_file_location(
                uuid=run_uuid,
                image_name=LONG_STEM,
            ),
            "ImagePath": segmented_image_path_url(uuid=run_uuid, image_name=LONG_STEM),
            "CellPairPrefix": cell_pair_prefix_url(uuid=run_uuid),
            "NumCells": 0,
        }

        self.assertGreater(len(defaults["ImagePath"]), 100)

        segmented, created = SegmentedImage.objects.update_or_create(
            UUID=run_uuid,
            defaults=defaults,
        )
        segmented.refresh_from_db()

        self.assertTrue(created)
        self.assertEqual(segmented.ImagePath, defaults["ImagePath"])
        self.assertEqual(segmented.file_location.name, defaults["file_location"])
        self.assertEqual(segmented.CellPairPrefix, defaults["CellPairPrefix"])

    def test_media_field_path_normalization_accepts_relative_and_public_media_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir) / "media"
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL="/media/"):
                self.assertEqual(
                    normalize_media_field_path("uuid/file.dv"),
                    media_root / "uuid/file.dv",
                )
                self.assertEqual(
                    normalize_media_field_path("/media/uuid/file.dv"),
                    media_root / "uuid/file.dv",
                )

    def test_safe_remove_path_rejects_absolute_path_outside_media_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir) / "media"
            media_root.mkdir()
            outside = Path(temp_dir) / "outside.txt"
            outside.write_text("do not delete", encoding="utf-8")

            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL="/media/"):
                self.assertFalse(_safe_remove_path(outside))
                self.assertTrue(outside.exists())

    def test_safe_analysis_failure_summary_includes_reference_without_internals(self):
        batch_key = "cef22bb0-b838-47f3-ab96-387cfb559b0b"
        message = safe_analysis_failure_summary(batch_key)

        self.assertIn(progress_log_ref(batch_key), message)
        self.assertNotIn("Traceback", message)
        self.assertNotIn("DataError", message)
        self.assertNotIn("password", message.lower())
