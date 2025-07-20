import math, cv2
import numpy as np
from core.contour_processing import get_contour_center
from core.image_processing import calculate_intensity_mask,create_circular_mask
from core.image_processing.GrayImage import GrayImage
from .Analysis import Analysis

class Green_Red_Intensity(Analysis):
    name = 'Green Red Intensity'
    def calculate_statistics(self, best_contours, contours_data,red_image, green_image,mcherry_line_width_input):
        """
            :param *args:
            :param **kwargs:
            :param preprocessed_images: GrayImage object
            :return: ratio between red and green intensity
            """
        mcherry_gray = self.preprocessed_images.get_image('gray_mcherry')
        GFP_gray = self.preprocessed_images.get_image('GFP')

        ratio = 0
        centers = get_contour_center([best_contours])

        for i in centers:
            mask = create_circular_mask(mcherry_gray.shape, centers[i],
                                        10)  # draw a contour around red signal TODO: make the radius configurable
            red_intensity = calculate_intensity_mask(mcherry_gray, mask)
            green_intensity = calculate_intensity_mask(GFP_gray, mask)
            cv2.circle(red_image, centers[i], 10, (0, 0, 255), 1)
            cv2.circle(green_image, centers[i], 10, (0, 0, 255), 1)

            ratio = green_intensity / red_intensity if red_intensity != 0 else 0
        self.cp.green_red_intensity = ratio
