"""Unit tests for upload-length conversion helpers."""

from django.test import SimpleTestCase

from core.views.upload_images import (
    _convert_length_to_pixels,
    _normalize_length_unit,
    _parse_positive_float,
)


class UploadLengthScaleHelperTests(SimpleTestCase):
    def test_normalize_length_unit_defaults_to_px(self):
        self.assertEqual(_normalize_length_unit("bad"), "px")
        self.assertEqual(_normalize_length_unit("UM"), "um")

    def test_parse_positive_float_enforces_minimum(self):
        self.assertEqual(_parse_positive_float("0.25", default=0.1, minimum=0.0001), 0.25)
        self.assertEqual(_parse_positive_float("-1", default=0.1, minimum=0.0001), 0.1)
        self.assertEqual(_parse_positive_float("abc", default=0.1, minimum=0.0001), 0.1)

    def test_convert_length_to_pixels_uses_px_value_directly(self):
        self.assertEqual(
            _convert_length_to_pixels(
                5,
                "px",
                minimum_px=1,
                fallback_px=1,
                microns_per_pixel=0.1,
            ),
            5,
        )

    def test_convert_length_to_pixels_converts_um_using_shared_scale(self):
        self.assertEqual(
            _convert_length_to_pixels(
                1.2,
                "um",
                minimum_px=0,
                fallback_px=37,
                microns_per_pixel=0.1,
            ),
            12,
        )

    def test_convert_length_to_pixels_falls_back_on_invalid_scale(self):
        self.assertEqual(
            _convert_length_to_pixels(
                3.0,
                "um",
                minimum_px=1,
                fallback_px=1,
                microns_per_pixel=0.0,
            ),
            1,
        )
