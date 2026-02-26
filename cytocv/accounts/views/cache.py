"""Cache helpers for recently viewed image data."""

from __future__ import annotations

from typing import Any

from django.core.cache import cache

from core.models import CellStatistics, SegmentedImage, UploadedImage


def get_cache_image(user_id: Any) -> dict[str, Any] | None:
    """Return cached image metadata for the given user.

    Args:
        user_id: User id to scope the cached result.

    Returns:
        Cached payload containing the latest segmented image and stats,
        or None if no segmented image exists for the user.
    """
    key = 'cached_image'
    value = cache.get(key)

    if value is None or value['id'] != user_id:
        segmented_image = (
            SegmentedImage.objects.filter(user=user_id)
            .order_by("-uploaded_date")
            .first()
        )
        if not segmented_image:
            return None
        uploaded_image = UploadedImage.objects.get(uuid=segmented_image.UUID)
        cells = (
            CellStatistics.objects.filter(segmented_image_id=segmented_image.UUID)
            .order_by("cell_id")
        )
        cell_stat: dict[int, CellStatistics] = {}
        for cell in cells:
            cell_stat[cell.cell_id] = cell

        value = {
            "id": user_id,
            "segmented": segmented_image,
            "uploaded": uploaded_image,
            "cell": cell_stat,
        }
        cache.set(key, value, 60 * 10)

    return value

