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

        workflow_css = static_text("css/components/workflow-controls.css")
        experiment_css = static_text("css/pages/experiment.css")
        defaults_css = static_text("css/pages/workflow-defaults.css")
        for selector in (
            ".signal-mode-panel {",
            ".length-unit-caret {",
            ".channel-order-control .channel-chip {",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, workflow_css)
                self.assertNotIn(selector, experiment_css)
                self.assertNotIn(selector, defaults_css)

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
