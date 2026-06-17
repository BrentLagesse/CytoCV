from __future__ import annotations

import json
import math
from uuid import UUID


def parse_file_scale_map_payload(
    raw_payload: str,
    active_uuid_set: set[str],
) -> tuple[dict[str, float], str | None, int]:
    if not raw_payload:
        return {}, None, 200
    try:
        payload = json.loads(raw_payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}, "Invalid per-file scale payload.", 400
    if not isinstance(payload, dict):
        return {}, "Per-file scale payload must be a JSON object.", 400

    parsed: dict[str, float] = {}
    for raw_uuid, raw_value in payload.items():
        try:
            normalized_uuid = str(UUID(str(raw_uuid)))
        except (TypeError, ValueError, AttributeError):
            return {}, "Per-file scale payload contains an invalid UUID.", 400
        if normalized_uuid not in active_uuid_set:
            return {}, "Per-file scale payload contains unavailable files.", 403

        value = raw_value
        if isinstance(raw_value, dict):
            value = raw_value.get("effective_um_per_px")
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return {}, "Per-file scale values must be numeric.", 400
        if not math.isfinite(numeric) or numeric <= 0:
            return {}, "Per-file scale values must be greater than 0.", 400
        parsed[normalized_uuid] = numeric
    return parsed, None, 200


def parse_file_scale_revert_payload(
    raw_payload: str,
    active_uuid_set: set[str],
) -> tuple[set[str], str | None, int]:
    if not raw_payload:
        return set(), None, 200
    try:
        payload = json.loads(raw_payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return set(), "Invalid scale revert payload.", 400
    if not isinstance(payload, list):
        return set(), "Scale revert payload must be a JSON array.", 400

    parsed: set[str] = set()
    for raw_uuid in payload:
        try:
            normalized_uuid = str(UUID(str(raw_uuid)))
        except (TypeError, ValueError, AttributeError):
            return set(), "Scale revert payload contains an invalid UUID.", 400
        if normalized_uuid not in active_uuid_set:
            return set(), "Scale revert payload contains unavailable files.", 403
        parsed.add(normalized_uuid)
    return parsed, None, 200
