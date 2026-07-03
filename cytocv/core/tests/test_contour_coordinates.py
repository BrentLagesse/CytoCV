"""Protect contour center coordinate storage and unit conversion contracts."""

from django.test import SimpleTestCase

from core.services.contour_coordinates import (
    BLUE_CONTOUR_PREFIX,
    apply_contour_center_context,
    build_contour_center_context,
    clear_contour_center_properties,
    contour_center_from_properties,
    format_contour_center_payload,
    store_contour_center,
    transform_local_center_to_main_bottom_left,
)


class ContourCoordinateHelpersTests(SimpleTestCase):
    def test_transform_local_center_to_main_bottom_left_origin(self):
        center = transform_local_center_to_main_bottom_left(
            (5.5, 4.0),
            crop_top_px=10,
            crop_left_px=20,
            main_image_height_px=100,
            main_image_width_px=200,
        )

        self.assertEqual(center, (25.5, 85.0))

    def test_transform_uses_bottom_left_pixel_center_convention(self):
        top_left = transform_local_center_to_main_bottom_left(
            (0, 0),
            crop_top_px=0,
            crop_left_px=0,
            main_image_height_px=8,
            main_image_width_px=8,
        )
        bottom_left = transform_local_center_to_main_bottom_left(
            (0, 0),
            crop_top_px=7,
            crop_left_px=0,
            main_image_height_px=8,
            main_image_width_px=8,
        )

        self.assertEqual(top_left, (0.0, 7.0))
        self.assertEqual(bottom_left, (0.0, 0.0))

    def test_transform_rejects_invalid_or_out_of_bounds_values(self):
        self.assertIsNone(
            transform_local_center_to_main_bottom_left(
                (float("nan"), 1),
                crop_top_px=0,
                crop_left_px=0,
                main_image_height_px=10,
            )
        )
        self.assertIsNone(
            transform_local_center_to_main_bottom_left(
                (12, 1),
                crop_top_px=0,
                crop_left_px=0,
                main_image_height_px=10,
                main_image_width_px=10,
            )
        )
        self.assertIsNone(
            transform_local_center_to_main_bottom_left(
                (1, 12),
                crop_top_px=0,
                crop_left_px=0,
                main_image_height_px=10,
                main_image_width_px=10,
            )
        )

    def test_store_and_clear_contour_center_properties(self):
        context = build_contour_center_context(
            crop_origin=(3, 4),
            main_image_shape=(20, 30),
        )
        properties = apply_contour_center_context({}, context)
        properties = store_contour_center(
            properties,
            BLUE_CONTOUR_PREFIX,
            (2.0, 5.0),
            context,
        )

        self.assertEqual(
            contour_center_from_properties(properties, BLUE_CONTOUR_PREFIX),
            {"x_px": 6.0, "y_px": 11.0},
        )
        self.assertEqual(properties["contour_center_origin"], "main_image_bottom_left")
        self.assertEqual(
            properties["contour_center_method"],
            "filled_mask_geometric_centroid",
        )

        cleared = clear_contour_center_properties(properties, (BLUE_CONTOUR_PREFIX,))
        self.assertIsNone(contour_center_from_properties(cleared, BLUE_CONTOUR_PREFIX))

    def test_format_contour_center_payload_converts_to_micrometers(self):
        payload = {"x_px": 10.0, "y_px": 20.0}

        self.assertEqual(
            format_contour_center_payload(
                payload,
                unit="px",
                x_um_per_px=0.5,
                y_um_per_px=0.25,
            ),
            "10.000, 20.000",
        )
        self.assertEqual(
            format_contour_center_payload(
                payload,
                unit="um",
                x_um_per_px=0.5,
                y_um_per_px=0.25,
            ),
            "5.000, 5.000",
        )

    def test_format_contour_center_payload_rejects_missing_values(self):
        self.assertEqual(
            format_contour_center_payload(
                None,
                unit="px",
                x_um_per_px=0.5,
                y_um_per_px=0.25,
            ),
            "N/A",
        )
        self.assertEqual(
            format_contour_center_payload(
                {"x_px": "bad", "y_px": 1},
                unit="px",
                x_um_per_px=0.5,
                y_um_per_px=0.25,
            ),
            "N/A",
        )
