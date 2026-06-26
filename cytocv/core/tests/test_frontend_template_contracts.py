from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from .frontend_contract_helpers import (
    assert_in_order,
    assert_no_duplicate_include,
    assert_no_inline_styles,
    create_display_file,
    create_preprocess_file,
    guest_user_id,
    login_user,
    response_text,
    set_transient_uuids,
    static_text,
)


RESULTS_VIEWER_CSS_VERSION = "single-channel-contour-card-20260626"
RESULTS_VIEWER_JS_VERSION = "single-channel-contour-card-20260626"
PAGE_VIEWER_JS_VERSION = "single-channel-contour-card-20260626"
ICON_ALIGN_VERSION = "icon-align-20260610-v5"
EXPERIMENT_JS_VERSION = "metadata-driven-3plane-20260626"
EXPERIMENT_CSS_VERSION = "channel-label-nudge-20260610"
SCALE_REVERT_ICON_VERSION = "scale-revert-icon-20260610"
PREPROCESS_CSS_VERSION = "preprocess-channel-label-nudge-20260610"
MOJIBAKE_TOKENS = ("Ã‚Âµ", "Âµ", "Ã¢â€º", "â›¶", "ï¿½")


class FrontendTemplateContractTests(TestCase):
    def _assert_viewer_encoding_and_stats_layout(self, content: str) -> None:
        for token in MOJIBAKE_TOKENS:
            with self.subTest(token=token):
                self.assertNotIn(token, content)
        self.assertEqual(
            content.count('data-spatial-unit="um" aria-pressed="false">&micro;m</button>'),
            2,
        )
        self.assertIn('<span class="fullscreen-icon" aria-hidden="true">&#x26F6;</span>', content)
        assert_in_order(
            self,
            content,
            'data-ui-region="cell-metrics-top"',
            "<p class=\"metric-lead\">Reference Channel</p>",
            "<p class=\"metric-lead\">Nucleus + Measurement</p>",
            "<p class=\"metric-lead\">Puncta Distance</p>",
            "<p class=\"metric-lead\">Biorientation</p>",
            "<p class=\"metric-lead\">CEN Dot Measurements</p>",
            "<p class=\"metric-lead\">Measurement/Contour</p>",
            'data-ui-region="cell-intensity-totals"',
            "<p class=\"metric-lead\">Contour Intensities</p>",
        )
        for hook in (
            'id="contourStateValue"',
            'id="colinearDots"',
            'id="offAxisDots"',
            'id="nucleusContourChannel"',
            'id="measurementChannel"',
            'id="nuclearStatus"',
            'id="nucleusIntensitySum"',
            'id="cellPairIntensitySum"',
            'id="cytoplasmicIntensity"',
            'id="nuclearCytoplasmicRatio"',
            'id="distance"',
            'id="punctaLineIntensity"',
            'id="cellParentage"',
            'id="cenDot"',
            'id="measurementContourRatioFormula"',
            'id="measurementContourRatio1"',
            'id="measurementContourRatio2"',
            'id="measurementContourRatio3"',
            'id="redInRedIntensity1"',
            'id="redInRedIntensity2"',
            'id="redInRedIntensity3"',
            'id="greenInRedIntensity1"',
            'id="greenInRedIntensity2"',
            'id="greenInRedIntensity3"',
            'id="redInGreenIntensity1"',
            'id="redInGreenIntensity2"',
            'id="redInGreenIntensity3"',
            'id="greenInGreenIntensity1"',
            'id="greenInGreenIntensity2"',
            'id="greenInGreenIntensity3"',
            'data-cell-card-root',
            'data-cell-card-mode="puncta_distance"',
            'data-cell-card-detail-row',
            'data-cell-card-section="reference"',
            'data-cell-card-section="nuclear_cell_pair_intensity"',
            'data-cell-card-section="puncta_distance"',
            'data-cell-card-section="biorientation"',
            'data-cell-card-section="cen_dot"',
            'data-cell-card-section="measurement_contour"',
            'data-cell-card-section="contour_intensity"',
            'data-contour-intensity-display="total"',
            'data-contour-intensity-display="max"',
            'data-contour-intensity-display="average"',
            'data-contour-intensity-display="total" aria-pressed="true"',
            'data-contour-intensity-type-label',
            'data-contour-intensity-combination="red_in_red"',
            'data-contour-intensity-combination="green_in_red"',
            'data-contour-intensity-combination="red_in_green"',
            'data-contour-intensity-combination="green_in_green"',
            'class="contour-intensity-title-group"',
            'data-active-intensity="total"',
            'class="contour-intensity-toggle-indicator" aria-hidden="true"',
            'data-contour-intensity-label-for="redInRedIntensity1"',
            'data-contour-slot-label="Slot 1"',
            'aria-label="Red In Red Total Intensity 1"',
            '>Slot 1</span>',
            '>Ratio 1</span>',
            'class="nuclear-metric-grid"',
            'data-nuclear-metric-grid',
            'data-nuclear-metric-group="setup"',
            'data-nuclear-metric-group="intensity"',
            'data-nuclear-metric-row="nucleus-contour-source"',
            'data-nuclear-metric-row="measurement-channel"',
            'data-nuclear-metric-row="nuclear-status"',
            'data-nuclear-metric-row="nuclear-intensity"',
            'data-nuclear-metric-row="cell-pair-intensity"',
            'data-nuclear-metric-row="cytoplasmic-intensity"',
            'data-nuclear-metric-row="nuclear-cytoplasmic-ratio"',
            '<p class="nuclear-metric-group-title">Setup</p>',
            '<p class="nuclear-metric-group-title">Intensity</p>',
            'data-stat-section="red_green_intensity"',
            'data-stat-section="nuclear_cell_pair_intensity"',
            'data-stat-section="cen_dot"',
            'data-stat-section="biorientation"',
            'data-stat-row="puncta_distance"',
            'data-stat-row="cen_dot"',
        ):
            with self.subTest(hook=hook):
                self.assertIn(hook, content)
        assert_in_order(
            self,
            content,
            'data-nuclear-metric-group="setup"',
            'data-nuclear-metric-row="nucleus-contour-source"',
            'id="nucleusContourChannel"',
            'data-nuclear-metric-row="measurement-channel"',
            'id="measurementChannel"',
            'data-nuclear-metric-row="nuclear-status"',
            'id="nuclearStatus"',
            'data-nuclear-metric-group="intensity"',
            'data-nuclear-metric-row="nuclear-intensity"',
            'id="nucleusIntensitySum"',
            'data-nuclear-metric-row="cell-pair-intensity"',
            'id="cellPairIntensitySum"',
            'data-nuclear-metric-row="cytoplasmic-intensity"',
            'id="cytoplasmicIntensity"',
            'data-nuclear-metric-row="nuclear-cytoplasmic-ratio"',
            'id="nuclearCytoplasmicRatio"',
        )
        assert_in_order(
            self,
            content,
            '<div class="metric-lead-row contour-intensity-heading">',
            'class="contour-intensity-title-group"',
            "<p class=\"metric-lead\">Contour Intensities</p>",
            'aria-label="Contour Intensity Details"',
            'data-contour-intensity-type-label',
            'class="contour-intensity-toggle"',
            'data-active-intensity="total"',
            'class="contour-intensity-toggle-indicator" aria-hidden="true"',
            'data-contour-intensity-display="total"',
            'data-contour-intensity-display="max"',
            'data-contour-intensity-display="average"',
            '<div class="contour-intensity-groups">',
        )

    def test_public_pages_render_expected_static_contracts(self):
        cases = (
            ("home", "home.html", "css/pages/home.css", "js/pages/home.js"),
            ("about", "about.html", "css/pages/about.css", None),
            ("about_technical", "about_detail.html", "css/pages/about-detail.css", None),
            ("about_biology", "about_detail.html", "css/pages/about-detail.css", None),
            ("license", "license.html", "css/pages/license.css", "js/pages/license.js"),
            ("collaborators", "collaborators.html", "css/pages/collaborators.css", None),
        )

        for route_name, template_name, css_path, js_path in cases:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                content = response_text(response)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template_name)
                self.assertIn("css/base.css", content)
                self.assertIn("css/base-overrides.css", content)
                self.assertIn(css_path, content)
                if js_path:
                    self.assertIn(js_path, content)
                self.assertIn("site-footer", content)
                assert_no_duplicate_include(self, content, css_path)
                assert_no_inline_styles(self, content)

    def test_auth_pages_preserve_form_and_static_hooks(self):
        cases = (
            ("signin", "registration/signin.html", "css/pages/signin.css", "js/pages/signin-password-toggle.js"),
            ("signup", "registration/signup.html", "css/pages/signup.css", "js/pages/signup.js"),
        )

        for route_name, template_name, css_path, js_path in cases:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                content = response_text(response)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template_name)
                self.assertIn("csrfmiddlewaretoken", content)
                self.assertIn(css_path, content)
                if js_path:
                    self.assertIn(js_path, content)
                assert_no_duplicate_include(self, content, css_path)
                assert_no_inline_styles(self, content)

    def test_account_and_workflow_pages_preserve_static_and_config_hooks(self):
        login_user(self, "frontend-account@example.com")

        account_response = self.client.get(reverse("account_settings"))
        account_content = response_text(account_response)
        self.assertEqual(account_response.status_code, 200)
        self.assertTemplateUsed(account_response, "account_settings.html")
        self.assertIn("css/pages/account-settings.css", account_content)
        self.assertIn("js/pages/account-settings.js", account_content)
        self.assertIn('id="accountSettingsConfig"', account_content)

        workflow_response = self.client.get(reverse("workflow_defaults"))
        workflow_content = response_text(workflow_response)
        self.assertEqual(workflow_response.status_code, 200)
        self.assertTemplateUsed(workflow_response, "workflow_defaults.html")
        assert_in_order(
            self,
            workflow_content,
            "css/components/workflow-controls.css",
            "css/pages/workflow-defaults.css",
        )
        self.assertIn(f"workflow-controls.css?v={ICON_ALIGN_VERSION}", workflow_content)
        self.assertIn('<svg class="channel-order-action-icon is-back"', workflow_content)
        self.assertIn('<svg class="channel-order-action-icon is-reset"', workflow_content)
        self.assertIn("js/workflow_defaults.js", workflow_content)
        self.assertIn('id="pluginDependencyPayload"', workflow_content)
        self.assertIn('id="workflowDefaultsNav"', workflow_content)
        self.assertIn('data-workflow-card="plugin-defaults"', workflow_content)
        self.assertIn('data-workflow-card="result-display-defaults"', workflow_content)
        self.assertIn("Cell Detection &amp; Inclusion", workflow_content)
        cell_detection_start = workflow_content.index("Cell Detection &amp; Inclusion")
        signal_start = workflow_content.index("Signal Quantification")
        cell_detection_section = workflow_content[cell_detection_start:signal_start]
        self.assertNotIn('class="info-dot compact"', cell_detection_section)
        self.assertNotIn("plugin-title-line", cell_detection_section)
        self.assertIn("Requires: Red, Green.", cell_detection_section)
        self.assertIn(
            "Choose whether CytoCV analyzes cell pairs, single cells, or both. "
            "This affects which result rows are created during analysis. "
            "Rerun analysis to include a cell type that was previously excluded.",
            workflow_content,
        )
        self.assertNotIn(
            "Controls which detected cell objects are retained for analysis. "
            "To include a cell type that was excluded, rerun analysis with a different mode.",
            workflow_content,
        )
        self.assertIn('id="cell_inclusion_mode"', workflow_content)
        self.assertIn("Cell Inclusion Mode:", workflow_content)
        self.assertIn('class="plugin-inline is-active"', workflow_content)
        self.assertIn('class="mode-select-group plugin-measure-right"', workflow_content)
        self.assertIn(">Cell pairs only</option>", workflow_content)
        self.assertIn(">Single cells only</option>", workflow_content)
        self.assertIn(">Single cells and cell pairs</option>", workflow_content)
        self.assertIn("Puncta &amp; Contour Detection", workflow_content)
        self.assertNotIn(">Dot Detection</p>", workflow_content)
        self.assertIn('id="default_puncta_source_contour_count_filter"', workflow_content)
        self.assertIn("result-display-filter-control", workflow_content)
        self.assertIn("Result Display Defaults", workflow_content)
        self.assertIn("Default Source Contour Count Filter", workflow_content)
        self.assertIn("Include cells by default:", workflow_content)
        self.assertIn(">All cells</option>", workflow_content)
        self.assertIn(">Exactly 1 source contour</option>", workflow_content)
        self.assertIn(">Exactly 2 source contours</option>", workflow_content)
        self.assertIn(
            "Sets the default filter used when opening Display and Dashboard results. "
            "You can still change this filter on each results page.",
            workflow_content,
        )
        self.assertNotIn('data-workflow-card="result-filters"', workflow_content)
        self.assertNotIn('id="puncta_source_contour_count_filter"', workflow_content)
        plugin_defaults_section = workflow_content[
            workflow_content.index('data-workflow-card="plugin-defaults"') :
            workflow_content.index('data-workflow-card="dot-detection"')
        ]
        self.assertNotIn("Default Source Contour Count Filter", plugin_defaults_section)
        self.assertNotIn(
            'id="default_puncta_source_contour_count_filter"',
            plugin_defaults_section,
        )
        assert_in_order(
            self,
            workflow_content,
            'data-workflow-card="plugin-defaults"',
            "Cell Detection &amp; Inclusion",
            "Cell Inclusion Mode",
            "Signal Quantification",
            "Primary Mode:",
            'data-workflow-card="dot-detection"',
            "Puncta &amp; Contour Detection",
            'data-workflow-card="measurement-scale"',
        )
        assert_in_order(
            self,
            workflow_content,
            'data-workflow-card="sidebar-preferences"',
            'data-workflow-card="result-display-defaults"',
            'data-workflow-action-card="saving"',
        )
        assert_no_inline_styles(self, workflow_content)

    def test_experiment_upload_page_preserves_frontend_hooks(self):
        login_user(self, "frontend-upload@example.com")

        response = self.client.get(reverse("experiment"))
        content = response_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form/experiment.html")
        assert_in_order(
            self,
            content,
            "css/components/workflow-controls.css",
            "css/pages/experiment.css",
        )
        self.assertIn(f"workflow-controls.css?v={ICON_ALIGN_VERSION}", content)
        self.assertIn(f"experiment.css?v={EXPERIMENT_CSS_VERSION}", content)
        self.assertIn("js/pages/experiment.js", content)
        self.assertIn(f"experiment.js?v={EXPERIMENT_JS_VERSION}", content)
        self.assertIn('id="uploadForm"', content)
        self.assertIn('id="fileInput"', content)
        self.assertIn('id="folderInput"', content)
        self.assertIn('accept=".dv,.tif,.tiff"', content)
        self.assertIn('id="uploadPreparationConfig"', content)
        self.assertIn('id="statsPluginPayload"', content)
        self.assertIn('"puncta_line_modes"', content)
        self.assertIn('"red_puncta_only"', content)
        self.assertIn('"green_puncta_only"', content)
        self.assertIn('"Red Puncta Only"', content)
        self.assertIn('"Green Puncta Only"', content)
        self.assertNotIn('id="resultFiltersList"', content)
        self.assertNotIn("Result Filters", content)
        self.assertIn("Puncta &amp; Contour Detection", content)
        self.assertNotIn("Dot Detection", content)
        assert_in_order(
            self,
            content,
            'id="statsList"',
            "Puncta &amp; Contour Detection",
            "Measurement Scale",
        )
        experiment_source = static_text("js/pages/experiment.js")
        self.assertIn("renderCellDetectionInclusionModule(list);", experiment_source)
        self.assertIn("const info = buildInfoDot(CELL_INCLUSION_INFO_TEXT);", experiment_source)
        self.assertIn("cellInclusionModeSelect = buildCustomModeSelect(", experiment_source)
        self.assertIn("trigger.id = 'cellInclusionMode';", experiment_source)
        self.assertIn("prepData.append('cell_inclusion_mode'", experiment_source)
        self.assertIn(
            "Choose whether CytoCV analyzes cell pairs, single cells, or both. This affects which result rows are created during analysis. Rerun analysis to include a cell type that was previously excluded.",
            experiment_source,
        )
        self.assertNotIn("help.textContent = 'Controls which detected cell objects", experiment_source)
        assert_in_order(
            self,
            experiment_source,
            "renderCellDetectionInclusionModule(list);",
            "renderSignalQuantificationModule(list);",
        )
        assert_in_order(
            self,
            experiment_source,
            "title.textContent = 'Cell Detection & Inclusion';",
            "modeLabel.textContent = 'Cell Inclusion Mode:';",
            "title.textContent = 'Signal Quantification';",
            "modeLabel.textContent = 'Primary Mode:';",
            "punctaModeLabel.textContent = 'Puncta Source:';",
            "contourLabel.textContent = 'Red/Green Contour Intensities';",
        )
        self.assertIn('id="uploadQuotaProjection"', content)
        self.assertIn('id="saveWorkflowDefaultsBackdrop"', content)
        self.assertIn("sortablejs@1.15.0/Sortable.min.js", content)
        assert_no_inline_styles(self, content)

    def test_preprocess_page_preserves_frontend_hooks(self):
        user = login_user(self, "frontend-preprocess@example.com")
        uuid_value = create_preprocess_file(user)

        response = self.client.get(reverse("pre_process", args=[uuid_value]))
        content = response_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pre_process.html")
        self.assertIn("css/pages/pre-process.css", content)
        self.assertIn(f"pre-process.css?v={PREPROCESS_CSS_VERSION}", content)
        self.assertIn("js/pages/pre-process.js", content)
        self.assertIn(f"pre-process.js?v={SCALE_REVERT_ICON_VERSION}", content)
        self.assertIn("js/pages/pre-process-csrf.js", content)
        self.assertIn("js/pages/pre-process-bfcache.js", content)
        self.assertIn('<svg class="scale-revert-icon"', content)
        self.assertIn('<span class="scale-revert-label">Revert</span>', content)
        self.assertIn('id="toggleSidebarBtn" type="button" aria-label="Toggle sidebar"', content)
        self.assertIn('id="preprocessPageConfig"', content)
        self.assertIn('id="preprocessScalePayload"', content)
        self.assertIn("sortablejs@1.15.0/Sortable.min.js", content)
        assert_no_inline_styles(self, content)

    def test_display_and_dashboard_render_viewer_page_shells(self):
        user = login_user(self, "frontend-viewer-shell@example.com")
        saved_uuid = create_display_file(uploaded_owner=user, filename="saved_shell")
        transient_uuid = create_display_file(
            uploaded_owner=user,
            segmented_owner_id=guest_user_id(),
            filename="transient_shell",
        )
        set_transient_uuids(self.client, [transient_uuid])

        display_response = self.client.get(reverse("display", args=[transient_uuid]))
        display_content = response_text(display_response)
        self.assertEqual(display_response.status_code, 200)
        self.assertTemplateUsed(display_response, "display.html")
        self.assertIn('data-ui-region="display-main-shell"', display_content)
        self.assertIn(f"results-viewer.css?v={RESULTS_VIEWER_CSS_VERSION}", display_content)
        self.assertIn(f"results-viewer.js?v={RESULTS_VIEWER_JS_VERSION}", display_content)
        self.assertIn(f"display-viewer.js?v={PAGE_VIEWER_JS_VERSION}", display_content)
        self.assertIn('id="toggleSidebarBtn" type="button" aria-label="Toggle sidebar"', display_content)
        self.assertIn('id="displayPageConfig"', display_content)
        self.assertIn('id="displayFilesData"', display_content)
        self.assertIn('id="saveFilesBackdrop"', display_content)
        self.assertEqual(
            display_content.count('class="table-spatial-unit-control"'),
            1,
        )
        self.assertEqual(
            display_content.count('class="spatial-unit-track table-spatial-unit-toggle"'),
            1,
        )
        self.assertEqual(
            display_content.count('class="skeleton-shape skeleton-table-spatial-unit"'),
            1,
        )
        self.assertEqual(
            display_content.count('class="skeleton-shape skeleton-table-cell-type-filter"'),
            1,
        )
        self.assertEqual(
            display_content.count('class="skeleton-shape skeleton-table-source-contour-filter"'),
            1,
        )
        self.assertEqual(
            display_content.count('class="skeleton-shape skeleton-table-filter-count"'),
            1,
        )
        self.assertEqual(
            display_content.count('class="skeleton-shape skeleton-cell-filter-badge"'),
            1,
        )
        self.assertEqual(display_content.count('data-cell-image-frame'), 4)
        self.assertEqual(
            display_content.count('class="skeleton-shape cell-image-loading-skeleton"'),
            4,
        )
        for image_id in ("cellImage1", "cellImage2", "cellImage3", "cellImage4"):
            self.assertIn(f'id="{image_id}" class="cell-image"', display_content)
        self.assertEqual(display_content.count('data-spatial-unit-toggle'), 3)
        self.assertIn(">Both cells</span>", display_content)
        self.assertIn(">Both cells</button>", display_content)
        self.assertIn('id="punctaSourceContourFilterControl"', display_content)
        self.assertIn('id="punctaSourceContourFilterButton"', display_content)
        self.assertIn('id="punctaSourceContourFilterStatus" aria-live="polite"', display_content)
        self.assertEqual(display_content.count('id="cellTypeFilterControl"'), 1)
        self.assertIn('id="cellTypeFilterButton"', display_content)
        self.assertIn(">All cells</span>", display_content)
        self.assertIn(">All cells</button>", display_content)
        self.assertIn(">1 contour</button>", display_content)
        self.assertIn(">2 contours</button>", display_content)
        self.assertNotIn(">Exactly 1 source contour</button>", display_content)
        self.assertNotIn(">Exactly 2 source contours</button>", display_content)
        self.assertIn(">Only single cells</button>", display_content)
        self.assertIn(">Only cell pairs</button>", display_content)
        self.assertIn(
            "This filter only applies to cells retained during analysis. Rerun analysis with a different Cell Inclusion Mode to include excluded cell types.",
            display_content,
        )
        self.assertIn(
            'id="punctaSourceContourFilterStatus" aria-live="polite" class="table-filter-count-meta cell-card-filter-meta"',
            display_content,
        )
        self.assertEqual(display_content.count('id="punctaSourceContourCellFilterBadge"'), 1)
        self.assertEqual(display_content.count('id="punctaSourceContourActiveCellMessage"'), 1)
        self.assertIn(
            'class="cell-card-filter-badge cell-card-filter-meta" id="punctaSourceContourCellFilterBadge" aria-live="polite" hidden',
            display_content,
        )
        self.assertIn(
            'class="cell-card-filter-message cell-card-filter-warning" id="punctaSourceContourActiveCellMessage" aria-live="polite" hidden',
            display_content,
        )
        display_navigation = display_content[
            display_content.index('class="navigation-buttons"') :
            display_content.index('class="file-swap-skeleton cell-swap-skeleton"')
        ]
        self.assertNotIn("punctaSourceContourCellFilterBadge", display_navigation)
        self.assertNotIn("punctaSourceContourActiveCellMessage", display_navigation)
        self.assertEqual(display_content.count('id="punctaSourceContourFilterControl"'), 1)
        self.assertNotIn("Counting Green source contours", display_content)
        self.assertNotIn("Counting Red source contours", display_content)
        self.assertNotIn("This cell is excluded by the current Puncta Source Contour Count filter.", display_content)
        self.assertNotIn("displaySpatialUnitToggleLegacy", display_content)
        self.assertNotIn("displaySpatialUnitToggleLegacySecondary", display_content)
        assert_in_order(
            self,
            display_content,
            'class="cell-pairs-title-group"',
            '<p class="section-eyebrow">Cell Pairs</p>',
            'id="punctaSourceContourCellFilterBadge"',
            'id="punctaSourceContourActiveCellMessage"',
            'class="cell-toolbar-actions"',
            'class="navigation-buttons"',
            'id="previousCellBtn"',
            'id="nextCellBtn"',
            'class="table-filter-summary"',
            'id="punctaSourceContourFilterStatus" aria-live="polite"',
        )
        assert_in_order(
            self,
            display_content,
            'class="table-puncta-source-contour-filter"',
            'id="punctaSourceContourFilterButton"',
            'class="table-spatial-unit-control"',
            '<span class="table-spatial-unit-label">Spatial Unit:</span>',
            'class="spatial-unit-track table-spatial-unit-toggle"',
            'id="tableFullscreenBtn"',
        )
        assert_in_order(
            self,
            display_content,
            'class="skeleton-cell-header"',
            'class="skeleton-cell-title-group"',
            'class="skeleton-shape skeleton-cell-title"',
            'class="skeleton-shape skeleton-cell-filter-badge"',
            'class="skeleton-cell-actions"',
        )
        display_table_swap_skeleton = display_content[
            display_content.index('class="file-swap-skeleton table-swap-skeleton"') :
        ]
        assert_in_order(
            self,
            display_table_swap_skeleton,
            'class="skeleton-table-actions"',
            'class="skeleton-shape skeleton-table-cell-type-filter"',
            'class="skeleton-shape skeleton-table-source-contour-filter"',
            'class="skeleton-shape skeleton-table-spatial-unit"',
            'class="skeleton-shape skeleton-table-fullscreen"',
            'class="skeleton-table-filter-summary"',
            'class="skeleton-shape skeleton-table-filter-count"',
            'class="skeleton-table"',
        )
        self.assertIn('class="table-region-skeleton" aria-hidden="true"', display_content)
        self._assert_viewer_encoding_and_stats_layout(display_content)

        dashboard_response = self.client.get(reverse("dashboard") + f"?file_uuid={saved_uuid}")
        dashboard_content = response_text(dashboard_response)
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertTemplateUsed(dashboard_response, "dashboard.html")
        self.assertIn('data-ui-region="dashboard-main-shell"', dashboard_content)
        self.assertIn(f"results-viewer.css?v={RESULTS_VIEWER_CSS_VERSION}", dashboard_content)
        self.assertIn(f"results-viewer.js?v={RESULTS_VIEWER_JS_VERSION}", dashboard_content)
        self.assertIn(f"dashboard-viewer.js?v={PAGE_VIEWER_JS_VERSION}", dashboard_content)
        self.assertIn('class="table-region-skeleton" aria-hidden="true"', dashboard_content)
        self.assertIn('id="toggleSidebarBtn" type="button" aria-label="Toggle sidebar"', dashboard_content)
        self.assertIn('id="dashboardPageConfig"', dashboard_content)
        self.assertIn('id="dashboardFilesData"', dashboard_content)
        self.assertIn('id="deleteFilesBackdrop"', dashboard_content)
        self.assertEqual(
            dashboard_content.count('class="table-spatial-unit-control"'),
            1,
        )
        self.assertEqual(
            dashboard_content.count('class="spatial-unit-track table-spatial-unit-toggle"'),
            1,
        )
        self.assertEqual(
            dashboard_content.count('class="skeleton-shape skeleton-table-spatial-unit"'),
            1,
        )
        self.assertEqual(
            dashboard_content.count('class="skeleton-shape skeleton-table-cell-type-filter"'),
            1,
        )
        self.assertEqual(
            dashboard_content.count('class="skeleton-shape skeleton-table-source-contour-filter"'),
            1,
        )
        self.assertEqual(
            dashboard_content.count('class="skeleton-shape skeleton-table-filter-count"'),
            1,
        )
        self.assertEqual(
            dashboard_content.count('class="skeleton-shape skeleton-cell-filter-badge"'),
            1,
        )
        self.assertEqual(dashboard_content.count('data-cell-image-frame'), 4)
        self.assertEqual(
            dashboard_content.count('class="skeleton-shape cell-image-loading-skeleton"'),
            4,
        )
        for image_id in ("cellImage1", "cellImage2", "cellImage3", "cellImage4"):
            self.assertIn(f'id="{image_id}" class="cell-image"', dashboard_content)
        self.assertEqual(dashboard_content.count('data-spatial-unit-toggle'), 3)
        self.assertIn(">Both cells</span>", dashboard_content)
        self.assertIn(">Both cells</button>", dashboard_content)
        self.assertIn('id="punctaSourceContourFilterControl"', dashboard_content)
        self.assertIn('id="punctaSourceContourFilterButton"', dashboard_content)
        self.assertIn('id="punctaSourceContourFilterStatus" aria-live="polite"', dashboard_content)
        self.assertEqual(dashboard_content.count('id="cellTypeFilterControl"'), 1)
        self.assertIn('id="cellTypeFilterButton"', dashboard_content)
        self.assertIn(">All cells</span>", dashboard_content)
        self.assertIn(">All cells</button>", dashboard_content)
        self.assertIn(">1 contour</button>", dashboard_content)
        self.assertIn(">2 contours</button>", dashboard_content)
        self.assertNotIn(">Exactly 1 source contour</button>", dashboard_content)
        self.assertNotIn(">Exactly 2 source contours</button>", dashboard_content)
        self.assertIn(">Only single cells</button>", dashboard_content)
        self.assertIn(">Only cell pairs</button>", dashboard_content)
        self.assertIn(
            "This filter only applies to cells retained during analysis. Rerun analysis with a different Cell Inclusion Mode to include excluded cell types.",
            dashboard_content,
        )
        self.assertIn(
            'id="punctaSourceContourFilterStatus" aria-live="polite" class="table-filter-count-meta cell-card-filter-meta"',
            dashboard_content,
        )
        self.assertEqual(dashboard_content.count('id="punctaSourceContourCellFilterBadge"'), 1)
        self.assertEqual(dashboard_content.count('id="punctaSourceContourActiveCellMessage"'), 1)
        self.assertIn(
            'class="cell-card-filter-badge cell-card-filter-meta" id="punctaSourceContourCellFilterBadge" aria-live="polite" hidden',
            dashboard_content,
        )
        self.assertIn(
            'class="cell-card-filter-message cell-card-filter-warning" id="punctaSourceContourActiveCellMessage" aria-live="polite" hidden',
            dashboard_content,
        )
        dashboard_navigation = dashboard_content[
            dashboard_content.index('class="navigation-buttons"') :
            dashboard_content.index('class="file-swap-skeleton cell-swap-skeleton"')
        ]
        self.assertNotIn("punctaSourceContourCellFilterBadge", dashboard_navigation)
        self.assertNotIn("punctaSourceContourActiveCellMessage", dashboard_navigation)
        self.assertEqual(dashboard_content.count('id="punctaSourceContourFilterControl"'), 1)
        self.assertNotIn("Counting Green source contours", dashboard_content)
        self.assertNotIn("Counting Red source contours", dashboard_content)
        self.assertNotIn("This cell is excluded by the current Puncta Source Contour Count filter.", dashboard_content)
        self.assertNotIn("dashboardSpatialUnitToggleLegacy", dashboard_content)
        assert_in_order(
            self,
            dashboard_content,
            'class="cell-pairs-title-group"',
            '<p class="section-eyebrow">Cell Pairs</p>',
            'id="punctaSourceContourCellFilterBadge"',
            'id="punctaSourceContourActiveCellMessage"',
            'class="cell-toolbar-actions"',
            'class="navigation-buttons"',
            'id="previousCellBtn"',
            'id="nextCellBtn"',
            'class="table-filter-summary"',
            'id="punctaSourceContourFilterStatus" aria-live="polite"',
        )
        assert_in_order(
            self,
            dashboard_content,
            'class="table-puncta-source-contour-filter"',
            'id="punctaSourceContourFilterButton"',
            'class="table-spatial-unit-control"',
            '<span class="table-spatial-unit-label">Spatial Unit:</span>',
            'class="spatial-unit-track table-spatial-unit-toggle"',
            'id="tableFullscreenBtn"',
        )
        assert_in_order(
            self,
            dashboard_content,
            'class="skeleton-cell-header"',
            'class="skeleton-cell-title-group"',
            'class="skeleton-shape skeleton-cell-title"',
            'class="skeleton-shape skeleton-cell-filter-badge"',
            'class="skeleton-cell-actions"',
        )
        dashboard_table_swap_skeleton = dashboard_content[
            dashboard_content.index('class="file-swap-skeleton table-swap-skeleton"') :
        ]
        assert_in_order(
            self,
            dashboard_table_swap_skeleton,
            'class="skeleton-table-actions"',
            'class="skeleton-shape skeleton-table-cell-type-filter"',
            'class="skeleton-shape skeleton-table-source-contour-filter"',
            'class="skeleton-shape skeleton-table-spatial-unit"',
            'class="skeleton-shape skeleton-table-fullscreen"',
            'class="skeleton-table-filter-summary"',
            'class="skeleton-shape skeleton-table-filter-count"',
            'class="skeleton-table"',
        )
        self._assert_viewer_encoding_and_stats_layout(dashboard_content)
