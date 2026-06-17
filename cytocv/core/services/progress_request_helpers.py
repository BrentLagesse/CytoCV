from __future__ import annotations

import re

from django.http import JsonResponse

from core.models import SegmentedImage, UploadedImage, get_guest_user
from core.services.analysis_context import build_batch_key
from core.services.analysis_jobs import get_latest_analysis_job
from core.services.analysis_progress_contract import (
    PROGRESS_PHASE_FAILED,
    PROGRESS_STATUS_FAILED,
)

PROGRESS_BATCH_SESSION_KEY = "authorized_progress_batches"


class ProgressRequestError(Exception):
    """Controlled progress request error carrying an HTTP status code."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def current_owner_filter(request) -> dict:
    if request.user.is_authenticated:
        return {"user": request.user}
    return {"user_id": get_guest_user()}


def get_authorized_progress_batches(request) -> set[str]:
    return {
        str(value)
        for value in request.session.get(PROGRESS_BATCH_SESSION_KEY, [])
        if str(value)
    }


def track_progress_batch(request, batch_key: str) -> None:
    tracked = get_authorized_progress_batches(request)
    if batch_key in tracked:
        return
    tracked.add(batch_key)
    request.session[PROGRESS_BATCH_SESSION_KEY] = sorted(tracked)
    request.session.modified = True


def release_progress_batch(request, batch_key: str) -> None:
    tracked = get_authorized_progress_batches(request)
    if batch_key not in tracked:
        return
    tracked.remove(batch_key)
    request.session[PROGRESS_BATCH_SESSION_KEY] = sorted(tracked)
    request.session.modified = True


def resolve_owned_progress_batch(request, raw_uuids: str) -> tuple[str, list[str]]:
    if not raw_uuids or not re.fullmatch(r"[0-9a-fA-F,-]+", raw_uuids):
        raise ProgressRequestError("Invalid analysis batch.", status_code=400)
    try:
        batch_key = build_batch_key(raw_uuids)
    except (TypeError, ValueError):
        raise ProgressRequestError("Invalid analysis batch.", status_code=400)
    uuid_list = [value for value in batch_key.split(",") if value]
    if not uuid_list:
        raise ProgressRequestError("Invalid analysis batch.", status_code=400)

    owner_filter = current_owner_filter(request)
    owned_uploads = {
        str(value)
        for value in UploadedImage.objects.filter(
            uuid__in=uuid_list,
            **owner_filter,
        ).values_list("uuid", flat=True)
    }
    owned_segmented = {
        str(value)
        for value in SegmentedImage.objects.filter(
            UUID__in=uuid_list,
            user=request.user,
        ).values_list("UUID", flat=True)
    }
    owned_uuids = owned_uploads | owned_segmented
    if set(uuid_list).issubset(owned_uuids):
        return batch_key, uuid_list

    if batch_key in get_authorized_progress_batches(request):
        return batch_key, uuid_list

    if get_latest_analysis_job(user_id=request.user.id, batch_key=batch_key) is not None:
        return batch_key, uuid_list

    raise ProgressRequestError("Forbidden", status_code=403)


def progress_read_error_response(message: str, *, status_code: int) -> JsonResponse:
    return JsonResponse(
        {
            "phase": PROGRESS_PHASE_FAILED,
            "status": PROGRESS_STATUS_FAILED,
            "failure_summary": message,
            "redirect": None,
        },
        status=status_code,
    )


def progress_write_error_response(message: str, *, status_code: int) -> JsonResponse:
    return JsonResponse({"status": "error", "message": message}, status=status_code)
