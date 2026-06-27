"""Path stability tests for media artifacts consumed across the workflow."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import UUID

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from core.models import UploadedImage
from core.services.artifact_paths import (
    output_frame_url,
    segmented_cell_image_url,
)
from core.services.artifact_storage import (
    output_media_path,
    preprocess_media_path,
    preview_media_path,
    run_media_path,
    segmented_media_path,
)
from core.services.neck_split import manifest_path, sidecar_path
from core.services.overlay_rendering import (
    overlay_cache_image_path,
    overlay_render_config_path,
)


class ArtifactPathContractTests(SimpleTestCase):
    """Lock down historical run, output, segmented, and overlay path layouts."""

    def test_run_artifact_paths_keep_current_layout(self):
        run_uuid = UUID("cef22bb0-b838-47f3-ab96-387cfb559b0b")
        image_stem = "sample"
        cell_id = 3

        with TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir) / "media"
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL="/media/"):
                uploaded = SimpleNamespace(uuid=run_uuid, name=image_stem)

                self.assertEqual(
                    UploadedImage.upload_to(uploaded, f"{image_stem}.dv"),
                    f"{run_uuid}/{image_stem}.dv",
                )
                self.assertEqual(
                    run_media_path(str(run_uuid)),
                    media_root.resolve() / str(run_uuid),
                )
                self.assertEqual(
                    run_media_path(str(run_uuid)) / "channel_config.json",
                    media_root.resolve() / str(run_uuid) / "channel_config.json",
                )
                self.assertEqual(
                    preview_media_path(str(run_uuid)) / "preview-layer2.png",
                    media_root.resolve() / str(run_uuid) / "preview_images" / "preview-layer2.png",
                )
                self.assertEqual(
                    preprocess_media_path(str(run_uuid)) / f"{image_stem}.png",
                    media_root.resolve() / str(run_uuid) / "preprocessed_images" / f"{image_stem}.png",
                )
                self.assertEqual(
                    output_media_path(str(run_uuid)) / "mask.tif",
                    media_root.resolve() / str(run_uuid) / "output" / "mask.tif",
                )
                self.assertEqual(
                    output_media_path(str(run_uuid)) / "cellpairs.tif",
                    media_root.resolve() / str(run_uuid) / "output" / "cellpairs.tif",
                )
                self.assertEqual(
                    output_media_path(str(run_uuid)) / f"{image_stem}_frame_2.png",
                    media_root.resolve() / str(run_uuid) / "output" / f"{image_stem}_frame_2.png",
                )
                self.assertEqual(
                    output_frame_url(uuid=run_uuid, image_name=f"{image_stem}.dv", frame_index=2),
                    f"{settings.MEDIA_URL}{run_uuid}/output/{image_stem}_frame_2.png",
                )
                self.assertEqual(
                    manifest_path(media_root / str(run_uuid)),
                    media_root / str(run_uuid) / "output" / "pair-geometry.json",
                )
                self.assertEqual(
                    sidecar_path(media_root / str(run_uuid), f"{image_stem}.dv", cell_id),
                    media_root / str(run_uuid) / "output" / f"{image_stem}-{cell_id}.neck_split",
                )
                self.assertEqual(
                    output_media_path(str(run_uuid)) / f"{image_stem}-{cell_id}.outline",
                    media_root.resolve() / str(run_uuid) / "output" / f"{image_stem}-{cell_id}.outline",
                )

    def test_segmented_and_overlay_paths_keep_current_layout(self):
        run_uuid = UUID("cef22bb0-b838-47f3-ab96-387cfb559b0b")
        image_stem = "sample"
        cell_id = 3
        channel_index = 2

        with TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir) / "media"
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL="/media/"):
                self.assertEqual(
                    segmented_media_path(str(run_uuid)) / f"cell_{cell_id}.png",
                    media_root.resolve() / str(run_uuid) / "segmented" / f"cell_{cell_id}.png",
                )
                self.assertEqual(
                    segmented_media_path(str(run_uuid)) / f"{image_stem}-{channel_index}-{cell_id}.png",
                    media_root.resolve()
                    / str(run_uuid)
                    / "segmented"
                    / f"{image_stem}-{channel_index}-{cell_id}.png",
                )
                self.assertEqual(
                    segmented_media_path(str(run_uuid)) / f"{image_stem}-{channel_index}-{cell_id}-no_outline.png",
                    media_root.resolve()
                    / str(run_uuid)
                    / "segmented"
                    / f"{image_stem}-{channel_index}-{cell_id}-no_outline.png",
                )
                self.assertEqual(
                    segmented_cell_image_url(
                        uuid=run_uuid,
                        image_name=f"{image_stem}.dv",
                        channel_index=channel_index,
                        cell_id=cell_id,
                    ),
                    f"{settings.MEDIA_URL}{run_uuid}/segmented/{image_stem}-{channel_index}-{cell_id}.png",
                )
                self.assertEqual(
                    segmented_cell_image_url(
                        uuid=run_uuid,
                        image_name=f"{image_stem}.dv",
                        channel_index=channel_index,
                        cell_id=cell_id,
                        outline=False,
                    ),
                    f"{settings.MEDIA_URL}{run_uuid}/segmented/{image_stem}-{channel_index}-{cell_id}-no_outline.png",
                )
                self.assertEqual(
                    overlay_render_config_path(str(run_uuid)),
                    media_root / str(run_uuid) / "segmented" / "overlay-render-config.json",
                )
                for channel in ("red", "green", "blue"):
                    with self.subTest(channel=channel):
                        self.assertEqual(
                            overlay_cache_image_path(str(run_uuid), cell_id, channel),
                            media_root
                            / str(run_uuid)
                            / "segmented"
                            / "overlay-cache-v4"
                            / f"cell-{cell_id}-{channel}.png",
                        )
