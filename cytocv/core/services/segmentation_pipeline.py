"""Shared segmentation and statistics pipeline for sync and worker execution."""

from __future__ import annotations

import csv
import logging
import math
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2
import matplotlib.patheffects as PathEffects
import matplotlib.pyplot as plt
import numpy as np
import skimage
from PIL import Image, ImageDraw, ImageFont
from cv2_rolling_ball import subtract_background_rolling_ball
from django.conf import settings
from django.db import transaction
from mrc import DVFile

from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
)
from core.config import DEFAULT_CHANNEL_CONFIG, DEFAULT_PROCESS_CONFIG, input_dir
from core.contour_processing import get_contour_center, get_neighbor_count
from core.image_processing.dashed_line import draw_dashed_line
from core.models import CellStatistics, SegmentedImage, UploadedImage, get_guest_user
from core.scale import (
    convert_length_to_pixels,
    normalize_length_unit,
    normalize_scale_info,
    resolve_scale_context,
)
from core.services.analysis_exceptions import AnalysisCancelled
from core.services.analysis_progress import AnalysisProgressHandle
from core.services.artifact_storage import (
    PNG_PROFILE_ANALYSIS_FAST,
    StorageQuotaExceeded,
    assert_user_can_save_runs,
    cleanup_transient_processing_artifacts,
    delete_uploaded_run_by_uuid,
    is_storage_full_error,
    log_storage_capacity_failure,
    refresh_user_storage_usage,
    save_png_array,
)
from core.services.neck_split import (
    NeckSplit,
    compute_side_areas,
    detect_neck_split,
    manifest_path as neck_split_manifest_path,
    write_neck_split_manifest,
)
from core.services.pair_refinement import refine_pair_label_image
from core.services.overlay_rendering import (
    build_overlay_render_config,
    persist_debug_overlay_exports,
    persist_overlay_cache_images,
    write_overlay_render_config,
)
from core.services.puncta_line_mode import (
    DEFAULT_PUNCTA_LINE_MODE,
    normalize_puncta_line_mode,
)
from core.stats_plugins import build_stats_execution_plan
from core.views.segment_image import (
    AUTOSAVE_STORAGE_FULL_MESSAGE,
    _build_layer_channel_lookup,
    _resolve_uploaded_dv_path,
    get_stats,
)

logger = logging.getLogger(__name__)
CYAN_DEBUG_COLOR = (0, 255, 255)
PAIR_CROP_MARGIN_PX = 4
_PARENTAGE_FONT_CANDIDATES = (
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "DejaVuSans.ttf",
    "Segoe UI.ttf",
    "segoeui.ttf",
    "Arial.ttf",
    "arial.ttf",
    "SegoeUI.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "DejaVuSans-Bold.ttf",
)


def _process_config_value(
    config: dict[str, object],
    key: str,
    legacy_key: str,
    default,
):
    return config.get(key, config.get(legacy_key, default))


@dataclass(frozen=True, slots=True)
class SegmentationBatchResult:
    """Outcome of a completed segmentation batch."""

    storage_warning_message: str = ""


@dataclass(frozen=True, slots=True)
class PairGeometryCacheEntry:
    """Cached pair geometry reused across frame render, crop, and stats phases."""

    cell_id: int
    full_contours: tuple[np.ndarray, ...]
    local_contours: tuple[np.ndarray, ...]
    min_x: int
    max_x: int
    min_y: int
    max_y: int
    local_split: NeckSplit | None = None
    full_split: NeckSplit | None = None
    side_area_large_px: int = 0
    side_area_small_px: int = 0
    mother_label_position: tuple[int, int] | None = None
    daughter_label_position: tuple[int, int] | None = None


def _current_owner_filter_for_user(user) -> dict[str, object]:
    if getattr(user, "is_authenticated", False):
        return {"user": user}
    return {"user_id": get_guest_user()}


def _raise_if_cancelled(progress: AnalysisProgressHandle) -> None:
    if progress.is_cancel_requested():
        raise AnalysisCancelled()


def _offset_neck_split(
    split: NeckSplit | None,
    *,
    row_offset: int,
    col_offset: int,
) -> NeckSplit | None:
    """Return a shifted copy of a split, or ``None`` when absent."""

    if split is None:
        return None
    return NeckSplit(
        x1=int(split.x1) + int(col_offset),
        y1=int(split.y1) + int(row_offset),
        x2=int(split.x2) + int(col_offset),
        y2=int(split.y2) + int(row_offset),
        status=split.status,
        defect_depth_1=int(split.defect_depth_1),
        defect_depth_2=int(split.defect_depth_2),
    )


def _crop_bounds_for_label_mask(
    label_mask: np.ndarray,
    *,
    margin_px: int = PAIR_CROP_MARGIN_PX,
) -> tuple[int, int, int, int] | None:
    """Return symmetric crop bounds for a single pair mask."""

    points = np.where(label_mask > 0)
    if points[0].size == 0:
        return None
    min_x = max(int(np.min(points[0])) - int(margin_px), 0)
    max_x = min(int(np.max(points[0])) + int(margin_px) + 1, label_mask.shape[0])
    min_y = max(int(np.min(points[1])) - int(margin_px), 0)
    max_y = min(int(np.max(points[1])) + int(margin_px) + 1, label_mask.shape[1])
    return min_x, max_x, min_y, max_y


def _mask_centroid(mask: np.ndarray) -> tuple[int, int] | None:
    """Return the integer x,y centroid of a binary mask."""

    binary = (mask > 0).astype(np.uint8)
    if not np.any(binary):
        return None
    moments = cv2.moments(binary, binaryImage=True)
    if moments["m00"] != 0:
        x = int(round(moments["m10"] / moments["m00"]))
        y = int(round(moments["m01"] / moments["m00"]))
        return x, y
    points = np.column_stack(np.nonzero(binary))
    if points.size == 0:
        return None
    return int(round(float(np.mean(points[:, 1])))), int(round(float(np.mean(points[:, 0]))))


def _draw_centered_label(
    image: np.ndarray,
    label: str,
    center: tuple[int, int] | None,
    *,
    text_color: tuple[int, int, int] = (255, 255, 255),
    stroke_color: tuple[int, int, int] = (0, 0, 0),
    font_size: int = 10,
    stroke_width: int = 1,
) -> None:
    """Draw centered debug text with a smooth stroked font for DIC readability."""

    if image is None or center is None:
        return
    height, width = image.shape[:2]
    if height <= 0 or width <= 0:
        return
    pil_image = Image.fromarray(image)
    draw = ImageDraw.Draw(pil_image)
    resolved_font_size = max(int(font_size), 8)
    font = None
    for candidate in _PARENTAGE_FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(candidate, resolved_font_size)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    x0, y0, x1, y1 = draw.textbbox((0, 0), label, font=font, stroke_width=int(stroke_width))
    text_width = x1 - x0
    text_height = y1 - y0
    x = int(round(center[0] - (text_width / 2.0) - x0))
    y = int(round(center[1] - (text_height / 2.0) - y0))
    x = max(0, min(x, max(width - text_width, 0)))
    y = max(0, min(y, max(height - text_height, 0)))
    draw.text(
        (x, y),
        label,
        font=font,
        fill=text_color,
        stroke_width=int(stroke_width),
        stroke_fill=stroke_color,
    )
    np.copyto(image, np.asarray(pil_image))


def _draw_pair_parentage_labels(
    image: np.ndarray,
    entry: PairGeometryCacheEntry,
) -> None:
    """Draw inferred mother/daughter labels on one DIC crop only."""

    if entry.local_split is None:
        return
    label_font_size = max(7, min(image.shape[:2]) // 8)
    _draw_centered_label(
        image,
        "M",
        entry.mother_label_position,
        font_size=label_font_size,
        text_color=(255, 255, 255),
        stroke_color=(0, 0, 0),
    )
    _draw_centered_label(
        image,
        "D",
        entry.daughter_label_position,
        font_size=label_font_size,
        text_color=(255, 255, 255),
        stroke_color=(0, 0, 0),
    )


def _build_pair_geometry_cache(seg: np.ndarray) -> dict[int, PairGeometryCacheEntry]:
    """Build one shared geometry cache per pair label from the finalized mask."""

    cache: dict[int, PairGeometryCacheEntry] = {}
    for cell_id in range(1, int(np.max(seg) + 1)):
        cell_mask_full = ((seg == cell_id).astype(np.uint8)) * 255
        if not np.any(cell_mask_full):
            continue
        bounds = _crop_bounds_for_label_mask(cell_mask_full)
        if bounds is None:
            continue
        min_x, max_x, min_y, max_y = bounds
        full_contours, _ = cv2.findContours(
            cell_mask_full,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_NONE,
        )
        local_mask = cell_mask_full[min_x:max_x, min_y:max_y]
        local_contours, _ = cv2.findContours(
            local_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_NONE,
        )
        local_split = None
        full_split = None
        side_area_large_px = 0
        side_area_small_px = 0
        mother_label_position = None
        daughter_label_position = None
        if local_contours:
            primary_contour = max(local_contours, key=len)
            try:
                local_split = detect_neck_split(primary_contour, local_mask)
            except Exception:
                logger.debug(
                    "Neck-split detection failed for cell %s",
                    cell_id,
                    exc_info=True,
                )
                local_split = None
            if local_split is not None:
                full_split = _offset_neck_split(
                    local_split,
                    row_offset=min_x,
                    col_offset=min_y,
                )
                try:
                    (
                        side_area_large_px,
                        side_area_small_px,
                        mother_mask,
                        daughter_mask,
                    ) = compute_side_areas(
                        local_mask,
                        local_split,
                    )
                    mother_label_position = _mask_centroid(mother_mask)
                    daughter_label_position = _mask_centroid(daughter_mask)
                except Exception:
                    logger.debug(
                        "Neck-split side-area computation failed for cell %s",
                        cell_id,
                        exc_info=True,
                    )
                    side_area_large_px = 0
                    side_area_small_px = 0
        cache[cell_id] = PairGeometryCacheEntry(
            cell_id=cell_id,
            full_contours=tuple(full_contours),
            local_contours=tuple(local_contours),
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
            local_split=local_split,
            full_split=full_split,
            side_area_large_px=int(side_area_large_px),
            side_area_small_px=int(side_area_small_px),
            mother_label_position=mother_label_position,
            daughter_label_position=daughter_label_position,
        )
    return cache


def _draw_pair_geometry_overlay(
    image: np.ndarray,
    pair_geometry_cache: dict[int, PairGeometryCacheEntry],
) -> None:
    """Draw the solid pair contour and dashed neck seam onto one frame."""

    for entry in pair_geometry_cache.values():
        if entry.full_contours:
            cv2.drawContours(image, list(entry.full_contours), -1, CYAN_DEBUG_COLOR, 1)
        if entry.full_split is not None:
            draw_dashed_line(
                image,
                (entry.full_split.x1, entry.full_split.y1),
                (entry.full_split.x2, entry.full_split.y2),
                CYAN_DEBUG_COLOR,
                dash_px=2,
                gap_px=2,
                thickness=1,
            )


def _build_neck_split_properties(entry: PairGeometryCacheEntry | None) -> dict:
    """Return the persisted-style neutral neck-split payload for one pair."""

    if entry is None or entry.local_split is None:
        return {"status": "no_neck"}
    return {
        **entry.local_split.to_dict(),
        "side_area_large_px": int(entry.side_area_large_px),
        "side_area_small_px": int(entry.side_area_small_px),
    }


def _build_neck_split_manifest_pairs(
    pair_geometry_cache: dict[int, PairGeometryCacheEntry],
) -> dict[int, dict]:
    """Build the persisted neck-split payload map for one run."""

    return {
        int(cell_id): _build_neck_split_properties(entry)
        for cell_id, entry in sorted(pair_geometry_cache.items())
    }


def _write_neck_split_manifest_for_run(
    output_dir: str | os.PathLike,
    *,
    image_name: str,
    pair_geometry_cache: dict[int, PairGeometryCacheEntry],
    use_cache: bool,
) -> Path:
    """Persist one run-level pair geometry manifest for all neck splits."""

    path = neck_split_manifest_path(output_dir)
    if not path.exists() or not use_cache:
        write_neck_split_manifest(
            path,
            image_name=image_name,
            pairs=_build_neck_split_manifest_pairs(pair_geometry_cache),
        )
    return path


def _finalize_segmented_run_batch_for_user(
    user,
    uuid_list: list[str],
    *,
    auto_save_experiments: bool,
) -> SegmentationBatchResult:
    """Persist completed outputs when quota allows, otherwise leave them transient."""

    if not getattr(user, "is_authenticated", False):
        return SegmentationBatchResult()

    current_uuids = {str(item) for item in uuid_list if str(item)}
    guest_id = get_guest_user()

    if not auto_save_experiments:
        SegmentedImage.objects.filter(UUID__in=current_uuids).update(user_id=guest_id)
        return SegmentationBatchResult()

    try:
        assert_user_can_save_runs(user, current_uuids)
    except StorageQuotaExceeded as exc:
        log_storage_capacity_failure(
            stage="segment_autosave",
            user=user,
            uuids=current_uuids,
            required_bytes=exc.required_bytes,
            available_bytes=exc.available_bytes,
            exc=exc,
        )
        SegmentedImage.objects.filter(UUID__in=current_uuids).update(user_id=guest_id)
        refresh_user_storage_usage(user)
        return SegmentationBatchResult(storage_warning_message=AUTOSAVE_STORAGE_FULL_MESSAGE)

    with transaction.atomic():
        SegmentedImage.objects.filter(UUID__in=current_uuids, user_id=guest_id).update(user=user)
    refresh_user_storage_usage(user)
    return SegmentationBatchResult()


def _save_segmentation_frame(fig, output_file: str) -> None:
    fig.savefig(output_file, dpi=600, bbox_inches="tight", pad_inches=0)


def run_segmentation_batch(
    *,
    user,
    batch_key: str,
    config_snapshot: dict[str, object],
    progress: AnalysisProgressHandle,
) -> SegmentationBatchResult:
    """Run segmentation, artifact generation, and statistics for a batch of runs."""

    uuid_list = [value for value in batch_key.split(",") if value]
    owner_filter = _current_owner_filter_for_user(user)
    auto_save_experiments = bool(config_snapshot.get("auto_save_experiments", True))
    use_cache = True
    choice_var = "Metaphase Arrested"
    start_time = time.time()

    progress.set_phase("Segmenting Cell-Pairs", status="running")

    for uuid in uuid_list:
        _raise_if_cancelled(progress)
        uploaded_image = UploadedImage.objects.get(pk=uuid, **owner_filter)
        dv_name = uploaded_image.name
        dv_path = _resolve_uploaded_dv_path(uploaded_image)
        channel_config = DEFAULT_CHANNEL_CONFIG
        try:
            from core.config import get_channel_config_for_uuid

            channel_config = get_channel_config_for_uuid(uuid)
        except Exception:
            logger.debug("Fell back to default channel config for %s", uuid)
        layer_channel_lookup = _build_layer_channel_lookup(channel_config)

        dv_file = DVFile(dv_path)
        try:
            image_stack = dv_file.asarray()
        finally:
            dv_file.close()
        if image_stack.ndim == 2:
            image_stack = np.expand_dims(image_stack, axis=0)

        image = Image.fromarray(image_stack[0])
        image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1))
        image = np.round(image * 255).astype(np.uint8)
        if len(image.shape) != 3 or image.shape[2] != 3:
            image = np.expand_dims(image, axis=-1)
            image = np.tile(image, 3)

        seg = np.array(Image.open(Path(settings.MEDIA_ROOT) / str(uuid) / "output" / "mask.tif"))

        lines_to_draw: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {}
        outputdirectory = str(Path(settings.MEDIA_ROOT) / str(uuid) / "output") + "/"

        if choice_var == "Metaphase Arrested":
            ignore_list: list[int] = []
            single_cell_list: list[int] = []
            closest_neighbors: dict[int, int] = {}
            neighbor_count: dict[int, int] = {}

            for i in range(1, int(np.max(seg) + 1)):
                cells = np.where(seg == i)
                for cell in zip(cells[0], cells[1]):
                    try:
                        neighbor_list = get_neighbor_count(seg, cell, 3)
                    except Exception:
                        continue
                    for neighbor in neighbor_list:
                        if int(neighbor) == i or int(neighbor) == 0:
                            continue
                        neighbor_count[neighbor] = neighbor_count.get(neighbor, 0) + 1

                sorted_dict = {
                    k: v for k, v in sorted(neighbor_count.items(), key=lambda item: item[1])
                }
                if len(sorted_dict) == 0:
                    single_cell_list.append(int(i))
                elif len(sorted_dict) == 1:
                    closest_neighbors[i] = list(sorted_dict.items())[0][0]
                else:
                    top_val = list(sorted_dict.items())[0][1]
                    second_val = list(sorted_dict.items())[1][1]
                    if second_val > 0.5 * top_val:
                        single_cell_list.append(int(i))
                        for cluster_cell in neighbor_count:
                            single_cell_list.append(int(cluster_cell))
                    else:
                        closest_neighbors[i] = list(sorted_dict.items())[0][0]
                neighbor_count = {}

            resolve_cells_using_spc110 = False
            if resolve_cells_using_spc110:
                dv_file = DVFile(dv_path)
                try:
                    red_index = channel_config.get(CHANNEL_ROLE_RED)
                    red_image = dv_file.asarray()[red_index]
                finally:
                    dv_file.close()

                red_image = np.round(red_image * 255).astype(np.uint8)
                if len(red_image.shape) != 3 or red_image.shape[2] != 3:
                    red_image = np.expand_dims(red_image, axis=-1)
                    red_image = np.tile(red_image, 3)
                red_image_gray = cv2.cvtColor(red_image, cv2.COLOR_RGB2GRAY)
                red_image_gray, _ = subtract_background_rolling_ball(
                    red_image_gray,
                    50,
                    light_background=False,
                    use_paraboloid=False,
                    do_presmooth=True,
                )
                _, red_image_thresh = cv2.threshold(
                    red_image_gray,
                    0,
                    1,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU,
                )
                red_image_cont, _ = cv2.findContours(red_image_thresh, 1, 2)

                min_red_distance: dict[int, float] = {}
                min_red_loc: dict[int, int] = {}
                for cnt1 in red_image_cont:
                    try:
                        contour_area = cv2.contourArea(cnt1)
                        if contour_area > 100000:
                            logger.debug(
                                "Discarded oversized bounding contour while pairing cells"
                            )
                            continue
                        coordinate = get_contour_center([cnt1])
                        c1y = coordinate[0][0]
                        c1x = coordinate[0][1]
                    except Exception:
                        continue

                    c_id = int(seg[c1x][c1y])
                    if c_id == 0:
                        continue

                    for cnt2 in red_image_cont:
                        try:
                            coordinate = get_contour_center([cnt2])
                            c2y = coordinate[0][0]
                            c2x = coordinate[0][1]
                        except Exception:
                            continue
                        if int(seg[c2x][c2y]) == 0:
                            continue
                        if seg[c1x][c1y] == seg[c2x][c2y]:
                            continue
                        distance = math.sqrt(pow(c1x - c2x, 2) + pow(c1y - c2y, 2))
                        if min_red_distance.get(c_id) is None:
                            min_red_distance[c_id] = distance
                            min_red_loc[c_id] = int(seg[c2x][c2y])
                            lines_to_draw[c_id] = ((c1y, c1x), (c2y, c2x))
                        elif distance < min_red_distance[c_id]:
                            min_red_distance[c_id] = distance
                            min_red_loc[c_id] = int(seg[c2x][c2y])
                            lines_to_draw[c_id] = ((c1y, c1x), (c2y, c2x))
                        elif distance == min_red_distance[c_id]:
                            logger.debug(
                                "Found tied Red pair distance while pairing cells: cell_a=%s cell_b=%s nearest=%s distance=%s",
                                seg[c1x][c1y],
                                seg[c2x][c2y],
                                min_red_loc[c_id],
                                distance,
                            )

            for k, v in closest_neighbors.items():
                if v in closest_neighbors:
                    if int(v) in ignore_list:
                        single_cell_list.append(int(k))
                        continue

                    if closest_neighbors[int(v)] == int(k) and int(k) not in ignore_list:
                        to_update = np.where(seg == v)
                        ignore_list.append(int(v))
                        for update in zip(to_update[0], to_update[1]):
                            seg[update[0]][update[1]] = k
                    elif int(k) not in ignore_list:
                        single_cell_list.append(int(k))
                elif int(k) not in ignore_list:
                    single_cell_list.append(int(k))

            for cell in single_cell_list:
                seg[np.where(seg == cell)] = 0.0

            to_rebase: list[int] = []
            for k, _ in closest_neighbors.items():
                if k in ignore_list or k in single_cell_list:
                    continue
                to_rebase.append(int(k))
            to_rebase.sort()

            for i, x in enumerate(to_rebase):
                seg[np.where(seg == x)] = i + 1

            seg = refine_pair_label_image(seg)

            seg_image = Image.fromarray(seg)
            seg_image.save(str(outputdirectory) + "\\cellpairs.tif")

        pair_geometry_cache = _build_pair_geometry_cache(seg)
        _write_neck_split_manifest_for_run(
            os.path.join(str(settings.MEDIA_ROOT), str(uuid)),
            image_name=f"{dv_name}.dv",
            pair_geometry_cache=pair_geometry_cache,
            use_cache=use_cache,
        )

        for frame_idx in range(image_stack.shape[0]):
            _raise_if_cancelled(progress)
            image = Image.fromarray(image_stack[frame_idx])
            image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1))
            image = np.round(image * 255).astype(np.uint8)
            if len(image.shape) != 3 or image.shape[2] != 3:
                image = np.expand_dims(image, axis=-1)
                image = np.tile(image, 3)

            image_outlined = image.copy()
            _draw_pair_geometry_overlay(image_outlined, pair_geometry_cache)

            fig = plt.figure(frameon=False)
            ax = plt.Axes(fig, [0.0, 0.0, 1.0, 1.0])
            ax.set_axis_off()
            fig.add_axes(ax)
            ax.imshow(image_outlined)

            for _, line in lines_to_draw.items():
                start, stop = line
                cv2.line(image_outlined, start, stop, (255, 0, 0), 1)

            for i in range(1, int(np.max(seg) + 1)):
                loc = np.where(seg == i)
                if len(loc[0]) > 0:
                    txt = ax.text(loc[1][0], loc[0][0], str(i), size=12)
                    txt.set_path_effects([PathEffects.withStroke(linewidth=1, foreground="w")])
                else:
                    logger.debug("Could not find cell id %s while rendering frame labels", i)

            output_file = os.path.join(outputdirectory, f"{dv_name}_frame_{frame_idx}.png")
            try:
                _save_segmentation_frame(fig, output_file)
            finally:
                plt.close(fig)

        segmented_directory = Path(settings.MEDIA_ROOT) / str(uuid) / "segmented"
        segmented_directory.mkdir(parents=True, exist_ok=True)

        for cell_number in range(1, int(np.max(seg)) + 1):
            cell_image = np.zeros_like(seg)
            cell_image[seg == cell_number] = 255
            cell_image_path = segmented_directory / f"cell_{cell_number}.png"
            save_png_array(
                cell_image.astype(np.uint8),
                cell_image_path,
                profile=PNG_PROFILE_ANALYSIS_FAST,
            )

        dv_file = DVFile(dv_path)
        try:
            cell_stack = dv_file.asarray()
        finally:
            dv_file.close()
        cell_image_cache: dict[int, dict[str, np.ndarray]] = defaultdict(dict)
        if cell_stack.ndim == 2:
            cell_stack = np.expand_dims(cell_stack, axis=0)

        for image_num in range(cell_stack.shape[0]):
            _raise_if_cancelled(progress)
            image = np.array(cell_stack[image_num])
            image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1))
            image = np.round(image * 255).astype(np.uint8)
            if len(image.shape) != 3 or image.shape[2] != 3:
                image = np.expand_dims(image, axis=-1)
                image = np.tile(image, 3)

            cached_channel_name = layer_channel_lookup.get(image_num)
            image_outlined = image.copy()
            if cached_channel_name == CHANNEL_ROLE_DIC:
                _draw_pair_geometry_overlay(image_outlined, pair_geometry_cache)

            for i in range(1, int(np.max(seg) + 1)):
                cell_tif_image = f"{dv_name}-{image_num}-{i}.png"
                no_outline_image = f"{dv_name}-{image_num}-{i}-no_outline.png"

                entry = pair_geometry_cache.get(i)
                if entry is None:
                    continue
                local_contours = entry.local_contours
                min_x = entry.min_x
                max_x = entry.max_x
                min_y = entry.min_y
                max_y = entry.max_y

                outline_path = Path(f"{outputdirectory}{dv_name}-{i}.outline")
                if not outline_path.exists() or not use_cache:
                    with open(outline_path, "w", newline="") as csvfile:
                        csvwriter = csv.writer(csvfile, lineterminator="\n")
                        for idx, contour in enumerate(local_contours):
                            if idx > 0:
                                csvwriter.writerow([])
                            for point in contour.reshape(-1, 2):
                                csvwriter.writerow([int(point[1]), int(point[0])])

                cellpair_image = image_outlined[min_x:max_x, min_y:max_y]
                not_outlined_image = image[min_x:max_x, min_y:max_y]
                if cached_channel_name == CHANNEL_ROLE_DIC:
                    _draw_pair_parentage_labels(cellpair_image, entry)
                if cached_channel_name:
                    cell_image_cache[i][cached_channel_name] = np.array(
                        not_outlined_image,
                        copy=True,
                    )
                if not (segmented_directory / cell_tif_image).exists() or not use_cache:
                    save_png_array(
                        cellpair_image,
                        segmented_directory / cell_tif_image,
                        profile=PNG_PROFILE_ANALYSIS_FAST,
                    )
                if not (segmented_directory / no_outline_image).exists() or not use_cache:
                    save_png_array(
                        not_outlined_image,
                        segmented_directory / no_outline_image,
                        profile=PNG_PROFILE_ANALYSIS_FAST,
                    )

        num_cells = max(int(np.max(seg)), 0)
        instance, _ = SegmentedImage.objects.update_or_create(
            UUID=uuid,
            defaults={
                "user_id": get_guest_user(),
                "file_location": f"user_{uuid}/{dv_name}.png",
                "ImagePath": f"{settings.MEDIA_URL}{uuid}/output/{dv_name}_frame_0.png",
                "CellPairPrefix": f"{settings.MEDIA_URL}{uuid}/segmented/cell_",
                "NumCells": num_cells,
            },
        )
        CellStatistics.objects.filter(segmented_image=instance).delete()

        configuration = user.config if getattr(user, "is_authenticated", False) else settings.DEFAULT_SEGMENT_CONFIG
        execution_plan = build_stats_execution_plan(config_snapshot.get("selected_analysis", []))
        selected_analysis = list(execution_plan.selected_plugins)
        raw_puncta_line_width = config_snapshot.get(
            "stats_puncta_line_width_value",
            config_snapshot.get(
                "punctaLineWidth",
                config_snapshot.get("redLineWidth", config_snapshot.get("mCherryWidth", 1)),
            ),
        )
        raw_cen_dot_distance = config_snapshot.get(
            "stats_cen_dot_distance_value",
            config_snapshot.get("cenDotDistance", config_snapshot.get("distance", 37)),
        )
        puncta_line_width_unit = str(
            config_snapshot.get(
                "stats_puncta_line_width_unit",
                config_snapshot.get("stats_red_line_width_unit", config_snapshot.get("stats_mcherry_width_unit", "px")),
            )
        )
        cen_dot_distance_unit = str(
            config_snapshot.get(
                "stats_cen_dot_distance_unit",
                config_snapshot.get("stats_gfp_distance_unit", "px"),
            )
        )
        session_manual_scale = config_snapshot.get("stats_microns_per_pixel", 0.1)
        scale_info = normalize_scale_info(
            uploaded_image.scale_info,
            manual_default=session_manual_scale,
            prefer_metadata_default=bool(config_snapshot.get("stats_use_metadata_scale", True)),
        )
        if uploaded_image.scale_info != scale_info:
            uploaded_image.scale_info = scale_info
            uploaded_image.save(update_fields=["scale_info"])
        scale_context = resolve_scale_context(
            scale_info,
            manual_default=session_manual_scale,
            prefer_metadata_default=bool(config_snapshot.get("stats_use_metadata_scale", True)),
        )
        effective_um_per_px = scale_context.get("effective_um_per_px", 0.1)
        x_um_per_px = scale_context.get("x_um_per_px", effective_um_per_px)
        y_um_per_px = scale_context.get("y_um_per_px", effective_um_per_px)
        line_width_proxy_um_per_px = scale_context.get(
            "line_width_proxy_um_per_px",
            effective_um_per_px,
        )
        cen_dot_distance_unit = normalize_length_unit(cen_dot_distance_unit, default="px")

        puncta_line_width = convert_length_to_pixels(
            raw_puncta_line_width,
            puncta_line_width_unit,
            minimum_px=1,
            fallback_px=1,
            um_per_px=line_width_proxy_um_per_px,
        )
        if cen_dot_distance_unit == "um":
            try:
                cen_dot_distance = float(raw_cen_dot_distance)
            except (TypeError, ValueError):
                cen_dot_distance = 37.0
            if not math.isfinite(cen_dot_distance) or cen_dot_distance < 0:
                cen_dot_distance = 37.0
            cen_dot_distance_px_equivalent = convert_length_to_pixels(
                cen_dot_distance,
                "um",
                minimum_px=0,
                fallback_px=37,
                um_per_px=line_width_proxy_um_per_px,
            )
            cen_dot_distance_mode = "physical_um"
        else:
            cen_dot_distance = float(
                convert_length_to_pixels(
                    raw_cen_dot_distance,
                    cen_dot_distance_unit,
                    minimum_px=0,
                    fallback_px=37,
                    um_per_px=effective_um_per_px,
                )
            )
            cen_dot_distance_px_equivalent = int(cen_dot_distance)
            cen_dot_distance_mode = "pixel"
        try:
            cen_dot_collinearity_threshold = int(
                config_snapshot.get(
                    "cenDotCollinearityThreshold",
                    config_snapshot.get("threshold", 66),
                )
            )
        except (TypeError, ValueError):
            cen_dot_collinearity_threshold = 66
        if cen_dot_collinearity_threshold < 0:
            cen_dot_collinearity_threshold = 66
        raw_cen_dot_proximity_radius = config_snapshot.get(
            "stats_cen_dot_proximity_radius_value",
            config_snapshot.get("cenDotProximityRadius", 13),
        )
        cen_dot_proximity_radius_unit = normalize_length_unit(
            str(config_snapshot.get("stats_cen_dot_proximity_radius_unit", "px")),
            default="px",
        )
        if cen_dot_proximity_radius_unit == "um":
            try:
                cen_dot_proximity_radius = float(raw_cen_dot_proximity_radius)
            except (TypeError, ValueError):
                cen_dot_proximity_radius = 13.0
            if not math.isfinite(cen_dot_proximity_radius) or cen_dot_proximity_radius < 0:
                cen_dot_proximity_radius = 13.0
            cen_dot_proximity_radius_px_equivalent = convert_length_to_pixels(
                cen_dot_proximity_radius,
                "um",
                minimum_px=0,
                fallback_px=13,
                um_per_px=line_width_proxy_um_per_px,
            )
        else:
            cen_dot_proximity_radius = float(
                convert_length_to_pixels(
                    raw_cen_dot_proximity_radius,
                    cen_dot_proximity_radius_unit,
                    minimum_px=0,
                    fallback_px=13,
                    um_per_px=effective_um_per_px,
                )
            )
            cen_dot_proximity_radius_px_equivalent = int(cen_dot_proximity_radius)
        green_contour_filter_enabled = config_snapshot.get(
            "greenContourFilterEnabled",
            config_snapshot.get("gfpFilterEnabled", False),
        )
        alternate_red_detection = config_snapshot.get(
            "alternateRedDetection",
            config_snapshot.get("alternateMCherryDetection", False),
        )

        configured_puncta_line_width = _process_config_value(
            configuration,
            "puncta_line_width",
            "red_line_width",
            DEFAULT_PROCESS_CONFIG.get("puncta_line_width", 1),
        )

        conf = {
            "input_dir": input_dir,
            "output_dir": os.path.join(str(settings.MEDIA_ROOT), str(uuid)),
            "kernel_size": configuration["kernel_size"],
            "puncta_line_width": configured_puncta_line_width,
            "kernel_deviation": configuration["kernel_deviation"],
            "arrested": configuration["arrested"],
            "analysis": selected_analysis,
            "puncta_line_mode": normalize_puncta_line_mode(
                config_snapshot.get("puncta_line_mode"),
                default=DEFAULT_PUNCTA_LINE_MODE,
            ),
            "nuclear_cell_pair_mode": config_snapshot.get(
                "nuclear_cell_pair_mode",
                config_snapshot.get("nuclear_cellular_mode", "green_nucleus"),
            ),
            "green_contour_filter_enabled": green_contour_filter_enabled,
            "alternate_red_detection": alternate_red_detection,
        }
        write_overlay_render_config(
            uuid,
            build_overlay_render_config(
                image_stem=dv_name,
                channel_config=channel_config,
                kernel_size=configuration["kernel_size"],
                kernel_deviation=configuration["kernel_deviation"],
                puncta_line_width=configured_puncta_line_width,
                arrested=configuration["arrested"],
                selected_analysis=selected_analysis,
                puncta_line_mode=normalize_puncta_line_mode(
                    config_snapshot.get("puncta_line_mode"),
                    default=DEFAULT_PUNCTA_LINE_MODE,
                ),
                nuclear_cell_pair_mode=config_snapshot.get(
                    "nuclear_cell_pair_mode",
                    config_snapshot.get("nuclear_cellular_mode", "green_nucleus"),
                ),
                puncta_line_width_px=puncta_line_width,
                cen_dot_distance_value_used=cen_dot_distance,
                cen_dot_collinearity_threshold=cen_dot_collinearity_threshold,
                green_contour_filter_enabled=bool(green_contour_filter_enabled),
                alternate_red_detection=bool(alternate_red_detection),
                puncta_line_width_unit=puncta_line_width_unit,
                cen_dot_distance_unit=cen_dot_distance_unit,
                cen_dot_proximity_radius=cen_dot_proximity_radius,
                cen_dot_proximity_radius_unit=cen_dot_proximity_radius_unit,
            ),
        )

        if selected_analysis:
            progress.set_phase("Calculating Statistics", status="running")

        for cell_number in range(1, int(np.max(seg)) + 1):
            _raise_if_cancelled(progress)
            logger.debug(
                "Calculating statistics for cell %s in image %s (UUID: %s)",
                cell_number,
                dv_name,
                uuid,
            )
            cp, _ = CellStatistics.objects.get_or_create(
                segmented_image=instance,
                cell_id=cell_number,
                defaults={
                    "puncta_distance": 0.0,
                    "puncta_line_intensity": 0.0,
                    "nucleus_intensity_sum": 0.0,
                    "cell_pair_intensity_sum": 0.0,
                    "green_red_intensity_1": 0.0,
                    "green_red_intensity_2": 0.0,
                    "green_red_intensity_3": 0.0,
                    "dv_file_path": str(dv_path),
                    "image_name": dv_name + ".dv",
                },
            )

            cp.properties = dict(cp.properties or {})
            cp.properties["puncta_line_mode"] = normalize_puncta_line_mode(
                config_snapshot.get("puncta_line_mode"),
                default=DEFAULT_PUNCTA_LINE_MODE,
            )
            cp.properties["nuclear_cell_pair_mode"] = config_snapshot.get(
                "nuclear_cell_pair_mode",
                config_snapshot.get("nuclear_cellular_mode", "green_nucleus"),
            )
            cp.properties["scale_effective_um_per_px"] = effective_um_per_px
            cp.properties["scale_source"] = scale_info.get("source", "manual_global")
            cp.properties["scale_status"] = scale_info.get("status", "missing")
            cp.properties["scale_note"] = scale_info.get("note", "")
            cp.properties["scale_manual_um_per_px"] = scale_info.get("manual_um_per_px")
            cp.properties["scale_metadata_um_per_px"] = scale_info.get("metadata_um_per_px")
            cp.properties["scale_x_um_per_px"] = x_um_per_px
            cp.properties["scale_y_um_per_px"] = y_um_per_px
            cp.properties["scale_is_anisotropic"] = bool(
                scale_context.get("is_anisotropic", False)
            )
            cp.properties["scale_distance_mode"] = scale_context.get("distance_mode", "scalar")
            cp.properties["scale_line_width_proxy_um_per_px"] = line_width_proxy_um_per_px
            cp.properties["stats_puncta_line_width_px"] = puncta_line_width
            cp.properties["stats_cen_dot_distance_px"] = cen_dot_distance_px_equivalent
            cp.properties["stats_cen_dot_distance_value"] = cen_dot_distance
            cp.properties["stats_cen_dot_distance_mode"] = cen_dot_distance_mode
            cp.properties["stats_puncta_line_width_unit"] = puncta_line_width_unit
            cp.properties["stats_cen_dot_distance_unit"] = cen_dot_distance_unit
            cp.properties["stats_cen_dot_proximity_radius_px"] = cen_dot_proximity_radius_px_equivalent
            cp.properties["stats_cen_dot_proximity_radius_value"] = cen_dot_proximity_radius
            cp.properties["stats_cen_dot_proximity_radius_unit"] = cen_dot_proximity_radius_unit

            cp.properties["neck_split"] = _build_neck_split_properties(
                pair_geometry_cache.get(cell_number)
            )

            debug_red, debug_green, debug_blue = get_stats(
                cp,
                conf,
                execution_plan,
                puncta_line_width,
                cen_dot_distance,
                cen_dot_collinearity_threshold,
                cen_dot_proximity_radius,
                green_contour_filter_enabled,
                alternate_red_detection,
                cached_images=cell_image_cache.get(cell_number),
            )
            rendered_overlay_images = {
                "red": debug_red,
                "green": debug_green,
                "blue": debug_blue,
            }

            if str(config_snapshot.get("execution_mode", "sync")).lower() == "worker":
                persist_overlay_cache_images(
                    uuid,
                    cell_number,
                    rendered_overlay_images,
                    overwrite=False,
                )

            if settings.SEGMENT_SAVE_DEBUG_ARTIFACTS:
                persist_debug_overlay_exports(
                    uuid,
                    dv_name,
                    cell_number,
                    rendered_overlay_images,
                )

            cp.save()

        cleanup_transient_processing_artifacts(uuid, remove_preview_assets=True)

    duration = time.time() - start_time
    if getattr(user, "is_authenticated", False):
        user.processing_used += duration
        user.save(update_fields=["processing_used"])

    return _finalize_segmented_run_batch_for_user(
        user,
        uuid_list,
        auto_save_experiments=auto_save_experiments,
    )
