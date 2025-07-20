from .Analysis import Analysis
from core.contour_processing import get_contour_center

import math, cv2
import numpy as np


class MCherryLine(Analysis):
    name = "MCherryLine"
    def calculate_statistics(self, best_contours, contours_data,red_image, green_image,mcherry_line_width_input):
        mcherry_line_pts = []
        contours_mcherry = contours_data['contours_mcherry']
        best_mcherry_contours = contours_data['bestContours_mcherry']

        gray_GFP_no_bg = self.preprocessed_images.get_image('GFP_no_bg')

        if len(best_mcherry_contours) == 2:
            # choose two best contour
            c1 = contours_mcherry[0][best_mcherry_contours[0]]
            c2 = contours_mcherry[0][best_mcherry_contours[1]]

            # getting 2 centers of contours
            try:
                centers = get_contour_center([c1, c2])
                # distance between 2 contour
                d = math.dist(centers[0], centers[1])
                # Directly assign to cp.red_dot_distance (instead of cp.set_red_dot_distance(d))
                self.cp.red_dot_distance = d
                self.cp.distance = float(d)

                c1x, c1y = centers[0]
                c2x, c2y = centers[1]

                # Use a 3-channel white color tuple:
                cv2.line(red_image, (c1x, c1y), (c2x, c2y), (255, 255, 255), int(mcherry_line_width_input))
                gray_mCherry = self.preprocessed_images.get_image('gray_mcherry')
                mcherry_line_mask = np.zeros(gray_mCherry.shape, np.uint8)
                cv2.line(mcherry_line_mask, (c1x, c1y), (c2x, c2y), 255, int(mcherry_line_width_input))
                mcherry_line_pts = np.transpose(np.nonzero(mcherry_line_mask))

                # Calculate mCherry line intensity
                mcherry_line_intensity_sum = 0
                for p in mcherry_line_pts:
                    mcherry_line_intensity_sum += gray_GFP_no_bg[p[0]][p[1]]

                # Again, cast to a Python int
                self.cp.mcherry_line_gfp_intensity = int(mcherry_line_intensity_sum)

                self.cp.line_gfp_intensity = float(mcherry_line_intensity_sum)

                return mcherry_line_pts

            except ZeroDivisionError:
                print("can't find contours")
                return []
        else:
            return []