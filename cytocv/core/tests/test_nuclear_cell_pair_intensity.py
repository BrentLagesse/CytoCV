from pathlib import Path
from types import SimpleNamespace
import tempfile

from django.test import SimpleTestCase
import cv2
import numpy as np

from core.cell_analysis import NuclearCellPairIntensity
from core.image_processing import GrayImage


class NuclearCellPairIntensityPluginTests(SimpleTestCase):
    def _write_outline(self, output_dir: Path, image_stem: str = "test", cell_id: int = 1) -> None:
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
            plugin.calculate_statistics({}, contours_data, red_debug, green_debug, 1, 37)
            return cp, red_debug, green_debug

    def test_red_nucleus_sets_expected_contour_and_measurement_channels(self):
        cp, _, _ = self._run_plugin("red_nucleus")
        self.assertEqual(cp.properties["nuclear_cell_pair_contour_channel"], "Red")
        self.assertEqual(cp.properties["nuclear_cell_pair_measurement_channel"], "Green")
        self.assertEqual(cp.properties["nuclear_cell_pair_mode"], "red_nucleus")
        self.assertEqual(cp.properties["nuclear_cell_pair_status"], "ok")
        self.assertEqual(cp.properties["nuclear_cell_pair_contour_source"], "canonical_slot_1")

    def test_green_nucleus_sets_expected_contour_and_measurement_channels(self):
        cp, _, _ = self._run_plugin("green_nucleus")
        self.assertEqual(cp.properties["nuclear_cell_pair_contour_channel"], "Green")
        self.assertEqual(cp.properties["nuclear_cell_pair_measurement_channel"], "Red")
        self.assertEqual(cp.properties["nuclear_cell_pair_mode"], "green_nucleus")
        self.assertEqual(cp.properties["nuclear_cell_pair_status"], "ok")
        self.assertEqual(cp.properties["nuclear_cell_pair_contour_source"], "canonical_slot_1")

    def test_debug_overlay_is_disabled_even_when_precomputed_contour_exists(self):
        _, red_debug, green_debug = self._run_plugin("red_nucleus")
        self.assertFalse(np.any(red_debug > 0))
        self.assertFalse(np.any(green_debug > 0))

    def test_hard_cutoff_marks_no_nucleus_contour_without_fallback(self):
        cp, red_debug, green_debug = self._run_plugin("red_nucleus", include_precomputed=False)
        self.assertEqual(cp.properties["nuclear_cell_pair_status"], "no_nucleus_contour")
        self.assertEqual(cp.properties["nuclear_cell_pair_contour_source"], "canonical_slot_1")
        self.assertEqual(cp.nucleus_intensity_sum, 0.0)
        self.assertEqual(cp.cell_pair_intensity_sum, 0.0)
        self.assertEqual(cp.cytoplasmic_intensity, 0.0)
        self.assertFalse(np.any(red_debug > 0))
        self.assertFalse(np.any(green_debug > 0))

    def test_measurement_channel_uses_raw_values_while_contour_uses_processed_channel(self):
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

        self.assertEqual(cp.nucleus_intensity_sum, float(np.sum(raw_red[nucleus_mask > 0])))
        self.assertEqual(cp.cell_pair_intensity_sum, float(np.sum(raw_red[cell_mask > 0])))
