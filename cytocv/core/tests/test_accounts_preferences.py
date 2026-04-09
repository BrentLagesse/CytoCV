"""Tests for account preference and account-area safeguards."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from accounts.preferences import (
    get_user_preferences,
    normalize_preferences_payload,
    should_auto_save_experiments,
    update_user_preferences,
)
from core.models import (
    CellStatistics,
    DVLayerTifPreview,
    SegmentedImage,
    UploadedImage,
    get_guest_user,
)
from core.mrcnn.preprocess_images import PreprocessedImageArtifact
from core.scale import apply_manual_override_scale, build_scale_info
from core.stats_plugins import PLUGIN_DEFINITIONS


class PreferenceNormalizationTests(TestCase):
    def test_default_payload_uses_expected_plugin_defaults(self):
        normalized = normalize_preferences_payload({})
        defaults = normalized["experiment_defaults"]
        self.assertEqual(
            defaults["selected_plugins"],
            [
                "RedLineIntensity",
                "CENDot",
                "GreenRedIntensity",
                "NuclearCellularIntensity",
            ],
        )
        self.assertEqual(defaults["puncta_line_mode"], "red_puncta")
        self.assertEqual(defaults["nuclear_cellular_mode"], "green_nucleus")
        self.assertTrue(defaults["use_metadata_scale"])
        self.assertTrue(normalized["show_saved_file_channels"])
        self.assertTrue(normalized["show_saved_file_scales"])
        self.assertTrue(normalized["sidebar_starts_open"])

    def test_normalize_preferences_filters_invalid_values(self):
        normalized = normalize_preferences_payload(
            {
                "experiment_defaults": {
                    "selected_plugins": ["RedLineIntensity", "Unknown"],
                    "module_enabled": "true",
                    "enforce_layer_count": "true",
                    "enforce_wavelengths": "false",
                    "manual_required_channels": ["DIC", "BAD"],
                    "red_line_width": "-5",
                    "cen_dot_distance": "abc",
                    "cen_dot_collinearity_threshold": "-1",
                    "puncta_line_mode": "bad_mode",
                    "nuclear_cellular_mode": "bad_mode",
                    "red_line_width_unit": "um",
                    "cen_dot_distance_unit": "px",
                    "microns_per_pixel": "0",
                    "use_metadata_scale": "off",
                },
                "auto_save_experiments": "off",
                "show_saved_file_scales": "off",
            }
        )

        defaults = normalized["experiment_defaults"]
        self.assertEqual(defaults["selected_plugins"], ["RedLineIntensity"])
        self.assertTrue(defaults["module_enabled"])
        self.assertTrue(defaults["enforce_layer_count"])
        self.assertFalse(defaults["enforce_wavelengths"])
        self.assertEqual(defaults["manual_required_channels"], ["DIC"])
        self.assertEqual(defaults["red_line_width"], 1)
        self.assertEqual(defaults["cen_dot_distance"], 37)
        self.assertEqual(defaults["cen_dot_collinearity_threshold"], 66)
        self.assertEqual(defaults["puncta_line_mode"], "red_puncta")
        self.assertEqual(defaults["nuclear_cellular_mode"], "green_nucleus")
        self.assertFalse(defaults["use_metadata_scale"])
        self.assertFalse(normalized["auto_save_experiments"])
        self.assertTrue(normalized["show_saved_file_channels"])
        self.assertFalse(normalized["show_saved_file_scales"])


class AccountAreaAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="preference-tests@example.com",
            password="TestPass123!",
            first_name="Pref",
            last_name="Tester",
        )

    def test_account_area_requires_authentication(self):
        for name in ("dashboard", "account_settings", "workflow_defaults"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("signin"), response["Location"])

    def test_delete_account_requires_matching_email(self):
        self.assertTrue(
            self.client.login(
                email="preference-tests@example.com",
                password="TestPass123!",
            )
        )
        response = self.client.post(
            reverse("account_settings"),
            {"action": "delete_account", "confirm_email": "wrong@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Incorrect email address entered.")
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_account_settings_page_renders_information_and_actions_cards(self):
        self.assertTrue(
            self.client.login(
                email="preference-tests@example.com",
                password="TestPass123!",
            )
        )
        response = self.client.get(reverse("account_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="accountInformationTitle"', html=False)
        self.assertContains(response, 'id="accountActionsTitle"', html=False)
        self.assertContains(response, "Account Information")
        self.assertContains(response, "Account Actions")
        self.assertContains(response, "Delete your account")

    def test_delete_account_removes_user_on_match(self):
        self.assertTrue(
            self.client.login(
                email="preference-tests@example.com",
                password="TestPass123!",
            )
        )
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "delete_account",
                "confirm_email": "preference-tests@example.com",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("home"))
        self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())


class AccountDeletionIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="delete-owner@example.com",
            password="TestPass123!",
            first_name="Delete",
            last_name="Owner",
        )
        self.other_user = user_model.objects.create_user(
            email="delete-other@example.com",
            password="TestPass123!",
        )
        self.assertTrue(
            self.client.login(
                email="delete-owner@example.com",
                password="TestPass123!",
            )
        )

    def _create_account_artifacts(self, owner, stem: str) -> str:
        file_uuid = uuid4()
        uploaded = UploadedImage.objects.create(
            user=owner,
            name=stem,
            uuid=file_uuid,
            file_location=f"{file_uuid}/{stem}.dv",
        )
        segmented = SegmentedImage.objects.create(
            user=owner,
            UUID=file_uuid,
            file_location=f"user_{file_uuid}/{stem}.png",
            ImagePath=f"{file_uuid}/output/{stem}_frame_0.png",
            CellPairPrefix=f"{file_uuid}/segmented/cell_",
            NumCells=1,
        )
        CellStatistics.objects.create(
            segmented_image=segmented,
            cell_id=1,
            distance=1.0,
            line_green_intensity=2.0,
            nucleus_intensity_sum=3.0,
            cellular_intensity_sum=4.0,
        )
        self.assertTrue(UploadedImage.objects.filter(pk=uploaded.pk).exists())
        self.assertTrue(SegmentedImage.objects.filter(pk=segmented.pk).exists())
        self.assertTrue(CellStatistics.objects.filter(segmented_image=segmented).exists())
        return str(file_uuid)

    def _create_media_artifacts(self, media_root: str, file_uuid: str, stem: str) -> tuple[Path, Path]:
        uuid_dir = Path(media_root) / file_uuid
        user_uuid_dir = Path(media_root) / f"user_{file_uuid}"
        paths = [
            uuid_dir / f"{stem}.dv",
            uuid_dir / "output" / f"{stem}_frame_0.png",
            uuid_dir / "segmented" / "cell_1.png",
            user_uuid_dir / f"{stem}.png",
        ]
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x")
        return uuid_dir, user_uuid_dir

    def test_delete_account_removes_user_related_rows_media_and_session(self):
        with TemporaryDirectory() as temp_media:
            owned_uuid = self._create_account_artifacts(self.user, "owned_sample")
            uuid_dir, user_uuid_dir = self._create_media_artifacts(
                temp_media,
                owned_uuid,
                "owned_sample",
            )
            self.assertTrue(uuid_dir.exists())
            self.assertTrue(user_uuid_dir.exists())

            with patch("accounts.views.profile.MEDIA_ROOT", temp_media):
                response = self.client.post(
                    reverse("account_settings"),
                    {
                        "action": "delete_account",
                        "confirm_email": "delete-owner@example.com",
                    },
                )

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], reverse("home"))
            self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())
            self.assertFalse(UploadedImage.objects.filter(uuid=owned_uuid).exists())
            self.assertFalse(SegmentedImage.objects.filter(UUID=owned_uuid).exists())
            self.assertFalse(
                CellStatistics.objects.filter(segmented_image_id=owned_uuid).exists()
            )
            self.assertFalse(uuid_dir.exists())
            self.assertFalse(user_uuid_dir.exists())

            auth_response = self.client.get(reverse("dashboard"))
            self.assertEqual(auth_response.status_code, 302)
            self.assertIn(reverse("signin"), auth_response["Location"])

    def test_delete_account_with_wrong_email_keeps_user_rows_and_media(self):
        with TemporaryDirectory() as temp_media:
            owned_uuid = self._create_account_artifacts(self.user, "keep_sample")
            uuid_dir, user_uuid_dir = self._create_media_artifacts(
                temp_media,
                owned_uuid,
                "keep_sample",
            )

            with patch("accounts.views.profile.MEDIA_ROOT", temp_media):
                response = self.client.post(
                    reverse("account_settings"),
                    {
                        "action": "delete_account",
                        "confirm_email": "wrong@example.com",
                    },
                )

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Incorrect email address entered.")
            self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())
            self.assertTrue(UploadedImage.objects.filter(uuid=owned_uuid).exists())
            self.assertTrue(SegmentedImage.objects.filter(UUID=owned_uuid).exists())
            self.assertTrue(
                CellStatistics.objects.filter(segmented_image_id=owned_uuid).exists()
            )
            self.assertTrue(uuid_dir.exists())
            self.assertTrue(user_uuid_dir.exists())

    def test_delete_account_does_not_remove_other_users_data(self):
        with TemporaryDirectory() as temp_media:
            owned_uuid = self._create_account_artifacts(self.user, "owned_sample")
            other_uuid = self._create_account_artifacts(self.other_user, "other_sample")
            owned_uuid_dir, owned_user_dir = self._create_media_artifacts(
                temp_media,
                owned_uuid,
                "owned_sample",
            )
            other_uuid_dir, other_user_dir = self._create_media_artifacts(
                temp_media,
                other_uuid,
                "other_sample",
            )

            with patch("accounts.views.profile.MEDIA_ROOT", temp_media):
                response = self.client.post(
                    reverse("account_settings"),
                    {
                        "action": "delete_account",
                        "confirm_email": "delete-owner@example.com",
                    },
                )

            self.assertEqual(response.status_code, 302)
            self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())
            self.assertTrue(get_user_model().objects.filter(pk=self.other_user.pk).exists())

            self.assertFalse(UploadedImage.objects.filter(uuid=owned_uuid).exists())
            self.assertFalse(SegmentedImage.objects.filter(UUID=owned_uuid).exists())
            self.assertFalse(
                CellStatistics.objects.filter(segmented_image_id=owned_uuid).exists()
            )
            self.assertFalse(owned_uuid_dir.exists())
            self.assertFalse(owned_user_dir.exists())

            self.assertTrue(UploadedImage.objects.filter(uuid=other_uuid).exists())
            self.assertTrue(SegmentedImage.objects.filter(UUID=other_uuid).exists())
            self.assertTrue(
                CellStatistics.objects.filter(segmented_image_id=other_uuid).exists()
            )
            self.assertTrue(other_uuid_dir.exists())
            self.assertTrue(other_user_dir.exists())


class DashboardBulkDeleteTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="dashboard-owner@example.com",
            password="TestPass123!",
        )
        self.other_user = user_model.objects.create_user(
            email="dashboard-other@example.com",
            password="TestPass123!",
        )
        self.assertTrue(
            self.client.login(
                email="dashboard-owner@example.com",
                password="TestPass123!",
            )
        )

    def _create_saved_file(self, owner, filename: str):
        file_uuid = uuid4()
        UploadedImage.objects.create(
            user=owner,
            name=filename,
            uuid=file_uuid,
            file_location=f"{file_uuid}/{filename}.dv",
        )
        SegmentedImage.objects.create(
            user=owner,
            UUID=file_uuid,
            file_location=f"user_{file_uuid}/{filename}.png",
            ImagePath=f"{file_uuid}/output/{filename}_frame_0.png",
            CellPairPrefix=f"{file_uuid}/segmented/cell_",
            NumCells=1,
        )
        return str(file_uuid)

    def test_bulk_delete_rejects_foreign_uuid(self):
        owned_uuid = self._create_saved_file(self.user, "owned")
        foreign_uuid = self._create_saved_file(self.other_user, "foreign")

        response = self.client.post(
            reverse("dashboard_bulk_delete"),
            data=json.dumps({"uuids": [owned_uuid, foreign_uuid]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(UploadedImage.objects.filter(uuid=owned_uuid).exists())
        self.assertTrue(UploadedImage.objects.filter(uuid=foreign_uuid).exists())

    def test_bulk_delete_removes_owned_files(self):
        uuid_one = self._create_saved_file(self.user, "sample_one")
        uuid_two = self._create_saved_file(self.user, "sample_two")

        response = self.client.post(
            reverse("dashboard_bulk_delete"),
            data=json.dumps({"uuids": [uuid_one, uuid_two]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["deleted_count"], 2)
        self.assertFalse(UploadedImage.objects.filter(uuid=uuid_one).exists())
        self.assertFalse(UploadedImage.objects.filter(uuid=uuid_two).exists())
        self.assertFalse(SegmentedImage.objects.filter(UUID=uuid_one).exists())
        self.assertFalse(SegmentedImage.objects.filter(UUID=uuid_two).exists())


class DisplayManualSaveTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="display-owner@example.com",
            password="TestPass123!",
        )
        self.other_user = user_model.objects.create_user(
            email="display-other@example.com",
            password="TestPass123!",
        )
        self.guest_user_id = get_guest_user()
        self.assertTrue(
            self.client.login(
                email="display-owner@example.com",
                password="TestPass123!",
            )
        )

    def _create_display_file(
        self,
        *,
        uploaded_owner,
        segmented_owner_id: str,
        filename: str,
    ) -> str:
        file_uuid = uuid4()
        UploadedImage.objects.create(
            user=uploaded_owner,
            name=filename,
            uuid=file_uuid,
            file_location=f"{file_uuid}/{filename}.dv",
        )
        SegmentedImage.objects.create(
            user_id=segmented_owner_id,
            UUID=file_uuid,
            file_location=f"user_{file_uuid}/{filename}.png",
            ImagePath=f"{file_uuid}/output/{filename}_frame_0.png",
            CellPairPrefix=f"{file_uuid}/segmented/cell_",
            NumCells=2,
        )
        return str(file_uuid)

    def _add_cell_stat(self, file_uuid: str, *, cell_id: int = 1) -> None:
        segmented = SegmentedImage.objects.get(UUID=file_uuid)
        CellStatistics.objects.create(
            segmented_image=segmented,
            cell_id=cell_id,
            distance=1.0,
            line_green_intensity=2.0,
            nucleus_intensity_sum=3.0,
            cellular_intensity_sum=4.0,
            red_intensity_1=5.0,
            green_intensity_1=6.0,
            red_in_green_intensity_1=7.0,
            green_in_green_intensity_1=8.0,
            green_red_intensity_1=6.0 / 5.0,
            category_cen_dot=1,
            properties={"nuclear_cellular_mode": "red_nucleus"},
        )

    def _set_transient_uuids(self, uuids: list[str]) -> None:
        session = self.client.session
        session["transient_experiment_uuids"] = uuids
        session.save()

    def _create_preprocess_file(self, *, filename: str) -> str:
        file_uuid = uuid4()
        uploaded = UploadedImage.objects.create(
            user=self.user,
            name=filename,
            uuid=file_uuid,
            file_location=f"{file_uuid}/{filename}.dv",
        )
        DVLayerTifPreview.objects.create(
            uploaded_image_uuid=uploaded,
            wavelength="DAPI",
            file_location=f"{file_uuid}/{filename}_preview.png",
        )
        return str(file_uuid)

    @staticmethod
    def _write_run_bytes(media_root: str, uuid_value: str, *, size: int) -> None:
        target = Path(media_root) / uuid_value / "output" / "frame.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x" * size)

    def test_display_save_endpoint_rejects_invalid_payload(self):
        response = self.client.post(
            reverse("display_save_files"),
            data=json.dumps({"uuids": "bad-shape"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_display_save_endpoint_rejects_empty_uuid_list(self):
        response = self.client.post(
            reverse("display_save_files"),
            data=json.dumps({"uuids": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_display_save_endpoint_rejects_foreign_or_unavailable_uuid(self):
        transient_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.guest_user_id,
            filename="transient_owned",
        )
        foreign_uuid = self._create_display_file(
            uploaded_owner=self.other_user,
            segmented_owner_id=self.guest_user_id,
            filename="foreign_uploaded",
        )
        self._set_transient_uuids([transient_uuid, foreign_uuid])

        response = self.client.post(
            reverse("display_save_files"),
            data=json.dumps({"uuids": [transient_uuid, foreign_uuid]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            SegmentedImage.objects.get(UUID=transient_uuid).user_id,
            self.guest_user_id,
        )
        session = self.client.session
        self.assertIn(transient_uuid, session.get("transient_experiment_uuids", []))

    def test_display_save_endpoint_saves_transient_file_and_clears_session(self):
        transient_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.guest_user_id,
            filename="manual_save_candidate",
        )
        self._set_transient_uuids([transient_uuid])

        response = self.client.post(
            reverse("display_save_files"),
            data=json.dumps({"uuids": [transient_uuid]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["saved_count"], 1)
        self.assertEqual(payload["already_saved_count"], 0)
        self.assertEqual(payload["saved_uuids"], [transient_uuid])
        self.assertEqual(
            SegmentedImage.objects.get(UUID=transient_uuid).user_id,
            self.user.id,
        )

        session = self.client.session
        self.assertNotIn(transient_uuid, session.get("transient_experiment_uuids", []))

        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "manual_save_candidate")

    def test_dashboard_renders_main_table_export_buttons(self):
        self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="dashboard_export_first",
        )

        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="exportButtons"', html=False)
        self.assertContains(response, 'id="downloadCsvBtn"', html=False)
        self.assertContains(response, 'id="downloadXlsxBtn"', html=False)
        self.assertNotContains(response, "data-file-export=", html=False)

    def test_dashboard_template_renders_glass_layout_and_existing_hooks(self):
        self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="dashboard_glass_layout",
        )

        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-ui-region="dashboard-main-shell"', html=False)
        self.assertContains(response, 'data-ui-region="dashboard-content-stack"', html=False)
        self.assertContains(response, 'data-ui-region="top-stage-card"', html=False)
        self.assertContains(response, 'data-ui-region="cell-pairs-card"', html=False)
        self.assertContains(response, 'data-ui-region="cell-metrics-strip"', html=False)
        self.assertContains(response, 'data-ui-region="stats-table-card"', html=False)
        self.assertContains(response, 'class="content-wrapper glass-shell"', html=False)
        self.assertContains(response, 'class="main-content glass-shell"', html=False)
        self.assertContains(response, 'class="storage-card glass-card glass-section"', html=False)
        self.assertContains(response, 'id="viewerPanel"', html=False)
        self.assertContains(response, 'id="mainChannelSwitcher"', html=False)
        self.assertContains(response, 'id="toggleContours"', html=False)
        self.assertContains(response, 'id="statsTablePanel"', html=False)
        self.assertContains(response, 'id="tableFullscreenBtn"', html=False)
        self.assertContains(response, 'id="tableScrollFrame"', html=False)
        self.assertContains(response, 'id="downloadCsvBtn"', html=False)
        self.assertContains(response, 'id="downloadXlsxBtn"', html=False)
        self.assertContains(response, 'id="previousFileBtn" disabled aria-disabled="true"', html=False)
        self.assertContains(response, 'id="nextFileBtn" disabled aria-disabled="true"', html=False)
        self.assertContains(response, 'Line + Spot Metrics')
        self.assertContains(response, 'Raw Contour Intensity Sums')
        self.assertContains(response, 'Contour slots 1/2/3 are ranked consistently after clipping to the segmented cell')
        self.assertNotContains(response, 'Intensity + Green Output')

    def test_display_template_renders_glass_layout_and_existing_hooks(self):
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="display_glass_layout",
        )

        response = self.client.get(reverse("display", args=[saved_uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-ui-region="display-main-shell"', html=False)
        self.assertContains(response, 'data-ui-region="display-content-stack"', html=False)
        self.assertContains(response, 'data-ui-region="top-stage-card"', html=False)
        self.assertContains(response, 'data-ui-region="cell-pairs-card"', html=False)
        self.assertContains(response, 'data-ui-region="cell-metrics-strip"', html=False)
        self.assertContains(response, 'data-ui-region="stats-table-card"', html=False)
        self.assertContains(response, 'class="content-wrapper glass-shell"', html=False)
        self.assertContains(response, 'class="main-content glass-shell"', html=False)
        self.assertContains(response, 'id="viewerPanel"', html=False)
        self.assertContains(response, 'id="mainChannelSwitcher"', html=False)
        self.assertContains(response, 'id="toggleContours"', html=False)
        self.assertContains(response, 'id="statsTablePanel"', html=False)
        self.assertContains(response, 'id="tableFullscreenBtn"', html=False)
        self.assertContains(response, 'id="tableScrollFrame"', html=False)
        self.assertContains(response, 'id="displayDownloadCsvBtn"', html=False)
        self.assertContains(response, 'id="displayDownloadXlsxBtn"', html=False)
        self.assertContains(response, 'id="previousFileBtn" disabled aria-disabled="true"', html=False)
        self.assertContains(response, 'id="nextFileBtn" disabled aria-disabled="true"', html=False)
        self.assertContains(response, 'id="dic_form"', html=False)
        self.assertContains(response, 'id="blue_form"', html=False)
        self.assertContains(response, 'id="red_form"', html=False)
        self.assertContains(response, 'id="green_form"', html=False)
        self.assertContains(response, 'Line + Spot Metrics')
        self.assertContains(response, 'Raw Contour Intensity Sums')
        self.assertContains(response, 'Contour slots 1/2/3 are ranked consistently after clipping to the segmented cell')
        self.assertNotContains(response, 'Intensity + Green Output')

    def test_preprocess_template_renders_glass_layout_and_existing_hooks(self):
        preprocess_uuid = self._create_preprocess_file(filename="preprocess_glass_layout")

        response = self.client.get(reverse("pre_process", args=[preprocess_uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-ui-region="preprocess-main-shell"', html=False)
        self.assertContains(response, 'data-ui-region="preprocess-content-stack"', html=False)
        self.assertContains(response, 'data-ui-region="file-context-card"', html=False)
        self.assertContains(response, 'data-ui-region="main-image-stage"', html=False)
        self.assertNotContains(response, 'data-ui-region="actions-card"', html=False)
        self.assertContains(response, 'class="content-wrapper glass-shell"', html=False)
        self.assertContains(response, 'class="main-content glass-shell"', html=False)
        self.assertContains(response, 'id="preprocessForm"', html=False)
        self.assertContains(response, 'id="imageContainer"', html=False)
        self.assertContains(response, 'id="prevButton"', html=False)
        self.assertContains(response, 'id="nextButton"', html=False)
        self.assertContains(response, 'id="currentFileInfo"', html=False)
        self.assertContains(response, 'id="currentFileIndex"', html=False)
        self.assertContains(response, 'id="preprocessScaleSummary"', html=False)

    def test_dashboard_csv_export_for_file_uuid_returns_attachment(self):
        file_name = "dashboard_csv_export"
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename=file_name,
        )
        self._add_cell_stat(saved_uuid)

        response = self.client.get(
            reverse("dashboard"),
            {"file_uuid": saved_uuid, "_export": "csv"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn(f"{file_name}.csv", response["Content-Disposition"])
        self.assertIn("text/csv", response["Content-Type"])
        csv_text = response.content.decode("utf-8")
        self.assertIn("Cell ID", csv_text)
        self.assertIn("Red in Red Intensity 1", csv_text)
        self.assertIn("Green in Red Intensity 1", csv_text)
        self.assertIn("Red in Green Intensity 1", csv_text)
        self.assertIn("Green in Green Intensity 1", csv_text)
        self.assertNotIn("Green/Red ratio 1", csv_text)
        self.assertIn("Measurement/Contour Ratio 1 (Green/Red)", csv_text)
        self.assertIn("5.000", csv_text)
        self.assertIn("8.000", csv_text)
        self.assertIn("CEN Dot Category", csv_text)
        self.assertIn("One green dot with each red dot", csv_text)

    def test_dashboard_xlsx_export_for_file_uuid_returns_attachment(self):
        file_name = "dashboard_xlsx_export"
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename=file_name,
        )
        self._add_cell_stat(saved_uuid)

        response = self.client.get(
            reverse("dashboard"),
            {"file_uuid": saved_uuid, "_export": "xlsx"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn(f"{file_name}.xlsx", response["Content-Disposition"])
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            response["Content-Type"],
        )
        self.assertGreater(len(response.content), 0)
        workbook = load_workbook(BytesIO(response.content))
        sheet = workbook.active
        headers = [cell.value for cell in sheet[1]]
        self.assertIn("Red in Red Intensity 1", headers)
        self.assertIn("Green in Red Intensity 1", headers)
        self.assertIn("Red in Green Intensity 1", headers)
        self.assertIn("Green in Green Intensity 1", headers)
        self.assertNotIn("Green/Red ratio 1", headers)
        self.assertIn("Measurement/Contour Ratio 1 (Green/Red)", headers)
        self.assertIn("CEN Dot Category", headers)
        gfp_dot_col = headers.index("CEN Dot Category") + 1
        self.assertEqual(sheet.cell(row=2, column=gfp_dot_col).value, "One green dot with each red dot")

    def test_display_csv_export_uses_uploaded_file_name(self):
        file_name = "display_csv_export_source"
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename=file_name,
        )
        self._add_cell_stat(saved_uuid)

        response = self.client.get(
            reverse("display", args=[saved_uuid]),
            {"_export": "csv"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn(f"{file_name}.csv", response["Content-Disposition"])
        self.assertIn("text/csv", response["Content-Type"])

    def test_display_xlsx_export_uses_uploaded_file_name(self):
        file_name = "display_xlsx_export_source"
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename=file_name,
        )
        self._add_cell_stat(saved_uuid)

        response = self.client.get(
            reverse("display", args=[saved_uuid]),
            {"_export": "xlsx"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn(f"{file_name}.xlsx", response["Content-Disposition"])
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            response["Content-Type"],
        )

    def test_display_save_endpoint_is_idempotent_for_saved_file(self):
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="already_saved",
        )

        response = self.client.post(
            reverse("display_save_files"),
            data=json.dumps({"uuids": [saved_uuid]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["saved_count"], 0)
        self.assertEqual(payload["already_saved_count"], 1)
        self.assertEqual(payload["already_saved_uuids"], [saved_uuid])
        self.assertEqual(
            SegmentedImage.objects.get(UUID=saved_uuid).user_id,
            self.user.id,
        )

    def test_display_save_endpoint_handles_mixed_saved_and_transient_selection(self):
        transient_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.guest_user_id,
            filename="mixed_transient",
        )
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="mixed_saved",
        )
        self._set_transient_uuids([transient_uuid])

        response = self.client.post(
            reverse("display_save_files"),
            data=json.dumps({"uuids": [saved_uuid, transient_uuid]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["saved_count"], 1)
        self.assertEqual(payload["already_saved_count"], 1)
        self.assertIn(transient_uuid, payload["saved_uuids"])
        self.assertIn(saved_uuid, payload["already_saved_uuids"])
        self.assertEqual(
            SegmentedImage.objects.get(UUID=transient_uuid).user_id,
            self.user.id,
        )
        self.assertEqual(
            SegmentedImage.objects.get(UUID=saved_uuid).user_id,
            self.user.id,
        )

        session = self.client.session
        self.assertNotIn(transient_uuid, session.get("transient_experiment_uuids", []))

    def test_display_save_endpoint_rejects_when_storage_quota_is_exceeded(self):
        transient_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.guest_user_id,
            filename="quota_transient",
        )
        self._set_transient_uuids([transient_uuid])
        self.user.total_storage = 32
        self.user.save(update_fields=["total_storage"])

        with TemporaryDirectory() as temp_media:
            with override_settings(MEDIA_ROOT=temp_media):
                self._write_run_bytes(temp_media, transient_uuid, size=96)
                response = self.client.post(
                    reverse("display_save_files"),
                    data=json.dumps({"uuids": [transient_uuid]}),
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 507)
        payload = response.json()
        self.assertEqual(payload["code"], "storage_full")
        self.assertEqual(
            payload["error"],
            "Selected files could not be saved because your storage is full. Free up space and try again.",
        )
        self.assertEqual(
            SegmentedImage.objects.get(UUID=transient_uuid).user_id,
            self.guest_user_id,
        )
        self.assertIn(
            transient_uuid,
            self.client.session.get("transient_experiment_uuids", []),
        )

    def test_display_unsave_endpoint_rejects_invalid_payload(self):
        response = self.client.post(
            reverse("display_unsave_files"),
            data=json.dumps({"uuids": "bad-shape"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_display_unsave_endpoint_unsaves_saved_file_and_adds_transient(self):
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="manual_unsave_candidate",
        )

        response = self.client.post(
            reverse("display_unsave_files"),
            data=json.dumps({"uuids": [saved_uuid]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["unsaved_count"], 1)
        self.assertEqual(payload["already_unsaved_count"], 0)
        self.assertEqual(payload["unsaved_uuids"], [saved_uuid])
        self.assertEqual(
            SegmentedImage.objects.get(UUID=saved_uuid).user_id,
            self.guest_user_id,
        )
        session = self.client.session
        self.assertIn(saved_uuid, session.get("transient_experiment_uuids", []))

        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertNotContains(dashboard_response, "manual_unsave_candidate")

    def test_display_unsave_endpoint_rejects_foreign_or_unavailable_uuid(self):
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="owner_saved",
        )
        foreign_uuid = self._create_display_file(
            uploaded_owner=self.other_user,
            segmented_owner_id=self.other_user.id,
            filename="foreign_saved",
        )

        response = self.client.post(
            reverse("display_unsave_files"),
            data=json.dumps({"uuids": [saved_uuid, foreign_uuid]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(SegmentedImage.objects.get(UUID=saved_uuid).user_id, self.user.id)

    def test_display_unsave_endpoint_is_idempotent_for_already_unsaved_file(self):
        transient_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.guest_user_id,
            filename="already_unsaved",
        )
        self._set_transient_uuids([transient_uuid])

        response = self.client.post(
            reverse("display_unsave_files"),
            data=json.dumps({"uuids": [transient_uuid]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["unsaved_count"], 0)
        self.assertEqual(payload["already_unsaved_count"], 1)
        self.assertEqual(payload["already_unsaved_uuids"], [transient_uuid])
        self.assertEqual(
            SegmentedImage.objects.get(UUID=transient_uuid).user_id,
            self.guest_user_id,
        )

    def test_display_unsave_endpoint_handles_mixed_saved_and_unsaved_selection(self):
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="mixed_saved_unsave",
        )
        transient_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.guest_user_id,
            filename="mixed_unsaved_unsave",
        )
        self._set_transient_uuids([transient_uuid])

        response = self.client.post(
            reverse("display_unsave_files"),
            data=json.dumps({"uuids": [saved_uuid, transient_uuid]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["unsaved_count"], 1)
        self.assertEqual(payload["already_unsaved_count"], 1)
        self.assertIn(saved_uuid, payload["unsaved_uuids"])
        self.assertIn(transient_uuid, payload["already_unsaved_uuids"])
        self.assertEqual(
            SegmentedImage.objects.get(UUID=saved_uuid).user_id,
            self.guest_user_id,
        )

    def test_display_sync_selection_rejects_selected_not_in_visible_list(self):
        visible_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.guest_user_id,
            filename="visible_sync",
        )
        outside_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.guest_user_id,
            filename="outside_sync",
        )
        self._set_transient_uuids([visible_uuid, outside_uuid])

        response = self.client.post(
            reverse("display_sync_file_selection"),
            data=json.dumps(
                {
                    "visible_uuids": [visible_uuid],
                    "selected_uuids": [outside_uuid],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_display_sync_selection_applies_save_and_unsave_together(self):
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="sync_saved",
        )
        transient_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.guest_user_id,
            filename="sync_transient",
        )
        self._set_transient_uuids([transient_uuid])

        response = self.client.post(
            reverse("display_sync_file_selection"),
            data=json.dumps(
                {
                    "visible_uuids": [saved_uuid, transient_uuid],
                    "selected_uuids": [transient_uuid],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["saved_count"], 1)
        self.assertEqual(payload["unsaved_count"], 1)
        self.assertIn(transient_uuid, payload["saved_uuids"])
        self.assertIn(saved_uuid, payload["unsaved_uuids"])
        self.assertEqual(
            SegmentedImage.objects.get(UUID=transient_uuid).user_id,
            self.user.id,
        )
        self.assertEqual(
            SegmentedImage.objects.get(UUID=saved_uuid).user_id,
            self.guest_user_id,
        )

        session = self.client.session
        transient_session = set(session.get("transient_experiment_uuids", []))
        self.assertIn(saved_uuid, transient_session)
        self.assertNotIn(transient_uuid, transient_session)

        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "sync_transient")
        self.assertNotContains(dashboard_response, "sync_saved")

    def test_display_sync_selection_allows_net_save_when_unsave_frees_space(self):
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="sync_saved_quota",
        )
        transient_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.guest_user_id,
            filename="sync_transient_quota",
        )
        self._set_transient_uuids([transient_uuid])
        self.user.total_storage = 80
        self.user.save(update_fields=["total_storage"])

        with TemporaryDirectory() as temp_media:
            with override_settings(MEDIA_ROOT=temp_media):
                self._write_run_bytes(temp_media, saved_uuid, size=80)
                self._write_run_bytes(temp_media, transient_uuid, size=60)
                response = self.client.post(
                    reverse("display_sync_file_selection"),
                    data=json.dumps(
                        {
                            "visible_uuids": [saved_uuid, transient_uuid],
                            "selected_uuids": [transient_uuid],
                        }
                    ),
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["saved_count"], 1)
        self.assertEqual(payload["unsaved_count"], 1)
        self.assertEqual(
            SegmentedImage.objects.get(UUID=transient_uuid).user_id,
            self.user.id,
        )
        self.assertEqual(
            SegmentedImage.objects.get(UUID=saved_uuid).user_id,
            self.guest_user_id,
        )

    def test_display_sync_selection_rejects_atomically_when_net_quota_is_exceeded(self):
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="sync_saved_atomic",
        )
        transient_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.guest_user_id,
            filename="sync_transient_atomic",
        )
        self._set_transient_uuids([transient_uuid])
        self.user.total_storage = 30
        self.user.save(update_fields=["total_storage"])

        with TemporaryDirectory() as temp_media:
            with override_settings(MEDIA_ROOT=temp_media):
                self._write_run_bytes(temp_media, saved_uuid, size=20)
                self._write_run_bytes(temp_media, transient_uuid, size=60)
                response = self.client.post(
                    reverse("display_sync_file_selection"),
                    data=json.dumps(
                        {
                            "visible_uuids": [saved_uuid, transient_uuid],
                            "selected_uuids": [transient_uuid],
                        }
                    ),
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 507)
        payload = response.json()
        self.assertEqual(payload["code"], "storage_full")
        self.assertEqual(
            SegmentedImage.objects.get(UUID=transient_uuid).user_id,
            self.guest_user_id,
        )
        self.assertEqual(
            SegmentedImage.objects.get(UUID=saved_uuid).user_id,
            self.user.id,
        )
        transient_session = set(self.client.session.get("transient_experiment_uuids", []))
        self.assertIn(transient_uuid, transient_session)
        self.assertNotIn(saved_uuid, transient_session)

    def test_display_sync_selection_rejects_foreign_visible_file(self):
        owned_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.guest_user_id,
            filename="sync_owned",
        )
        foreign_uuid = self._create_display_file(
            uploaded_owner=self.other_user,
            segmented_owner_id=self.guest_user_id,
            filename="sync_foreign",
        )
        self._set_transient_uuids([owned_uuid, foreign_uuid])

        response = self.client.post(
            reverse("display_sync_file_selection"),
            data=json.dumps(
                {
                    "visible_uuids": [owned_uuid, foreign_uuid],
                    "selected_uuids": [owned_uuid],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_display_view_respects_channel_visibility_preference(self):
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="visibility_saved",
        )
        prefs = get_user_preferences(self.user)
        prefs["show_saved_file_channels"] = False
        update_user_preferences(self.user, prefs)

        response = self.client.get(reverse("display", args=[saved_uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="sidebar channels-hidden"')
        self.assertContains(response, "Show Channels")

    def test_preprocess_view_respects_channel_visibility_preference(self):
        preprocess_uuid = self._create_preprocess_file(filename="visibility_preprocess")
        prefs = get_user_preferences(self.user)
        prefs["show_saved_file_channels"] = False
        update_user_preferences(self.user, prefs)

        response = self.client.get(reverse("pre_process", args=[preprocess_uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="sidebar channels-hidden"')
        self.assertContains(response, "Show Channels")

    def test_display_view_respects_scale_visibility_preference(self):
        saved_uuid = self._create_display_file(
            uploaded_owner=self.user,
            segmented_owner_id=self.user.id,
            filename="scale_visibility_saved",
        )
        prefs = get_user_preferences(self.user)
        prefs["show_saved_file_scales"] = False
        update_user_preferences(self.user, prefs)

        response = self.client.get(reverse("display", args=[saved_uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="sidebar scales-hidden"')
        self.assertContains(response, "Show Scale")

    def test_preprocess_view_respects_scale_visibility_preference(self):
        preprocess_uuid = self._create_preprocess_file(filename="scale_visibility_preprocess")
        prefs = get_user_preferences(self.user)
        prefs["show_saved_file_scales"] = False
        update_user_preferences(self.user, prefs)

        response = self.client.get(reverse("pre_process", args=[preprocess_uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="sidebar scales-hidden"')
        self.assertContains(response, "Show Scale")

    def test_preprocess_post_rejects_tampered_scale_uuid_map(self):
        preprocess_uuid = self._create_preprocess_file(filename="tamper_preprocess")
        outside_uuid = self._create_preprocess_file(filename="outside_preprocess")

        response = self.client.post(
            reverse("pre_process", args=[preprocess_uuid]),
            data={"file_scale_map": json.dumps({outside_uuid: 0.2})},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 403)

    def test_preprocess_post_rejects_tampered_scale_revert_uuid_map(self):
        preprocess_uuid = self._create_preprocess_file(filename="tamper_revert_preprocess")
        outside_uuid = self._create_preprocess_file(filename="outside_revert_preprocess")

        response = self.client.post(
            reverse("pre_process", args=[preprocess_uuid]),
            data={"file_scale_revert_uuids": json.dumps([outside_uuid])},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 403)

    @patch(
        "core.views.pre_process.preprocess_images",
        return_value=PreprocessedImageArtifact(
            image_id="stub_image.dv",
            preprocessed_path=Path("stub_prep.png"),
            original_height=1,
            original_width=1,
        ),
    )
    @patch("core.views.pre_process.predict_images", return_value=True)
    @patch("core.views.pre_process.tif_to_jpg", return_value=None)
    def test_preprocess_post_persists_manual_scale_override_before_analysis(
        self,
        _mock_tif_to_jpg,
        _mock_predict,
        _mock_preprocess,
    ):
        preprocess_uuid = self._create_preprocess_file(filename="scale_override_preprocess")

        response = self.client.post(
            reverse("pre_process", args=[preprocess_uuid]),
            data={"file_scale_map": json.dumps({preprocess_uuid: 0.27})},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/segment/", response["Location"])
        uploaded = UploadedImage.objects.get(uuid=preprocess_uuid)
        scale_info = uploaded.scale_info or {}
        self.assertEqual(scale_info.get("source"), "manual_override")
        self.assertAlmostEqual(float(scale_info.get("effective_um_per_px", 0)), 0.27, places=6)

    @patch(
        "core.views.pre_process.preprocess_images",
        return_value=PreprocessedImageArtifact(
            image_id="stub_image.dv",
            preprocessed_path=Path("stub_prep.png"),
            original_height=1,
            original_width=1,
        ),
    )
    @patch("core.views.pre_process.predict_images", return_value=True)
    @patch("core.views.pre_process.tif_to_jpg", return_value=None)
    def test_preprocess_post_reverts_manual_override_to_metadata_scale(
        self,
        _mock_tif_to_jpg,
        _mock_predict,
        _mock_preprocess,
    ):
        preprocess_uuid = self._create_preprocess_file(filename="scale_revert_preprocess")
        uploaded = UploadedImage.objects.get(uuid=preprocess_uuid)
        uploaded.scale_info = apply_manual_override_scale(
            build_scale_info(
                manual_um_per_px=0.2,
                prefer_metadata=True,
                metadata_um_per_px=0.11,
                status="ok",
            ),
            effective_um_per_px=0.27,
        )
        uploaded.save(update_fields=["scale_info"])

        response = self.client.post(
            reverse("pre_process", args=[preprocess_uuid]),
            data={"file_scale_revert_uuids": json.dumps([preprocess_uuid])},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 302)
        uploaded.refresh_from_db()
        scale_info = uploaded.scale_info or {}
        self.assertEqual(scale_info.get("source"), "metadata")
        self.assertAlmostEqual(float(scale_info.get("effective_um_per_px", 0)), 0.11, places=6)


class ChannelVisibilityPreferenceTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="visibility@example.com",
            password="TestPass123!",
        )
        self.assertTrue(
            self.client.login(
                email="visibility@example.com",
                password="TestPass123!",
            )
        )

    def _create_saved_sidebar_file(self, filename: str = "sidebar_saved") -> str:
        file_uuid = uuid4()
        UploadedImage.objects.create(
            user=self.user,
            name=filename,
            uuid=file_uuid,
            file_location=f"{file_uuid}/{filename}.dv",
        )
        SegmentedImage.objects.create(
            user=self.user,
            UUID=file_uuid,
            file_location=f"user_{file_uuid}/{filename}.png",
            ImagePath=f"{file_uuid}/output/{filename}_frame_0.png",
            CellPairPrefix=f"{file_uuid}/segmented/cell_",
            NumCells=1,
        )
        return str(file_uuid)

    def _create_preprocess_sidebar_file(self, filename: str = "sidebar_preprocess") -> str:
        file_uuid = uuid4()
        uploaded = UploadedImage.objects.create(
            user=self.user,
            name=filename,
            uuid=file_uuid,
            file_location=f"{file_uuid}/{filename}.dv",
        )
        DVLayerTifPreview.objects.create(
            uploaded_image_uuid=uploaded,
            wavelength="DAPI",
            file_location=f"{file_uuid}/{filename}_preview.png",
        )
        return str(file_uuid)

    def test_preferences_page_renders_review_modal_and_form_review_hooks(self):
        response = self.client.get(reverse("workflow_defaults"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="workflowDefaultsNav"', html=False)
        self.assertContains(response, "Workflow Defaults")
        self.assertContains(response, 'id="pluginForm" data-review-section="plugins"', html=False)
        self.assertContains(response, 'id="advancedForm" data-review-section="advanced"', html=False)
        self.assertContains(response, 'id="savingForm" data-review-section="saving"', html=False)
        self.assertContains(response, 'data-workflow-card="plugin-required-channels"', html=False)
        self.assertContains(response, 'data-workflow-card="validation-enforcement"', html=False)
        self.assertContains(response, 'data-workflow-card="saving-preferences"', html=False)
        self.assertContains(response, 'data-workflow-card="sidebar-preferences"', html=False)
        self.assertContains(response, 'data-workflow-action-card="plugins"', html=False)
        self.assertContains(response, 'data-workflow-action-card="advanced"', html=False)
        self.assertContains(response, 'data-workflow-action-card="saving"', html=False)
        self.assertContains(response, 'id="advancedOptionalChecksNote"', html=False)
        self.assertContains(response, 'id="advancedOptionalChecksGroup"', html=False)
        self.assertContains(response, 'id="advancedManualChannelsGroup"', html=False)
        self.assertContains(response, 'id="manualRequiredChannels"', html=False)
        self.assertContains(response, 'id="advancedLayerCheckRow"', html=False)
        self.assertContains(response, 'id="advancedWavelengthCheckRow"', html=False)
        self.assertContains(response, 'id="sidebar_starts_open"', html=False)
        self.assertContains(response, 'id="prefsGfpFilterExperimentalDot"', html=False)
        self.assertNotContains(response, 'data-workflow-card="channel-requirements"', html=False)
        self.assertContains(
            response,
            "Start sidebars open on dashboard, display, and preprocess",
        )
        self.assertContains(
            response,
            "Stats-required channels always stay enforced. Manual channel requirements and all-channel enforcement are saved here and pause when this module is OFF.",
        )
        self.assertContains(
            response,
            "Require exactly four layers before preprocessing.",
        )
        self.assertContains(
            response,
            "Require DIC, Blue, Red, and Green even if not needed by selected statistics.",
        )
        self.assertContains(
            response,
            "Filter out low-confidence Green signal contours in challenging images.",
        )
        self.assertContains(
            response,
            "Utilize an alternate Red detection mode where the tool attempts to find a single contour to surround all speckles.",
        )
        self.assertContains(response, 'id="reviewChangesBackdrop"', html=False)
        self.assertContains(response, 'class="review-backdrop popup-backdrop"', html=False)
        self.assertContains(response, 'class="review-modal popup-surface"', html=False)
        self.assertContains(response, 'id="reviewKeepOld"', html=False)
        self.assertContains(response, 'id="reviewConfirmChanges"', html=False)
        self.assertContains(response, 'id="leaveUnsavedBackdrop"', html=False)
        self.assertContains(response, 'id="leaveUnsavedKeepOld"', html=False)
        self.assertContains(response, 'id="leaveUnsavedConfirmNew"', html=False)
        self.assertContains(response, 'id="leaveUnsavedListWrap"', html=False)
        self.assertContains(response, 'id="leaveUnsavedList"', html=False)
        self.assertContains(response, "Leave without saving changes?")
        self.assertContains(response, "Keep Old")
        self.assertContains(response, "Confirm Changes")
        self.assertContains(response, "Confirm New")

    def test_preferences_plugin_payload_includes_exclusive_and_dependency_fields(self):
        response = self.client.get(reverse("workflow_defaults"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"required_plugins"', html=False)
        self.assertContains(response, '"exclusive_group"', html=False)
        self.assertContains(response, '"exclusive_group": "nuclear_cellular"', html=False)

    def test_advanced_settings_override_reports_and_removes_dependent_plugins(self):
        response = self.client.post(
            reverse("workflow_defaults"),
            {
                "action": "save_advanced_settings",
                "override_required_channels": ["channel_red"],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Advanced settings saved. Removed dependent plugins:")
        for plugin_id in (
            "RedLineIntensity",
            "CENDot",
            "GreenRedIntensity",
            "NuclearCellularIntensity",
        ):
            self.assertContains(response, PLUGIN_DEFINITIONS[plugin_id].label)

        self.user.refresh_from_db()
        defaults = get_user_preferences(self.user)["experiment_defaults"]
        self.assertEqual(defaults["selected_plugins"], [])

    def test_dashboard_channel_visibility_requires_boolean(self):
        response = self.client.post(
            reverse("dashboard_channel_visibility"),
            data=json.dumps({"show_saved_file_channels": "yes"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_dashboard_scale_visibility_requires_boolean(self):
        response = self.client.post(
            reverse("dashboard_channel_visibility"),
            data=json.dumps({"show_saved_file_scales": "yes"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_dashboard_channel_visibility_persists_user_preference(self):
        response = self.client.post(
            reverse("dashboard_channel_visibility"),
            data=json.dumps({"show_saved_file_channels": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(get_user_preferences(self.user)["show_saved_file_channels"])

    def test_dashboard_scale_visibility_persists_user_preference(self):
        response = self.client.post(
            reverse("dashboard_channel_visibility"),
            data=json.dumps({"show_saved_file_scales": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(get_user_preferences(self.user)["show_saved_file_scales"])

    def test_behavior_form_persists_channel_visibility_toggle(self):
        response = self.client.post(
            reverse("workflow_defaults"),
            {
                "action": "save_behavior",
                "auto_save_experiments": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{reverse('workflow_defaults')}?section=saving")
        self.user.refresh_from_db()
        self.assertFalse(get_user_preferences(self.user)["show_saved_file_channels"])
        self.assertFalse(get_user_preferences(self.user)["show_saved_file_scales"])

    def test_behavior_form_persists_sidebar_start_preference(self):
        response = self.client.post(
            reverse("workflow_defaults"),
            {
                "action": "save_behavior",
                "auto_save_experiments": "on",
                "show_saved_file_channels": "on",
                "show_saved_file_scales": "on",
                "sidebar_starts_open": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(get_user_preferences(self.user)["sidebar_starts_open"])

    def test_behavior_form_honors_safe_next_redirect(self):
        response = self.client.post(
            reverse("workflow_defaults"),
            {
                "action": "save_behavior",
                "next": "/dashboard/",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/")

    def test_behavior_form_rejects_external_next_redirect(self):
        response = self.client.post(
            reverse("workflow_defaults"),
            {
                "action": "save_behavior",
                "next": "https://example.com/phish",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{reverse('workflow_defaults')}?section=saving")

    def test_behavior_form_disables_auto_save_when_toggle_is_off(self):
        response = self.client.post(
            reverse("workflow_defaults"),
            {
                "action": "save_behavior",
                "show_saved_file_channels": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Experiment autosave disabled. New runs will stay out of your dashboard history.",
        )

        self.user.refresh_from_db()
        preferences = get_user_preferences(self.user)
        self.assertFalse(preferences["auto_save_experiments"])
        self.assertTrue(preferences["show_saved_file_channels"])
        self.assertFalse(preferences["show_saved_file_scales"])
        self.assertFalse(should_auto_save_experiments(self.user))

    def test_behavior_form_enables_auto_save_when_toggle_is_on(self):
        existing = get_user_preferences(self.user)
        existing["auto_save_experiments"] = False
        update_user_preferences(self.user, existing)
        self.assertFalse(should_auto_save_experiments(self.user))

        response = self.client.post(
            reverse("workflow_defaults"),
            {
                "action": "save_behavior",
                "auto_save_experiments": "on",
                "show_saved_file_channels": "on",
                "show_saved_file_scales": "on",
                "sidebar_starts_open": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Experiment autosave enabled. New runs will appear on your dashboard.",
        )

        self.user.refresh_from_db()
        preferences = get_user_preferences(self.user)
        self.assertTrue(preferences["auto_save_experiments"])
        self.assertTrue(preferences["show_saved_file_channels"])
        self.assertTrue(preferences["show_saved_file_scales"])
        self.assertTrue(preferences["sidebar_starts_open"])
        self.assertTrue(should_auto_save_experiments(self.user))

    def test_dashboard_display_and_preprocess_sidebars_start_open_by_default(self):
        saved_uuid = self._create_saved_sidebar_file()
        preprocess_uuid = self._create_preprocess_sidebar_file()

        dashboard_response = self.client.get(reverse("dashboard"))
        display_response = self.client.get(reverse("display", args=[saved_uuid]))
        preprocess_response = self.client.get(reverse("pre_process", args=[preprocess_uuid]))

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(display_response.status_code, 200)
        self.assertEqual(preprocess_response.status_code, 200)
        self.assertNotContains(dashboard_response, 'class="sidebar collapsed"', html=False)
        self.assertNotContains(display_response, 'class="sidebar collapsed"', html=False)
        self.assertNotContains(preprocess_response, 'class="sidebar collapsed"', html=False)

    def test_dashboard_display_and_preprocess_sidebars_render_collapsed_when_preference_is_off(self):
        prefs = get_user_preferences(self.user)
        prefs["sidebar_starts_open"] = False
        update_user_preferences(self.user, prefs)

        saved_uuid = self._create_saved_sidebar_file(filename="sidebar_saved_closed")
        preprocess_uuid = self._create_preprocess_sidebar_file(filename="sidebar_preprocess_closed")

        dashboard_response = self.client.get(reverse("dashboard"))
        display_response = self.client.get(reverse("display", args=[saved_uuid]))
        preprocess_response = self.client.get(reverse("pre_process", args=[preprocess_uuid]))

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(display_response.status_code, 200)
        self.assertEqual(preprocess_response.status_code, 200)
        self.assertContains(dashboard_response, 'class="sidebar collapsed"', html=False)
        self.assertContains(display_response, 'class="sidebar collapsed"', html=False)
        self.assertContains(preprocess_response, 'class="sidebar collapsed"', html=False)

    def test_new_user_has_default_selected_plugins(self):
        defaults = get_user_preferences(self.user)["experiment_defaults"]
        self.assertEqual(
            defaults["selected_plugins"],
            [
                "RedLineIntensity",
                "CENDot",
                "GreenRedIntensity",
                "NuclearCellularIntensity",
            ],
        )
        self.assertEqual(defaults["puncta_line_mode"], "red_puncta")
        self.assertEqual(defaults["nuclear_cellular_mode"], "green_nucleus")

    def test_plugin_settings_form_persists_measurement_defaults(self):
        response = self.client.post(
            reverse("workflow_defaults"),
            {
                "action": "save_plugin_defaults",
                "selected_plugins": ["RedLineIntensity"],
                "red_line_width": "2.5",
                "red_line_width_unit": "um",
                "cen_dot_distance": "11.2",
                "cen_dot_distance_unit": "px",
                "cen_dot_collinearity_threshold": "77",
                "puncta_line_mode": "green_puncta",
                "nuclear_cellular_mode": "red_nucleus",
                "microns_per_pixel": "0.25",
                "use_metadata_scale": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{reverse('workflow_defaults')}?section=plugins")

        self.user.refresh_from_db()
        defaults = get_user_preferences(self.user)["experiment_defaults"]
        self.assertEqual(defaults["selected_plugins"], ["RedLineIntensity"])
        self.assertEqual(defaults["red_line_width"], 2.5)
        self.assertEqual(defaults["red_line_width_unit"], "um")
        self.assertEqual(defaults["cen_dot_distance"], 11.2)
        self.assertEqual(defaults["cen_dot_distance_unit"], "px")
        self.assertEqual(defaults["cen_dot_collinearity_threshold"], 77)
        self.assertEqual(defaults["puncta_line_mode"], "green_puncta")
        self.assertEqual(defaults["nuclear_cellular_mode"], "red_nucleus")
        self.assertEqual(defaults["microns_per_pixel"], 0.25)
        self.assertTrue(defaults["use_metadata_scale"])

    def test_advanced_settings_save_preserves_measurement_defaults(self):
        payload = get_user_preferences(self.user)
        payload["experiment_defaults"].update(
            {
                "red_line_width": 3.5,
                "red_line_width_unit": "um",
                "cen_dot_distance": 9.0,
                "cen_dot_distance_unit": "um",
                "cen_dot_collinearity_threshold": 81,
                "puncta_line_mode": "green_puncta",
                "nuclear_cellular_mode": "red_nucleus",
                "microns_per_pixel": 0.33,
                "use_metadata_scale": False,
            }
        )
        update_user_preferences(self.user, payload)

        response = self.client.post(
            reverse("workflow_defaults"),
            {
                "action": "save_advanced_settings",
                "module_enabled": "on",
                "enforce_layer_count": "on",
                "enforce_wavelengths": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{reverse('workflow_defaults')}?section=advanced")

        self.user.refresh_from_db()
        defaults = get_user_preferences(self.user)["experiment_defaults"]
        self.assertEqual(defaults["red_line_width"], 3.5)
        self.assertEqual(defaults["red_line_width_unit"], "um")
        self.assertEqual(defaults["cen_dot_distance"], 9.0)
        self.assertEqual(defaults["cen_dot_distance_unit"], "um")
        self.assertEqual(defaults["cen_dot_collinearity_threshold"], 81)
        self.assertEqual(defaults["puncta_line_mode"], "green_puncta")
        self.assertEqual(defaults["nuclear_cellular_mode"], "red_nucleus")
        self.assertEqual(defaults["microns_per_pixel"], 0.33)
        self.assertFalse(defaults["use_metadata_scale"])

    def test_advanced_settings_pauses_optional_checks_when_module_disabled(self):
        response = self.client.post(
            reverse("workflow_defaults"),
            {
                "action": "save_advanced_settings",
                "enforce_layer_count": "on",
                "enforce_wavelengths": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{reverse('workflow_defaults')}?section=advanced")

        self.user.refresh_from_db()
        defaults = get_user_preferences(self.user)["experiment_defaults"]
        self.assertFalse(defaults["module_enabled"])
        self.assertTrue(defaults["enforce_layer_count"])
        self.assertTrue(defaults["enforce_wavelengths"])

    def test_workflow_defaults_summary_marks_manual_channels_active_in_both_sections(self):
        preferences = get_user_preferences(self.user)
        preferences["experiment_defaults"]["module_enabled"] = True
        preferences["experiment_defaults"]["manual_required_channels"] = ["channel_blue"]
        update_user_preferences(self.user, preferences)

        response = self.client.get(reverse("workflow_defaults"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertEqual(content.count(">Required manually<"), 2)
        self.assertIn('data-req-row="channel_blue" data-summary-scope="plugins"', content)
        self.assertIn('data-req-row="channel_blue" data-summary-scope="advanced"', content)

    def test_workflow_defaults_summary_marks_manual_channels_paused_in_both_sections(self):
        preferences = get_user_preferences(self.user)
        preferences["experiment_defaults"]["module_enabled"] = False
        preferences["experiment_defaults"]["manual_required_channels"] = ["channel_blue"]
        update_user_preferences(self.user, preferences)

        response = self.client.get(reverse("workflow_defaults"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertEqual(content.count(">Paused manually<"), 2)
        self.assertContains(response, 'id="manual_channel_blue"', html=False)
        self.assertContains(response, 'value="channel_blue"', html=False)
        self.assertContains(response, 'data-channel="channel_blue"', html=False)
        self.assertContains(response, "checked disabled", html=False)

    def test_workflow_defaults_summary_marks_paused_all_wavelengths_in_both_sections(self):
        preferences = get_user_preferences(self.user)
        preferences["experiment_defaults"]["module_enabled"] = False
        preferences["experiment_defaults"]["enforce_wavelengths"] = True
        update_user_preferences(self.user, preferences)

        response = self.client.get(reverse("workflow_defaults"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertEqual(content.count(">Paused by all-channels<"), 2)

    def test_workflow_defaults_renders_optional_validation_controls_disabled_when_module_is_off(self):
        preferences = get_user_preferences(self.user)
        preferences["experiment_defaults"]["module_enabled"] = False
        preferences["experiment_defaults"]["enforce_layer_count"] = True
        preferences["experiment_defaults"]["enforce_wavelengths"] = True
        preferences["experiment_defaults"]["manual_required_channels"] = ["channel_blue"]
        update_user_preferences(self.user, preferences)

        response = self.client.get(reverse("workflow_defaults"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="advancedOptionalChecksGroup"', html=False)
        self.assertContains(response, 'id="enforce_layer_count" checked disabled', html=False)
        self.assertContains(response, 'id="enforce_wavelengths" checked disabled', html=False)
        self.assertContains(response, 'id="manual_channel_blue"', html=False)
        self.assertContains(response, 'value="channel_blue"', html=False)
        self.assertContains(response, 'data-channel="channel_blue"', html=False)
        self.assertContains(response, "checked disabled", html=False)

    def test_advanced_settings_save_preserves_manual_required_channels_when_module_is_off(self):
        response = self.client.post(
            reverse("workflow_defaults"),
            {
                "action": "save_advanced_settings",
                "enforce_layer_count": "1",
                "manual_required_channels": ["channel_blue"],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{reverse('workflow_defaults')}?section=advanced")

        self.user.refresh_from_db()
        defaults = get_user_preferences(self.user)["experiment_defaults"]
        self.assertFalse(defaults["module_enabled"])
        self.assertTrue(defaults["enforce_layer_count"])
        self.assertFalse(defaults["enforce_wavelengths"])
        self.assertEqual(defaults["manual_required_channels"], ["channel_blue"])

        response = self.client.get(reverse("workflow_defaults"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertEqual(content.count(">Paused manually<"), 2)

