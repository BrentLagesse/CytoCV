"""Nuclear and cell-pair intensity statistics for red/green workflows."""

import cv2
import math
import numpy as np

from core.services.canonical_contours import (
    CANONICAL_ALTERNATE_GREEN_SLOTS_KEY,
    CANONICAL_ALTERNATE_RED_SLOTS_KEY,
    get_canonical_green_slots,
    get_canonical_red_slots,
    load_cell_mask,
)
from core.channel_roles import CHANNEL_ROLE_GREEN, CHANNEL_ROLE_RED
from core.services.nuclear_cell_pair_contour_mode import (
    normalize_nuclear_cell_pair_contour_mode,
)
from .analysis import Analysis
from .nuclear_cell_pair_legacy_scaled import (
    apply_legacy_cell_pair_mask_provenance,
    apply_legacy_scaled_provenance,
    legacy_scaled_measurement_keys,
    select_legacy_exact_cell_pair_mask,
    truthy_legacy_flag,
)


class NuclearCellPairIntensity(Analysis):
    """Measure one channel inside a nucleus contour and its paired-cell mask."""

    name = "Nuclear, Cell-Pair Intensity"

    _MODE_CONFIG = {
        "green_nucleus": (
            ("green_no_bg", "green"),
            ("raw_red", "red_no_bg", "gray_red"),
            "Green",
            "Red",
        ),
        "red_nucleus": (
            ("red_no_bg", "gray_red"),
            ("raw_green", "green_no_bg", "green"),
            "Red",
            "Green",
        ),
    }

    def _first_available_image(self, keys):
        for key in keys:
            image = self.preprocessed_images.get_image(key)
            if image is not None:
                return image
        return None

    @staticmethod
    def _resolved_alternate_target_channel(props: dict) -> str | None:
        raw_enabled = props.get("alternate_nucleus_detection_enabled")
        if isinstance(raw_enabled, str):
            normalized = raw_enabled.strip().lower()
            if normalized in {"0", "false", "no", "off"}:
                return None
        elif raw_enabled is False or raw_enabled == 0:
            return None
        return props.get("alternate_nucleus_detection_channel")

    @staticmethod
    def _draw_nucleus_contours(red_image, green_image, contours, mode: str) -> None:
        if not contours:
            return
        color = (0, 0, 255) if mode == "red_nucleus" else (0, 255, 0)
        contour_list = [
            contour for contour in contours if contour is not None and len(contour) >= 3
        ]
        if not contour_list:
            return
        for image in (red_image, green_image):
            if image is not None:
                cv2.drawContours(image, contour_list, -1, color, 1)

    @staticmethod
    def _nuclear_cytoplasmic_ratio(
        nucleus_intensity: float,
        cytoplasmic_intensity: float,
    ) -> float | None:
        try:
            numerator = float(nucleus_intensity)
            denominator = float(cytoplasmic_intensity)
        except (TypeError, ValueError):
            return None
        if denominator == 0.0:
            return None
        ratio = numerator / denominator
        return ratio if math.isfinite(ratio) else None

    def _clear_nuclear_cell_pair_sums(self) -> None:
        self.cp.nucleus_intensity_sum = 0.0
        self.cp.cell_pair_intensity_sum = 0.0
        self.cp.cytoplasmic_intensity = 0.0
        self.cp.nuclear_cytoplasmic_ratio = None

    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image=None,
        green_image=None,
        puncta_line_width_input=None,
        cen_dot_distance=0,
        cen_dot_proximity_radius=13,
    ):
        props = dict(getattr(self.cp, "properties", {}) or {})
        mode = props.get("nuclear_cell_pair_mode", "green_nucleus")
        if mode not in self._MODE_CONFIG:
            mode = "green_nucleus"
        contour_mode = normalize_nuclear_cell_pair_contour_mode(
            props.get("nuclear_cell_pair_contour_mode")
        )

        contour_keys, measure_keys, contour_channel, measurement_channel = (
            self._MODE_CONFIG[mode]
        )
        use_legacy_scaled_measurement = truthy_legacy_flag(
            props.get("use_legacy_nuclear_cell_pair_pipeline")
        )
        # The legacy-scaled option changes only the measurement pixel source;
        # contour identity, clipping, and cell-pair masks remain CytoCV-native.
        if use_legacy_scaled_measurement:
            measure_keys = legacy_scaled_measurement_keys(mode)
        contour_img = self._first_available_image(contour_keys)
        measure_img = self._first_available_image(measure_keys)

        if contour_img is None or measure_img is None:
            self._clear_nuclear_cell_pair_sums()
            props["nuclear_cell_pair_mode"] = mode
            props["nuclear_cell_pair_contour_mode"] = contour_mode
            props["nuclear_cell_pair_contour_channel"] = contour_channel
            props["nuclear_cell_pair_measurement_channel"] = measurement_channel
            props["nuclear_cell_pair_status"] = "missing_channel"
            self.cp.properties = props
            return

        h, w = contour_img.shape[:2]
        cell_mask = contours_data.get("cell_mask")
        if cell_mask is None or cell_mask.shape[:2] != (h, w) or not np.any(cell_mask):
            cell_mask = load_cell_mask(
                self.cp.image_name, self.cp.cell_id, self.output_dir, (h, w)
            )

        if not np.any(cell_mask):
            self._clear_nuclear_cell_pair_sums()
            props["nuclear_cell_pair_mode"] = mode
            props["nuclear_cell_pair_contour_mode"] = contour_mode
            props["nuclear_cell_pair_contour_channel"] = contour_channel
            props["nuclear_cell_pair_measurement_channel"] = measurement_channel
            props["nuclear_cell_pair_status"] = "no_cell_points"
            self.cp.properties = props
            return

        slot_payload = dict(contours_data or {})
        slot_payload["cell_mask"] = cell_mask
        alternate_target_channel = self._resolved_alternate_target_channel(props)
        if mode == "red_nucleus":
            if alternate_target_channel == CHANNEL_ROLE_RED:
                source_slots = list(
                    slot_payload.get(CANONICAL_ALTERNATE_RED_SLOTS_KEY, [])
                )[:1]
                used_contour_source = "alternate_red_nucleus_slot_1"
            else:
                source_slots = get_canonical_red_slots(slot_payload, (h, w), limit=1)
                used_contour_source = "canonical_slot_1"
        else:
            if alternate_target_channel == CHANNEL_ROLE_GREEN:
                source_slots = list(
                    slot_payload.get(CANONICAL_ALTERNATE_GREEN_SLOTS_KEY, [])
                )[:1]
                used_contour_source = "alternate_green_nucleus_slot_1"
            else:
                source_slots = get_canonical_green_slots(slot_payload, (h, w), limit=1)
                used_contour_source = "canonical_slot_1"

        if not source_slots:
            self._clear_nuclear_cell_pair_sums()
            props["nuclear_cell_pair_mode"] = mode
            props["nuclear_cell_pair_contour_mode"] = contour_mode
            props["nuclear_cell_pair_contour_channel"] = contour_channel
            props["nuclear_cell_pair_measurement_channel"] = measurement_channel
            props["nuclear_cell_pair_contour_source"] = used_contour_source
            props["nuclear_cell_pair_status"] = "no_nucleus_contour"
            self.cp.properties = props
            return

        nucleus_slot = source_slots[0]
        cell_mask = np.where(cell_mask > 0, 255, 0).astype(np.uint8)
        cell_measurement_mask = cell_mask
        legacy_cell_mask_fallback = False
        if use_legacy_scaled_measurement:
            cell_measurement_mask, legacy_cell_mask_fallback = (
                select_legacy_exact_cell_pair_mask(
                    slot_payload,
                    cell_mask,
                    (h, w),
                )
            )
        nucleus_mask = np.asarray(nucleus_slot.mask)
        if nucleus_mask.ndim == 3:
            nucleus_mask = cv2.cvtColor(nucleus_mask, cv2.COLOR_BGR2GRAY)
        nucleus_mask = np.where(nucleus_mask > 0, 255, 0).astype(np.uint8)
        nucleus_mask = cv2.bitwise_and(nucleus_mask, cell_measurement_mask)
        clipped_nucleus_contours, _ = cv2.findContours(
            nucleus_mask.copy(),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        clipped_nucleus_contours = tuple(
            contour
            for contour in clipped_nucleus_contours
            if contour is not None and len(contour) >= 3
        )
        if not clipped_nucleus_contours:
            self._clear_nuclear_cell_pair_sums()
            props["nuclear_cell_pair_mode"] = mode
            props["nuclear_cell_pair_contour_mode"] = contour_mode
            props["nuclear_cell_pair_contour_channel"] = contour_channel
            props["nuclear_cell_pair_measurement_channel"] = measurement_channel
            props["nuclear_cell_pair_contour_source"] = used_contour_source
            props["nuclear_cell_pair_status"] = "no_nucleus_contour"
            self.cp.properties = props
            return

        measure_values = measure_img.astype(np.float64, copy=False)
        cell_pixels = measure_values[cell_measurement_mask > 0]
        nucleus_pixels = measure_values[nucleus_mask > 0]

        cell_intensity = float(np.sum(cell_pixels)) if cell_pixels.size else 0.0
        nucleus_intensity = (
            float(np.sum(nucleus_pixels)) if nucleus_pixels.size else 0.0
        )

        self.cp.cell_pair_intensity_sum = cell_intensity
        self.cp.nucleus_intensity_sum = nucleus_intensity
        cytoplasmic_intensity = cell_intensity - nucleus_intensity
        self.cp.cytoplasmic_intensity = cytoplasmic_intensity
        self.cp.nuclear_cytoplasmic_ratio = self._nuclear_cytoplasmic_ratio(
            nucleus_intensity,
            cytoplasmic_intensity,
        )

        props["nuclear_cell_pair_mode"] = mode
        props["nuclear_cell_pair_contour_mode"] = contour_mode
        props["nuclear_cell_pair_contour_channel"] = contour_channel
        props["nuclear_cell_pair_measurement_channel"] = measurement_channel
        props["nuclear_cell_pair_contour_source"] = used_contour_source
        props["nuclear_cell_pair_status"] = "ok"
        if use_legacy_scaled_measurement:
            props = apply_legacy_scaled_provenance(props)
            props = apply_legacy_cell_pair_mask_provenance(
                props,
                fallback_used=legacy_cell_mask_fallback,
            )
        self.cp.properties = props

        self._draw_nucleus_contours(
            red_image, green_image, clipped_nucleus_contours, mode
        )
