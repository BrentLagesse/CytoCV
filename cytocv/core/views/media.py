"""Protected media serving for user-owned analysis artifacts."""

from __future__ import annotations

import mimetypes
import uuid as uuid_lib
from pathlib import Path

from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404

from core.models import UploadedImage, get_guest_user
from cytocv.settings import MEDIA_ROOT


def _current_owner_filter(request: HttpRequest) -> dict:
    """Return queryset filter args for the current upload owner."""

    if request.user.is_authenticated:
        return {"user": request.user}
    return {"user_id": get_guest_user()}


def serve_media(request: HttpRequest, relative_path: str) -> HttpResponse:
    """Serve media files only when the path belongs to the current user.

    Expected media layout starts with a UUID directory segment:
    ``<uuid>/...``
    """

    normalized = (relative_path or "").strip().lstrip("/\\")
    if not normalized:
        raise Http404("File not found")

    first_segment = normalized.replace("\\", "/").split("/", 1)[0]
    try:
        file_uuid = str(uuid_lib.UUID(first_segment))
    except (ValueError, TypeError, AttributeError):
        raise Http404("File not found")

    # Ensure the requesting user owns this UUID namespace.
    owner_filter = _current_owner_filter(request)
    get_object_or_404(UploadedImage, uuid=file_uuid, **owner_filter)

    media_root = Path(MEDIA_ROOT).resolve()
    file_path = (media_root / normalized).resolve()

    # Prevent traversal outside MEDIA_ROOT.
    if file_path != media_root and media_root not in file_path.parents:
        raise Http404("File not found")
    if not file_path.is_file():
        raise Http404("File not found")

    content_type, _ = mimetypes.guess_type(file_path.name)
    return FileResponse(file_path.open("rb"), content_type=content_type or "application/octet-stream")
