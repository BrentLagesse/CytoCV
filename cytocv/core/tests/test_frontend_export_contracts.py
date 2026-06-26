from __future__ import annotations

import csv
import json
import re
from io import StringIO

from django.test import TestCase
from django.urls import reverse

from .frontend_contract_helpers import (
    add_cell_stat,
    assert_in_order,
    create_display_file,
    login_user,
    response_text,
    static_text,
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
                self.assertEqual(
                    content.count('class="selection-info-dot info-dot compact export-intensity-info-dot export-intensity-section-info-dot"'),
                    2,
                )
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
                    "Presets apply immediately. Clicking one changes the matching download columns and updates the Custom Filters below.",
                    "Custom Filters",
                    "Custom Filters let you choose value type, contour slot, and signal pairing. Click Apply custom filters at the bottom to update the download columns.",
                    "Intensity Value",
                    "Contour Slot",
                    "Signal Measured Inside Contour",
                    'class="export-intensity-filter-stack"',
                    'class="export-intensity-filter-module"',
                    "Reset changes",
                    "Apply custom filters",
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

    def test_export_contracts_include_puncta_source_contour_count_filter_parameter(self):
        display_source = static_text("js/pages/display-viewer.js")
        dashboard_source = static_text("js/pages/dashboard-viewer.js")
        results_source = static_text("js/shared/results-viewer.js")

        self.assertIn("displayPageConfig.initialCellTypeFilter", display_source)
        self.assertIn("dashboardPageConfig.initialCellTypeFilter", dashboard_source)
        self.assertIn(
            "displayPageConfig.initialPunctaSourceContourCountFilter",
            display_source,
        )
        self.assertIn(
            "dashboardPageConfig.initialPunctaSourceContourCountFilter",
            dashboard_source,
        )
        for source in (display_source, dashboard_source):
            with self.subTest(source=source[:20]):
                self.assertIn("_cell_type", source)
                self.assertIn("getCurrentCellTypeFilter()", source)
                self.assertIn("cellTypeFilterButton.addEventListener('click'", source)
                self.assertIn("getCellTypeFilterUiState", source)
                self.assertIn("cellTypeFilterButton.disabled = !state.enabled", source)
                self.assertIn("_puncta_source_contour_count", source)
                self.assertIn("getCurrentPunctaSourceContourCountFilter()", source)
                self.assertIn("punctaSourceContourFilterButton.addEventListener('click'", source)
                self.assertIn("getPunctaSourceContourFilterUiState", source)
                self.assertIn("punctaSourceContourFilterButton.disabled = !state.enabled", source)
                self.assertIn("syncCurrentCellToActiveContourFilter", source)
                self.assertIn("getActiveCellNavigationIds", source)
                self.assertIn("getAdjacentFilteredCellId(currentCellNumber, activeIds", source)
                self.assertIn("closest('tbody tr[data-cell-id]')", source)
                self.assertIn("prefix.textContent = 'Filtered view'", source)
                self.assertIn("separator.textContent = '\\u00b7'", source)
                self.assertIn("value.textContent = label || getCellTypeFilterLabel('all')", source)
                self.assertIn("cell-card-filter-value", source)
                self.assertIn("PUNCTA_SOURCE_FILTER_APPLY_FEEDBACK_MS = 120", source)
                self.assertIn("punctaSourceContourApplySkeletonTimer", source)
                self.assertIn("waitForPunctaSourceContourFilterApplyFeedback", source)
                self.assertIn("setPunctaSourceContourFilterSkeleton", source)
                self.assertIn("startPunctaSourceContourFilterApplyVisualState", source)
                self.assertIn("clearPunctaSourceContourFilterApplyVisualState", source)
                self.assertIn("setCellDataRegionLoading(isApplying)", source)
                self.assertIn("setPunctaSourceContourFilterApplying(true)", source)
                self.assertIn("await waitForPunctaSourceContourFilterApplyFeedback()", source)
                self.assertIn("status.textContent = 'Applying filter...'", source)
                self.assertIn("status.classList.remove('is-applying-filter')", source)
                self.assertIn("Showing ${shown} of ${counts.total} cells", source)
                self.assertNotIn("Showing ${shown} of ${counts.total} cells.", source)
                self.assertIn("getRowFilterEmptyMessage", source)
                handler_start = source.index("option.addEventListener('click', async () => {")
                handler_end = source.index("document.addEventListener('click'", handler_start)
                filter_handler = source[handler_start:handler_end]
                self.assertIn("startPunctaSourceContourFilterApplyVisualState()", filter_handler)
                self.assertIn("clearPunctaSourceContourFilterApplyVisualState()", filter_handler)
                self.assertNotIn("setFileSwapLoading", filter_handler)
                self.assertNotIn("is-file-swap-loading", filter_handler)
                self.assertNotIn("fetch(", filter_handler)
                self.assertNotIn("/dashboard/preferences/channels/", filter_handler)
                self.assertNotIn("startAnalysis", filter_handler)
                self.assertNotIn("start-analysis", filter_handler)
                self.assertNotIn(
                    "default_puncta_source_contour_count_filter",
                    source,
                )
                self.assertNotIn("Filtered view:", source)
                self.assertNotIn("Filter active:", source)
                self.assertNotIn("Viewing filtered cells only", source)
                self.assertNotIn("Counting Green source contours", source)
                self.assertNotIn("Counting Red source contours", source)
                self.assertNotIn("This cell is excluded by the current Puncta Source Contour Count filter.", source)
                self.assertNotIn("startAnalysis", source)

        self.assertIn("normalizePunctaSourceContourCountFilter", results_source)
        self.assertIn("normalizeCellTypeFilter", results_source)
        self.assertIn("matchesCellTypeFilter", results_source)
        self.assertIn("getAvailableCellTypes", results_source)
        self.assertIn("getCellTypeFilterUiState", results_source)
        self.assertIn("getPunctaSourceContourFilterUiState", results_source)
        self.assertIn("getRowFilterEmptyMessage", results_source)
        self.assertIn("No cells match the current row filters.", results_source)
        self.assertIn("No retained cells are available for this result.", results_source)
        self.assertIn("No cells match the current Cell Type Filter.", results_source)
        self.assertIn("No cells match the current source contour filter.", results_source)
        self.assertIn("matchesPunctaSourceContourCountFilter", results_source)
        self.assertIn("getPunctaSourceContourCountFilterCounts", results_source)
        self.assertIn("getPunctaSourceContourFilteredCellIds", results_source)
        self.assertIn("findNearestMatchingCellByOriginalOrder", results_source)
        self.assertIn("getAdjacentFilteredCellId", results_source)
        self.assertIn("function setCellDataRegionLoading", results_source)
        self.assertIn("querySelector('#tableScrollFrame')", results_source)
        self.assertIn("querySelectorAll('[data-ui-region=\"cell-metrics-strip\"]')", results_source)
        self.assertIn("region.classList.toggle('is-contour-filter-applying'", results_source)
        self.assertIn("region.setAttribute('aria-busy'", results_source)
        self.assertIn("tr.dataset.cellId = String(id)", results_source)
        self.assertIn("tr.classList.add('is-active-cell')", results_source)

    def test_filtered_table_delete_contract_uses_stable_cell_id(self):
        actions_source = static_text("js/shared/results-cell-actions.js")

        self.assertIn("contextMenu.dataset.cellId = String(cellId)", actions_source)
        self.assertIn("Number(contextMenu.dataset.cellId)", actions_source)
        self.assertIn("requestCellDelete({", actions_source)
        self.assertIn("syncCurrentCellToActiveContourFilter", actions_source)
        self.assertIn("updateTableState(fileUuid, fileData)", actions_source)
        self.assertNotIn("rowIndex", actions_source)

    def test_combined_export_payloads_respect_puncta_source_contour_count_row_filter(self):
        user = login_user(self, "frontend-combined-source-filter@example.com")
        first_uuid = create_display_file(uploaded_owner=user, filename="source_filter_first")
        second_uuid = create_display_file(uploaded_owner=user, filename="source_filter_second")
        source_props = {
            "signal_quantification_mode": "puncta_distance",
            "puncta_line_mode": "red_puncta",
        }
        add_cell_stat(first_uuid, cell_id=1, properties={**source_props, "puncta_source_contour_count": 1})
        add_cell_stat(first_uuid, cell_id=2, properties={**source_props, "puncta_source_contour_count": 2})
        add_cell_stat(second_uuid, cell_id=1, properties={**source_props, "puncta_source_contour_count": 1})

        for route_name, payload in (
            (
                "dashboard_bulk_export",
                {
                    "uuids": [first_uuid, second_uuid],
                    "_export": "csv",
                    "_columns": ["red_in_red_total_intensity_1"],
                    "_unit": "px",
                    "_puncta_source_contour_count": "exactly_2",
                },
            ),
            (
                "display_export_files",
                {
                    "visible_uuids": [first_uuid, second_uuid],
                    "uuids": [first_uuid, second_uuid],
                    "_export": "csv",
                    "_columns": ["red_in_red_total_intensity_1"],
                    "_unit": "px",
                    "_puncta_source_contour_count": "exactly_2",
                },
            ),
        ):
            with self.subTest(route=route_name):
                response = self.client.post(
                    reverse(route_name),
                    data=json.dumps(payload),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 200)
                csv_text = response.content.decode("utf-8")
                self.assertIn("source_filter_first", csv_text)
                self.assertIn(",2,Unknown,5.000", csv_text)
                self.assertNotIn(",1,Unknown,5.000", csv_text)
                self.assertNotIn("source_filter_second", csv_text)

    def test_combined_export_payloads_respect_cell_type_row_filter(self):
        user = login_user(self, "frontend-combined-cell-type-filter@example.com")
        uuid_value = create_display_file(uploaded_owner=user, filename="cell_type_filter")
        add_cell_stat(uuid_value, cell_id=1, properties={"cell_type": "single_cell"})
        add_cell_stat(uuid_value, cell_id=2, properties={"cell_type": "cell_pair"})

        for route_name, payload in (
            (
                "dashboard_bulk_export",
                {
                    "uuids": [uuid_value],
                    "_export": "csv",
                    "_columns": ["red_in_red_total_intensity_1"],
                    "_unit": "px",
                    "_cell_type": "single_cell",
                },
            ),
            (
                "display_export_files",
                {
                    "visible_uuids": [uuid_value],
                    "uuids": [uuid_value],
                    "_export": "csv",
                    "_columns": ["red_in_red_total_intensity_1"],
                    "_unit": "px",
                    "_cell_type": "single_cell",
                },
            ),
        ):
            with self.subTest(route=route_name):
                response = self.client.post(
                    reverse(route_name),
                    data=json.dumps(payload),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 200)
                csv_text = response.content.decode("utf-8")
                self.assertIn("Cell Type", csv_text)
                self.assertIn(",1,Single Cell,5.000", csv_text)
                self.assertNotIn(",2,Cell Pair,5.000", csv_text)

    def test_direct_exports_use_all_when_cell_type_filter_unavailable(self):
        user = login_user(self, "frontend-direct-disabled-cell-type-filter@example.com")
        uuid_value = create_display_file(uploaded_owner=user, filename="disabled_cell_type_filter")
        add_cell_stat(uuid_value, cell_id=1, properties={"cell_type": "cell_pair"})

        for url in (
            reverse("dashboard") + f"?file_uuid={uuid_value}&_export=csv&_cell_type=single_cell",
            reverse("display", args=[uuid_value]) + "?_export=csv&_cell_type=single_cell",
        ):
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 200)
                csv_text = response.content.decode("utf-8")
                rows = list(csv.reader(StringIO(csv_text)))
                self.assertEqual(
                    rows[0][:3],
                    ["Cell ID", "Cell Type", "Distance Between Red Puncta (px)"],
                )
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[1][0], "1")
                self.assertEqual(rows[1][1], "Cell Pair")
                self.assertNotIn("Single Cell", csv_text)

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
