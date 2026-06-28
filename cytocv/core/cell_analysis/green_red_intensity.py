"""Red/green contour intensity statistics plugin."""

import math

from core.image_processing import calculate_masked_intensity_stats
from core.services.canonical_contours import (
    get_canonical_green_slots,
    get_canonical_red_slots,
)
from core.services.contour_coordinates import (
    GREEN_CONTOUR_PREFIXES,
    RED_CONTOUR_PREFIXES,
    RED_GREEN_CONTOUR_PREFIXES,
    clear_contour_center_properties,
    contour_center_context_from_properties,
    store_contour_slot_centers,
)
from core.services.measurement_contour_ratio import (
    normalize_measurement_contour_ratio_mode,
    store_measurement_contour_ratio_triplet,
)
from core.services.signal_quantification import measurement_ratio_mode_for_puncta_line_mode
from .analysis import Analysis


class GreenRedIntensity(Analysis):
    """Store masked red/green intensity summaries for canonical contour slots."""

    name = "Green Red Intensity"
    intensity_prefixes = (
        "red_in_red",
        "green_in_red",
        "red_in_green",
        "green_in_green",
    )

    def _set_default_triplet(self, prefix):
        for idx in range(1, 4):
            setattr(self.cp, f"{prefix}_{idx}", 0.0)

    def _set_default_red_contour_sizes(self):
        for idx in range(1, 4):
            setattr(self.cp, f"red_contour_{idx}_size", 0.0)

    def _set_default_intensity_stats(self):
        for prefix in self.intensity_prefixes:
            for idx in range(1, 4):
                setattr(self.cp, f"{prefix}_total_intensity_{idx}", 0.0)
                setattr(self.cp, f"{prefix}_max_intensity_{idx}", 0.0)
                setattr(self.cp, f"{prefix}_average_intensity_{idx}", 0.0)

    def _store_intensity_stats(self, prefix, index, image, mask):
        total, maximum, average = calculate_masked_intensity_stats(image, mask)
        setattr(self.cp, f"{prefix}_total_intensity_{index}", total)
        setattr(self.cp, f"{prefix}_max_intensity_{index}", maximum)
        setattr(self.cp, f"{prefix}_average_intensity_{index}", average)

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
        # Use raw red/green planes for measured intensity values when available;
        # the no-background/display fallbacks preserve compatibility with older caches.
        red_gray = self.preprocessed_images.get_image("raw_red")
        if red_gray is None:
            red_gray = self.preprocessed_images.get_image("red_no_bg")
        if red_gray is None:
            red_gray = self.preprocessed_images.get_image("gray_red")

        green_gray = self.preprocessed_images.get_image("raw_green")
        if green_gray is None:
            green_gray = self.preprocessed_images.get_image("green_no_bg")
        if green_gray is None:
            green_gray = self.preprocessed_images.get_image("green")
        props = dict(getattr(self.cp, "properties", {}) or {})
        if props.get("measurement_contour_ratio_mode"):
            mode_source = props.get("measurement_contour_ratio_mode")
        elif props.get("signal_quantification_mode") == "puncta_distance":
            mode_source = measurement_ratio_mode_for_puncta_line_mode(props.get("puncta_line_mode"))
        else:
            mode_source = props.get("nuclear_cell_pair_mode")
        mode = normalize_measurement_contour_ratio_mode(mode_source)
        props["measurement_contour_ratio_mode"] = mode
        self.cp.properties = props
        center_context = contour_center_context_from_properties(props)
        if red_gray is None or green_gray is None:
            # Missing measurement channels should zero this plugin's output fields
            # instead of leaving stale values on a reused CellStatistics instance.
            self._set_default_intensity_stats()
            self._set_default_triplet("green_red_intensity")
            self._set_default_triplet("distance_of_green_from_red")
            self._set_default_red_contour_sizes()
            for idx in range(1, 4):
                setattr(self.cp, f"green_contour_{idx}_size", 0.0)
            self.cp.properties = clear_contour_center_properties(
                self.cp.properties,
                RED_GREEN_CONTOUR_PREFIXES,
            )
            return

        red_slots = get_canonical_red_slots(contours_data, red_gray.shape, limit=3)
        green_slots = get_canonical_green_slots(contours_data, green_gray.shape, limit=3)
        red_centers = [slot.center for slot in red_slots]
        # Canonical contour slots keep table/export columns stable even when more
        # contours are present in the source masks.
        self.cp.properties = store_contour_slot_centers(
            self.cp.properties,
            RED_CONTOUR_PREFIXES,
            red_slots,
            center_context,
        )
        self.cp.properties = store_contour_slot_centers(
            self.cp.properties,
            GREEN_CONTOUR_PREFIXES,
            green_slots,
            center_context,
        )

        self._set_default_intensity_stats()
        self._set_default_triplet("green_red_intensity")
        self._set_default_triplet("distance_of_green_from_red")
        self._set_default_red_contour_sizes()
        for idx in range(1, 4):
            setattr(self.cp, f"green_contour_{idx}_size", 0.0)

        for i, slot in enumerate(red_slots):
            index = i + 1
            self._store_intensity_stats("red_in_red", index, red_gray, slot.mask)
            self._store_intensity_stats("green_in_red", index, green_gray, slot.mask)
            setattr(self.cp, f"red_contour_{index}_size", float(slot.area))

        for i, slot in enumerate(green_slots):
            index = i + 1
            # Distance fields describe the nearest red contour center to each
            # canonical green slot; they are stored alongside raw intensity stats.
            if red_centers:
                nearest_red_center = min(
                    red_centers,
                    key=lambda red_center: math.dist(slot.center, red_center),
                )
                nearest_red_dist = math.dist(slot.center, nearest_red_center)
            else:
                nearest_red_center = None
                nearest_red_dist = 0.0

            self._store_intensity_stats("red_in_green", index, red_gray, slot.mask)
            self._store_intensity_stats("green_in_green", index, green_gray, slot.mask)
            setattr(self.cp, f"green_contour_{index}_size", float(slot.area))
            setattr(self.cp, f"distance_of_green_from_red_{index}", float(nearest_red_dist))
            self.cp.properties = dict(self.cp.properties or {})
            if nearest_red_center is not None:
                self.cp.properties[f"distance_of_green_from_red_{index}_delta_x_px"] = float(
                    nearest_red_center[0] - slot.center[0]
                )
                self.cp.properties[f"distance_of_green_from_red_{index}_delta_y_px"] = float(
                    nearest_red_center[1] - slot.center[1]
                )

        # Keep raw masked sums as the source of truth. The legacy
        # green_red_intensity_* storage fields now persist the toggle-driven
        # measurement/contour ratio derived from those raw sums.
        store_measurement_contour_ratio_triplet(self.cp, mode=mode)
