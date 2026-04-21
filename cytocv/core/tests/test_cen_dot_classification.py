from __future__ import annotations

from types import SimpleNamespace

import cv2
import numpy as np
from django.test import SimpleTestCase

from core.cell_analysis.cen_dot import CENDot
from core.image_processing import GrayImage
from core.services.canonical_contours import (
    CANONICAL_BLUE_SLOTS_KEY,
    CANONICAL_GREEN_SLOTS_KEY,
    CANONICAL_RED_SLOTS_KEY,
    CELL_MASK_KEY,
    CanonicalContourSlot,
    DAUGHTER_MASK_KEY,
    MOTHER_MASK_KEY,
    NECK_SPLIT_KEY,
)
from core.services.neck_split import NeckSplit


SHAPE = (60, 40)


def _disk_slot(source_index: int, center_xy, radius: int = 2) -> CanonicalContourSlot:
    mask = np.zeros(SHAPE, dtype=np.uint8)
    cv2.circle(
        mask,
        (int(round(center_xy[0])), int(round(center_xy[1]))),
        radius,
        255,
        -1,
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return CanonicalContourSlot(
        source_index=source_index,
        mask=mask,
        contours=tuple(contours),
        area=float(np.count_nonzero(mask)),
        center=(float(center_xy[0]), float(center_xy[1])),
    )


def _slot_with_override(
    source_index: int,
    mask: np.ndarray,
    center_xy,
) -> CanonicalContourSlot:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return CanonicalContourSlot(
        source_index=source_index,
        mask=mask,
        contours=tuple(contours),
        area=float(np.count_nonzero(mask)),
        center=(float(center_xy[0]), float(center_xy[1])),
    )


def _build_side_masks() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mother = np.zeros(SHAPE, dtype=np.uint8)
    mother[5:32, 5:35] = 255
    daughter = np.zeros(SHAPE, dtype=np.uint8)
    daughter[33:55, 8:32] = 255
    cell = cv2.bitwise_or(mother, daughter)
    return cell, mother, daughter


def _build_preprocessed_images() -> GrayImage:
    red_gray = np.zeros(SHAPE, dtype=np.uint8)
    green_gray = np.zeros(SHAPE, dtype=np.uint8)
    blue_gray = np.zeros(SHAPE, dtype=np.uint8)
    return GrayImage(
        img={
            "gray_red": red_gray,
            "red_no_bg": red_gray,
            "green": green_gray,
            "green_no_bg": green_gray,
            "gray_blue": blue_gray,
            "gray_blue_3": blue_gray,
        }
    )


class CENDotMotherDaughterClassificationTests(SimpleTestCase):
    def _run(
        self,
        *,
        red_slots,
        green_slots,
        cell_mask,
        mother_mask,
        daughter_mask,
        neck_split,
        cen_dot_distance: float = 5.0,
        cen_dot_proximity_radius: float = 10.0,
        cen_dot_collinearity_threshold: int = 66,
    ):
        cp = SimpleNamespace(
            image_name="test.dv",
            cell_id=1,
            properties={},
        )
        images = _build_preprocessed_images()
        analysis = CENDot(cp=cp, image=images, output_dir="/tmp")
        contours_data = {
            CELL_MASK_KEY: cell_mask,
            MOTHER_MASK_KEY: mother_mask,
            DAUGHTER_MASK_KEY: daughter_mask,
            NECK_SPLIT_KEY: neck_split,
            CANONICAL_RED_SLOTS_KEY: red_slots,
            CANONICAL_GREEN_SLOTS_KEY: green_slots,
            CANONICAL_BLUE_SLOTS_KEY: [],
        }
        red_image = np.dstack(
            [images.get_image("gray_red")] * 3
        ).astype(np.uint8)
        green_image = np.dstack(
            [images.get_image("green")] * 3
        ).astype(np.uint8)
        analysis.calculate_statistics(
            best_contours=[],
            contours_data=contours_data,
            red_image=red_image,
            green_image=green_image,
            puncta_line_width_input=1,
            cen_dot_distance=cen_dot_distance,
            cen_dot_collinearity_threshold=cen_dot_collinearity_threshold,
            cen_dot_proximity_radius=cen_dot_proximity_radius,
        )
        return cp

    @staticmethod
    def _standard_split() -> NeckSplit:
        return NeckSplit(x1=5, y1=32, x2=34, y2=32, status="ok")

    def test_two_reds_opposite_sides_and_green_in_both_yields_mother_and_daughter(self):
        cell, mother, daughter = _build_side_masks()
        red_top = _disk_slot(0, (20, 15))
        red_bot = _disk_slot(1, (20, 45))
        green_top = _disk_slot(0, (22, 17))
        green_bot = _disk_slot(1, (22, 43))

        cp = self._run(
            red_slots=[red_top, red_bot],
            green_slots=[green_top, green_bot],
            cell_mask=cell,
            mother_mask=mother,
            daughter_mask=daughter,
            neck_split=self._standard_split(),
        )

        self.assertEqual(cp.category_cen_dot, 1)
        payload = cp.properties["cen_dot_location"]
        self.assertEqual(payload["status"], "mother_and_daughter")
        self.assertTrue(payload["green_in_mother"])
        self.assertTrue(payload["green_in_daughter"])
        self.assertTrue(payload["mother_red_has_green"])
        self.assertTrue(payload["daughter_red_has_green"])
        self.assertEqual(payload["green_assignment_rule"], "nearest_red_inside_pair_mask")
        self.assertEqual(cp.properties["cen_dot_schema_version"], 3)
        self.assertEqual(cp.biorientation, 0)

    def test_green_only_in_mother_yields_mother_only(self):
        cell, mother, daughter = _build_side_masks()
        red_top = _disk_slot(0, (20, 15))
        red_bot = _disk_slot(1, (20, 45))
        green_top = _disk_slot(0, (22, 17))

        cp = self._run(
            red_slots=[red_top, red_bot],
            green_slots=[green_top],
            cell_mask=cell,
            mother_mask=mother,
            daughter_mask=daughter,
            neck_split=self._standard_split(),
        )

        self.assertEqual(cp.category_cen_dot, 2)
        self.assertEqual(cp.properties["cen_dot_location"]["status"], "mother_only")

    def test_green_only_in_daughter_yields_daughter_only(self):
        cell, mother, daughter = _build_side_masks()
        red_top = _disk_slot(0, (20, 15))
        red_bot = _disk_slot(1, (20, 45))
        green_bot = _disk_slot(0, (22, 43))

        cp = self._run(
            red_slots=[red_top, red_bot],
            green_slots=[green_bot],
            cell_mask=cell,
            mother_mask=mother,
            daughter_mask=daughter,
            neck_split=self._standard_split(),
        )

        self.assertEqual(cp.category_cen_dot, 3)
        self.assertEqual(cp.properties["cen_dot_location"]["status"], "daughter_only")

    def test_two_reds_on_same_side_yields_na(self):
        cell, mother, daughter = _build_side_masks()
        red_a = _disk_slot(0, (15, 12))
        red_b = _disk_slot(1, (25, 28))
        green_any = _disk_slot(0, (20, 43))

        cp = self._run(
            red_slots=[red_a, red_b],
            green_slots=[green_any],
            cell_mask=cell,
            mother_mask=mother,
            daughter_mask=daughter,
            neck_split=self._standard_split(),
        )

        self.assertEqual(cp.category_cen_dot, 4)
        self.assertEqual(cp.properties["cen_dot_location"]["status"], "reds_same_side")

    def test_more_than_two_usable_reds_yields_na(self):
        cell, mother, daughter = _build_side_masks()
        red_a = _disk_slot(0, (20, 15))
        red_b = _disk_slot(1, (20, 45))
        red_c = _disk_slot(2, (10, 10))

        cp = self._run(
            red_slots=[red_a, red_b, red_c],
            green_slots=[],
            cell_mask=cell,
            mother_mask=mother,
            daughter_mask=daughter,
            neck_split=self._standard_split(),
        )

        self.assertEqual(cp.category_cen_dot, 4)
        payload = cp.properties["cen_dot_location"]
        self.assertEqual(payload["status"], "too_many_reds")
        self.assertEqual(payload["usable_red_count"], 3)

    def test_red_distance_equal_to_threshold_qualifies(self):
        cell, mother, daughter = _build_side_masks()
        # Reds exactly `cen_dot_distance` pixels apart.
        red_top = _disk_slot(0, (20, 15))
        red_bot = _disk_slot(1, (20, 45))
        green_top = _disk_slot(0, (22, 17))
        green_bot = _disk_slot(1, (22, 43))

        cp = self._run(
            red_slots=[red_top, red_bot],
            green_slots=[green_top, green_bot],
            cell_mask=cell,
            mother_mask=mother,
            daughter_mask=daughter,
            neck_split=self._standard_split(),
            cen_dot_distance=30.0,  # exact distance between (20,15) and (20,45)
        )

        self.assertEqual(cp.category_cen_dot, 1)
        payload = cp.properties["cen_dot_location"]
        self.assertAlmostEqual(payload["red_distance"], 30.0, places=4)
        self.assertAlmostEqual(payload["red_distance_threshold_effective"], 30.0, places=4)

    def test_greens_outside_pair_mask_do_not_count(self):
        cell, mother, daughter = _build_side_masks()
        red_top = _disk_slot(0, (20, 15))
        red_bot = _disk_slot(1, (20, 45))
        # Green slot centered outside the cell mask entirely.
        green_outside_mother = _disk_slot(0, (2, 15))
        green_outside_daughter = _disk_slot(1, (2, 45))

        cp = self._run(
            red_slots=[red_top, red_bot],
            green_slots=[green_outside_mother, green_outside_daughter],
            cell_mask=cell,
            mother_mask=mother,
            daughter_mask=daughter,
            neck_split=self._standard_split(),
        )

        self.assertEqual(cp.category_cen_dot, 4)
        payload = cp.properties["cen_dot_location"]
        self.assertEqual(payload["status"], "no_valid_green")
        self.assertFalse(payload["green_in_mother"])
        self.assertFalse(payload["green_in_daughter"])

    def test_green_with_daughter_footprint_can_credit_nearest_mother_red(self):
        cell, mother, daughter = _build_side_masks()
        red_top = _disk_slot(0, (20, 15))
        red_bot = _disk_slot(1, (20, 45))

        daughter_only_mask = np.zeros(SHAPE, dtype=np.uint8)
        cv2.circle(daughter_only_mask, (20, 45), 2, 255, -1)
        daughter_only_mask = cv2.bitwise_and(daughter_only_mask, daughter)
        self.assertTrue(np.any(daughter_only_mask))
        daughter_footprint_green = _slot_with_override(
            source_index=0,
            mask=daughter_only_mask,
            center_xy=(20, 17),
        )

        cp = self._run(
            red_slots=[red_top, red_bot],
            green_slots=[daughter_footprint_green],
            cell_mask=cell,
            mother_mask=mother,
            daughter_mask=daughter,
            neck_split=self._standard_split(),
            cen_dot_proximity_radius=5.0,
        )

        self.assertEqual(cp.category_cen_dot, 2)
        payload = cp.properties["cen_dot_location"]
        self.assertEqual(payload["status"], "mother_only")
        self.assertTrue(payload["mother_red_has_green"])
        self.assertFalse(payload["daughter_red_has_green"])
        self.assertEqual(payload["mother_associated_green_centers"], [[20.0, 17.0]])
        self.assertEqual(payload["ambiguous_green_centers"], [])

    def test_green_with_mother_footprint_can_credit_nearest_daughter_red(self):
        cell, mother, daughter = _build_side_masks()
        red_top = _disk_slot(0, (20, 15))
        red_bot = _disk_slot(1, (20, 45))

        mother_only_mask = np.zeros(SHAPE, dtype=np.uint8)
        cv2.circle(mother_only_mask, (20, 15), 2, 255, -1)
        mother_only_mask = cv2.bitwise_and(mother_only_mask, mother)
        self.assertTrue(np.any(mother_only_mask))
        mother_footprint_green = _slot_with_override(
            source_index=0,
            mask=mother_only_mask,
            center_xy=(20, 43),
        )

        cp = self._run(
            red_slots=[red_top, red_bot],
            green_slots=[mother_footprint_green],
            cell_mask=cell,
            mother_mask=mother,
            daughter_mask=daughter,
            neck_split=self._standard_split(),
            cen_dot_proximity_radius=5.0,
        )

        self.assertEqual(cp.category_cen_dot, 3)
        payload = cp.properties["cen_dot_location"]
        self.assertEqual(payload["status"], "daughter_only")
        self.assertFalse(payload["mother_red_has_green"])
        self.assertTrue(payload["daughter_red_has_green"])
        self.assertEqual(payload["daughter_associated_green_centers"], [[20.0, 43.0]])
        self.assertEqual(payload["ambiguous_green_centers"], [])

    def test_green_inside_both_red_radii_credits_nearest_red_only(self):
        cell, mother, daughter = _build_side_masks()
        red_top = _disk_slot(0, (20, 15))
        red_bot = _disk_slot(1, (20, 45))
        green_nearer_mother = _disk_slot(0, (20, 27))

        cp = self._run(
            red_slots=[red_top, red_bot],
            green_slots=[green_nearer_mother],
            cell_mask=cell,
            mother_mask=mother,
            daughter_mask=daughter,
            neck_split=self._standard_split(),
            cen_dot_proximity_radius=20.0,
        )

        self.assertEqual(cp.category_cen_dot, 2)
        payload = cp.properties["cen_dot_location"]
        self.assertEqual(payload["status"], "mother_only")
        self.assertTrue(payload["mother_red_has_green"])
        self.assertFalse(payload["daughter_red_has_green"])
        self.assertEqual(payload["mother_associated_green_centers"], [[20.0, 27.0]])
        self.assertEqual(payload["daughter_associated_green_centers"], [])
        self.assertEqual(payload["ambiguous_green_centers"], [])

    def test_green_exactly_tied_between_reds_is_recorded_as_ambiguous(self):
        cell, mother, daughter = _build_side_masks()
        red_top = _disk_slot(0, (20, 15))
        red_bot = _disk_slot(1, (20, 45))
        green_tied = _disk_slot(0, (20, 30))

        cp = self._run(
            red_slots=[red_top, red_bot],
            green_slots=[green_tied],
            cell_mask=cell,
            mother_mask=mother,
            daughter_mask=daughter,
            neck_split=self._standard_split(),
            cen_dot_proximity_radius=20.0,
        )

        self.assertEqual(cp.category_cen_dot, 4)
        payload = cp.properties["cen_dot_location"]
        self.assertEqual(payload["status"], "no_valid_green")
        self.assertFalse(payload["mother_red_has_green"])
        self.assertFalse(payload["daughter_red_has_green"])
        self.assertEqual(payload["ambiguous_green_centers"], [[20.0, 30.0]])
        self.assertFalse(payload["green_in_mother"])
        self.assertFalse(payload["green_in_daughter"])

    def test_missing_neck_split_yields_na(self):
        cell, _, _ = _build_side_masks()
        red_top = _disk_slot(0, (20, 15))
        red_bot = _disk_slot(1, (20, 45))
        green_top = _disk_slot(0, (22, 17))

        cp = self._run(
            red_slots=[red_top, red_bot],
            green_slots=[green_top],
            cell_mask=cell,
            mother_mask=None,
            daughter_mask=None,
            neck_split=None,
        )

        self.assertEqual(cp.category_cen_dot, 4)
        payload = cp.properties["cen_dot_location"]
        self.assertEqual(payload["status"], "missing_neck_split")
        self.assertFalse(payload["has_neck_split"])

    def test_reds_below_threshold_path_preserves_biorientation(self):
        """Close reds skip mother/daughter classification but retain biorientation."""
        cell, mother, daughter = _build_side_masks()
        red_a = _disk_slot(0, (15, 20))
        red_b = _disk_slot(1, (25, 20))
        # One green between the two reds to trip biorientation=1.
        green_between = _disk_slot(0, (20, 20))

        cp = self._run(
            red_slots=[red_a, red_b],
            green_slots=[green_between],
            cell_mask=cell,
            mother_mask=mother,
            daughter_mask=daughter,
            neck_split=self._standard_split(),
            cen_dot_distance=50.0,  # reds are 10 px apart, below threshold
        )

        self.assertEqual(cp.category_cen_dot, 4)
        payload = cp.properties["cen_dot_location"]
        self.assertEqual(payload["status"], "reds_below_threshold")
        self.assertEqual(cp.biorientation, 1)
