"""Request payload helpers for dashboard/display statistics exports."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from core.services.combined_stat_export import StatisticsExportFile


def normalize_uuid_list(raw_values: Any) -> list[str]:
    """Return valid UUID strings in request order, or an empty invalid result."""

    if not isinstance(raw_values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        try:
            value_uuid = str(UUID(str(value)))
        except (TypeError, ValueError, AttributeError):
            return []
        if value_uuid in seen:
            continue
        seen.add(value_uuid)
        normalized.append(value_uuid)
    return normalized


def build_statistics_export_sources(
    ordered_uuids: list[str],
    *,
    uploaded_map: dict[str, Any],
    segmented_map: dict[str, Any],
) -> list[StatisticsExportFile]:
    """Build export source objects without changing the requested file order."""

    return [
        StatisticsExportFile(
            uuid=uuid,
            file_name=uploaded_map[uuid].name,
            segmented_image=segmented_map[uuid],
            scale_info=uploaded_map[uuid].scale_info,
        )
        for uuid in ordered_uuids
    ]
