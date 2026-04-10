from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase
from PIL import Image

from core.image_processing.image_operations import load_image
from core.stats_plugins import build_stats_execution_plan
from core.views.segment_image import get_stats


class DummyCellStats:
    def __init__(self, image_names: dict[str, str] | None = None):
        self._image_names = dict(image_names or {})
        self.properties = {}
        self.image_name = "test.dv"
        self.cell_id = 1

    def get_image(self, channel: str, use_id: bool = False, outline: bool = True):
        return self._image_names.get(channel)


class LoadImageCacheTests(SimpleTestCase):
    def test_load_image_uses_cached_images_without_disk_access(self):
        cp = DummyCellStats({"channel_red": "red.png"})
        cached_images = {
            "channel_red": np.full((4, 4, 3), 17, dtype=np.uint8),
        }

        with patch(
            "core.image_processing.image_operations.Image.open",
            side_effect=AssertionError("unexpected disk access"),
        ):
            loaded = load_image(
                cp,
                output_dir="unused",
                required_channels={"channel_red"},
                cached_images=cached_images,
            )

        self.assertTrue(np.array_equal(loaded["red"], cached_images["channel_red"]))
        self.assertTrue(np.array_equal(np.array(loaded["im_red"]), cached_images["channel_red"]))

        loaded["red"][0, 0, 0] = 99
        self.assertEqual(cached_images["channel_red"][0, 0, 0], 17)

    def test_load_image_falls_back_to_disk_for_missing_cached_channel(self):
        cached_mcherry = np.full((3, 3, 3), 9, dtype=np.uint8)
        disk_gfp = np.full((3, 3, 3), 21, dtype=np.uint8)
        cp = DummyCellStats({"channel_red": "red.png", "channel_green": "green.png"})

        with TemporaryDirectory() as temp_dir:
            segmented_dir = Path(temp_dir) / "segmented"
            segmented_dir.mkdir(parents=True, exist_ok=True)
            Image.fromarray(disk_gfp).save(segmented_dir / "green.png")

            with patch(
                "core.image_processing.image_operations.Image.open",
                wraps=Image.open,
            ) as image_open:
                loaded = load_image(
                    cp,
                    output_dir=temp_dir,
                    required_channels={"channel_red", "channel_green"},
                    cached_images={"channel_red": cached_mcherry},
                )

        self.assertEqual(image_open.call_count, 1)
        self.assertTrue(np.array_equal(loaded["red"], cached_mcherry))
        self.assertTrue(np.array_equal(loaded["green"], disk_gfp))


class GetStatsCacheTests(SimpleTestCase):
    @staticmethod
    def _build_conf(output_dir: str, analysis: list[str] | None = None) -> dict:
        return {
            "input_dir": output_dir,
            "output_dir": output_dir,
            "kernel_size": 3,
            "puncta_line_width": 1,
            "kernel_deviation": 1,
            "arrested": "Metaphase Arrested",
            "analysis": list(analysis or []),
            "nuclear_cell_pair_mode": "green_nucleus",
        }

    def test_get_stats_uses_cached_images_for_no_analysis_path(self):
        cp = DummyCellStats()
        cached_images = {
            "channel_red": np.full((6, 6, 3), 40, dtype=np.uint8),
        }
        execution_plan = build_stats_execution_plan(["UnknownPlugin"])

        with TemporaryDirectory() as temp_dir, patch(
            "core.image_processing.image_operations.Image.open",
            side_effect=AssertionError("unexpected disk access"),
        ):
            debug_mcherry, debug_gfp, debug_dapi = get_stats(
                cp,
                self._build_conf(temp_dir, ["UnknownPlugin"]),
                execution_plan,
                1,
                37,
                66,
                cached_images=cached_images,
            )

        self.assertEqual(debug_mcherry.size, (6, 6))
        self.assertEqual(debug_gfp.size, (6, 6))
        self.assertEqual(debug_dapi.size, (6, 6))

    def test_get_stats_keeps_missing_required_channel_behavior_with_cached_images(self):
        cp = DummyCellStats()
        cached_images = {
            "channel_green": np.full((5, 5, 3), 28, dtype=np.uint8),
        }
        execution_plan = build_stats_execution_plan(["BlueNucleusIntensity"])

        with TemporaryDirectory() as temp_dir, patch(
            "core.image_processing.image_operations.Image.open",
            side_effect=AssertionError("unexpected disk access"),
        ):
            debug_mcherry, debug_gfp, debug_dapi = get_stats(
                cp,
                self._build_conf(temp_dir, ["BlueNucleusIntensity"]),
                execution_plan,
                1,
                37,
                66,
                cached_images=cached_images,
            )

        self.assertEqual(debug_mcherry.size, (5, 5))
        self.assertEqual(debug_gfp.size, (5, 5))
        self.assertEqual(debug_dapi.size, (5, 5))
        self.assertEqual(getattr(cp, "blue_contour_size", None), 0.0)

