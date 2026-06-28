"""Regression tests for TIFF label metadata and fallback channel ordering."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase
import numpy as np
import tifffile

from core.config import DEFAULT_CHANNEL_CONFIG
from core.metadata_processing.tiff_channel_parser import (
    build_tiff_channel_config_from_labels,
    extract_tiff_channel_config,
)


class TiffChannelParserTests(SimpleTestCase):
    def test_softworx_imagej_labels_map_complete_channel_order(self):
        labels = [
            "2021_1028_M2208_001_PRJ_w625.tif\nSoftware: Source: softWoRx\n",
            "2021_1028_M2208_001_PRJ_w435.tif\nSoftware: Source: softWoRx\n",
            "2021_1028_M2208_001_PRJ_w525.tif\nSoftware: Source: softWoRx\n",
            "2021_1028_M2208_001_R3D_REF.tif\nSoftware: Source: softWoRx\n",
        ]

        config = build_tiff_channel_config_from_labels(labels)

        self.assertEqual(
            config,
            {
                "channel_red": 0,
                "channel_blue": 1,
                "channel_green": 2,
                "DIC": 3,
            },
        )

    def test_softworx_imagej_labels_map_different_valid_order(self):
        labels = [
            "sample_PRJ_w625.tif",
            "sample_PRJ_w525.tif",
            "sample_PRJ_w435.tif",
            "sample_R3D_REF.tif",
        ]

        config = build_tiff_channel_config_from_labels(labels)

        self.assertEqual(
            config,
            {
                "channel_red": 0,
                "channel_green": 1,
                "channel_blue": 2,
                "DIC": 3,
            },
        )

    def test_three_channel_labels_map_when_one_non_dic_channel_is_missing(self):
        labels = [
            "sample_R3D_REF.tif",
            "sample_PRJ_w435.tif",
            "sample_PRJ_w625.tif",
        ]

        config = build_tiff_channel_config_from_labels(labels)

        self.assertEqual(
            config,
            {
                "DIC": 0,
                "channel_blue": 1,
                "channel_red": 2,
            },
        )

    def test_ambiguous_labels_return_no_metadata_config(self):
        labels = [
            "sample_PRJ_w625.tif",
            "sample_PRJ_w625_duplicate.tif",
            "sample_PRJ_w525.tif",
            "sample_R3D_REF.tif",
        ]

        self.assertIsNone(build_tiff_channel_config_from_labels(labels))

    def test_unlabeled_tiff_uses_default_channel_config(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "unlabeled.tif"
            tifffile.imwrite(
                path,
                np.ones((4, 5, 6), dtype=np.uint16),
                photometric="minisblack",
            )

            config = extract_tiff_channel_config(path)

        self.assertEqual(config, DEFAULT_CHANNEL_CONFIG)

    def test_unlabeled_tiff_uses_configured_fallback_channel_order(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "unlabeled.tif"
            tifffile.imwrite(
                path,
                np.ones((4, 5, 6), dtype=np.uint16),
                photometric="minisblack",
            )

            config = extract_tiff_channel_config(
                path,
                fallback_order=["Green", "DIC", "Red", "Blue"],
            )

        self.assertEqual(
            config,
            {
                "channel_green": 0,
                "DIC": 1,
                "channel_red": 2,
                "channel_blue": 3,
            },
        )

    def test_imagej_label_metadata_is_read_from_tiff(self):
        labels = [
            "sample_PRJ_w625.tif",
            "sample_PRJ_w435.tif",
            "sample_PRJ_w525.tif",
            "sample_R3D_REF.tif",
        ]
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "labeled.tif"
            tifffile.imwrite(
                path,
                np.ones((4, 5, 6), dtype=np.uint16),
                photometric="minisblack",
                imagej=True,
                metadata={"Labels": labels, "mode": "composite"},
            )

            config = extract_tiff_channel_config(path)

        self.assertEqual(
            config,
            {
                "channel_red": 0,
                "channel_blue": 1,
                "channel_green": 2,
                "DIC": 3,
            },
        )

    def test_tiff_skips_metadata_when_disabled(self):
        labels = [
            "sample_PRJ_w625.tif",
            "sample_PRJ_w435.tif",
            "sample_PRJ_w525.tif",
            "sample_R3D_REF.tif",
        ]
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "labeled.tif"
            tifffile.imwrite(
                path,
                np.ones((4, 5, 6), dtype=np.uint16),
                photometric="minisblack",
                imagej=True,
                metadata={"Labels": labels, "mode": "composite"},
            )

            config = extract_tiff_channel_config(
                path,
                prefer_metadata=False,
                fallback_order=["Green", "DIC", "Red", "Blue"],
            )

        self.assertEqual(
            config,
            {
                "channel_green": 0,
                "DIC": 1,
                "channel_red": 2,
                "channel_blue": 3,
            },
        )
