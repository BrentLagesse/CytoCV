import math

from core.image_processing import calculate_intensity_mask
from core.services.canonical_contours import (
    get_canonical_green_slots,
    get_canonical_red_slots,
)
from core.services.measurement_contour_ratio import (
    normalize_nuclear_cell_pair_mode,
    store_measurement_contour_ratio_triplet,
)
from .analysis import Analysis


class GreenRedIntensity(Analysis):
    name = "Green Red Intensity"

    def _set_default_triplet(self, prefix):
        for idx in range(1, 4):
            setattr(self.cp, f"{prefix}_{idx}", 0.0)

    def _set_default_red_contour_sizes(self):
        for idx in range(1, 4):
            setattr(self.cp, f"red_contour_{idx}_size", 0.0)

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
        red_gray = self.preprocessed_images.get_image("red_no_bg")
        if red_gray is None:
            red_gray = self.preprocessed_images.get_image("gray_red")

        green_gray = self.preprocessed_images.get_image("green_no_bg")
        if green_gray is None:
            green_gray = self.preprocessed_images.get_image("green")
        props = dict(getattr(self.cp, "properties", {}) or {})
        mode = normalize_nuclear_cell_pair_mode(props.get("nuclear_cell_pair_mode"))
        props["nuclear_cell_pair_mode"] = mode
        self.cp.properties = props
        if red_gray is None or green_gray is None:
            self._set_default_triplet("red_intensity")
            self._set_default_triplet("green_intensity")
            self._set_default_triplet("green_red_intensity")
            self._set_default_triplet("red_in_green_intensity")
            self._set_default_triplet("green_in_green_intensity")
            self._set_default_triplet("distance_of_green_from_red")
            self._set_default_red_contour_sizes()
            for idx in range(1, 4):
                setattr(self.cp, f"green_contour_{idx}_size", 0.0)
            return

        red_slots = get_canonical_red_slots(contours_data, red_gray.shape, limit=3)
        green_slots = get_canonical_green_slots(contours_data, green_gray.shape, limit=3)
        red_centers = [slot.center for slot in red_slots]

        self._set_default_triplet("red_intensity")
        self._set_default_triplet("green_intensity")
        self._set_default_triplet("green_red_intensity")
        self._set_default_triplet("red_in_green_intensity")
        self._set_default_triplet("green_in_green_intensity")
        self._set_default_triplet("distance_of_green_from_red")
        self._set_default_red_contour_sizes()
        for idx in range(1, 4):
            setattr(self.cp, f"green_contour_{idx}_size", 0.0)

        for i, slot in enumerate(red_slots):
            red_intensity = float(calculate_intensity_mask(red_gray, slot.mask))
            green_intensity = float(calculate_intensity_mask(green_gray, slot.mask))
            setattr(self.cp, f"red_intensity_{i + 1}", red_intensity)
            setattr(self.cp, f"green_intensity_{i + 1}", green_intensity)
            setattr(self.cp, f"red_contour_{i + 1}_size", float(slot.area))

        for i, slot in enumerate(green_slots):
            red_in_green = float(calculate_intensity_mask(red_gray, slot.mask))
            green_in_green = float(calculate_intensity_mask(green_gray, slot.mask))
            if red_centers:
                nearest_red_center = min(
                    red_centers,
                    key=lambda red_center: math.dist(slot.center, red_center),
                )
                nearest_red_dist = math.dist(slot.center, nearest_red_center)
            else:
                nearest_red_center = None
                nearest_red_dist = 0.0

            setattr(self.cp, f"red_in_green_intensity_{i + 1}", red_in_green)
            setattr(self.cp, f"green_in_green_intensity_{i + 1}", green_in_green)
            setattr(self.cp, f"green_contour_{i + 1}_size", float(slot.area))
            setattr(self.cp, f"distance_of_green_from_red_{i + 1}", float(nearest_red_dist))
            self.cp.properties = dict(self.cp.properties or {})
            if nearest_red_center is not None:
                self.cp.properties[f"distance_of_green_from_red_{i + 1}_delta_x_px"] = float(
                    nearest_red_center[0] - slot.center[0]
                )
                self.cp.properties[f"distance_of_green_from_red_{i + 1}_delta_y_px"] = float(
                    nearest_red_center[1] - slot.center[1]
                )

        # Keep raw masked sums as the source of truth. The legacy
        # green_red_intensity_* storage fields now persist the toggle-driven
        # measurement/contour ratio derived from those raw sums.
        store_measurement_contour_ratio_triplet(self.cp, mode=mode)
