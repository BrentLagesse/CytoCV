"""Tests for account preference and account-area safeguards."""

from __future__ import annotations

import json
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.preferences import (
    get_user_preferences,
    normalize_preferences_payload,
    update_user_preferences,
)
from core.models import SegmentedImage, UploadedImage


class PreferenceNormalizationTests(TestCase):
    def test_default_payload_uses_expected_plugin_defaults(self):
        normalized = normalize_preferences_payload({})
        defaults = normalized["experiment_defaults"]
        self.assertEqual(
            defaults["selected_plugins"],
            [
                "MCherryLine",
                "GFPDot",
                "GreenRedIntensity",
                "NuclearCellularIntensity",
            ],
        )
        self.assertEqual(defaults["nuclear_cellular_mode"], "green_nucleus")

    def test_normalize_preferences_filters_invalid_values(self):
        normalized = normalize_preferences_payload(
            {
                "experiment_defaults": {
                    "selected_plugins": ["MCherryLine", "Unknown"],
                    "module_enabled": "true",
                    "enforce_layer_count": "true",
                    "enforce_wavelengths": "false",
                    "manual_required_channels": ["DIC", "BAD"],
                    "mcherry_width": "-5",
                    "gfp_distance": "abc",
                    "gfp_threshold": "-1",
                    "nuclear_cellular_mode": "bad_mode",
                    "mcherry_width_unit": "um",
                    "gfp_distance_unit": "px",
                    "microns_per_pixel": "0",
                },
                "auto_save_experiments": "off",
            }
        )

        defaults = normalized["experiment_defaults"]
        self.assertEqual(defaults["selected_plugins"], ["MCherryLine"])
        self.assertTrue(defaults["module_enabled"])
        self.assertTrue(defaults["enforce_layer_count"])
        self.assertFalse(defaults["enforce_wavelengths"])
        self.assertEqual(defaults["manual_required_channels"], ["DIC"])
        self.assertEqual(defaults["mcherry_width"], 1)
        self.assertEqual(defaults["gfp_distance"], 37)
        self.assertEqual(defaults["gfp_threshold"], 66)
        self.assertEqual(defaults["nuclear_cellular_mode"], "green_nucleus")
        self.assertFalse(normalized["auto_save_experiments"])
        self.assertTrue(normalized["show_saved_file_channels"])


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
        for name in ("dashboard", "account_settings", "preferences"):
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
        self.assertEqual(response["Location"], reverse("homepage"))
        self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())


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

    def test_dashboard_channel_visibility_requires_boolean(self):
        response = self.client.post(
            reverse("dashboard_channel_visibility"),
            data=json.dumps({"show_saved_file_channels": "yes"}),
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

    def test_behavior_form_persists_channel_visibility_toggle(self):
        response = self.client.post(
            reverse("preferences"),
            {
                "action": "save_behavior",
                "auto_save_experiments": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(get_user_preferences(self.user)["show_saved_file_channels"])

    def test_new_user_has_default_selected_plugins(self):
        defaults = get_user_preferences(self.user)["experiment_defaults"]
        self.assertEqual(
            defaults["selected_plugins"],
            [
                "MCherryLine",
                "GFPDot",
                "GreenRedIntensity",
                "NuclearCellularIntensity",
            ],
        )
        self.assertEqual(defaults["nuclear_cellular_mode"], "green_nucleus")

    def test_plugin_settings_form_persists_measurement_defaults(self):
        response = self.client.post(
            reverse("preferences"),
            {
                "action": "save_plugin_defaults",
                "selected_plugins": ["MCherryLine"],
                "mcherry_width": "2.5",
                "mcherry_width_unit": "um",
                "gfp_distance": "11.2",
                "gfp_distance_unit": "px",
                "gfp_threshold": "77",
                "nuclear_cellular_mode": "red_nucleus",
                "microns_per_pixel": "0.25",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        defaults = get_user_preferences(self.user)["experiment_defaults"]
        self.assertEqual(defaults["selected_plugins"], ["MCherryLine"])
        self.assertEqual(defaults["mcherry_width"], 2.5)
        self.assertEqual(defaults["mcherry_width_unit"], "um")
        self.assertEqual(defaults["gfp_distance"], 11.2)
        self.assertEqual(defaults["gfp_distance_unit"], "px")
        self.assertEqual(defaults["gfp_threshold"], 77)
        self.assertEqual(defaults["nuclear_cellular_mode"], "red_nucleus")
        self.assertEqual(defaults["microns_per_pixel"], 0.25)

    def test_advanced_settings_save_preserves_measurement_defaults(self):
        payload = get_user_preferences(self.user)
        payload["experiment_defaults"].update(
            {
                "mcherry_width": 3.5,
                "mcherry_width_unit": "um",
                "gfp_distance": 9.0,
                "gfp_distance_unit": "um",
                "gfp_threshold": 81,
                "nuclear_cellular_mode": "red_nucleus",
                "microns_per_pixel": 0.33,
            }
        )
        update_user_preferences(self.user, payload)

        response = self.client.post(
            reverse("preferences"),
            {
                "action": "save_advanced_settings",
                "module_enabled": "on",
                "enforce_layer_count": "on",
                "enforce_wavelengths": "on",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        defaults = get_user_preferences(self.user)["experiment_defaults"]
        self.assertEqual(defaults["mcherry_width"], 3.5)
        self.assertEqual(defaults["mcherry_width_unit"], "um")
        self.assertEqual(defaults["gfp_distance"], 9.0)
        self.assertEqual(defaults["gfp_distance_unit"], "um")
        self.assertEqual(defaults["gfp_threshold"], 81)
        self.assertEqual(defaults["nuclear_cellular_mode"], "red_nucleus")
        self.assertEqual(defaults["microns_per_pixel"], 0.33)
