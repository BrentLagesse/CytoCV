import logging
import math

from core.services.canonical_contours import (
    get_canonical_green_slots,
    get_canonical_red_slots,
)
from core.scale import normalize_length_unit

from .analysis import Analysis
from .cen_dot import CENDot

logger = logging.getLogger(__name__)


_MAX_SLOTS_TO_COUNT = 3
_MAX_REPORTED_DOTS = 2


def _coerce_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pixel_distance(center_1, center_2, properties: dict, unit: str) -> float:
    if unit == "um":
        x_scale = _coerce_float(
            properties.get("scale_x_um_per_px", properties.get("scale_effective_um_per_px")),
            default=0.1,
        )
        y_scale = _coerce_float(
            properties.get("scale_y_um_per_px", properties.get("scale_effective_um_per_px")),
            default=0.1,
        )
        if x_scale <= 0:
            x_scale = 0.1
        if y_scale <= 0:
            y_scale = 0.1
        dx_um = (center_1[0] - center_2[0]) * x_scale
        dy_um = (center_1[1] - center_2[1]) * y_scale
        return math.hypot(dx_um, dy_um)
    return float(math.dist(center_1, center_2))


class Biorientation(Analysis):
    name = "Biorientation"

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
        properties = dict(getattr(self.cp, "properties", {}) or {})

        red_min = _coerce_float(
            properties.get("stats_biorientation_red_min_distance_value", 0.0),
            default=0.0,
        )
        red_max = _coerce_float(
            properties.get("stats_biorientation_red_max_distance_value", 37.0),
            default=37.0,
        )
        collinearity_threshold = _coerce_float(
            properties.get("stats_biorientation_collinearity_threshold", 66),
            default=66,
        )
        min_unit = normalize_length_unit(
            properties.get("stats_biorientation_red_min_distance_unit"),
            default="px",
        )
        max_unit = normalize_length_unit(
            properties.get("stats_biorientation_red_max_distance_unit"),
            default="px",
        )

        self.cp.colinear_dots = 0
        self.cp.off_axis_dots = 0

        red_gray = self.preprocessed_images.get_image("gray_red")
        green_gray = self.preprocessed_images.get_image("green")
        base_shape = None
        if red_gray is not None:
            base_shape = red_gray.shape
        green_shape = green_gray.shape if green_gray is not None else base_shape
        if base_shape is None:
            base_shape = green_shape
        if base_shape is None:
            return

        cell_mask = contours_data.get("cell_mask")

        try:
            red_slots = CENDot._deduplicate_slots(
                get_canonical_red_slots(contours_data, base_shape, limit=_MAX_SLOTS_TO_COUNT)
            )
            green_slots = CENDot._deduplicate_slots(
                get_canonical_green_slots(
                    contours_data, green_shape or base_shape, limit=_MAX_SLOTS_TO_COUNT
                )
            )

            if len(red_slots) != 2:
                return

            center_1 = red_slots[0].center
            center_2 = red_slots[1].center
            distance_min = _pixel_distance(center_1, center_2, properties, min_unit)
            distance_max = _pixel_distance(center_1, center_2, properties, max_unit)
            if distance_min < red_min:
                return
            if distance_max > red_max:
                return

            collinear_count = 0
            off_axis_count = 0
            for green_slot in green_slots:
                if not CENDot._green_slot_inside_pair_mask(green_slot, cell_mask):
                    continue
                if self._is_collinear(
                    green_slot.center, center_1, center_2, collinearity_threshold
                ):
                    collinear_count += 1
                else:
                    off_axis_count += 1

            self.cp.colinear_dots = min(collinear_count, _MAX_REPORTED_DOTS)
            self.cp.off_axis_dots = min(off_axis_count, _MAX_REPORTED_DOTS)
        except Exception as exc:
            logger.debug("Biorientation analysis skipped: %s", exc)
            self.cp.colinear_dots = 0
            self.cp.off_axis_dots = 0

    @staticmethod
    def _is_collinear(point, endpoint1, endpoint2, eps) -> bool:
        px, py = float(point[0]), float(point[1])
        x1, y1 = float(endpoint1[0]), float(endpoint1[1])
        x2, y2 = float(endpoint2[0]), float(endpoint2[1])
        dx = x2 - x1
        dy = y2 - y1
        cross = (py - y1) * dx - (px - x1) * dy
        if abs(cross) > eps:
            return False

        dot = (px - x1) * dx + (py - y1) * dy
        squared_dist = dx * dx + dy * dy
        return not (dot < 0 or dot > squared_dist)
