from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase
import numpy as np
import tifffile

from core.metadata_processing.tiff_scale_parser import extract_tiff_scale_metadata


class TiffScaleParserTests(SimpleTestCase):
    def test_missing_physical_scale_metadata_returns_missing(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "no_scale.tif"
            tifffile.imwrite(
                path,
                np.ones((4, 5, 6), dtype=np.uint16),
                photometric="minisblack",
                imagej=True,
                metadata={"mode": "composite"},
            )

            payload = extract_tiff_scale_metadata(path)

        self.assertEqual(payload["status"], "missing")
        self.assertIsNone(payload["metadata_um_per_px"])

    def test_standard_resolution_tags_produce_scale(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "standard_scale.tif"
            tifffile.imwrite(
                path,
                np.ones((4, 5, 6), dtype=np.uint16),
                photometric="minisblack",
                resolution=(10000, 10000),
                resolutionunit="CENTIMETER",
            )

            payload = extract_tiff_scale_metadata(path)

        self.assertEqual(payload["status"], "ok")
        self.assertAlmostEqual(payload["metadata_um_per_px"], 1.0, places=6)
        self.assertAlmostEqual(payload["dx"], 1.0, places=6)
        self.assertAlmostEqual(payload["dy"], 1.0, places=6)

    def test_imagej_unit_and_resolution_produce_scale(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "imagej_scale.tif"
            tifffile.imwrite(
                path,
                np.ones((4, 5, 6), dtype=np.uint16),
                photometric="minisblack",
                imagej=True,
                metadata={"unit": "um"},
                resolution=(10, 10),
            )

            payload = extract_tiff_scale_metadata(path)

        self.assertEqual(payload["status"], "ok")
        self.assertAlmostEqual(payload["metadata_um_per_px"], 0.1, places=6)
        self.assertAlmostEqual(payload["dx"], 0.1, places=6)
        self.assertAlmostEqual(payload["dy"], 0.1, places=6)
