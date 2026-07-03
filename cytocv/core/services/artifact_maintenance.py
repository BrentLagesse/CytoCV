"""Shared artifact-maintenance helpers for background services."""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model

from core.models import AnalysisJob, UploadPreparationJob, UploadedImage
from core.services.analysis_jobs import ACTIVE_ANALYSIS_JOB_STATUSES
from core.services.artifact_storage import sweep_user_run_artifacts
from core.services.upload_preparation_jobs import ACTIVE_UPLOAD_PREPARATION_STATUSES

logger = logging.getLogger(__name__)


def _protected_run_uuids_by_user() -> dict[int, set[str]]:
    """Return active analysis run UUIDs that maintenance must not delete."""

    protected: dict[int, set[str]] = {}

    for row in AnalysisJob.objects.filter(
        status__in=ACTIVE_ANALYSIS_JOB_STATUSES
    ).values("user_id", "run_uuids"):
        user_id = int(row["user_id"])
        protected.setdefault(user_id, set()).update(
            str(value) for value in row.get("run_uuids", []) if str(value)
        )

    for row in UploadPreparationJob.objects.filter(
        status__in=ACTIVE_UPLOAD_PREPARATION_STATUSES
    ).values("user_id", "new_run_uuids", "restored_run_uuids"):
        user_id = int(row["user_id"])
        protected.setdefault(user_id, set()).update(
            str(value)
            for value in [
                *(row.get("new_run_uuids") or []),
                *(row.get("restored_run_uuids") or []),
            ]
            if str(value)
        )

    return protected


def run_artifact_maintenance() -> None:
    """Sweep stale regenerable artifacts while preserving active-job inputs."""

    protected_by_user = _protected_run_uuids_by_user()
    user_ids = set(
        int(value)
        for value in UploadedImage.objects.values_list("user_id", flat=True).distinct()
        if value is not None
    )
    user_ids.update(protected_by_user.keys())

    user_model = get_user_model()
    for user in user_model.objects.filter(id__in=user_ids).only("id"):
        summary = sweep_user_run_artifacts(
            user,
            protected_uuids=protected_by_user.get(int(user.id), set()),
        )
        if any(summary.get(key) for key in summary):
            logger.info(
                "Artifact maintenance swept artifacts for user %s: %s",
                user.id,
                summary,
            )
