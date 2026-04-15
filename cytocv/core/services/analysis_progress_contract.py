"""Shared contract helpers for analysis progress state and user-facing messages."""

from __future__ import annotations

import hashlib

PROGRESS_PHASE_IDLE = "Idle"
PROGRESS_PHASE_QUEUED = "Queued"
PROGRESS_PHASE_PREPROCESSING = "Preprocessing Images"
PROGRESS_PHASE_DETECTING = "Detecting Cells"
PROGRESS_PHASE_SEGMENTING = "Segmenting Images"
PROGRESS_PHASE_STATISTICS = "Calculating Statistics"
PROGRESS_PHASE_CANCELLING = "Cancelling"
PROGRESS_PHASE_CANCELLED = "Cancelled"
PROGRESS_PHASE_COMPLETED = "Completed"
PROGRESS_PHASE_FAILED = "Failed"

PROGRESS_PHASES = frozenset(
    {
        PROGRESS_PHASE_IDLE,
        PROGRESS_PHASE_QUEUED,
        PROGRESS_PHASE_PREPROCESSING,
        PROGRESS_PHASE_DETECTING,
        PROGRESS_PHASE_SEGMENTING,
        PROGRESS_PHASE_STATISTICS,
        PROGRESS_PHASE_CANCELLING,
        PROGRESS_PHASE_CANCELLED,
        PROGRESS_PHASE_COMPLETED,
        PROGRESS_PHASE_FAILED,
    }
)

PROGRESS_STATUS_IDLE = "idle"
PROGRESS_STATUS_QUEUED = "queued"
PROGRESS_STATUS_RUNNING = "running"
PROGRESS_STATUS_CANCELLING = "cancelling"
PROGRESS_STATUS_SUCCEEDED = "succeeded"
PROGRESS_STATUS_FAILED = "failed"
PROGRESS_STATUS_CANCELLED = "cancelled"

PROGRESS_STATUSES = frozenset(
    {
        PROGRESS_STATUS_IDLE,
        PROGRESS_STATUS_QUEUED,
        PROGRESS_STATUS_RUNNING,
        PROGRESS_STATUS_CANCELLING,
        PROGRESS_STATUS_SUCCEEDED,
        PROGRESS_STATUS_FAILED,
        PROGRESS_STATUS_CANCELLED,
    }
)

TERMINAL_PROGRESS_STATUSES = frozenset(
    {
        PROGRESS_STATUS_SUCCEEDED,
        PROGRESS_STATUS_FAILED,
        PROGRESS_STATUS_CANCELLED,
    }
)

SAFE_ANALYSIS_FAILURE_SUMMARY = (
    "Analysis failed due to an internal error. Please try again."
)
SAFE_PROGRESS_ERROR_MESSAGE = (
    "Analysis status is unavailable. Please refresh and try again."
)
SAFE_PROGRESS_WRITE_ERROR_MESSAGE = "Progress update rejected."
STALE_QUEUE_FAILURE_SUMMARY = (
    "Analysis worker did not pick up the queued job before it expired."
)
STALE_RUNNING_FAILURE_SUMMARY = (
    "Analysis job exceeded the maximum runtime and was marked failed."
)

_PHASE_ALIASES = {
    "idle": PROGRESS_PHASE_IDLE,
    "queued": PROGRESS_PHASE_QUEUED,
    "preprocessing images": PROGRESS_PHASE_PREPROCESSING,
    "detecting cells": PROGRESS_PHASE_DETECTING,
    "segmenting images": PROGRESS_PHASE_SEGMENTING,
    "calculating statistics": PROGRESS_PHASE_STATISTICS,
    "cancelling": PROGRESS_PHASE_CANCELLING,
    "canceling": PROGRESS_PHASE_CANCELLING,
    "cancelled": PROGRESS_PHASE_CANCELLED,
    "canceled": PROGRESS_PHASE_CANCELLED,
    "completed": PROGRESS_PHASE_COMPLETED,
    "complete": PROGRESS_PHASE_COMPLETED,
    "failed": PROGRESS_PHASE_FAILED,
}

_STATUS_ALIASES = {
    "idle": PROGRESS_STATUS_IDLE,
    "queued": PROGRESS_STATUS_QUEUED,
    "queue": PROGRESS_STATUS_QUEUED,
    "running": PROGRESS_STATUS_RUNNING,
    "preprocessing images": PROGRESS_STATUS_RUNNING,
    "detecting cells": PROGRESS_STATUS_RUNNING,
    "segmenting images": PROGRESS_STATUS_RUNNING,
    "calculating statistics": PROGRESS_STATUS_RUNNING,
    "cancelling": PROGRESS_STATUS_CANCELLING,
    "canceling": PROGRESS_STATUS_CANCELLING,
    "completed": PROGRESS_STATUS_SUCCEEDED,
    "complete": PROGRESS_STATUS_SUCCEEDED,
    "success": PROGRESS_STATUS_SUCCEEDED,
    "succeeded": PROGRESS_STATUS_SUCCEEDED,
    "failed": PROGRESS_STATUS_FAILED,
    "error": PROGRESS_STATUS_FAILED,
    "cancelled": PROGRESS_STATUS_CANCELLED,
    "canceled": PROGRESS_STATUS_CANCELLED,
}


def progress_log_ref(key: str) -> str:
    """Return a short log-safe identifier for a progress batch."""

    return hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:12]


def normalize_progress_phase(phase: object | None) -> str | None:
    """Return a canonical display phase, or None when unknown."""

    if phase is None:
        return None
    candidate = str(phase).strip()
    if not candidate:
        return None
    if candidate in PROGRESS_PHASES:
        return candidate
    return _PHASE_ALIASES.get(candidate.lower())


def validate_progress_status(status: object | None) -> str | None:
    """Return a canonical status when valid for client-originated input."""

    if status is None:
        return None
    candidate = str(status).strip().lower()
    if not candidate:
        return None
    if candidate in PROGRESS_STATUSES:
        return candidate
    return _STATUS_ALIASES.get(candidate)


def normalize_progress_status(*, phase: str, status: str | None) -> str:
    """Return the normalized contract status for stored phase/status values."""

    normalized_status = validate_progress_status(status)
    if normalized_status is not None:
        return normalized_status

    normalized_phase = normalize_progress_phase(phase)
    if normalized_phase is not None:
        fallback = _STATUS_ALIASES.get(normalized_phase.lower())
        if fallback is not None:
            return fallback

    return PROGRESS_STATUS_FAILED if str(status or "").strip() else PROGRESS_STATUS_IDLE
