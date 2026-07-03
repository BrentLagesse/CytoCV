"""Protect Django settings assumptions that tests and deployment rely on."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


PROJECT_DIR = Path(__file__).resolve().parents[2]


class SettingsEnvironmentContractTests(SimpleTestCase):
    def _run_settings_import(self, code: str, **env_overrides: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "CYTOCV_SECRET_KEY": "test-settings-secret-key",
                "CYTOCV_DEBUG": "1",
                "CYTOCV_ALLOWED_HOSTS": "localhost,127.0.0.1,testserver",
                "CYTOCV_DB_BACKEND": "sqlite",
                "CYTOCV_ANALYSIS_EXECUTION_MODE": "sync",
            }
        )
        env.update(env_overrides)
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_sqlite_settings_import_for_test_environment(self):
        result = self._run_settings_import(
            "import cytocv.settings as s\n"
            "assert s.DEBUG is True\n"
            "assert s.DB_BACKEND == 'sqlite'\n"
            "assert s.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'\n"
            "print('sqlite settings ok')\n"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "sqlite settings ok")

    def test_production_mode_rejects_sqlite_backend(self):
        result = self._run_settings_import(
            "import cytocv.settings\n",
            CYTOCV_SECRET_KEY="test-settings-production-secret-key",
            CYTOCV_DEBUG="0",
            CYTOCV_ALLOWED_HOSTS="cytocv.example.test",
            CYTOCV_DB_BACKEND="sqlite",
        )

        combined_output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SQLite is not allowed when CYTOCV_DEBUG=0", combined_output)
        self.assertNotIn("test-settings-production-secret-key", combined_output)
