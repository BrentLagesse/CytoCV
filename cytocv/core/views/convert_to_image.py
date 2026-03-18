from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import redirect

from cytocv.settings import MEDIA_ROOT
from .utils import clear_cancelled, is_cancelled, prune_experiment_session_state
from core.services.artifact_storage import delete_uploaded_run_by_uuid

PROCESSING_STORAGE_FULL_MESSAGE = (
    "Files could not be saved because storage is full. Free up space and try again."
)


def convert_to_image(request, uuids):
    """Compatibility shim for the retired RLE-to-TIFF conversion step."""

    uuid_list = [value for value in uuids.split(",") if value]

    if is_cancelled(uuids):
        clear_cancelled(uuids)
        for cleanup_uuid in uuid_list:
            delete_uploaded_run_by_uuid(cleanup_uuid)
        prune_experiment_session_state(request, uuid_list)
        return HttpResponse("Cancelled")

    return redirect("experiment_segment", uuids=uuids)
