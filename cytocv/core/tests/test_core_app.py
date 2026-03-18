from __future__ import annotations

import json
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.cell_analysis import Analysis
from core.config import DEFAULT_CHANNEL_CONFIG
from core.image_processing import GrayImage
from core.models import DVLayerTifPreview, SegmentedImage, UploadedImage
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

    def test_dashboard_cell_pair_cards_use_stat_formatter_for_numeric_metrics(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "if (Number.isInteger(value)) {", html=False)
        self.assertContains(response, "return value.toFixed(3);", html=False)
        self.assertContains(response, "return 'N/A';", html=False)
        self.assertContains(
            response,
            'document.getElementById("distance").textContent = formatStatValue(cellStats ? cellStats.distance : null);',
            html=False,
        )
        self.assertContains(
            response,
            'document.getElementById("lineGFPIntensity").textContent = formatStatValue(cellStats ? cellStats.line_gfp_intensity : null);',
            html=False,
        )
        self.assertContains(
            response,
            'document.getElementById("nucleusIntensitySum").textContent = (!cellStats || nuclearUnavailable) ? "N/A" : formatStatValue(cellStats.nucleus_intensity_sum);',
            html=False,
        )
        self.assertContains(
            response,
            'document.getElementById("biorientation").textContent = formatStatValue(cellStats ? cellStats.biorientation : null);',
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
            'document.getElementById("distance").textContent = formatStatValue(cellStats ? cellStats.distance : null);',
            html=False,
        )
        self.assertContains(
            response,
            'document.getElementById("lineGFPIntensity").textContent = formatStatValue(cellStats ? cellStats.line_gfp_intensity : null);',
            html=False,
        )
        self.assertContains(
            response,
            'document.getElementById("nucleusIntensitySum").textContent = (!cellStats || nuclearUnavailable) ? "N/A" : formatStatValue(cellStats.nucleus_intensity_sum);',
            html=False,
        )
        self.assertContains(
            response,
            'document.getElementById("biorientation").textContent = formatStatValue(cellStats ? cellStats.biorientation : null);',
            html=False,
        )


class PluginMappingRegressionTests(TestCase):
    def test_plugin_loader_maps_stable_ids_to_renamed_modules(self):
        plugin_ids = load_available_plugin_ids()
        self.assertIn("MCherryLine", plugin_ids)
        self.assertIn("GFPDot", plugin_ids)

        plugin_class = get_plugin_class("MCherryLine")
        self.assertEqual(plugin_class.__name__, "MCherryLine")
        self.assertTrue(issubclass(plugin_class, Analysis))

        instances = instantiate_selected_plugins(["MCherryLine", "GFPDot"])
        self.assertEqual(
            [instance.__class__.__name__ for instance in instances],
            ["MCherryLine", "GFPDot"],
        )
        self.assertEqual(GrayImage.__name__, "GrayImage")

    def test_build_stats_execution_plan_normalizes_raw_plugin_selection(self):
        plan = build_stats_execution_plan(
            ["UnknownPlugin", "NucleusIntensity", "NuclearCellularIntensity", "DAPI_NucleusIntensity"]
        )

        self.assertEqual(plan.normalized_plugins, ("NuclearCellularIntensity",))
        self.assertEqual(plan.selected_plugins, ("NuclearCellularIntensity",))
        self.assertEqual(plan.required_channels, ("DIC", "mCherry", "GFP"))
        self.assertEqual(
            [instance.__class__.__name__ for instance in plan.analyses],
            ["NuclearCellularIntensity"],
        )
