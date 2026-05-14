"""Reusable download filenames for exported statistics."""

from __future__ import annotations

from datetime import datetime

from django.utils import timezone


EXPORT_SCOPE_ALL = "all"
EXPORT_SCOPE_SELECTED = "selected"
EXPORT_SCOPES = {EXPORT_SCOPE_ALL, EXPORT_SCOPE_SELECTED}
EXPORT_FORMAT_EXTENSIONS = {"csv": "csv", "xlsx": "xlsx"}


def build_statistics_export_filename(
    *,
    scope: str,
    file_count: int,
    export_format: str,
    exported_at: datetime | None = None,
) -> str:
    """Build a stable, readable statistics export attachment filename."""

    normalized_scope = str(scope or "").strip().lower()
    if normalized_scope not in EXPORT_SCOPES:
        normalized_scope = EXPORT_SCOPE_SELECTED

    extension = EXPORT_FORMAT_EXTENSIONS.get(str(export_format or "").strip().lower())
    if extension is None:
        extension = "csv"

    try:
        normalized_file_count = max(int(file_count), 0)
    except (TypeError, ValueError):
        normalized_file_count = 0

    timestamp = timezone.localtime(exported_at or timezone.now()).strftime(
        "%Y-%m-%d_%H%M"
    )
    return (
        f"cytocv_{normalized_scope}_cell-metrics_"
        f"{normalized_file_count}files_{timestamp}.{extension}"
    )
