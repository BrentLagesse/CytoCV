import math, cv2
import numpy as np
from .Analysis import Analysis
from core.contour_processing import get_contour_center
from core.scale import convert_pixel_delta_to_microns, normalize_length_unit

class GFPDot(Analysis):
    name = 'GFPDot'

    def _get_distance_threshold_unit(self) -> str:
        properties = getattr(self.cp, "properties", {}) or {}
        return normalize_length_unit(properties.get("stats_gfp_distance_unit"), default="px")

    def _distance_between_centers(
        self,
        center_1,
        center_2,
        *,
        threshold_unit: str,
    ) -> float:
        if threshold_unit == "um":
            properties = getattr(self.cp, "properties", {}) or {}
            x_scale = properties.get("scale_x_um_per_px", properties.get("scale_effective_um_per_px", 0.1))
            y_scale = properties.get("scale_y_um_per_px", properties.get("scale_effective_um_per_px", 0.1))
            return convert_pixel_delta_to_microns(
                center_1[0] - center_2[0],
                center_1[1] - center_2[1],
                x_um_per_px=x_scale,
                y_um_per_px=y_scale,
            )
        return float(math.dist(center_1, center_2))

    def _is_distance_above_threshold(self, center_1, center_2, threshold_value) -> bool:
        threshold_unit = self._get_distance_threshold_unit()
        distance = self._distance_between_centers(
            center_1,
            center_2,
            threshold_unit=threshold_unit,
        )
        try:
            threshold = float(threshold_value)
        except (TypeError, ValueError):
            threshold = 0.0
        return distance > threshold

    # Calculate the distance between a point and a line defined by endpoints
    def point_is_between(self, point, endpoint1, endpoint2, eps):
        # Convert to numpy array
        point = np.array(point)
        endpoint1 = np.array(endpoint1)
        endpoint2 = np.array(endpoint2)

        # Use cross product to determine whether the points are collinear
        cross = (point[1] - endpoint1[1]) * (endpoint2[0] - endpoint1[0]) - (point[0] - endpoint1[0]) * (endpoint2[1] - endpoint1[1])

        # Points are not collinear
        if abs(cross) > eps:
            return False
        
        # Use dot product to determine whether the point is between the other two
        dot = (point[0] - endpoint1[0]) * (endpoint2[0] - endpoint1[0]) + (point[1] - endpoint1[1]) * (endpoint2[1] - endpoint1[1])
        squared_dist = math.dist(endpoint1, endpoint2) * math.dist(endpoint1, endpoint2)
        
        # Point is not between the other two if either condition is true 
        return not (dot < 0 or dot > squared_dist)
    
    # Check if green signals should be considered as a single one
    def is_close(self, green_center_1, green_center_2):
        return math.dist(green_center_1, green_center_2) <= 8


    def calculate_statistics(self, best_contours, contours_data, red_image, green_image, mcherry_line_width_input, gfp_distance=37, gfp_threshold=66):
        """
        :param: 
        :return: 
        """
        prox_radius = 13

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
                # Get green signals
                contours_gfp = contours_data['contours_gfp']
                green_centers = get_contour_center(contours_gfp)

                # Check for no contours
                if not green_centers:
                    self.cp.category_GFP_dot = 4
                    self.cp.biorientation = 0
                    return

                # "Merge" green signals that are too close
                filtered_centers = {0: green_centers[0]}
                if len(green_centers) > 1:
                    for i in range(1, len(green_centers)):
                        close = False
                        for j in range(len(filtered_centers)):
                            if self.is_close(filtered_centers[j], green_centers[i]):
                                close = True
                        if not close:
                            filtered_centers[i] = green_centers[i]
                green_centers = filtered_centers
                
                # Check whether distance is greater than 4 micrometers (given distance in pixels)
                # TODO: Is the return value actually pixels?
                if self._is_distance_above_threshold(centers[0], centers[1], gfp_distance):
                    num_signals = [0] * len(centers)
                    for i in range(len(centers)):
                        for green_center in green_centers.values():
                            # Visualize circles
                            cv2.circle(green_image, centers[i], prox_radius, (255, 255, 255), 1)

                            # Check how many green signals are within a circle of 20-30 pixels in diameter 
                            if math.dist(centers[i], green_center) <= prox_radius:       # TODO: 20-30?
                                num_signals[i] += 1 

                    # TODO: Because of above issue, using >= instead of == below; should fix this issue in contour_operations.py find_contours
                    if num_signals[0] >= 1 and num_signals[1] >= 1:    # 1 green dot with each of the 2 red dots
                        self.cp.category_GFP_dot = 1
                    elif (num_signals[0] == 1 and num_signals[1] == 0) or (num_signals[0] == 0 and num_signals[1] == 1):    # 1 green dot with only 1 of the 2 red dots
                        self.cp.category_GFP_dot = 2
                    elif (num_signals[0] == 2 and num_signals[1] == 0) or (num_signals[0] == 0 and num_signals[1] == 2):    # 2 green dots with only 1 of the 2 red dots
                        self.cp.category_GFP_dot = 3    # TODO: Test since none of the original images actually had this
                    else:   # Other unexpected category
                        self.cp.category_GFP_dot = 4
                else:   # Check biorientation instead
                    num_between = 0
                    for green_center in green_centers.values():
                        if self.point_is_between(green_center, centers[0], centers[1], gfp_threshold):
                            num_between += 1

                    # Set biorientation status
                    if num_between == 1:
                        self.cp.biorientation = 1
                    elif num_between > 1:
                        self.cp.biorientation = 2
                    else: 
                        self.cp.biorientation = 0

            except Exception as e:
                print(f"Encountered error while analyzing GFPDot: {e}")
                self.cp.category_GFP_dot = 4
                self.cp.biorientation = 0
                return
