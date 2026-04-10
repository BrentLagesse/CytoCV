import cv2, os, csv
import numpy as np
from core.models import Contour
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
        cen_dot_collinearity_threshold=0,
    ):
        """
            This function calculate the nucleus intensity within the green image
        """
        gray_green = self.preprocessed_images.get_image('green')
        gray_green_no_bg = self.preprocessed_images.get_image('green_no_bg')

        mask_contour = np.zeros(gray_green.shape, np.uint8)
        cv2.fillPoly(mask_contour, [best_contours['Blue']], 255)
        pts_contour = np.transpose(np.nonzero(mask_contour))

        # Build the expected outline filename:
        # cp.image_name is set (in the get_or_create for CellStatistics) as DV_Name + '.dv',
        # so taking os.path.splitext(cp.image_name)[0] gives the full DV name (e.g. "M3850_001_PRJ")
        outline_filename = os.path.splitext(self.cp.image_name)[0] + '-' + str(self.cp.cell_id) + '.outline'

        # The outline files are stored in the "output" folder (not in a "masks" folder)
        mask_file_path = os.path.join(self.output_dir, 'output', outline_filename)

        with open(mask_file_path, 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            border_cells = []
            for row in csvreader:
                border_cells.append([int(row[0]), int(row[1])])

        # Calculate nucleus intensity inside the best_contour
        intensity_sum = 0
        for p in pts_contour:
            intensity_sum += gray_green_no_bg[p[0]][p[1]]

        # Cast to Python int before saving into the JSON field
        self.cp.nucleus_intensity[Contour.CONTOUR.name] = int(intensity_sum)
        self.cp.nucleus_total_points = len(pts_contour)  # This is usually a Python int already

        self.cp.nucleus_intensity_sum = float(intensity_sum)

        # Calculate cell intensity from the "border_cells" list
        cell_intensity_sum = 0
        for p in border_cells:
            cell_intensity_sum += gray_green_no_bg[p[0]][p[1]]

        # Ensure that the JSON field gets a Python int
        self.cp.cell_intensity = int(cell_intensity_sum)
        self.cp.cell_total_points = len(border_cells)

        self.cp.cell_pair_intensity_sum = float(cell_intensity_sum)

        self.cp.cytoplasmic_intensity = float(cell_intensity_sum) - float(intensity_sum)
