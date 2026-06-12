from __future__ import annotations

import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .frontend_contract_helpers import (
    create_preprocess_file,
    login_user,
    parse_json_script,
    response_text,
    temporary_media_root,
)


class FrontendWorkflowContractTests(TestCase):
    def test_upload_batch_rejects_invalid_file_with_frontend_error_shape(self):
        login_user(self, "frontend-upload-invalid@example.com")

        response = self.client.post(
            reverse("experiment_upload_batch"),
            {"files": [SimpleUploadedFile("sample.txt", b"not-dv")]},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIsInstance(payload["errors"], list)
        self.assertTrue(payload["errors"])

    def test_upload_batch_accepts_supported_file_with_uploads_shape(self):
        login_user(self, "frontend-upload-valid@example.com")

        with temporary_media_root():
            response = self.client.post(
                reverse("experiment_upload_batch"),
                {"files": [SimpleUploadedFile("sample.tiff", b"tiff")]},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsInstance(payload["uploads"], list)
        self.assertEqual(len(payload["uploads"]), 1)
        self.assertIn("uuid", payload["uploads"][0])
        self.assertEqual(payload["uploads"][0]["name"], "sample")

    def test_upload_preparation_empty_request_keeps_frontend_error_shape(self):
        login_user(self, "frontend-upload-prep-empty@example.com")

        response = self.client.post(
            reverse("experiment_upload_prepare"),
            data={},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIsInstance(payload["errors"], list)

    def test_experiment_workflow_defaults_invalid_json_keeps_error_shape(self):
        login_user(self, "frontend-workflow-invalid-json@example.com")

        response = self.client.post(
            reverse("experiment_workflow_defaults"),
            data="{bad-json",
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIsInstance(payload["errors"], list)
        self.assertTrue(payload["errors"])

    def test_progress_endpoint_exposes_polling_payload_shape(self):
        user = login_user(self, "frontend-progress@example.com")
        uuid_value = create_preprocess_file(user)

        response = self.client.get(reverse("analysis_progress", args=[uuid_value]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in ("phase", "status", "failure_summary", "detail", "redirect"):
            self.assertIn(key, payload)
        self.assertIsInstance(payload["detail"], dict)

    def test_preprocess_page_config_matches_progress_and_cancel_routes(self):
        user = login_user(self, "frontend-preprocess-config@example.com")
        uuid_value = create_preprocess_file(user)

        response = self.client.get(reverse("pre_process", args=[uuid_value]))
        config = parse_json_script(response_text(response), "preprocessPageConfig")

        self.assertEqual(config["uuids"], uuid_value)
        self.assertIn(config["analysisExecutionMode"], {"sync", "worker"})
        self.assertEqual(config["experimentUrl"], reverse("experiment"))


