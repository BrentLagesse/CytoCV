import csv
import os

import cv2
import numpy as np

from core.services.canonical_contours import (
    get_canonical_green_slots,
    get_canonical_red_slots,
    load_cell_mask,
)
from .analysis import Analysis


class NuclearCellularIntensity(Analysis):
    name = "Nuclear, Cellular Intensity"

    # Temporary release toggle: keep overlay logic available but disabled by default.
    _DRAW_NUCLEAR_CONTOUR_OVERLAY = False

    _MODE_CONFIG = {
        "green_nucleus": (
            ("green_no_bg", "green"),
            ("red_no_bg", "gray_red"),
            "Green",
            "Red",
        ),
        "red_nucleus": (
            ("red_no_bg", "gray_red"),
            ("green_no_bg", "green"),
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

    def _cell_points(self):
        outline_filename = os.path.splitext(self.cp.image_name)[0] + "-" + str(self.cp.cell_id) + ".outline"
        mask_file_path = os.path.join(self.output_dir, "output", outline_filename)
        points = []
        with open(mask_file_path, "r") as csvfile:
            csvreader = csv.reader(csvfile)
            for row in csvreader:
                points.append((int(row[0]), int(row[1])))
        return points

    @staticmethod
    def _draw_dashed_contour(image, contour, color=(0, 255, 255), dash_px=6, gap_px=4, thickness=1):
        if image is None or contour is None or len(contour) < 2:
            return
        dash_px = max(int(dash_px), 1)
        gap_px = max(int(gap_px), 1)
        points = contour.reshape(-1, 2).astype(np.float32)
        if points.shape[0] < 2:
            return
        points = np.vstack([points, points[0]])
        draw_segment = True
        remaining = float(dash_px)
        for idx in range(points.shape[0] - 1):
            start = points[idx]
            end = points[idx + 1]
            segment = end - start
            segment_length = float(np.linalg.norm(segment))
            if segment_length <= 0:
                continue
            direction = segment / segment_length
            traversed = 0.0
            while traversed < segment_length:
                step = min(remaining, segment_length - traversed)
                seg_start = start + (direction * traversed)
                seg_end = start + (direction * (traversed + step))
                if draw_segment:
                    p1 = tuple(np.round(seg_start).astype(int))
                    p2 = tuple(np.round(seg_end).astype(int))
                    cv2.line(image, p1, p2, color, thickness=thickness, lineType=cv2.LINE_AA)
                traversed += step
                remaining -= step
                if remaining <= 1e-6:
                    draw_segment = not draw_segment
                    remaining = float(dash_px if draw_segment else gap_px)

    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image=None,
        green_image=None,
        red_line_width_input=None,
        cen_dot_distance=0,
        cen_dot_collinearity_threshold=0,
    ):
        props = dict(getattr(self.cp, "properties", {}) or {})
        mode = props.get("nuclear_cellular_mode", "green_nucleus")
        if mode not in self._MODE_CONFIG:
            mode = "green_nucleus"

        contour_keys, measure_keys, contour_channel, measurement_channel = self._MODE_CONFIG[mode]
        contour_img = self._first_available_image(contour_keys)
        measure_img = self._first_available_image(measure_keys)

        if contour_img is None or measure_img is None:
            self.cp.nucleus_intensity_sum = 0.0
            self.cp.cellular_intensity_sum = 0.0
            self.cp.cytoplasmic_intensity = 0.0
            props["nuclear_cellular_mode"] = mode
            props["nuclear_cellular_contour_channel"] = contour_channel
            props["nuclear_cellular_measurement_channel"] = measurement_channel
            props["nuclear_cellular_status"] = "missing_channel"
            self.cp.properties = props
            return

        h, w = contour_img.shape[:2]
        cell_mask = contours_data.get("cell_mask")
        if cell_mask is None or cell_mask.shape[:2] != (h, w) or not np.any(cell_mask):
            cell_mask = load_cell_mask(self.cp.image_name, self.cp.cell_id, self.output_dir, (h, w))

        if not np.any(cell_mask):
            self.cp.nucleus_intensity_sum = 0.0
            self.cp.cellular_intensity_sum = 0.0
            self.cp.cytoplasmic_intensity = 0.0
            props["nuclear_cellular_mode"] = mode
            props["nuclear_cellular_contour_channel"] = contour_channel
            props["nuclear_cellular_measurement_channel"] = measurement_channel
            props["nuclear_cellular_status"] = "no_cell_points"
            self.cp.properties = props
            return

        slot_payload = dict(contours_data or {})
        slot_payload["cell_mask"] = cell_mask
        if mode == "red_nucleus":
            source_slots = get_canonical_red_slots(slot_payload, (h, w), limit=1)
        else:
            source_slots = get_canonical_green_slots(slot_payload, (h, w), limit=1)
        used_contour_source = "canonical_slot_1"

        if not source_slots:
            self.cp.nucleus_intensity_sum = 0.0
            self.cp.cellular_intensity_sum = 0.0
            self.cp.cytoplasmic_intensity = 0.0
            props["nuclear_cellular_mode"] = mode
            props["nuclear_cellular_contour_channel"] = contour_channel
            props["nuclear_cellular_measurement_channel"] = measurement_channel
            props["nuclear_cellular_contour_source"] = used_contour_source
            props["nuclear_cellular_status"] = "no_nucleus_contour"
            self.cp.properties = props
            return

        nucleus_slot = source_slots[0]
        nucleus_mask = nucleus_slot.mask
        largest_contour = max(
            nucleus_slot.contours,
            key=cv2.contourArea,
            default=None,
        )

        measure_u8 = measure_img.astype(np.float32, copy=False)
        cell_pixels = measure_u8[cell_mask > 0]
        nucleus_pixels = measure_u8[nucleus_mask > 0]

        cell_intensity = float(np.sum(cell_pixels)) if cell_pixels.size else 0.0
        nucleus_intensity = float(np.sum(nucleus_pixels)) if nucleus_pixels.size else 0.0

        self.cp.cellular_intensity_sum = cell_intensity
        self.cp.nucleus_intensity_sum = nucleus_intensity
        self.cp.cytoplasmic_intensity = cell_intensity - nucleus_intensity

        props["nuclear_cellular_mode"] = mode
        props["nuclear_cellular_contour_channel"] = contour_channel
        props["nuclear_cellular_measurement_channel"] = measurement_channel
        props["nuclear_cellular_contour_source"] = used_contour_source
        props["nuclear_cellular_status"] = "ok"
        self.cp.properties = props

        if self._DRAW_NUCLEAR_CONTOUR_OVERLAY:
            if red_image is not None:
                self._draw_dashed_contour(red_image, largest_contour, color=(0, 255, 255), dash_px=6, gap_px=4, thickness=1)
            if green_image is not None:
                self._draw_dashed_contour(green_image, largest_contour, color=(0, 255, 255), dash_px=6, gap_px=4, thickness=1)
