from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase

from .frontend_contract_helpers import CORE_STATIC_ROOT, TEMPLATE_ROOT, static_text


STATIC_TAG_RE = re.compile(r"{%\s*static\s+[\"']([^\"']+)[\"']\s*%}")
CSS_URL_RE = re.compile(r"url\(\s*([\"']?)(.*?)\1\s*\)")


class FrontendStaticContractTests(SimpleTestCase):
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
