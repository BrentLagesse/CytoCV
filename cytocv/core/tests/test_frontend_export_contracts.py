from __future__ import annotations

import json

from django.test import TestCase
from django.urls import reverse

from .frontend_contract_helpers import add_cell_stat, create_display_file, login_user, response_text


class FrontendExportContractTests(TestCase):
    def test_export_modal_hooks_render_once_on_display_and_dashboard(self):
        user = login_user(self, "frontend-export-hooks@example.com")
        uuid_value = create_display_file(uploaded_owner=user, filename="export_hooks")

        for route_name, url in (
            ("display", reverse("display", args=[uuid_value])),
            ("dashboard", reverse("dashboard") + f"?file_uuid={uuid_value}"),
        ):
            with self.subTest(route=route_name):
                content = response_text(self.client.get(url))
                for hook in (
                    'id="exportSelectionBackdrop"',
                    'id="exportFileSelectionView"',
                    'id="exportStatSelectionView"',
                    'id="exportFormatToggle"',
                    'id="exportSelectionConfig"',
                    'id="exportIntensityQuickSelect"',
                    'id="exportIntensityQuickSelectSummary"',
                    'id="exportIntensityQuickSelectToggle"',
                    'id="exportIntensityQuickSelectBody"',
                    'aria-controls="exportIntensityQuickSelectBody"',
                    'data-export-format="csv"',
                    'data-export-format="xlsx"',
                    'data-export-intensity-action="apply"',
                    'data-export-intensity-action="clear"',
                    'data-export-intensity-action="all"',
                    'data-export-intensity-action="totals"',
                    'data-export-intensity-action="total_max"',
                    'data-export-intensity-action="average"',
                    'data-export-intensity-action="slots_1_2"',
                ):
                    self.assertIn(hook, content)
                    self.assertEqual(content.count(hook), 1)
                for hook in (
                    'data-expanded="false"',
                    'aria-expanded="false"',
                    'id="exportIntensityQuickSelectBody" hidden',
                    "Show</button>",
                    'data-export-intensity-filter="statistic"',
                    'data-export-intensity-filter="slot"',
                    'data-export-intensity-filter="combination"',
                    "Contour Intensity Quick Select",
                    "Presets",
                    "Custom Filters",
                    "Average only",
                    "Slot 1",
                    "Slot 2",
                    "Slot 3",
                    "Red In Red",
                    "Green In Green",
                ):
                    self.assertIn(hook, content)
                self.assertIn("js/export_selection_modal.js", content)

    def test_dashboard_export_endpoint_preserves_invalid_selection_error_shape(self):
        login_user(self, "frontend-dashboard-export-invalid@example.com")

        response = self.client.post(
            reverse("dashboard_bulk_export"),
            data=json.dumps({"uuids": [], "_export": "csv", "_columns": [], "_unit": "px"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("error", payload)
        self.assertIsInstance(payload["error"], str)

    def test_display_export_endpoint_preserves_invalid_selection_error_shape(self):
        login_user(self, "frontend-display-export-invalid@example.com")

        response = self.client.post(
            reverse("display_export_files"),
            data=json.dumps({"visible_uuids": [], "uuids": [], "_export": "csv", "_columns": [], "_unit": "px"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("error", payload)
        self.assertIsInstance(payload["error"], str)

    def test_dashboard_export_valid_csv_preserves_download_response_contract(self):
        user = login_user(self, "frontend-dashboard-export-valid@example.com")
        uuid_value = create_display_file(uploaded_owner=user, filename="dashboard_export_contract")
        add_cell_stat(uuid_value)

        response = self.client.post(
            reverse("dashboard_bulk_export"),
            data=json.dumps(
                {
                    "uuids": [uuid_value],
                    "_export": "csv",
                    "_columns": ["red_in_red_total_intensity_1"],
                    "_unit": "px",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("cytocv_", response["Content-Disposition"])
        self.assertIn("Red In Red Total Intensity 1", response.content.decode("utf-8"))

    def test_display_export_valid_csv_preserves_download_response_contract(self):
        user = login_user(self, "frontend-display-export-valid@example.com")
        uuid_value = create_display_file(uploaded_owner=user, filename="display_export_contract")
        add_cell_stat(uuid_value)

        response = self.client.post(
            reverse("display_export_files"),
            data=json.dumps(
                {
                    "visible_uuids": [uuid_value],
                    "uuids": [uuid_value],
                    "_export": "csv",
                    "_columns": ["red_in_red_total_intensity_1"],
                    "_unit": "px",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("cytocv_", response["Content-Disposition"])
        self.assertIn("Red In Red Total Intensity 1", response.content.decode("utf-8"))

    def test_display_export_preserves_visible_subset_order(self):
        user = login_user(self, "frontend-display-export-order@example.com")
        first_uuid = create_display_file(uploaded_owner=user, filename="display_export_first")
        second_uuid = create_display_file(uploaded_owner=user, filename="display_export_second")
        add_cell_stat(first_uuid)
        add_cell_stat(second_uuid)

        response = self.client.post(
            reverse("display_export_files"),
            data=json.dumps(
                {
                    "visible_uuids": [second_uuid, first_uuid],
                    "uuids": [first_uuid, second_uuid],
                    "_export": "csv",
                    "_columns": ["red_in_red_total_intensity_1"],
                    "_unit": "px",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertLess(
            content.index("display_export_second"),
            content.index("display_export_first"),
        )

    def test_dashboard_export_preserves_selected_uuid_order(self):
        user = login_user(self, "frontend-dashboard-export-order@example.com")
        first_uuid = create_display_file(uploaded_owner=user, filename="dashboard_export_first")
        second_uuid = create_display_file(uploaded_owner=user, filename="dashboard_export_second")
        add_cell_stat(first_uuid)
        add_cell_stat(second_uuid)

        response = self.client.post(
            reverse("dashboard_bulk_export"),
            data=json.dumps(
                {
                    "uuids": [second_uuid, first_uuid],
                    "_export": "csv",
                    "_columns": ["red_in_red_total_intensity_1"],
                    "_unit": "px",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertLess(
            content.index("dashboard_export_second"),
            content.index("dashboard_export_first"),
        )
