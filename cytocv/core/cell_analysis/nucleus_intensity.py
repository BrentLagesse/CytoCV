import numpy as np

from core.image_processing import calculate_intensity_mask
from core.models import Contour
from core.services.canonical_contours import (
    CELL_MASK_KEY,
    get_canonical_blue_slots,
    load_cell_mask,
)
from .analysis import Analysis


class NucleusIntensity(Analysis):
    name = 'Nucleus Intensity'

    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image=None,
        green_image=None,
        puncta_line_width_input=None,
        cen_dot_distance=0,
        cen_dot_proximity_radius=13,
    ):
        """Calculate green-channel intensity within the nucleus and cell regions."""

        green_intensity_image = self.preprocessed_images.get_image('raw_green')
        if green_intensity_image is None:
            green_intensity_image = self.preprocessed_images.get_image('green_no_bg')
        if green_intensity_image is None:
            green_intensity_image = self.preprocessed_images.get_image('green')

        if green_intensity_image is None:
            self._set_defaults()
            return

        shape = green_intensity_image.shape[:2]

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

        nucleus_intensity = float(calculate_intensity_mask(green_intensity_image, nucleus_mask))
        cell_intensity = float(calculate_intensity_mask(green_intensity_image, cell_mask))

        self.cp.nucleus_intensity[Contour.CONTOUR.name] = int(nucleus_intensity)
        self.cp.nucleus_total_points = int(np.count_nonzero(nucleus_mask))
        self.cp.nucleus_intensity_sum = nucleus_intensity
        self.cp.cell_intensity = int(cell_intensity)
        self.cp.cell_total_points = int(np.count_nonzero(cell_mask))
        self.cp.cell_pair_intensity_sum = cell_intensity
        self.cp.cytoplasmic_intensity = cell_intensity - nucleus_intensity

    def _set_defaults(self):
        self.cp.nucleus_intensity[Contour.CONTOUR.name] = 0
        self.cp.nucleus_total_points = 0
        self.cp.nucleus_intensity_sum = 0.0
        self.cp.cell_intensity = 0
        self.cp.cell_total_points = 0
        self.cp.cell_pair_intensity_sum = 0.0
        self.cp.cytoplasmic_intensity = 0.0
