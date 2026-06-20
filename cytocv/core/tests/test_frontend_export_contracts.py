from __future__ import annotations

import json
import re

from django.test import TestCase
from django.urls import reverse

from .frontend_contract_helpers import (
    add_cell_stat,
    assert_in_order,
    create_display_file,
    login_user,
    response_text,
)


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
                    'id="exportIntensityFilterStatus"',
                    'id="exportIntensityQuickSelectBody"',
                    'class="export-selection-workspace"',
                    'class="export-quick-select-sidebar"',
                    'class="export-stat-list-panel"',
                    'class="selection-info-dot info-dot compact export-intensity-info-dot"',
                    'class="export-intensity-module export-intensity-presets-module"',
                    'class="export-intensity-module export-intensity-custom-module"',
                    'data-export-format="csv"',
                    'data-export-format="xlsx"',
                    'data-export-intensity-action="apply"',
                    'data-export-intensity-action="reset"',
                    'data-export-intensity-action="clear"',
                    'data-export-intensity-action="all"',
                    'data-export-intensity-action="totals"',
                    'data-export-intensity-action="total_max"',
                    'data-export-intensity-action="average"',
                    'data-export-intensity-action="slots_1_2"',
                    'class="export-spatial-unit-control"',
                    'class="spatial-unit-track export-spatial-unit-toggle"',
                    'aria-label="Download spatial units"',
                ):
                    self.assertIn(hook, content)
                    self.assertEqual(content.count(hook), 1)
                for hook in (
                    'data-export-intensity-filter="statistic"',
                    'data-export-intensity-filter="slot"',
                    'data-export-intensity-filter="combination"',
                    "Quick Select",
                    "0 filters applied",
                    "Quick Select helps you choose contour-intensity columns for CSV or Excel downloads",
                    "It does not rerun analysis, change the saved results, or change the table itself",
                    "Total is the summed signal inside the contour",
                    "Max is the brightest pixel inside the contour",
                    "Average is the mean signal inside the contour",
                    "Use Contour Slot to choose contour 1, 2, or 3",
                    "Red in Green means the red signal is measured inside the green contour",
                    "You can still manually check or uncheck individual statistics",
                    "Presets",
                    "Custom Filters",
                    "Intensity Value",
                    "Contour Slot",
                    "Signal Measured Inside Contour",
                    'class="export-intensity-filter-stack"',
                    'class="export-intensity-filter-module"',
                    "Reset changes",
                    "Apply filters",
                    "Average only",
                    "Slot 1",
                    "Slot 2",
                    "Slot 3",
                    "Red in Red",
                    "Green in Green",
                    'title="Red signal measured inside red contour"',
                    'aria-label="Green signal measured inside green contour"',
                    'class="export-selection-btn export-intensity-btn export-quick-select-reset"',
                    'class="export-selection-btn export-intensity-btn export-quick-select-apply confirm"',
                    '<span class="export-spatial-unit-label">Spatial Unit:</span>',
                    'data-spatial-unit="px" aria-pressed="false">px</button>',
                    'data-spatial-unit="um" aria-pressed="false">µm</button>',
                ):
                    self.assertIn(hook, content)
                for removed_hook in (
                    "Contour Intensity Quick Select",
                    "Quickly select contour-intensity columns by value type, contour slot, and signal/contour pairing.",
                    'id="exportIntensityQuickSelectSummary"',
                    'id="exportIntensityQuickSelectToggle"',
                    'aria-controls="exportIntensityQuickSelectBody"',
                    'data-expanded="false"',
                ):
                    self.assertNotIn(removed_hook, content)
                self.assertIn(
                    '</div>\n                        <div class="export-quick-select-actions">',
                    content,
                )
                assert_in_order(
                    self,
                    content,
                    '<span class="export-format-label">File Type:</span>',
                    '<span class="export-spatial-unit-label">Spatial Unit:</span>',
                    'id="exportSelectionCount"',
                    'class="export-selection-workspace"',
                    'class="export-quick-select-sidebar"',
                    'id="exportIntensityQuickSelect"',
                    'id="exportIntensityFilterStatus"',
                    'id="exportIntensityQuickSelectBody"',
                    'class="export-quick-select-actions"',
                    'class="export-stat-list-panel"',
                    'id="exportSelectionList"',
                )
                ids = re.findall(r'\bid="([^"]+)"', content)
                self.assertEqual(len(ids), len(set(ids)))
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
