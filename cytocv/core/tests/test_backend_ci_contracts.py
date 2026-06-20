from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase


WORKFLOW_PATH = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "backend-ci.yml"


class BackendCiContractTests(SimpleTestCase):
    @staticmethod
    def _workflow_text() -> str:
        return WORKFLOW_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")

    @classmethod
    def _workflow_step(cls, name: str) -> str:
        workflow = cls._workflow_text()
        start = workflow.index(f"      - name: {name}")
        next_step = workflow.find("\n      - name:", start + 1)
        if next_step == -1:
            return workflow[start:]
        return workflow[start:next_step]

    def test_backend_ci_keeps_original_baseline_commands(self):
        workflow = self._workflow_text()

        expected_snippets = (
            "      - name: Django system check\n"
            "        working-directory: cytocv\n"
            "        run: python manage.py check",
            "      - name: Migration dry-run\n"
            "        working-directory: cytocv\n"
            "        run: python manage.py makemigrations --check --dry-run",
            "      - name: Static collection dry-run\n"
            "        working-directory: cytocv\n"
            "        run: python manage.py collectstatic --dry-run --noinput",
            "      - name: Core tests\n"
            "        working-directory: cytocv\n"
            "        run: python manage.py test core",
            "      - name: Account tests\n"
            "        working-directory: cytocv\n"
            "        run: python manage.py test accounts",
            "      - name: Full test suite\n"
            "        working-directory: cytocv\n"
            "        run: python manage.py test",
        )
        for snippet in expected_snippets:
            with self.subTest(snippet=snippet.splitlines()[0]):
                self.assertIn(snippet, workflow)

    def test_backend_ci_keeps_frontend_contract_step_before_core_suite(self):
        workflow = self._workflow_text()
        frontend_step = self._workflow_step("Frontend contract tests")

        frontend_index = workflow.index("      - name: Frontend contract tests")
        core_index = workflow.index("      - name: Core tests")

        self.assertLess(frontend_index, core_index)
        self.assertIn("working-directory: cytocv", frontend_step)
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
                self.assertIn(test_module, frontend_step)

    def test_backend_ci_keeps_encoding_regressions_in_frontend_contract_step(self):
        frontend_step = self._workflow_step("Frontend contract tests")

        self.assertIn("core.tests.test_frontend_template_contracts", frontend_step)
        self.assertIn("core.tests.test_frontend_static_contracts", frontend_step)
        self.assertLess(
            frontend_step.index("core.tests.test_frontend_template_contracts"),
            frontend_step.index("core.tests.test_frontend_static_contracts"),
        )

    def test_backend_ci_uses_sqlite_test_environment(self):
        workflow = self._workflow_text()

        self.assertIn("CYTOCV_DB_BACKEND: sqlite", workflow)
        self.assertIn('CYTOCV_ANALYSIS_EXECUTION_MODE: sync', workflow)
