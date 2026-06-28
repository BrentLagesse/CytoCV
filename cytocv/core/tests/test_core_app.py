"""Broad Django surface tests for routes, artifacts, exports, and frontend contracts."""

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
import tifffile
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.cell_analysis import Analysis
from core.config import DEFAULT_CHANNEL_CONFIG
from core.image_processing import GrayImage
from core.models import CellStatistics, DVLayerTifPreview, SegmentedImage, UploadedImage
from core.services.neck_split import NeckSplit, sidecar_path, write_neck_split
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


CORE_STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"


def _frontend_static_text(relative_path: str) -> str:
    return (CORE_STATIC_ROOT / relative_path).read_text(encoding="utf-8")


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
    FOOTER_LINKS = (
        "https://www.uwb.edu/stem/about",
        "https://www.uwb.edu/stem/about/departments/css",
        "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        "https://www.washington.edu/online/privacy",
        "https://www.washington.edu/online/terms",
        "https://www.uwb.edu/accessibility/",
    )
    FILES_DATA_REQUIRED_KEYS = {
        "MainImagePath",
        "MainImagePaths",
        "NumberOfCells",
        "CellPairImages",
        "Image_Name",
        "ScaleContext",
        "ChannelConfig",
        "Statistics",
        "NoCellsWarning",
    }

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

    def _assert_footer_present(self, response):
        self.assertContains(response, "UW Bothell School of STEM")
        self.assertContains(response, "Department of Computing &amp; Software Systems", html=False)
        self.assertContains(response, "18115 Campus Way NE, Bothell, WA 98011-8246")
        self.assertContains(response, "425.352.5000")
        self.assertContains(response, "License")
        self.assertContains(response, "Privacy")
        self.assertContains(response, "Terms")
        self.assertContains(response, "Accessibility")
        self.assertContains(
            response,
            "Licensed under",
        )
        self.assertContains(
            response,
            "CC BY-NC-SA 4.0",
        )
        self.assertContains(response, reverse("license"))
        self.assertContains(
            response,
            "/static/assets/uwb/web-white-left-school-signature-uw-bothell.png",
            html=False,
        )
        for url in self.FOOTER_LINKS:
            self.assertContains(response, url, html=False)

    def _assert_footer_absent(self, response):
        self.assertNotContains(response, '<footer class="site-footer"', html=False)
        self.assertNotContains(response, "Licensed under")
        self.assertNotContains(
            response,
            "/static/assets/uwb/web-white-left-school-signature-uw-bothell.png",
            html=False,
        )

    def _assert_files_data_payload_contract(self, payload):
        self.assertTrue(
            self.FILES_DATA_REQUIRED_KEYS.issubset(payload.keys()),
            sorted(self.FILES_DATA_REQUIRED_KEYS.difference(payload.keys())),
        )

    def test_static_frontend_javascript_does_not_embed_template_syntax(self):
        for path in CORE_STATIC_ROOT.rglob("*.js"):
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(CORE_STATIC_ROOT)):
                for token in ("{%", "%}", "{{", "}}"):
                    self.assertNotIn(token, source)

    def test_results_viewer_animation_keyframes_are_shared(self):
        shared_css = _frontend_static_text("css/components/results-viewer.css")
        dashboard_css = _frontend_static_text("css/pages/dashboard.css")
        display_css = _frontend_static_text("css/pages/display.css")
        keyframes = (
            "tableFullscreenEnter",
            "tableFullscreenExit",
            "cellSelectEnterForward",
            "cellSelectEnterBackward",
            "cellSelectExitForward",
            "cellSelectExitBackward",
            "skeletonShimmer",
        )

        for keyframe in keyframes:
            with self.subTest(keyframe=keyframe):
                marker = f"@keyframes {keyframe}"
                self.assertIn(marker, shared_css)
                self.assertNotIn(marker, dashboard_css)
                self.assertNotIn(marker, display_css)

    def test_workflow_control_styles_are_shared_without_moving_page_owned_rules(self):
        shared_css = _frontend_static_text("css/components/workflow-controls.css")
        experiment_css = _frontend_static_text("css/pages/experiment.css")
        workflow_css = _frontend_static_text("css/pages/workflow-defaults.css")
        shared_selectors = (
            ".signal-mode-panel {",
            ".length-unit-caret {",
            ".length-unit-trigger:hover {",
            ".channel-order-control .channel-chip {",
            ".channel-order-action-copy {",
        )
        page_owned_selectors = (
            ".length-unit-option.is-selected",
            ".popup-backdrop.modal-enter",
            ".channel-order-control {",
        )

        for selector in shared_selectors:
            with self.subTest(selector=selector):
                self.assertIn(selector, shared_css)
                self.assertNotIn(selector, experiment_css)
                self.assertNotIn(selector, workflow_css)

        for selector in page_owned_selectors:
            with self.subTest(page_owned_selector=selector):
                self.assertIn(selector, experiment_css)
                self.assertIn(selector, workflow_css)

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

    @staticmethod
    def _write_labeled_tiff(path: Path):
        labels = [
            "sample_PRJ_w625.tif",
            "sample_PRJ_w435.tif",
            "sample_PRJ_w525.tif",
            "sample_R3D_REF.tif",
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        tifffile.imwrite(
            path,
            np.ones((4, 5, 6), dtype=np.uint16),
            photometric="minisblack",
            imagej=True,
            metadata={"Labels": labels, "mode": "composite"},
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
    def _write_output_frame_assets(
        media_root: Path,
        uuid_value: str,
        image_stem: str,
        *,
        frame_indices: tuple[int, ...] = (0, 1, 2, 3),
    ) -> None:
        output_dir = media_root / uuid_value / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        frame_colors = {
            0: (120, 120, 120),
            1: (30, 30, 220),
            2: (30, 220, 30),
            3: (220, 30, 30),
        }
        for frame_index in frame_indices:
            color = frame_colors.get(frame_index, (200, 200, 200))
            Image.fromarray(
                np.full((8, 8, 3), color, dtype=np.uint8)
            ).save(output_dir / f"{image_stem}_frame_{frame_index}.png")

    @staticmethod
    def _write_overlay_cache_image(
        uuid_value: str,
        cell_id: int,
        channel: str,
        *,
        color: tuple[int, int, int],
    ) -> Path:
        path = overlay_cache_image_path(uuid_value, cell_id, channel)
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.full((6, 6, 3), color, dtype=np.uint8)).save(path)
        return path

    @staticmethod
    def _write_historical_overlay_cache_image(
        media_root: Path,
        uuid_value: str,
        cell_id: int,
        channel: str,
        *,
        color: tuple[int, int, int],
        schema_version: int = 3,
    ) -> Path:
        path = (
            media_root
            / uuid_value
            / "segmented"
            / f"overlay-cache-v{schema_version}"
            / f"cell-{cell_id}-{channel}.png"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.full((6, 6, 3), color, dtype=np.uint8)).save(path)
        return path

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
            green_contour_filter_enabled=False,
            alternate_red_detection=False,
            puncta_line_width_unit="px",
            cen_dot_distance_unit="px",
        )
        write_overlay_render_config(uuid_value, render_config)
        return render_config

    @staticmethod
    def _write_neck_split_sidecar(
        media_root: Path,
        uuid_value: str,
        image_stem: str,
        *,
        cell_id: int = 1,
        split: NeckSplit | None = None,
    ) -> Path:
        target = sidecar_path(media_root / uuid_value, f"{image_stem}.dv", cell_id)
        write_neck_split(
            target,
            split or NeckSplit(x1=0, y1=0, x2=5, y2=5),
        )
        return target

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
            red_in_red_total_intensity_1=0.0,
            red_in_red_max_intensity_1=0.0,
            red_in_red_average_intensity_1=0.0,
            red_in_red_total_intensity_2=0.0,
            red_in_red_max_intensity_2=0.0,
            red_in_red_average_intensity_2=0.0,
            red_in_red_total_intensity_3=0.0,
            red_in_red_max_intensity_3=0.0,
            red_in_red_average_intensity_3=0.0,
            green_in_red_total_intensity_1=0.0,
            green_in_red_max_intensity_1=0.0,
            green_in_red_average_intensity_1=0.0,
            green_in_red_total_intensity_2=0.0,
            green_in_red_max_intensity_2=0.0,
            green_in_red_average_intensity_2=0.0,
            green_in_red_total_intensity_3=0.0,
            green_in_red_max_intensity_3=0.0,
            green_in_red_average_intensity_3=0.0,
            red_in_green_total_intensity_1=0.0,
            red_in_green_max_intensity_1=0.0,
            red_in_green_average_intensity_1=0.0,
            red_in_green_total_intensity_2=0.0,
            red_in_green_max_intensity_2=0.0,
            red_in_green_average_intensity_2=0.0,
            red_in_green_total_intensity_3=0.0,
            red_in_green_max_intensity_3=0.0,
            red_in_green_average_intensity_3=0.0,
            green_in_green_total_intensity_1=0.0,
            green_in_green_max_intensity_1=0.0,
            green_in_green_average_intensity_1=0.0,
            green_in_green_total_intensity_2=0.0,
            green_in_green_max_intensity_2=0.0,
            green_in_green_average_intensity_2=0.0,
            green_in_green_total_intensity_3=0.0,
            green_in_green_max_intensity_3=0.0,
            green_in_green_average_intensity_3=0.0,
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
        self.assertEqual(reverse("about"), "/about/")
        self.assertEqual(reverse("about_technical"), "/about/technical/")
        self.assertEqual(reverse("about_biology"), "/about/biology/")
        self.assertEqual(reverse("collaborators"), "/collaborators/")
        self.assertEqual(reverse("license"), "/license/")
        self.assertEqual(reverse("signin"), "/signin/")
        self.assertEqual(reverse("account_settings"), "/account-settings/")
        self.assertEqual(reverse("workflow_defaults"), "/workflow-defaults/")
        self.assertEqual(reverse("experiment"), "/experiment/")
        self.assertEqual(
            reverse("experiment_workflow_defaults"),
            "/api/experiment/workflow-defaults/",
        )
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

    @override_settings(RECAPTCHA_ENABLED=False)
    def test_shared_footer_renders_on_public_pages_and_is_hidden_on_tool_pages(self):
        self.client.logout()

        public_responses = (
            self.client.get(reverse("home")),
            self.client.get(reverse("about")),
            self.client.get(reverse("about_technical")),
            self.client.get(reverse("about_biology")),
            self.client.get(reverse("collaborators")),
            self.client.get(reverse("license")),
            self.client.get(reverse("signin")),
            self.client.get(reverse("signup")),
        )
        for response in public_responses:
            self.assertEqual(response.status_code, 200)
            self._assert_footer_present(response)

        self.assertTrue(self.client.login(email=self.user.email, password="TestPass123!"))

        authenticated_responses = (
            self.client.get(reverse("experiment")),
            self.client.get(reverse("dashboard")),
            self.client.get(reverse("account_settings")),
            self.client.get(reverse("workflow_defaults")),
        )
        for response in authenticated_responses:
            self.assertEqual(response.status_code, 200)
            self._assert_footer_absent(response)

        preprocess_uuid = str(uuid4())
        display_uuid = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, preprocess_uuid)
            preprocess_upload = self._create_uploaded_image(preprocess_uuid, name="footer-preprocess")
            DVLayerTifPreview.objects.create(
                wavelength="DIC",
                uploaded_image_uuid=preprocess_upload,
                file_location=f"{preprocess_uuid}/preprocessed_images/footer-preprocess-image0.jpg",
            )

            self._write_channel_config(media_root, display_uuid)
            self._create_uploaded_image(display_uuid, name="footer-display")
            self._create_segmented_image(display_uuid, name="footer-display")

            preprocess_response = self.client.get(reverse("pre_process", args=[preprocess_uuid]))
            display_response = self.client.get(reverse("display", args=[display_uuid]))

        self.assertEqual(preprocess_response.status_code, 200)
        self.assertEqual(display_response.status_code, 200)
        self._assert_footer_absent(preprocess_response)
        self._assert_footer_absent(display_response)

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
        self.assertContains(home_response, reverse("about"))
        self.assertContains(home_response, reverse("collaborators"))
        self.assertContains(
            home_response,
            "Built by the UW Bothell School of STEM SEE Lab engineering team in collaboration with the University of Utah Miller Lab biology team.",
        )
        self.assertContains(
            home_response,
            "CytoCV: Automated Cell Image Analysis for Research Workflows",
        )
        self.assertContains(home_response, "University of Washington Bothell")
        self.assertContains(
            home_response,
            "Department of Computing &amp; Software Systems",
            html=True,
        )
        self.assertContains(
            home_response,
            "/static/assets/uwb/web-white-left-school-signature-uw-bothell.png",
            html=False,
        )
        self.assertContains(home_response, "CytoCV Team")
        self.assertContains(home_response, "About CytoCV")
        self.assertContains(home_response, "View CytoCV Team")
        self.assertContains(home_response, "See About page")
        self.assertContains(home_response, "From Upload to Export")
        self.assertContains(home_response, "Cell-Level Research Outputs")
        self.assertContains(home_response, "Built for DeltaVision Yeast Images")
        self.assertContains(home_response, "Review Segmentation and Export Data")
        self.assertContains(home_response, "Using CytoCV")
        self.assertContains(home_response, "View Workflow")
        self.assertContains(home_response, "View Measurements")
        self.assertContains(home_response, "View Image Inputs")
        self.assertContains(home_response, "View Results")
        self.assertContains(home_response, "View Documentation")
        self.assertContains(home_response, "Need the full product overview?")
        self.assertContains(home_response, "Want to see who built CytoCV?")
        self.assertContains(home_response, "Meet the CytoCV Team")
        self.assertContains(home_response, 'class="cta-support-links"', html=False)
        self.assertNotContains(home_response, 'class="cta-signin"', html=False)
        self.assertNotContains(home_response, "Already have an account?")
        self.assertContains(home_response, f"{reverse('about')}#workflow", html=False)
        self.assertContains(home_response, f"{reverse('about')}#measurements", html=False)
        self.assertContains(home_response, f"{reverse('about')}#image-inputs", html=False)
        self.assertContains(home_response, f"{reverse('about')}#results", html=False)
        self.assertContains(
            home_response,
            "https://github.com/BrentLagesse/CytoCV/tree/main/docs",
            html=False,
        )
        self.assertNotContains(home_response, "What CytoCV Is")
        self.assertNotContains(home_response, "Why Researchers Need It")
        self.assertNotContains(home_response, "How the Workflow Works")
        self.assertNotContains(home_response, "What CytoCV Measures")
        self.assertNotContains(home_response, "Why This Matters Biologically")
        self.assertNotContains(home_response, "Why trust this workflow")
        self.assertNotContains(home_response, "Methods, validation, and reproducibility are public.")
        self.assertNotContains(home_response, "/image/upload/")

    def test_home_about_collaborators_and_license_pages_are_public_surfaces(self):
        self.client.logout()

        home_response = self.client.get(reverse("home"))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(
            home_response,
            "CytoCV: Automated Cell Image Analysis for Research Workflows",
        )
        self.assertContains(
            home_response,
            "CytoCV helps researchers upload supported",
        )
        self.assertContains(
            home_response,
            "School of Science, Technology, Engineering &amp; Mathematics",
            html=True,
        )
        self.assertContains(home_response, reverse("about"))
        self.assertContains(home_response, reverse("about_technical"))
        self.assertContains(home_response, reverse("about_biology"))
        self.assertContains(home_response, reverse("collaborators"))
        self.assertContains(home_response, 'id="aboutNavMenu"', html=False)
        self.assertNotContains(home_response, '<a href="/about/">About</a>', html=False)
        self.assertNotContains(home_response, "Jump to section")
        self.assertNotContains(home_response, "Table of contents")
        self.assertContains(home_response, "From Upload to Export")
        self.assertContains(home_response, "Cell-Level Research Outputs")
        self.assertContains(home_response, "Built for DeltaVision Yeast Images")
        self.assertContains(home_response, "Review Segmentation and Export Data")
        self.assertContains(home_response, "Using CytoCV")
        self.assertContains(home_response, 'class="cta-signin"', html=False)
        self.assertContains(home_response, "Already have an account?")
        self.assertContains(home_response, "Need the full product overview?")
        self.assertContains(home_response, "Want to see who built CytoCV?")
        self.assertContains(home_response, "Meet the CytoCV Team")
        self.assertContains(home_response, 'class="cta-support-links"', html=False)
        self.assertNotContains(home_response, "DAPI, mCherry, and GFP image channels.")
        self.assertNotContains(home_response, "What CytoCV Is")
        self.assertNotContains(home_response, "Why Researchers Need It")
        self.assertNotContains(home_response, "How the Workflow Works")
        self.assertNotContains(home_response, "What CytoCV Measures")
        self.assertNotContains(home_response, "Why This Matters Biologically")
        self.assertNotContains(home_response, "Why trust this workflow")

        about_response = self.client.get(reverse("about"))
        self.assertEqual(about_response.status_code, 200)
        self.assertTemplateUsed(about_response, "about.html")
        self.assertContains(about_response, "About CytoCV")
        self.assertContains(about_response, "What CytoCV Is")
        self.assertContains(about_response, "Why Researchers Need It")
        self.assertContains(about_response, "How the Workflow Works")
        self.assertContains(about_response, "What CytoCV Measures")
        self.assertContains(about_response, "What Image Inputs CytoCV Expects")
        self.assertContains(about_response, "Review and Export Results")
        self.assertContains(about_response, "Why This Matters Biologically")
        self.assertContains(about_response, 'id="aboutNavMenu"', html=False)
        self.assertContains(about_response, 'data-about-current="about"', html=False)
        self.assertNotContains(about_response, "Current page")
        self.assertContains(about_response, "Table of contents")
        self.assertContains(about_response, 'id="pageSectionJump"', html=False)
        self.assertContains(about_response, reverse("about_technical"))
        self.assertContains(about_response, reverse("about_biology"))
        self.assertContains(about_response, 'href="#overview"', html=False)
        self.assertContains(about_response, 'href="#biological-value"', html=False)
        self.assertNotContains(about_response, 'role="tablist"', html=False)
        self.assertNotContains(about_response, 'data-about-tab="technical"', html=False)
        self.assertNotContains(about_response, 'data-about-tab="biological"', html=False)
        self.assertNotContains(about_response, "Upload, validation, and processing stages")
        self.assertNotContains(about_response, "Experimental context for the imaging workflow")
        self.assertNotContains(about_response, "Technical Details")
        self.assertNotContains(about_response, "Open the larger technical or biological pages")
        self.assertNotContains(about_response, "Technical Overview")
        self.assertNotContains(about_response, "Open Technical page")
        self.assertNotContains(about_response, "Open Biological page")
        self.assertContains(about_response, 'id="workflow"', html=False)
        self.assertContains(about_response, 'id="measurements"', html=False)
        self.assertContains(about_response, 'id="image-inputs"', html=False)
        self.assertContains(about_response, 'id="results"', html=False)
        self.assertNotContains(about_response, "Go deeper into the software and biology")

        technical_response = self.client.get(reverse("about_technical"))
        self.assertEqual(technical_response.status_code, 200)
        self.assertTemplateUsed(technical_response, "about_detail.html")
        self.assertContains(technical_response, 'id="aboutNavMenu"', html=False)
        self.assertContains(technical_response, 'data-about-current="technical"', html=False)
        self.assertContains(technical_response, "Table of contents")
        self.assertContains(technical_response, 'id="pageSectionJump"', html=False)
        self.assertContains(technical_response, "Technical Overview")
        self.assertNotContains(technical_response, "This technical overview describes")
        self.assertNotContains(technical_response, 'class="detail-actions"', html=False)
        self.assertNotContains(technical_response, "Documentation Links")
        self.assertNotContains(technical_response, "Related documentation")
        self.assertContains(technical_response, "Purpose, scope, and application boundaries")
        self.assertContains(technical_response, "High-level architecture and workflow ownership")
        self.assertContains(technical_response, "End-to-end workflow from upload to export")
        self.assertContains(technical_response, "Segmentation, measurement, and result assembly")
        self.assertContains(technical_response, "Runtime stack, dependencies, and practical limits")
        self.assertNotContains(technical_response, "Back to About")
        self.assertContains(technical_response, 'id="purpose-scope"', html=False)
        self.assertContains(technical_response, 'id="developer-docs"', html=False)
        self.assertContains(technical_response, 'id="research-pdfs"', html=False)
        self.assertContains(technical_response, 'href="#developer-docs"', html=False)
        self.assertContains(
            technical_response,
            "https://github.com/BrentLagesse/CytoCV/blob/main/docs/developer/architecture-overview.md",
            html=False,
        )
        self.assertContains(
            technical_response,
            "https://github.com/BrentLagesse/CytoCV/blob/main/docs/reference/data-model.md",
            html=False,
        )
        self.assertContains(
            technical_response,
            "https://github.com/BrentLagesse/CytoCV/blob/main/docs/research/pdfs/methods-and-system-description.pdf",
            html=False,
        )
        self.assertNotContains(technical_response, "docs/ops/deployment-guide.md", html=False)
        self.assertNotContains(technical_response, "docs/ops/environment-reference.md", html=False)
        self.assertNotContains(technical_response, "docs/vm-deployment-record/README.md", html=False)

        biology_response = self.client.get(reverse("about_biology"))
        self.assertEqual(biology_response.status_code, 200)
        self.assertTemplateUsed(biology_response, "about_detail.html")
        self.assertContains(biology_response, 'id="aboutNavMenu"', html=False)
        self.assertContains(biology_response, 'data-about-current="biological"', html=False)
        self.assertContains(biology_response, "Table of contents")
        self.assertContains(biology_response, 'id="pageSectionJump"', html=False)
        self.assertContains(biology_response, "Biological Context")
        self.assertNotContains(biology_response, "Back to About")
        self.assertNotContains(biology_response, 'class="detail-actions"', html=False)
        self.assertNotContains(biology_response, "This biology overview explains")
        self.assertNotContains(biology_response, "Documentation Links")
        self.assertNotContains(biology_response, "Related documentation")
        self.assertContains(biology_response, "Chromosome segregation in yeast")
        self.assertContains(biology_response, "Reference and experimental fluorophore comparisons")
        self.assertContains(biology_response, "Classifying CEN dots after anaphase")
        self.assertContains(biology_response, "Evaluating chromosome biorientation in metaphase")
        self.assertContains(biology_response, "Nuclear versus cytoplasmic protein localization")
        self.assertContains(biology_response, "Practical value and biological caution points")
        self.assertContains(biology_response, 'id="experimental-context"', html=False)
        self.assertContains(biology_response, 'id="biology-research-docs"', html=False)
        self.assertContains(biology_response, 'href="#biology-workflow-docs"', html=False)
        self.assertContains(
            biology_response,
            "https://github.com/BrentLagesse/CytoCV/blob/main/docs/research/pdfs/figure-catalog.pdf",
            html=False,
        )
        self.assertContains(
            biology_response,
            "https://github.com/BrentLagesse/CytoCV/blob/main/docs/user/output-guide.md",
            html=False,
        )
        self.assertNotContains(
            biology_response,
            "https://github.com/BrentLagesse/CytoCV/blob/main/docs/developer/architecture-overview.md",
            html=False,
        )

        collaborators_response = self.client.get(reverse("collaborators"))
        self.assertEqual(collaborators_response.status_code, 200)
        self.assertTemplateUsed(collaborators_response, "collaborators.html")
        self.assertContains(collaborators_response, "Project Team Members")
        self.assertContains(collaborators_response, "CytoCV Team")
        self.assertContains(
            collaborators_response,
            "CytoCV was built by the UW Bothell School of STEM SEE Lab engineering team in collaboration with the University of Utah Miller Lab biology team.",
        )
        self.assertContains(
            collaborators_response,
            "UW Bothell School of STEM, SEE Lab Engineering Team",
        )
        self.assertContains(
            collaborators_response,
            "University of Utah Spencer Fox Eccles School of Medicine, Miller Lab Biology Team",
        )
        self.assertContains(collaborators_response, "Engineering Team")
        self.assertContains(collaborators_response, "Biology collaborators")
        self.assertContains(collaborators_response, "Nicolas Gioanni")
        self.assertContains(collaborators_response, "Anoop Prasad")
        self.assertContains(collaborators_response, "Emily Parnell")
        self.assertContains(collaborators_response, "Brent Lagesse")
        self.assertContains(collaborators_response, "Matthew P. Miller")
        self.assertContains(
            collaborators_response,
            "Led the development of CytoCV",
        )
        self.assertContains(
            collaborators_response,
            "architecture, implementation, deployment",
        )
        self.assertContains(
            collaborators_response,
            "requirements translation, and ongoing maintenance",
        )
        self.assertContains(collaborators_response, "ngioanni@uw.edu")
        self.assertContains(collaborators_response, "anoopp@uw.edu")
        self.assertContains(collaborators_response, "emily.parnell@biochem.utah.edu")
        self.assertContains(collaborators_response, "lagesse@uw.edu")
        self.assertContains(collaborators_response, "matt.miller@biochem.utah.edu")
        self.assertContains(collaborators_response, "mailto:ngioanni@uw.edu", html=False)
        self.assertContains(collaborators_response, "mailto:anoopp@uw.edu", html=False)
        self.assertContains(collaborators_response, "mailto:emily.parnell@biochem.utah.edu", html=False)
        self.assertContains(collaborators_response, "mailto:lagesse@uw.edu", html=False)
        self.assertContains(collaborators_response, "mailto:matt.miller@biochem.utah.edu", html=False)
        self.assertContains(
            collaborators_response,
            "https://faculty.washington.edu/lagesse/",
            html=False,
        )
        self.assertContains(
            collaborators_response,
            "https://medicine.utah.edu/faculty/matthew-p-miller",
            html=False,
        )
        self.assertContains(
            collaborators_response,
            "https://www.linkedin.com/in/brent-lagesse-1a117960/",
            html=False,
        )
        self.assertContains(
            collaborators_response,
            "https://github.com/BrentLagesse",
            html=False,
        )
        self.assertContains(
            collaborators_response,
            "https://www.linkedin.com/in/nicolas-gioanni",
            html=False,
        )
        self.assertContains(
            collaborators_response,
            "https://github.com/nicolasgioanni",
            html=False,
        )
        self.assertContains(
            collaborators_response,
            "https://nicolasmgioanni.dev",
            html=False,
        )
        self.assertContains(
            collaborators_response,
            "https://www.linkedin.com/in/anoop-prasad-uwb",
            html=False,
        )
        self.assertContains(
            collaborators_response,
            "https://github.com/AnoopP7",
            html=False,
        )
        self.assertContains(
            collaborators_response,
            "https://miller.biochem.utah.edu/members",
            html=False,
        )
        self.assertNotContains(collaborators_response, "Contributors")
        self.assertNotContains(collaborators_response, "Supervising Professors")
        self.assertNotContains(collaborators_response, "Acknowledgement")
        self.assertNotContains(collaborators_response, "Methods, validation, reproducibility, and affiliation")
        self.assertNotContains(collaborators_response, "Methods and system description")
        self.assertNotContains(collaborators_response, "Validation-aware workflow rules")
        self.assertNotContains(collaborators_response, "/static/research/methods-and-system-description.pdf")
        self.assertNotContains(collaborators_response, "/static/research/reproducibility-and-validation.pdf")
        self.assertNotContains(collaborators_response, "Jump to section")
        self.assertNotContains(collaborators_response, "Table of contents")

        research_response = self.client.get("/research/")
        self.assertEqual(research_response.status_code, 404)

        license_response = self.client.get(reverse("license"))
        self.assertEqual(license_response.status_code, 200)
        self.assertTemplateUsed(license_response, "license.html")
        self.assertContains(license_response, "CytoCV License")
        self.assertContains(
            license_response,
            "Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License",
        )
        self.assertContains(
            license_response,
            "CytoCV is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License (CC BY-NC-SA 4.0).",
        )
        self.assertContains(license_response, "CC BY-NC-SA 4.0")
        self.assertContains(
            license_response,
            "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            html=False,
        )
        self.assertContains(
            license_response,
            "https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.en",
            html=False,
        )
        self.assertContains(license_response, "View official license")
        self.assertContains(license_response, 'id="licenseBackLink"', html=False)
        self.assertNotContains(license_response, "This page summarizes the")

    @override_settings(RECAPTCHA_ENABLED=False)
    def test_auth_public_pages_use_user_facing_copy(self):
        self.client.logout()

        signin_response = self.client.get(reverse("signin"))
        self.assertEqual(signin_response.status_code, 200)
        self.assertContains(signin_response, "Sign in to access your dashboard and saved experiments.")
        self.assertContains(
            signin_response,
            "Use Google or Microsoft instead of entering your email and password.",
        )
        self.assertNotContains(
            signin_response,
            "Use a connected provider instead of entering credentials directly.",
        )

        signup_response = self.client.get(reverse("signup"))
        self.assertEqual(signup_response.status_code, 200)
        self.assertContains(signup_response, "Used for your CytoCV profile.")
        self.assertContains(
            signup_response,
            "Already have an account? <a href=\"/signin/\">Sign In</a>",
            html=True,
        )
        self.assertNotContains(signup_response, "This helps personalize your account.")

    def test_surfaced_json_errors_use_safe_user_facing_copy(self):
        invalid_json_response = self.client.post(
            reverse("dashboard_bulk_delete"),
            data="{",
            content_type="application/json",
        )
        self.assertEqual(invalid_json_response.status_code, 400)
        self.assertJSONEqual(
            invalid_json_response.content.decode("utf-8"),
            {"error": "Your request could not be processed. Please try again."},
        )

        display_sync_response = self.client.post(
            reverse("display_sync_file_selection"),
            data="{",
            content_type="application/json",
        )
        self.assertEqual(display_sync_response.status_code, 400)
        self.assertJSONEqual(
            display_sync_response.content.decode("utf-8"),
            {"error": "Your request could not be processed. Please try again."},
        )

        update_channel_response = self.client.post(
            reverse("update_channel_order", args=[str(uuid4())]),
            data=json.dumps({"order": ["DIC", "channel_blue", "channel_red", "channel_green"]}),
            content_type="application/json",
        )
        self.assertEqual(update_channel_response.status_code, 404)
        self.assertJSONEqual(
            update_channel_response.content.decode("utf-8"),
            {"error": "Channel information for this file could not be loaded."},
        )

    def test_update_channel_order_accepts_display_labels(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value)
            response = self.client.post(
                reverse("update_channel_order", args=[uuid_value]),
                data=json.dumps({"order": ["Red", "Blue", "Green", "DIC"]}),
                content_type="application/json",
            )
            payload = json.loads((media_root / uuid_value / "channel_config.json").read_text())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            payload,
            {
                "channel_red": 0,
                "channel_blue": 1,
                "channel_green": 2,
                "DIC": 3,
            },
        )

    def test_update_channel_order_accepts_canonical_keys(self):
        uuid_value = str(uuid4())
        order = ["channel_red", "channel_blue", "channel_green", "DIC"]
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value)
            response = self.client.post(
                reverse("update_channel_order", args=[uuid_value]),
                data=json.dumps({"order": order}),
                content_type="application/json",
            )
            payload = json.loads((media_root / uuid_value / "channel_config.json").read_text())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload, {channel: index for index, channel in enumerate(order)})

    def test_update_channel_order_rejects_duplicate_display_labels(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value)
            response = self.client.post(
                reverse("update_channel_order", args=[uuid_value]),
                data=json.dumps({"order": ["Red", "Red", "Green", "DIC"]}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content.decode("utf-8"),
            {"error": "Invalid channel order."},
        )

    def test_update_channel_order_rejects_unowned_file(self):
        user_model = get_user_model()
        other_user = user_model.objects.create_user(
            email="other-channel-owner@example.com",
            password="TestPass123!",
        )
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            UploadedImage.objects.create(
                user=other_user,
                uuid=uuid_value,
                name="other",
                file_location=f"{uuid_value}/other.dv",
            )
            response = self.client.post(
                reverse("update_channel_order", args=[uuid_value]),
                data=json.dumps({"order": ["Red", "Blue", "Green", "DIC"]}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 404)
        self.assertJSONEqual(
            response.content.decode("utf-8"),
            {"error": "Channel information for this file could not be loaded."},
        )

    def test_pre_process_refreshes_default_tiff_channel_config_from_metadata(self):
        uuid_value = str(uuid4())
        image_name = "metadata_channels"
        with temporary_media_root() as media_root:
            source_path = media_root / uuid_value / f"{image_name}.tif"
            self._write_labeled_tiff(source_path)
            self._write_channel_config(media_root, uuid_value)
            UploadedImage.objects.create(
                user=self.user,
                uuid=uuid_value,
                name=image_name,
                file_location=f"{uuid_value}/{image_name}.tif",
            )

            response = self.client.get(reverse("pre_process", args=[uuid_value]))
            payload = json.loads((media_root / uuid_value / "channel_config.json").read_text())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            payload,
            {
                "channel_red": 0,
                "channel_blue": 1,
                "channel_green": 2,
                "DIC": 3,
            },
        )

    def test_pre_process_preserves_user_edited_tiff_channel_config(self):
        uuid_value = str(uuid4())
        image_name = "user_channels"
        user_config = {
            "channel_blue": 0,
            "DIC": 1,
            "channel_green": 2,
            "channel_red": 3,
        }
        with temporary_media_root() as media_root:
            source_path = media_root / uuid_value / f"{image_name}.tif"
            self._write_labeled_tiff(source_path)
            config_path = media_root / uuid_value / "channel_config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(user_config), encoding="utf-8")
            UploadedImage.objects.create(
                user=self.user,
                uuid=uuid_value,
                name=image_name,
                file_location=f"{uuid_value}/{image_name}.tif",
            )

            response = self.client.get(reverse("pre_process", args=[uuid_value]))
            payload = json.loads(config_path.read_text())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload, user_config)

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
        self.assertContains(response, "js/pages/display-viewer.js", html=False)
        display_source = _frontend_static_text("js/pages/display-viewer.js")
        shared_viewer_source = _frontend_static_text("js/shared/results-viewer.js")
        self.assertIn("/experiment/${fileUUID}/main-channel/", shared_viewer_source)
        self.assertIn("/experiment/display/files/sync-selection/", display_source)
        self._assert_removed_paths(response)

    def test_display_payload_includes_main_image_paths_for_all_channels(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="display-main-paths")
            self._create_segmented_image(uuid_value, name="display-main-paths")
            self._write_output_frame_assets(media_root, uuid_value, "display-main-paths")

            response = self.client.get(reverse("display", args=[uuid_value]))

        self.assertEqual(response.status_code, 200)
        files_data = json.loads(response.context["files_data"])
        payload = files_data[uuid_value]
        self._assert_files_data_payload_contract(payload)
        self.assertEqual(
            set(payload["MainImagePaths"].keys()),
            {"dic", "blue", "red", "green"},
        )
        self.assertEqual(
            payload["MainImagePaths"]["dic"],
            f"/media/{uuid_value}/output/display-main-paths_frame_0.png",
        )
        self.assertEqual(
            payload["MainImagePaths"]["blue"],
            f"/media/{uuid_value}/output/display-main-paths_frame_1.png",
        )
        self.assertEqual(
            payload["MainImagePaths"]["green"],
            f"/media/{uuid_value}/output/display-main-paths_frame_2.png",
        )
        self.assertEqual(
            payload["MainImagePaths"]["red"],
            f"/media/{uuid_value}/output/display-main-paths_frame_3.png",
        )

    def test_dashboard_payload_includes_main_image_paths_for_all_channels(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="dashboard-main-paths")
            segmented = self._create_segmented_image(uuid_value, name="dashboard-main-paths")
            segmented.user = self.user
            segmented.save(update_fields=["user"])
            self._write_output_frame_assets(media_root, uuid_value, "dashboard-main-paths")

            response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        files_data = json.loads(response.context["files_data_json"])
        payload = files_data[uuid_value]
        self._assert_files_data_payload_contract(payload)
        self.assertEqual(
            set(payload["MainImagePaths"].keys()),
            {"dic", "blue", "red", "green"},
        )
        self.assertEqual(
            payload["MainImagePaths"]["red"],
            f"/media/{uuid_value}/output/dashboard-main-paths_frame_3.png",
        )

    def test_viewers_use_payload_backed_main_image_warmup(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="viewer-main-warmup")
            segmented = self._create_segmented_image(uuid_value, name="viewer-main-warmup")
            segmented.user = self.user
            segmented.save(update_fields=["user"])

            display_response = self.client.get(reverse("display", args=[uuid_value]))
            dashboard_response = self.client.get(reverse("dashboard"))

        self.assertContains(display_response, "js/pages/display-viewer.js", html=False)
        display_source = _frontend_static_text("js/pages/display-viewer.js")
        self.assertIn(
            "scheduleMainImageWarmup(fileUUID, fileData, activeMainChannel || inferredDefaultChannel);",
            display_source,
        )
        self.assertIn(
            "const imageUrl = await warmMainImageChannel(fileUUID, fileData, normalizedChannel);",
            display_source,
        )
        shared_viewer_source = _frontend_static_text("js/shared/results-viewer.js")
        self.assertIn("fileData.MainImagePaths = {};", shared_viewer_source)
        self.assertContains(dashboard_response, "js/pages/dashboard-viewer.js", html=False)
        dashboard_source = _frontend_static_text("js/pages/dashboard-viewer.js")
        self.assertIn(
            "scheduleMainImageWarmup(fileUUID, fileData, activeMainChannel || inferredDefaultChannel);",
            dashboard_source,
        )
        self.assertIn(
            "const imageUrl = await warmMainImageChannel(fileUUID, fileData, normalizedChannel);",
            dashboard_source,
        )

    def test_main_image_channel_matches_display_and_dashboard_payload_paths(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="main-channel-match")
            segmented = self._create_segmented_image(uuid_value, name="main-channel-match")
            segmented.user = self.user
            segmented.save(update_fields=["user"])
            self._write_output_frame_assets(media_root, uuid_value, "main-channel-match")

            display_response = self.client.get(reverse("display", args=[uuid_value]))
            dashboard_response = self.client.get(reverse("dashboard"))

            display_payload = json.loads(display_response.context["files_data"])[uuid_value]
            dashboard_payload = json.loads(dashboard_response.context["files_data_json"])[uuid_value]

            for channel in ("dic", "blue", "red", "green"):
                response = self.client.get(
                    reverse("main_image_channel", args=[uuid_value]),
                    {"channel": channel},
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["image_url"], display_payload["MainImagePaths"][channel])
                self.assertEqual(payload["image_url"], dashboard_payload["MainImagePaths"][channel])

    def test_main_image_channel_and_payload_fall_back_to_first_available_frame(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="main-channel-fallback")
            self._create_segmented_image(uuid_value, name="main-channel-fallback")
            self._write_output_frame_assets(
                media_root,
                uuid_value,
                "main-channel-fallback",
                frame_indices=(0,),
            )

            display_response = self.client.get(reverse("display", args=[uuid_value]))
            display_payload = json.loads(display_response.context["files_data"])[uuid_value]

            response = self.client.get(
                reverse("main_image_channel", args=[uuid_value]),
                {"channel": "green"},
            )

        self.assertEqual(response.status_code, 200)
        expected_url = f"/media/{uuid_value}/output/main-channel-fallback_frame_0.png"
        self.assertEqual(display_payload["MainImagePaths"]["green"], expected_url)
        self.assertEqual(response.json()["image_url"], expected_url)

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

    def test_display_uses_cached_overlay_endpoint_without_render_config(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="display-cached-overlay")
            segmented = self._create_segmented_image(
                uuid_value,
                name="display-cached-overlay",
            )
            segmented.NumCells = 1
            segmented.save(update_fields=["NumCells"])
            self._write_segmented_cell_assets(
                media_root,
                uuid_value,
                "display-cached-overlay",
            )
            self._create_cell_stats(segmented, "display-cached-overlay")
            self._write_overlay_cache_image(
                uuid_value,
                1,
                "green",
                color=(30, 220, 30),
            )

            response = self.client.get(reverse("display", args=[uuid_value]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "green"]),
            html=False,
        )
        self.assertContains(
            response,
            f"/media/{uuid_value}/segmented/display-cached-overlay-{DEFAULT_CHANNEL_CONFIG['channel_red']}-1.png",
            html=False,
        )
        self.assertContains(
            response,
            f"/media/{uuid_value}/segmented/display-cached-overlay-{DEFAULT_CHANNEL_CONFIG['channel_blue']}-1.png",
            html=False,
        )
        self.assertNotContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "red"]),
            html=False,
        )
        self.assertNotContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "blue"]),
            html=False,
        )

    def test_dashboard_uses_cached_overlay_endpoint_without_render_config(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="dashboard-cached-overlay")
            segmented = self._create_segmented_image(
                uuid_value,
                name="dashboard-cached-overlay",
            )
            segmented.user = self.user
            segmented.NumCells = 1
            segmented.save(update_fields=["user", "NumCells"])
            self._write_segmented_cell_assets(
                media_root,
                uuid_value,
                "dashboard-cached-overlay",
            )
            self._create_cell_stats(segmented, "dashboard-cached-overlay")
            self._write_overlay_cache_image(
                uuid_value,
                1,
                "green",
                color=(30, 220, 30),
            )

            response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "green"]),
            html=False,
        )
        self.assertNotContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "red"]),
            html=False,
        )
        self.assertNotContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "blue"]),
            html=False,
        )

    def test_dashboard_uses_historical_cached_overlay_endpoint_for_old_schema(self):
        uuid_value = str(uuid4())
        expected_path: Path | None = None
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="dashboard-old-overlay")
            segmented = self._create_segmented_image(
                uuid_value,
                name="dashboard-old-overlay",
            )
            segmented.user = self.user
            segmented.NumCells = 1
            segmented.save(update_fields=["user", "NumCells"])
            self._write_segmented_cell_assets(
                media_root,
                uuid_value,
                "dashboard-old-overlay",
            )
            self._create_cell_stats(segmented, "dashboard-old-overlay")
            render_config = self._write_overlay_config(uuid_value, "dashboard-old-overlay")
            render_config["schema_version"] = 3
            write_overlay_render_config(uuid_value, render_config)
            expected_path = self._write_historical_overlay_cache_image(
                media_root,
                uuid_value,
                1,
                "green",
                color=(12, 180, 45),
            )

            response = self.client.get(reverse("dashboard"))
            overlay_response = self.client.get(
                reverse("cell_overlay_image", args=[uuid_value, 1, "green"])
            )
            self.assertEqual(overlay_response.status_code, 200)
            payload = b"".join(overlay_response.streaming_content)
            rendered = np.array(Image.open(BytesIO(payload)))
            with Image.open(expected_path) as expected_image:
                expected = np.array(expected_image)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "green"]),
            html=False,
        )
        self.assertNotContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "red"]),
            html=False,
        )
        self.assertNotContains(
            response,
            reverse("cell_overlay_image", args=[uuid_value, 1, "blue"]),
            html=False,
        )
        self.assertTrue(np.array_equal(rendered, expected))

    def test_dashboard_uses_static_images_for_old_schema_without_historical_cache(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="dashboard-old-static")
            segmented = self._create_segmented_image(
                uuid_value,
                name="dashboard-old-static",
            )
            segmented.user = self.user
            segmented.NumCells = 1
            segmented.save(update_fields=["user", "NumCells"])
            self._write_segmented_cell_assets(
                media_root,
                uuid_value,
                "dashboard-old-static",
            )
            self._create_cell_stats(segmented, "dashboard-old-static")
            render_config = self._write_overlay_config(uuid_value, "dashboard-old-static")
            render_config["schema_version"] = 3
            write_overlay_render_config(uuid_value, render_config)

            response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        for channel in ("green", "red", "blue"):
            self.assertNotContains(
                response,
                reverse("cell_overlay_image", args=[uuid_value, 1, channel]),
                html=False,
            )
        self.assertContains(
            response,
            f"/media/{uuid_value}/segmented/dashboard-old-static-{DEFAULT_CHANNEL_CONFIG['channel_green']}-1.png",
            html=False,
        )

    def test_overlay_endpoint_serves_cached_channel_without_render_config(self):
        uuid_value = str(uuid4())
        expected_path: Path | None = None
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="overlay-cache-only")
            segmented = self._create_segmented_image(uuid_value, name="overlay-cache-only")
            segmented.NumCells = 1
            segmented.save(update_fields=["NumCells"])
            self._write_segmented_cell_assets(media_root, uuid_value, "overlay-cache-only")
            self._create_cell_stats(segmented, "overlay-cache-only")
            expected_path = self._write_overlay_cache_image(
                uuid_value,
                1,
                "green",
                color=(10, 180, 10),
            )

            response = self.client.get(
                reverse("cell_overlay_image", args=[uuid_value, 1, "green"])
            )
            self.assertEqual(response.status_code, 200)
            payload = b"".join(response.streaming_content)

            with Image.open(expected_path) as expected_image:
                expected = np.array(expected_image)

        rendered = np.array(Image.open(BytesIO(payload)))
        self.assertTrue(np.array_equal(rendered, expected))

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

    def test_overlay_endpoint_ignores_neck_split_sidecar_for_fluorescence_channels(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="overlay-neck")
            segmented = self._create_segmented_image(uuid_value, name="overlay-neck")
            segmented.NumCells = 1
            segmented.save(update_fields=["NumCells"])
            self._write_segmented_cell_assets(media_root, uuid_value, "overlay-neck")
            self._create_cell_stats(segmented, "overlay-neck")
            self._write_overlay_config(uuid_value, "overlay-neck")
            self._write_neck_split_sidecar(media_root, uuid_value, "overlay-neck")

            response = self.client.get(
                reverse("cell_overlay_image", args=[uuid_value, 1, "green"])
            )
            payload = b"".join(response.streaming_content)
            response.close()

        self.assertEqual(response.status_code, 200)
        rendered = np.array(Image.open(BytesIO(payload)))
        cyan_like = (
            (rendered[:, :, 0] < 100)
            & (rendered[:, :, 1] > 150)
            & (rendered[:, :, 2] > 150)
        )
        self.assertEqual(int(np.count_nonzero(cyan_like)), 0)

    def test_overlay_cache_path_uses_schema_v4_directory(self):
        uuid_value = str(uuid4())
        cache_path = overlay_cache_image_path(uuid_value, 1, "green")
        self.assertIn("overlay-cache-v4", str(cache_path))

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
        self.assertContains(response, "js/pages/dashboard-viewer.js", html=False)
        source = _frontend_static_text("js/pages/dashboard-viewer.js")
        shared_source = _frontend_static_text("js/shared/results-viewer.js")
        for expected in (
            "if (Number.isInteger(value)) {",
            "return value.toFixed(3);",
            "return 'N/A';",
            "return tableFieldOrder.slice();",
            "document.querySelectorAll('[data-cell-card-section]')",
            "section.hidden = sectionName && Object.prototype.hasOwnProperty.call(sections, sectionName)",
            "function buildCellCardMetricValues(cellStats",
            "punctaLineIntensity: formatStatValue(cellStats ? cellStats.puncta_line_intensity : null),",
            "nucleusIntensitySum: (!cellStats || nuclearUnavailable) ? 'N/A' : formatStatValue(cellStats.nucleus_intensity_sum),",
            "colinearDots: formatStatValue(cellStats ? cellStats.colinear_dots : null),",
            "getContourIntensityDisplayFields(displayType).forEach((field) => {",
            "metricValues[field.metricId] = formatStatValue(cellStats ? cellStats[field.fieldName] : null);",
            "function getSortedCellIds(fileData)",
            "function getWarmPriorityOffsets(direction = 'initial')",
            "function buildFullCircularCellOrder(sortedIds, activeCellNumber, totalCells)",
            "return [1, -1, 2, -2];",
            "return [1, 2, -1, -2];",
            "return [-1, -2, 1, 2];",
            "buildFullCircularCellOrder(sortedIds, currentCellNumber, maxCells)",
        ):
            self.assertIn(expected, shared_source)
        for expected in (
            "buildCellCardMetricValues(cellStats, {",
            "contourIntensityType: currentContourIntensityDisplayType",
            "const getSortedCellIds = resultsViewerShared.getSortedCellIds;",
            "return resultsViewerShared.getCircularWarmQueue({",
        ):
            self.assertIn(expected, source)
        self.assertNotIn("redInRedIntensity1: formatStatValue(cellStats ? cellStats.red_in_red_total_intensity_1 : null),", source)
        self.assertNotIn("greenInGreenIntensity1: formatStatValue(cellStats ? cellStats.green_in_green_total_intensity_1 : null),", source)
        self.assertNotIn("function getWarmPriorityOffsets", source)
        self.assertNotIn("function buildFullCircularCellOrder", source)
        self.assertNotIn("section.hidden = visibility[key] === false;", shared_source)

    def test_display_cell_pair_cards_use_stat_formatter_for_numeric_metrics(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="display-stats")
            self._create_segmented_image(uuid_value, name="display-stats")

            response = self.client.get(reverse("display", args=[uuid_value]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/pages/display-viewer.js", html=False)
        source = _frontend_static_text("js/pages/display-viewer.js")
        shared_source = _frontend_static_text("js/shared/results-viewer.js")
        for expected in (
            "return tableFieldOrder.slice();",
            "document.querySelectorAll('[data-cell-card-section]')",
            "section.hidden = sectionName && Object.prototype.hasOwnProperty.call(sections, sectionName)",
            "function buildCellCardMetricValues(cellStats",
            "punctaLineIntensity: formatStatValue(cellStats ? cellStats.puncta_line_intensity : null),",
            "nucleusIntensitySum: (!cellStats || nuclearUnavailable) ? 'N/A' : formatStatValue(cellStats.nucleus_intensity_sum),",
            "colinearDots: formatStatValue(cellStats ? cellStats.colinear_dots : null),",
            "getContourIntensityDisplayFields(displayType).forEach((field) => {",
            "metricValues[field.metricId] = formatStatValue(cellStats ? cellStats[field.fieldName] : null);",
            "function getSortedCellIds(fileData)",
            "function getWarmPriorityOffsets(direction = 'initial')",
            "function buildFullCircularCellOrder(sortedIds, activeCellNumber, totalCells)",
            "return [1, -1, 2, -2];",
            "return [1, 2, -1, -2];",
            "return [-1, -2, 1, 2];",
            "buildFullCircularCellOrder(sortedIds, currentCellNumber, maxCells)",
        ):
            self.assertIn(expected, shared_source)
        for expected in (
            "buildCellCardMetricValues(cellStats, {",
            "contourIntensityType: currentContourIntensityDisplayType",
            "const getSortedCellIds = resultsViewerShared.getSortedCellIds;",
            "return resultsViewerShared.getCircularWarmQueue({",
        ):
            self.assertIn(expected, source)
        self.assertNotIn("redInRedIntensity1: formatStatValue(cellStats ? cellStats.red_in_red_total_intensity_1 : null),", source)
        self.assertNotIn("redInGreenIntensity1: formatStatValue(cellStats ? cellStats.red_in_green_total_intensity_1 : null),", source)
        self.assertNotIn("function getWarmPriorityOffsets", source)
        self.assertNotIn("function buildFullCircularCellOrder", source)
        self.assertNotIn("section.hidden = visibility[key] === false;", shared_source)

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
                red_in_red_total_intensity_1=11.0,
                green_in_red_total_intensity_1=7.0,
                red_in_green_total_intensity_1=5.0,
                green_in_green_total_intensity_1=13.0,
                green_red_intensity_1=99.0,
                properties={
                    "nuclear_cell_pair_mode": "red_nucleus",
                    "puncta_line_mode": "green_puncta",
                    "cen_dot_schema_version": 3,
                    "cell_parentage": {
                        "status": "identified",
                        "mode": "conservative",
                        "method": "neck_split",
                        "label": "Mother/Daughter identified",
                        "reason": "ok",
                    },
                },
                category_cen_dot=1,
            )

            response = self.client.get(reverse("display", args=[uuid_value]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Red In Red Total Intensity")
        self.assertContains(response, "Green In Red Total Intensity")
        self.assertContains(response, "Red In Green Total Intensity")
        self.assertContains(response, "Green In Green Total Intensity")
        self.assertContains(response, "Measurement/Contour Ratio 1")
        self.assertContains(response, "Measurement/Contour")
        self.assertContains(response, "Formula")
        self.assertContains(response, "Measurement/Contour Ratio 1 (Green/Red)")
        self.assertContains(response, "Measurement/Contour Ratio 2 (Green/Red)")
        self.assertContains(response, "Measurement/Contour Ratio 3 (Green/Red)")
        self.assertContains(response, "Green/Red: Green In Red / Red In Red")
        self.assertContains(response, "CEN Dot Measurements")
        self.assertContains(response, "Distance Between Green Puncta")
        self.assertContains(response, "Red Intensity Over Green Line")
        self.assertContains(response, "Contour Intensities")
        self.assertContains(response, 'data-contour-intensity-display="total"', html=False)
        self.assertContains(response, 'data-contour-intensity-display="max"', html=False)
        self.assertContains(response, 'data-contour-intensity-display="average"', html=False)
        self.assertNotContains(response, "Intensity + Green Output")
        self.assertContains(response, '"red_in_red_total_intensity_1": 11.0', html=False)
        self.assertContains(response, '"red_in_green_total_intensity_1": 5.0', html=False)
        self.assertContains(response, '"green_in_green_total_intensity_1": 13.0', html=False)
        self.assertContains(response, '"measurement_contour_ratio_1": 0.6363636363636364', html=False)
        self.assertContains(response, '"measurement_contour_ratio_formula": "Green In Red / Red In Red"', html=False)
        self.assertContains(response, '"puncta_distance_label": "Distance Between Green Puncta"', html=False)
        self.assertContains(
            response,
            '"category_cen_dot_label": "Mother and daughter"',
            html=False,
        )
        self.assertContains(
            response,
            '"cell_parentage_label": "Mother/Daughter identified"',
            html=False,
        )
        display_source = _frontend_static_text("js/pages/display-viewer.js")
        shared_source = _frontend_static_text("js/shared/results-viewer.js")
        self.assertIn("buildCellCardMetricValues", display_source)
        self.assertIn("cellStats.cell_parentage_label || 'Not identified'", shared_source)
        self.assertContains(response, "Cell Parentage")
        self.assertIn("cellStats.category_cen_dot_label || 'N/A'", shared_source)
        self.assertNotIn("const categories = ['One green dot with each red dot'", display_source)
        self.assertNotContains(response, "Green/Red Ratio 1 (Compatibility)")
        self.assertNotIn("Green/Red Ratio 1 (Compatibility)", shared_source)

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
                red_in_red_total_intensity_1=19.0,
                green_in_red_total_intensity_1=23.0,
                red_in_green_total_intensity_1=29.0,
                green_in_green_total_intensity_1=31.0,
                green_red_intensity_1=99.0,
                properties={
                    "nuclear_cell_pair_mode": "green_nucleus",
                    "puncta_line_mode": "green_puncta",
                    "cen_dot_schema_version": 3,
                    "cell_parentage": {
                        "status": "identified",
                        "mode": "conservative",
                        "method": "neck_split",
                        "label": "Mother/Daughter identified",
                        "reason": "ok",
                    },
                },
                category_cen_dot=1,
            )

            response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Red In Red Total Intensity")
        self.assertContains(response, "Green In Red Total Intensity")
        self.assertContains(response, "Red In Green Total Intensity")
        self.assertContains(response, "Green In Green Total Intensity")
        self.assertContains(response, "Measurement/Contour Ratio 1")
        self.assertContains(response, "Measurement/Contour")
        self.assertContains(response, "Formula")
        self.assertContains(response, "Measurement/Contour Ratio 1 (Red/Green)")
        self.assertContains(response, "Measurement/Contour Ratio 2 (Red/Green)")
        self.assertContains(response, "Measurement/Contour Ratio 3 (Red/Green)")
        self.assertContains(response, "Red/Green: Red In Green / Green In Green")
        self.assertContains(response, "CEN Dot Measurements")
        self.assertContains(response, "Distance Between Green Puncta")
        self.assertContains(response, "Red Intensity Over Green Line")
        self.assertContains(response, "Contour Intensities")
        self.assertContains(response, 'data-contour-intensity-display="total"', html=False)
        self.assertContains(response, 'data-contour-intensity-display="max"', html=False)
        self.assertContains(response, 'data-contour-intensity-display="average"', html=False)
        self.assertNotContains(response, "Intensity + Green Output")
        self.assertContains(response, '"red_in_red_total_intensity_1": 19.0', html=False)
        self.assertContains(response, '"green_in_red_total_intensity_1": 23.0', html=False)
        self.assertContains(response, '"green_in_green_total_intensity_1": 31.0', html=False)
        self.assertContains(response, '"measurement_contour_ratio_formula": "Red In Green / Green In Green"', html=False)
        self.assertContains(response, '"puncta_distance_label": "Distance Between Green Puncta"', html=False)
        self.assertContains(
            response,
            '"category_cen_dot_label": "Mother and daughter"',
            html=False,
        )
        self.assertContains(
            response,
            '"cell_parentage_label": "Mother/Daughter identified"',
            html=False,
        )
        dashboard_source = _frontend_static_text("js/pages/dashboard-viewer.js")
        shared_source = _frontend_static_text("js/shared/results-viewer.js")
        self.assertIn("buildCellCardMetricValues", dashboard_source)
        self.assertIn("cellStats.cell_parentage_label || 'Not identified'", shared_source)
        self.assertContains(response, "Cell Parentage")
        self.assertIn("cellStats.category_cen_dot_label || 'N/A'", shared_source)
        self.assertNotIn("const categories = ['One green dot with each red dot'", dashboard_source)
        self.assertNotContains(response, "Green/Red Ratio 1 (Compatibility)")
        self.assertNotIn("Green/Red Ratio 1 (Compatibility)", shared_source)

    def test_display_payload_marks_uncomputed_stats_na_for_nuclear_only(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="display-nuclear-only")
            segmented = self._create_segmented_image(uuid_value, name="display-nuclear-only")
            segmented.NumCells = 1
            segmented.save(update_fields=["NumCells"])
            self._write_segmented_cell_assets(media_root, uuid_value, "display-nuclear-only")
            self._create_cell_stats(
                segmented,
                "display-nuclear-only",
                puncta_distance=10.0,
                puncta_line_intensity=20.0,
                red_in_red_total_intensity_1=5.0,
                green_in_red_total_intensity_1=6.0,
                red_in_green_total_intensity_1=7.0,
                green_in_green_total_intensity_1=8.0,
                nucleus_intensity_sum=30.0,
                cell_pair_intensity_sum=40.0,
                cytoplasmic_intensity=10.0,
                nuclear_cytoplasmic_ratio=3.0,
                colinear_dots=0,
                off_axis_dots=0,
                properties={
                    "selected_analysis": ["NuclearCellPairIntensity"],
                    "nuclear_cell_pair_mode": "green_nucleus",
                    "nuclear_cell_pair_status": "ok",
                    "nuclear_cell_pair_contour_source": "canonical_slot_1",
                    "cen_dot_schema_version": 3,
                },
                category_cen_dot=1,
            )

            response = self.client.get(reverse("display", args=[uuid_value]))

        self.assertEqual(response.status_code, 200)
        files_data = json.loads(response.context["files_data"])
        payload = files_data[uuid_value]["Statistics"]["1"]
        self.assertIsNone(payload["puncta_distance"])
        self.assertIsNone(payload["puncta_line_intensity"])
        self.assertIsNone(payload["red_in_red_total_intensity_1"])
        self.assertIsNone(payload["measurement_contour_ratio_1"])
        self.assertEqual(payload["measurement_contour_ratio_display_text"], "N/A")
        self.assertIsNone(payload["category_cen_dot"])
        self.assertEqual(payload["category_cen_dot_label"], "N/A")
        self.assertIsNone(payload["colinear_dots"])
        self.assertEqual(payload["nucleus_intensity_sum"], 30.0)
        self.assertEqual(payload["cell_pair_intensity_sum"], 40.0)
        self.assertEqual(payload["nuclear_cytoplasmic_ratio"], 3.0)

    def test_dashboard_payload_marks_uncomputed_stats_na_for_nuclear_only(self):
        uuid_value = str(uuid4())
        with temporary_media_root() as media_root:
            self._write_channel_config(media_root, uuid_value)
            self._create_uploaded_image(uuid_value, name="dashboard-nuclear-only")
            segmented = self._create_segmented_image(uuid_value, name="dashboard-nuclear-only")
            segmented.NumCells = 1
            segmented.save(update_fields=["NumCells"])
            self._write_segmented_cell_assets(media_root, uuid_value, "dashboard-nuclear-only")
            self._create_cell_stats(
                segmented,
                "dashboard-nuclear-only",
                puncta_distance=10.0,
                puncta_line_intensity=20.0,
                red_in_red_total_intensity_1=5.0,
                green_in_red_total_intensity_1=6.0,
                red_in_green_total_intensity_1=7.0,
                green_in_green_total_intensity_1=8.0,
                nucleus_intensity_sum=30.0,
                cell_pair_intensity_sum=40.0,
                cytoplasmic_intensity=10.0,
                nuclear_cytoplasmic_ratio=3.0,
                colinear_dots=0,
                off_axis_dots=0,
                properties={
                    "selected_analysis": ["NuclearCellPairIntensity"],
                    "nuclear_cell_pair_mode": "green_nucleus",
                    "nuclear_cell_pair_status": "ok",
                    "nuclear_cell_pair_contour_source": "canonical_slot_1",
                    "cen_dot_schema_version": 3,
                },
                category_cen_dot=1,
            )

            response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        files_data = json.loads(response.context["files_data_json"])
        payload = files_data[uuid_value]["Statistics"]["1"]
        self.assertIsNone(payload["puncta_distance"])
        self.assertIsNone(payload["red_in_red_total_intensity_1"])
        self.assertIsNone(payload["measurement_contour_ratio_1"])
        self.assertEqual(payload["category_cen_dot_label"], "N/A")
        self.assertIsNone(payload["colinear_dots"])
        self.assertEqual(payload["nuclear_cell_pair_contour_source"], "canonical_slot_1")
        self.assertEqual(payload["cell_pair_intensity_sum"], 40.0)
        self.assertEqual(payload["nuclear_cytoplasmic_ratio"], 3.0)

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
                red_in_green_total_intensity_1=11.0,
                green_in_green_total_intensity_1=22.0,
                red_in_green_total_intensity_2=8.0,
                green_in_green_total_intensity_2=4.0,
                red_in_green_total_intensity_3=18.0,
                green_in_green_total_intensity_3=6.0,
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
        self.assertIn("Red In Red Total Intensity 1", header_row)
        self.assertIn("Measurement/Contour Ratio 1 (Red/Green)", header_row)
        self.assertIn("Measurement/Contour Ratio 2 (Red/Green)", header_row)
        self.assertIn("Measurement/Contour Ratio 3 (Red/Green)", header_row)
        self.assertLess(
            list(header_row).index("Green In Green Average Intensity 3"),
            list(header_row).index("Measurement/Contour Ratio 1 (Red/Green)"),
        )
        self.assertLess(
            list(header_row).index("Measurement/Contour Ratio 3 (Red/Green)"),
            list(header_row).index("Distance Of Green From Red 1 (px)"),
        )
        self.assertEqual(csv_rows[0]["Measurement/Contour Ratio 1 (Red/Green)"], "0.500")
        self.assertEqual(csv_rows[0]["Measurement/Contour Ratio 2 (Red/Green)"], "2.000")
        self.assertEqual(csv_rows[0]["Measurement/Contour Ratio 3 (Red/Green)"], "3.000")


class PluginMappingRegressionTests(TestCase):
    def test_plugin_loader_maps_stable_ids_to_renamed_modules(self):
        plugin_ids = load_available_plugin_ids()
        self.assertEqual(plugin_ids[0], "PunctaDistance")
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

    def test_build_stats_execution_plan_keeps_cen_dot_standalone(self):
        plan = build_stats_execution_plan(["CENDot"])

        self.assertEqual(plan.normalized_plugins, ("CENDot",))
        self.assertEqual(plan.selected_plugins, ("CENDot",))
        self.assertEqual(plan.required_channels, ("DIC", "channel_red", "channel_green"))
        self.assertEqual(
            [instance.__class__.__name__ for instance in plan.analyses],
            ["CENDot"],
        )
