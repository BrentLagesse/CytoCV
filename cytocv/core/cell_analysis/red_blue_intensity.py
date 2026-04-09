import math, cv2
import numpy as np
from core.contour_processing import get_contour_center
from core.image_processing import calculate_intensity_mask,create_circular_mask
from core.image_processing import GrayImage
from .analysis import Analysis

class RedBlueIntensity(Analysis):
    name = 'Red in Blue Intensity'

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
        """
        """
        dot_contours = contours_data['dot_contours']
        blue_gray = self.preprocessed_images.get_image('gray_blue')

        for i in range (0,len(dot_contours)):
            mask = create_circular_mask(blue_gray.shape, dot_contours,i)  # draw a mask around contour
            red_intensity = calculate_intensity_mask(blue_gray, mask)
            setattr(self.cp, f'red_blue_intensity_{i+1}', red_intensity)
