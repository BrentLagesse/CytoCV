from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import tifffile
from django.test import SimpleTestCase

from core.image_sources import (
    get_image_layer_count,
    is_recognized_image_file,
    is_supported_image_filename,
    load_image_stack,
)


class ImageSourceTests(SimpleTestCase):
    def test_supported_source_extensions_are_case_insensitive(self):
        self.assertTrue(is_supported_image_filename("sample.dv"))
        self.assertTrue(is_supported_image_filename("sample.TIF"))
        self.assertTrue(is_supported_image_filename("sample.tiff"))
        self.assertFalse(is_supported_image_filename("sample.png"))

    def test_single_page_tiff_loads_as_one_layer_stack(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "single.tif"
            tifffile.imwrite(path, np.arange(12, dtype=np.uint16).reshape(3, 4))

            stack = load_image_stack(path)

        self.assertEqual(stack.shape, (1, 3, 4))
        self.assertEqual(stack.dtype, np.uint16)

    def test_multi_page_tiff_loads_channel_first(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "stack.tiff"
            expected = np.arange(4 * 5 * 6, dtype=np.uint16).reshape(4, 5, 6)
            tifffile.imwrite(path, expected, photometric="minisblack")

            stack = load_image_stack(path)
            layer_count = get_image_layer_count(path)
            recognized = is_recognized_image_file(path)

        np.testing.assert_array_equal(stack, expected)
        self.assertEqual(layer_count, 4)
        self.assertTrue(recognized)

    def test_rgb_tiff_is_not_treated_as_microscopy_layer_stack(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rgb.tif"
            tifffile.imwrite(path, np.zeros((5, 6, 3), dtype=np.uint8), photometric="rgb")

            with self.assertRaises(ValueError):
                load_image_stack(path)
            self.assertFalse(is_recognized_image_file(path))
