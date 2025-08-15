import math, cv2
import numpy as np
from core.contour_processing import get_contour_center
from core.image_processing import calculate_intensity_mask,create_circular_mask
from core.image_processing.GrayImage import GrayImage
from .Analysis import Analysis

class GreenRedIntensity(Analysis):
    name = 'Green Red Intensity'
    def calculate_statistics(self, best_contours, contours_data,red_image, green_image,mcherry_line_width_input):
        """
        :param preprocessed_images: GrayImage object
        :return: ratio between red and green intensity
        """
        dot_contours = contours_data['dot_contours']
        mcherry_gray = self.preprocessed_images.get_image('gray_mcherry')
        GFP_gray = self.preprocessed_images.get_image('GFP')

        for i in range (0,len(dot_contours)):
            mask = create_circular_mask(mcherry_gray.shape, dot_contours,i)  # draw a mask around countour
            red_intensity = calculate_intensity_mask(mcherry_gray, mask)
            green_intensity = calculate_intensity_mask(GFP_gray, mask)
            ratio = green_intensity / red_intensity if red_intensity != 0 else 0
            setattr(self.cp, f'green_red_intensity_{i+1}', ratio)
