from datetime import datetime

from django.test import SimpleTestCase
from django.utils import timezone

from core.services.export_filenames import (
    build_statistics_export_filename,
)
from core.services.stat_export_selection import (
    ExportColumnSelectionError,
    CLIENT_FIELD_ALIASES,
    USER_SELECTABLE_TABLE_FIELDS,
    export_exclude_columns,
    export_included_columns,
    export_metric_scope,
    export_selection_config,
    normalize_export_columns,
)


class StatExportSelectionTests(SimpleTestCase):
    def test_statistics_export_filename_uses_scope_count_timestamp_and_extension(self):
        exported_at = timezone.make_aware(
            datetime(2026, 5, 10, 18, 34),
            timezone.get_current_timezone(),
        )

        self.assertEqual(
            build_statistics_export_filename(
                scope="selected",
                file_count=8,
                export_format="csv",
                exported_at=exported_at,
            ),
            "cytocv_selected_cell-metrics_8files_2026-05-10_1834.csv",
        )
        self.assertEqual(
            build_statistics_export_filename(
                scope="all",
                file_count=24,
                export_format="xlsx",
                exported_at=exported_at,
            ),
            "cytocv_all_cell-metrics_24files_2026-05-10_1834.xlsx",
        )

    def test_export_metric_scope_treats_omitted_columns_as_all_metrics(self):
        self.assertEqual(
            export_metric_scope(None, columns_present=False),
            "all",
        )

    def test_export_metric_scope_detects_all_user_selectable_metrics(self):
        self.assertEqual(
            export_metric_scope(USER_SELECTABLE_TABLE_FIELDS, columns_present=True),
            "all",
        )

    def test_export_metric_scope_resolves_aliases_duplicates_and_canonical_fields(self):
        alias_by_table_field = {
            table_field: client_field
            for client_field, table_field in CLIENT_FIELD_ALIASES.items()
        }
        raw_columns = [
            alias_by_table_field.get(table_field, table_field)
            for table_field in USER_SELECTABLE_TABLE_FIELDS
        ]
        raw_columns.extend(
            [
                "measurement_contour_ratio_1",
                "measurement_contour_ratio_2",
                "puncta_distance",
            ]
        )

        self.assertEqual(
            export_metric_scope(raw_columns, columns_present=True),
            "all",
        )

    def test_export_metric_scope_detects_selected_metric_subset(self):
        self.assertEqual(
            export_metric_scope(
                "cytoplasmic_intensity,red_intensity_1,puncta_distance",
                columns_present=True,
            ),
            "selected",
        )

    def test_export_metric_scope_uses_existing_validation(self):
        with self.assertRaises(ExportColumnSelectionError):
            export_metric_scope("cell_id", columns_present=True)
        with self.assertRaises(ExportColumnSelectionError):
            export_metric_scope("unknown_field", columns_present=True)

    def test_valid_columns_are_returned_in_table_order(self):
        selected = normalize_export_columns(
            "cytoplasmic_intensity,puncta_distance,red_intensity_1"
        )

        self.assertEqual(
            selected,
            ("puncta_distance", "red_intensity_1", "cytoplasmic_intensity"),
        )

    def test_contour_center_columns_are_selectable_in_table_order(self):
        selected = normalize_export_columns(
            "green_contour_1_center_xy,blue_contour_center_xy,"
            "red_contour_1_center_xy,red_contour_3_size,red_contour_1_size"
        )

        self.assertEqual(
            selected,
            (
                "blue_contour_center_xy",
                "red_contour_1_size",
                "red_contour_3_size",
                "red_contour_1_center_xy",
                "green_contour_1_center_xy",
            ),
        )

    def test_duplicate_fields_collapse_without_changing_order(self):
        selected = normalize_export_columns(
            [
                "red_intensity_1,puncta_distance",
                "puncta_distance",
                "red_intensity_1",
            ]
        )

        self.assertEqual(selected, ("puncta_distance", "red_intensity_1"))

    def test_unknown_fields_are_ignored_when_valid_fields_are_present(self):
        selected = normalize_export_columns("unknown_field,cell_id,nucleus_intensity_sum")

        self.assertEqual(selected, ("nucleus_intensity_sum",))

    def test_invalid_only_columns_raise_validation_error(self):
        with self.assertRaises(ExportColumnSelectionError):
            normalize_export_columns("unknown_field,cell_id")

    def test_empty_present_columns_raise_validation_error(self):
        with self.assertRaises(ExportColumnSelectionError):
            export_exclude_columns("", columns_present=True)

    def test_ratio_aliases_map_to_table_fields(self):
        selected = normalize_export_columns(
            "measurement_contour_ratio_3,measurement_contour_ratio_1"
        )

        self.assertEqual(
            selected,
            ("green_red_intensity_1", "green_red_intensity_3"),
        )

    def test_cell_id_is_not_user_selectable(self):
        with self.assertRaises(ExportColumnSelectionError):
            normalize_export_columns("cell_id")

    def test_included_columns_always_keep_cell_id_first(self):
        included_columns = export_included_columns(
            "red_intensity_1,puncta_distance",
            columns_present=True,
        )

        self.assertEqual(
            included_columns,
            ("cell_id", "puncta_distance", "red_intensity_1"),
        )

    def test_exclude_columns_excludes_every_unselected_stat_field(self):
        exclude_columns = export_exclude_columns(
            "puncta_distance,measurement_contour_ratio_1",
            columns_present=True,
        )

        self.assertIsNotNone(exclude_columns)
        self.assertNotIn("cell_id", exclude_columns)
        self.assertNotIn("puncta_distance", exclude_columns)
        self.assertNotIn("green_red_intensity_1", exclude_columns)
        self.assertIn("puncta_line_intensity", exclude_columns)
        self.assertIn("red_contour_1_center_xy", exclude_columns)
        self.assertIn("nucleus_intensity_sum", exclude_columns)

    def test_missing_columns_parameter_preserves_full_export(self):
        self.assertIsNone(export_exclude_columns(None, columns_present=False))

    def test_export_selection_config_uses_generic_selectable_items(self):
        config = export_selection_config()
        first_item = config["items"][0]

        self.assertEqual(first_item["type"], "stat_column")
        self.assertIn("payloadParam", first_item)
        self.assertEqual(config["payloadParam"], "_columns")
        self.assertEqual(config["alwaysIncluded"][0]["id"], "cell_id")
        self.assertTrue(
            any(item["id"] == "red_contour_1_center_xy" for item in config["items"])
        )
