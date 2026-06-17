from __future__ import annotations

import shutil
import subprocess

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .frontend_contract_helpers import CORE_STATIC_ROOT, assert_in_order, create_display_file, login_user, response_text, static_text


class FrontendJavaScriptStaticContractTests(SimpleTestCase):
    def test_static_javascript_passes_node_syntax_check_when_node_is_available(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not available for static JavaScript syntax checks.")

        for js_path in (CORE_STATIC_ROOT / "js").rglob("*.js"):
            with self.subTest(js=js_path.relative_to(CORE_STATIC_ROOT)):
                result = subprocess.run(
                    [node, "--check", str(js_path)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_expected_window_globals_are_defined_by_their_owner_files(self):
        owner_contracts = {
            "js/export_selection_modal.js": "window.CytoCVExportSelection =",
            "js/viewer_overlay_prefetch.js": "window.CytoCVOverlayPrefetch =",
            "js/shared/async-progress.js": "window.CytoCVAsyncProgress =",
            "js/shared/base-interactions.js": "window.showGlobalMessage =",
            "js/shared/results-viewer.js": "global.CytoCVResultsViewerShared =",
            "js/shared/results-cell-actions.js": "global.CytoCVResultsCellActions =",
        }

        for path, marker in owner_contracts.items():
            with self.subTest(path=path):
                self.assertIn(marker, static_text(path))

    def test_results_viewer_shared_namespace_exposes_documented_helpers(self):
        source = static_text("js/shared/results-viewer.js")
        for helper_name in (
            "readJsonConfig",
            "createBlendHelpers",
            "preloadImageSet",
            "getSortedCellIds",
            "getCircularWarmQueue",
            "normalizeMainImageChannel",
            "createMainImageHelpers",
            "createStatisticsHelpers",
        ):
            with self.subTest(helper=helper_name):
                self.assertIn(helper_name, source)

    def test_spatial_unit_control_binding_is_shared(self):
        shared_source = static_text("js/shared/results-viewer.js")
        display_source = static_text("js/pages/display-viewer.js")
        dashboard_source = static_text("js/pages/dashboard-viewer.js")

        self.assertIn("function bindSpatialUnitControls", shared_source)
        self.assertIn("[data-spatial-unit-toggle]", shared_source)
        self.assertIn("bindSpatialUnitControls({", display_source)
        self.assertIn("bindSpatialUnitControls({", dashboard_source)
        self.assertNotIn("const sidebarSpatialUnitToggle", display_source)
        self.assertNotIn("const sidebarSpatialUnitToggle", dashboard_source)

    def test_dashboard_quota_fill_width_is_applied_from_data_attribute(self):
        source = static_text("js/pages/dashboard-viewer.js")
        self.assertIn(".quota-fill[data-quota-fill-width]", source)
        self.assertIn("dataset.quotaFillWidth", source)
        self.assertIn("--quota-fill-width", source)
        self.assertIn("`${quotaFillWidth}%`", source)


class FrontendJavaScriptRenderedOrderTests(TestCase):
    def test_dashboard_and_display_load_shared_globals_before_consumers(self):
        user = login_user(self, "frontend-js-order@example.com")
        uuid_value = create_display_file(uploaded_owner=user, filename="js_order")

        for route_name, page_script, page_cell_script in (
            ("dashboard", "js/pages/dashboard-viewer.js", "js/pages/dashboard-cell-actions.js"),
            ("display", "js/pages/display-viewer.js", "js/pages/display-cell-actions.js"),
        ):
            with self.subTest(route=route_name):
                url = reverse(route_name, args=[uuid_value]) if route_name == "display" else reverse(route_name)
                content = response_text(self.client.get(url))
                assert_in_order(self, content, "js/shared/results-viewer.js", page_script)
                assert_in_order(self, content, "js/shared/results-cell-actions.js", page_cell_script)
                assert_in_order(self, content, "js/export_selection_modal.js", page_script)
                assert_in_order(self, content, "js/viewer_overlay_prefetch.js", page_script)

    def test_base_global_scripts_are_included_on_dynamic_pages(self):
        login_user(self, "frontend-base-js@example.com")
        content = response_text(self.client.get(reverse("experiment")))
        self.assertIn("js/shared/async-progress.js", content)
        self.assertIn("js/shared/base-interactions.js", content)
        self.assertIn("js/pages/experiment.js", content)
