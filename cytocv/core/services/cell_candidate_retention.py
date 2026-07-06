"""Candidate typing and retention for DIC segmentation labels."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.cell_types import (
    CELL_INCLUSION_MODE_PAIRS_ONLY,
    CELL_INCLUSION_MODE_SINGLES_AND_PAIRS,
    CELL_INCLUSION_MODE_SINGLES_ONLY,
    CELL_TYPE_PAIR,
    CELL_TYPE_SINGLE,
    normalize_cell_inclusion_mode,
)
from core.contour_processing import get_neighbor_count


@dataclass(frozen=True, slots=True)
class CellCandidateRecord:
    """A typed candidate retained or excluded before final label rebasing."""

    primary_label: int
    source_labels: tuple[int, ...]
    cell_type: str


def retains_candidate_type(cell_type: str, inclusion_mode: str) -> bool:
    """Return whether an analysis mode retains a typed candidate."""

    normalized_mode = normalize_cell_inclusion_mode(inclusion_mode)
    if normalized_mode == CELL_INCLUSION_MODE_PAIRS_ONLY:
        return cell_type == CELL_TYPE_PAIR
    if normalized_mode == CELL_INCLUSION_MODE_SINGLES_ONLY:
        return cell_type == CELL_TYPE_SINGLE
    if normalized_mode == CELL_INCLUSION_MODE_SINGLES_AND_PAIRS:
        return cell_type in {CELL_TYPE_SINGLE, CELL_TYPE_PAIR}
    return False


def build_retained_candidate_label_image(
    seg: np.ndarray,
    inclusion_mode: str,
) -> tuple[np.ndarray, dict[int, str]]:
    """Return final label image and final-label cell types for one mask image."""

    working = np.array(seg, copy=True)
    single_labels: set[int] = set()
    unknown_labels: set[int] = set()
    closest_neighbors: dict[int, int] = {}
    neighbor_count: dict[int, int] = {}

    for i in range(1, int(np.max(working) + 1)):
        cells = np.where(working == i)
        for cell in zip(cells[0], cells[1]):
            try:
                neighbor_list = get_neighbor_count(working, cell, 3)
            except Exception:
                continue
            for neighbor in neighbor_list:
                neighbor_id = int(neighbor)
                if neighbor_id == i or neighbor_id == 0:
                    continue
                neighbor_count[neighbor_id] = neighbor_count.get(neighbor_id, 0) + 1

        sorted_neighbors = sorted(
            neighbor_count.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        if len(sorted_neighbors) == 0:
            single_labels.add(int(i))
        elif len(sorted_neighbors) == 1:
            closest_neighbors[int(i)] = int(sorted_neighbors[0][0])
        else:
            top_val = sorted_neighbors[0][1]
            second_val = sorted_neighbors[1][1]
            if second_val > 0.5 * top_val:
                unknown_labels.add(int(i))
                for cluster_cell in neighbor_count:
                    unknown_labels.add(int(cluster_cell))
            else:
                closest_neighbors[int(i)] = int(sorted_neighbors[0][0])
        neighbor_count = {}

    ignored_labels: set[int] = set()
    candidates: list[CellCandidateRecord] = [
        CellCandidateRecord(
            primary_label=label,
            source_labels=(label,),
            cell_type=CELL_TYPE_SINGLE,
        )
        for label in sorted(single_labels - unknown_labels)
    ]

    for k, v in closest_neighbors.items():
        if int(k) in unknown_labels:
            continue
        if v in closest_neighbors:
            if int(v) in ignored_labels:
                unknown_labels.add(int(k))
                continue

            if closest_neighbors[int(v)] == int(k) and int(k) not in ignored_labels:
                to_update = np.where(working == v)
                ignored_labels.add(int(v))
                for update in zip(to_update[0], to_update[1]):
                    working[update[0]][update[1]] = k
                candidates.append(
                    CellCandidateRecord(
                        primary_label=int(k),
                        source_labels=(int(k), int(v)),
                        cell_type=CELL_TYPE_PAIR,
                    )
                )
            elif int(k) not in ignored_labels:
                unknown_labels.add(int(k))
        elif int(k) not in ignored_labels:
            unknown_labels.add(int(k))

    retained_candidates = {
        candidate.primary_label: candidate
        for candidate in candidates
        if candidate.primary_label not in unknown_labels
        and retains_candidate_type(candidate.cell_type, inclusion_mode)
    }
    retained_labels = sorted(retained_candidates)

    for label in range(1, int(np.max(working) + 1)):
        if label not in retained_candidates:
            working[np.where(working == label)] = 0.0

    cell_type_by_label: dict[int, str] = {}
    for final_index, source_label in enumerate(retained_labels, start=1):
        working[np.where(working == source_label)] = final_index
        cell_type_by_label[final_index] = retained_candidates[source_label].cell_type

    return working, cell_type_by_label
