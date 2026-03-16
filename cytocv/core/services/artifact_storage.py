"""Helpers for managing experiment media artifacts and retention."""

from __future__ import annotations

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

PNG_SAVE_OPTIONS = {
    "format": "PNG",
    "optimize": True,
    "compress_level": 9,
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


def save_png_image(image: Image.Image, destination: Path) -> Path:
    """Persist an in-memory image as an optimized lossless PNG."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if image.mode not in {"L", "RGB", "RGBA"}:
        image = image.convert("RGB")
    image.save(destination, **PNG_SAVE_OPTIONS)
    return destination


def save_png_array(image_array: np.ndarray, destination: Path) -> Path:
    """Persist a numpy image array as an optimized lossless PNG."""

    normalized = _normalize_png_array(image_array)
    return save_png_image(Image.fromarray(normalized), destination)


def optimize_png_file(path: Path) -> bool:
    """Re-save an existing PNG using a smaller lossless encoding."""

    if not path.exists() or path.suffix.lower() != ".png":
        return False
    with Image.open(path) as source:
        source.load()
        optimized = source.copy()
    save_png_image(optimized, path)
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
        save_png_image(preview_image, file_path)
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
