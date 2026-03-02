from pathlib import Path
from types import SimpleNamespace
import tempfile

from django.test import SimpleTestCase
import numpy as np

from core.cell_analysis.NuclearCellularIntensity import NuclearCellularIntensity
from core.image_processing import GrayImage


class NuclearCellularIntensityPluginTests(SimpleTestCase):
    def _write_outline(self, output_dir: Path, image_stem: str = "test", cell_id: int = 1) -> None:
        output_path = output_dir / "output"
        output_path.mkdir(parents=True, exist_ok=True)
        outline_path = output_path / f"{image_stem}-{cell_id}.outline"
        with outline_path.open("w", encoding="utf-8") as handle:
            for y in range(4, 20):
                for x in range(4, 20):
                    handle.write(f"{y},{x}\n")

    def _build_gray_images(self) -> GrayImage:
        mcherry = np.zeros((24, 24), dtype=np.uint8)
        gfp = np.zeros((24, 24), dtype=np.uint8)
        mcherry[7:18, 7:18] = 220
        gfp[6:17, 6:17] = 210
        return GrayImage(
            img={
                "mCherry_no_bg": mcherry,
                "gray_mcherry": mcherry,
                "GFP_no_bg": gfp,
                "GFP": gfp,
            }
        )

    def _run_plugin(self, mode: str):
        plugin = NuclearCellularIntensity()
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={"nuclear_cellular_mode": mode},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_outline(output_dir)
            preprocessed = self._build_gray_images()
            red_debug = np.zeros((24, 24, 3), dtype=np.uint8)
            green_debug = np.zeros((24, 24, 3), dtype=np.uint8)
            plugin.setting_up(cp, preprocessed, str(output_dir))
            plugin.calculate_statistics({}, {}, red_debug, green_debug, 1, 37)
            return cp, red_debug, green_debug

    def test_red_nucleus_sets_expected_contour_and_measurement_channels(self):
        cp, _, _ = self._run_plugin("red_nucleus")
        self.assertEqual(cp.properties["nuclear_cellular_contour_channel"], "mCherry")
        self.assertEqual(cp.properties["nuclear_cellular_measurement_channel"], "GFP")
        self.assertEqual(cp.properties["nuclear_cellular_mode"], "red_nucleus")
        self.assertEqual(cp.properties["nuclear_cellular_status"], "ok")

    def test_green_nucleus_sets_expected_contour_and_measurement_channels(self):
        cp, _, _ = self._run_plugin("green_nucleus")
        self.assertEqual(cp.properties["nuclear_cellular_contour_channel"], "GFP")
        self.assertEqual(cp.properties["nuclear_cellular_measurement_channel"], "mCherry")
        self.assertEqual(cp.properties["nuclear_cellular_mode"], "green_nucleus")
        self.assertEqual(cp.properties["nuclear_cellular_status"], "ok")

    def test_debug_overlay_is_white_dashed_not_yellow(self):
        _, red_debug, green_debug = self._run_plugin("red_nucleus")

        has_white_red = np.any(
            (red_debug[:, :, 0] > 200) & (red_debug[:, :, 1] > 200) & (red_debug[:, :, 2] > 200)
        )
        has_white_green = np.any(
            (green_debug[:, :, 0] > 200) & (green_debug[:, :, 1] > 200) & (green_debug[:, :, 2] > 200)
        )
        self.assertTrue(has_white_red)
        self.assertTrue(has_white_green)

        has_yellow_red = np.any(
            (red_debug[:, :, 0] < 40) & (red_debug[:, :, 1] > 200) & (red_debug[:, :, 2] > 200)
        )
        has_yellow_green = np.any(
            (green_debug[:, :, 0] < 40) & (green_debug[:, :, 1] > 200) & (green_debug[:, :, 2] > 200)
        )
        self.assertFalse(has_yellow_red)
        self.assertFalse(has_yellow_green)
