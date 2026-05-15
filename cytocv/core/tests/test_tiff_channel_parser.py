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
