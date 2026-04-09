import math

import cv2

from core.image_processing import calculate_intensity_mask, create_circular_mask
from core.services.measurement_contour_ratio import (
    normalize_nuclear_cellular_mode,
    store_measurement_contour_ratio_triplet,
)
from .analysis import Analysis


class GreenRedIntensity(Analysis):
    name = "Green Red Intensity"

    @staticmethod
    def _contour_center(contour):
        moment = cv2.moments(contour)
        if moment["m00"] == 0:
            x, y, w, h = cv2.boundingRect(contour)
            return (x + w / 2.0, y + h / 2.0)
        return (moment["m10"] / moment["m00"], moment["m01"] / moment["m00"])

    def _rank_contours(self, contours, limit=3):
        ranked = []
        for contour in contours or []:
            if contour is None or len(contour) == 0:
                continue
            area = float(cv2.contourArea(contour))
            if area <= 0:
                continue
            center = self._contour_center(contour)
            ranked.append((area, center, contour))
        ranked.sort(key=lambda item: (-item[0], item[1][0], item[1][1]))
        return ranked[:limit]

    def _set_default_triplet(self, prefix):
        for idx in range(1, 4):
            setattr(self.cp, f"{prefix}_{idx}", 0.0)

    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image,
        green_image,
        mcherry_line_width_input,
        gfp_distance,
        gfp_threshold,
    ):
        red_contours = [entry[2] for entry in self._rank_contours(contours_data.get("dot_contours", []), limit=3)]
        green_contours_ranked = self._rank_contours(contours_data.get("contours_gfp", []), limit=3)
        green_contours = [entry[2] for entry in green_contours_ranked]

        mcherry_gray = self.preprocessed_images.get_image("mCherry_no_bg")
        if mcherry_gray is None:
            mcherry_gray = self.preprocessed_images.get_image("gray_mcherry")

        gfp_gray = self.preprocessed_images.get_image("GFP_no_bg")
        if gfp_gray is None:
            gfp_gray = self.preprocessed_images.get_image("GFP")
        props = dict(getattr(self.cp, "properties", {}) or {})
        mode = normalize_nuclear_cellular_mode(props.get("nuclear_cellular_mode"))
        props["nuclear_cellular_mode"] = mode
        self.cp.properties = props
        if mcherry_gray is None or gfp_gray is None:
            self._set_default_triplet("red_intensity")
            self._set_default_triplet("green_intensity")
            self._set_default_triplet("green_red_intensity")
            self._set_default_triplet("red_in_green_intensity")
            self._set_default_triplet("green_in_green_intensity")
            self._set_default_triplet("gfp_to_mcherry_distance")
            for idx in range(1, 4):
                setattr(self.cp, f"gfp_contour_{idx}_size", 0.0)
            return

        red_centers = [self._contour_center(contour) for contour in red_contours]

        self._set_default_triplet("red_intensity")
        self._set_default_triplet("green_intensity")
        self._set_default_triplet("green_red_intensity")
        self._set_default_triplet("red_in_green_intensity")
        self._set_default_triplet("green_in_green_intensity")
        self._set_default_triplet("gfp_to_mcherry_distance")
        for idx in range(1, 4):
            setattr(self.cp, f"gfp_contour_{idx}_size", 0.0)

        for i, contour in enumerate(red_contours):
            mask = create_circular_mask(mcherry_gray.shape, red_contours, i)
            red_intensity = float(calculate_intensity_mask(mcherry_gray, mask))
            green_intensity = float(calculate_intensity_mask(gfp_gray, mask))
            setattr(self.cp, f"red_intensity_{i + 1}", red_intensity)
            setattr(self.cp, f"green_intensity_{i + 1}", green_intensity)

        for i, contour_info in enumerate(green_contours_ranked):
            area, center, _ = contour_info
            mask = create_circular_mask(gfp_gray.shape, green_contours, i)
            red_in_green = float(calculate_intensity_mask(mcherry_gray, mask))
            green_in_green = float(calculate_intensity_mask(gfp_gray, mask))
            if red_centers:
                nearest_red_dist = min(math.dist(center, red_center) for red_center in red_centers)
            else:
                nearest_red_dist = 0.0

            setattr(self.cp, f"red_in_green_intensity_{i + 1}", red_in_green)
            setattr(self.cp, f"green_in_green_intensity_{i + 1}", green_in_green)
            setattr(self.cp, f"gfp_contour_{i + 1}_size", float(area))
            setattr(self.cp, f"gfp_to_mcherry_distance_{i + 1}", float(nearest_red_dist))

        # Keep raw masked sums as the source of truth. The legacy
        # green_red_intensity_* storage fields now persist the toggle-driven
        # measurement/contour ratio derived from those raw sums.
        store_measurement_contour_ratio_triplet(self.cp, mode=mode)
