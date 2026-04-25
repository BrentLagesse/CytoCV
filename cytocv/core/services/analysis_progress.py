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
    get_stale_job_terminal_state,
    get_latest_analysis_job,
    request_job_cancellation,
)
from core.services.analysis_progress_contract import (
    PROGRESS_STATUS_FAILED,
    normalize_progress_status,
    progress_log_ref,
)

logger = logging.getLogger(__name__)

_DETAIL_STRING_KEYS = frozenset({"fileName", "message"})
_DETAIL_INT_KEYS = frozenset(
    {
        "fileIndex",
        "fileTotal",
        "batchIndex",
        "batchTotal",
        "cellIndex",
        "cellTotal",
    }
)


def _safe_detail_string(value: object, *, file_name: bool = False) -> str:
    text = str(value or "").strip()
    if file_name:
        text = text.replace("\\", "/").rsplit("/", 1)[-1]
    return text[:240]


def _safe_detail_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def normalize_progress_detail(detail: object | None) -> dict[str, object]:
    """Return a safe progress-detail payload for user-facing polling APIs."""

    if not isinstance(detail, dict):
        return {}

    normalized: dict[str, object] = {}
    for key in _DETAIL_STRING_KEYS:
        value = _safe_detail_string(detail.get(key), file_name=key == "fileName")
        if value:
            normalized[key] = value

    for key in _DETAIL_INT_KEYS:
        value = _safe_detail_int(detail.get(key))
        if value is not None:
            normalized[key] = value

    return normalized


def _log_inconsistent_snapshot(
    *,
    batch_key: str,
    phase: str,
    status: str,
) -> None:
    terminal_phase = str(phase).strip().lower() in {"completed", "failed", "cancelled", "canceled"}
    terminal_status = status in {"succeeded", "failed", "cancelled"}
    if terminal_phase and not terminal_status:
        logger.warning(
            "Progress snapshot has terminal phase with non-terminal status",
            extra={
                "progress_ref": progress_log_ref(batch_key),
                "phase": phase,
                "status": status,
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
    detail: dict[str, object] | None = None,
) -> None:
    """Write the mirrored filesystem progress payload."""

    payload = {
        "phase": phase,
        "status": status,
        "failure_summary": failure_summary,
        "detail": normalize_progress_detail(detail),
    }
    try:
        progress_path(key).write_text(json.dumps(payload))
    except (OSError, IOError, PermissionError):
        logger.debug("Failed to write progress payload for ref %s", progress_log_ref(key))


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
        logger.debug("Failed to write cancel flag for ref %s", progress_log_ref(key))


def clear_cancelled(key: str) -> None:
    """Delete the filesystem cancel marker for a batch."""

    try:
        path = cancel_path(key)
        if path.exists():
            path.unlink()
    except (OSError, IOError, PermissionError):
        logger.debug("Failed to clear cancel flag for ref %s", progress_log_ref(key))


@dataclass(frozen=True, slots=True)
class AnalysisProgressSnapshot:
    """Normalized progress payload returned to views and templates."""

    phase: str
    status: str
    failure_summary: str = ""
    detail: dict[str, object] | None = None


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
        detail: dict[str, object] | None = None,
    ) -> None:
        if self.job is None:
            return
        update_fields: dict[str, object] = {"current_phase": phase}
        if status is not None:
            update_fields["status"] = status
        if failure_summary is not None:
            update_fields["failure_summary"] = failure_summary
        if detail is not None:
            update_fields["progress_detail"] = normalize_progress_detail(detail)
        AnalysisJob.objects.filter(pk=self.job.pk).update(**update_fields)
        self.job.refresh_from_db(fields=list(update_fields.keys()))

    def set_phase(
        self,
        phase: str,
        *,
        status: str | None = None,
        failure_summary: str = "",
        detail: dict[str, object] | None = None,
    ) -> None:
        normalized_detail = normalize_progress_detail(detail)
        self._update_job(
            phase=phase,
            status=status,
            failure_summary=failure_summary if failure_summary or status else None,
            detail=normalized_detail,
        )
        write_file_progress(
            self.batch_key,
            phase=phase,
            status=status or getattr(self.job, "status", None),
            failure_summary=failure_summary,
            detail=normalized_detail,
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
        stale_state = get_stale_job_terminal_state(job)
        if stale_state is None:
            phase = job.current_phase or "Idle"
            status = normalize_progress_status(
                phase=phase,
                status=job.status,
            )
            failure_summary = job.failure_summary or ""
            detail = normalize_progress_detail(job.progress_detail)
        else:
            status, phase, failure_summary = stale_state
            detail = {}
        _log_inconsistent_snapshot(
            batch_key=batch_key,
            phase=phase,
            status=status,
        )
        return AnalysisProgressSnapshot(
            phase=phase,
            status=status,
            failure_summary=failure_summary if status == PROGRESS_STATUS_FAILED else "",
            detail=detail,
        )

    file_progress = read_file_progress(batch_key)
    phase = str(file_progress.get("phase") or "Idle")
    raw_status = str(file_progress.get("status") or "")
    status = normalize_progress_status(phase=phase, status=raw_status)
    failure_summary = str(file_progress.get("failure_summary") or "")
    detail = normalize_progress_detail(file_progress.get("detail"))
    _log_inconsistent_snapshot(
        batch_key=batch_key,
        phase=phase,
        status=status,
    )
    return AnalysisProgressSnapshot(
        phase=phase,
        status=status,
        failure_summary=failure_summary if status == PROGRESS_STATUS_FAILED else "",
        detail=detail,
    )
