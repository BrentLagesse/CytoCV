from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from .frontend_contract_helpers import (
    assert_json_script_keys,
    create_display_file,
    create_preprocess_file,
    guest_user_id,
    login_user,
    parse_json_script,
    response_text,
    set_transient_uuids,
)


class FrontendJsonContractTests(TestCase):
    def test_experiment_upload_json_contracts_parse_and_expose_endpoint_urls(self):
        login_user(self, "frontend-json-upload@example.com")
        response = self.client.get(reverse("experiment"))
        content = response_text(response)

        config = assert_json_script_keys(
            self,
            content,
            "uploadPreparationConfig",
            ("batch_target_bytes", "execution_mode", "workflow_defaults_url", "upload_batch_url", "upload_prepare_url"),
        )
        self.assertIsInstance(config["batch_target_bytes"], int)
        self.assertIn(config["execution_mode"], {"worker", "sync"})
        self.assertEqual(config["workflow_defaults_url"], reverse("experiment_workflow_defaults"))
        self.assertEqual(config["upload_batch_url"], reverse("experiment_upload_batch"))
        self.assertEqual(config["upload_prepare_url"], reverse("experiment_upload_prepare"))

        for script_id in (
            "statsPluginPayload",
            "restoredQueuePayload",
            "serverPreferenceDefaults",
            "uploadQuotaProjection",
            "uploadAccessPolicy",
            "uploadResumePayload",
        ):
            with self.subTest(script_id=script_id):
                self.assertIsNotNone(parse_json_script(content, script_id))

    def test_workflow_defaults_json_contract_parses(self):
        login_user(self, "frontend-json-workflow@example.com")
        response = self.client.get(reverse("workflow_defaults"))
        payload = parse_json_script(response_text(response), "pluginDependencyPayload")
        self.assertIsInstance(payload, dict)

    def test_preprocess_json_contracts_expose_navigation_and_progress_context(self):
        user = login_user(self, "frontend-json-preprocess@example.com")
        uuid_value = create_preprocess_file(user)
        response = self.client.get(reverse("pre_process", args=[uuid_value]))
        content = response_text(response)

        scale_payload = parse_json_script(content, "preprocessScalePayload")
        self.assertIsInstance(scale_payload, dict)
        config = assert_json_script_keys(
            self,
            content,
            "preprocessPageConfig",
            (
                "currentFileIndex",
                "totalFiles",
                "defaultSpatialStatsUnit",
                "initialSidebarSpatialStatsUnit",
                "uuids",
                "experimentUrl",
                "analysisExecutionMode",
                "hasSelectedStats",
            ),
        )
        self.assertIsInstance(config["currentFileIndex"], int)
        self.assertIsInstance(config["totalFiles"], int)
        self.assertEqual(config["experimentUrl"], reverse("experiment"))
        self.assertIsInstance(config["hasSelectedStats"], bool)

    def test_display_dashboard_and_export_json_contracts_parse(self):
        user = login_user(self, "frontend-json-viewers@example.com")
        saved_uuid = create_display_file(uploaded_owner=user, filename="json_saved")
        transient_uuid = create_display_file(
            uploaded_owner=user,
            segmented_owner_id=guest_user_id(),
            filename="json_transient",
        )
        set_transient_uuids(self.client, [transient_uuid])

        display_response = self.client.get(reverse("display", args=[transient_uuid]))
        display_content = response_text(display_response)
        self.assertIsInstance(parse_json_script(display_content, "displayFilesData"), dict)
        display_config = assert_json_script_keys(
            self,
            display_content,
            "displayPageConfig",
            (
                "confirmCellDeletion",
                "confirmMultiCellDeletion",
                "defaultSpatialStatsUnit",
                "initialSidebarSpatialStatsUnit",
                "initialPreferredMainImageChannel",
                "tableFileUuid",
            ),
        )
        self.assertIsInstance(display_config["confirmCellDeletion"], bool)
        self.assertIsInstance(parse_json_script(display_content, "exportSelectionConfig"), dict)

        dashboard_response = self.client.get(reverse("dashboard") + f"?file_uuid={saved_uuid}")
        dashboard_content = response_text(dashboard_response)
        self.assertIsInstance(parse_json_script(dashboard_content, "dashboardFilesData"), dict)
        dashboard_config = assert_json_script_keys(
            self,
            dashboard_content,
            "dashboardPageConfig",
            (
                "confirmCellDeletion",
                "confirmMultiCellDeletion",
                "hasFiles",
                "defaultSpatialStatsUnit",
                "initialSidebarSpatialStatsUnit",
                "initialPreferredMainImageChannel",
                "tableFileUuid",
            ),
        )
        self.assertIsInstance(dashboard_config["hasFiles"], bool)
        self.assertIsInstance(parse_json_script(dashboard_content, "exportSelectionConfig"), dict)

    def test_account_settings_json_contract_parses(self):
        login_user(self, "frontend-json-account@example.com")
        response = self.client.get(reverse("account_settings"))
        payload = assert_json_script_keys(
            self,
            response_text(response),
            "accountSettingsConfig",
            ("openDeleteModal",),
        )
        self.assertIsInstance(payload["openDeleteModal"], bool)
