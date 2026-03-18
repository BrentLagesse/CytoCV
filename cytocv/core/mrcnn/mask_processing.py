from __future__ import annotations

from pathlib import Path

import numpy as np
import skimage.transform
from PIL import Image
from scipy import ndimage

DEFAULT_MASK_DUPLICATE_THRESHOLD = 0.7


def _copy_mask_volume(mask_volume: np.ndarray) -> np.ndarray:
    """Return a writable 3D mask volume copy in uint8 form."""

    copied_masks = np.array(mask_volume, copy=True)
    if copied_masks.ndim != 3:
        raise ValueError("Mask volumes must have shape [height, width, instances].")
    if copied_masks.dtype != np.uint8:
        copied_masks = copied_masks.astype(np.uint8, copy=False)
    return copied_masks


def _normalize_scores(mask_volume: np.ndarray, scores: np.ndarray | None) -> np.ndarray:
    """Return one score per mask, falling back to mask area when absent."""

    mask_count = int(mask_volume.shape[2])
    if scores is None:
        return np.sum(mask_volume, axis=(0, 1), dtype=np.float64)

    normalized_scores = np.asarray(scores, dtype=np.float64).reshape(-1)
    if normalized_scores.size != mask_count:
        raise ValueError(
            f"Expected {mask_count} mask scores, received {normalized_scores.size}."
        )
    return normalized_scores


def dilate_mask_volume(mask_volume: np.ndarray) -> np.ndarray:
    """Apply one binary dilation pass to each instance mask without mutating input."""

    dilated_masks = _copy_mask_volume(mask_volume)
    for index in range(dilated_masks.shape[2]):
        dilated_masks[:, :, index] = ndimage.binary_dilation(
            dilated_masks[:, :, index] > 0
        ).astype(np.uint8)
    return dilated_masks


def remove_duplicate_masks(
    mask_volume: np.ndarray,
    *,
    threshold: float = DEFAULT_MASK_DUPLICATE_THRESHOLD,
    scores: np.ndarray | None = None,
) -> np.ndarray:
    """Resolve overlapping masks by score and drop masks reduced beyond the threshold."""

    deduplicated_masks = _copy_mask_volume(mask_volume)
    if deduplicated_masks.shape[2] == 0:
        return deduplicated_masks

    normalized_scores = _normalize_scores(deduplicated_masks, scores)
    order = np.argsort(normalized_scores)[::-1] + 1
    flat_mask = np.max(
        deduplicated_masks * np.reshape(order, [1, 1, -1]),
        axis=-1,
    )

    for index in range(len(order)):
        deduplicated_masks[:, :, index] = deduplicated_masks[:, :, index] * (
            flat_mask == order[index]
        )

    new_scores = np.sum(deduplicated_masks, axis=(0, 1), dtype=np.float64)
    score_delta = normalized_scores - new_scores
    reduction = np.divide(
        score_delta,
        normalized_scores,
        out=np.zeros_like(score_delta, dtype=np.float64),
        where=normalized_scores != 0,
    )
    deduplicated_masks[:, :, reduction > threshold] = 0
    return deduplicated_masks


def postprocess_prediction_masks(
    mask_volume: np.ndarray,
    *,
    scores: np.ndarray | None = None,
    threshold: float = DEFAULT_MASK_DUPLICATE_THRESHOLD,
    dilation: bool = False,
) -> np.ndarray:
    """Return a processed mask volume ready for encoding or label-image writing."""

    processed_masks = _copy_mask_volume(mask_volume)
    if dilation:
        processed_masks = dilate_mask_volume(processed_masks)
    return remove_duplicate_masks(
        processed_masks,
        threshold=threshold,
        scores=scores,
    )


def label_mask_volume(mask_volume: np.ndarray) -> np.ndarray:
    """Convert a processed mask volume into a 2D instance label image."""

    processed_masks = _copy_mask_volume(mask_volume)
    label_image = np.zeros(processed_masks.shape[:2], dtype=np.uint16)
    current_label = 1

    for index in range(processed_masks.shape[2]):
        current_mask = processed_masks[:, :, index] > 0
        if not np.any(current_mask):
            continue
        label_image[current_mask] = current_label
        current_label += 1

    return label_image


def build_labeled_mask_image(
    mask_volume: np.ndarray,
    *,
    scores: np.ndarray | None = None,
    threshold: float = DEFAULT_MASK_DUPLICATE_THRESHOLD,
    dilation: bool = False,
    output_shape: tuple[int, int] | None = None,
) -> np.ndarray:
    """Return a uint16 labeled mask image derived from raw prediction masks."""

    processed_masks = postprocess_prediction_masks(
        mask_volume,
        scores=scores,
        threshold=threshold,
        dilation=dilation,
    )
    label_image = label_mask_volume(processed_masks)

    if output_shape is not None and tuple(label_image.shape) != tuple(output_shape):
        label_image = skimage.transform.resize(
            label_image,
            output_shape=output_shape,
            order=0,
            preserve_range=True,
            anti_aliasing=False,
        ).astype(np.uint16)

    return label_image


def save_mask_tiff(mask_image: np.ndarray, destination: Path) -> Path:
    """Persist a labeled mask image as a TIFF artifact."""

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized_mask = np.asarray(mask_image, dtype=np.uint16)
    Image.fromarray(normalized_mask).save(destination, format="TIFF")
    return destination

