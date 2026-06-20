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
)


RESULTS_VIEWER_CSS_VERSION = "table-skeleton-spatial-unit-20260618"
ICON_ALIGN_VERSION = "icon-align-20260610-v5"
EXPERIMENT_CSS_VERSION = "channel-label-nudge-20260610"
SCALE_REVERT_ICON_VERSION = "scale-revert-icon-20260610"
PREPROCESS_CSS_VERSION = "preprocess-channel-label-nudge-20260610"
MOJIBAKE_TOKENS = ("Âµ", "â›", "�")


class FrontendTemplateContractTests(TestCase):
    def _assert_viewer_encoding_and_stats_layout(self, content: str) -> None:
        for token in MOJIBAKE_TOKENS:
            with self.subTest(token=token):
                self.assertNotIn(token, content)
        self.assertEqual(
            content.count('data-spatial-unit="um" aria-pressed="false">µm</button>'),
            3,
        )
        self.assertIn('<span class="fullscreen-icon" aria-hidden="true">⛶</span>', content)
        assert_in_order(
            self,
            content,
            'data-ui-region="cell-metrics-top"',
            "<p class=\"metric-lead\">Reference Channel</p>",
            "<p class=\"metric-lead\">Biorientation</p>",
            "<p class=\"metric-lead\">Nucleus + Measurement</p>",
            "<p class=\"metric-lead\">CEN Dot Measurements</p>",
            "<p class=\"metric-lead\">Measurement/Contour</p>",
            'data-ui-region="cell-intensity-totals"',
            "<p class=\"metric-lead\">Red In Red Total Intensity</p>",
            "<p class=\"metric-lead\">Green In Red Total Intensity</p>",
            "<p class=\"metric-lead\">Red In Green Total Intensity</p>",
            "<p class=\"metric-lead\">Green In Green Total Intensity</p>",
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
            'data-stat-section="red_green_intensity"',
            'data-stat-section="nuclear_cell_pair_intensity"',
            'data-stat-section="cen_puncta"',
            'data-stat-section="biorientation"',
            'data-stat-row="puncta_distance"',
            'data-stat-row="cen_dot"',
        ):
            with self.subTest(hook=hook):
                self.assertIn(hook, content)

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
        self.assertIn(f"experiment.js?v={ICON_ALIGN_VERSION}", content)
        self.assertIn('id="uploadForm"', content)
        self.assertIn('id="fileInput"', content)
        self.assertIn('id="folderInput"', content)
        self.assertIn('accept=".dv,.tif,.tiff"', content)
        self.assertIn('id="uploadPreparationConfig"', content)
        self.assertIn('id="statsPluginPayload"', content)
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
        self.assertEqual(display_content.count('data-spatial-unit-toggle'), 3)
        self.assertNotIn("displaySpatialUnitToggleLegacy", display_content)
        self.assertNotIn("displaySpatialUnitToggleLegacySecondary", display_content)
        assert_in_order(
            self,
            display_content,
            'class="table-spatial-unit-control"',
            '<span class="table-spatial-unit-label">Spatial Unit:</span>',
            'class="spatial-unit-track table-spatial-unit-toggle"',
            'id="tableFullscreenBtn"',
        )
        assert_in_order(
            self,
            display_content,
            'class="skeleton-table-actions"',
            'class="skeleton-shape skeleton-table-spatial-unit"',
            'class="skeleton-shape skeleton-table-fullscreen"',
        )
        self._assert_viewer_encoding_and_stats_layout(display_content)

        dashboard_response = self.client.get(reverse("dashboard") + f"?file_uuid={saved_uuid}")
        dashboard_content = response_text(dashboard_response)
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertTemplateUsed(dashboard_response, "dashboard.html")
        self.assertIn('data-ui-region="dashboard-main-shell"', dashboard_content)
        self.assertIn(f"results-viewer.css?v={RESULTS_VIEWER_CSS_VERSION}", dashboard_content)
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
        self.assertEqual(dashboard_content.count('data-spatial-unit-toggle'), 3)
        self.assertNotIn("dashboardSpatialUnitToggleLegacy", dashboard_content)
        assert_in_order(
            self,
            dashboard_content,
            'class="table-spatial-unit-control"',
            '<span class="table-spatial-unit-label">Spatial Unit:</span>',
            'class="spatial-unit-track table-spatial-unit-toggle"',
            'id="tableFullscreenBtn"',
        )
        assert_in_order(
            self,
            dashboard_content,
            'class="skeleton-table-actions"',
            'class="skeleton-shape skeleton-table-spatial-unit"',
            'class="skeleton-shape skeleton-table-fullscreen"',
        )
        self._assert_viewer_encoding_and_stats_layout(dashboard_content)
