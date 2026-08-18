"""Static source contracts that keep templates, CSS, and JS loadable together."""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase

from .frontend_contract_helpers import CORE_STATIC_ROOT, TEMPLATE_ROOT, static_text


STATIC_TAG_RE = re.compile(r"{%\s*static\s+[\"']([^\"']+)[\"']\s*%}")
CSS_URL_RE = re.compile(r"url\(\s*([\"']?)(.*?)\1\s*\)")


class FrontendStaticContractTests(SimpleTestCase):
    """Catch broken static references and accidental frontend encoding regressions."""

    def test_frontend_sources_do_not_contain_known_mojibake_tokens_or_bom(self):
        forbidden_tokens = ("Âµ", "â›", "�")
        for root in (TEMPLATE_ROOT, CORE_STATIC_ROOT):
            for path in root.rglob("*"):
                if path.suffix not in {".html", ".css", ".js"}:
                    continue
                raw_source = path.read_bytes()
                with self.subTest(path=path.relative_to(root), token="utf-8-bom"):
                    self.assertFalse(raw_source.startswith(b"\xef\xbb\xbf"))
                source = raw_source.decode("utf-8", errors="replace")
                for token in forbidden_tokens:
                    with self.subTest(path=path.relative_to(root), token=token):
                        self.assertNotIn(token, source)

    def test_template_static_references_exist_in_source_static_tree(self):
        for template_path in TEMPLATE_ROOT.rglob("*.html"):
            source = template_path.read_text(encoding="utf-8")
            for static_path in STATIC_TAG_RE.findall(source):
                with self.subTest(template=template_path.relative_to(TEMPLATE_ROOT), static_path=static_path):
                    self.assertTrue(
                        (CORE_STATIC_ROOT / static_path).exists(),
                        f"Missing static source file: {static_path}",
                    )

    def test_css_url_references_resolve_or_are_external(self):
        for css_path in (CORE_STATIC_ROOT / "css").rglob("*.css"):
            css_source = css_path.read_text(encoding="utf-8", errors="replace")
            for _, raw_url in CSS_URL_RE.findall(css_source):
                url = raw_url.strip()
                if not url or url.startswith(("http:", "https:", "data:", "#")):
                    continue
                url_path = url.split("?", 1)[0].split("#", 1)[0]
                if url_path.startswith("/static/"):
                    target = CORE_STATIC_ROOT / url_path.removeprefix("/static/")
                else:
                    target = (css_path.parent / url_path).resolve()
                with self.subTest(css=css_path.relative_to(CORE_STATIC_ROOT), url=url):
                    self.assertTrue(target.exists(), f"Missing CSS asset reference: {url}")

    def test_static_js_has_no_template_syntax_or_debug_markers(self):
        forbidden = ("{%", "%}", "{{", "}}", "{#", "#}", "debugger;", "console.log")
        for js_path in (CORE_STATIC_ROOT / "js").rglob("*.js"):
            source = js_path.read_text(encoding="utf-8")
            for token in forbidden:
                with self.subTest(js=js_path.relative_to(CORE_STATIC_ROOT), token=token):
                    self.assertNotIn(token, source)

    def test_frontend_sources_have_no_conflict_markers_or_inline_template_styles(self):
        for root in (TEMPLATE_ROOT, CORE_STATIC_ROOT):
            for path in root.rglob("*"):
                if path.suffix not in {".html", ".css", ".js", ".md"}:
                    continue
                source = path.read_text(encoding="utf-8", errors="replace")
                for marker in ("<<<<<<<", "=======", ">>>>>>>"):
                    with self.subTest(path=path.relative_to(root), marker=marker):
                        self.assertNotIn(marker, source)
                if path.suffix == ".html":
                    lowered = source.lower()
                    self.assertNotIn("<style", lowered)
                    self.assertNotIn("style=", lowered)

    def test_shared_component_css_owns_extracted_duplicate_rules(self):
        results_css = static_text("css/components/results-viewer.css")
        dashboard_css = static_text("css/pages/dashboard.css")
        display_css = static_text("css/pages/display.css")
        for keyframe in (
            "tableFullscreenEnter",
            "tableFullscreenExit",
            "cellSelectEnterForward",
            "cellSelectEnterBackward",
            "cellSelectExitForward",
            "cellSelectExitBackward",
            "skeletonShimmer",
        ):
            marker = f"@keyframes {keyframe}"
            with self.subTest(keyframe=keyframe):
                self.assertIn(marker, results_css)
                self.assertNotIn(marker, dashboard_css)
                self.assertNotIn(marker, display_css)
        self.assertIn("vertical-align: middle;", results_css)

        workflow_css = static_text("css/components/workflow-controls.css")
        experiment_css = static_text("css/pages/experiment.css")
        defaults_css = static_text("css/pages/workflow-defaults.css")
        for selector in (
            ".signal-mode-panel {",
            ".length-unit-caret {",
            ".channel-order-control .channel-chip {",
            ".channel-order-action-icon path {",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, workflow_css)
                self.assertNotIn(selector, experiment_css)
                self.assertNotIn(selector, defaults_css)
        self.assertIn(".channel-order-control .channel-chip-grip::before", workflow_css)
        self.assertIn("flex: 0 0 12px;", workflow_css)
        self.assertIn("height: 12px;", workflow_css)
        self.assertIn("width: 12px;", workflow_css)
        self.assertIn("display: block;", workflow_css)
        self.assertIn("line-height: 12px;", workflow_css)
        self.assertNotIn("vertical-align: text-bottom", workflow_css)
        self.assertIn(".channel-order-action-icon.is-back {", workflow_css)
        self.assertIn("transform: translateY(-0.5px);", workflow_css)
        self.assertIn("width: 7px;", workflow_css)
        self.assertIn("height: 12px;", workflow_css)
        self.assertIn(".channel-order-control .channel-chip-label {", workflow_css)
        self.assertIn(
            "box-shadow: 5px 0 0 currentColor, 0 4px 0 currentColor, 5px 4px 0 currentColor, 0 8px 0 currentColor, 5px 8px 0 currentColor;",
            workflow_css,
        )
        self.assertIn("top: 1px;", workflow_css)
        self.assertNotIn("radial-gradient(circle, currentColor 1.1px", workflow_css)
        self.assertNotIn(".channel-order-action-icon.is-back::before", workflow_css)
        self.assertNotIn(".channel-order-action-icon.is-reset::before", workflow_css)
        self.assertNotIn(".experiment-page .channel-order-control .channel-chip-grip::before", workflow_css)
        self.assertNotIn(".preprocess-page .channel-chip-grip::before", workflow_css)

        experiment_js = static_text("js/pages/experiment.js")
        self.assertIn("label.className = 'channel-chip-label';", experiment_js)
        self.assertNotIn("grip.textContent", experiment_js)

        self.assertIn(".experiment-page .channel-order-control .channel-chip-label {", experiment_css)
        self.assertNotIn(".experiment-page .channel-order-control .channel-chip-grip::before", experiment_css)
        self.assertNotIn(".experiment-page .channel-order-control .channel-chip-grip::before", defaults_css)
        self.assertIn(
            '#savingForm [data-workflow-card="result-display-defaults"] .result-display-filter-control',
            defaults_css,
        )
        self.assertRegex(
            defaults_css,
            r'#savingForm \[data-workflow-card="result-display-defaults"\] \.result-display-filter-control\s*\{[^}]*--result-display-filter-width:\s*var\(--workflow-module-control-width\);[^}]*flex:\s*0 0 var\(--result-display-filter-width\);[^}]*width:\s*var\(--result-display-filter-width\);[^}]*min-width:\s*var\(--result-display-filter-width\);[^}]*max-width:\s*var\(--result-display-filter-width\);',
        )
        self.assertRegex(
            defaults_css,
            r'#savingForm \[data-workflow-card="result-display-defaults"\] \.result-display-filter-control select,\s*#savingForm \[data-workflow-card="result-display-defaults"\] \.result-display-filter-control \.length-unit-dropdown,\s*#savingForm \[data-workflow-card="result-display-defaults"\] \.result-display-filter-control \.length-unit-trigger,\s*#savingForm \[data-workflow-card="result-display-defaults"\] \.result-display-filter-control \.length-unit-menu\s*\{[^}]*width:\s*var\(--result-display-filter-width\);[^}]*min-width:\s*var\(--result-display-filter-width\);[^}]*max-width:\s*var\(--result-display-filter-width\);',
        )
        self.assertRegex(
            defaults_css,
            r'#savingForm \[data-workflow-card="result-display-defaults"\] \.result-display-filter-control \.length-unit-trigger,\s*#savingForm \[data-workflow-card="result-display-defaults"\] \.result-display-filter-control \.length-unit-option\s*\{[^}]*white-space:\s*nowrap;',
        )

        workflow_template = (TEMPLATE_ROOT / "workflow_defaults.html").read_text(encoding="utf-8")
        for source in (experiment_js, workflow_template):
            with self.subTest(source="action-svg"):
                self.assertIn('<svg class="channel-order-action-icon is-back"', source)
                self.assertIn('<svg class="channel-order-action-icon is-reset"', source)
                self.assertIn('viewBox="0 0 12 12"', source)
                self.assertIn('<path d="M4.8 3.1 2.2 5.7l2.6 2.6"></path><path d="M2.6 5.7h4a3 3 0 1 1-1.8 5.4"></path>', source)
                self.assertIn('<path d="M9.4 5.4A3.5 3.5 0 1 0 8.3 8.5"></path><path d="M9.4 2.6v2.8H6.6"></path>', source)
                self.assertIn('aria-hidden="true" focusable="false"', source)
        self.assertIn('<span class="channel-chip-label">{{ item.label }}</span>', workflow_template)

    def test_sidebar_toggle_alignment_is_not_scrollbar_state_dependent(self):
        for css_path in (
            "css/components/results-viewer.css",
            "css/pages/pre-process.css",
        ):
            css_source = static_text(css_path)
            with self.subTest(css=css_path):
                self.assertNotRegex(css_source, r"\.sidebar\.has-scrollbar\s+\.sidebar-header")
                self.assertRegex(
                    css_source,
                    r"\.sidebar-content\s*\{[^}]*scrollbar-gutter:\s*stable;",
                )

    def test_export_selection_modal_uses_compact_sidebar_and_transparent_stat_panel(self):
        css_source = static_text("css/components/export-selection-modal.css")

        self.assertRegex(
            css_source,
            r"\.export-selection-modal\s*\{[^}]*width:\s*min\(82vw,\s*820px\);",
        )
        self.assertIn(".export-selection-workspace {", css_source)
        self.assertRegex(
            css_source,
            r"\.export-selection-workspace\s*\{[^}]*grid-template-columns:\s*minmax\(260px,\s*300px\)\s+minmax\(0,\s*1fr\);",
        )
        self.assertRegex(
            css_source,
            r"\.export-selection-status-row\s*\{[^}]*padding-bottom:\s*10px;[^}]*border-bottom:\s*1px\s+solid\s+rgba\(255,\s*255,\s*255,\s*0\.16\);",
        )
        self.assertRegex(
            css_source,
            r"\.export-selection-modal\s+\.export-selection-count\s*\{[^}]*transition:\s*color\s+0\.18s\s+ease,\s*opacity\s+140ms\s+ease;",
        )
        self.assertRegex(
            css_source,
            r"\.export-selection-modal\s+\.export-selection-count\.is-updating\s*\{[^}]*opacity:\s*0\.45;",
        )
        self.assertRegex(
            css_source,
            r'\.export-intensity-filter-status\[data-filter-state="pending"\]\s*\{[^}]*color:\s*#f0c95a;',
        )
        self.assertRegex(
            css_source,
            r"\.export-selection-btn:disabled\s*\{[^}]*opacity:\s*0\.52;[^}]*cursor:\s*not-allowed;",
        )
        self.assertRegex(
            css_source,
            r"\.export-quick-select-sidebar\s*\{[^}]*overflow:\s*hidden;",
        )
        self.assertRegex(
            css_source,
            r"\.export-stat-list-panel\s*\{[^}]*overflow-y:\s*auto;[^}]*scrollbar-gutter:\s*stable;",
        )
        self.assertRegex(
            css_source,
            r"\.export-stat-list-panel\s*\{[^}]*background:\s*transparent;[^}]*border:\s*none;",
        )
        self.assertRegex(
            css_source,
            r"\.export-intensity-quick-select\s*\{[^}]*display:\s*flex;[^}]*flex-direction:\s*column;[^}]*height:\s*100%;[^}]*overflow:\s*hidden;",
        )
        self.assertRegex(
            css_source,
            r"\.export-intensity-quick-select\s*\{[^}]*border:\s*none;[^}]*background:\s*transparent;",
        )
        self.assertRegex(
            css_source,
            r"\.export-intensity-quick-select-header\s*\{[^}]*flex:\s*0\s+0\s+auto;[^}]*border-bottom:\s*1px\s+solid\s+rgba\(255,\s*255,\s*255,\s*0\.16\);",
        )
        self.assertRegex(
            css_source,
            r"\.export-intensity-quick-select-body\s*\{[^}]*overflow-y:\s*auto;",
        )
        self.assertRegex(
            css_source,
            r"\.export-quick-select-actions\s*\{[^}]*flex:\s*0\s+0\s+auto;[^}]*padding-top:\s*8px;",
        )
        self.assertRegex(
            css_source,
            r"\.export-intensity-info-dot\s*\{[^}]*border:\s*1px\s+solid\s+var\(--panel-border\);[^}]*width:\s*16px;[^}]*height:\s*16px;",
        )
        self.assertRegex(
            css_source,
            r"\.export-intensity-section-title-row\s*\{[^}]*display:\s*flex;[^}]*align-items:\s*center;[^}]*gap:\s*6px;",
        )
        self.assertRegex(
            css_source,
            r"\.export-intensity-section-info-dot\s*\{[^}]*width:\s*14px;[^}]*height:\s*14px;[^}]*font-size:\s*9px;",
        )
        self.assertRegex(
            css_source,
            r"\.export-intensity-module\s*\{[^}]*border:\s*none;[^}]*background:\s*transparent;",
        )
        self.assertRegex(
            css_source,
            r"\.export-intensity-filter-module\s*\{[^}]*display:\s*flex;[^}]*flex-wrap:\s*wrap;[^}]*border:\s*none;[^}]*background:\s*transparent;",
        )
        self.assertRegex(
            css_source,
            r"\.export-intensity-filter-title\s*\{[^}]*flex:\s*0\s+0\s+100%;",
        )
        self.assertRegex(
            css_source,
            r"\.export-intensity-chip\s*\{[^}]*flex:\s*0\s+0\s+auto;[^}]*min-height:\s*28px;[^}]*border:\s*1px\s+solid\s+var\(--popup-secondary-button-border\);[^}]*border-radius:\s*8px;[^}]*background:\s*var\(--popup-secondary-button-bg\);",
        )
        self.assertRegex(
            css_source,
            r"\.export-intensity-chip:hover\s*\{[^}]*background:\s*var\(--popup-secondary-button-hover-bg\);",
        )
        self.assertNotIn(".export-intensity-chip:has(input:checked)", css_source)
        self.assertRegex(
            css_source,
            r"\.export-selection-row\.stat-export-row\s*\{[^}]*border:\s*1px\s+solid\s+var\(--settings-module-border\);[^}]*background:\s*var\(--settings-module-bg\);",
        )
        self.assertIn("@media (max-width: 760px)", css_source)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css_source)
        self.assertNotIn("exportQuickSelectOverlayIn", css_source)
        self.assertNotIn('data-expanded="true"', css_source)

    def test_table_skeleton_toolbar_placeholders_match_toolbar_controls(self):
        results_css = static_text("css/components/results-viewer.css")
        self.assertRegex(
            results_css,
            r"\.skeleton-table-cell-type-filter,\s*\.skeleton-table-source-contour-filter,\s*\.skeleton-table-spatial-unit,\s*\.skeleton-table-fullscreen\s*\{[^}]*height:\s*36px;[^}]*border-radius:\s*999px;",
        )
        self.assertRegex(
            results_css,
            r"\.skeleton-table-cell-type-filter\s*\{[^}]*width:\s*272px;",
        )
        self.assertRegex(
            results_css,
            r"\.skeleton-table-source-contour-filter\s*\{[^}]*width:\s*298px;",
        )
        self.assertRegex(
            results_css,
            r"\.skeleton-table-spatial-unit\s*\{[^}]*width:\s*208px;",
        )
        self.assertRegex(
            results_css,
            r"\.skeleton-table-toolbar\s*\{[^}]*align-items:\s*flex-start;",
        )
        self.assertRegex(
            results_css,
            r"\.skeleton-table-filter-count\s*\{[^}]*width:\s*150px;[^}]*height:\s*24px;[^}]*border-radius:\s*999px;",
        )

    def test_cell_pairs_skeleton_header_uses_title_top_alignment(self):
        results_css = static_text("css/components/results-viewer.css")
        self.assertRegex(
            results_css,
            r"\.cell-pairs-toolbar\s*\{[^}]*align-items:\s*flex-start;",
        )
        self.assertRegex(
            results_css,
            r"\.skeleton-cell-header\s*\{[^}]*align-items:\s*flex-start;",
        )
        self.assertIn(".skeleton-cell-title-group {", results_css)
        self.assertRegex(
            results_css,
            r"\.skeleton-cell-filter-badge\s*\{[^}]*width:\s*150px;[^}]*height:\s*24px;[^}]*border-radius:\s*999px;",
        )

    def test_cell_pair_image_loader_uses_image_only_skeleton_overlay(self):
        results_css = static_text("css/components/results-viewer.css")

        self.assertRegex(
            results_css,
            r"\.cell-image-frame\s*\{[^}]*position:\s*relative;[^}]*width:\s*100%;[^}]*aspect-ratio:\s*1\s*/\s*1;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-image-loading-skeleton\s*\{[^}]*position:\s*absolute;[^}]*inset:\s*0;[^}]*opacity:\s*0;[^}]*visibility:\s*hidden;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-image-frame\.is-cell-image-loading\s+\.cell-image-loading-skeleton\s*\{[^}]*opacity:\s*1;[^}]*visibility:\s*visible;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-image-frame\.is-cell-image-loading\s+\.cell-image\s*\{[^}]*opacity:\s*0\.28;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-image\s*\{[^}]*width:\s*100%;[^}]*aspect-ratio:\s*1\s*/\s*1;[^}]*border-radius:\s*14px;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-image-frame\s+\.cell-image,\s*\.cell-overlay-layer\s*\{"
            r"[^}]*position:\s*absolute;[^}]*inset:\s*0;[^}]*width:\s*100%;"
            r"[^}]*height:\s*100%;[^}]*object-fit:\s*contain;"
            r"[^}]*object-position:\s*center;",
        )
        self.assertNotRegex(
            results_css,
            r"\.cell-overlay-layer\s*\{[^}]*object-fit:\s*fill;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-image-frame\s+\.cell-image\s*\{[^}]*z-index:\s*1;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-overlay-layer\s*\{[^}]*z-index:\s*2;",
        )
        self.assertNotRegex(
            results_css,
            r"\.cell-overlay-layer\s*\{[^}]*transition:\s*opacity",
        )

    def test_overlay_visibility_control_uses_blue_filter_treatment(self):
        results_css = static_text("css/components/results-viewer.css")

        self.assertRegex(
            results_css,
            r"\.overlay-visibility-control\s*\{[^}]*width:\s*184px;",
        )
        self.assertRegex(
            results_css,
            r"\.overlay-visibility-trigger\s*\{"
            r"[^}]*width:\s*98px;"
            r"[^}]*min-width:\s*98px;"
            r"[^}]*border:\s*1px solid rgba\(0,\s*123,\s*255,\s*0\.64\);"
            r"[^}]*background:\s*#007bff;"
            r"[^}]*box-shadow:\s*inset 0 1px 0 rgba\(255,\s*255,\s*255,\s*0\.16\);",
        )
        self.assertNotIn(
            '.overlay-visibility-trigger[aria-expanded="true"] .overlay-visibility-caret',
            results_css,
        )
        self.assertNotRegex(
            results_css,
            r"\.overlay-visibility-caret\s*\{[^}]*transition:\s*transform",
        )
        self.assertRegex(
            results_css,
            r"\.overlay-visibility-trigger:hover\s*\{[^}]*background:\s*#006fe6;",
        )
        self.assertRegex(
            results_css,
            r"\.overlay-visibility-option input\s*\{[^}]*accent-color:\s*#007bff;",
        )
        self.assertRegex(
            results_css,
            r"\.overlay-visibility-option:not\(:has\(input:disabled\)\):hover\s*\{"
            r"[^}]*background:\s*rgba\(0,\s*122,\s*255,\s*0\.82\);"
            r"[^}]*color:\s*#ffffff;",
        )
        self.assertRegex(
            results_css,
            r"\.overlay-visibility-actions button\s*\{"
            r"[^}]*background:\s*transparent;"
            r"[^}]*box-shadow:\s*none;",
        )
        self.assertRegex(
            results_css,
            r"\.overlay-visibility-actions button:hover,\s*"
            r"\.overlay-visibility-actions button:focus-visible\s*\{"
            r"[^}]*background:\s*rgba\(0,\s*122,\s*255,\s*0\.82\);"
            r"[^}]*color:\s*#ffffff;"
            r"[^}]*outline:\s*none;",
        )
        self.assertNotRegex(
            results_css,
            r"\.overlay-visibility-(?:trigger|option input)\s*\{[^}]*(?:#2f8f4e|#277b43|rgba\(73,\s*171,\s*104)",
        )

    def test_cell_card_contour_filter_badge_uses_quiet_meta_styling(self):
        results_css = static_text("css/components/results-viewer.css")

        self.assertIn(".cell-card-filter-meta {", results_css)
        self.assertIn(".cell-card-filter-warning {", results_css)
        self.assertIn(".cell-card-filter-label {", results_css)
        self.assertIn(".cell-card-filter-separator {", results_css)
        self.assertIn(".cell-card-filter-value {", results_css)
        self.assertIn(".cell-card-filter-warning:empty", results_css)
        self.assertRegex(
            results_css,
            r"\.cell-card-filter-meta\[hidden\],\s*\.cell-card-filter-warning\[hidden\],\s*\.cell-card-filter-warning:empty\s*\{[^}]*display:\s*none\s*!important;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-card-filter-meta\s*\{[^}]*border:\s*1px\s+solid\s+rgba\(var\(--glass-border-rgb\),\s*0\.34\);[^}]*background:\s*rgba\(18,\s*28,\s*40,\s*0\.48\);",
        )
        self.assertIn(".table-filter-count-meta {", results_css)
        self.assertRegex(
            results_css,
            r"\.table-filter-count-meta\s*\{[^}]*border:\s*1px\s+solid\s+rgba\(var\(--glass-border-rgb\),\s*0\.34\);[^}]*background:\s*rgba\(18,\s*28,\s*40,\s*0\.48\);",
        )
        self.assertIn(".table-filter-count-meta.is-applying-filter {", results_css)
        self.assertIn(".table-puncta-source-contour-filter[data-cell-type-filter] {", results_css)
        self.assertRegex(
            results_css,
            r"\.table-puncta-source-contour-filter\s*\{[^}]*flex:\s*0 0 auto;[^}]*justify-content:\s*flex-start;[^}]*gap:\s*10px;[^}]*width:\s*auto;[^}]*min-width:\s*0;",
        )
        self.assertRegex(
            results_css,
            r"\.table-puncta-source-contour-filter\[data-cell-type-filter\]\s*\{[^}]*flex:\s*0 0 272px;[^}]*justify-content:\s*flex-start;[^}]*width:\s*272px;[^}]*min-width:\s*272px;[^}]*gap:\s*10px;",
        )
        self.assertRegex(
            results_css,
            r"\.table-puncta-source-contour-filter\[data-cell-type-filter\]\s+\.table-filter-trigger\s*\{[^}]*width:\s*150px;[^}]*min-width:\s*150px;",
        )
        self.assertRegex(
            results_css,
            r"\.table-puncta-source-contour-filter\[data-puncta-source-contour-filter\]\s*\{[^}]*flex:\s*0 0 auto;[^}]*width:\s*fit-content;[^}]*min-width:\s*0;[^}]*padding-right:\s*9px;",
        )
        self.assertRegex(
            results_css,
            r"\.table-puncta-source-contour-filter\[data-puncta-source-contour-filter\]\s+\.table-filter-trigger\s*\{[^}]*flex-basis:\s*104px;[^}]*width:\s*104px;[^}]*min-width:\s*104px;",
        )
        self.assertRegex(
            results_css,
            r"\.table-puncta-source-contour-filter\[data-puncta-source-contour-filter\]\s+\.table-filter-menu\s*\{[^}]*min-width:\s*104px;",
        )
        self.assertRegex(
            results_css,
            r"\.table-filter-menu button\s*\{"
            r"[^}]*background:\s*transparent;"
            r"[^}]*box-shadow:\s*none;",
        )
        self.assertRegex(
            results_css,
            r"\.export-buttons\s+\.export_btn\s*\{[^}]*display:\s*inline-flex;[^}]*flex:\s*1\s+1\s+160px;[^}]*max-width:\s*240px;[^}]*border-radius:\s*10px;",
        )
        self.assertIn(".table-scroll-frame.is-contour-filter-applying .celltable", results_css)
        self.assertIn(".table-region-skeleton {", results_css)
        self.assertIn(".table-scroll-frame.is-contour-filter-applying .table-region-skeleton", results_css)
        self.assertIn(".table-region-skeleton .skeleton-table {", results_css)
        self.assertIn(".table-region-skeleton .skeleton-table-row {", results_css)
        self.assertIn(".cell-stats-strip.is-contour-filter-applying .metric-row", results_css)
        self.assertIn(".cell-stats-strip.is-contour-filter-applying .metric-detail", results_css)
        self.assertIn(".cell-stats-strip.is-contour-filter-applying .metric-note", results_css)
        self.assertIn(".cell-stats-strip.is-contour-filter-applying .contour-intensity-toggle", results_css)
        self.assertRegex(
            results_css,
            r"\.table-region-skeleton\s+\.skeleton-table-cell::after\s*\{[^}]*animation:\s*skeletonShimmer\s+1\.15s\s+ease-in-out\s+infinite;",
        )
        self.assertNotIn(".table-scroll-frame.is-contour-filter-applying tbody td::before", results_css)
        self.assertRegex(
            results_css,
            r"\.cell-stats-strip\.is-contour-filter-applying\s+\.metric-row::before,\s*\.cell-stats-strip\.is-contour-filter-applying\s+\.metric-detail::before,\s*\.cell-stats-strip\.is-contour-filter-applying\s+\.metric-note::before,\s*\.cell-stats-strip\.is-contour-filter-applying\s+\.contour-intensity-toggle::before\s*\{[^}]*animation:\s*skeletonShimmer\s+1\.15s\s+ease-in-out\s+infinite;",
        )
        self.assertRegex(
            results_css,
            r"\.table-toolbar\s*\{[^}]*align-items:\s*flex-start;",
        )
        self.assertRegex(
            results_css,
            r"\.table-toolbar\s*>\s*\.section-eyebrow\s*\{[^}]*margin:\s*0;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-card-filter-warning\s*\{[^}]*rgba\(255,\s*205,\s*138,\s*0\.38\);",
        )
        self.assertNotRegex(
            results_css,
            r"\.cell-card-filter-meta\s*\{[^}]*255,\s*205,\s*138",
        )

    def test_cell_pair_card_mode_specific_sections_and_contour_selector_css(self):
        results_css = static_text("css/components/results-viewer.css")
        display_css = static_text("css/pages/display.css")
        dashboard_css = static_text("css/pages/dashboard.css")

        self.assertIn("[data-cell-card-section][hidden]", results_css)
        self.assertIn("[data-contour-intensity-combination][hidden]", results_css)
        self.assertIn(".cell-stats-detail-grid[hidden]", results_css)
        self.assertIn(".cell-stats-intensity-grid[hidden]", results_css)
        self.assertRegex(
            results_css,
            r"\[data-cell-card-section\]\[hidden\],\s*\[data-contour-intensity-combination\]\[hidden\],\s*\.cell-stats-section\[hidden\],\s*\.cell-stats-detail-grid\[hidden\],\s*\.cell-stats-intensity-grid\[hidden\]\s*\{[^}]*display:\s*none\s*!important;",
        )
        self.assertIn('.cell-stats-strip[data-cell-card-mode="nuclear_cell_pair"] .cell-stats-top-grid', results_css)
        self.assertIn('.cell-stats-strip[data-cell-card-mode="puncta_distance"] .nuclear-stat-section', results_css)
        self.assertIn(".nuclear-metric-grid {", results_css)
        self.assertIn(".nuclear-metric-group {", results_css)
        self.assertIn(".nuclear-metric-group-title {", results_css)
        self.assertIn(".cell-stats-strip .nuclear-metric-grid .nuclear-metric-row {", results_css)
        self.assertIn(".cell-stats-detail-grid {", results_css)
        self.assertIn(".contour-intensity-heading {", results_css)
        self.assertIn(".contour-intensity-title-group {", results_css)
        self.assertIn(".contour-intensity-type-pill {", results_css)
        self.assertIn(".contour-intensity-toggle {", results_css)
        self.assertIn(".contour-intensity-toggle-indicator {", results_css)
        self.assertIn(".contour-intensity-toggle-btn {", results_css)
        self.assertIn('.contour-intensity-toggle-btn[aria-pressed="true"]', results_css)
        self.assertIn(".contour-intensity-groups {", results_css)
        self.assertNotIn("grid-template-columns: repeat(5", results_css)
        self.assertRegex(
            results_css,
            r"\.cell-stats-strip\s+\.nuclear-metric-grid\s+\.nuclear-metric-row\s*\{[^}]*grid-template-columns:\s*minmax\(138px,\s*1fr\)\s+minmax\(72px,\s*auto\);[^}]*border-top:\s*1px\s+solid\s+rgba\(255,\s*255,\s*255,\s*0\.07\);",
        )
        self.assertRegex(
            results_css,
            r"\.nuclear-metric-row\s+\.metric-value\s*\{[^}]*justify-self:\s*end;[^}]*text-align:\s*right;[^}]*white-space:\s*nowrap;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-stats-strip\[data-cell-card-mode=\"puncta_distance\"\]\s+\.puncta-stat-section\s+\.metric-row,\s*\.cell-stats-strip\[data-cell-card-mode=\"puncta_distance\"\]\s+\.biorientation-stat-section\s+\.metric-row,\s*\.cell-stats-strip\[data-cell-card-mode=\"puncta_distance\"\]\s+\.cen-dot-stat-section\s+\.metric-row,\s*\.cell-stats-strip\[data-cell-card-mode=\"puncta_distance\"\]\s+\.measurement-contour-section\s+\.metric-row,\s*\.cell-stats-strip\[data-cell-card-mode=\"puncta_distance\"\]\s+\.contour-intensity-combination\s+\.metric-row\s*\{[^}]*min-height:\s*22px;[^}]*padding:\s*3px\s+0;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-stats-strip\[data-cell-card-mode=\"puncta_distance\"\]\s+\.puncta-stat-section\s+\.metric-row\s+\+\s+\.metric-row,\s*\.cell-stats-strip\[data-cell-card-mode=\"puncta_distance\"\]\s+\.biorientation-stat-section\s+\.metric-row\s+\+\s+\.metric-row,\s*\.cell-stats-strip\[data-cell-card-mode=\"puncta_distance\"\]\s+\.cen-dot-stat-section\s+\.metric-row\s+\+\s+\.metric-row,\s*\.cell-stats-strip\[data-cell-card-mode=\"puncta_distance\"\]\s+\.measurement-contour-section\s+\.metric-row,\s*\.cell-stats-strip\[data-cell-card-mode=\"puncta_distance\"\]\s+\.contour-intensity-combination\s+\.metric-row\s+\+\s+\.metric-row\s*\{[^}]*border-top:\s*1px\s+solid\s+rgba\(255,\s*255,\s*255,\s*0\.07\);",
        )
        self.assertRegex(
            results_css,
            r"\.cell-stats-detail-grid\s*>\s*\.measurement-contour-section\[hidden\]\s*\+\s*\.cell-stats-intensity-grid\s*\{[^}]*grid-column:\s*1\s*/\s*-1;[^}]*border-left:\s*0;",
        )
        self.assertRegex(
            results_css,
            r"\.contour-intensity-heading\s*\{[^}]*display:\s*flex;[^}]*justify-content:\s*space-between;",
        )
        self.assertRegex(
            results_css,
            r"\.contour-intensity-title-group\s*\{[^}]*display:\s*inline-flex;[^}]*gap:\s*6px;",
        )
        self.assertRegex(
            results_css,
            r"\.contour-intensity-type-pill\s*\{[^}]*justify-content:\s*center;[^}]*box-sizing:\s*border-box;[^}]*flex:\s*0 0 68px;[^}]*width:\s*68px;[^}]*min-width:\s*68px;[^}]*white-space:\s*nowrap;",
        )
        self.assertRegex(
            results_css,
            r"\.contour-intensity-toggle\s*\{[^}]*position:\s*relative;[^}]*display:\s*inline-flex;[^}]*justify-self:\s*end;[^}]*margin-left:\s*auto;[^}]*border-radius:\s*8px;",
        )
        self.assertRegex(
            results_css,
            r"\.contour-intensity-toggle-indicator\s*\{[^}]*position:\s*absolute;[^}]*width:\s*calc\(\(100%\s*-\s*10px\)\s*/\s*3\);[^}]*transition:\s*transform\s+170ms\s+ease;",
        )
        self.assertRegex(
            results_css,
            r'\.contour-intensity-toggle\[data-active-intensity="max"\]\s+\.contour-intensity-toggle-indicator\s*\{[^}]*transform:\s*translateX\(calc\(100%\s*\+\s*2px\)\);',
        )
        self.assertRegex(
            results_css,
            r'\.contour-intensity-toggle\[data-active-intensity="average"\]\s+\.contour-intensity-toggle-indicator\s*\{[^}]*transform:\s*translateX\(calc\(200%\s*\+\s*4px\)\);',
        )
        self.assertRegex(
            results_css,
            r"\.contour-intensity-toggle-btn\s*\{[^}]*position:\s*relative;[^}]*z-index:\s*1;[^}]*width:\s*72px;[^}]*min-height:\s*24px;[^}]*border-radius:\s*6px;[^}]*white-space:\s*nowrap;",
        )
        self.assertRegex(
            results_css,
            r'\.contour-intensity-toggle-btn:not\(\.active\):not\(\[aria-pressed="true"\]\):not\(:hover\):not\(:focus-visible\)\s*\{'
            r"[^}]*background:\s*transparent;"
            r"[^}]*box-shadow:\s*none\s*!important;"
            r"[^}]*filter:\s*none\s*!important;",
        )
        self.assertRegex(
            results_css,
            r'\.contour-intensity-toggle-btn\.active,\s*\.contour-intensity-toggle-btn\[aria-pressed="true"\]\s*\{[^}]*color:\s*#ffffff;[^}]*background:\s*transparent;',
        )
        self.assertRegex(
            results_css,
            r"\.contour-intensity-groups\s*\{[^}]*grid-template-columns:\s*repeat\(4,\s*minmax\(118px,\s*1fr\)\);",
        )
        self.assertRegex(
            results_css,
            r"\.cell-stats-strip\[data-contour-intensity-combination-count=\"1\"\]\s+\.contour-intensity-section\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(176px,\s*220px\)\s+minmax\(0,\s*1fr\);[^}]*grid-template-areas:\s*\"title combo toggle\";",
        )
        self.assertRegex(
            results_css,
            r"\.cell-stats-strip\[data-contour-intensity-combination-count=\"1\"\]\s+\.contour-intensity-heading\s*\{[^}]*display:\s*contents;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-stats-strip\[data-contour-intensity-combination-count=\"1\"\]\s+\.contour-intensity-groups\s*\{[^}]*grid-area:\s*combo;[^}]*grid-template-columns:\s*minmax\(176px,\s*220px\);[^}]*justify-self:\s*center;",
        )
        self.assertRegex(
            results_css,
            r"\.cell-stats-strip\s+\.contour-intensity-combination\s*\{[^}]*border-top:\s*0;",
        )
        self.assertRegex(
            results_css,
            r"\.contour-intensity-combination\s+\.metric-label\s*\{[^}]*overflow-wrap:\s*normal;[^}]*word-break:\s*normal;",
        )
        self.assertIn("@media (max-width: 1180px)", results_css)
        self.assertIn("@media (max-width: 760px)", results_css)
        self.assertRegex(
            results_css,
            r"\.cell-stats-strip\[data-contour-intensity-combination-count=\"1\"\]\s+\.contour-intensity-section\s*\{[^}]*grid-template-columns:\s*1fr;[^}]*grid-template-areas:\s*\"heading\"\s*\"combo\";",
        )
        self.assertRegex(
            results_css,
            r"\.cell-stats-strip\[data-contour-intensity-combination-count=\"1\"\]\s+\.contour-intensity-heading\s*\{[^}]*display:\s*flex;[^}]*grid-area:\s*heading;",
        )
        self.assertIn(".nuclear-metric-grid {\n        grid-template-columns: 1fr;", results_css)
        self.assertNotIn(".cell-stats-column", display_css)
        self.assertNotIn(".cell-stats-column", dashboard_css)
        self.assertNotIn(".cell-stats-strip {\n        grid-template-columns", display_css)
        self.assertNotIn(".cell-stats-strip {\n        grid-template-columns", dashboard_css)

    def test_decorative_icon_slots_do_not_use_placeholder_glyphs(self):
        for css_path in (CORE_STATIC_ROOT / "css").rglob("*.css"):
            source = css_path.read_text(encoding="utf-8", errors="replace")
            with self.subTest(css=css_path.relative_to(CORE_STATIC_ROOT)):
                self.assertNotRegex(source, r"content:\s*['\"]\?['\"]")

        icon_text_pattern = re.compile(
            r'class=["\'][^"\']*(?:channel-order-action-icon|channel-chip-grip|scale-revert-icon)[^"\']*["\'][^>]*>([^<]+)</span>'
        )
        source_paths = (
            list(TEMPLATE_ROOT.rglob("*.html"))
            + list((CORE_STATIC_ROOT / "js").rglob("*.js"))
        )
        for path in source_paths:
            source = path.read_text(encoding="utf-8", errors="replace")
            for match in icon_text_pattern.finditer(source):
                with self.subTest(path=path.name, icon=match.group(0)):
                    self.assertEqual(match.group(1).strip(), "")
            for pattern in (
                r"channel-order-action-icon[^>]*>\s*\?+\s*</span>",
                r"channel-chip-grip[^>]*>\s*\?+\s*</span>",
                r"scale-revert-icon[^>]*>\s*\?+\s*</span>",
                r"aria-hidden=[\"']true[\"'][^>]*>\s*\?+\s*</span>",
            ):
                with self.subTest(path=path.name, pattern=pattern):
                    self.assertNotRegex(source, pattern)
            with self.subTest(path=path.name, generated_unicode_grip=True):
                self.assertNotIn(chr(0x22EE) * 2, source)
            with self.subTest(path=path.name, generated_unicode_actions=True):
                self.assertNotIn(chr(0x21B6), source)
                self.assertNotIn(chr(0x21BB), source)
            with self.subTest(path=path.name, generated_grip_text=True):
                self.assertNotIn("grip.textContent", source)
            with self.subTest(path=path.name, generated_revert_placeholder=True):
                self.assertNotIn("? Revert", source)
                self.assertNotIn(chr(0x21BA) + " Revert", source)

        preprocess_css = (CORE_STATIC_ROOT / "css/pages/pre-process.css").read_text(
            encoding="utf-8",
            errors="replace",
        )
        preprocess_js = (CORE_STATIC_ROOT / "js/pages/pre-process.js").read_text(encoding="utf-8")
        preprocess_template = (TEMPLATE_ROOT / "pre_process.html").read_text(encoding="utf-8")
        for source in (preprocess_js, preprocess_template):
            with self.subTest(source="scale-revert-svg"):
                self.assertIn('<svg class="scale-revert-icon"', source)
                self.assertIn('viewBox="0 0 12 12"', source)
                self.assertIn('<path d="M4.8 3.1 2.2 5.7l2.6 2.6"></path><path d="M2.6 5.7h4a3 3 0 1 1-1.8 5.4"></path>', source)
                self.assertIn('<span class="scale-revert-label">Revert</span>', source)
        self.assertIn(".scale-revert-icon {", preprocess_css)
        self.assertIn("transform: translateY(-0.5px);", preprocess_css)
        self.assertIn(".scale-revert-label {", preprocess_css)
        self.assertIn(".channel-chip-grip::before", preprocess_css)
        self.assertNotIn(".preprocess-page .channel-chip-grip::before", preprocess_css)
        self.assertIn("width: 7px;", preprocess_css)
        self.assertIn("height: 12px;", preprocess_css)
        self.assertIn(
            "box-shadow: 5px 0 0 currentColor, 0 4px 0 currentColor, 5px 4px 0 currentColor, 0 8px 0 currentColor, 5px 8px 0 currentColor;",
            preprocess_css,
        )
        self.assertIn("top: 1px;", preprocess_css)
        self.assertNotIn("radial-gradient(circle, currentColor 1.1px", preprocess_css)

    def test_no_stale_modularization_paths_remain(self):
        stale_paths = (
            "js/shared/export-selection.js",
            "js/shared/overlay-prefetch.js",
            "css/results-viewer.css",
            "js/results-viewer.js",
        )
        for path in list(TEMPLATE_ROOT.rglob("*.html")) + list((CORE_STATIC_ROOT / "js").rglob("*.js")):
            source = path.read_text(encoding="utf-8")
            for stale_path in stale_paths:
                with self.subTest(path=path.name, stale_path=stale_path):
                    self.assertNotIn(stale_path, source)
