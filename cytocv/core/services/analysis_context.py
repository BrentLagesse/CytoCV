"""Shared analysis execution context helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from django.conf import settings

from accounts.preferences import should_auto_save_experiments
from core.services.puncta_line_mode import (
    DEFAULT_PUNCTA_LINE_MODE,
    normalize_puncta_line_mode,
)

NUCLEAR_CELL_PAIR_MODES = frozenset({"green_nucleus", "red_nucleus"})
DEFAULT_ANALYSIS_CONFIG_SNAPSHOT = {
    "selected_analysis": [],
    "punctaLineWidth": 1,
    "cenDotDistance": 37,
    "cenDotCollinearityThreshold": 66,
    "stats_puncta_line_width_unit": "px",
    "stats_cen_dot_distance_unit": "px",
    "stats_microns_per_pixel": 0.1,
    "stats_use_metadata_scale": True,
    "stats_puncta_line_width_value": 1.0,
    "stats_cen_dot_distance_value": 37.0,
    "puncta_line_mode": DEFAULT_PUNCTA_LINE_MODE,
    "nuclear_cell_pair_mode": "green_nucleus",
    "greenContourFilterEnabled": False,
    "alternateRedDetection": False,
    "auto_save_experiments": True,
    "execution_mode": "sync",
}


@dataclass(frozen=True, slots=True)
class AnalysisBatchContext:
    """Whitelisted immutable input for an analysis batch."""

    batch_key: str
    run_uuids: tuple[str, ...]
    user_id: int
    config_snapshot: dict[str, object]
    execution_mode: str


def _parse_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: object, *, default: int, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and parsed < minimum:
        return default
    return parsed


def _parse_float(value: object, *, default: float, minimum: float | None = None) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and parsed < minimum:
        return default
    return parsed


def normalize_uuid_list(raw_values: Iterable[object] | str) -> tuple[str, ...]:
    """Return a normalized ordered UUID tuple."""

    if isinstance(raw_values, str):
        values = [part.strip() for part in raw_values.split(",")]
    else:
        values = [str(value).strip() for value in raw_values]

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        normalized_uuid = str(UUID(value))
        if normalized_uuid in seen:
            continue
        seen.add(normalized_uuid)
        normalized.append(normalized_uuid)
    return tuple(normalized)


def build_batch_key(raw_values: Iterable[object] | str) -> str:
    """Return the canonical batch key for a set of UUIDs."""

    return ",".join(normalize_uuid_list(raw_values))


def normalize_execution_mode(value: object | None = None) -> str:
    """Normalize sync vs worker execution mode."""

    candidate = str(value or settings.ANALYSIS_EXECUTION_MODE).strip().lower()
    if candidate not in {"sync", "worker"}:
        return "sync"
    return candidate


def normalize_analysis_config_snapshot(snapshot: dict[str, object] | None) -> dict[str, object]:
    """Normalize a persisted analysis snapshot back into safe runtime values."""

    payload = dict(DEFAULT_ANALYSIS_CONFIG_SNAPSHOT)
    if snapshot:
        payload.update(snapshot)

    selected_analysis = payload.get("selected_analysis") or []
    if not isinstance(selected_analysis, list):
        selected_analysis = list(selected_analysis) if isinstance(selected_analysis, tuple) else []

    nuclear_cell_pair_mode = str(
        payload.get(
            "nuclear_cell_pair_mode",
            payload.get(
                "nuclear_cellular_mode",
                DEFAULT_ANALYSIS_CONFIG_SNAPSHOT["nuclear_cell_pair_mode"],
            ),
        )
    ).strip()
    if nuclear_cell_pair_mode not in NUCLEAR_CELL_PAIR_MODES:
        nuclear_cell_pair_mode = DEFAULT_ANALYSIS_CONFIG_SNAPSHOT["nuclear_cell_pair_mode"]
    puncta_line_mode = normalize_puncta_line_mode(
        payload.get(
            "puncta_line_mode",
            DEFAULT_ANALYSIS_CONFIG_SNAPSHOT["puncta_line_mode"],
        ),
        default=DEFAULT_ANALYSIS_CONFIG_SNAPSHOT["puncta_line_mode"],
    )

    normalized = {
        "selected_analysis": [str(item) for item in selected_analysis if str(item)],
        "punctaLineWidth": _parse_int(
            payload.get(
                "punctaLineWidth",
                payload.get("redLineWidth", payload.get("mCherryWidth")),
            ),
            default=1,
            minimum=1,
        ),
        "cenDotDistance": _parse_int(
            payload.get("cenDotDistance", payload.get("distance")),
            default=37,
            minimum=0,
        ),
        "cenDotCollinearityThreshold": _parse_int(
            payload.get("cenDotCollinearityThreshold", payload.get("threshold")),
            default=66,
            minimum=0,
        ),
        "stats_puncta_line_width_unit": "um"
        if str(
            payload.get(
                "stats_puncta_line_width_unit",
                payload.get("stats_red_line_width_unit", payload.get("stats_mcherry_width_unit", "px")),
            )
        ).strip().lower() == "um"
        else "px",
        "stats_cen_dot_distance_unit": "um"
        if str(payload.get("stats_cen_dot_distance_unit", payload.get("stats_gfp_distance_unit", "px"))).strip().lower() == "um"
        else "px",
        "stats_microns_per_pixel": _parse_float(
            payload.get("stats_microns_per_pixel"),
            default=0.1,
            minimum=0.000001,
        ),
        "stats_use_metadata_scale": _parse_bool(
            payload.get("stats_use_metadata_scale"),
            default=True,
        ),
        "stats_puncta_line_width_value": _parse_float(
            payload.get(
                "stats_puncta_line_width_value",
                payload.get("stats_red_line_width_value", payload.get("stats_mcherry_width_value")),
            ),
            default=1.0,
            minimum=0.0,
        ),
        "stats_cen_dot_distance_value": _parse_float(
            payload.get("stats_cen_dot_distance_value", payload.get("stats_gfp_distance_value")),
            default=37.0,
            minimum=0.0,
        ),
        "puncta_line_mode": puncta_line_mode,
        "nuclear_cell_pair_mode": nuclear_cell_pair_mode,
        "greenContourFilterEnabled": _parse_bool(
            payload.get("greenContourFilterEnabled", payload.get("gfpFilterEnabled")),
            default=False,
        ),
        "alternateRedDetection": _parse_bool(
            payload.get("alternateRedDetection", payload.get("alternateMCherryDetection")),
            default=False,
        ),
        "auto_save_experiments": _parse_bool(
            payload.get("auto_save_experiments"),
            default=True,
        ),
        "execution_mode": normalize_execution_mode(payload.get("execution_mode")),
    }
    return normalized


def build_analysis_config_snapshot(request) -> dict[str, object]:
    """Build the whitelisted session-backed analysis snapshot for a request."""

    snapshot = {
        "selected_analysis": request.session.get("selected_analysis", []),
        "punctaLineWidth": request.session.get(
            "punctaLineWidth",
            request.session.get("redLineWidth", request.session.get("mCherryWidth", 1)),
        ),
        "cenDotDistance": request.session.get("cenDotDistance", request.session.get("distance", 37)),
        "cenDotCollinearityThreshold": request.session.get("cenDotCollinearityThreshold", request.session.get("threshold", 66)),
        "stats_puncta_line_width_unit": request.session.get(
            "stats_puncta_line_width_unit",
            request.session.get("stats_red_line_width_unit", request.session.get("stats_mcherry_width_unit", "px")),
        ),
        "stats_cen_dot_distance_unit": request.session.get("stats_cen_dot_distance_unit", request.session.get("stats_gfp_distance_unit", "px")),
        "stats_microns_per_pixel": request.session.get("stats_microns_per_pixel", 0.1),
        "stats_use_metadata_scale": request.session.get("stats_use_metadata_scale", True),
        "stats_puncta_line_width_value": request.session.get(
            "stats_puncta_line_width_value",
            request.session.get("stats_red_line_width_value", request.session.get("stats_mcherry_width_value", 1.0)),
        ),
        "stats_cen_dot_distance_value": request.session.get("stats_cen_dot_distance_value", request.session.get("stats_gfp_distance_value", 37.0)),
        "puncta_line_mode": request.session.get("puncta_line_mode", DEFAULT_PUNCTA_LINE_MODE),
        "nuclear_cell_pair_mode": request.session.get(
            "nuclear_cell_pair_mode",
            request.session.get("nuclear_cellular_mode", "green_nucleus"),
        ),
        "greenContourFilterEnabled": request.session.get("greenContourFilterEnabled", request.session.get("gfpFilterEnabled", False)),
        "alternateRedDetection": request.session.get("alternateRedDetection", request.session.get("alternateMCherryDetection", False)),
        "auto_save_experiments": should_auto_save_experiments(request.user)
        if getattr(request.user, "is_authenticated", False)
        else True,
        "execution_mode": normalize_execution_mode(),
    }
    return normalize_analysis_config_snapshot(snapshot)


def build_analysis_batch_context(request, raw_uuids: Iterable[object] | str) -> AnalysisBatchContext:
    """Build the immutable runtime context for a request-scoped batch."""

    run_uuids = normalize_uuid_list(raw_uuids)
    return AnalysisBatchContext(
        batch_key=",".join(run_uuids),
        run_uuids=run_uuids,
        user_id=int(request.user.id),
        config_snapshot=build_analysis_config_snapshot(request),
        execution_mode=normalize_execution_mode(),
    )
