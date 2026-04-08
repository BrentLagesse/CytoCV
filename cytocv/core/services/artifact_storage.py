"""Helpers for managing experiment media artifacts and retention."""

from __future__ import annotations

import errno
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import numpy as np
import skimage.exposure
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from mrc import DVFile
from PIL import Image

from core.artifact_constants import PRE_PROCESS_FOLDER_NAME, PREVIEW_FOLDER_NAME
from core.models import CellStatistics, DVLayerTifPreview, SegmentedImage, UploadedImage

logger = logging.getLogger(__name__)

PNG_PROFILE_ARCHIVAL = "archival"
PNG_PROFILE_ANALYSIS_FAST = "analysis_fast"
PNG_SAVE_PROFILES = {
    PNG_PROFILE_ARCHIVAL: {
        "format": "PNG",
        "optimize": True,
        "compress_level": 9,
    },
    PNG_PROFILE_ANALYSIS_FAST: {
        "format": "PNG",
        "optimize": False,
        "compress_level": 1,
    },
}
TRANSIENT_FILE_NAMES = (
    "compressed_masks.csv",
    "preprocessed_images_list.csv",
)
TRANSIENT_ROOT_GLOBS = (
    "*.jpg",
    "*.jpeg",
)
TRANSIENT_DIR_NAMES = (
    PRE_PROCESS_FOLDER_NAME,
    "logs",
)
LEGACY_PREVIEW_PATTERNS = (
    "preprocess-image*.jpg",
    "preprocess-image*.jpeg",
    "preprocess-image*.png",
    "preprocess-image*.tif",
    "preprocess-image*.tiff",
)
STORAGE_FULL_ERRNOS = {
    errno.ENOSPC,
    getattr(errno, "EDQUOT", errno.ENOSPC),
}
STORAGE_FULL_MESSAGE_PATTERNS = (
    "no space left",
    "disk quota exceeded",
    "quota exceeded",
    "storage is full",
)


class StorageQuotaExceeded(Exception):
    """Raised when saving runs would exceed a user's retained storage quota."""

    def __init__(
        self,
        *,
        required_bytes: int,
        available_bytes: int,
        reclaimed_bytes: int = 0,
    ) -> None:
        self.required_bytes = max(int(required_bytes), 0)
        self.available_bytes = max(int(available_bytes), 0)
        self.reclaimed_bytes = max(int(reclaimed_bytes), 0)
        super().__init__(
            "Storage quota exceeded "
            f"(required={self.required_bytes}, available={self.available_bytes}, reclaimed={self.reclaimed_bytes})."
        )


class MediaStorageFullError(Exception):
    """Raised when the backing media filesystem cannot accept more writes."""


def is_storage_full_error(exc: BaseException | None) -> bool:
    """Return whether an exception chain represents a disk-full condition."""

    current = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, OSError):
            if current.errno in STORAGE_FULL_ERRNOS:
                return True
            strerror = str(current).lower()
            if any(pattern in strerror for pattern in STORAGE_FULL_MESSAGE_PATTERNS):
                return True
        else:
            message = str(current).lower()
            if any(pattern in message for pattern in STORAGE_FULL_MESSAGE_PATTERNS):
                return True
        current = current.__cause__ or current.__context__
    return False


def log_storage_capacity_failure(
    *,
    stage: str,
    user: object | None,
    uuids: Iterable[str] = (),
    required_bytes: int | None = None,
    available_bytes: int | None = None,
    exc: BaseException | None = None,
) -> None:
    """Log a quota or media-capacity failure with stable context."""

    normalized_uuids = [str(value) for value in uuids if str(value)]
    user_id = getattr(user, "id", None)
    payload = {
        "stage": stage,
        "user_id": str(user_id) if user_id is not None else None,
        "uuids": normalized_uuids,
        "required_bytes": None if required_bytes is None else int(required_bytes),
        "available_bytes": None if available_bytes is None else int(available_bytes),
    }
    if exc is None:
        logger.warning("Storage capacity failure: %s", payload)
        return
    logger.warning("Storage capacity failure: %s (%s)", payload, exc, exc_info=exc)


def media_root_path() -> Path:
    """Return the active media root as a resolved path."""

    return Path(settings.MEDIA_ROOT).resolve()


def run_media_path(run_uuid: str) -> Path:
    """Return the media namespace for a run UUID."""

    return media_root_path() / str(run_uuid)


def preview_media_path(run_uuid: str) -> Path:
    """Return the stored preview directory for a run UUID."""

    return run_media_path(run_uuid) / PREVIEW_FOLDER_NAME


def preprocess_media_path(run_uuid: str) -> Path:
    """Return the transient preprocess directory for a run UUID."""

    return run_media_path(run_uuid) / PRE_PROCESS_FOLDER_NAME


def output_media_path(run_uuid: str) -> Path:
    """Return the output directory for a run UUID."""

    return run_media_path(run_uuid) / "output"


def segmented_media_path(run_uuid: str) -> Path:
    """Return the segmented asset directory for a run UUID."""

    return run_media_path(run_uuid) / "segmented"


def user_media_path(run_uuid: str) -> Path:
    """Return the user-scoped file namespace for a run UUID."""

    return media_root_path() / f"user_{run_uuid}"


def _media_path_size(path: Path) -> int:
    """Return the total file size at a media path without raising on access errors."""

    if not path.exists():
        return 0
    if path.is_file():
        try:
            return int(path.stat().st_size)
        except OSError:
            return 0

    total = 0
    try:
        for candidate in path.rglob("*"):
            if not candidate.is_file():
                continue
            try:
                total += int(candidate.stat().st_size)
            except OSError:
                continue
    except OSError:
        return total
    return total


def get_run_storage_bytes(run_uuid: str) -> int:
    """Return the retained media size for a run across shared and user namespaces."""

    normalized_uuid = str(run_uuid)
    return _media_path_size(run_media_path(normalized_uuid)) + _media_path_size(
        user_media_path(normalized_uuid)
    )


def _saved_run_uuids_for_user(user: object) -> set[str]:
    """Return the saved run UUIDs retained by an authenticated user."""

    if not getattr(user, "is_authenticated", False):
        return set()
    return {
        str(value)
        for value in SegmentedImage.objects.filter(user=user).values_list("UUID", flat=True)
    }


def _calculate_user_storage_usage(
    user: object,
    *,
    saved_uuids: Iterable[str] | None = None,
) -> dict[str, int]:
    """Calculate retained storage totals for an authenticated user."""

    if not getattr(user, "is_authenticated", False):
        return {
            "used_storage": 0,
            "available_storage": 0,
            "total_storage": 0,
            "saved_run_count": 0,
        }

    normalized_saved_uuids = {
        str(value)
        for value in (saved_uuids if saved_uuids is not None else _saved_run_uuids_for_user(user))
        if str(value)
    }
    used_storage = sum(get_run_storage_bytes(run_uuid) for run_uuid in normalized_saved_uuids)
    total_storage = max(int(getattr(user, "total_storage", 0) or 0), 0)
    return {
        "used_storage": max(0, int(used_storage)),
        "available_storage": max(0, int(total_storage - used_storage)),
        "total_storage": int(total_storage),
        "saved_run_count": len(normalized_saved_uuids),
    }


def _persist_user_storage_usage(user: object, storage_usage: dict[str, int]) -> None:
    """Persist calculated storage usage back onto the authenticated user row."""

    if not getattr(user, "is_authenticated", False):
        return
    user.used_storage = max(int(storage_usage.get("used_storage", 0) or 0), 0)
    user.available_storage = max(int(storage_usage.get("available_storage", 0) or 0), 0)
    user.save(update_fields=["used_storage", "available_storage"])


def refresh_user_storage_usage(user: object) -> dict[str, int]:
    """Recalculate and persist retained storage usage for an authenticated user."""

    storage_usage = _calculate_user_storage_usage(user)
    _persist_user_storage_usage(user, storage_usage)
    return {
        "used_storage": int(storage_usage["used_storage"]),
        "available_storage": int(storage_usage["available_storage"]),
        "total_storage": int(storage_usage["total_storage"]),
    }


def get_user_storage_projection(user: object) -> dict[str, int | float | bool]:
    """Return storage totals plus queue-capacity estimates for saved runs."""

    if not getattr(user, "is_authenticated", False):
        return {
            "used_storage": 0,
            "available_storage": 0,
            "total_storage": 0,
            "average_saved_run_bytes": 0.0,
            "additional_files_possible": 0,
            "projection_ready": False,
        }

    saved_uuids = _saved_run_uuids_for_user(user)
    storage_usage = _calculate_user_storage_usage(user, saved_uuids=saved_uuids)
    _persist_user_storage_usage(user, storage_usage)

    saved_run_count = int(storage_usage.get("saved_run_count", 0))
    used_storage = int(storage_usage.get("used_storage", 0))
    available_storage = int(storage_usage.get("available_storage", 0))
    average_saved_run_bytes = (
        float(used_storage) / saved_run_count
        if saved_run_count > 0 and used_storage > 0
        else 0.0
    )
    projection_ready = average_saved_run_bytes > 0
    additional_files_possible = (
        max(0, int(available_storage / average_saved_run_bytes))
        if projection_ready
        else 0
    )

    return {
        "used_storage": used_storage,
        "available_storage": available_storage,
        "total_storage": int(storage_usage.get("total_storage", 0)),
        "average_saved_run_bytes": average_saved_run_bytes,
        "additional_files_possible": additional_files_possible,
        "projection_ready": projection_ready,
    }


def assert_user_can_save_runs(
    user: object,
    to_save: Iterable[str],
    to_unsave: Iterable[str] = (),
) -> None:
    """Raise when saving a run set would exceed the user's remaining quota."""

    if not getattr(user, "is_authenticated", False):
        return

    save_set = {str(value) for value in to_save if str(value)}
    unsave_set = {str(value) for value in to_unsave if str(value)}
    if not save_set:
        return
    unsave_set.difference_update(save_set)

    storage_usage = refresh_user_storage_usage(user)
    required_bytes = sum(get_run_storage_bytes(run_uuid) for run_uuid in save_set)
    reclaimed_bytes = sum(get_run_storage_bytes(run_uuid) for run_uuid in unsave_set)
    net_required_bytes = max(required_bytes - reclaimed_bytes, 0)
    available_bytes = int(storage_usage.get("available_storage", 0))

    if net_required_bytes > available_bytes:
        raise StorageQuotaExceeded(
            required_bytes=net_required_bytes,
            available_bytes=available_bytes,
            reclaimed_bytes=reclaimed_bytes,
        )


def _safe_remove_path(path: Path) -> bool:
    """Delete a file or directory only when it resides within MEDIA_ROOT."""

    try:
        candidate = path.resolve()
    except OSError:
        return False

    media_root = media_root_path()
    if candidate != media_root and media_root not in candidate.parents:
        return False

    try:
        if candidate.is_file():
            candidate.unlink(missing_ok=True)
            return True
        if candidate.is_dir():
            shutil.rmtree(candidate, ignore_errors=True)
            return True
    except OSError:
        return False
    return False


def _media_path_from_field(field_value: object) -> Path | None:
    """Resolve a media-relative field value into an absolute path."""

    name = str(field_value or "").strip()
    if not name:
        return None
    return media_root_path() / name


def resolve_uploaded_file_path(uploaded_image: UploadedImage) -> Path:
    """Return the on-disk path for an uploaded source DV file."""

    file_field = uploaded_image.file_location
    if not file_field:
        raise FileNotFoundError(
            f"Uploaded image {uploaded_image.pk} has no stored file location."
        )

    try:
        dv_path = Path(file_field.path)
    except (AttributeError, NotImplementedError, ValueError):
        dv_path = _media_path_from_field(file_field.name) or run_media_path(str(uploaded_image.uuid))

    if not dv_path.exists():
        raise FileNotFoundError(
            f"Stored DV file not found for upload {uploaded_image.pk}: {dv_path}"
        )

    return dv_path


def _normalize_png_array(image_array: np.ndarray) -> np.ndarray:
    """Normalize a numpy image array into a PNG-safe representation."""

    array = np.asarray(image_array)
    if array.dtype == np.bool_:
        array = array.astype(np.uint8) * 255
    elif np.issubdtype(array.dtype, np.floating):
        scale = 255.0 if float(np.nanmax(array)) <= 1.0 else 1.0
        array = np.clip(array * scale, 0, 255).astype(np.uint8)
    elif array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8)

    if array.ndim == 3 and array.shape[2] == 1:
        array = array[:, :, 0]
    return array


def _png_save_options_for_profile(profile: str) -> dict[str, object]:
    """Return the configured Pillow save kwargs for a named PNG profile."""

    if profile not in PNG_SAVE_PROFILES:
        available_profiles = ", ".join(sorted(PNG_SAVE_PROFILES))
        raise ValueError(f"Unknown PNG profile '{profile}'. Expected one of: {available_profiles}.")
    return dict(PNG_SAVE_PROFILES[profile])


def save_png_image(
    image: Image.Image,
    destination: Path,
    *,
    profile: str = PNG_PROFILE_ARCHIVAL,
) -> Path:
    """Persist an in-memory image as a PNG using a named save profile."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if image.mode not in {"L", "RGB", "RGBA"}:
        image = image.convert("RGB")
    image.save(destination, **_png_save_options_for_profile(profile))
    return destination


def save_png_array(
    image_array: np.ndarray,
    destination: Path,
    *,
    profile: str = PNG_PROFILE_ARCHIVAL,
) -> Path:
    """Persist a numpy image array as a PNG using a named save profile."""

    normalized = _normalize_png_array(image_array)
    return save_png_image(Image.fromarray(normalized), destination, profile=profile)


def optimize_png_file(path: Path) -> bool:
    """Re-save an existing PNG using the archival lossless profile."""

    if not path.exists() or path.suffix.lower() != ".png":
        return False
    with Image.open(path) as source:
        source.load()
        optimized = source.copy()
    save_png_image(optimized, path, profile=PNG_PROFILE_ARCHIVAL)
    return True


def _load_dv_layers(dv_path: Path) -> np.ndarray:
    """Load a DV file and return a channel-first layer stack."""

    dv_file = DVFile(dv_path)
    try:
        array = dv_file.asarray()
    finally:
        dv_file.close()

    if array.ndim == 2:
        return np.expand_dims(array, axis=0)
    if array.ndim == 3:
        z_axis = int(np.argmin(array.shape))
        return np.moveaxis(array, z_axis, 0)
    raise ValueError(f"Unexpected DV array rank {array.ndim} for {dv_path}")


def _build_preview_rgb_image(layer: np.ndarray) -> Image.Image:
    """Convert a raw DV layer into a browser-friendly preview image."""

    image = Image.fromarray(layer)
    normalized = skimage.exposure.rescale_intensity(
        np.float32(image),
        out_range=(0, 1),
    )
    normalized = np.round(normalized * 255).astype(np.uint8)
    normalized = np.expand_dims(normalized, axis=-1)
    rgb_image = np.tile(normalized, 3)
    return Image.fromarray(rgb_image)


def delete_preview_assets(uploaded_image: UploadedImage) -> bool:
    """Delete stored preview rows and files for an uploaded run."""

    changed = False
    preview_rows = list(
        DVLayerTifPreview.objects.filter(uploaded_image_uuid=uploaded_image)
    )
    preview_paths = [
        _media_path_from_field(item.file_location)
        for item in preview_rows
    ]
    if preview_rows:
        DVLayerTifPreview.objects.filter(uploaded_image_uuid=uploaded_image).delete()
        changed = True

    for preview_path in preview_paths:
        if preview_path is None:
            continue
        changed = _safe_remove_path(preview_path) or changed

    preview_dir = preview_media_path(str(uploaded_image.uuid))
    changed = _safe_remove_path(preview_dir) or changed

    legacy_preview_dir = preprocess_media_path(str(uploaded_image.uuid))
    for pattern in LEGACY_PREVIEW_PATTERNS:
        for candidate in legacy_preview_dir.glob(pattern):
            changed = _safe_remove_path(candidate) or changed

    return changed


def generate_preview_assets(
    uploaded_image: UploadedImage,
    *,
    expected_layers: int = 4,
) -> list[DVLayerTifPreview]:
    """Generate browser preview images for a DV upload."""

    dv_path = resolve_uploaded_file_path(uploaded_image)
    layers = _load_dv_layers(dv_path)
    layer_count = min(expected_layers, int(layers.shape[0]))

    delete_preview_assets(uploaded_image)

    preview_dir = preview_media_path(str(uploaded_image.uuid))
    preview_dir.mkdir(parents=True, exist_ok=True)

    preview_rows: list[DVLayerTifPreview] = []
    for layer_index in range(layer_count):
        preview_image = _build_preview_rgb_image(layers[layer_index])
        file_name = f"preview-layer{layer_index}.png"
        file_path = preview_dir / file_name
        save_png_image(preview_image, file_path, profile=PNG_PROFILE_ANALYSIS_FAST)
        preview_rows.append(
            DVLayerTifPreview(
                wavelength="",
                uploaded_image_uuid=uploaded_image,
                file_location=str(file_path.relative_to(media_root_path())),
            )
        )

    if preview_rows:
        DVLayerTifPreview.objects.bulk_create(preview_rows)

    return list(
        DVLayerTifPreview.objects.filter(uploaded_image_uuid=uploaded_image).order_by("id")
    )


def ensure_preview_assets(
    uploaded_image: UploadedImage,
    *,
    expected_layers: int = 4,
) -> list[DVLayerTifPreview]:
    """Return existing preview rows, regenerating them when files are missing."""

    preview_rows = list(
        DVLayerTifPreview.objects.filter(uploaded_image_uuid=uploaded_image).order_by("id")
    )
    if preview_rows:
        all_files_exist = True
        for preview in preview_rows:
            preview_path = _media_path_from_field(preview.file_location)
            if preview_path is None or not preview_path.exists():
                all_files_exist = False
                break
        if all_files_exist:
            return preview_rows
        try:
            return generate_preview_assets(uploaded_image, expected_layers=expected_layers)
        except FileNotFoundError:
            # Preserve legacy behavior when old rows exist but the original DV source
            # is unavailable to regenerate previews in-place.
            return preview_rows

    return generate_preview_assets(uploaded_image, expected_layers=expected_layers)


def cleanup_transient_processing_artifacts(
    run_uuid: str,
    *,
    remove_preview_assets: bool = False,
) -> bool:
    """Delete regenerable preprocess and inference artifacts for a run."""

    changed = False
    run_uuid = str(run_uuid)
    run_dir = run_media_path(run_uuid)

    for file_name in TRANSIENT_FILE_NAMES:
        changed = _safe_remove_path(run_dir / file_name) or changed

    for dir_name in TRANSIENT_DIR_NAMES:
        changed = _safe_remove_path(run_dir / dir_name) or changed

    for pattern in TRANSIENT_ROOT_GLOBS:
        for candidate in run_dir.glob(pattern):
            changed = _safe_remove_path(candidate) or changed

    if remove_preview_assets:
        uploaded = UploadedImage.objects.filter(uuid=run_uuid).first()
        if uploaded is not None:
            changed = delete_preview_assets(uploaded) or changed
        else:
            changed = _safe_remove_path(preview_media_path(run_uuid)) or changed

    return changed


def cleanup_processing_results(run_uuid: str) -> bool:
    """Delete persisted segmentation results for a run."""

    run_uuid = str(run_uuid)
    changed = False

    if SegmentedImage.objects.filter(UUID=run_uuid).exists():
        SegmentedImage.objects.filter(UUID=run_uuid).delete()
        changed = True
    elif CellStatistics.objects.filter(segmented_image_id=run_uuid).exists():
        CellStatistics.objects.filter(segmented_image_id=run_uuid).delete()
        changed = True

    changed = _safe_remove_path(output_media_path(run_uuid)) or changed
    changed = _safe_remove_path(segmented_media_path(run_uuid)) or changed
    changed = _safe_remove_path(user_media_path(run_uuid)) or changed
    return changed


def cleanup_failed_processing_artifacts(run_uuid: str) -> bool:
    """Delete partial processing outputs while preserving the source upload and previews."""

    normalized_uuid = str(run_uuid)
    changed = cleanup_processing_results(normalized_uuid)
    changed = cleanup_transient_processing_artifacts(
        normalized_uuid,
        remove_preview_assets=False,
    ) or changed
    return changed


def delete_uploaded_run(uploaded_image: UploadedImage) -> bool:
    """Delete an uploaded run plus all associated media and derived rows."""

    run_uuid = str(uploaded_image.uuid)
    changed = delete_preview_assets(uploaded_image)
    changed = cleanup_processing_results(run_uuid) or changed

    with transaction.atomic():
        UploadedImage.objects.filter(uuid=run_uuid).delete()

    changed = _safe_remove_path(run_media_path(run_uuid)) or changed
    changed = _safe_remove_path(user_media_path(run_uuid)) or changed
    return changed


def delete_uploaded_run_by_uuid(run_uuid: str) -> bool:
    """Delete a run and all artifacts by UUID when it exists."""

    run_uuid = str(run_uuid)
    uploaded = UploadedImage.objects.filter(uuid=run_uuid).first()
    if uploaded is not None:
        return delete_uploaded_run(uploaded)

    changed = cleanup_processing_results(run_uuid)
    changed = cleanup_transient_processing_artifacts(
        run_uuid,
        remove_preview_assets=True,
    ) or changed
    changed = _safe_remove_path(run_media_path(run_uuid)) or changed
    changed = _safe_remove_path(user_media_path(run_uuid)) or changed
    return changed


def _stale_retention_cutoff() -> datetime:
    """Return the retention cutoff for unsaved transient runs."""

    max_age_hours = int(getattr(settings, "TRANSIENT_RUN_RETENTION_HOURS", 24))
    return timezone.now() - timedelta(hours=max(max_age_hours, 1))


def sweep_user_run_artifacts(
    user: object,
    *,
    protected_uuids: Iterable[str] = (),
) -> dict[str, object]:
    """Clean stale unsaved runs and transient artifacts for a user."""

    if not getattr(user, "is_authenticated", False):
        return {
            "deleted_uuids": [],
            "cleaned_saved_runs": [],
            "cleaned_transient_runs": [],
        }

    protected_set = {str(value) for value in protected_uuids if str(value)}
    uploaded_items = list(
        UploadedImage.objects.filter(user=user).only("uuid", "created_at", "file_location")
    )
    if not uploaded_items:
        return {
            "deleted_uuids": [],
            "cleaned_saved_runs": [],
            "cleaned_transient_runs": [],
        }

    uploaded_by_uuid = {str(item.uuid): item for item in uploaded_items}
    segmented_by_uuid = {
        str(item.UUID): item
        for item in SegmentedImage.objects.filter(UUID__in=uploaded_by_uuid.keys()).only(
            "UUID",
            "user_id",
        )
    }

    cutoff = _stale_retention_cutoff()
    deleted_uuids: list[str] = []
    cleaned_saved_runs: list[str] = []
    cleaned_transient_runs: list[str] = []

    for run_uuid, uploaded in uploaded_by_uuid.items():
        segmented = segmented_by_uuid.get(run_uuid)
        if segmented is not None:
            changed = cleanup_transient_processing_artifacts(
                run_uuid,
                remove_preview_assets=True,
            )
            if segmented.user_id == getattr(user, "id", None):
                if changed:
                    cleaned_saved_runs.append(run_uuid)
                continue
            if changed:
                cleaned_transient_runs.append(run_uuid)

        if run_uuid in protected_set:
            continue
        if uploaded.created_at >= cutoff:
            continue
        delete_uploaded_run(uploaded)
        deleted_uuids.append(run_uuid)

    return {
        "deleted_uuids": deleted_uuids,
        "cleaned_saved_runs": cleaned_saved_runs,
        "cleaned_transient_runs": cleaned_transient_runs,
    }
