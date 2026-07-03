"""Shared loaders for supported source microscopy image files."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile
from mrc import DVFile

SUPPORTED_IMAGE_EXTENSIONS = frozenset({".dv", ".tif", ".tiff"})
SUPPORTED_IMAGE_EXTENSIONS_LABEL = ".dv, .tif, .tiff"
TIFF_IMAGE_EXTENSIONS = frozenset({".tif", ".tiff"})
DV_IMAGE_EXTENSION = ".dv"

_SPATIAL_AXES = {"Y", "X"}
_NON_STACK_AXES = _SPATIAL_AXES | {"S"}
_SMALL_AXIS_MAX = 16


def source_image_extension(path_or_name: str | Path) -> str:
    """Return the lowercase suffix used to identify a supported source format."""

    return Path(str(path_or_name)).suffix.lower()


def is_supported_image_filename(name: object) -> bool:
    """Return True when the filename extension is accepted for upload."""

    return source_image_extension(str(name or "")) in SUPPORTED_IMAGE_EXTENSIONS


def _load_dv_array(path: str | Path) -> np.ndarray:
    """Read a DV file into a numpy array and always close the file handle."""

    dv_file = DVFile(path)
    try:
        return np.asarray(dv_file.asarray())
    finally:
        dv_file.close()


def _squeeze_singleton_non_spatial_axes(
    array: np.ndarray,
    axes: str | None,
) -> tuple[np.ndarray, str | None]:
    """Drop singleton non-XY axes before stack-axis inference."""

    # TIFF metadata often includes one-length time/channel/sample axes. Removing
    # only non-spatial singleton axes keeps Y/X interpretation explicit.
    if not axes or len(axes) != array.ndim:
        return array, axes

    squeeze_axes = [
        index
        for index, axis in enumerate(axes)
        if axis not in _SPATIAL_AXES and array.shape[index] == 1
    ]
    if not squeeze_axes:
        return array, axes

    squeezed = np.squeeze(array, axis=tuple(squeeze_axes))
    next_axes = "".join(axis for index, axis in enumerate(axes) if index not in squeeze_axes)
    return squeezed, next_axes


def _normalize_stack_with_axes(
    array: np.ndarray,
    axes: str | None,
    source_path: Path,
) -> np.ndarray | None:
    """Normalize arrays with trustworthy axes metadata to channel-first order."""

    if not axes or len(axes) != array.ndim:
        return None

    axes = axes.upper()
    if array.ndim == 2 and axes == "YX":
        return np.expand_dims(array, axis=0)

    if "Y" not in axes or "X" not in axes:
        return None

    stack_axes = [
        index for index, axis in enumerate(axes) if axis not in _NON_STACK_AXES
    ]
    if "S" in axes and not stack_axes:
        # RGB/sample images are display images, not supported channel stacks for
        # analysis upload, so fail before a misleading channel count is inferred.
        raise ValueError(f"Unsupported RGB/sample image shape {array.shape} for {source_path}")
    if len(stack_axes) != 1:
        return None

    y_axis = axes.index("Y")
    x_axis = axes.index("X")
    stack_axis = stack_axes[0]
    # Downstream preprocessing assumes stack[logical_channel, y, x] regardless of
    # how tifffile exposed the original axis order.
    normalized = np.moveaxis(array, [stack_axis, y_axis, x_axis], [0, 1, 2])
    if normalized.ndim != 3:
        raise ValueError(f"Unsupported image stack shape {array.shape} for {source_path}")
    return normalized


def _normalize_stack_without_axes(array: np.ndarray, source_path: Path) -> np.ndarray:
    """Infer channel-first order when the source lacks reliable axes metadata."""

    if array.ndim == 2:
        return np.expand_dims(array, axis=0)

    if array.ndim == 3:
        # Without reliable axes metadata, the smallest dimension is treated as the
        # channel/layer axis. The small-axis shortcuts preserve common channel-first
        # and channel-last stacks without relying on filename hints.
        if array.shape[0] <= _SMALL_AXIS_MAX:
            return array
        if array.shape[-1] <= _SMALL_AXIS_MAX:
            return np.moveaxis(array, -1, 0)
        stack_axis = int(np.argmin(array.shape))
        return np.moveaxis(array, stack_axis, 0)

    raise ValueError(f"Unsupported image stack shape {array.shape} for {source_path}")


def _normalize_image_stack(
    array: np.ndarray,
    source_path: Path,
    *,
    axes: str | None = None,
) -> np.ndarray:
    """Return a channel-first stack or raise a source-format error."""

    array = np.asarray(array)
    if array.ndim == 0:
        raise ValueError(f"Unsupported scalar image data for {source_path}")

    normalized_axes = axes.upper() if axes else None
    array, normalized_axes = _squeeze_singleton_non_spatial_axes(
        array,
        normalized_axes,
    )

    normalized = _normalize_stack_with_axes(array, normalized_axes, source_path)
    if normalized is not None:
        return np.asarray(normalized)
    return np.asarray(_normalize_stack_without_axes(array, source_path))


def _load_tiff_stack(path: Path) -> np.ndarray:
    """Load the first TIFF series and normalize it as an analysis stack."""

    with tifffile.TiffFile(path) as tiff:
        series = tiff.series[0]
        axes = getattr(series, "axes", None)
        array = series.asarray()
    return _normalize_image_stack(array, path, axes=axes)


def load_image_stack(path: str | Path) -> np.ndarray:
    """Load a supported source image and return a channel-first stack."""

    source_path = Path(path)
    extension = source_image_extension(source_path)
    if extension == DV_IMAGE_EXTENSION:
        return _normalize_image_stack(_load_dv_array(source_path), source_path)
    if extension in TIFF_IMAGE_EXTENSIONS:
        return _load_tiff_stack(source_path)
    raise ValueError(f"Unsupported image file extension '{extension}' for {source_path}")


def get_image_layer_count(path: str | Path) -> int:
    """Return the number of channel/layer images in the source file."""

    stack = load_image_stack(path)
    return int(stack.shape[0])


def is_recognized_image_file(path: str | Path) -> bool:
    """Return True when the file can be opened as a supported source image."""

    try:
        get_image_layer_count(path)
        return True
    except Exception:
        # Validation treats unreadable/unsupported sources uniformly so upload UI
        # can show a safe file-level error without surfacing parser internals.
        return False
