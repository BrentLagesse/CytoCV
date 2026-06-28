"""Puncta-distance and contour-intensity measurements for red/green modes."""

import cv2
import logging
import math
import numpy as np

from core.channel_roles import CHANNEL_ROLE_GREEN, CHANNEL_ROLE_RED
from core.image_processing import calculate_masked_intensity_stats
from core.services.canonical_contours import (
    get_canonical_green_slots,
    get_canonical_red_slots,
)
from core.services.contour_coordinates import (
    GREEN_CONTOUR_PREFIXES,
    RED_CONTOUR_PREFIXES,
    contour_center_context_from_properties,
    store_contour_slot_centers,
)
from core.services.puncta_line_mode import (
    get_puncta_line_mode_metadata,
    is_single_channel_puncta_line_mode,
)

from .analysis import Analysis

logger = logging.getLogger(__name__)


class PunctaDistance(Analysis):
    """Measure source-contour distance and optional same-channel intensities."""

    name = "PunctaDistance"

    # Single-channel modes deliberately mark paired-channel fields unavailable
    # while preserving computed same-channel contour metrics for exports/cards.
    _RED_ONLY_UNAVAILABLE_FIELDS = frozenset(
        {
            "puncta_line_intensity",
            "green_contour_1_size",
            "green_contour_2_size",
            "green_contour_3_size",
            "green_contour_1_center_xy",
            "green_contour_2_center_xy",
            "green_contour_3_center_xy",
            "green_in_red_total_intensity_1",
            "green_in_red_max_intensity_1",
            "green_in_red_average_intensity_1",
            "green_in_red_total_intensity_2",
            "green_in_red_max_intensity_2",
            "green_in_red_average_intensity_2",
            "green_in_red_total_intensity_3",
            "green_in_red_max_intensity_3",
            "green_in_red_average_intensity_3",
            "red_in_green_total_intensity_1",
            "red_in_green_max_intensity_1",
            "red_in_green_average_intensity_1",
            "red_in_green_total_intensity_2",
            "red_in_green_max_intensity_2",
            "red_in_green_average_intensity_2",
            "red_in_green_total_intensity_3",
            "red_in_green_max_intensity_3",
            "red_in_green_average_intensity_3",
            "green_in_green_total_intensity_1",
            "green_in_green_max_intensity_1",
            "green_in_green_average_intensity_1",
            "green_in_green_total_intensity_2",
            "green_in_green_max_intensity_2",
            "green_in_green_average_intensity_2",
            "green_in_green_total_intensity_3",
            "green_in_green_max_intensity_3",
            "green_in_green_average_intensity_3",
            "green_red_intensity_1",
            "green_red_intensity_2",
            "green_red_intensity_3",
            "measurement_contour_ratio_1",
            "measurement_contour_ratio_2",
            "measurement_contour_ratio_3",
            "distance_of_green_from_red_1",
            "distance_of_green_from_red_2",
            "distance_of_green_from_red_3",
        }
    )
    _GREEN_ONLY_UNAVAILABLE_FIELDS = frozenset(
        {
            "puncta_line_intensity",
            "red_contour_1_size",
            "red_contour_2_size",
            "red_contour_3_size",
            "red_contour_1_center_xy",
            "red_contour_2_center_xy",
            "red_contour_3_center_xy",
            "red_in_red_total_intensity_1",
            "red_in_red_max_intensity_1",
            "red_in_red_average_intensity_1",
            "red_in_red_total_intensity_2",
            "red_in_red_max_intensity_2",
            "red_in_red_average_intensity_2",
            "red_in_red_total_intensity_3",
            "red_in_red_max_intensity_3",
            "red_in_red_average_intensity_3",
            "green_in_red_total_intensity_1",
            "green_in_red_max_intensity_1",
            "green_in_red_average_intensity_1",
            "green_in_red_total_intensity_2",
            "green_in_red_max_intensity_2",
            "green_in_red_average_intensity_2",
            "green_in_red_total_intensity_3",
            "green_in_red_max_intensity_3",
            "green_in_red_average_intensity_3",
            "red_in_green_total_intensity_1",
            "red_in_green_max_intensity_1",
            "red_in_green_average_intensity_1",
            "red_in_green_total_intensity_2",
            "red_in_green_max_intensity_2",
            "red_in_green_average_intensity_2",
            "red_in_green_total_intensity_3",
            "red_in_green_max_intensity_3",
            "red_in_green_average_intensity_3",
            "green_red_intensity_1",
            "green_red_intensity_2",
            "green_red_intensity_3",
            "measurement_contour_ratio_1",
            "measurement_contour_ratio_2",
            "measurement_contour_ratio_3",
            "distance_of_green_from_red_1",
            "distance_of_green_from_red_2",
            "distance_of_green_from_red_3",
        }
    )

    def _measurement_image(self, measurement_channel: str):
        # Prefer raw measurement images for intensity values; normalized display
        # fallbacks keep older cached runs measurable when raw variants are absent.
        if not measurement_channel:
            return None
        if measurement_channel == CHANNEL_ROLE_GREEN:
            image = self.preprocessed_images.get_image("raw_green")
            if image is None:
                image = self.preprocessed_images.get_image("green_no_bg")
            if image is None:
                image = self.preprocessed_images.get_image("green")
            return image
        image = self.preprocessed_images.get_image("raw_red")
        if image is None:
            image = self.preprocessed_images.get_image("red_no_bg")
        if image is None:
            image = self.preprocessed_images.get_image("gray_red")
        return image

    def _source_image(self, source_channel: str):
        if source_channel == CHANNEL_ROLE_GREEN:
            return self._measurement_image(CHANNEL_ROLE_GREEN)
        return self._measurement_image(CHANNEL_ROLE_RED)

    def _merge_unavailable_fields(self, fields):
        """Merge plugin-specific unavailable field names into row properties."""

        properties = dict(getattr(self.cp, "properties", {}) or {})
        existing = properties.get("unavailable_stat_fields")
        if not isinstance(existing, list):
            existing = list(existing) if isinstance(existing, (tuple, set)) else []
        merged = sorted({str(field) for field in existing} | {str(field) for field in fields})
        properties["unavailable_stat_fields"] = merged
        self.cp.properties = properties

    def _set_default_same_channel_stats(self, source_channel: str):
        if source_channel == CHANNEL_ROLE_GREEN:
            for index in range(1, 4):
                setattr(self.cp, f"green_contour_{index}_size", 0.0)
                setattr(self.cp, f"green_in_green_total_intensity_{index}", 0.0)
                setattr(self.cp, f"green_in_green_max_intensity_{index}", 0.0)
                setattr(self.cp, f"green_in_green_average_intensity_{index}", 0.0)
            return
        for index in range(1, 4):
            setattr(self.cp, f"red_contour_{index}_size", 0.0)
            setattr(self.cp, f"red_in_red_total_intensity_{index}", 0.0)
            setattr(self.cp, f"red_in_red_max_intensity_{index}", 0.0)
            setattr(self.cp, f"red_in_red_average_intensity_{index}", 0.0)

    def _store_same_channel_contour_stats(self, contours_data, source_channel: str, shape_source):
        """Store same-channel contour stats only for single-channel puncta modes."""

        if not is_single_channel_puncta_line_mode(self.cp.properties.get("puncta_line_mode")):
            return
        if not self.cp.properties.get("puncta_contour_intensity_enabled"):
            return

        source_image = self._source_image(source_channel)
        if source_image is None:
            return

        self.cp.properties = dict(self.cp.properties or {})
        stat_visibility = dict(self.cp.properties.get("stat_visibility") or {})
        stat_visibility["red_green_intensity"] = True
        self.cp.properties["stat_visibility"] = stat_visibility

        center_context = contour_center_context_from_properties(self.cp.properties)
        self._set_default_same_channel_stats(source_channel)
        if source_channel == CHANNEL_ROLE_GREEN:
            slots = get_canonical_green_slots(contours_data, shape_source, limit=3)
            self.cp.properties = store_contour_slot_centers(
                self.cp.properties,
                GREEN_CONTOUR_PREFIXES,
                slots,
                center_context,
            )
            for i, slot in enumerate(slots):
                index = i + 1
                total, maximum, average = calculate_masked_intensity_stats(
                    source_image,
                    slot.mask,
                )
                setattr(self.cp, f"green_contour_{index}_size", float(slot.area))
                setattr(self.cp, f"green_in_green_total_intensity_{index}", total)
                setattr(self.cp, f"green_in_green_max_intensity_{index}", maximum)
                setattr(self.cp, f"green_in_green_average_intensity_{index}", average)
            return

        slots = get_canonical_red_slots(contours_data, shape_source, limit=3)
        self.cp.properties = store_contour_slot_centers(
            self.cp.properties,
            RED_CONTOUR_PREFIXES,
            slots,
            center_context,
        )
        for i, slot in enumerate(slots):
            index = i + 1
            total, maximum, average = calculate_masked_intensity_stats(
                source_image,
                slot.mask,
            )
            setattr(self.cp, f"red_contour_{index}_size", float(slot.area))
            setattr(self.cp, f"red_in_red_total_intensity_{index}", total)
            setattr(self.cp, f"red_in_red_max_intensity_{index}", maximum)
            setattr(self.cp, f"red_in_red_average_intensity_{index}", average)

    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image,
        green_image,
        puncta_line_width_input,
        cen_dot_distance,
        cen_dot_proximity_radius=13,
    ):
        puncta_line_points = []
        properties = dict(getattr(self.cp, "properties", {}) or {})
        metadata = get_puncta_line_mode_metadata(properties.get("puncta_line_mode"))
        # Mode metadata normalizes legacy red/green wording into the current
        # source-channel and measurement-channel contract used by exports.
        properties["puncta_line_mode"] = metadata["mode"]
        properties["puncta_line_source_channel"] = metadata["source_channel"]
        properties["puncta_line_measurement_channel"] = metadata["measurement_channel"]
        self.cp.properties = properties

        gray_red = self.preprocessed_images.get_image("gray_red")
        green_gray = self.preprocessed_images.get_image("green")
        source_image = self._source_image(metadata["source_channel"])
        measurement_image = self._measurement_image(metadata["measurement_channel"])
        single_channel_mode = is_single_channel_puncta_line_mode(metadata["mode"])
        if single_channel_mode:
            # Single-channel modes keep same-channel contour stats while explicitly
            # hiding paired-channel fields from downstream table/export surfaces.
            self._merge_unavailable_fields(
                self._GREEN_ONLY_UNAVAILABLE_FIELDS
                if metadata["source_channel"] == CHANNEL_ROLE_GREEN
                else self._RED_ONLY_UNAVAILABLE_FIELDS
            )
        shape_source = source_image.shape if source_image is not None else None
        if shape_source is None and measurement_image is not None:
            shape_source = measurement_image.shape
        if shape_source is None and gray_red is not None:
            shape_source = gray_red.shape
        if shape_source is None and green_gray is not None:
            shape_source = green_gray.shape
        if shape_source is None:
            return []
        if measurement_image is None and not single_channel_mode:
            return []

        if metadata["source_channel"] == CHANNEL_ROLE_GREEN:
            source_slots = get_canonical_green_slots(contours_data, shape_source, limit=2)
        else:
            source_slots = get_canonical_red_slots(contours_data, shape_source, limit=2)
        self._store_same_channel_contour_stats(
            contours_data,
            metadata["source_channel"],
            shape_source,
        )
        if len(source_slots) < 2:
            return []

        try:
            center_1 = source_slots[0].center
            center_2 = source_slots[1].center
            puncta_distance = math.dist(center_1, center_2)
            self.cp.puncta_distance = float(puncta_distance)
            self.cp.properties = dict(self.cp.properties or {})
            self.cp.properties["puncta_distance_delta_x_px"] = float(center_2[0] - center_1[0])
            self.cp.properties["puncta_distance_delta_y_px"] = float(center_2[1] - center_1[1])

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

            if measurement_image is not None:
                line_intensity_sum = 0.0
                for p in puncta_line_points:
                    line_intensity_sum += float(measurement_image[p[0]][p[1]])
                self.cp.puncta_line_intensity = float(line_intensity_sum)
            return puncta_line_points
        except Exception as exc:
            logger.debug("Puncta-distance analysis skipped: %s", exc)
            return []
