"""CEN-dot classification from canonical red/green contour geometry."""

import logging
import math

import cv2
import numpy as np

from core.services.canonical_contours import (
    CELL_PARENTAGE_KEY,
    CanonicalContourSlot,
    get_canonical_green_slots,
    get_canonical_red_slots,
    get_neck_split,
    get_side_masks,
)
from core.scale import convert_pixel_delta_to_microns, normalize_length_unit

from .analysis import Analysis

logger = logging.getLogger(__name__)


CEN_DOT_SCHEMA_VERSION = 3

_CATEGORY_BOTH = 1
_CATEGORY_MOTHER_ONLY = 2
_CATEGORY_DAUGHTER_ONLY = 3
_CATEGORY_NA = 4

_SIDE_MOTHER = "mother"
_SIDE_DAUGHTER = "daughter"

_MAX_RED_SLOTS_FOR_CLASSIFICATION = 3
_GREEN_ASSIGNMENT_RULE = "nearest_red_inside_pair_mask"
_DISTANCE_TIE_EPSILON = 1e-9


class CENDot(Analysis):
    """Classify green-dot association with mother/daughter red contour context."""

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

    def _distance_meets_threshold(self, center_1, center_2, threshold_value) -> tuple[bool, float, float]:
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
        return distance >= threshold, distance, threshold

    def _get_proximity_radius_unit(self) -> str:
        properties = getattr(self.cp, "properties", {}) or {}
        return normalize_length_unit(properties.get("stats_cen_dot_proximity_radius_unit"), default="px")

    def _proximity_radius_in_pixels(self, proximity_radius: float) -> float:
        proximity_radius_unit = self._get_proximity_radius_unit()
        if proximity_radius_unit == "um":
            properties = getattr(self.cp, "properties", {}) or {}
            um_per_px = properties.get(
                "scale_effective_um_per_px",
                properties.get("scale_x_um_per_px", 0.1),
            )
            try:
                um_per_px = float(um_per_px)
            except (TypeError, ValueError):
                um_per_px = 0.1
            if um_per_px <= 0:
                um_per_px = 0.1
            return proximity_radius / um_per_px
        return proximity_radius

    @staticmethod
    def _center_distance_sq(center_1, center_2) -> float:
        dx = float(center_1[0]) - float(center_2[0])
        dy = float(center_1[1]) - float(center_2[1])
        return dx * dx + dy * dy

    @staticmethod
    def _deduplicate_slots(
        slots: list[CanonicalContourSlot],
        min_center_distance: float = 8.0,
    ) -> list[CanonicalContourSlot]:
        """Drop slots whose center lies within ``min_center_distance`` of a kept slot."""

        kept: list[CanonicalContourSlot] = []
        min_center_distance_sq = float(min_center_distance) * float(min_center_distance)
        for slot in slots:
            keep = True
            for existing in kept:
                if (
                    CENDot._center_distance_sq(slot.center, existing.center)
                    <= min_center_distance_sq
                ):
                    keep = False
                    break
            if keep:
                kept.append(slot)
        return kept

    @staticmethod
    def _assign_slot_side(
        slot: CanonicalContourSlot,
        mother_mask: np.ndarray | None,
        daughter_mask: np.ndarray | None,
    ) -> str | None:
        """Return ``mother``/``daughter`` based on which side mask overlaps most."""

        if mother_mask is None or daughter_mask is None:
            return None
        slot_mask = slot.mask
        if slot_mask is None or not np.any(slot_mask):
            return None
        mother_overlap = int(np.count_nonzero(cv2.bitwise_and(slot_mask, mother_mask)))
        daughter_overlap = int(np.count_nonzero(cv2.bitwise_and(slot_mask, daughter_mask)))
        if mother_overlap == 0 and daughter_overlap == 0:
            return None
        return _SIDE_MOTHER if mother_overlap >= daughter_overlap else _SIDE_DAUGHTER

    @staticmethod
    def _green_slot_inside_pair_mask(
        slot: CanonicalContourSlot,
        cell_mask: np.ndarray | None,
    ) -> bool:
        """Require a non-empty green footprint inside the DIC pair mask."""

        if cell_mask is None or slot.mask is None:
            return False
        clipped = cv2.bitwise_and(slot.mask, cell_mask)
        return bool(np.any(clipped))

    @classmethod
    def _associate_green_slots_to_reds(
        cls,
        green_slots: list[CanonicalContourSlot],
        cell_mask: np.ndarray | None,
        mother_red_center,
        daughter_red_center,
        prox_radius: float,
    ) -> tuple[
        list[tuple[float, float]],
        list[tuple[float, float]],
        list[tuple[float, float]],
    ]:
        """Associate eligible green centers to the nearest in-radius red center."""

        if prox_radius < 0:
            return [], [], []

        proximity_radius_sq = float(prox_radius) * float(prox_radius)
        mother_associated_centers: list[tuple[float, float]] = []
        daughter_associated_centers: list[tuple[float, float]] = []
        ambiguous_centers: list[tuple[float, float]] = []

        for green_slot in green_slots:
            if not cls._green_slot_inside_pair_mask(green_slot, cell_mask):
                continue

            mother_distance_sq = cls._center_distance_sq(
                mother_red_center,
                green_slot.center,
            )
            daughter_distance_sq = cls._center_distance_sq(
                daughter_red_center,
                green_slot.center,
            )
            within_mother = mother_distance_sq <= proximity_radius_sq
            within_daughter = daughter_distance_sq <= proximity_radius_sq

            if not within_mother and not within_daughter:
                continue
            if within_mother and within_daughter:
                if abs(mother_distance_sq - daughter_distance_sq) <= _DISTANCE_TIE_EPSILON:
                    ambiguous_centers.append(green_slot.center)
                elif mother_distance_sq < daughter_distance_sq:
                    mother_associated_centers.append(green_slot.center)
                else:
                    daughter_associated_centers.append(green_slot.center)
            elif within_mother:
                mother_associated_centers.append(green_slot.center)
            else:
                daughter_associated_centers.append(green_slot.center)

        return mother_associated_centers, daughter_associated_centers, ambiguous_centers

    @staticmethod
    def _set_location_properties(cp, payload: dict) -> None:
        properties = dict(getattr(cp, "properties", {}) or {})
        properties["cen_dot_schema_version"] = CEN_DOT_SCHEMA_VERSION
        properties["cen_dot_location"] = payload
        cp.properties = properties

    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image,
        green_image,
        puncta_line_width_input,
        cen_dot_distance=37,
        cen_dot_proximity_radius=13,
    ):
        prox_radius = self._proximity_radius_in_pixels(cen_dot_proximity_radius)
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

        cell_mask = contours_data.get("cell_mask")
        mother_mask, daughter_mask = get_side_masks(contours_data)
        neck_split = get_neck_split(contours_data)
        parentage_payload = contours_data.get(CELL_PARENTAGE_KEY)
        if not isinstance(parentage_payload, dict):
            parentage_payload = (getattr(self.cp, "properties", {}) or {}).get("cell_parentage")
        if not isinstance(parentage_payload, dict):
            parentage_payload = {}
        threshold_unit = self._get_distance_threshold_unit()
        proximity_unit = self._get_proximity_radius_unit()

        def _finalize(category: int, status: str, extra: dict | None = None) -> None:
            # Store one structured location payload so table/export/render layers can
            # distinguish classification status from the numeric category field.
            has_parentage_neck_split = parentage_payload.get("has_neck_split")
            if has_parentage_neck_split is None:
                has_parentage_neck_split = neck_split is not None and mother_mask is not None
            payload: dict = {
                "status": status,
                "category": int(category),
                "cell_parentage_status": parentage_payload.get("status"),
                "cell_parentage_mode": parentage_payload.get("mode"),
                "cell_parentage_method": parentage_payload.get("method"),
                "threshold_unit": threshold_unit,
                "proximity_unit": proximity_unit,
                "proximity_radius_value": float(cen_dot_proximity_radius),
                "proximity_radius_px": float(prox_radius),
                "red_distance_threshold": float(cen_dot_distance),
                "has_neck_split": bool(has_parentage_neck_split),
            }
            if extra:
                payload.update(extra)
            self.cp.category_cen_dot = int(category)
            self._set_location_properties(self.cp, payload)

        try:
            raw_red_slots = get_canonical_red_slots(
                contours_data,
                base_shape,
                limit=_MAX_RED_SLOTS_FOR_CLASSIFICATION,
            )
            red_slots = self._deduplicate_slots(raw_red_slots)

            raw_green_slots = get_canonical_green_slots(
                contours_data,
                green_shape or base_shape,
                limit=_MAX_RED_SLOTS_FOR_CLASSIFICATION,
            )
            green_slots = self._deduplicate_slots(raw_green_slots)

            red_count = len(red_slots)
            if red_count != 2:
                reason = "too_few_reds" if red_count < 2 else "too_many_reds"
                _finalize(
                    _CATEGORY_NA,
                    reason,
                    {"usable_red_count": int(red_count)},
                )
                return

            center_1 = red_slots[0].center
            center_2 = red_slots[1].center
            meets_threshold, distance, threshold = self._distance_meets_threshold(
                center_1,
                center_2,
                cen_dot_distance,
            )

            if not meets_threshold:
                _finalize(
                    _CATEGORY_NA,
                    "reds_below_threshold",
                    {
                        "red_distance": float(distance),
                        "red_distance_threshold_effective": float(threshold),
                    },
                )
                return

            if mother_mask is None or daughter_mask is None:
                _finalize(
                    _CATEGORY_NA,
                    "missing_cell_parentage",
                    {
                        "cell_parentage_reason": parentage_payload.get("reason"),
                        "red_distance": float(distance),
                    },
                )
                return

            side_by_red_index: dict[int, str] = {}
            for index, slot in enumerate(red_slots[:2]):
                side = self._assign_slot_side(slot, mother_mask, daughter_mask)
                if side is not None:
                    side_by_red_index[index] = side

            if len(side_by_red_index) != 2:
                _finalize(
                    _CATEGORY_NA,
                    "red_side_unassigned",
                    {"red_distance": float(distance)},
                )
                return

            if side_by_red_index[0] == side_by_red_index[1]:
                _finalize(
                    _CATEGORY_NA,
                    "reds_same_side",
                    {
                        "red_distance": float(distance),
                        "red_sides": [side_by_red_index[0], side_by_red_index[1]],
                    },
                )
                return

            mother_red_index = next(
                idx for idx, side in side_by_red_index.items() if side == _SIDE_MOTHER
            )
            daughter_red_index = next(
                idx for idx, side in side_by_red_index.items() if side == _SIDE_DAUGHTER
            )
            mother_red_center = red_slots[mother_red_index].center
            daughter_red_center = red_slots[daughter_red_index].center

            (
                mother_associated_green_centers,
                daughter_associated_green_centers,
                ambiguous_green_centers,
            ) = self._associate_green_slots_to_reds(
                green_slots,
                cell_mask,
                mother_red_center,
                daughter_red_center,
                prox_radius,
            )

            has_mother = bool(mother_associated_green_centers)
            has_daughter = bool(daughter_associated_green_centers)

            if has_mother and has_daughter:
                category = _CATEGORY_BOTH
                status = "mother_and_daughter"
            elif has_mother:
                category = _CATEGORY_MOTHER_ONLY
                status = "mother_only"
            elif has_daughter:
                category = _CATEGORY_DAUGHTER_ONLY
                status = "daughter_only"
            else:
                category = _CATEGORY_NA
                status = "no_valid_green"

            _finalize(
                category,
                status,
                {
                    "red_distance": float(distance),
                    "red_distance_threshold_effective": float(threshold),
                    "mother_red_center": [float(mother_red_center[0]), float(mother_red_center[1])],
                    "daughter_red_center": [float(daughter_red_center[0]), float(daughter_red_center[1])],
                    "green_assignment_rule": _GREEN_ASSIGNMENT_RULE,
                    "mother_red_has_green": has_mother,
                    "daughter_red_has_green": has_daughter,
                    "mother_associated_green_centers": [
                        [float(c[0]), float(c[1])] for c in mother_associated_green_centers
                    ],
                    "daughter_associated_green_centers": [
                        [float(c[0]), float(c[1])] for c in daughter_associated_green_centers
                    ],
                    "ambiguous_green_centers": [
                        [float(c[0]), float(c[1])] for c in ambiguous_green_centers
                    ],
                    # Compatibility aliases retained for older display/export callers.
                    "mother_green_centers": [
                        [float(c[0]), float(c[1])] for c in mother_associated_green_centers
                    ],
                    "daughter_green_centers": [
                        [float(c[0]), float(c[1])] for c in daughter_associated_green_centers
                    ],
                    "green_in_mother": has_mother,
                    "green_in_daughter": has_daughter,
                },
            )
        except Exception as exc:
            logger.debug("CENDot analysis skipped due to contour error: %s", exc)
            self.cp.category_cen_dot = _CATEGORY_NA
            self._set_location_properties(
                self.cp,
                {
                    "status": "error",
                    "category": int(_CATEGORY_NA),
                    "threshold_unit": threshold_unit,
                    "proximity_unit": proximity_unit,
                    "error": str(exc),
                },
            )
