import csv
import os

import cv2
import numpy as np

from .Analysis import Analysis


class NuclearCellularIntensity(Analysis):
    name = "Nuclear, Cellular Intensity"

    _MODE_CONFIG = {
        "green_nucleus": (
            ("GFP_no_bg", "GFP"),
            ("mCherry_no_bg", "gray_mcherry"),
            "GFP",
            "mCherry",
        ),
        "red_nucleus": (
            ("mCherry_no_bg", "gray_mcherry"),
            ("GFP_no_bg", "GFP"),
            "mCherry",
            "GFP",
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
    def _largest_component_mask(binary_mask):
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return np.zeros(binary_mask.shape, np.uint8), None
        largest = max(contours, key=cv2.contourArea)
        nucleus_mask = np.zeros(binary_mask.shape, np.uint8)
        cv2.drawContours(nucleus_mask, [largest], -1, 255, thickness=-1)
        return nucleus_mask, largest

    @staticmethod
    def _draw_dashed_contour(image, contour, color=(255, 255, 255), dash_px=6, gap_px=4, thickness=1):
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
        mcherry_line_width_input=None,
        gfp_distance=0,
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

        cell_points = self._cell_points()
        if not cell_points:
            self.cp.nucleus_intensity_sum = 0.0
            self.cp.cellular_intensity_sum = 0.0
            self.cp.cytoplasmic_intensity = 0.0
            props["nuclear_cellular_mode"] = mode
            props["nuclear_cellular_contour_channel"] = contour_channel
            props["nuclear_cellular_measurement_channel"] = measurement_channel
            props["nuclear_cellular_status"] = "no_cell_points"
            self.cp.properties = props
            return

        h, w = contour_img.shape[:2]
        cell_mask = np.zeros((h, w), np.uint8)
        for y, x in cell_points:
            if 0 <= y < h and 0 <= x < w:
                cell_mask[y, x] = 255

        contour_u8 = contour_img.astype(np.uint8, copy=False)
        _, threshold_mask = cv2.threshold(contour_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        threshold_mask = cv2.bitwise_and(threshold_mask, cell_mask)

        kernel = np.ones((3, 3), np.uint8)
        threshold_mask = cv2.morphologyEx(threshold_mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        threshold_mask = cv2.morphologyEx(threshold_mask, cv2.MORPH_OPEN, kernel, iterations=1)

        nucleus_mask, largest_contour = self._largest_component_mask(threshold_mask)
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
        props["nuclear_cellular_status"] = "ok" if largest_contour is not None else "no_nucleus_contour"
        self.cp.properties = props

        if largest_contour is not None:
            if red_image is not None:
                self._draw_dashed_contour(red_image, largest_contour, color=(255, 255, 255), dash_px=6, gap_px=4, thickness=1)
            if green_image is not None:
                self._draw_dashed_contour(green_image, largest_contour, color=(255, 255, 255), dash_px=6, gap_px=4, thickness=1)
