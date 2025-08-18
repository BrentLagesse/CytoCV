import math, cv2
import numpy as np
from core.contour_processing import get_contour_center
from core.image_processing import calculate_intensity_mask,create_circular_mask
from core.image_processing.GrayImage import GrayImage
from .Analysis import Analysis

class RedBlueIntensity(Analysis):
    name = 'Red in Blue Intensity'
    def calculate_statistics(self, best_contours, contours_data,red_image, green_image,mcherry_line_width_input):
        """
        """
        dot_contours = contours_data['dot_contours']
        dapi_gray = self.preprocessed_images.get_image('gray_dapi')

        for i in range (0,len(dot_contours)):
            mask = create_circular_mask(dapi_gray.shape, dot_contours,i)  # draw a mask around countour
            red_intensity = calculate_intensity_mask(dapi_gray, mask)
            setattr(self.cp, f'red_blue_intensity_{i+1}', red_intensity)
