"""Protect server-rendered JSON script payload shapes consumed by frontend code."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from .frontend_contract_helpers import (
    add_cell_stat,
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
            num_cells=1,
        )
        add_cell_stat(saved_uuid, cell_id=1)
        add_cell_stat(transient_uuid, cell_id=1)
        set_transient_uuids(self.client, [transient_uuid])

        display_response = self.client.get(reverse("display", args=[transient_uuid]))
        display_content = response_text(display_response)
        display_files = parse_json_script(display_content, "displayFilesData")
        self.assertIsInstance(display_files, dict)
        display_file = display_files[transient_uuid]
        expected_file_keys = {
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
        self.assertEqual(set(display_file.keys()), expected_file_keys)
        self.assertEqual(display_file["NumberOfCells"], 1)
        self.assertEqual(list(display_file["CellPairImages"].keys()), ["1"])
        self.assertEqual(
            display_file["CellPairImages"]["1"],
            [
                f"/media/{transient_uuid}/segmented/json_transient-0-1.png",
                f"/media/{transient_uuid}/segmented/json_transient-0-1-no_outline.png",
                f"/media/{transient_uuid}/segmented/json_transient-1-1.png",
                f"/media/{transient_uuid}/segmented/json_transient-1-1-no_outline.png",
                f"/media/{transient_uuid}/segmented/json_transient-3-1.png",
                f"/media/{transient_uuid}/segmented/json_transient-3-1-no_outline.png",
                f"/media/{transient_uuid}/segmented/json_transient-2-1.png",
                f"/media/{transient_uuid}/segmented/json_transient-2-1-no_outline.png",
            ],
        )
        self.assertEqual(list(display_file["Statistics"].keys()), ["1"])
        self.assertEqual(display_file["Statistics"]["1"]["cell_type"], "unknown")
        self.assertEqual(display_file["Statistics"]["1"]["cell_type_label"], "Unknown")
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
                "initialCellTypeFilter",
                "tableFileUuid",
            ),
        )
        self.assertIsInstance(display_config["confirmCellDeletion"], bool)
        display_export_config = parse_json_script(display_content, "exportSelectionConfig")
        self.assertIsInstance(display_export_config, dict)
        self.assertContourIntensityExportMetadata(display_export_config)

        dashboard_response = self.client.get(reverse("dashboard") + f"?file_uuid={saved_uuid}")
        dashboard_content = response_text(dashboard_response)
        dashboard_files = parse_json_script(dashboard_content, "dashboardFilesData")
        self.assertIsInstance(dashboard_files, dict)
        dashboard_file = dashboard_files[saved_uuid]
        self.assertEqual(set(dashboard_file.keys()), expected_file_keys)
        self.assertEqual(dashboard_file["NumberOfCells"], 1)
        self.assertEqual(list(dashboard_file["CellPairImages"].keys()), ["1"])
        self.assertEqual(len(dashboard_file["CellPairImages"]["1"]), 8)
        self.assertEqual(list(dashboard_file["Statistics"].keys()), ["1"])
        self.assertEqual(dashboard_file["Statistics"]["1"]["cell_type"], "unknown")
        self.assertEqual(dashboard_file["Statistics"]["1"]["cell_type_label"], "Unknown")
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
                "initialCellTypeFilter",
                "tableFileUuid",
            ),
        )
        self.assertIsInstance(dashboard_config["hasFiles"], bool)
        dashboard_export_config = parse_json_script(dashboard_content, "exportSelectionConfig")
        self.assertIsInstance(dashboard_export_config, dict)
        self.assertContourIntensityExportMetadata(dashboard_export_config)

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

    def assertContourIntensityExportMetadata(self, config):
        items = config["items"]
        intensity_items = [
            item for item in items if item.get("family") == "contour_intensity"
        ]
        self.assertEqual(len(intensity_items), 36)
        fields = {item["tableField"]: item for item in intensity_items}
        self.assertEqual(
            fields["red_in_red_total_intensity_1"]["combination"],
            "red_in_red",
        )
        self.assertEqual(fields["red_in_red_total_intensity_1"]["statistic"], "total")
        self.assertEqual(fields["red_in_red_total_intensity_1"]["slot"], 1)
        self.assertEqual(
            fields["green_in_green_average_intensity_3"]["combination"],
            "green_in_green",
        )
        self.assertEqual(
            fields["green_in_green_average_intensity_3"]["statistic"],
            "average",
        )
        self.assertEqual(fields["green_in_green_average_intensity_3"]["slot"], 3)
        self.assertNotEqual(
            next(item for item in items if item["tableField"] == "puncta_distance").get("family"),
            "contour_intensity",
        )
