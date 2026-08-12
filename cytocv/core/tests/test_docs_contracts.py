"""Protect documentation references that describe public routes and workflows."""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase

from core.services.signal_quantification import (
    DEFAULT_SIGNAL_SELECTED_PLUGINS,
    NUCLEAR_CELL_PAIR_PLUGIN,
    PUNCTA_DISTANCE_PLUGIN,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def doc_text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


class DocumentationContractTests(SimpleTestCase):
    def test_docs_distinguish_primary_modes_from_puncta_defaults(self):
        readme = doc_text("README.md")
        workflow_guide = doc_text("docs/user/workflow-guide.md")
        analysis_options = doc_text("docs/user/analysis-options.md")
        getting_started = doc_text("docs/user/getting-started.md")
        overview = readme.split("## Overview", maxsplit=1)[1].split(
            "## System Scope",
            maxsplit=1,
        )[0]
        companion_plugins = tuple(
            re.findall(r"^- `([^`]+)`$", overview, flags=re.MULTILINE)
        )
        documented_default_plugins = (
            PUNCTA_DISTANCE_PLUGIN,
            *companion_plugins,
        )

        self.assertEqual(
            documented_default_plugins,
            DEFAULT_SIGNAL_SELECTED_PLUGINS,
        )
        self.assertNotIn(NUCLEAR_CELL_PAIR_PLUGIN, DEFAULT_SIGNAL_SELECTED_PLUGINS)
        self.assertIn(
            "CytoCV exposes two primary Signal Quantification modes:",
            overview,
        )
        self.assertIn(
            f"`{PUNCTA_DISTANCE_PLUGIN}` (`Puncta Distance`)",
            overview,
        )
        self.assertIn(
            f"`{NUCLEAR_CELL_PAIR_PLUGIN}` (`Nuclear, Cell-Pair Intensity`)",
            overview,
        )
        self.assertIn("fully supported selectable primary mode", overview)
        self.assertIn("default puncta-oriented plugin selection", overview)

        self.assertIn(PUNCTA_DISTANCE_PLUGIN, workflow_guide)
        self.assertIn(NUCLEAR_CELL_PAIR_PLUGIN, workflow_guide)
        self.assertIn("default primary mode", workflow_guide)
        self.assertIn("default puncta-oriented selection", workflow_guide)
        self.assertIn("nucleus-contour and measurement controls", workflow_guide)

        current_docs = {
            "README.md": readme,
            "docs/user/workflow-guide.md": workflow_guide,
            "docs/user/analysis-options.md": analysis_options,
            "docs/user/getting-started.md": getting_started,
        }
        for path, content in current_docs.items():
            normalized_content = " ".join(content.split())
            with self.subTest(path=path, mode=PUNCTA_DISTANCE_PLUGIN):
                self.assertIn(PUNCTA_DISTANCE_PLUGIN, normalized_content)
            with self.subTest(path=path, mode=NUCLEAR_CELL_PAIR_PLUGIN):
                self.assertIn(NUCLEAR_CELL_PAIR_PLUGIN, normalized_content)
            with self.subTest(path=path, default="puncta"):
                self.assertRegex(
                    normalized_content,
                    rf"(?:default.{{0,80}}{PUNCTA_DISTANCE_PLUGIN}|"
                    rf"{PUNCTA_DISTANCE_PLUGIN}.{{0,80}}default)",
                )
            with self.subTest(path=path, alternative="nuclear"):
                self.assertRegex(
                    normalized_content,
                    rf"{NUCLEAR_CELL_PAIR_PLUGIN}.{{0,300}}"
                    r"(?:fully supported|selectable|activates)",
                )

        prohibited_descriptions = (
            " ".join(("not enabled in the", "default plugin set")),
        )
        prohibited_mode_pattern = re.compile(
            rf"{NUCLEAR_CELL_PAIR_PLUGIN.lower()}\s+"
            r"(?:is|was|has been)\s+"
            r"(?:unavailable|removed|deprecated|legacy|not (?:offered|available))"
        )
        for path, content in current_docs.items():
            normalized_content = " ".join(content.replace("`", "").split()).lower()
            for prohibited in prohibited_descriptions:
                with self.subTest(path=path, prohibited=prohibited):
                    self.assertNotIn(prohibited.lower(), normalized_content)
            with self.subTest(path=path, prohibited="mode status"):
                self.assertIsNone(prohibited_mode_pattern.search(normalized_content))

    def test_citation_metadata_and_readme_release_citation(self):
        citation = doc_text("CITATION.cff")
        readme = doc_text("README.md")
        normalized_citation = " ".join(citation.split())
        citation_section = readme.split("## Citation", maxsplit=1)[1].split(
            "## License",
            maxsplit=1,
        )[0]

        for expected in (
            'version: "2.0.0"',
            'date-released: "2026-08-12"',
            'doi: "10.5281/zenodo.21901187"',
            'repository-code: "https://github.com/BrentLagesse/CytoCV"',
            'repository-artifact: "https://doi.org/10.5281/zenodo.21901187"',
            'url: "https://cytocv2.uwb.edu/"',
            'license: "AGPL-3.0-or-later"',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, citation)

        self.assertIn(
            "[10.5281/zenodo.21901187](https://doi.org/10.5281/zenodo.21901187)",
            citation_section,
        )
        self.assertIn("[`CITATION.cff`](CITATION.cff)", citation_section)
        self.assertLess(readme.index("## Citation"), readme.index("## License"))
        self.assertIn(
            "CytoCV is a browser-accessible Django platform for reproducible "
            "analysis of yeast fluorescence microscopy images. It supports "
            "DeltaVision and stack TIFF inputs, DIC-guided Mask R-CNN "
            "segmentation, configurable single-cell and cell-pair retention, "
            "plugin-based per-cell measurements, visual review, and structured "
            "CSV/XLSX export.",
            normalized_citation,
        )

        keywords = (
            "yeast microscopy",
            "fluorescence quantification",
            "bioimage analysis",
            "cell instance segmentation",
            "Django",
            "Mask R-CNN",
            "reproducible research",
        )
        keyword_positions = [citation.index(f"  - {keyword}") for keyword in keywords]
        self.assertEqual(keyword_positions, sorted(keyword_positions))

        for family_name, given_name in (
            ("Gioanni", "Nicolas"),
            ("Prasad", "Anoop"),
            ("Parnell", "Emily"),
            ("Miller", "Matthew P."),
            ("Lagesse", "Brent"),
        ):
            with self.subTest(author=family_name):
                self.assertIn(
                    f'- family-names: "{family_name}"\n'
                    f'    given-names: "{given_name}"',
                    citation,
                )

    def test_license_docs_preserve_v2_release_and_commercial_position(self):
        license_docs = doc_text("docs/license/README.md")

        self.assertIn("AGPL-3.0-or-later", license_docs)
        self.assertIn("Section 13 network-source requirement", license_docs)
        self.assertIn("non-binding project preference", license_docs)
        self.assertIn("The full `LICENSE` file controls.", license_docs)
        self.assertIn("Releases through v1.8.2", license_docs)
        self.assertIn(
            "Beginning with v2.0.0, CytoCV releases are published under "
            "`AGPL-3.0-or-later`.",
            license_docs,
        )
        self.assertIn(
            "https://github.com/BrentLagesse/CytoCV/tree/v2.0.0",
            license_docs,
        )
        self.assertNotIn("COMMERCIAL USE IS PERMITTED", license_docs)

    def test_uw_names_and_marks_notice_is_separate_from_agpl(self):
        notice_path = PROJECT_ROOT / "TRADEMARKS.md"
        notice = doc_text("TRADEMARKS.md")
        readme = doc_text("README.md")
        normalized_notice = " ".join(notice.split())

        self.assertTrue(notice_path.is_file())
        self.assertIn(
            "University of Washington names, logos, and marks are not licensed "
            "under AGPL-3.0-or-later.",
            normalized_notice,
        )
        self.assertIn(
            "Their use is subject to the applicable University of Washington "
            "branding and trademark requirements.",
            normalized_notice,
        )
        self.assertIn("[TRADEMARKS.md](TRADEMARKS.md)", readme)
        self.assertNotIn("used with permission", f"{notice}\n{readme}".lower())

    def test_docs_describe_cell_inclusion_mode_as_analysis_time_setting(self):
        combined = "\n".join(
            [
                doc_text("docs/user/analysis-options.md"),
                doc_text("docs/user/workflow-guide.md"),
                doc_text("docs/user/account-and-dashboard.md"),
            ]
        )

        self.assertIn("Cell Inclusion Mode", combined)
        self.assertIn("analysis-time", combined)
        self.assertIn("Cell pairs only", combined)
        self.assertIn("Single cells only", combined)
        self.assertIn("Single cells and cell pairs", combined)
        self.assertIn("Display and Dashboard filters cannot recover", combined)
        self.assertIn("pair-specific outputs", combined)
        self.assertIn("N/A", combined)

    def test_docs_describe_cell_type_and_source_count_row_filters(self):
        combined = "\n".join(
            [
                doc_text("docs/user/output-guide.md"),
                doc_text("docs/user/account-and-dashboard.md"),
                doc_text("docs/reference/file-format-and-artifact-spec.md"),
            ]
        )

        self.assertIn("Cell Type Filter", combined)
        self.assertIn("Puncta Source", combined)
        self.assertIn("Source Contour Count", combined)
        self.assertIn("row filters", combined)
        self.assertIn("Deleted cells", combined)
        self.assertIn("_cell_type", combined)
        self.assertIn("_puncta_source_contour_count", combined)
        self.assertIn("_columns", combined)
        self.assertIn("Selected metrics are column", combined)

    def test_docs_describe_total_max_average_intensity_exports(self):
        combined = "\n".join(
            [
                doc_text("docs/user/analysis-options.md"),
                doc_text("docs/user/output-guide.md"),
            ]
        )

        self.assertIn("Total Intensity", combined)
        self.assertIn("Max Intensity", combined)
        self.assertIn("Average Intensity", combined)
        self.assertIn("raw pixel", combined)
        self.assertIn("Red In Red", combined)
        self.assertIn("Green In Red", combined)
        self.assertIn("Red In Green", combined)
        self.assertIn("Green In Green", combined)
        self.assertIn("independently", combined)

    def test_docs_describe_ci_jobs_and_local_commands(self):
        testing_guide = doc_text("docs/developer/testing-guide.md")

        for expected in (
            "backend-full-suite",
            "targeted-regressions",
            "frontend-contracts",
            "docs-and-ci-contracts",
            "python manage.py check",
            "python manage.py makemigrations --check --dry-run",
            "python -m compileall cytocv",
            "node --check",
            "git diff --check",
            "core.tests.test_docs_contracts",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, testing_guide)

    def test_active_docs_use_current_puncta_contour_detection_label(self):
        active_docs = "\n".join(
            doc_text(path)
            for path in (
                "README.md",
                "docs/user/analysis-options.md",
                "docs/user/workflow-guide.md",
                "docs/user/output-guide.md",
                "docs/user/account-and-dashboard.md",
                "docs/reference/file-format-and-artifact-spec.md",
                "docs/reference/data-model.md",
                "docs/developer/testing-guide.md",
            )
        )

        self.assertIn("Puncta & Contour Detection", active_docs)
        self.assertNotIn("Dot Detection", active_docs)
