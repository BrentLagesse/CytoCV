from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def doc_text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


class DocumentationContractTests(SimpleTestCase):
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
