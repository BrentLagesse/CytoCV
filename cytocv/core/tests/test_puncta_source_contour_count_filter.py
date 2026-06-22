from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from core.services.puncta_source_contour_count_filter import (
    PUNCTA_SOURCE_CONTOUR_FILTER_ALL,
    PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_1,
    PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_2,
    count_valid_contour_slots,
    derive_puncta_source_contour_count_from_statistics,
    filter_statistics_by_puncta_source_contour_count,
    matches_puncta_source_contour_count_filter,
    normalize_puncta_source_contour_count_filter,
    puncta_source_channel_from_statistics,
)


def _row(
    source_count=...,
    *,
    signal_mode="puncta_distance",
    puncta_line_mode="red_puncta",
    source_channel=None,
    red_count=...,
    green_count=...,
    **overrides,
):
    properties = {
        "signal_quantification_mode": signal_mode,
        "puncta_line_mode": puncta_line_mode,
    }
    if source_count is not ...:
        properties["puncta_source_contour_count"] = source_count
    if source_channel is not None:
        properties["puncta_source_contour_count_channel"] = source_channel
    if red_count is not ...:
        properties["red_contour_count"] = red_count
    if green_count is not ...:
        properties["green_contour_count"] = green_count
    defaults = {
        "properties": properties,
        "red_contour_1_size": None,
        "red_contour_2_size": None,
        "red_contour_3_size": None,
        "green_contour_1_size": None,
        "green_contour_2_size": None,
        "green_contour_3_size": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class PunctaSourceContourCountFilterTests(SimpleTestCase):
    def test_normalizes_missing_unknown_blank_and_alias_values(self):
        for value in (None, "", "bad", object(), False):
            with self.subTest(value=value):
                self.assertEqual(
                    normalize_puncta_source_contour_count_filter(value),
                    PUNCTA_SOURCE_CONTOUR_FILTER_ALL,
                )

        self.assertEqual(
            normalize_puncta_source_contour_count_filter("all"),
            PUNCTA_SOURCE_CONTOUR_FILTER_ALL,
        )
        self.assertEqual(
            normalize_puncta_source_contour_count_filter("exactly_1"),
            PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_1,
        )
        self.assertEqual(
            normalize_puncta_source_contour_count_filter("exactly_2"),
            PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_2,
        )
        self.assertEqual(
            normalize_puncta_source_contour_count_filter("1"),
            PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_1,
        )
        self.assertEqual(
            normalize_puncta_source_contour_count_filter("2"),
            PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_2,
        )

    def test_all_includes_rows_with_any_or_unknown_count(self):
        rows = [_row(0), _row(1), _row(2), _row(3), _row(...)]

        self.assertEqual(
            filter_statistics_by_puncta_source_contour_count(rows, "all"),
            rows,
        )

    def test_red_puncta_exact_filters_use_red_source_counts(self):
        rows = [
            _row(0, red_count=0),
            _row(1, red_count=1),
            _row(2, red_count=2),
            _row(3, red_count=3),
            _row(None, red_count=None),
        ]

        self.assertEqual(
            filter_statistics_by_puncta_source_contour_count(rows, "exactly_1"),
            [rows[1]],
        )
        self.assertEqual(
            filter_statistics_by_puncta_source_contour_count(rows, "exactly_2"),
            [rows[2]],
        )
        self.assertEqual(puncta_source_channel_from_statistics(rows[1]), "red")
        self.assertFalse(
            matches_puncta_source_contour_count_filter(rows[0], "exactly_1")
        )
        self.assertFalse(
            matches_puncta_source_contour_count_filter(rows[3], "exactly_2")
        )

    def test_green_puncta_exact_filters_use_green_source_counts(self):
        rows = [
            _row(..., puncta_line_mode="green_puncta", red_count=1, green_count=0),
            _row(..., puncta_line_mode="green_puncta", red_count=2, green_count=1),
            _row(..., puncta_line_mode="green_puncta", red_count=1, green_count=2),
        ]

        self.assertEqual(
            derive_puncta_source_contour_count_from_statistics(rows[1]),
            1,
        )
        self.assertEqual(puncta_source_channel_from_statistics(rows[1]), "green")
        self.assertEqual(
            filter_statistics_by_puncta_source_contour_count(rows, "exactly_2"),
            [rows[2]],
        )

    def test_nuclear_mode_treats_filter_as_all(self):
        row = _row(
            2,
            signal_mode="nuclear_cell_pair",
            puncta_line_mode="red_puncta",
            red_count=2,
        )

        self.assertIsNone(puncta_source_channel_from_statistics(row))
        self.assertIsNone(derive_puncta_source_contour_count_from_statistics(row))
        self.assertTrue(
            matches_puncta_source_contour_count_filter(row, "exactly_1")
        )
        self.assertEqual(
            filter_statistics_by_puncta_source_contour_count([row], "exactly_2"),
            [row],
        )

    def test_malformed_properties_and_missing_old_slots_do_not_crash(self):
        rows = [
            SimpleNamespace(properties=None),
            SimpleNamespace(properties="bad"),
            {"properties": {"puncta_source_contour_count": "bad"}},
        ]

        for row in rows:
            with self.subTest(row=row):
                self.assertIsNone(
                    derive_puncta_source_contour_count_from_statistics(row)
                )
                self.assertTrue(
                    matches_puncta_source_contour_count_filter(row, "all")
                )

    def test_reliable_old_source_size_slots_can_derive_counts(self):
        red_one = _row(
            ...,
            red_contour_1_size=5.0,
            red_contour_2_size=0,
            red_contour_3_size=None,
        )
        green_two = _row(
            ...,
            puncta_line_mode="green_puncta",
            green_contour_1_size=5.0,
            green_contour_2_size="3.2",
            green_contour_3_size="N/A",
            red_contour_1_size=1,
        )
        red_three = _row(
            ...,
            red_contour_1_size=1,
            red_contour_2_size=2,
            red_contour_3_size=3,
        )

        self.assertEqual(derive_puncta_source_contour_count_from_statistics(red_one), 1)
        self.assertEqual(
            derive_puncta_source_contour_count_from_statistics(green_two),
            2,
        )
        self.assertEqual(
            derive_puncta_source_contour_count_from_statistics(red_three),
            3,
        )
        self.assertTrue(
            matches_puncta_source_contour_count_filter(red_one, "exactly_1")
        )
        self.assertTrue(
            matches_puncta_source_contour_count_filter(green_two, "exactly_2")
        )
        self.assertFalse(
            matches_puncta_source_contour_count_filter(red_three, "exactly_2")
        )

    def test_unreliable_old_rows_are_excluded_from_exact_filters(self):
        old_row = _row(
            ...,
            red_contour_1_size=0,
            red_contour_2_size=None,
            red_contour_3_size="N/A",
        )

        self.assertIsNone(
            derive_puncta_source_contour_count_from_statistics(old_row)
        )
        self.assertTrue(
            matches_puncta_source_contour_count_filter(old_row, "all")
        )
        self.assertFalse(
            matches_puncta_source_contour_count_filter(old_row, "exactly_1")
        )
        self.assertFalse(
            matches_puncta_source_contour_count_filter(old_row, "exactly_2")
        )

    def test_filtering_does_not_mutate_source_rows(self):
        rows = [_row(1), _row(2), _row(3)]
        original_ids = [id(row) for row in rows]
        original_properties = [dict(row.properties) for row in rows]

        result = filter_statistics_by_puncta_source_contour_count(rows, "exactly_2")

        self.assertEqual(result, [rows[1]])
        self.assertEqual([id(row) for row in rows], original_ids)
        self.assertEqual([row.properties for row in rows], original_properties)

    def test_count_valid_contour_slots_counts_only_positive_area_slots(self):
        slots = [
            SimpleNamespace(area=12.5),
            SimpleNamespace(area=0),
            {"area": 2},
            {"area": "N/A"},
            SimpleNamespace(area=-1),
        ]

        self.assertEqual(count_valid_contour_slots(slots), 2)
