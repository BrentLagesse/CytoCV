import cv2
import logging
import math
import numpy as np

from core.contour_processing import get_contour_center

from .analysis import Analysis

logger = logging.getLogger(__name__)


class RedLineIntensity(Analysis):
    name = "RedLineIntensity"

    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image,
        green_image,
        red_line_width_input,
        cen_dot_distance,
        cen_dot_collinearity_threshold,
    ):
        red_line_points = []
        dot_contours = contours_data["dot_contours"]
        green_no_bg = self.preprocessed_images.get_image("green_no_bg")

        if len(dot_contours) < 2:
            return []

        try:
            c1, c2 = dot_contours[0], dot_contours[1]
            centers = get_contour_center([c1, c2])
            d = math.dist(centers[0], centers[1])
            self.cp.red_dot_distance = d
            self.cp.distance = float(d)

            c1x, c1y = centers[0]
            c2x, c2y = centers[1]
            cv2.line(
                red_image,
                (c1x, c1y),
                (c2x, c2y),
                (255, 255, 255),
                thickness=int(red_line_width_input),
            )
            gray_red = self.preprocessed_images.get_image("gray_red")
            red_line_mask = np.zeros(gray_red.shape, np.uint8)
            cv2.line(
                red_line_mask,
                (c1x, c1y),
                (c2x, c2y),
                255,
                thickness=int(red_line_width_input),
            )
            red_line_points = np.transpose(np.nonzero(red_line_mask))

            red_line_intensity_sum = 0
            for p in red_line_points:
                red_line_intensity_sum += green_no_bg[p[0]][p[1]]

            self.cp.red_line_green_intensity = int(red_line_intensity_sum)
            self.cp.line_green_intensity = float(red_line_intensity_sum)
            return red_line_points
        except Exception as exc:
            logger.debug("Red contour analysis skipped: %s", exc)
            return []
