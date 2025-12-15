import math, cv2
import numpy as np
from .Analysis import Analysis
from core.contour_processing import get_contour_center

class GFPDot(Analysis):
    name = 'GFPDot'
    def calculate_statistics(self, best_contours, contours_data, red_image, green_image, mcherry_line_width_input, gfp_distance=37):
        """
        :param: 
        :return: 
        """
        prox_diameter = 26

        # Use default gfp_distance value if a negative value was provided
        gfp_distance = gfp_distance if (gfp_distance >= 0) else 37

        # Get red signals
        dot_contours = contours_data['dot_contours']

        # Check whether we have two red signals
        if len(dot_contours) > 1:
            contour1 = dot_contours[0]
            contour2 = dot_contours[1]

            try:
                # Center of each contour
                centers = get_contour_center([contour1, contour2])
                # Distance between 2 contours
                distance = math.dist(centers[0], centers[1])
                
                # Check whether distance is greater than 4 micrometers (37 pixels) TODO: This should be tunable and the distance is too much
                # TODO: Is the return value actually pixels?
                if distance > gfp_distance:
                    # Get green signals
                    contours_gfp = contours_data['contours_gfp']

                    # Check how many green signals are within a circle of 20-30 pixels in diameter 
                    green_centers = get_contour_center(contours_gfp)

                    # TODO: Visualize circle    
                    num_signals = [0] * len(centers)
                    for i in range(len(centers)):
                        for green_center in green_centers.values():
                            cv2.circle(green_image, green_center, (prox_diameter / 2), (255, 255, 255), mcherry_line_width_input)
                            if math.dist(centers[i], green_center) <= (prox_diameter / 2):       # TODO: 20-30?
                                num_signals[i] += 1 # TODO: This is sometimes wrong because of GFP contours being counted twice sometimes

                    # TODO: Because of above issue, using >= instead of == below; should fix this issue in contour_operations.py find_contours
                    if num_signals[0] >= 1 and num_signals[1] >= 1:    # 1 green dot with each of the 2 red dots
                        self.cp.category_GFP_dot = 1
                    elif (num_signals[0] == 1 and num_signals[1] == 0) or (num_signals[0] == 0 and num_signals[1] == 1):    # 1 green dot with only 1 of the 2 red dots
                        self.cp.category_GFP_dot = 2
                    elif (num_signals[0] == 2 and num_signals[1] == 0) or (num_signals[0] == 0 and num_signals[1] == 2):    # 2 green dots with only 1 of the 2 red dots
                        self.cp.category_GFP_dot = 3    # TODO: Test since none of the original images actually had this
                    else:   # Other unexpected category
                        self.cp.category_GFP_dot = 4

            except Exception as e:
                print(f"Encountered error while analyzing GFPDot: {e}")
                return
