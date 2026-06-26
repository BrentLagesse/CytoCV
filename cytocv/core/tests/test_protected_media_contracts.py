from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import UploadedImage


class ProtectedMediaContractTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="media-owner@example.com",
            password="TestPass123!",
        )
        self.other_user = user_model.objects.create_user(
            email="media-other@example.com",
            password="TestPass123!",
        )

        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.temp_root = Path(self.temp_dir.name)
        self.media_root = self.temp_root / "media"
        self.media_root.mkdir()
        self.media_root_patcher = patch("core.views.media.MEDIA_ROOT", self.media_root)
        self.media_root_patcher.start()
        self.addCleanup(self.media_root_patcher.stop)

        self.run_uuid = uuid4()
        UploadedImage.objects.create(
            user=self.user,
            uuid=self.run_uuid,
            name="owned-media",
            file_location=f"{self.run_uuid}/owned-media.dv",
        )

        self.relative_path = f"{self.run_uuid}/output/owned.txt"
        file_path = self.media_root / self.relative_path
        file_path.parent.mkdir(parents=True)
        file_path.write_bytes(b"owned media")

    def test_owner_can_download_owned_media_file(self):
        self.assertTrue(self.client.login(email=self.user.email, password="TestPass123!"))

        response = self.client.get(reverse("protected_media", args=[self.relative_path]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertEqual(b"".join(response.streaming_content), b"owned media")

    def test_anonymous_request_redirects_to_signin(self):
        response = self.client.get(reverse("protected_media", args=[self.relative_path]))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/signin/", response["Location"])

    def test_other_user_cannot_download_owned_media_file(self):
        self.assertTrue(self.client.login(email=self.other_user.email, password="TestPass123!"))

        response = self.client.get(reverse("protected_media", args=[self.relative_path]))

        self.assertEqual(response.status_code, 404)

    def test_invalid_uuid_path_returns_404(self):
        self.assertTrue(self.client.login(email=self.user.email, password="TestPass123!"))

        response = self.client.get(reverse("protected_media", args=["not-a-uuid/output/owned.txt"]))

        self.assertEqual(response.status_code, 404)

    def test_missing_owned_artifact_returns_404(self):
        self.assertTrue(self.client.login(email=self.user.email, password="TestPass123!"))

        response = self.client.get(
            reverse("protected_media", args=[f"{self.run_uuid}/output/missing.txt"])
        )

        self.assertEqual(response.status_code, 404)

    def test_traversal_path_does_not_escape_media_root(self):
        self.assertTrue(self.client.login(email=self.user.email, password="TestPass123!"))
        outside_file = self.temp_root / "secret.txt"
        outside_file.write_bytes(b"outside media root")

        response = self.client.get(f"/media/{self.run_uuid}/../../secret.txt")

        self.assertEqual(response.status_code, 404)
