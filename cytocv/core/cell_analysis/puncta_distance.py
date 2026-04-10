import cv2
import logging
import math
import numpy as np

from core.channel_roles import CHANNEL_ROLE_GREEN
from core.services.canonical_contours import (
    get_canonical_green_slots,
    get_canonical_red_slots,
)
from core.services.puncta_line_mode import get_puncta_line_mode_metadata

from .analysis import Analysis

logger = logging.getLogger(__name__)


class PunctaDistance(Analysis):
    name = "PunctaDistance"

    def _measurement_image(self, measurement_channel: str):
        if measurement_channel == CHANNEL_ROLE_GREEN:
            image = self.preprocessed_images.get_image("green_no_bg")
            if image is None:
                image = self.preprocessed_images.get_image("green")
            return image
        image = self.preprocessed_images.get_image("red_no_bg")
        if image is None:
            image = self.preprocessed_images.get_image("gray_red")
        return image

    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image,
        green_image,
        puncta_line_width_input,
        cen_dot_distance,
        cen_dot_collinearity_threshold,
        cen_dot_proximity_radius=13,
    ):
        puncta_line_points = []
        properties = dict(getattr(self.cp, "properties", {}) or {})
        metadata = get_puncta_line_mode_metadata(properties.get("puncta_line_mode"))
        properties["puncta_line_mode"] = metadata["mode"]
        properties["puncta_line_source_channel"] = metadata["source_channel"]
        properties["puncta_line_measurement_channel"] = metadata["measurement_channel"]
        self.cp.properties = properties

        gray_red = self.preprocessed_images.get_image("gray_red")
        green_gray = self.preprocessed_images.get_image("green")
        measurement_image = self._measurement_image(metadata["measurement_channel"])
        shape_source = measurement_image.shape if measurement_image is not None else None
        if shape_source is None and gray_red is not None:
            shape_source = gray_red.shape
        if shape_source is None and green_gray is not None:
            shape_source = green_gray.shape
        if measurement_image is None or shape_source is None:
            return []

        if metadata["source_channel"] == CHANNEL_ROLE_GREEN:
            source_slots = get_canonical_green_slots(contours_data, shape_source, limit=2)
        else:
            source_slots = get_canonical_red_slots(contours_data, shape_source, limit=2)
        if len(source_slots) < 2:
            return []

        try:
            center_1 = source_slots[0].center
            center_2 = source_slots[1].center
            puncta_distance = math.dist(center_1, center_2)
            self.cp.puncta_distance = float(puncta_distance)

            c1x, c1y = source_slots[0].center_int
            c2x, c2y = source_slots[1].center_int
            thickness = int(puncta_line_width_input)
            for canvas in (red_image, green_image):
                if canvas is None:
                    continue
                cv2.line(
                    canvas,
                    (c1x, c1y),
                    (c2x, c2y),
                    (255, 255, 255),
                    thickness=thickness,
                )

            line_mask = np.zeros(shape_source, np.uint8)
            cv2.line(
                line_mask,
                (c1x, c1y),
                (c2x, c2y),
                255,
                thickness=thickness,
            )
            puncta_line_points = np.transpose(np.nonzero(line_mask))

            line_intensity_sum = 0.0
            for p in puncta_line_points:
                line_intensity_sum += float(measurement_image[p[0]][p[1]])

            self.cp.puncta_line_intensity = float(line_intensity_sum)
            return puncta_line_points
        except Exception as exc:
            logger.debug("Puncta-distance analysis skipped: %s", exc)
            return []
