from .analysis import Analysis
import numpy as np
import cv2, os, csv
import logging
from core.models import Contour
from cv2_rolling_ball import subtract_background_rolling_ball

from core.image_processing import calculate_intensity_mask

logger = logging.getLogger(__name__)


class BlueNucleusIntensity(Analysis):
    name = "BlueNucleusIntensity"

    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image=None,
        green_image=None,
        red_line_width_input=None,
        cen_dot_distance=0,
        cen_dot_collinearity_threshold=66,
    ):
        gray_blue = self.preprocessed_images.get_image("gray_blue")
        gray_blue_no_bg, background = subtract_background_rolling_ball(
            gray_blue,
            50,
            light_background=False,
            use_paraboloid=False,
            do_presmooth=True,
        )

        mask_contour = np.zeros(gray_blue.shape, np.uint8)
        cv2.fillPoly(mask_contour, [best_contours["Blue"]], 255)
        pts_contour = np.transpose(np.nonzero(mask_contour))

        outline_filename = os.path.splitext(self.cp.image_name)[0] + '-' + str(self.cp.cell_id) + '.outline'
        mask_file_path = os.path.join(self.output_dir, 'output', outline_filename)

        with open(mask_file_path, 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            border_cells = []
            for row in csvreader:
                border_cells.append([int(row[0]), int(row[1])])

        intensity_sum = 0
        for p in pts_contour:
            intensity_sum += gray_blue_no_bg[p[0]][p[1]]
        logger.debug("Blue nucleus intensity sum for cell %s: %s", self.cp.cell_id, intensity_sum)
        self.cp.nucleus_intensity_sum_blue = float(intensity_sum)

        cell_intensity_sum = 0
        for p in border_cells:
             cell_intensity_sum += gray_blue_no_bg[p[0]][p[1]]
        logger.debug(
            "Blue cellular intensity sum for cell %s: %s",
            self.cp.cell_id,
            cell_intensity_sum,
        )

        self.cp.cellular_intensity_sum_blue = float(cell_intensity_sum)
        self.cp.cytoplasmic_intensity_blue = float(cell_intensity_sum) - float(intensity_sum)
