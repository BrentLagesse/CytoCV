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
from PIL import Image
from cv2_rolling_ball import subtract_background_rolling_ball
from django.conf import settings
from django.db import transaction
from mrc import DVFile

from core.config import DEFAULT_CHANNEL_CONFIG, DEFAULT_PROCESS_CONFIG, input_dir
from core.contour_processing import get_contour_center, get_neighbor_count
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
from core.services.overlay_rendering import (
    build_overlay_render_config,
    persist_debug_overlay_exports,
    persist_overlay_cache_images,
    write_overlay_render_config,
)
from core.stats_plugins import build_stats_execution_plan
from core.views.segment_image import (
    AUTOSAVE_STORAGE_FULL_MESSAGE,
    _build_layer_channel_lookup,
    _resolve_uploaded_dv_path,
    get_stats,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SegmentationBatchResult:
    """Outcome of a completed segmentation batch."""

    storage_warning_message: str = ""


def _current_owner_filter_for_user(user) -> dict[str, object]:
    if getattr(user, "is_authenticated", False):
        return {"user": user}
    return {"user_id": get_guest_user()}


def _raise_if_cancelled(progress: AnalysisProgressHandle) -> None:
    if progress.is_cancel_requested():
        raise AnalysisCancelled()


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

    progress.set_phase("Segmenting Images", status="running")

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

        outlines = np.zeros(seg.shape)
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
                    mcherry_index = channel_config.get("mCherry")
                    mcherry_image = dv_file.asarray()[mcherry_index]
                finally:
                    dv_file.close()

                mcherry_image = np.round(mcherry_image * 255).astype(np.uint8)
                if len(mcherry_image.shape) != 3 or mcherry_image.shape[2] != 3:
                    mcherry_image = np.expand_dims(mcherry_image, axis=-1)
                    mcherry_image = np.tile(mcherry_image, 3)
                mcherry_image_gray = cv2.cvtColor(mcherry_image, cv2.COLOR_RGB2GRAY)
                mcherry_image_gray, _ = subtract_background_rolling_ball(
                    mcherry_image_gray,
                    50,
                    light_background=False,
                    use_paraboloid=False,
                    do_presmooth=True,
                )
                _, mcherry_image_thresh = cv2.threshold(
                    mcherry_image_gray,
                    0,
                    1,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU,
                )
                mcherry_image_cont, _ = cv2.findContours(mcherry_image_thresh, 1, 2)

                min_mcherry_distance: dict[int, float] = {}
                min_mcherry_loc: dict[int, int] = {}
                for cnt1 in mcherry_image_cont:
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

                    for cnt2 in mcherry_image_cont:
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
                        if min_mcherry_distance.get(c_id) is None:
                            min_mcherry_distance[c_id] = distance
                            min_mcherry_loc[c_id] = int(seg[c2x][c2y])
                            lines_to_draw[c_id] = ((c1y, c1x), (c2y, c2x))
                        elif distance < min_mcherry_distance[c_id]:
                            min_mcherry_distance[c_id] = distance
                            min_mcherry_loc[c_id] = int(seg[c2x][c2y])
                            lines_to_draw[c_id] = ((c1y, c1x), (c2y, c2x))
                        elif distance == min_mcherry_distance[c_id]:
                            logger.debug(
                                "Found tied mCherry pair distance while pairing cells: cell_a=%s cell_b=%s nearest=%s distance=%s",
                                seg[c1x][c1y],
                                seg[c2x][c2y],
                                min_mcherry_loc[c_id],
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

            seg_image = Image.fromarray(seg)
            seg_image.save(str(outputdirectory) + "\\cellpairs.tif")

        for frame_idx in range(image_stack.shape[0]):
            _raise_if_cancelled(progress)
            image = Image.fromarray(image_stack[frame_idx])
            image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1))
            image = np.round(image * 255).astype(np.uint8)
            if len(image.shape) != 3 or image.shape[2] != 3:
                image = np.expand_dims(image, axis=-1)
                image = np.tile(image, 3)

            for i in range(1, int(np.max(seg) + 1)):
                tmp = np.zeros(seg.shape)
                tmp[np.where(seg == i)] = 1
                tmp = tmp - skimage.morphology.erosion(tmp)
                outlines += tmp

            image_outlined = image.copy()
            image_outlined[outlines > 0] = (0, 255, 255)

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
            outlines = np.zeros(seg.shape)
            for i in range(1, int(np.max(seg) + 1)):
                tmp = np.zeros(seg.shape)
                tmp[np.where(seg == i)] = 1
                tmp = tmp - skimage.morphology.erosion(tmp)
                outlines += tmp

            image_outlined = image.copy()
            image_outlined[outlines > 0] = (0, 255, 255)

            for i in range(1, int(np.max(seg) + 1)):
                cell_tif_image = f"{dv_name}-{image_num}-{i}.png"
                no_outline_image = f"{dv_name}-{image_num}-{i}-no_outline.png"

                a = np.where(seg == i)
                min_x = max(np.min(a[0]) - 1, 0)
                max_x = min(np.max(a[0]) + 1, seg.shape[0])
                min_y = max(np.min(a[1]) - 1, 0)
                max_y = min(np.max(a[1]) + 1, seg.shape[1])

                outline_path = Path(f"{outputdirectory}{dv_name}-{i}.outline")
                if not outline_path.exists() or not use_cache:
                    with open(outline_path, "w", newline="") as csvfile:
                        csvwriter = csv.writer(csvfile, lineterminator="\n")
                        csvwriter.writerows(zip(a[0] - min_x, a[1] - min_y))

                cellpair_image = image_outlined[min_x:max_x, min_y:max_y]
                not_outlined_image = image[min_x:max_x, min_y:max_y]
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
        raw_mcherry_width = config_snapshot.get(
            "stats_mcherry_width_value",
            config_snapshot.get("mCherryWidth", 1),
        )
        raw_gfp_distance = config_snapshot.get(
            "stats_gfp_distance_value",
            config_snapshot.get("distance", 37),
        )
        mcherry_width_unit = str(config_snapshot.get("stats_mcherry_width_unit", "px"))
        gfp_distance_unit = str(config_snapshot.get("stats_gfp_distance_unit", "px"))
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
        gfp_distance_unit = normalize_length_unit(gfp_distance_unit, default="px")

        mcherry_width = convert_length_to_pixels(
            raw_mcherry_width,
            mcherry_width_unit,
            minimum_px=1,
            fallback_px=1,
            um_per_px=line_width_proxy_um_per_px,
        )
        if gfp_distance_unit == "um":
            try:
                gfp_distance = float(raw_gfp_distance)
            except (TypeError, ValueError):
                gfp_distance = 37.0
            if not math.isfinite(gfp_distance) or gfp_distance < 0:
                gfp_distance = 37.0
            gfp_distance_px_equivalent = convert_length_to_pixels(
                gfp_distance,
                "um",
                minimum_px=0,
                fallback_px=37,
                um_per_px=line_width_proxy_um_per_px,
            )
            gfp_distance_mode = "physical_um"
        else:
            gfp_distance = float(
                convert_length_to_pixels(
                    raw_gfp_distance,
                    gfp_distance_unit,
                    minimum_px=0,
                    fallback_px=37,
                    um_per_px=effective_um_per_px,
                )
            )
            gfp_distance_px_equivalent = int(gfp_distance)
            gfp_distance_mode = "pixel"
        try:
            gfp_threshold = int(config_snapshot.get("threshold", 66))
        except (TypeError, ValueError):
            gfp_threshold = 66
        if gfp_threshold < 0:
            gfp_threshold = 66
        gfp_filter_enabled = config_snapshot.get("gfpFilterEnabled", False)
        alternate_mcherry_detection = config_snapshot.get("alternateMCherryDetection", False)

        conf = {
            "input_dir": input_dir,
            "output_dir": os.path.join(str(settings.MEDIA_ROOT), str(uuid)),
            "kernel_size": configuration["kernel_size"],
            "mCherry_line_width": configuration["mCherry_line_width"],
            "kernel_deviation": configuration["kernel_deviation"],
            "arrested": configuration["arrested"],
            "analysis": selected_analysis,
            "nuclear_cellular_mode": config_snapshot.get(
                "nuclear_cellular_mode",
                "green_nucleus",
            ),
            "gfp_filter_enabled": gfp_filter_enabled,
            "alternate_mcherry_detection": alternate_mcherry_detection,
        }
        write_overlay_render_config(
            uuid,
            build_overlay_render_config(
                image_stem=dv_name,
                channel_config=channel_config,
                kernel_size=configuration["kernel_size"],
                kernel_deviation=configuration["kernel_deviation"],
                mcherry_line_width=configuration["mCherry_line_width"],
                arrested=configuration["arrested"],
                selected_analysis=selected_analysis,
                nuclear_cellular_mode=config_snapshot.get(
                    "nuclear_cellular_mode",
                    "green_nucleus",
                ),
                mcherry_width_px=mcherry_width,
                gfp_distance_value_used=gfp_distance,
                gfp_threshold=gfp_threshold,
                gfp_filter_enabled=bool(gfp_filter_enabled),
                alternate_mcherry_detection=bool(alternate_mcherry_detection),
                mcherry_width_unit=mcherry_width_unit,
                gfp_distance_unit=gfp_distance_unit,
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
                    "distance": 0.0,
                    "line_gfp_intensity": 0.0,
                    "nucleus_intensity_sum": 0.0,
                    "cellular_intensity_sum": 0.0,
                    "green_red_intensity_1": 0.0,
                    "green_red_intensity_2": 0.0,
                    "green_red_intensity_3": 0.0,
                    "dv_file_path": str(dv_path),
                    "image_name": dv_name + ".dv",
                },
            )

            cp.properties = dict(cp.properties or {})
            cp.properties["nuclear_cellular_mode"] = config_snapshot.get(
                "nuclear_cellular_mode",
                "green_nucleus",
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
            cp.properties["stats_mcherry_width_px"] = mcherry_width
            cp.properties["stats_gfp_distance_px"] = gfp_distance_px_equivalent
            cp.properties["stats_gfp_distance_threshold"] = gfp_distance
            cp.properties["stats_gfp_distance_mode"] = gfp_distance_mode
            cp.properties["stats_mcherry_width_unit"] = mcherry_width_unit
            cp.properties["stats_gfp_distance_unit"] = gfp_distance_unit

            debug_mcherry, debug_gfp, debug_dapi = get_stats(
                cp,
                conf,
                execution_plan,
                mcherry_width,
                gfp_distance,
                gfp_threshold,
                gfp_filter_enabled,
                alternate_mcherry_detection,
                cached_images=cell_image_cache.get(cell_number),
            )
            rendered_overlay_images = {
                "mcherry": debug_mcherry,
                "gfp": debug_gfp,
                "dapi": debug_dapi,
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
