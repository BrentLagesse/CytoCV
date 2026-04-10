import logging
import math
import numpy as np

from core.services.canonical_contours import (
    get_canonical_green_slots,
    get_canonical_red_slots,
)
from core.scale import convert_pixel_delta_to_microns, normalize_length_unit

from .analysis import Analysis

logger = logging.getLogger(__name__)


class CENDot(Analysis):
    name = "CENDot"

    def _get_distance_threshold_unit(self) -> str:
        properties = getattr(self.cp, "properties", {}) or {}
        return normalize_length_unit(properties.get("stats_cen_dot_distance_unit"), default="px")

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

    def point_is_between(self, point, endpoint1, endpoint2, eps):
        point = np.array(point)
        endpoint1 = np.array(endpoint1)
        endpoint2 = np.array(endpoint2)

        cross = (point[1] - endpoint1[1]) * (endpoint2[0] - endpoint1[0]) - (point[0] - endpoint1[0]) * (endpoint2[1] - endpoint1[1])
        if abs(cross) > eps:
            return False

        dot = (point[0] - endpoint1[0]) * (endpoint2[0] - endpoint1[0]) + (point[1] - endpoint1[1]) * (endpoint2[1] - endpoint1[1])
        squared_dist = math.dist(endpoint1, endpoint2) * math.dist(endpoint1, endpoint2)
        return not (dot < 0 or dot > squared_dist)

    def is_close(self, green_center_1, green_center_2):
        return math.dist(green_center_1, green_center_2) <= 8

    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image,
        green_image,
        puncta_line_width_input,
        cen_dot_distance=37,
        cen_dot_collinearity_threshold=66,
    ):
        prox_radius = 13
        cen_dot_distance = cen_dot_distance if (cen_dot_distance >= 0) else 37
        red_shape = None
        green_shape = None
        red_gray = self.preprocessed_images.get_image("gray_red")
        green_gray = self.preprocessed_images.get_image("green")
        if red_gray is not None:
            red_shape = red_gray.shape
        if green_gray is not None:
            green_shape = green_gray.shape
        if red_shape is None and green_shape is None:
            return
        base_shape = red_shape or green_shape
        red_slots = get_canonical_red_slots(contours_data, base_shape, limit=2)
        if len(red_slots) <= 1:
            return
        green_slots = get_canonical_green_slots(contours_data, green_shape or base_shape)

        try:
            centers = [red_slots[0].center, red_slots[1].center]
            green_centers = {index: slot.center for index, slot in enumerate(green_slots)}

            if not green_centers:
                self.cp.category_cen_dot = 4
                self.cp.biorientation = 0
                return

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

            if self._is_distance_above_threshold(centers[0], centers[1], cen_dot_distance):
                num_signals = [0] * len(centers)
                for i in range(len(centers)):
                    for green_center in green_centers.values():
                        if math.dist(centers[i], green_center) <= prox_radius:
                            num_signals[i] += 1

                if num_signals[0] >= 1 and num_signals[1] >= 1:
                    self.cp.category_cen_dot = 1
                elif (num_signals[0] == 1 and num_signals[1] == 0) or (num_signals[0] == 0 and num_signals[1] == 1):
                    self.cp.category_cen_dot = 2
                elif (num_signals[0] == 2 and num_signals[1] == 0) or (num_signals[0] == 0 and num_signals[1] == 2):
                    self.cp.category_cen_dot = 3
                else:
                    self.cp.category_cen_dot = 4
            else:
                num_between = 0
                for green_center in green_centers.values():
                    if self.point_is_between(
                        green_center,
                        centers[0],
                        centers[1],
                        cen_dot_collinearity_threshold,
                    ):
                        num_between += 1

                if num_between == 1:
                    self.cp.biorientation = 1
                elif num_between > 1:
                    self.cp.biorientation = 2
                else:
                    self.cp.biorientation = 0
        except Exception as exc:
            logger.debug("CENDot analysis skipped due to contour error: %s", exc)
            self.cp.category_cen_dot = 4
            self.cp.biorientation = 0
            return
