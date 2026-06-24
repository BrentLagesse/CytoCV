"""Regression tests for Cell Inclusion Mode candidate and row filtering."""

from __future__ import annotations

import csv
from io import StringIO
from uuid import uuid4

import numpy as np
from django.contrib.auth import get_user_model
from django.test import TestCase

from core.cell_types import (
    CELL_INCLUSION_MODE_PAIRS_ONLY,
    CELL_INCLUSION_MODE_SINGLES_AND_PAIRS,
    CELL_INCLUSION_MODE_SINGLES_ONLY,
    CELL_TYPE_FILTER_PAIR,
    CELL_TYPE_FILTER_SINGLE,
    CELL_TYPE_PAIR,
    CELL_TYPE_SINGLE,
    CELL_TYPE_UNKNOWN,
    filter_statistics_by_cell_type,
    matches_cell_type_filter,
)
from core.models import CellStatistics, SegmentedImage, UploadedImage
from core.services.analysis_context import normalize_analysis_config_snapshot
from core.services.analysis_jobs import enqueue_analysis_job
from core.services.cell_candidate_retention import build_retained_candidate_label_image
from core.services.cell_statistics_payload import serialize_cell_statistics_payload
from core.services.combined_stat_export import (
    StatisticsExportFile,
    build_combined_statistics_export_response,
)
from core.services.puncta_source_contour_count_filter import (
    PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_1,
    PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_2,
    filter_statistics_by_puncta_source_contour_count,
)
from core.services.stat_export_selection import export_included_columns
from core.tables import CellTable


def _pair_and_single_mask() -> np.ndarray:
    seg = np.zeros((40, 40), dtype=np.float64)
    seg[10:14, 10:14] = 1.0
    seg[10:14, 16:20] = 2.0
    seg[28:32, 28:32] = 3.0
    return seg


def _ambiguous_mask() -> np.ndarray:
    seg = np.zeros((40, 40), dtype=np.float64)
    seg[10:14, 8:12] = 1.0
    seg[10:14, 14:18] = 2.0
    seg[10:14, 20:24] = 3.0
    return seg


class CellInclusionCandidateTests(TestCase):
    def test_pairs_only_mode_preserves_pair_and_removes_single(self):
        result, cell_type_by_label = build_retained_candidate_label_image(
            _pair_and_single_mask(),
            CELL_INCLUSION_MODE_PAIRS_ONLY,
        )

        self.assertEqual(cell_type_by_label, {1: CELL_TYPE_PAIR})
        self.assertEqual(set(np.unique(result)) - {0}, {1.0})
        self.assertTrue(np.all(result[10:14, 10:14] == 1.0))
        self.assertTrue(np.all(result[10:14, 16:20] == 1.0))
        self.assertTrue(np.all(result[28:32, 28:32] == 0.0))

    def test_single_only_mode_keeps_detected_single_and_excludes_pair(self):
        result, cell_type_by_label = build_retained_candidate_label_image(
            _pair_and_single_mask(),
            CELL_INCLUSION_MODE_SINGLES_ONLY,
        )

        self.assertEqual(cell_type_by_label, {1: CELL_TYPE_SINGLE})
        self.assertEqual(set(np.unique(result)) - {0}, {1.0})
        self.assertTrue(np.all(result[10:14, 10:14] == 0.0))
        self.assertTrue(np.all(result[10:14, 16:20] == 0.0))
        self.assertTrue(np.all(result[28:32, 28:32] == 1.0))

    def test_both_mode_keeps_detected_single_and_pair(self):
        result, cell_type_by_label = build_retained_candidate_label_image(
            _pair_and_single_mask(),
            CELL_INCLUSION_MODE_SINGLES_AND_PAIRS,
        )

        self.assertEqual(cell_type_by_label, {1: CELL_TYPE_PAIR, 2: CELL_TYPE_SINGLE})
        self.assertEqual(set(np.unique(result)) - {0}, {1.0, 2.0})
        self.assertTrue(np.all(result[10:14, 10:14] == 1.0))
        self.assertTrue(np.all(result[10:14, 16:20] == 1.0))
        self.assertTrue(np.all(result[28:32, 28:32] == 2.0))

    def test_ambiguous_non_mutual_labels_are_excluded(self):
        result, cell_type_by_label = build_retained_candidate_label_image(
            _ambiguous_mask(),
            CELL_INCLUSION_MODE_SINGLES_AND_PAIRS,
        )

        self.assertEqual(cell_type_by_label, {})
        self.assertEqual(set(np.unique(result)) - {0}, set())


class CellInclusionPersistenceAndFilteringTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="cell-inclusion@example.com",
            password="TestPass123!",
        )
        file_uuid = uuid4()
        self.uploaded = UploadedImage.objects.create(
            user=self.user,
            uuid=file_uuid,
            name="cell_inclusion",
            file_location=f"{file_uuid}/cell_inclusion.dv",
        )
        self.segmented = SegmentedImage.objects.create(
            user_id=self.user.id,
            UUID=file_uuid,
            file_location=f"user_{file_uuid}/segmented.png",
            ImagePath=f"{file_uuid}/output/cell_inclusion_frame_0.png",
            CellPairPrefix=f"{file_uuid}/segmented/cell_",
            NumCells=3,
            cell_inclusion_mode=CELL_INCLUSION_MODE_SINGLES_AND_PAIRS,
        )

    def _create_stat(self, *, cell_id: int, cell_type: str, source_count: int) -> CellStatistics:
        return CellStatistics.objects.create(
            segmented_image=self.segmented,
            cell_id=cell_id,
            cell_type=cell_type,
            puncta_distance=1.0,
            puncta_line_intensity=2.0,
            nucleus_intensity_sum=3.0,
            cell_pair_intensity_sum=4.0,
            red_contour_1_size=8.0 if source_count >= 1 else 0.0,
            red_contour_2_size=9.0 if source_count >= 2 else 0.0,
            properties={
                "cell_type": cell_type,
                "selected_analysis": ["PunctaDistance", "GreenRedIntensity"],
                "signal_quantification_mode": "puncta_distance",
                "puncta_line_mode": "red_puncta",
                "puncta_source_contour_count": source_count,
                "puncta_source_contour_count_channel": "red",
            },
        )

    def test_cell_type_persists_payload_and_table_render_label(self):
        stat = self._create_stat(cell_id=1, cell_type=CELL_TYPE_SINGLE, source_count=1)
        stat.refresh_from_db()

        payload = serialize_cell_statistics_payload(stat)
        table_values = list(CellTable([stat]).as_values())

        self.assertEqual(stat.cell_type, CELL_TYPE_SINGLE)
        self.assertEqual(payload["cell_type"], CELL_TYPE_SINGLE)
        self.assertEqual(payload["cell_type_label"], "Single Cell")
        self.assertEqual(table_values[0][:2], ["Cell ID", "Cell Type"])
        self.assertEqual(table_values[1][1], "Single Cell")

    def test_old_or_missing_cell_type_matches_all_filter_only(self):
        unknown = self._create_stat(cell_id=1, cell_type=CELL_TYPE_UNKNOWN, source_count=1)

        self.assertTrue(matches_cell_type_filter(unknown, "all"))
        self.assertFalse(matches_cell_type_filter(unknown, CELL_TYPE_FILTER_SINGLE))
        self.assertFalse(matches_cell_type_filter(unknown, CELL_TYPE_FILTER_PAIR))

    def test_cell_type_filter_composes_before_source_contour_filter(self):
        single_one = self._create_stat(cell_id=1, cell_type=CELL_TYPE_SINGLE, source_count=1)
        single_two = self._create_stat(cell_id=2, cell_type=CELL_TYPE_SINGLE, source_count=2)
        pair_two = self._create_stat(cell_id=3, cell_type=CELL_TYPE_PAIR, source_count=2)

        single_rows = filter_statistics_by_cell_type(
            [single_one, single_two, pair_two],
            CELL_TYPE_FILTER_SINGLE,
        )

        self.assertEqual(
            [stat.cell_id for stat in filter_statistics_by_puncta_source_contour_count(
                single_rows,
                PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_1,
            )],
            [1],
        )
        self.assertEqual(
            [stat.cell_id for stat in filter_statistics_by_puncta_source_contour_count(
                single_rows,
                PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_2,
            )],
            [2],
        )

        pair_rows = filter_statistics_by_cell_type(
            [single_one, single_two, pair_two],
            CELL_TYPE_FILTER_PAIR,
        )
        self.assertEqual(
            [stat.cell_id for stat in filter_statistics_by_puncta_source_contour_count(
                pair_rows,
                PUNCTA_SOURCE_CONTOUR_FILTER_EXACTLY_2,
            )],
            [3],
        )

    def test_selected_combined_export_respects_cell_type_row_filter(self):
        self._create_stat(cell_id=1, cell_type=CELL_TYPE_SINGLE, source_count=1)
        self._create_stat(cell_id=2, cell_type=CELL_TYPE_PAIR, source_count=1)

        response = build_combined_statistics_export_response(
            [
                StatisticsExportFile(
                    uuid=str(self.segmented.UUID),
                    file_name="cell_inclusion",
                    segmented_image=self.segmented,
                )
            ],
            export_format="csv",
            raw_columns=["puncta_distance"],
            spatial_stats_unit="px",
            default_manual_scale=0.1,
            cell_type_filter=CELL_TYPE_FILTER_SINGLE,
        )
        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))

        self.assertEqual(rows[0][:4], ["File Name", "Cell ID", "Cell Type", "Puncta Distance (px)"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][2], "Single Cell")
        self.assertNotIn("Cell Pair", response.content.decode("utf-8"))

    def test_selected_export_identity_columns_are_independent_from_metric_columns(self):
        self.assertEqual(
            export_included_columns(["puncta_distance"], columns_present=True)[:2],
            ("cell_id", "cell_type"),
        )

    def test_analysis_job_snapshot_normalizes_cell_inclusion_mode(self):
        job, created = enqueue_analysis_job(
            user_id=self.user.id,
            raw_uuids=[str(self.uploaded.uuid)],
            config_snapshot={
                "execution_mode": "worker",
                "cell_inclusion_mode": CELL_INCLUSION_MODE_SINGLES_ONLY,
            },
        )

        self.assertTrue(created)
        self.assertEqual(
            job.config_snapshot["cell_inclusion_mode"],
            CELL_INCLUSION_MODE_SINGLES_ONLY,
        )

    def test_analysis_snapshot_defaults_invalid_cell_inclusion_mode_to_pairs_only(self):
        self.assertEqual(
            normalize_analysis_config_snapshot({"cell_inclusion_mode": "bad"})[
                "cell_inclusion_mode"
            ],
            CELL_INCLUSION_MODE_PAIRS_ONLY,
        )
