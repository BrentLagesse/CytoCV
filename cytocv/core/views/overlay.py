from __future__ import annotations

import logging
import time

from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404

from core.models import CellStatistics, SegmentedImage, UploadedImage
from core.services.overlay_rendering import (
    ensure_overlay_cache_image,
    find_legacy_debug_image_path,
    normalize_overlay_channel,
)

logger = logging.getLogger(__name__)


def cell_overlay_image(
    request: HttpRequest,
    uuid: str,
    cell_id: int,
    channel: str,
) -> HttpResponse:
    from .display import _can_access_display_uuid

    try:
        normalized_channel = normalize_overlay_channel(channel)
    except ValueError as exc:
        raise Http404("Unsupported overlay channel") from exc

    uploaded_image = get_object_or_404(UploadedImage, uuid=uuid)
    segmented_image = get_object_or_404(SegmentedImage, UUID=uuid)
    if not _can_access_display_uuid(request, uploaded_image, segmented_image):
        raise Http404("Overlay not found")

    cell_stat = get_object_or_404(
        CellStatistics.objects.select_related("segmented_image"),
        segmented_image=segmented_image,
        cell_id=cell_id,
    )
    started_at = time.perf_counter()

    try:
        overlay_path = ensure_overlay_cache_image(
            uuid,
            cell_id,
            normalized_channel,
            cell_stat=cell_stat,
        )
    except FileNotFoundError:
        legacy_debug = find_legacy_debug_image_path(uuid, cell_id, normalized_channel)
        if legacy_debug is None or not legacy_debug.exists():
            raise Http404("Overlay not found")
        logger.info(
            "Overlay cache event=legacy_fallback run_uuid=%s cell_id=%s channel=%s elapsed_ms=%.2f",
            uuid,
            int(cell_id),
            normalized_channel,
            (time.perf_counter() - started_at) * 1000.0,
        )
        overlay_path = legacy_debug
    except CellStatistics.DoesNotExist as exc:
        raise Http404("Overlay not found") from exc
    except ValueError as exc:
        raise Http404("Overlay not found") from exc

    return FileResponse(overlay_path.open("rb"), content_type="image/png")
