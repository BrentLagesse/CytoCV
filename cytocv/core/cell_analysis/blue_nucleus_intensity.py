import logging

import numpy as np
from cv2_rolling_ball import subtract_background_rolling_ball

from core.image_processing import calculate_intensity_mask
from core.services.canonical_contours import (
    CELL_MASK_KEY,
    get_canonical_blue_slots,
    load_cell_mask,
)
from .analysis import Analysis

logger = logging.getLogger(__name__)


class BlueNucleusIntensity(Analysis):
    name = "BlueNucleusIntensity"

    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image=None,
        green_image=None,
        puncta_line_width_input=None,
        cen_dot_distance=0,
        cen_dot_collinearity_threshold=66,
        cen_dot_proximity_radius=13,
    ):
        """Calculate blue-channel intensity within the nucleus and cell regions."""

        gray_blue = self.preprocessed_images.get_image("gray_blue")
        if gray_blue is None:
            self._set_defaults()
            return

        gray_blue_no_bg, _background = subtract_background_rolling_ball(
            gray_blue,
            50,
            light_background=False,
            use_paraboloid=False,
            do_presmooth=True,
        )

        shape = gray_blue_no_bg.shape[:2]

        blue_slots = get_canonical_blue_slots(contours_data, shape, limit=1)
        if not blue_slots:
            self._set_defaults()
            return

        nucleus_mask = blue_slots[0].mask

        cell_mask = contours_data.get(CELL_MASK_KEY)
        if cell_mask is None or cell_mask.shape[:2] != shape or not np.any(cell_mask):
            cell_mask = load_cell_mask(
                self.cp.image_name, self.cp.cell_id, self.output_dir, shape,
            )

        nucleus_intensity = float(calculate_intensity_mask(gray_blue_no_bg, nucleus_mask))
        cell_intensity = float(calculate_intensity_mask(gray_blue_no_bg, cell_mask))

        logger.debug("Blue nucleus intensity sum for cell %s: %s", self.cp.cell_id, nucleus_intensity)
        logger.debug(
            "Blue cellular intensity sum for cell %s: %s",
            self.cp.cell_id,
            cell_intensity,
        )

        self.cp.nucleus_intensity_sum_blue = nucleus_intensity
        self.cp.cell_pair_intensity_sum_blue = cell_intensity
        self.cp.cytoplasmic_intensity_blue = cell_intensity - nucleus_intensity

    def _set_defaults(self):
        self.cp.nucleus_intensity_sum_blue = 0.0
        self.cp.cell_pair_intensity_sum_blue = 0.0
        self.cp.cytoplasmic_intensity_blue = 0.0
