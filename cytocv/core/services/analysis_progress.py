"""Progress and cancellation helpers for sync and worker analysis execution."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from cytocv.settings import MEDIA_ROOT
from core.models import AnalysisJob
from core.services.analysis_jobs import (
    get_latest_analysis_job,
    request_job_cancellation,
    resolve_stale_job,
)

logger = logging.getLogger(__name__)
NORMALIZED_PROGRESS_STATUSES = frozenset(
    {
        "idle",
        "queued",
        "running",
        "cancelling",
        "succeeded",
        "failed",
        "cancelled",
    }
)


def _normalize_status(*, phase: str, status: str | None) -> str:
    candidate = str(status or "").strip().lower()
    phase_candidate = str(phase or "").strip().lower()
    status_map = {
        "completed": "succeeded",
        "complete": "succeeded",
        "success": "succeeded",
        "queued": "queued",
        "queue": "queued",
        "running": "running",
        "preprocessing images": "running",
        "detecting cells": "running",
        "segmenting images": "running",
        "calculating statistics": "running",
        "cancelling": "cancelling",
        "canceling": "cancelling",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "failed": "failed",
        "error": "failed",
        "idle": "idle",
    }
    normalized = status_map.get(candidate)
    if normalized:
        return normalized

    phase_normalized = status_map.get(phase_candidate)
    if phase_normalized:
        return phase_normalized

    if candidate in NORMALIZED_PROGRESS_STATUSES:
        return candidate
    return "failed" if candidate else "idle"


def _log_inconsistent_snapshot(
    *,
    batch_key: str,
    phase: str,
    status: str,
    failure_summary: str,
) -> None:
    terminal_phase = str(phase).strip().lower() in {"completed", "failed", "cancelled", "canceled"}
    terminal_status = status in {"succeeded", "failed", "cancelled"}
    if terminal_phase and not terminal_status:
        logger.warning(
            "Progress snapshot has terminal phase with non-terminal status",
            extra={
                "batch_key": batch_key,
                "phase": phase,
                "status": status,
                "failure_summary": failure_summary,
            },
        )


def progress_path(key: str) -> Path:
    """Return the JSON progress path for a batch key."""

    root = Path(MEDIA_ROOT) / "progress"
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return root / f"{digest}.json"


def cancel_path(key: str) -> Path:
    """Return the filesystem cancel marker path for a batch key."""

    root = Path(MEDIA_ROOT) / "progress"
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return root / f"{digest}.cancel"


def read_file_progress(key: str) -> dict[str, object]:
    """Read the mirrored filesystem progress payload."""

    try:
        path = progress_path(key)
        if path.exists():
            return json.loads(path.read_text() or "{}")
    except (OSError, IOError, PermissionError, json.JSONDecodeError):
        return {}
    return {}


def write_file_progress(
    key: str,
    *,
    phase: str,
    status: str | None = None,
    failure_summary: str = "",
) -> None:
    """Write the mirrored filesystem progress payload."""

    payload = {
        "phase": phase,
        "status": status,
        "failure_summary": failure_summary,
    }
    try:
        progress_path(key).write_text(json.dumps(payload))
    except (OSError, IOError, PermissionError):
        logger.debug("Failed to write progress payload for %s", key)


def is_cancelled(key: str) -> bool:
    """Return whether the filesystem cancel marker exists."""

    try:
        return cancel_path(key).exists()
    except (OSError, IOError, PermissionError):
        return False


def set_cancelled(key: str) -> None:
    """Write the filesystem cancel marker for a batch."""

    try:
        cancel_path(key).write_text("1")
    except (OSError, IOError, PermissionError):
        logger.debug("Failed to write cancel flag for %s", key)


def clear_cancelled(key: str) -> None:
    """Delete the filesystem cancel marker for a batch."""

    try:
        path = cancel_path(key)
        if path.exists():
            path.unlink()
    except (OSError, IOError, PermissionError):
        logger.debug("Failed to clear cancel flag for %s", key)


@dataclass(frozen=True, slots=True)
class AnalysisProgressSnapshot:
    """Normalized progress payload returned to views and templates."""

    phase: str
    status: str
    failure_summary: str = ""


class AnalysisProgressHandle:
    """Update a batch's progress while optionally mirroring into an AnalysisJob."""

    def __init__(self, batch_key: str, *, job: AnalysisJob | None = None) -> None:
        self.batch_key = batch_key
        self.job = job

    def _update_job(
        self,
        *,
        phase: str,
        status: str | None = None,
        failure_summary: str | None = None,
    ) -> None:
        if self.job is None:
            return
        update_fields: dict[str, object] = {"current_phase": phase}
        if status is not None:
            update_fields["status"] = status
        if failure_summary is not None:
            update_fields["failure_summary"] = failure_summary
        AnalysisJob.objects.filter(pk=self.job.pk).update(**update_fields)
        self.job.refresh_from_db(fields=list(update_fields.keys()))

    def set_phase(
        self,
        phase: str,
        *,
        status: str | None = None,
        failure_summary: str = "",
    ) -> None:
        self._update_job(
            phase=phase,
            status=status,
            failure_summary=failure_summary if failure_summary or status else None,
        )
        write_file_progress(
            self.batch_key,
            phase=phase,
            status=status or getattr(self.job, "status", None),
            failure_summary=failure_summary,
        )

    def request_cancel(self) -> None:
        set_cancelled(self.batch_key)
        if self.job is not None:
            self.job = request_job_cancellation(self.job)

    def clear_cancel(self) -> None:
        clear_cancelled(self.batch_key)

    def is_cancel_requested(self) -> bool:
        if is_cancelled(self.batch_key):
            return True
        if self.job is None:
            return False
        self.job.refresh_from_db(fields=["cancellation_requested"])
        return bool(self.job.cancellation_requested)


def get_progress_snapshot(*, batch_key: str, user_id: int) -> AnalysisProgressSnapshot:
    """Return the best available progress state for a user's batch."""

    job = get_latest_analysis_job(user_id=user_id, batch_key=batch_key)
    if job is not None:
        job = resolve_stale_job(job)
        status = _normalize_status(
            phase=job.current_phase or "Idle",
            status=job.status,
        )
        phase = job.current_phase or "Idle"
        failure_summary = job.failure_summary or ""
        _log_inconsistent_snapshot(
            batch_key=batch_key,
            phase=phase,
            status=status,
            failure_summary=failure_summary,
        )
        return AnalysisProgressSnapshot(
            phase=phase,
            status=status,
            failure_summary=failure_summary if status == "failed" else "",
        )

    file_progress = read_file_progress(batch_key)
    phase = str(file_progress.get("phase") or "Idle")
    raw_status = str(file_progress.get("status") or "")
    status = _normalize_status(phase=phase, status=raw_status)
    failure_summary = str(file_progress.get("failure_summary") or "")
    _log_inconsistent_snapshot(
        batch_key=batch_key,
        phase=phase,
        status=status,
        failure_summary=failure_summary,
    )
    return AnalysisProgressSnapshot(
        phase=phase,
        status=status,
        failure_summary=failure_summary if status == "failed" else "",
    )
