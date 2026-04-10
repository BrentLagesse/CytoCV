from __future__ import annotations

import csv
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import json
from io import BytesIO, StringIO
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from unittest.mock import patch

import numpy as np
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.cell_analysis import Analysis
from core.config import DEFAULT_CHANNEL_CONFIG
from core.image_processing import GrayImage
from core.models import CellStatistics, DVLayerTifPreview, SegmentedImage, UploadedImage
from core.services.overlay_rendering import (
    build_legacy_debug_image_path,
    build_overlay_render_config,
    ensure_overlay_cache_image,
    overlay_cache_image_path,
    render_overlay_images_for_cell,
    write_overlay_render_config,
)
from core.stats_plugins import (
    build_stats_execution_plan,
    get_plugin_class,
    instantiate_selected_plugins,
    load_available_plugin_ids,
)
from core.views.segment_image import _resolve_uploaded_dv_path


@contextmanager
def temporary_media_root():
    with TemporaryDirectory() as temp_media:
        with ExitStack() as stack:
            stack.enter_context(override_settings(MEDIA_ROOT=temp_media))
            stack.enter_context(patch("accounts.views.profile.MEDIA_ROOT", temp_media))
            stack.enter_context(patch("core.config.MEDIA_ROOT", temp_media))
            stack.enter_context(patch("core.views.display.MEDIA_ROOT", temp_media))
            stack.enter_context(patch("core.views.pre_process.MEDIA_ROOT", temp_media))
            yield Path(temp_media)


class RouteSurfaceRefactorTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="surface-tests@example.com",
            password="TestPass123!",
        )
        self.client.login(email=self.user.email, password="TestPass123!")

    def _assert_removed_paths(self, response):
        content = response.content.decode("utf-8")
        for removed in (
            'href="/profile/"',
            'a[href="/profile/"]',
            'href="/settings/"',
            'a[href="/settings/"]',
            'href="/preferences/"',
            'a[href="/preferences/"]',
            '"/image/upload/"',
            "'/image/upload/'",
            '"/image/display/files/sync-selection/"',
            "'/image/display/files/sync-selection/'",
        ):
            self.assertNotIn(removed, content)

    @staticmethod
    def _write_channel_config(media_root: Path, uuid_value: str):
        output_dir = media_root / uuid_value
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "channel_config.json").write_text(
            json.dumps(DEFAULT_CHANNEL_CONFIG),
            encoding="utf-8",
        )

    def _create_uploaded_image(self, uuid_value: str, name: str = "sample") -> UploadedImage:
        return UploadedImage.objects.create(
            user=self.user,
            uuid=uuid_value,
            name=name,
            file_location=f"{uuid_value}/{name}.dv",
        )

    def _create_segmented_image(self, uuid_value: str, name: str = "sample") -> SegmentedImage:
        return SegmentedImage.objects.create(
            user=self.user,
            UUID=uuid_value,
            file_location=f"user_{uuid_value}/{name}.png",
            ImagePath=f"{uuid_value}/output/{name}_frame_0.png",
            CellPairPrefix=f"{uuid_value}/segmented/cell_",
            NumCells=0,
        )

    @staticmethod
    def _write_segmented_cell_assets(
        media_root: Path,
        uuid_value: str,
        image_stem: str,
        *,
        cell_id: int = 1,
    ) -> dict[str, np.ndarray]:
        segmented_dir = media_root / uuid_value / "segmented"
        segmented_dir.mkdir(parents=True, exist_ok=True)

        channel_pixels = {
            "channel_red": np.full((6, 6, 3), (220, 30, 30), dtype=np.uint8),
            "channel_green": np.full((6, 6, 3), (30, 220, 30), dtype=np.uint8),
            "channel_blue": np.full((6, 6, 3), (30, 30, 220), dtype=np.uint8),
            "DIC": np.full((6, 6, 3), (120, 120, 120), dtype=np.uint8),
        }

        for channel_name, channel_index in DEFAULT_CHANNEL_CONFIG.items():
            pixels = channel_pixels[channel_name]
            Image.fromarray(pixels).save(
                segmented_dir / f"{image_stem}-{channel_index}-{cell_id}.png"
            )
            Image.fromarray(pixels).save(
                segmented_dir / f"{image_stem}-{channel_index}-{cell_id}-no_outline.png"
            )
        (segmented_dir / f"cell_{cell_id}.png").write_bytes(b"png")
        return channel_pixels

    @staticmethod
    def _write_overlay_config(uuid_value: str, image_stem: str) -> dict[str, object]:
        render_config = build_overlay_render_config(
            image_stem=image_stem,
            channel_config=DEFAULT_CHANNEL_CONFIG,
            kernel_size=3,
            kernel_deviation=1,
            puncta_line_width=1,
            arrested="Metaphase Arrested",
            selected_analysis=[],
            puncta_line_mode="red_puncta",
            nuclear_cell_pair_mode="green_nucleus",
            puncta_line_width_px=1,
            cen_dot_distance_value_used=37.0,
            cen_dot_collinearity_threshold=66,
            green_contour_filter_enabled=False,
            alternate_red_detection=False,
            puncta_line_width_unit="px",
            cen_dot_distance_unit="px",
        )
        write_overlay_render_config(uuid_value, render_config)
        return render_config

    @staticmethod
    def _create_cell_stats(
        segmented: SegmentedImage,
        image_stem: str,
        *,
        cell_id: int = 1,
        **overrides,
    ) -> CellStatistics:
        defaults = dict(
            segmented_image=segmented,
            cell_id=cell_id,
            puncta_distance=0.0,
            puncta_line_intensity=0.0,
            nucleus_intensity_sum=0.0,
            cell_pair_intensity_sum=0.0,
            red_intensity_1=0.0,
            red_intensity_2=0.0,
            red_intensity_3=0.0,
            green_intensity_1=0.0,
            green_intensity_2=0.0,
            green_intensity_3=0.0,
            red_in_green_intensity_1=0.0,
            red_in_green_intensity_2=0.0,
            red_in_green_intensity_3=0.0,
            green_in_green_intensity_1=0.0,
            green_in_green_intensity_2=0.0,
            green_in_green_intensity_3=0.0,
            green_red_intensity_1=0.0,
            green_red_intensity_2=0.0,
            green_red_intensity_3=0.0,
            dv_file_path=f"{segmented.UUID}/{image_stem}.dv",
            image_name=f"{image_stem}.dv",
            properties={
                "nuclear_cell_pair_mode": "green_nucleus",
                "puncta_line_mode": "red_puncta",
            },
        )
        defaults.update(overrides)
        return CellStatistics.objects.create(**defaults)

    def test_segment_image_uses_stored_file_location_for_dv_path(self):
        uuid_value = str(uuid4())
        display_name = "220720_M2129_020_PRJ - Copy"
        stored_name = "220720_M2129_020_PRJ_-_Copy.dv"
        with temporary_media_root() as media_root:
            stored_path = media_root / uuid_value / stored_name
            stored_path.parent.mkdir(parents=True, exist_ok=True)
            stored_path.write_bytes(b"dv")
            uploaded = UploadedImage.objects.create(
                user=self.user,
                uuid=uuid_value,
                name=display_name,
                file_location=f"{uuid_value}/{stored_name}",
            )

            resolved = _resolve_uploaded_dv_path(uploaded)

        self.assertEqual(resolved, stored_path)

    def test_reverse_uses_new_public_routes(self):
        uuid_value = str(uuid4())
        self.assertEqual(reverse("home"), "/")
        self.assertEqual(reverse("signin"), "/signin/")
        self.assertEqual(reverse("account_settings"), "/account-settings/")
        self.assertEqual(reverse("workflow_defaults"), "/workflow-defaults/")
        self.assertEqual(reverse("experiment"), "/experiment/")
        self.assertEqual(
            reverse("pre_process", args=[uuid_value]),
            f"/experiment/{uuid_value}/pre-process/",
        )
        self.assertEqual(
            reverse("experiment_convert", args=[uuid_value]),
            f"/experiment/{uuid_value}/convert/",
        )
        self.assertEqual(
            reverse("experiment_segment", args=[uuid_value]),
            f"/experiment/{uuid_value}/segment/",
        )
        self.assertEqual(
            reverse("display", args=[uuid_value]),
            f"/experiment/{uuid_value}/display/",
        )
        self.assertEqual(
            reverse("cell_overlay_image", args=[uuid_value, 7, "green"]),
            f"/experiment/{uuid_value}/cell/7/overlay/green/",
        )

    def test_removed_legacy_routes_return_404(self):
        uuid_value = str(uuid4())
        for path in (
            "/login/",
            "/profile/",
            "/settings/",
            "/preferences/",
            "/image/upload/",
            "/image/preprocess/",
            f"/image/preprocess/{uuid_value}/",
            f"/image/{uuid_value}/convert/",
            f"/image/{uuid_value}/segment/",
            f"/image/{uuid_value}/display/",
            "/image/display/files/save/",
            "/image/display/files/unsave/",
            "/image/display/files/sync-selection/",
            f"/image/{uuid_value}/main-channel/",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404, path)

    @override_settings(RECAPTCHA_ENABLED=False)
    def test_signin_uses_renamed_template(self):
        self.client.logout()
        response = self.client.get(reverse("signin"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/signin.html")

    def test_authenticated_pages_render_renamed_templates(self):
        response = self.client.get(reverse("account_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account_settings.html")
        self._assert_removed_paths(response)
        self.assertContains(response, reverse("workflow_defaults"))

        response = self.client.get(reverse("workflow_defaults"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "workflow_defaults.html")
        self._assert_removed_paths(response)
        self.assertContains(response, reverse("experiment"))

        response = self.client.get(reverse("experiment"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form/experiment.html")
        self._assert_removed_paths(response)

        home_response = self.client.get(reverse("home"))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, reverse("experiment"))
        self.assertNotContains(home_response, "/image/upload/")

    def test_pre_process_uses_renamed_template_and_routes(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            uploaded = self._create_uploaded_image(uuid_value, name="preprocess")
            DVLayerTifPreview.objects.create(
                wavelength="DIC",
                uploaded_image_uuid=uploaded,
                file_location=f"{uuid_value}/preprocessed_images/preprocess-image0.jpg",
            )

            response = self.client.get(reverse("pre_process", args=[uuid_value]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pre_process.html")
        self.assertContains(response, reverse("experiment"))
        self.assertContains(response, reverse("display", args=[uuid_value]))
        self._assert_removed_paths(response)

    def test_display_uses_renamed_template_and_routes(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="display")
            self._create_segmented_image(uuid_value, name="display")

            response = self.client.get(reverse("display", args=[uuid_value]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "display.html")
        self.assertContains(
            response,
            "/experiment/${fileUUID}/main-channel/",
            html=False,
        )
        self.assertContains(
            response,
            "/experiment/display/files/sync-selection/",
            html=False,
        )
        self._assert_removed_paths(response)

    def test_display_uses_overlay_endpoint_for_fluorescence_contour_on_images(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="display-fallback")
            segmented = self._create_segmented_image(uuid_value, name="display-fallback")
            segmented.NumCells = 1
            segmented.save(update_fields=["NumCells"])
            self._write_segmented_cell_assets(media_root, uuid_value, "display-fallback")
            self._create_cell_stats(segmented, "display-fallback")
            self._write_overlay_config(uuid_value, "display-fallback")

            response = self.client.get(reverse("display", args=[uuid_value]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "blue"]),
            html=False,
        )
        self.assertContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "red"]),
            html=False,
        )
        self.assertContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "green"]),
            html=False,
        )
        self.assertContains(
            response,
            f"/media/{uuid_value}/segmented/display-fallback-0-1.png",
            html=False,
        )

    def test_dashboard_uses_overlay_endpoint_for_fluorescence_contour_on_images(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="dashboard-overlay")
            segmented = self._create_segmented_image(uuid_value, name="dashboard-overlay")
            segmented.user = self.user
            segmented.NumCells = 1
            segmented.save(update_fields=["user", "NumCells"])
            self._write_segmented_cell_assets(media_root, uuid_value, "dashboard-overlay")
            self._create_cell_stats(segmented, "dashboard-overlay")
            self._write_overlay_config(uuid_value, "dashboard-overlay")

            response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "blue"]),
            html=False,
        )
        self.assertContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "red"]),
            html=False,
        )
        self.assertContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "green"]),
            html=False,
        )

    def test_overlay_endpoint_renders_pixel_exact_png_from_cached_crops(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="overlay-source")
            segmented = self._create_segmented_image(uuid_value, name="overlay-source")
            segmented.NumCells = 1
            segmented.save(update_fields=["NumCells"])
            self._write_segmented_cell_assets(media_root, uuid_value, "overlay-source")
            cell_stat = self._create_cell_stats(segmented, "overlay-source")
            render_config = self._write_overlay_config(uuid_value, "overlay-source")

            expected = render_overlay_images_for_cell(
                uuid_value,
                cell_stat,
                render_config,
            )["green"]
            response = self.client.get(
                reverse("cell_overlay_image", args=[uuid_value, 1, "green"])
            )

            self.assertEqual(response.status_code, 200)
            payload = b"".join(response.streaming_content)
            rendered = np.array(Image.open(BytesIO(payload)))
            self.assertTrue(np.array_equal(rendered, np.array(expected)))
            self.assertTrue(
                overlay_cache_image_path(uuid_value, 1, "green").exists()
            )

    def test_overlay_endpoint_returns_404_for_unauthorized_user(self):
        other_user = get_user_model().objects.create_user(
            email="overlay-other@example.com",
            password="TestPass123!",
        )
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            UploadedImage.objects.create(
                user=other_user,
                uuid=uuid_value,
                name="overlay-private",
                file_location=f"{uuid_value}/overlay-private.dv",
            )
            segmented = SegmentedImage.objects.create(
                user=other_user,
                UUID=uuid_value,
                file_location=f"user_{uuid_value}/overlay-private.png",
                ImagePath=f"{uuid_value}/output/overlay-private_frame_0.png",
                CellPairPrefix=f"{uuid_value}/segmented/cell_",
                NumCells=1,
            )
            self._write_segmented_cell_assets(media_root, uuid_value, "overlay-private")
            self._create_cell_stats(segmented, "overlay-private")
            self._write_overlay_config(uuid_value, "overlay-private")

            response = self.client.get(
                reverse("cell_overlay_image", args=[uuid_value, 1, "green"])
            )

        self.assertEqual(response.status_code, 404)

    def test_overlay_cache_warm_deduplicates_concurrent_channel_requests(self):
        uuid_value = str(uuid4())
        with temporary_media_root():
            self._create_uploaded_image(uuid_value, name="overlay-dedupe")
            segmented = self._create_segmented_image(uuid_value, name="overlay-dedupe")
            cell_stat = self._create_cell_stats(segmented, "overlay-dedupe")
            render_config = {"image_stem": "overlay-dedupe"}
            expected_paths = {
                channel: overlay_cache_image_path(uuid_value, 1, channel)
                for channel in ("blue", "green", "red")
            }
            start_barrier = threading.Barrier(3)
            render_calls = 0
            render_lock = threading.Lock()

            def fake_render(*args, **kwargs):
                nonlocal render_calls
                with render_lock:
                    render_calls += 1
                time.sleep(0.15)
                return {
                    "blue": Image.fromarray(np.full((4, 4, 3), (20, 20, 220), dtype=np.uint8)),
                    "green": Image.fromarray(np.full((4, 4, 3), (20, 220, 20), dtype=np.uint8)),
                    "red": Image.fromarray(np.full((4, 4, 3), (220, 20, 20), dtype=np.uint8)),
                }

            def warm_channel(channel: str):
                start_barrier.wait(timeout=5)
                return ensure_overlay_cache_image(
                    uuid_value,
                    1,
                    channel,
                    cell_stat=cell_stat,
                    render_config=render_config,
                )

            with patch(
                "core.services.overlay_rendering.render_overlay_images_for_cell",
                side_effect=fake_render,
            ):
                with ThreadPoolExecutor(max_workers=3) as executor:
                    results = list(executor.map(warm_channel, ("blue", "green", "red")))

            self.assertTrue(expected_paths["blue"].exists())
            self.assertTrue(expected_paths["green"].exists())
            self.assertTrue(expected_paths["red"].exists())

        self.assertEqual(render_calls, 1)
        self.assertEqual(results[0], expected_paths["blue"])
        self.assertEqual(results[1], expected_paths["green"])
        self.assertEqual(results[2], expected_paths["red"])

    def test_overlay_endpoint_falls_back_to_legacy_debug_image_when_cache_missing(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="overlay-legacy")
            segmented = self._create_segmented_image(uuid_value, name="overlay-legacy")
            segmented.NumCells = 1
            segmented.save(update_fields=["NumCells"])
            self._create_cell_stats(segmented, "overlay-legacy")

            legacy_image = Image.fromarray(
                np.full((5, 5, 3), (25, 200, 25), dtype=np.uint8)
            )
            legacy_path = build_legacy_debug_image_path(
                uuid_value,
                "overlay-legacy",
                1,
                "green",
            )
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_image.save(legacy_path)

            response = self.client.get(
                reverse("cell_overlay_image", args=[uuid_value, 1, "green"])
            )
            self.assertEqual(response.status_code, 200)
            payload = b"".join(response.streaming_content)
            rendered = np.array(Image.open(BytesIO(payload)))
            self.assertTrue(np.array_equal(rendered, np.array(legacy_image)))

    def test_dashboard_cell_pair_cards_use_stat_formatter_for_numeric_metrics(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "if (Number.isInteger(value)) {", html=False)
        self.assertContains(response, "return value.toFixed(3);", html=False)
        self.assertContains(response, "return 'N/A';", html=False)
        self.assertContains(
            response,
            "distance: formatStatValue(cellStats ? cellStats.puncta_distance : null),",
            html=False,
        )
        self.assertContains(
            response,
            "punctaLineIntensity: formatStatValue(cellStats ? cellStats.puncta_line_intensity : null),",
            html=False,
        )
        self.assertContains(
            response,
            "redInRedIntensity1: formatStatValue(cellStats ? cellStats.red_intensity_1 : null),",
            html=False,
        )
        self.assertContains(
            response,
            "greenInGreenIntensity1: formatStatValue(cellStats ? cellStats.green_in_green_intensity_1 : null),",
            html=False,
        )
        self.assertContains(
            response,
            "nucleusIntensitySum: (!cellStats || nuclearUnavailable) ? 'N/A' : formatStatValue(cellStats.nucleus_intensity_sum),",
            html=False,
        )
        self.assertContains(
            response,
            "biorientation: formatStatValue(cellStats ? cellStats.biorientation : null),",
            html=False,
        )
        self.assertContains(
            response,
            "return [1, -1, 2, -2];",
            html=False,
        )
        self.assertContains(
            response,
            "return [1, 2, -1, -2];",
            html=False,
        )
        self.assertContains(
            response,
            "return [-1, -2, 1, 2];",
            html=False,
        )
        self.assertContains(
            response,
            "buildFullCircularCellOrder(currentCellNumber, maxCells)",
            html=False,
        )
        self.assertContains(
            response,
            "'Measurement/Contour Ratio 1 (Green/Red)': 'measurement_contour_ratio_1'",
            html=False,
        )
        self.assertContains(
            response,
            "'Measurement/Contour Ratio 1 (Red/Green)': 'measurement_contour_ratio_1'",
            html=False,
        )
        self.assertContains(
            response,
            "'Measurement/Contour Ratio 3 (Red/Green)': 'measurement_contour_ratio_3'",
            html=False,
        )

    def test_display_cell_pair_cards_use_stat_formatter_for_numeric_metrics(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="display-stats")
            self._create_segmented_image(uuid_value, name="display-stats")

            response = self.client.get(reverse("display", args=[uuid_value]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "distance: formatStatValue(cellStats ? cellStats.puncta_distance : null),",
            html=False,
        )
        self.assertContains(
            response,
            "punctaLineIntensity: formatStatValue(cellStats ? cellStats.puncta_line_intensity : null),",
            html=False,
        )
        self.assertContains(
            response,
            "redInRedIntensity1: formatStatValue(cellStats ? cellStats.red_intensity_1 : null),",
            html=False,
        )
        self.assertContains(
            response,
            "redInGreenIntensity1: formatStatValue(cellStats ? cellStats.red_in_green_intensity_1 : null),",
            html=False,
        )
        self.assertContains(
            response,
            "nucleusIntensitySum: (!cellStats || nuclearUnavailable) ? 'N/A' : formatStatValue(cellStats.nucleus_intensity_sum),",
            html=False,
        )
        self.assertContains(
            response,
            "biorientation: formatStatValue(cellStats ? cellStats.biorientation : null),",
            html=False,
        )
        self.assertContains(
            response,
            "return [1, -1, 2, -2];",
            html=False,
        )
        self.assertContains(
            response,
            "return [1, 2, -1, -2];",
            html=False,
        )
        self.assertContains(
            response,
            "return [-1, -2, 1, 2];",
            html=False,
        )
        self.assertContains(
            response,
            "buildFullCircularCellOrder(currentCellNumber, maxCells)",
            html=False,
        )
        self.assertContains(
            response,
            "'Measurement/Contour Ratio 1 (Green/Red)': 'measurement_contour_ratio_1'",
            html=False,
        )
        self.assertContains(
            response,
            "'Measurement/Contour Ratio 1 (Red/Green)': 'measurement_contour_ratio_1'",
            html=False,
        )
        self.assertContains(
            response,
            "'Measurement/Contour Ratio 3 (Red/Green)': 'measurement_contour_ratio_3'",
            html=False,
        )

    def test_display_surfaces_raw_contour_sums_and_labels_ratio_explicitly(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="display-raw-intensity")
            segmented = self._create_segmented_image(uuid_value, name="display-raw-intensity")
            segmented.NumCells = 1
            segmented.save(update_fields=["NumCells"])
            self._write_segmented_cell_assets(media_root, uuid_value, "display-raw-intensity")
            self._create_cell_stats(
                segmented,
                "display-raw-intensity",
                red_intensity_1=11.0,
                green_intensity_1=7.0,
                red_in_green_intensity_1=5.0,
                green_in_green_intensity_1=13.0,
                green_red_intensity_1=99.0,
                properties={
                    "nuclear_cell_pair_mode": "red_nucleus",
                    "puncta_line_mode": "green_puncta",
                },
                category_cen_dot=1,
            )

            response = self.client.get(reverse("display", args=[uuid_value]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Raw Contour Intensity Sums")
        self.assertContains(response, "Measurement/Contour ratio 1")
        self.assertContains(response, "Measurement/Contour")
        self.assertContains(response, "Formula")
        self.assertContains(response, "Measurement/Contour Ratio 1 (Green/Red)")
        self.assertContains(response, "Measurement/Contour Ratio 2 (Green/Red)")
        self.assertContains(response, "Measurement/Contour Ratio 3 (Green/Red)")
        self.assertContains(response, "Green/Red: Green in Red / Red in Red")
        self.assertContains(response, "Line + Spot Metrics")
        self.assertContains(response, "Distance between Green Puncta")
        self.assertContains(response, "Red Intensity over Green Line")
        self.assertContains(response, "Contour slots 1/2/3 are ranked consistently after clipping to the segmented cell")
        self.assertNotContains(response, "Intensity + Green Output")
        self.assertContains(response, '"red_intensity_1": 11.0', html=False)
        self.assertContains(response, '"red_in_green_intensity_1": 5.0', html=False)
        self.assertContains(response, '"green_in_green_intensity_1": 13.0', html=False)
        self.assertContains(response, '"measurement_contour_ratio_1": 0.6363636363636364', html=False)
        self.assertContains(response, '"measurement_contour_ratio_formula": "Green in Red / Red in Red"', html=False)
        self.assertContains(response, '"puncta_distance_label": "Distance between Green Puncta"', html=False)
        self.assertContains(
            response,
            '"category_cen_dot_label": "One green dot with each red dot"',
            html=False,
        )
        self.assertContains(response, "cellStats.category_cen_dot_label || 'N/A'", html=False)
        self.assertNotContains(response, "const categories = ['One green dot with each red dot'", html=False)
        self.assertNotContains(response, "Green/Red Ratio 1 (Compatibility)")

    def test_dashboard_surfaces_raw_contour_sums_and_labels_ratio_explicitly(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="dashboard-raw-intensity")
            segmented = self._create_segmented_image(uuid_value, name="dashboard-raw-intensity")
            segmented.user = self.user
            segmented.NumCells = 1
            segmented.save(update_fields=["user", "NumCells"])
            self._write_segmented_cell_assets(media_root, uuid_value, "dashboard-raw-intensity")
            self._create_cell_stats(
                segmented,
                "dashboard-raw-intensity",
                red_intensity_1=19.0,
                green_intensity_1=23.0,
                red_in_green_intensity_1=29.0,
                green_in_green_intensity_1=31.0,
                green_red_intensity_1=99.0,
                properties={
                    "nuclear_cell_pair_mode": "green_nucleus",
                    "puncta_line_mode": "green_puncta",
                },
                category_cen_dot=1,
            )

            response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Raw Contour Intensity Sums")
        self.assertContains(response, "Measurement/Contour ratio 1")
        self.assertContains(response, "Measurement/Contour")
        self.assertContains(response, "Formula")
        self.assertContains(response, "Measurement/Contour Ratio 1 (Red/Green)")
        self.assertContains(response, "Measurement/Contour Ratio 2 (Red/Green)")
        self.assertContains(response, "Measurement/Contour Ratio 3 (Red/Green)")
        self.assertContains(response, "Red/Green: Red in Green / Green in Green")
        self.assertContains(response, "Line + Spot Metrics")
        self.assertContains(response, "Distance between Green Puncta")
        self.assertContains(response, "Red Intensity over Green Line")
        self.assertContains(response, "Contour slots 1/2/3 are ranked consistently after clipping to the segmented cell")
        self.assertNotContains(response, "Intensity + Green Output")
        self.assertContains(response, '"red_intensity_1": 19.0', html=False)
        self.assertContains(response, '"green_intensity_1": 23.0', html=False)
        self.assertContains(response, '"green_in_green_intensity_1": 31.0', html=False)
        self.assertContains(response, '"measurement_contour_ratio_formula": "Red in Green / Green in Green"', html=False)
        self.assertContains(response, '"puncta_distance_label": "Distance between Green Puncta"', html=False)
        self.assertContains(
            response,
            '"category_cen_dot_label": "One green dot with each red dot"',
            html=False,
        )
        self.assertContains(response, "cellStats.category_cen_dot_label || 'N/A'", html=False)
        self.assertNotContains(response, "const categories = ['One green dot with each red dot'", html=False)
        self.assertNotContains(response, "Green/Red Ratio 1 (Compatibility)")

    def test_display_csv_export_includes_ratio_columns_after_raw_intensity_sums(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="display-ratio-export")
            segmented = self._create_segmented_image(uuid_value, name="display-ratio-export")
            segmented.NumCells = 1
            segmented.save(update_fields=["NumCells"])
            self._write_segmented_cell_assets(media_root, uuid_value, "display-ratio-export")
            self._create_cell_stats(
                segmented,
                "display-ratio-export",
                red_in_green_intensity_1=11.0,
                green_in_green_intensity_1=22.0,
                red_in_green_intensity_2=8.0,
                green_in_green_intensity_2=4.0,
                red_in_green_intensity_3=18.0,
                green_in_green_intensity_3=6.0,
                green_red_intensity_1=99.0,
                green_red_intensity_2=99.0,
                green_red_intensity_3=99.0,
                properties={"nuclear_cell_pair_mode": "green_nucleus"},
            )

            response = self.client.get(
                reverse("display", args=[uuid_value]),
                {"_export": "csv"},
            )

        self.assertEqual(response.status_code, 200)
        csv_rows = list(csv.DictReader(StringIO(response.content.decode("utf-8"))))
        self.assertEqual(len(csv_rows), 1)
        header_row = csv_rows[0].keys()
        self.assertIn("Red in Red Intensity 1", header_row)
        self.assertIn("Measurement/Contour Ratio 1 (Red/Green)", header_row)
        self.assertIn("Measurement/Contour Ratio 2 (Red/Green)", header_row)
        self.assertIn("Measurement/Contour Ratio 3 (Red/Green)", header_row)
        self.assertLess(
            list(header_row).index("Green in Green Intensity 3"),
            list(header_row).index("Measurement/Contour Ratio 1 (Red/Green)"),
        )
        self.assertLess(
            list(header_row).index("Measurement/Contour Ratio 3 (Red/Green)"),
            list(header_row).index("Distance of Green from Red 1"),
        )
        self.assertEqual(csv_rows[0]["Measurement/Contour Ratio 1 (Red/Green)"], "0.500")
        self.assertEqual(csv_rows[0]["Measurement/Contour Ratio 2 (Red/Green)"], "2.000")
        self.assertEqual(csv_rows[0]["Measurement/Contour Ratio 3 (Red/Green)"], "3.000")


class PluginMappingRegressionTests(TestCase):
    def test_plugin_loader_maps_stable_ids_to_renamed_modules(self):
        plugin_ids = load_available_plugin_ids()
        self.assertIn("PunctaDistance", plugin_ids)
        self.assertIn("CENDot", plugin_ids)

        plugin_class = get_plugin_class("RedLineIntensity")
        self.assertEqual(plugin_class.__name__, "PunctaDistance")
        self.assertTrue(issubclass(plugin_class, Analysis))

        instances = instantiate_selected_plugins(["RedLineIntensity", "CENDot"])
        self.assertEqual(
            [instance.__class__.__name__ for instance in instances],
            ["PunctaDistance", "CENDot"],
        )
        self.assertEqual(GrayImage.__name__, "GrayImage")

    def test_build_stats_execution_plan_normalizes_raw_plugin_selection(self):
        plan = build_stats_execution_plan(
            ["UnknownPlugin", "NucleusIntensity", "NuclearCellularIntensity", "BlueNucleusIntensity"]
        )

        self.assertEqual(plan.normalized_plugins, ("NuclearCellPairIntensity",))
        self.assertEqual(plan.selected_plugins, ("NuclearCellPairIntensity",))
        self.assertEqual(plan.required_channels, ("DIC", "channel_red", "channel_green"))
        self.assertEqual(
            [instance.__class__.__name__ for instance in plan.analyses],
            ["NuclearCellPairIntensity"],
        )

