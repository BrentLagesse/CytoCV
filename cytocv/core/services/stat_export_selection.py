"""Selectable statistics export metadata and validation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from core.services.export_filenames import EXPORT_SCOPE_ALL, EXPORT_SCOPE_SELECTED
from core.services.stat_applicability import STAT_FIELD_GROUPS
from core.tables import CellTable


ALWAYS_INCLUDED_EXPORT_COLUMNS = ("cell_id", "cell_type")
CLIENT_FIELD_ALIASES = {
    "measurement_contour_ratio_1": "green_red_intensity_1",
    "measurement_contour_ratio_2": "green_red_intensity_2",
    "measurement_contour_ratio_3": "green_red_intensity_3",
}
TABLE_FIELD_CLIENT_IDS = {
    table_field: client_field
    for client_field, table_field in CLIENT_FIELD_ALIASES.items()
}
EXPORT_GROUP_LABELS = {
    "puncta_distance": "Puncta Distance",
    "legacy_blue_intensity": "Legacy Blue-Channel",
    "red_green_intensity": "Red/Green Contour Intensities",
    "nuclear_cell_pair_intensity": "Nuclear, Cell-Pair Intensity",
    "cen_dot": "Cen Dot",
    "biorientation": "Biorientation",
}
CONTOUR_INTENSITY_FIELD_RE = re.compile(
    r"^(?P<combination>red_in_red|green_in_red|red_in_green|green_in_green)_"
    r"(?P<statistic>total|max|average)_intensity_(?P<slot>[1-3])$"
)


class ExportColumnSelectionError(ValueError):
    """Raised when a supplied export column selection has no usable stat fields."""


def _table_field_order() -> tuple[str, ...]:
    return tuple(str(field_name) for field_name in CellTable.Meta.fields)


def _user_selectable_table_fields() -> tuple[str, ...]:
    always_included = set(ALWAYS_INCLUDED_EXPORT_COLUMNS)
    return tuple(
        field_name
        for field_name in _table_field_order()
        if field_name not in always_included
    )


TABLE_FIELD_ORDER = _table_field_order()
USER_SELECTABLE_TABLE_FIELDS = _user_selectable_table_fields()
USER_SELECTABLE_TABLE_FIELD_SET = set(USER_SELECTABLE_TABLE_FIELDS)


def export_included_columns(
    raw_columns: Any,
    *,
    columns_present: bool,
) -> tuple[str, ...] | None:
    """Return included table fields, including always-included identity columns."""

    if not columns_present:
        return None
    return (*ALWAYS_INCLUDED_EXPORT_COLUMNS, *normalize_export_columns(raw_columns))


def _client_id_for_table_field(table_field: str) -> str:
    return TABLE_FIELD_CLIENT_IDS.get(table_field, table_field)


def _group_for_table_field(table_field: str) -> str:
    for group_name, field_names in STAT_FIELD_GROUPS.items():
        if table_field in field_names:
            return group_name
    return "other"


def _base_label_for_table_field(table_field: str) -> str:
    table = CellTable([])
    try:
        return str(table.columns[table_field].column.verbose_name)
    except KeyError:
        return table_field.replace("_", " ").title()


def _contour_intensity_metadata(table_field: str) -> dict[str, Any]:
    match = CONTOUR_INTENSITY_FIELD_RE.match(table_field)
    if not match:
        return {}
    return {
        "family": "contour_intensity",
        "combination": match.group("combination"),
        "statistic": match.group("statistic"),
        "slot": int(match.group("slot")),
    }


def export_selection_config() -> dict[str, Any]:
    """Return generic selectable-item metadata for the export modal."""

    group_ids = []
    items = []
    for table_field in USER_SELECTABLE_TABLE_FIELDS:
        group_id = _group_for_table_field(table_field)
        if group_id not in group_ids:
            group_ids.append(group_id)
        item = {
            "type": "stat_column",
            "id": _client_id_for_table_field(table_field),
            "tableField": table_field,
            "label": _base_label_for_table_field(table_field),
            "group": group_id,
            "defaultSelected": True,
            "disabled": False,
            "payloadParam": "_columns",
        }
        item.update(_contour_intensity_metadata(table_field))
        items.append(item)

    return {
        "version": 1,
        "payloadParam": "_columns",
        "alwaysIncluded": [
            {
                "type": "stat_column",
                "id": "cell_id",
                "tableField": "cell_id",
                "label": "Cell ID",
                "group": "identity",
                "defaultSelected": True,
                "disabled": True,
                "payloadParam": "_columns",
            },
            {
                "type": "stat_column",
                "id": "cell_type",
                "tableField": "cell_type",
                "label": "Cell Type",
                "group": "identity",
                "defaultSelected": True,
                "disabled": True,
                "payloadParam": "_columns",
            }
        ],
        "groups": [
            {
                "id": group_id,
                "label": EXPORT_GROUP_LABELS.get(
                    group_id,
                    group_id.replace("_", " ").title(),
                ),
            }
            for group_id in group_ids
        ],
        "items": items,
    }


def _iter_raw_column_tokens(raw_columns: Any) -> Iterable[str]:
    if raw_columns is None:
        return ()
    if isinstance(raw_columns, str):
        values: Iterable[Any] = (raw_columns,)
    elif isinstance(raw_columns, Iterable):
        values = raw_columns
    else:
        values = (raw_columns,)

    tokens: list[str] = []
    for value in values:
        for token in str(value or "").split(","):
            normalized = token.strip()
            if normalized:
                tokens.append(normalized)
    return tokens


def normalize_export_columns(raw_columns: Any) -> tuple[str, ...]:
    """Return valid table fields in canonical export order."""

    requested_fields = {
        CLIENT_FIELD_ALIASES.get(token, token)
        for token in _iter_raw_column_tokens(raw_columns)
    }
    valid_fields = requested_fields & USER_SELECTABLE_TABLE_FIELD_SET
    if not valid_fields:
        raise ExportColumnSelectionError("Select at least one statistic to export.")
    return tuple(
        field_name
        for field_name in USER_SELECTABLE_TABLE_FIELDS
        if field_name in valid_fields
    )


def export_exclude_columns(
    raw_columns: Any,
    *,
    columns_present: bool,
) -> tuple[str, ...] | None:
    """Return ``TableExport`` exclusions, or ``None`` for full fallback export."""

    if not columns_present:
        return None
    selected_fields = set(normalize_export_columns(raw_columns))
    return tuple(
        field_name
        for field_name in USER_SELECTABLE_TABLE_FIELDS
        if field_name not in selected_fields
    )


def export_metric_scope(raw_columns: Any, *, columns_present: bool) -> str:
    """Return whether all user-selectable metric columns are included."""

    if not columns_present:
        return EXPORT_SCOPE_ALL
    selected_fields = set(normalize_export_columns(raw_columns))
    if selected_fields == USER_SELECTABLE_TABLE_FIELD_SET:
        return EXPORT_SCOPE_ALL
    return EXPORT_SCOPE_SELECTED
