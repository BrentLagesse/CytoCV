"""Per-cell deletion service.

Removes a single ``CellStatistics`` row, decrements the parent
``SegmentedImage.NumCells`` counter, and wipes the cell's on-disk artifacts
(masks, per-channel cropped images, contour outline file, overlay cache).
"""

from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import F

from core.config import get_channel_config_for_uuid
from core.models import CellStatistics, SegmentedImage
from core.services.artifact_storage import _safe_remove_path
from core.services.overlay_rendering import (
    OVERLAY_CHANNEL_LABELS,
    OVERLAY_RENDER_CHANNELS,
    overlay_cache_image_path,
    overlay_cache_lock_path,
)

logger = logging.getLogger(__name__)


def _segmented_dir(run_uuid: str) -> Path:
    return Path(settings.MEDIA_ROOT) / str(run_uuid) / "segmented"


def _collect_artifact_paths(
    run_uuid: str,
    cell_id: int,
    image_name: str,
) -> list[Path]:
    """Build the list of on-disk artifact paths owned by a single cell."""

    segmented_dir = _segmented_dir(run_uuid)
    paths: list[Path] = [segmented_dir / f"cell_{cell_id}.png"]

    # The segmentation pipeline writes per-cell filenames as
    # ``{dv_name}-{channel_idx}-{cell_id}.png`` and ``{dv_name}-{cell_id}.outline``,
    # where ``dv_name`` is the uploaded file stem (i.e. ``Path(image_name).stem``).
    dv_name = Path(image_name).stem if image_name else ""
    if dv_name:
        paths.append(segmented_dir / f"{dv_name}-{cell_id}.outline")

    channel_config = get_channel_config_for_uuid(str(run_uuid)) or {}
    seen_indices: set[int] = set()
    for channel_index in channel_config.values():
        if channel_index is None:
            continue
        try:
            idx = int(channel_index)
        except (TypeError, ValueError):
            continue
        if idx in seen_indices:
            continue
        seen_indices.add(idx)
        if dv_name:
            paths.append(segmented_dir / f"{dv_name}-{idx}-{cell_id}.png")
            paths.append(segmented_dir / f"{dv_name}-{idx}-{cell_id}-no_outline.png")

    if segmented_dir.is_dir():
        # Catch any per-channel filenames not enumerated by channel_config
        # (e.g. legacy runs or extra channels) using glob patterns.
        paths.extend(segmented_dir.glob(f"*-*-{cell_id}.png"))
        paths.extend(segmented_dir.glob(f"*-*-{cell_id}-no_outline.png"))
        paths.extend(segmented_dir.glob(f"*-{cell_id}.outline"))

    for channel in OVERLAY_RENDER_CHANNELS:
        paths.append(overlay_cache_image_path(str(run_uuid), cell_id, channel))
    paths.append(overlay_cache_lock_path(str(run_uuid), cell_id))

    if segmented_dir.is_dir():
        for channel_label in OVERLAY_CHANNEL_LABELS.values():
            paths.extend(
                segmented_dir.glob(f"*-{cell_id}-{channel_label}_debug.png")
            )

    # Deduplicate while preserving order.
    seen_paths: set[Path] = set()
    deduped: list[Path] = []
    for path in paths:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        deduped.append(path)
    return deduped


def delete_single_cell(
    segmented_image: SegmentedImage,
    cell_id: int,
) -> bool:
    """Remove a cell's DB row and on-disk artifacts.

    Args:
        segmented_image: The parent ``SegmentedImage`` record.
        cell_id: The integer cell id (label) to remove.

    Returns:
        ``True`` if the DB row was deleted (regardless of whether disk
        artifacts existed).

    Raises:
        CellStatistics.DoesNotExist: If no row exists for the given cell id.
    """

    cell_id_int = int(cell_id)
    run_uuid = str(segmented_image.UUID)

    with transaction.atomic():
        cell_row = (
            CellStatistics.objects
            .select_for_update()
            .get(segmented_image=segmented_image, cell_id=cell_id_int)
        )
        image_name = cell_row.image_name or ""
        cell_row.delete()
        SegmentedImage.objects.filter(pk=segmented_image.pk).update(
            NumCells=F("NumCells") - 1
        )

    segmented_image.refresh_from_db(fields=["NumCells"])
    if (segmented_image.NumCells or 0) < 0:
        SegmentedImage.objects.filter(pk=segmented_image.pk).update(NumCells=0)
        segmented_image.refresh_from_db(fields=["NumCells"])

    for path in _collect_artifact_paths(run_uuid, cell_id_int, image_name):
        try:
            _safe_remove_path(path)
        except Exception:
            logger.exception(
                "Failed to remove cell artifact",
                extra={"run_uuid": run_uuid, "cell_id": cell_id_int, "path": str(path)},
            )

    return True


def delete_multiple_cells(
    segmented_image: SegmentedImage,
    cell_ids: list[int],
) -> list[int]:
    """Remove multiple cells' DB rows and on-disk artifacts.

    Missing cell IDs are ignored so callers can safely submit stale selections.
    The parent ``NumCells`` value is reset from the remaining statistics rows.
    """

    requested_ids = sorted({int(cell_id) for cell_id in cell_ids})
    if not requested_ids:
        return []

    run_uuid = str(segmented_image.UUID)
    image_names_by_cell: dict[int, str] = {}

    with transaction.atomic():
        rows = list(
            CellStatistics.objects
            .select_for_update()
            .filter(segmented_image=segmented_image, cell_id__in=requested_ids)
            .order_by("cell_id")
        )
        if not rows:
            return []

        for row in rows:
            image_names_by_cell[int(row.cell_id)] = row.image_name or ""

        deleted_ids = sorted(image_names_by_cell.keys())
        CellStatistics.objects.filter(
            segmented_image=segmented_image,
            cell_id__in=deleted_ids,
        ).delete()
        remaining_count = CellStatistics.objects.filter(
            segmented_image=segmented_image,
        ).count()
        SegmentedImage.objects.filter(pk=segmented_image.pk).update(
            NumCells=remaining_count,
        )

    segmented_image.refresh_from_db(fields=["NumCells"])

    for cell_id_int, image_name in image_names_by_cell.items():
        for path in _collect_artifact_paths(run_uuid, cell_id_int, image_name):
            try:
                _safe_remove_path(path)
            except Exception:
                logger.exception(
                    "Failed to remove cell artifact",
                    extra={
                        "run_uuid": run_uuid,
                        "cell_id": cell_id_int,
                        "path": str(path),
                    },
                )

    return sorted(image_names_by_cell.keys())
