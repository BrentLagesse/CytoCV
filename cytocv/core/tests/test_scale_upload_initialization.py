"""Integration tests for upload-time per-file scale initialization."""

from __future__ import annotations

from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.metadata_processing.error_handling.dv_validation import DVValidationResult
from core.models import UploadedImage, UploadPreparationJob
from core.services.upload_preparation import run_upload_preparation_job


class UploadScaleInitializationTests(TestCase):
    def setUp(self):
        self.client.defaults["HTTP_X_REQUESTED_WITH"] = "XMLHttpRequest"
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="upload-scale@example.com",
            password="TestPass123!",
        )
        self.assertTrue(
            self.client.login(
                email="upload-scale@example.com",
                password="TestPass123!",
            )
        )

    def _post_upload(
        self,
        *,
        metadata_payload: dict,
        use_metadata_scale: bool,
        puncta_line_mode: str = "red_puncta",
        extra_payload: dict | None = None,
    ) -> UploadedImage:
        upload_file = SimpleUploadedFile(
            "sample.dv",
            b"fake-dv-data",
            content_type="application/octet-stream",
        )
        valid_result = DVValidationResult(
            is_valid=True,
            layer_count=4,
            missing_channels=set(),
            required_channels={"DIC"},
        )

        with TemporaryDirectory() as temp_media:
            with override_settings(MEDIA_ROOT=temp_media):
                with patch(
                    "core.services.upload_preparation.validate_dv_file",
                    return_value=valid_result,
                ):
                    with patch(
                        "core.services.upload_preparation.extract_dv_scale_metadata",
                        return_value=metadata_payload,
                    ):
                        with patch(
                            "core.services.upload_preparation.extract_channel_config",
                            return_value={
                                "DIC": 0,
                                "channel_blue": 1,
                                "channel_red": 2,
                                "channel_green": 3,
                            },
                        ):
                            with patch(
                                "core.services.upload_preparation.generate_preview_assets",
                                return_value=None,
                            ):
                                post_data = {
                                    "files": [upload_file],
                                    "selected_analysis": ["PunctaDistance"],
                                    "stats_puncta_line_width_value": "1",
                                    "stats_cen_dot_distance_value": "37",
                                    "stats_puncta_line_width_unit": "px",
                                    "stats_cen_dot_distance_unit": "px",
                                    "puncta_line_mode": puncta_line_mode,
                                    "stats_microns_per_pixel": "0.2",
                                    "stats_use_metadata_scale": "1" if use_metadata_scale else "0",
                                }
                                if extra_payload:
                                    post_data.update(extra_payload)
                                response = self.client.post(
                                    reverse("experiment"),
                                    data=post_data,
                                )
                                self.assertEqual(response.status_code, 200)
                                payload = response.json()
                                self.assertIn("job_uuid", payload)
                                job = UploadPreparationJob.objects.get(
                                    job_uuid=payload["job_uuid"]
                                )
                                run_upload_preparation_job(job)

        return UploadedImage.objects.order_by("-uuid").first()

    def test_upload_initializes_scale_info_from_metadata_when_enabled(self):
        uploaded = self._post_upload(
            metadata_payload={
                "metadata_um_per_px": 0.11,
                "status": "ok",
                "dx": 0.11,
                "dy": 0.11,
                "dz": 0.2,
                "note": "",
            },
            use_metadata_scale=True,
        )
        self.assertIsNotNone(uploaded)
        self.assertEqual(uploaded.scale_info.get("source"), "metadata")
        self.assertAlmostEqual(uploaded.scale_info.get("effective_um_per_px"), 0.11, places=6)
        self.assertTrue(uploaded.scale_info.get("prefer_metadata"))

    def test_upload_uses_manual_fallback_when_metadata_invalid(self):
        uploaded = self._post_upload(
            metadata_payload={
                "metadata_um_per_px": None,
                "status": "invalid",
                "dx": None,
                "dy": None,
                "dz": None,
                "note": "invalid",
            },
            use_metadata_scale=True,
        )
        self.assertIsNotNone(uploaded)
        self.assertEqual(uploaded.scale_info.get("source"), "manual_fallback")
        self.assertAlmostEqual(uploaded.scale_info.get("effective_um_per_px"), 0.2, places=6)

    def test_upload_uses_manual_global_when_metadata_mode_disabled(self):
        uploaded = self._post_upload(
            metadata_payload={
                "metadata_um_per_px": 0.11,
                "status": "ok",
                "dx": 0.11,
                "dy": 0.11,
                "dz": 0.2,
                "note": "",
            },
            use_metadata_scale=False,
        )
        self.assertIsNotNone(uploaded)
        self.assertEqual(uploaded.scale_info.get("source"), "manual_global")
        self.assertAlmostEqual(uploaded.scale_info.get("effective_um_per_px"), 0.2, places=6)
        self.assertFalse(uploaded.scale_info.get("prefer_metadata"))

    def test_upload_persists_puncta_line_mode_in_session(self):
        self._post_upload(
            metadata_payload={
                "metadata_um_per_px": 0.11,
                "status": "ok",
                "dx": 0.11,
                "dy": 0.11,
                "dz": 0.2,
                "note": "",
            },
            use_metadata_scale=True,
            puncta_line_mode="green_puncta",
        )

        self.assertEqual(self.client.session.get("puncta_line_mode"), "green_puncta")
        self.assertEqual(self.client.session.get("selected_analysis"), ["PunctaDistance"])
        self.assertTrue(self.client.session.get("signalQuantificationEnabled"))
        self.assertEqual(self.client.session.get("signalQuantificationMode"), "puncta_distance")
        self.assertFalse(self.client.session.get("punctaContourIntensityEnabled"))

    def test_upload_signal_quantification_nuclear_mode_derives_session_selection(self):
        self._post_upload(
            metadata_payload={
                "metadata_um_per_px": 0.11,
                "status": "ok",
                "dx": 0.11,
                "dy": 0.11,
                "dz": 0.2,
                "note": "",
            },
            use_metadata_scale=True,
            extra_payload={
                "selected_analysis": ["PunctaDistance", "GreenRedIntensity", "CENDot"],
                "signalQuantificationEnabled": "true",
                "signalQuantificationMode": "nuclear_cell_pair",
                "punctaContourIntensityEnabled": "true",
                "alternateNucleusDetectionEnabled": "true",
                "nuclear_cell_pair_mode": "red_nucleus",
            },
        )

        self.assertEqual(
            self.client.session.get("selected_analysis"),
            ["NuclearCellPairIntensity"],
        )
        self.assertEqual(self.client.session.get("signalQuantificationMode"), "nuclear_cell_pair")
        self.assertTrue(self.client.session.get("alternateNucleusDetectionEnabled"))
        self.assertEqual(
            self.client.session.get("alternateNucleusDetectionChannel"),
            "channel_red",
        )

    def test_upload_signal_quantification_green_nuclear_mode_derives_session_selection(self):
        self._post_upload(
            metadata_payload={
                "metadata_um_per_px": 0.11,
                "status": "ok",
                "dx": 0.11,
                "dy": 0.11,
                "dz": 0.2,
                "note": "",
            },
            use_metadata_scale=True,
            extra_payload={
                "selected_analysis": ["PunctaDistance", "Biorientation"],
                "signalQuantificationEnabled": "true",
                "signalQuantificationMode": "nuclear_cell_pair",
                "punctaContourIntensityEnabled": "false",
                "alternateNucleusDetectionEnabled": "true",
                "nuclear_cell_pair_mode": "green_nucleus",
            },
        )

        self.assertEqual(
            self.client.session.get("selected_analysis"),
            ["NuclearCellPairIntensity"],
        )
        self.assertEqual(self.client.session.get("signalQuantificationMode"), "nuclear_cell_pair")
        self.assertTrue(self.client.session.get("alternateNucleusDetectionEnabled"))
        self.assertEqual(
            self.client.session.get("alternateNucleusDetectionChannel"),
            "channel_green",
        )

    def test_upload_signal_quantification_nuclear_mode_off_clears_alternate_channel(self):
        self._post_upload(
            metadata_payload={
                "metadata_um_per_px": 0.11,
                "status": "ok",
                "dx": 0.11,
                "dy": 0.11,
                "dz": 0.2,
                "note": "",
            },
            use_metadata_scale=True,
            extra_payload={
                "selected_analysis": ["NuclearCellPairIntensity"],
                "signalQuantificationEnabled": "true",
                "signalQuantificationMode": "nuclear_cell_pair",
                "punctaContourIntensityEnabled": "false",
                "alternateNucleusDetectionEnabled": "false",
                "nuclear_cell_pair_mode": "red_nucleus",
            },
        )

        self.assertEqual(
            self.client.session.get("selected_analysis"),
            ["NuclearCellPairIntensity"],
        )
        self.assertFalse(self.client.session.get("alternateNucleusDetectionEnabled"))
        self.assertIsNone(self.client.session.get("alternateNucleusDetectionChannel"))
