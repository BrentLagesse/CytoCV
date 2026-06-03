from pathlib import Path
from types import SimpleNamespace
import tempfile

from django.test import SimpleTestCase
import cv2
import numpy as np

from core.cell_analysis import NuclearCellPairIntensity
from core.cell_analysis.nuclear_cell_pair_legacy_scaled import (
    LEGACY_EXACT_CELL_PAIR_MASK_KEY,
)
from core.channel_roles import CHANNEL_ROLE_GREEN, CHANNEL_ROLE_RED
from core.image_processing import GrayImage
from core.services.canonical_contours import build_canonical_contour_payload
from core.services.nuclear_cell_pair_contour_mode import (
    NUCLEAR_CELL_PAIR_ALTERNATE_GREEN_MASK_KEY,
)


class NuclearCellPairIntensityPluginTests(SimpleTestCase):
    def _write_outline(
        self, output_dir: Path, image_stem: str = "test", cell_id: int = 1
    ) -> None:
        output_path = output_dir / "output"
        output_path.mkdir(parents=True, exist_ok=True)
        outline_path = output_path / f"{image_stem}-{cell_id}.outline"
        with outline_path.open("w", encoding="utf-8") as handle:
            for vy, vx in ((4, 4), (4, 19), (19, 19), (19, 4)):
                handle.write(f"{vy},{vx}\n")

    def _build_gray_images(self) -> GrayImage:
        mcherry = np.zeros((24, 24), dtype=np.uint8)
        gfp = np.zeros((24, 24), dtype=np.uint8)
        mcherry[7:18, 7:18] = 220
        gfp[6:17, 6:17] = 210
        return GrayImage(
            img={
                "red_no_bg": mcherry,
                "gray_red": mcherry,
                "green_no_bg": gfp,
                "green": gfp,
            }
        )

    @staticmethod
    def _rect_contour(x1: int, y1: int, x2: int, y2: int):
        return np.array(
            [[[x1, y1]], [[x2, y1]], [[x2, y2]], [[x1, y2]]],
            dtype=np.int32,
        )

    def _run_plugin(self, mode: str, *, include_precomputed: bool = True):
        plugin = NuclearCellPairIntensity()
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={"nuclear_cell_pair_mode": mode},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_outline(output_dir)
            preprocessed = self._build_gray_images()
            red_debug = np.zeros((24, 24, 3), dtype=np.uint8)
            green_debug = np.zeros((24, 24, 3), dtype=np.uint8)
            contours_data = {"dot_contours": [], "contours_green": []}
            if include_precomputed:
                contour = self._rect_contour(8, 8, 16, 16)
                if mode == "red_nucleus":
                    contours_data["dot_contours"] = [contour]
                else:
                    contours_data["contours_green"] = [contour]
            plugin.setting_up(cp, preprocessed, str(output_dir))
            plugin.calculate_statistics(
                {}, contours_data, red_debug, green_debug, 1, 37
            )
            return cp, red_debug, green_debug

    def _run_plugin_with_alternate_target(self, mode: str, alternate_channel: str):
        plugin = NuclearCellPairIntensity()
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={
                "nuclear_cell_pair_mode": mode,
                "alternate_nucleus_detection_channel": alternate_channel,
            },
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_outline(output_dir)
            preprocessed = self._build_gray_images()
            standard_contour = self._rect_contour(8, 8, 12, 12)
            alternate_contour = self._rect_contour(8, 8, 16, 16)
            contours_data = build_canonical_contour_payload(
                {
                    "dot_contours": [standard_contour],
                    "contours_green": [standard_contour],
                    "alternate_nucleus_contours_red": [alternate_contour],
                    "alternate_nucleus_contours_green": [alternate_contour],
                },
                image_name="test.dv",
                cell_id=1,
                output_dir=str(output_dir),
                shape=(24, 24),
            )
            plugin.setting_up(cp, preprocessed, str(output_dir))
            plugin.calculate_statistics(
                {},
                contours_data,
                np.zeros((24, 24, 3), dtype=np.uint8),
                np.zeros((24, 24, 3), dtype=np.uint8),
                1,
                37,
            )
            return cp, preprocessed, standard_contour, alternate_contour

    def test_red_nucleus_sets_expected_contour_and_measurement_channels(self):
        cp, _, _ = self._run_plugin("red_nucleus")
        self.assertEqual(cp.properties["nuclear_cell_pair_contour_channel"], "Red")
        self.assertEqual(
            cp.properties["nuclear_cell_pair_measurement_channel"], "Green"
        )
        self.assertEqual(cp.properties["nuclear_cell_pair_mode"], "red_nucleus")
        self.assertEqual(cp.properties["nuclear_cell_pair_contour_mode"], "balanced")
        self.assertEqual(cp.properties["nuclear_cell_pair_status"], "ok")
        self.assertEqual(
            cp.properties["nuclear_cell_pair_contour_source"], "canonical_slot_1"
        )

    def test_green_nucleus_sets_expected_contour_and_measurement_channels(self):
        cp, _, _ = self._run_plugin("green_nucleus")
        self.assertEqual(cp.properties["nuclear_cell_pair_contour_channel"], "Green")
        self.assertEqual(cp.properties["nuclear_cell_pair_measurement_channel"], "Red")
        self.assertEqual(cp.properties["nuclear_cell_pair_mode"], "green_nucleus")
        self.assertEqual(cp.properties["nuclear_cell_pair_contour_mode"], "balanced")
        self.assertEqual(cp.properties["nuclear_cell_pair_status"], "ok")
        self.assertEqual(
            cp.properties["nuclear_cell_pair_contour_source"], "canonical_slot_1"
        )

    def test_alternate_detection_targets_red_nucleus_contours_for_red_nucleus_mode(
        self,
    ):
        cp, preprocessed, _, alternate_contour = self._run_plugin_with_alternate_target(
            "red_nucleus",
            CHANNEL_ROLE_RED,
        )
        green_image = preprocessed.get_image("green_no_bg")
        nucleus_mask = np.zeros(green_image.shape, dtype=np.uint8)
        cv2.drawContours(nucleus_mask, [alternate_contour], 0, 255, -1)

        self.assertEqual(
            cp.properties["nuclear_cell_pair_contour_source"],
            "alternate_red_nucleus_slot_1",
        )
        self.assertEqual(
            cp.nucleus_intensity_sum,
            float(np.sum(green_image[nucleus_mask > 0])),
        )

    def test_alternate_detection_targets_green_nucleus_contours_for_green_nucleus_mode(
        self,
    ):
        cp, preprocessed, _, alternate_contour = self._run_plugin_with_alternate_target(
            "green_nucleus",
            CHANNEL_ROLE_GREEN,
        )
        red_image = preprocessed.get_image("red_no_bg")
        nucleus_mask = np.zeros(red_image.shape, dtype=np.uint8)
        cv2.drawContours(nucleus_mask, [alternate_contour], 0, 255, -1)

        self.assertEqual(
            cp.properties["nuclear_cell_pair_contour_source"],
            "alternate_green_nucleus_slot_1",
        )
        self.assertEqual(
            cp.nucleus_intensity_sum,
            float(np.sum(red_image[nucleus_mask > 0])),
        )

    def test_alternate_detection_ignores_unselected_nucleus_channel(self):
        cp, preprocessed, standard_contour, _ = self._run_plugin_with_alternate_target(
            "green_nucleus",
            CHANNEL_ROLE_RED,
        )
        red_image = preprocessed.get_image("red_no_bg")
        nucleus_mask = np.zeros(red_image.shape, dtype=np.uint8)
        cv2.drawContours(nucleus_mask, [standard_contour], 0, 255, -1)

        self.assertEqual(
            cp.properties["nuclear_cell_pair_contour_source"], "canonical_slot_1"
        )
        self.assertEqual(
            cp.nucleus_intensity_sum,
            float(np.sum(red_image[nucleus_mask > 0])),
        )

    def test_alternate_detection_without_alternate_slot_does_not_fallback_to_canonical(
        self,
    ):
        plugin = NuclearCellPairIntensity()
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={
                "nuclear_cell_pair_mode": "red_nucleus",
                "alternate_nucleus_detection_enabled": True,
                "alternate_nucleus_detection_channel": CHANNEL_ROLE_RED,
            },
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_outline(output_dir)
            preprocessed = self._build_gray_images()
            standard_contour = self._rect_contour(8, 8, 16, 16)
            contours_data = build_canonical_contour_payload(
                {
                    "dot_contours": [standard_contour],
                    "contours_green": [],
                },
                image_name="test.dv",
                cell_id=1,
                output_dir=str(output_dir),
                shape=(24, 24),
            )
            red_debug = np.zeros((24, 24, 3), dtype=np.uint8)
            green_debug = np.zeros((24, 24, 3), dtype=np.uint8)
            plugin.setting_up(cp, preprocessed, str(output_dir))
            plugin.calculate_statistics(
                {},
                contours_data,
                red_debug,
                green_debug,
                1,
                37,
            )

        self.assertEqual(
            cp.properties["nuclear_cell_pair_status"], "no_nucleus_contour"
        )
        self.assertEqual(
            cp.properties["nuclear_cell_pair_contour_source"],
            "alternate_red_nucleus_slot_1",
        )
        self.assertEqual(cp.nucleus_intensity_sum, 0.0)
        self.assertFalse(np.any(red_debug > 0))
        self.assertFalse(np.any(green_debug > 0))

    def test_debug_overlay_draws_selected_red_nucleus_contour(self):
        _, red_debug, green_debug = self._run_plugin("red_nucleus")
        red_pixels = np.array([0, 0, 255], dtype=np.uint8)

        self.assertTrue(np.any(np.all(red_debug == red_pixels, axis=2)))
        self.assertTrue(np.any(np.all(green_debug == red_pixels, axis=2)))

    def test_debug_overlay_draws_selected_green_nucleus_contour(self):
        _, red_debug, green_debug = self._run_plugin("green_nucleus")
        green_pixels = np.array([0, 255, 0], dtype=np.uint8)

        self.assertTrue(np.any(np.all(red_debug == green_pixels, axis=2)))
        self.assertTrue(np.any(np.all(green_debug == green_pixels, axis=2)))

    def test_hard_cutoff_marks_no_nucleus_contour_without_fallback(self):
        cp, red_debug, green_debug = self._run_plugin(
            "red_nucleus", include_precomputed=False
        )
        self.assertEqual(
            cp.properties["nuclear_cell_pair_status"], "no_nucleus_contour"
        )
        self.assertEqual(
            cp.properties["nuclear_cell_pair_contour_source"], "canonical_slot_1"
        )
        self.assertEqual(cp.nucleus_intensity_sum, 0.0)
        self.assertEqual(cp.cell_pair_intensity_sum, 0.0)
        self.assertEqual(cp.cytoplasmic_intensity, 0.0)
        self.assertIsNone(cp.nuclear_cytoplasmic_ratio)
        self.assertFalse(np.any(red_debug > 0))
        self.assertFalse(np.any(green_debug > 0))

    def test_measurement_channel_uses_raw_values_while_contour_uses_processed_channel(
        self,
    ):
        plugin = NuclearCellPairIntensity()
        shape = (24, 24)
        processed_green = np.zeros(shape, dtype=np.uint8)
        processed_red = np.zeros(shape, dtype=np.uint8)
        processed_green[8:17, 8:17] = 255
        raw_red = np.zeros(shape, dtype=np.uint16)
        raw_red[4:20, 4:20] = 4000
        preprocessed = GrayImage(
            img={
                "green_no_bg": processed_green,
                "green": processed_green,
                "red_no_bg": processed_red,
                "gray_red": processed_red,
                "raw_red": raw_red,
            }
        )
        contour = self._rect_contour(8, 8, 16, 16)
        nucleus_mask = np.zeros(shape, dtype=np.uint8)
        cv2.drawContours(nucleus_mask, [contour], 0, 255, -1)
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={"nuclear_cell_pair_mode": "green_nucleus"},
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_outline(output_dir)
            cell_mask = np.zeros(shape, dtype=np.uint8)
            cell_mask[4:20, 4:20] = 255
            plugin.setting_up(cp, preprocessed, str(output_dir))
            plugin.calculate_statistics(
                {},
                {"contours_green": [contour], "cell_mask": cell_mask},
                np.zeros((*shape, 3), dtype=np.uint8),
                np.zeros((*shape, 3), dtype=np.uint8),
                1,
                37,
            )

        self.assertEqual(
            cp.nucleus_intensity_sum, float(np.sum(raw_red[nucleus_mask > 0]))
        )
        self.assertEqual(
            cp.cell_pair_intensity_sum, float(np.sum(raw_red[cell_mask > 0]))
        )
        self.assertEqual(
            cp.cytoplasmic_intensity,
            cp.cell_pair_intensity_sum - cp.nucleus_intensity_sum,
        )
        self.assertEqual(
            cp.nuclear_cytoplasmic_ratio,
            cp.nucleus_intensity_sum / cp.cytoplasmic_intensity,
        )

    def test_legacy_scaled_mode_uses_processed_measurement_with_cytocv_masks(self):
        plugin = NuclearCellPairIntensity()
        shape = (24, 24)
        processed_red = np.zeros(shape, dtype=np.uint8)
        processed_green = np.zeros(shape, dtype=np.uint8)
        processed_red[4:20, 4:20] = 7
        processed_red[8:17, 8:17] = 19
        raw_red = np.zeros(shape, dtype=np.uint16)
        raw_red[4:20, 4:20] = 4000
        preprocessed = GrayImage(
            img={
                "green_no_bg": processed_green,
                "green": processed_green,
                "red_no_bg": processed_red,
                "gray_red": processed_red,
                "raw_red": raw_red,
            }
        )
        contour = self._rect_contour(8, 8, 16, 16)
        nucleus_mask = np.zeros(shape, dtype=np.uint8)
        cv2.drawContours(nucleus_mask, [contour], 0, 255, -1)
        cell_mask = np.zeros(shape, dtype=np.uint8)
        cell_mask[4:20, 4:20] = 255
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={
                "nuclear_cell_pair_mode": "green_nucleus",
                "use_legacy_nuclear_cell_pair_pipeline": True,
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            plugin.setting_up(cp, preprocessed, str(output_dir))
            plugin.calculate_statistics(
                {},
                {"contours_green": [contour], "cell_mask": cell_mask},
                np.zeros((*shape, 3), dtype=np.uint8),
                np.zeros((*shape, 3), dtype=np.uint8),
                1,
                37,
            )

        self.assertEqual(
            cp.nucleus_intensity_sum,
            float(np.sum(processed_red[nucleus_mask > 0])),
        )
        self.assertEqual(
            cp.cell_pair_intensity_sum,
            float(np.sum(processed_red[cell_mask > 0])),
        )
        self.assertNotEqual(
            cp.cell_pair_intensity_sum,
            float(np.sum(raw_red[cell_mask > 0])),
        )
        self.assertEqual(
            cp.properties["nuclear_cell_pair_measurement_mode"],
            "legacy_scaled_cytocv_masks",
        )
        self.assertEqual(
            cp.properties["intensity_pixel_source"],
            "legacy_scaled_8bit_crop",
        )
        self.assertTrue(cp.properties["legacy_preserves_channel_identity"])
        self.assertTrue(cp.properties["legacy_preserves_cytocv_cell_mask"])
        self.assertTrue(cp.properties["legacy_preserves_cytocv_contours"])
        self.assertFalse(cp.properties["legacy_copies_yat_channel_collision"])
        self.assertFalse(cp.properties["legacy_copies_yat_outline_summing"])
        self.assertFalse(cp.properties["legacy_copies_yat_contour_selection"])
        self.assertEqual(
            cp.properties["legacy_cell_pair_pixel_support"],
            "filled_cytocv_cell_mask_fallback",
        )
        self.assertTrue(cp.properties["legacy_cell_pair_mask_fallback"])
        self.assertTrue(cp.properties["legacy_uses_filled_cell_mask"])
        self.assertEqual(
            cp.nuclear_cytoplasmic_ratio,
            cp.nucleus_intensity_sum / cp.cytoplasmic_intensity,
        )

    def test_legacy_scaled_mode_uses_exact_label_mask_for_cell_pair_sum(self):
        plugin = NuclearCellPairIntensity()
        shape = (24, 24)
        measurement = np.zeros(shape, dtype=np.uint8)
        measurement[4:20, 4:20] = 5
        measurement[10:18, 10:18] = 17
        contour_image = np.zeros(shape, dtype=np.uint8)
        contour_image[5:19, 5:19] = 255
        raw_red = np.full(shape, 4000, dtype=np.uint16)
        preprocessed = GrayImage(
            img={
                "green_no_bg": contour_image,
                "green": contour_image,
                "red_no_bg": measurement,
                "gray_red": measurement,
                "raw_red": raw_red,
            }
        )
        filled_cell_mask = np.zeros(shape, dtype=np.uint8)
        filled_cell_mask[4:20, 4:20] = 255
        exact_label_mask = np.zeros(shape, dtype=np.uint8)
        exact_label_mask[4:12, 4:20] = 255
        exact_label_mask[15:20, 6:18] = 255
        nucleus_mask = np.zeros(shape, dtype=np.uint8)
        nucleus_mask[8:18, 8:18] = 255
        contours, _ = cv2.findContours(
            nucleus_mask.copy(),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        slot = SimpleNamespace(mask=nucleus_mask, contours=tuple(contours))
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={
                "nuclear_cell_pair_mode": "green_nucleus",
                "use_legacy_nuclear_cell_pair_pipeline": True,
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            plugin.setting_up(cp, preprocessed, str(output_dir))
            plugin.calculate_statistics(
                {},
                {
                    "cell_mask": filled_cell_mask,
                    "canonical_green_slots": [slot],
                    LEGACY_EXACT_CELL_PAIR_MASK_KEY: exact_label_mask,
                },
                np.zeros((*shape, 3), dtype=np.uint8),
                np.zeros((*shape, 3), dtype=np.uint8),
                1,
                37,
            )

        expected_nucleus_mask = cv2.bitwise_and(nucleus_mask, exact_label_mask)
        self.assertEqual(
            cp.cell_pair_intensity_sum,
            float(np.sum(measurement[exact_label_mask > 0])),
        )
        self.assertEqual(
            cp.nucleus_intensity_sum,
            float(np.sum(measurement[expected_nucleus_mask > 0])),
        )
        self.assertEqual(
            cp.nuclear_cytoplasmic_ratio,
            cp.nucleus_intensity_sum / cp.cytoplasmic_intensity,
        )
        self.assertNotEqual(
            cp.cell_pair_intensity_sum,
            float(np.sum(measurement[filled_cell_mask > 0])),
        )
        self.assertEqual(
            cp.properties["legacy_cell_pair_pixel_support"],
            "segmentation_label_pixels",
        )
        self.assertFalse(cp.properties["legacy_cell_pair_mask_fallback"])
        self.assertFalse(cp.properties["legacy_uses_filled_cell_mask"])

    def test_legacy_scaled_mode_falls_back_when_exact_label_mask_shape_differs(self):
        plugin = NuclearCellPairIntensity()
        shape = (24, 24)
        measurement = np.zeros(shape, dtype=np.uint8)
        measurement[4:20, 4:20] = 9
        contour_image = np.zeros(shape, dtype=np.uint8)
        contour_image[4:20, 4:20] = 255
        preprocessed = GrayImage(
            img={
                "green_no_bg": contour_image,
                "green": contour_image,
                "red_no_bg": measurement,
                "gray_red": measurement,
                "raw_red": np.full(shape, 4000, dtype=np.uint16),
            }
        )
        cell_mask = np.zeros(shape, dtype=np.uint8)
        cell_mask[4:20, 4:20] = 255
        wrong_shape_exact_mask = np.ones((12, 12), dtype=np.uint8) * 255
        nucleus_mask = np.zeros(shape, dtype=np.uint8)
        nucleus_mask[8:16, 8:16] = 255
        contours, _ = cv2.findContours(
            nucleus_mask.copy(),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        slot = SimpleNamespace(mask=nucleus_mask, contours=tuple(contours))
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={
                "nuclear_cell_pair_mode": "green_nucleus",
                "use_legacy_nuclear_cell_pair_pipeline": True,
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            plugin.setting_up(cp, preprocessed, str(output_dir))
            plugin.calculate_statistics(
                {},
                {
                    "cell_mask": cell_mask,
                    "canonical_green_slots": [slot],
                    LEGACY_EXACT_CELL_PAIR_MASK_KEY: wrong_shape_exact_mask,
                },
                np.zeros((*shape, 3), dtype=np.uint8),
                np.zeros((*shape, 3), dtype=np.uint8),
                1,
                37,
            )

        self.assertEqual(
            cp.cell_pair_intensity_sum,
            float(np.sum(measurement[cell_mask > 0])),
        )
        self.assertTrue(cp.properties["legacy_cell_pair_mask_fallback"])

    def test_legacy_scaled_mode_still_clips_nucleus_to_cell_mask(self):
        plugin = NuclearCellPairIntensity()
        shape = (24, 24)
        measurement = np.zeros(shape, dtype=np.uint8)
        measurement[2:22, 2:22] = 5
        measurement[2:6, 2:6] = 100
        contour_image = np.zeros(shape, dtype=np.uint8)
        contour_image[2:22, 2:22] = 255
        cell_mask = np.zeros(shape, dtype=np.uint8)
        cell_mask[8:20, 8:20] = 255
        nucleus_mask = np.zeros(shape, dtype=np.uint8)
        nucleus_mask[2:18, 2:18] = 255
        contours, _ = cv2.findContours(
            nucleus_mask.copy(),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        preprocessed = GrayImage(
            img={
                "green_no_bg": contour_image,
                "green": contour_image,
                "red_no_bg": measurement,
                "gray_red": measurement,
                "raw_red": np.full(shape, 4000, dtype=np.uint16),
            }
        )
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={
                "nuclear_cell_pair_mode": "green_nucleus",
                "use_legacy_nuclear_cell_pair_pipeline": True,
            },
        )
        slot = SimpleNamespace(mask=nucleus_mask, contours=tuple(contours))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            plugin.setting_up(cp, preprocessed, str(output_dir))
            plugin.calculate_statistics(
                {},
                {
                    "cell_mask": cell_mask,
                    "canonical_green_slots": [slot],
                },
                np.zeros((*shape, 3), dtype=np.uint8),
                np.zeros((*shape, 3), dtype=np.uint8),
                1,
                37,
            )

        clipped_nucleus = cv2.bitwise_and(nucleus_mask, cell_mask)
        self.assertEqual(
            cp.nucleus_intensity_sum,
            float(np.sum(measurement[clipped_nucleus > 0])),
        )
        self.assertEqual(
            cp.cell_pair_intensity_sum,
            float(np.sum(measurement[cell_mask > 0])),
        )

    def test_alternate_mask_slot_draws_and_measures_all_components_together(self):
        plugin = NuclearCellPairIntensity()
        shape = (24, 24)
        red_measurement = np.zeros(shape, dtype=np.uint16)
        red_measurement[4:20, 4:20] = 10
        red_measurement[7:10, 7:10] = 100
        red_measurement[15:18, 15:18] = 200
        green_contour = np.zeros(shape, dtype=np.uint8)
        green_contour[7:10, 7:10] = 255
        green_contour[15:18, 15:18] = 255
        mask = np.zeros(shape, dtype=np.uint8)
        mask[7:10, 7:10] = 255
        mask[15:18, 15:18] = 255
        preprocessed = GrayImage(
            img={
                "green_no_bg": green_contour,
                "green": green_contour,
                "red_no_bg": red_measurement.astype(np.uint8),
                "gray_red": red_measurement.astype(np.uint8),
                "raw_red": red_measurement,
            }
        )
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={
                "nuclear_cell_pair_mode": "green_nucleus",
                "alternate_nucleus_detection_enabled": True,
                "alternate_nucleus_detection_channel": CHANNEL_ROLE_GREEN,
                "nuclear_cell_pair_contour_mode": "aggressive",
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_outline(output_dir)
            contours_data = build_canonical_contour_payload(
                {
                    "contours_green": [],
                    "dot_contours": [],
                    NUCLEAR_CELL_PAIR_ALTERNATE_GREEN_MASK_KEY: mask,
                },
                image_name="test.dv",
                cell_id=1,
                output_dir=str(output_dir),
                shape=shape,
            )
            red_debug = np.zeros((*shape, 3), dtype=np.uint8)
            green_debug = np.zeros((*shape, 3), dtype=np.uint8)
            plugin.setting_up(cp, preprocessed, str(output_dir))
            plugin.calculate_statistics(
                {},
                contours_data,
                red_debug,
                green_debug,
                1,
                37,
            )

        self.assertEqual(
            cp.properties["nuclear_cell_pair_contour_source"],
            "alternate_green_nucleus_slot_1",
        )
        self.assertEqual(cp.properties["nuclear_cell_pair_contour_mode"], "aggressive")
        self.assertEqual(
            cp.nucleus_intensity_sum, float(np.sum(red_measurement[mask > 0]))
        )
        green_pixels = np.array([0, 255, 0], dtype=np.uint8)
        self.assertTrue(np.any(np.all(red_debug[7:10, 7:10] == green_pixels, axis=2)))
        self.assertTrue(np.any(np.all(red_debug[15:18, 15:18] == green_pixels, axis=2)))

    def test_final_nucleus_mask_is_clipped_to_cell_mask_before_statistics(self):
        plugin = NuclearCellPairIntensity()
        shape = (24, 24)
        measurement = np.zeros(shape, dtype=np.uint16)
        measurement[2:22, 2:22] = 5
        measurement[2:6, 2:6] = 100
        contour_image = np.zeros(shape, dtype=np.uint8)
        contour_image[2:22, 2:22] = 255
        cell_mask = np.zeros(shape, dtype=np.uint8)
        cell_mask[8:20, 8:20] = 255
        nucleus_mask = np.zeros(shape, dtype=np.uint8)
        nucleus_mask[2:18, 2:18] = 255
        contours, _ = cv2.findContours(
            nucleus_mask.copy(),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        preprocessed = GrayImage(
            img={
                "green_no_bg": contour_image,
                "green": contour_image,
                "red_no_bg": measurement.astype(np.uint8),
                "gray_red": measurement.astype(np.uint8),
                "raw_red": measurement,
            }
        )
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={"nuclear_cell_pair_mode": "green_nucleus"},
        )
        slot = SimpleNamespace(mask=nucleus_mask, contours=tuple(contours))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            plugin.setting_up(cp, preprocessed, str(output_dir))
            plugin.calculate_statistics(
                {},
                {
                    "cell_mask": cell_mask,
                    "canonical_green_slots": [slot],
                },
                np.zeros((*shape, 3), dtype=np.uint8),
                np.zeros((*shape, 3), dtype=np.uint8),
                1,
                37,
            )

        clipped_nucleus = cv2.bitwise_and(nucleus_mask, cell_mask)
        self.assertEqual(
            cp.nucleus_intensity_sum,
            float(np.sum(measurement[clipped_nucleus > 0])),
        )
        self.assertEqual(
            cp.cell_pair_intensity_sum,
            float(np.sum(measurement[cell_mask > 0])),
        )
        self.assertEqual(
            cp.cytoplasmic_intensity,
            cp.cell_pair_intensity_sum - cp.nucleus_intensity_sum,
        )
        self.assertEqual(
            cp.nuclear_cytoplasmic_ratio,
            cp.nucleus_intensity_sum / cp.cytoplasmic_intensity,
        )

    def test_ratio_is_none_when_cytoplasmic_intensity_is_zero(self):
        plugin = NuclearCellPairIntensity()
        shape = (24, 24)
        measurement = np.zeros(shape, dtype=np.uint16)
        measurement[8:17, 8:17] = 10
        contour_image = np.zeros(shape, dtype=np.uint8)
        contour_image[8:17, 8:17] = 255
        cell_mask = np.zeros(shape, dtype=np.uint8)
        cell_mask[8:17, 8:17] = 255
        contour = self._rect_contour(8, 8, 16, 16)
        preprocessed = GrayImage(
            img={
                "green_no_bg": contour_image,
                "green": contour_image,
                "red_no_bg": measurement.astype(np.uint8),
                "gray_red": measurement.astype(np.uint8),
                "raw_red": measurement,
            }
        )
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={"nuclear_cell_pair_mode": "green_nucleus"},
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            plugin.setting_up(cp, preprocessed, str(output_dir))
            plugin.calculate_statistics(
                {},
                {"contours_green": [contour], "cell_mask": cell_mask},
                np.zeros((*shape, 3), dtype=np.uint8),
                np.zeros((*shape, 3), dtype=np.uint8),
                1,
                37,
            )

        self.assertEqual(cp.cell_pair_intensity_sum, cp.nucleus_intensity_sum)
        self.assertEqual(cp.cytoplasmic_intensity, 0.0)
        self.assertIsNone(cp.nuclear_cytoplasmic_ratio)
