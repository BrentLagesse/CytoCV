from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from .frontend_contract_helpers import (
    add_cell_stat,
    assert_in_order,
    create_display_file,
    guest_user_id,
    login_user,
    response_text,
    set_transient_uuids,
    static_text,
)


class FrontendViewerContractTests(TestCase):
    def test_display_transient_viewer_preserves_page_owned_controls_and_load_order(self):
        user = login_user(self, "frontend-display-contract@example.com")
        uuid_value = create_display_file(
            uploaded_owner=user,
            segmented_owner_id=guest_user_id(),
            filename="display_contract",
        )
        add_cell_stat(uuid_value)
        set_transient_uuids(self.client, [uuid_value])

        response = self.client.get(reverse("display", args=[uuid_value]))
        content = response_text(response)

        self.assertEqual(response.status_code, 200)
        assert_in_order(self, content, "css/components/results-viewer.css", "css/pages/display.css")
        assert_in_order(self, content, "js/shared/results-viewer.js", "js/pages/display-viewer.js")
        assert_in_order(self, content, "js/shared/results-cell-actions.js", "js/pages/display-cell-actions.js")
        for hook in (
            'id="viewerPanel"',
            'id="mainChannelSwitcher"',
            'id="statsTablePanel"',
            'id="celltable"',
            'id="saveSelectedBtn"',
            'id="saveFilesBackdrop"',
            'id="selectCellsBackdrop"',
            'id="exportSelectionBackdrop"',
            'data-action="select-cells"',
            'onclick="previousCell()"',
            'onclick="nextCell()"',
        ):
            with self.subTest(hook=hook):
                self.assertIn(hook, content)

    def test_dashboard_saved_viewer_preserves_page_owned_controls_and_load_order(self):
        user = login_user(self, "frontend-dashboard-contract@example.com")
        uuid_value = create_display_file(uploaded_owner=user, filename="dashboard_contract")
        add_cell_stat(uuid_value)

        response = self.client.get(reverse("dashboard") + f"?file_uuid={uuid_value}")
        content = response_text(response)

        self.assertEqual(response.status_code, 200)
        assert_in_order(self, content, "css/components/results-viewer.css", "css/pages/dashboard.css")
        assert_in_order(self, content, "js/shared/results-viewer.js", "js/pages/dashboard-viewer.js")
        assert_in_order(self, content, "js/shared/results-cell-actions.js", "js/pages/dashboard-cell-actions.js")
        for hook in (
            'id="viewerPanel"',
            'id="mainChannelSwitcher"',
            'id="statsTablePanel"',
            'id="celltable"',
            'id="deleteSelectedBtn"',
            'id="deleteFilesBackdrop"',
            'id="selectCellsBackdrop"',
            'id="exportSelectionBackdrop"',
            'id="previousCellBtn"',
            'id="nextCellBtn"',
            'data-action="select-cells"',
        ):
            with self.subTest(hook=hook):
                self.assertIn(hook, content)
        self.assertNotIn('onclick="previousCell()"', content)
        self.assertNotIn('onclick="nextCell()"', content)

    def test_dashboard_empty_state_remains_rendered_without_saved_files(self):
        login_user(self, "frontend-dashboard-empty@example.com")

        response = self.client.get(reverse("dashboard"))
        content = response_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn('class="empty-dashboard"', content)
        self.assertIn("No files saved", content)
        self.assertIn('id="dashboardPageConfig"', content)

    def test_cell_action_page_wrappers_remain_thin_shared_controller_initializers(self):
        dashboard_wrapper = static_text("js/pages/dashboard-cell-actions.js")
        display_wrapper = static_text("js/pages/display-cell-actions.js")

        self.assertIn("window.CytoCVResultsCellActions.init", dashboard_wrapper)
        self.assertIn("window.CytoCVDashboardPageConfig", dashboard_wrapper)
        self.assertNotIn("fetch(", dashboard_wrapper)
        self.assertNotIn("querySelector", dashboard_wrapper)

        self.assertIn("window.CytoCVResultsCellActions.init", display_wrapper)
        self.assertIn("window.CytoCVDisplayPageConfig", display_wrapper)
        self.assertNotIn("fetch(", display_wrapper)
        self.assertNotIn("querySelector", display_wrapper)

    def test_remaining_viewer_navigation_contracts_stay_page_owned(self):
        display_source = static_text("js/pages/display-viewer.js")
        dashboard_source = static_text("js/pages/dashboard-viewer.js")

        self.assertIn("async function previousCell()", display_source)
        self.assertIn("async function nextCell()", display_source)
        self.assertNotIn('onclick="previousCell()"', dashboard_source)
        self.assertNotIn('onclick="nextCell()"', dashboard_source)

    def test_cell_pair_image_loading_state_is_image_only_for_cell_transitions(self):
        shared_source = static_text("js/shared/results-viewer.js")
        display_source = static_text("js/pages/display-viewer.js")
        dashboard_source = static_text("js/pages/dashboard-viewer.js")

        self.assertIn("function setCellPairImagesLoading", shared_source)
        self.assertIn("querySelectorAll('[data-cell-image-frame]')", shared_source)
        self.assertIn("is-cell-image-loading", shared_source)

        for page_name, source in (("display", display_source), ("dashboard", dashboard_source)):
            with self.subTest(page=page_name):
                self.assertIn("setCellPairImagesLoading,", source)
                self.assertIn("setCellPairImagesLoading(true)", source)
                self.assertIn("setCellPairImagesLoading(false)", source)
                self.assertEqual(source.count("imageLoading: true"), 4)
                self.assertEqual(source.count("imageLoading: options.imageLoading === true"), 2)
                file_swap_start = source.index("setFileSwapLoading(true, requestToken)")
                file_swap_end = source.index("setFileSwapLoading(false, requestToken)", file_swap_start)
                self.assertNotIn("imageLoading: true", source[file_swap_start:file_swap_end])
