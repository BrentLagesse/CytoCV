from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase


WORKFLOW_PATH = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "backend-ci.yml"


class BackendCiContractTests(SimpleTestCase):
    @staticmethod
    def _workflow_text() -> str:
        return WORKFLOW_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")

    @classmethod
    def _job_block(cls, job_name: str) -> str:
        workflow = cls._workflow_text()
        match = re.search(rf"^  {re.escape(job_name)}:\n", workflow, flags=re.MULTILINE)
        if not match:
            raise AssertionError(f"Missing CI job {job_name!r}")
        next_job = re.search(r"^  [a-z0-9-]+:\n", workflow[match.end():], flags=re.MULTILINE)
        if next_job:
            return workflow[match.start(): match.end() + next_job.start()]
        return workflow[match.start():]

    def test_backend_ci_defines_expected_jobs_and_safe_environment(self):
        workflow = self._workflow_text()

        for job_name in (
            "backend-full-suite",
            "targeted-regressions",
            "frontend-contracts",
            "docs-and-ci-contracts",
        ):
            with self.subTest(job=job_name):
                self.assertIn(f"  {job_name}:", workflow)
                self.assertIn(f"    name: {job_name}", workflow)
        self.assertIn("CYTOCV_DB_BACKEND: sqlite", workflow)
        self.assertIn("CYTOCV_ANALYSIS_EXECUTION_MODE: sync", workflow)
        self.assertIn("CYTOCV_SECRET_KEY: ci-insecure-secret-key", workflow)
        self.assertNotIn("${{ secrets.", workflow)
        self.assertNotIn("GOOGLE_CLIENT_SECRET", workflow)
        self.assertNotIn("MICROSOFT_CLIENT_SECRET", workflow)
        self.assertNotIn("EMAIL_HOST_PASSWORD", workflow)

    def test_backend_full_suite_runs_django_safety_gate_and_full_suite(self):
        job = self._job_block("backend-full-suite")

        for snippet in (
            "uses: actions/checkout@v6",
            "uses: actions/setup-python@v6",
            "python-version-file: .python-version",
            "python -m pip install -r requirements.txt",
            "run: python manage.py check",
            "run: python manage.py makemigrations --check --dry-run",
            "run: python manage.py collectstatic --dry-run --noinput",
            "run: python manage.py test",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, job)

    def test_targeted_regressions_run_high_signal_modules(self):
        job = self._job_block("targeted-regressions")

        for test_module in (
            "core.tests.test_cell_inclusion_mode",
            "core.tests.test_puncta_source_contour_count_filter",
            "core.tests.test_intensity_helpers",
            "core.tests.test_stats_validation",
            "core.tests.test_modern_contour_statistics",
            "core.tests.test_tables",
            "core.tests.test_cell_statistics_payload",
            "core.tests.test_stat_export_selection",
            "core.tests.test_cell_deletion",
            "core.tests.test_analysis_async",
            "core.tests.test_accounts_preferences",
            "core.tests.test_tiff_channel_parser",
            "core.tests.test_tiff_scale_parser",
            "core.tests.test_upload_preparation",
            "core.tests.test_upload_length_scale",
        ):
            with self.subTest(test_module=test_module):
                self.assertIn(test_module, job)

    def test_frontend_contracts_run_node_check_before_frontend_tests(self):
        job = self._job_block("frontend-contracts")

        self.assertIn("uses: actions/setup-node@v6", job)
        self.assertIn('node-version: "22"', job)
        self.assertIn("node --check \"$file\"", job)
        self.assertLess(job.index("node --check \"$file\""), job.index("Frontend contract tests"))
        for test_module in (
            "core.tests.test_frontend_template_contracts",
            "core.tests.test_frontend_static_contracts",
            "core.tests.test_frontend_json_contracts",
            "core.tests.test_frontend_js_contracts",
            "core.tests.test_frontend_workflow_contracts",
            "core.tests.test_frontend_viewer_contracts",
            "core.tests.test_frontend_export_contracts",
            "core.tests.test_core_app",
        ):
            with self.subTest(test_module=test_module):
                self.assertIn(test_module, job)

    def test_docs_and_ci_contracts_run_compile_whitespace_and_contract_tests(self):
        job = self._job_block("docs-and-ci-contracts")

        self.assertIn("run: python -m compileall cytocv", job)
        self.assertIn("git diff --check", job)
        self.assertIn("core.tests.test_docs_contracts", job)
        self.assertIn("core.tests.test_backend_ci_contracts", job)
        self.assertIn("core.tests.test_settings_contracts", job)
