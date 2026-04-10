# =========================
# Standard library imports
# =========================
import csv
import logging
import math
import os
import time
from collections import defaultdict
from pathlib import Path
import json
import hashlib

# ==========================================================
# Matplotlib backend (must run BEFORE importing pyplot/etc.)
# ==========================================================
os.environ.setdefault("MPLBACKEND", "Agg")
try:
    import matplotlib  # noqa: E402
    matplotlib.use("Agg", force=True)
except Exception:
    # In server contexts we prefer to fail closed (headless) vs. crash.
    pass

# =========================
# Third-party library imports
# =========================
import cv2
import matplotlib.pyplot as plt
import matplotlib.patheffects as PathEffects
import numpy as np
import skimage
from PIL import Image
from cv2_rolling_ball import subtract_background_rolling_ball
from mrc import DVFile
from scipy.spatial.distance import euclidean
from skimage import io

# =========================
# Django imports
# =========================
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect

# =========================
# Local application imports
# =========================
from cytocv.settings import MEDIA_ROOT, MEDIA_URL
from .utils import write_progress, is_cancelled, clear_cancelled, prune_experiment_session_state
from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
)
from core.config import (
    DEFAULT_PROCESS_CONFIG,
    get_channel_config_for_uuid,
    input_dir,
    output_dir,
)
from core.models import CellStatistics, Contour, SegmentedImage, UploadedImage, get_guest_user
from core.image_processing import (
    ensure_3channel_bgr,
    load_image,
    preprocess_image_to_gray,
)
from core.contour_processing import (
    find_contours,
    get_contour_center,
    get_neighbor_count,
    merge_contour,
)
from core.stats_plugins import StatsExecutionPlan, build_stats_execution_plan
from accounts.preferences import should_auto_save_experiments
from core.scale import (
    convert_length_to_pixels,
    normalize_length_unit,
    normalize_scale_info,
    resolve_scale_context,
)
from core.services.artifact_storage import (
    PNG_PROFILE_ANALYSIS_FAST,
    StorageQuotaExceeded,
    assert_user_can_save_runs,
    cleanup_failed_processing_artifacts,
    cleanup_transient_processing_artifacts,
    delete_uploaded_run_by_uuid,
    is_storage_full_error,
    log_storage_capacity_failure,
    refresh_user_storage_usage,
    resolve_uploaded_file_path,
    save_png_array,
)
from core.services.canonical_contours import (
    build_canonical_contour_payload,
    flatten_slot_contours,
)
from core.services.overlay_rendering import (
    build_overlay_render_config,
    persist_debug_overlay_exports,
    persist_overlay_cache_images,
    write_overlay_render_config,
)
from core.services.puncta_line_mode import (
    DEFAULT_PUNCTA_LINE_MODE,
    get_puncta_line_mode_metadata,
    normalize_puncta_line_mode,
)

logger = logging.getLogger(__name__)

AUTOSAVE_STORAGE_FULL_MESSAGE = (
    "Analysis finished, but these files were not saved to your account because your storage is full."
)
PROCESSING_STORAGE_FULL_MESSAGE = (
    "Files could not be saved because storage is full. Free up space and try again."
)
STATS_CACHE_CHANNELS = frozenset(
    {CHANNEL_ROLE_RED, CHANNEL_ROLE_GREEN, CHANNEL_ROLE_BLUE, CHANNEL_ROLE_DIC}
)

## progress helpers moved to core.views.utils


def _build_layer_channel_lookup(channel_config: dict[str, object]) -> dict[int, str]:
    """Invert a channel config so layer indices can be mapped to stats channels."""

    layer_channel_lookup: dict[int, str] = {}
    for channel_name, raw_index in (channel_config or {}).items():
        if channel_name not in STATS_CACHE_CHANNELS:
            continue
        try:
            layer_index = int(raw_index)
        except (TypeError, ValueError):
            continue
        layer_channel_lookup[layer_index] = channel_name
    return layer_channel_lookup


def _process_config_value(
    config: dict[str, object],
    key: str,
    legacy_key: str,
    default,
):
    return config.get(key, config.get(legacy_key, default))

def _current_owner_filter(request) -> dict:
    """Return queryset filter args for the current upload owner."""

    if request.user.is_authenticated:
        return {"user": request.user}
    return {"user_id": get_guest_user()}


def _resolve_uploaded_dv_path(uploaded_image: UploadedImage) -> Path:
    """Return the on-disk DV path recorded for an uploaded file."""

    return resolve_uploaded_file_path(uploaded_image)


def set_options(opt):
    """
    This function sets global variables based on parsed arguments (like the old legacy code).
    """
    global input_dir, output_dir, ignore_btn, current_image, current_cell, outline_dict, image_dict, cp_dict, n
    input_dir = opt['input_dir']
    output_dir = opt['output_dir']
    kernel_size_input = opt['kernel_size']
    puncta_line_width_input = _process_config_value(opt, 'puncta_line_width', 'red_line_width', 1)
    kernel_deviation_input = opt['kernel_deviation']
    choice_var = opt['arrested']
    return kernel_size_input, puncta_line_width_input, kernel_deviation_input, choice_var

def get_stats(
    cp,
    conf,
    execution_plan: StatsExecutionPlan | None,
    puncta_line_width,
    cen_dot_distance,
    cen_dot_collinearity_threshold,
    cen_dot_proximity_radius=13,
    green_contour_filter_enabled=False,
    alternate_red_detection=False,
    cached_images=None,
):
    # loading configuration
    kernel_size_input, puncta_line_width_input, kernel_deviation_input, _ = set_options(conf)
    nuclear_cell_pair_mode = conf.get("nuclear_cell_pair_mode", "green_nucleus")
    puncta_line_metadata = get_puncta_line_mode_metadata(conf.get("puncta_line_mode"))
    cp.properties = dict(cp.properties or {})
    cp.properties["nuclear_cell_pair_mode"] = nuclear_cell_pair_mode
    cp.properties["puncta_line_mode"] = puncta_line_metadata["mode"]
    cp.properties["puncta_line_source_channel"] = puncta_line_metadata["source_channel"]
    cp.properties["puncta_line_measurement_channel"] = puncta_line_metadata["measurement_channel"]

    if execution_plan is None:
        execution_plan = build_stats_execution_plan(conf.get("analysis", []))
    stats_required_channels = {
        channel
        for channel in execution_plan.required_channels
        if channel in {CHANNEL_ROLE_RED, CHANNEL_ROLE_GREEN, CHANNEL_ROLE_BLUE}
    }

    # Always try to load all analysis channels if present so debug images remain available.
    channels_to_load = {
        CHANNEL_ROLE_RED,
        CHANNEL_ROLE_GREEN,
        CHANNEL_ROLE_BLUE,
        CHANNEL_ROLE_DIC,
    } | stats_required_channels
    images = load_image(
        cp,
        output_dir,
        required_channels=channels_to_load,
        cached_images=cached_images,
    )

    available_image_keys = [key for key in ("red", "green", "blue", "dic") if key in images]
    if not available_image_keys:
        blank = np.zeros((64, 64, 3), dtype=np.uint8)
        return Image.fromarray(blank), Image.fromarray(blank), Image.fromarray(blank)

    reference = images[available_image_keys[0]]

    def _canvas_for(channel_key: str) -> np.ndarray:
        base = images.get(channel_key, reference)
        return ensure_3channel_bgr(np.array(base, copy=True))

    edit_red_img = _canvas_for("red")
    edit_green_img = _canvas_for("green")
    edit_blue_img = _canvas_for("blue")

    if not execution_plan.selected_plugins:
        # No selected statistics: keep defaults and return plain debug frames.
        edit_red_img_rgb = cv2.cvtColor(edit_red_img, cv2.COLOR_BGR2RGB)
        edit_green_img_rgb = cv2.cvtColor(edit_green_img, cv2.COLOR_BGR2RGB)
        edit_blue_img_rgb = cv2.cvtColor(edit_blue_img, cv2.COLOR_BGR2RGB)
        return (
            Image.fromarray(edit_red_img_rgb),
            Image.fromarray(edit_green_img_rgb),
            Image.fromarray(edit_blue_img_rgb),
        )

    preprocessed_images = preprocess_image_to_gray(images, kernel_deviation_input, kernel_size_input)
    contours_data = find_contours(
        preprocessed_images,
        green_contour_filter_enabled,
        alternate_red_detection,
    )
    contours_data = build_canonical_contour_payload(
        contours_data,
        image_name=cp.image_name,
        cell_id=cp.cell_id,
        output_dir=output_dir,
        shape=reference.shape[:2],
    )
    canonical_red_contours = flatten_slot_contours(contours_data.get("canonical_red_slots", []))
    canonical_green_contours = flatten_slot_contours(contours_data.get("canonical_green_slots", []))

    best_contour_data = {}
    best_contour_blue = None
    best_blue_area = None
    blue_gray = preprocessed_images.get_image("gray_blue")
    if blue_gray is not None:
        image_area = float(blue_gray.shape[0] * blue_gray.shape[1])
        min_blue_area = max(10.0, image_area * 0.002)
        max_blue_area = image_area * 0.95

        def _pick_first_valid(contours, indices):
            for idx in indices:
                if idx >= len(contours):
                    continue
                cnt = contours[idx]
                area = cv2.contourArea(cnt)
                if min_blue_area <= area <= max_blue_area:
                    return cnt, area
            return None, None

        best_contour_blue, best_blue_area = _pick_first_valid(
            contours_data.get("contours_blue_3", []),
            contours_data.get("best_contours_blue_3", []),
        )

        if best_contour_blue is None:
            best_contour_blue, best_blue_area = _pick_first_valid(
                contours_data.get("contours_blue", []),
                contours_data.get("best_contours_blue", []),
            )

        if best_contour_blue is None and contours_data.get("contours_blue"):
            valid_blue = []
            for cnt in contours_data["contours_blue"]:
                area = cv2.contourArea(cnt)
                if min_blue_area <= area <= max_blue_area:
                    valid_blue.append((area, cnt))
            if valid_blue:
                valid_blue.sort(key=lambda item: item[0], reverse=True)
                best_blue_area, best_contour_blue = valid_blue[0]

    if best_contour_blue is not None:
        best_contour_data["Blue"] = best_contour_blue
        cp.blue_contour_size = float(best_blue_area)
    else:
        cp.blue_contour_size = 0.0

    if canonical_red_contours:
        cv2.drawContours(edit_red_img, canonical_red_contours, -1, (0, 0, 255), 1)
        cv2.drawContours(edit_green_img, canonical_red_contours, -1, (0, 0, 255), 1)
        cv2.drawContours(edit_blue_img, canonical_red_contours, -1, (0, 0, 255), 1)

    if best_contour_blue is not None:
        cv2.drawContours(edit_green_img, [best_contour_blue], 0, (255, 0, 0), 1)
        cv2.drawContours(edit_blue_img, [best_contour_blue], 0, (255, 0, 0), 1)

    if canonical_green_contours:
        cv2.drawContours(edit_red_img, canonical_green_contours, -1, (0, 255, 0), 1)
        cv2.drawContours(edit_green_img, canonical_green_contours, -1, (0, 255, 0), 1)
        cv2.drawContours(edit_blue_img, canonical_green_contours, -1, (0, 255, 0), 1)

    blue_contour_required_plugins = {"NucleusIntensity", "BlueNucleusIntensity"}
    for analysis in execution_plan.analyses:
        analysis_name = analysis.__class__.__name__
        if analysis_name in blue_contour_required_plugins and "Blue" not in best_contour_data:
            continue
        analysis.setting_up(cp, preprocessed_images, output_dir)
        analysis.calculate_statistics(
            best_contour_data,
            contours_data,
            edit_red_img,
            edit_green_img,
            puncta_line_width,
            cen_dot_distance,
            cen_dot_collinearity_threshold,
            cen_dot_proximity_radius,
        )

    # Convert BGR back to RGB so PIL shows correct colors
    edit_red_img_rgb = cv2.cvtColor(edit_red_img, cv2.COLOR_BGR2RGB)
    edit_green_img_rgb = cv2.cvtColor(edit_green_img, cv2.COLOR_BGR2RGB)
    edit_blue_img_rgb = cv2.cvtColor(edit_blue_img, cv2.COLOR_BGR2RGB)

    return (
        Image.fromarray(edit_red_img_rgb),
        Image.fromarray(edit_green_img_rgb),
        Image.fromarray(edit_blue_img_rgb),
    )

def finalize_segmented_run_batch(request, uuid_list: list[str], *, auto_save_experiments: bool) -> None:
    """Persist a completed batch when quota allows, otherwise keep it transient."""

    if not getattr(request.user, "is_authenticated", False):
        return

    current_uuids = {str(item) for item in uuid_list if str(item)}
    transient = {
        str(item)
        for item in request.session.get("transient_experiment_uuids", [])
        if str(item)
    }
    guest_id = get_guest_user()

    if not auto_save_experiments:
        transient.update(current_uuids)
        request.session["transient_experiment_uuids"] = sorted(transient)
        return

    try:
        assert_user_can_save_runs(request.user, current_uuids)
    except StorageQuotaExceeded as exc:
        log_storage_capacity_failure(
            stage="segment_autosave",
            user=request.user,
            uuids=current_uuids,
            required_bytes=exc.required_bytes,
            available_bytes=exc.available_bytes,
            exc=exc,
        )
        messages.error(request, AUTOSAVE_STORAGE_FULL_MESSAGE)
        SegmentedImage.objects.filter(UUID__in=current_uuids).update(user_id=guest_id)
        transient.update(current_uuids)
        request.session["transient_experiment_uuids"] = sorted(transient)
        refresh_user_storage_usage(request.user)
        return

    with transaction.atomic():
        SegmentedImage.objects.filter(UUID__in=current_uuids, user_id=guest_id).update(
            user=request.user
        )
    transient.difference_update(current_uuids)
    request.session["transient_experiment_uuids"] = sorted(transient)
    refresh_user_storage_usage(request.user)

'''Creates image "segments" from the desired image'''
def segment_image(request, uuids):
    """
    Handles segmentation cell_analysis for multiple images passed as UUIDs.
    """
    uuid_list = uuids.split(',')
    owner_filter = _current_owner_filter(request)
    cancelled = lambda: is_cancelled(uuids)
    auto_save_experiments = (
        should_auto_save_experiments(request.user)
        if request.user.is_authenticated
        else True
    )

    def cancel_response():
        for cleanup_uuid in uuid_list:
            delete_uploaded_run_by_uuid(cleanup_uuid)
        prune_experiment_session_state(request, uuid_list)
        return HttpResponse("Cancelled")

    def storage_full_response(exc: Exception):
        log_storage_capacity_failure(
            stage="segment_analysis",
            user=request.user,
            uuids=uuid_list,
            exc=exc,
        )
        for cleanup_uuid in uuid_list:
            cleanup_failed_processing_artifacts(cleanup_uuid)
        write_progress(uuids, "Idle")
        clear_cancelled(uuids)
        messages.error(request, PROCESSING_STORAGE_FULL_MESSAGE)
        return redirect("pre_process", uuids=uuids)

    if cancelled():
        write_progress(uuids, "Cancelled")
        clear_cancelled(uuids)
        return cancel_response()

    # Initialize some variables that would normally be a part of config
    choice_var = "Metaphase Arrested" # We need to be able to change this
    seg = None
    use_cache = True

    # Configuations for statistic calculation
    #kernel_size = 3
    #deviation = 1
    #mcherry_line_width = 1

    # Calculate processing time
    start_time = time.time()

    # We're gonna use image_dict to store all of the cell pairs (i think?)
    for uuid in uuid_list:
        if cancelled():
            write_progress(uuids, "Cancelled")
            clear_cancelled(uuids)
            return cancel_response()
        uploaded_image = get_object_or_404(UploadedImage, pk=uuid, **owner_filter)
        DV_Name = uploaded_image.name
        DV_path = _resolve_uploaded_dv_path(uploaded_image)
        channel_config = get_channel_config_for_uuid(uuid)
        layer_channel_lookup = _build_layer_channel_lookup(channel_config)
        image_dict = dict()
        image_dict[DV_Name] = list()

        # Need to grab the original DV file
        # Load the original raw image and rescale its intensity values
        f = DVFile(DV_path)
        try:
            im = f.asarray()
        finally:
            f.close()
        if im.ndim == 2:
            im = np.expand_dims(im, axis=0)

        cell_stats = {}

        image = Image.fromarray(im[0])
        image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1))
        image = np.round(image * 255).astype(np.uint8)

        debug_image = image

        # Convert the image to an RGB image, if necessary
        if len(image.shape) == 3 and image.shape[2] == 3:
            pass
        else:
            image = np.expand_dims(image, axis=-1)
            image = np.tile(image, 3)

        # TODO -- make it show it is choosing the correct segmented
        # Open the segmentation file (the mask generated in convert_to_image)
        # TODO:  on first run, this can't find outputs/masks/M***.tif'
        seg = np.array(Image.open(Path(MEDIA_ROOT) / str(uuid) / "output" / "mask.tif"))   # create a 2D matrix of the image

        #TODO:   If G1 Arrested, we don't want to merge neighbors and ignore non-budding cells
        #choices = ['Metaphase Arrested', 'G1 Arrested']
        outlines = np.zeros(seg.shape)
        if choice_var == 'Metaphase Arrested':
            # Create a raw file to store the outlines
            ignore_list = list()
            single_cell_list = list()
            # merge cell pairs
            neighbor_count = dict()
            closest_neighbors = dict()
            for i in range(1, int(np.max(seg) + 1)):
                cells = np.where(seg == i)
                #examine neighbors
                neighbor_list = list()
                for cell in zip(cells[0], cells[1]):
                    #TODO:  account for going over the edge without throwing out the data

                    try:
                        neighbor_list = get_neighbor_count(seg, cell, 3) # get neighbor with a 3 pixel radius from the cell
                    except:
                        continue
                    # count the number of pixels that are within 3 pixel radius of all neighbors
                    for neighbor in neighbor_list:
                        if int(neighbor) == i or int(neighbor) == 0: # same cell
                            continue
                        if neighbor in neighbor_count:
                            neighbor_count[neighbor] += 1
                        else:
                            neighbor_count[neighbor] = 1

                sorted_dict = {k: v for k, v in sorted(neighbor_count.items(), key=lambda item: item[1])}
                if len(sorted_dict) == 0:
                    single_cell_list.append(int(i))
                else:
                    if len(sorted_dict) == 1:
                        # one cell close by
                        closest_neighbors[i] = list(sorted_dict.items())[0][0]
                    else:
                        # find the closest neighbor by number of pixels close by
                        top_val = list(sorted_dict.items())[0][1]
                        second_val = list(sorted_dict.items())[1][1]
                        if second_val > 0.5 * top_val:    # things got confusing, so we throw it and its neighbor out
                            single_cell_list.append(int(i))
                            for cluster_cell in neighbor_count:
                                single_cell_list.append(int(cluster_cell))
                        else:
                            closest_neighbors[i] = list(sorted_dict.items())[0][0]

                #reset for the next cell
                neighbor_count = dict()
            #TODO:  Examine the spc110 dots and make closest dots neighbors

            #resolve_cells_using_spc110 = use_spc110.get()

            resolve_cells_using_spc110 = False # Hard coding this for now but will have to use a config file in the future

            lines_to_draw = dict()
            if resolve_cells_using_spc110:

                # Open the red channel from the DV stack.

                # basename = image_name.split('_R3D_REF')[0]
                # red_dir = input_dir + basename + '_PRJ_TIFFS/'
                # red_image_name = basename + '_PRJ' + '_w625' + '.tif'
                # red_image = np.array(Image.open(red_dir + red_image_name))

                # Which file are we trying to find here?
                f = DVFile(DV_path)
                try:
                    red_index = channel_config.get(CHANNEL_ROLE_RED)
                    red_image = f.asarray()[red_index]
                finally:
                    f.close()

                red_image = np.round(red_image * 255).astype(np.uint8)

                # Convert the image to an RGB image, if necessary
                if len(red_image.shape) == 3 and red_image.shape[2] == 3:
                    pass
                else:
                    red_image = np.expand_dims(red_image, axis=-1)
                    red_image = np.tile(red_image, 3)
                # find contours
                red_image_gray = cv2.cvtColor(red_image, cv2.COLOR_RGB2GRAY)
                red_image_gray, _background = subtract_background_rolling_ball(
                    red_image_gray,
                    50,
                    light_background=False,
                    use_paraboloid=False,
                    do_presmooth=True,
                )

                debug = False
                if debug:
                    plt.figure(dpi=600)
                    plt.title("red")
                    plt.imshow(red_image_gray, cmap='gray')
                    plt.show()

                _red_image_ret, red_image_thresh = cv2.threshold(
                    red_image_gray,
                    0,
                    1,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU,
                )
                red_image_cont, _red_image_h = cv2.findContours(red_image_thresh, 1, 2)

                if debug:
                    cv2.drawContours(image, red_image_cont, -1, 255, 1)
                    plt.figure(dpi=600)
                    plt.title("ref image with contours")
                    plt.imshow(image, cmap='gray')
                    plt.show()


                #921,800

                min_red_distance = dict()
                min_red_loc = dict()   # maps a red dot to its closest red dot in terms of cell id
                for cnt1 in red_image_cont:
                    try:
                        contourArea = cv2.contourArea(cnt1)
                        if contourArea > 100000:   #test for the big box, TODO: fix this to be adaptive
                            logger.debug("Discarded oversized bounding contour while pairing cells")
                            continue
                        coordinate = get_contour_center(cnt1)
                        # These are opposite of what we would expect
                        c1y = coordinate[0][0]
                        c1x = coordinate[0][1]


                    except:  #no moment found
                        continue
                    c_id = int(seg[c1x][c1y])
                    if c_id == 0:
                        continue
                    for cnt2 in red_image_cont:
                        try:
                            coordinate = get_contour_center(cnt2)
                            # find center of each contour
                            c2y = coordinate[0][0]
                            c2x = coordinate[0][1]

                        except:
                            continue #no moment found
                        if int(seg[c2x][c2y]) == 0:
                            continue
                        if seg[c1x][c1y] == seg[c2x][c2y]:   # these are the same cell already
                            continue
                        # find the closest point to each center
                        d = math.sqrt(pow(c1x - c2x, 2) + pow(c1y - c2y, 2))
                        if min_red_distance.get(c_id) == None:
                            min_red_distance[c_id] = d
                            min_red_loc[c_id] = int(seg[c2x][c2y])
                            lines_to_draw[c_id] = ((c1y,c1x), (c2y, c2x))
                        else:
                            if d < min_red_distance[c_id]:
                                min_red_distance[c_id] = d
                                min_red_loc[c_id] = int(seg[c2x][c2y])
                                lines_to_draw[c_id] = ((c1y, c1x), (c2y, c2x))  #flip it back here
                            elif d == min_red_distance[c_id]:
                                logger.debug(
                                    "Found tied Red pair distance while pairing cells: cell_a=%s cell_b=%s nearest=%s distance=%s",
                                    seg[c1x][c1y],
                                    seg[c2x][c2y],
                                    min_red_loc[c_id],
                                    d,
                                )

            for k, v in closest_neighbors.items():
                if v in closest_neighbors:      # check to see if v could be a mutual pair
                    if int(v) in ignore_list:    # if we have already paired this one, throw it out
                        single_cell_list.append(int(k))
                        continue

                    if closest_neighbors[int(v)] == int(k) and int(k) not in ignore_list:  # closest neighbors are reciprocal
                        #TODO:  set them to all be the same cell
                        to_update = np.where(seg == v)
                        ignore_list.append(int(v))
                        if resolve_cells_using_spc110:
                            if int(v) in min_red_loc:    #if we merge them here, we don't need to do it with red
                                del min_red_loc[int(v)]
                            if int(k) in min_red_loc:
                                del min_red_loc[int(k)]
                        for update in zip(to_update[0], to_update[1]):
                            seg[update[0]][update[1]] = k

                    elif int(k) not in ignore_list and not resolve_cells_using_spc110:
                        single_cell_list.append(int(k))


                elif int(k) not in ignore_list and not resolve_cells_using_spc110:
                    single_cell_list.append(int(k))

            if resolve_cells_using_spc110:
                for c_id, nearest_cid in min_red_loc.items():
                    if int(c_id) in ignore_list:    # if we have already paired this one, ignore it
                        continue
                    if int(nearest_cid) in min_red_loc:  #make sure the reciprocal exists
                        if min_red_loc[int(nearest_cid)] == int(c_id) and int(c_id) not in ignore_list:   # if it is mutual
                            #print('added a cell pair in image {} using the red-channel technique {} and {}'.format(image_name, int(nearest_cid),
                                                                                                    #int(c_id)))
                            if int(c_id) in single_cell_list:
                                single_cell_list.remove(int(c_id))
                            if int(nearest_cid) in single_cell_list:
                                single_cell_list.remove(int(nearest_cid))
                            to_update = np.where(seg == nearest_cid)
                            closest_neighbors[int(c_id)] = int(nearest_cid)
                            ignore_list.append(int(nearest_cid))
                            for update in zip(to_update[0], to_update[1]):
                                seg[update[0]][update[1]] = c_id
                        elif int(c_id) not in ignore_list:
                            logger.debug(
                                "Skipped non-mutual closest cell pair candidate: %s vs %s",
                                nearest_cid,
                                int(v),
                            )
                            single_cell_list.append(int(k))

            # remove single cells or confusing cells
            for cell in single_cell_list:
                seg[np.where(seg == cell)] = 0.0


            # only merge if two cells are both each others closest neighbors
                # otherwise zero them out?
            # rebase segment count
            to_rebase = list()
            for k, v in closest_neighbors.items():
                if k in ignore_list or k in single_cell_list:
                    continue
                else:
                    to_rebase.append(int(k))
            to_rebase.sort()

            for i, x in enumerate(to_rebase):
                seg[np.where(seg == x)] = i + 1

            # now seg has the updated masks, so lets save them so we don't have to do this every time
            outputdirectory = str(Path(MEDIA_ROOT)) + '/' + str(uuid) + '/output/'
            seg_image = Image.fromarray(seg)
            try:
                seg_image.save(str(outputdirectory) + "\\cellpairs.tif")
            except Exception as exc:
                if is_storage_full_error(exc):
                    return storage_full_response(exc)
                raise
        else:   #g1 arrested
            pass

        for i in range(1, int(np.max(seg)) + 1):
            image_dict[DV_Name].append(i)

        #base_image_name = image_name.split('_PRJ')[0]
        #for images in os.listdir(input_dir):
        # don't overlay if it isn't the right base image
        #if base_image_name not in images:
        #    continue
        if_g1 = ''
        #if choice_var.get() == 'G1 Arrested':   #if it is a g1 cell, do we really need a separate type of file?
        #    if_g1 = '-g1'
        #tif_image = images.split('.')[0] + if_g1 + '.tif'
        #if os.path.exists(output_dir + 'segmented/' + tif_image) and use_cache.get():
        #    continue
        #to_open = input_dir + images
        #if os.path.isdir(to_open):
        #    continue
        #image = np.array(Image.open(to_open))
        f = DVFile(DV_path)
        try:
            im = f.asarray()
        finally:
            f.close()
        if im.ndim == 2:
            im = np.expand_dims(im, axis=0)

        for frame_idx in range(im.shape[0]):
            # begin drawing the cell contours all over 4 DV images
            # TODO: Make this a method
            image = Image.fromarray(im[frame_idx])
            image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1)) # 0/1 normalization
            image = np.round(image * 255).astype(np.uint8) # scale for 8 bit gray scale

            # Convert the image to an RGB image, if necessary
            if len(image.shape) == 3 and image.shape[2] == 3:
                pass
            else:
                image = np.expand_dims(image, axis=-1)
                image = np.tile(image, 3)

            # Iterate over each integer in the segmentation and save the outline of each cell onto the outline file
            for i in range(1, int(np.max(seg) + 1)):
                tmp = np.zeros(seg.shape)
                tmp[np.where(seg == i)] = 1
                tmp = tmp - skimage.morphology.erosion(tmp)
                outlines += tmp

            # Overlay the outlines on the original image in green
            image_outlined = image.copy()
            image_outlined[outlines > 0] = (0, 255, 255)

            # Display the outline file
            fig = plt.figure(frameon=False)
            ax = plt.Axes(fig, [0., 0., 1., 1.])
            ax.set_axis_off()
            fig.add_axes(ax)
            ax.imshow(image_outlined)

            # debugging to see where the red signals connect
            for k, v in lines_to_draw.items():
                start, stop = v
                cv2.line(image_outlined, start, stop, (255,0,0), 1)
                #txt = ax.text(start[0], start[1], str(start), size=12)
                #txt.set_path_effects([PathEffects.withStroke(linewidth=1, foreground='w')])
                #txt = ax.text(stop[0], stop[1], str(stop), size=12)
                #txt.set_path_effects([PathEffects.withStroke(linewidth=1, foreground='w')])


            # iterate over each cell pair and add an ID to the image
            for i in range(1, int(np.max(seg) + 1)):
                loc = np.where(seg == i)
                if len(loc[0]) > 0:
                    txt = ax.text(loc[1][0], loc[0][0], str(i), size=12)
                    txt.set_path_effects([PathEffects.withStroke(linewidth=1, foreground='w')])
                else:
                    logger.debug("Could not find cell id %s while rendering frame labels", i)

            output_file = os.path.join(outputdirectory, f"{DV_Name}_frame_{frame_idx}.png")
            try:
                fig.savefig(output_file, dpi=600, bbox_inches='tight', pad_inches=0)
            except Exception as exc:
                plt.close(fig)
                if is_storage_full_error(exc):
                    return storage_full_response(exc)
                raise
            plt.close(fig)

        #plt.show()

        #TODO:  Combine the two iterations over the input directory images

        # This is where we overlay what we learned in the DIC onto the other images
        
        #filter_dir = input_dir  + base_image_name + '_PRJ_TIFFS/'
        segmented_directory = Path(MEDIA_ROOT) / str(uuid) / 'segmented'
        # Ensure directory exists
        try:
            segmented_directory.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            if is_storage_full_error(exc):
                return storage_full_response(exc)
            raise

        # Iterate over the segmented cells
        for cell_number in range(1, int(np.max(seg)) + 1):
            cell_image = np.zeros_like(seg)
            cell_image[seg == cell_number] = 255  # Mark cell areas

            # File paths
            cell_image_path = segmented_directory / f"cell_{cell_number}.png"

            # Save each cell image as PNG
            try:
                save_png_array(
                    cell_image.astype(np.uint8),
                    cell_image_path,
                    profile=PNG_PROFILE_ANALYSIS_FAST,
                )
            except Exception as exc:
                if is_storage_full_error(exc):
                    return storage_full_response(exc)
                raise
        
        try:
            os.makedirs(segmented_directory, exist_ok=True)
        except Exception as exc:
            if is_storage_full_error(exc):
                return storage_full_response(exc)
            raise
        f = DVFile(DV_path)
        try:
            image_stack = f.asarray()
        finally:
            f.close()
        cell_image_cache: dict[int, dict[str, np.ndarray]] = defaultdict(dict)

        if image_stack.ndim == 2:
            image_stack = np.expand_dims(image_stack, axis=0)

        for image_num in range(image_stack.shape[0]):
            if cancelled():
                write_progress(uuids, "Cancelled")
                clear_cancelled(uuids)
                return cancel_response()
            # images = os.path.split(full_path)[1]  # we start in separate directories, but need to end up in the same one
            # # don't overlay if it isn't the right base image
            # if base_image_name not in images:
            #     continue
            # extspl = os.path.splitext(images)
            # if len(extspl) != 2 or extspl[1] != '.tif':  # ignore files that aren't dv
            #     continue
            # #tif_image = images.split('.')[0] + '.tif'
            #
            # if os.path.isdir(full_path):
            #     continue
            image = np.array(image_stack[image_num])
            image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1))
            image = np.round(image * 255).astype(np.uint8)

            # Convert the image to an RGB image, if necessary
            if len(image.shape) == 3 and image.shape[2] == 3:
                pass
            else:
                image = np.expand_dims(image, axis=-1)
                image = np.tile(image, 3)

            # Trying to figure out why we're only seeing one wave length represented
            # plt.imsave(str(Path(MEDIA_ROOT)) + '/' + str(uuid) + '/' + DV_Name + '-' + str(image_num) + '.tif', image, dpi=600, format='TIFF')
            cached_channel_name = layer_channel_lookup.get(image_num)

            outlines = np.zeros(seg.shape)
            # Iterate over each integer in the segmentation and save the outline of each cell onto the outline file
            for i in range(1, int(np.max(seg) + 1)):
                tmp = np.zeros(seg.shape)
                tmp[np.where(seg == i)] = 1
                tmp = tmp - skimage.morphology.erosion(tmp)
                outlines += tmp
            
            # Overlay the outlines on the original image in green
            image_outlined = image.copy()
            # image_outlined[outlines > 0] = (0, 255, 0)
            # NOTE: Temporarily changing to cyan to debug the Green channel
            image_outlined[outlines > 0] = (0, 255, 255)

            # Iterate over each integer in the segmentation and save the outline of each cell onto the outline file
            for i in range(1, int(np.max(seg) + 1)):
                #cell_tif_image = tif_image.split('.')[0] + '-' + str(i) + '.tif'
                #no_outline_image = tif_image.split('.')[0] + '-' + str(i) + '-no_outline.tif'
                # cell_tif_image = images.split('.')[0] + '-' + str(i) + '.tif'
                # no_outline_image = images.split('.')[0] + '-' + str(i) + '-no_outline.tif'
                cell_tif_image = DV_Name + '-' + str(image_num) + '-' + str(i) + '.png'
                no_outline_image = DV_Name + '-' + str(image_num) + '-'  + str(i) + '-no_outline.png'

                a = np.where(seg == i)   # somethin bad is happening when i = 4 on my tests
                min_x = max(np.min(a[0]) - 1, 0)
                max_x = min(np.max(a[0]) + 1, seg.shape[0])
                min_y = max(np.min(a[1]) - 1, 0)
                max_y = min(np.max(a[1]) + 1, seg.shape[1])

                # a[0] contains the x coords and a[1] contains the y coords
                # save this to use later when I want to calculate cellular intensity

                #convert from absolute location to relative location for later use

                if not os.path.exists(str(outputdirectory) + DV_Name + '-' + str(i) + '.outline')  or not use_cache:
                    try:
                        with open(str(outputdirectory) + DV_Name + '-' + str(i) + '.outline', 'w') as csvfile:
                            csvwriter = csv.writer(csvfile, lineterminator='\n')
                            csvwriter.writerows(zip(a[0] - min_x, a[1] - min_y))
                    except Exception as exc:
                        if is_storage_full_error(exc):
                            return storage_full_response(exc)
                        raise

                cellpair_image = image_outlined[min_x: max_x, min_y:max_y]
                not_outlined_image = image[min_x: max_x, min_y:max_y]
                if cached_channel_name:
                    cell_image_cache[i][cached_channel_name] = np.array(not_outlined_image, copy=True)
                if not os.path.exists(segmented_directory / cell_tif_image) or not use_cache:  # don't redo things we already have
                    try:
                        save_png_array(
                            cellpair_image,
                            segmented_directory / cell_tif_image,
                            profile=PNG_PROFILE_ANALYSIS_FAST,
                        )
                    except Exception as exc:
                        if is_storage_full_error(exc):
                            return storage_full_response(exc)
                        raise
                if not os.path.exists(segmented_directory / no_outline_image) or not use_cache:  # don't redo things we already have
                    try:
                        save_png_array(
                            not_outlined_image,
                            segmented_directory / no_outline_image,
                            profile=PNG_PROFILE_ANALYSIS_FAST,
                        )
                    except Exception as exc:
                        if is_storage_full_error(exc):
                            return storage_full_response(exc)
                        raise

        # ================================================
        # Calculate statistics for each cell only once after the loop
        # ================================================

        num_cells = max(int(np.max(seg)), 0)
        instance, _ = SegmentedImage.objects.update_or_create(
            UUID=uuid,
            defaults={
                "user_id": get_guest_user(),
                "file_location": f"user_{uuid}/{DV_Name}.png",
                "ImagePath": f"{MEDIA_URL}{uuid}/output/{DV_Name}_frame_0.png",
                "CellPairPrefix": f"{MEDIA_URL}{uuid}/segmented/cell_",
                "NumCells": num_cells,
            },
        )
        CellStatistics.objects.filter(segmented_image=instance).delete()

        configuration = DEFAULT_PROCESS_CONFIG
        if request.user.is_authenticated:
            configuration = request.user.config
        else:
            configuration = settings.DEFAULT_SEGMENT_CONFIG

        execution_plan = build_stats_execution_plan(
            request.session.get('selected_analysis', [])
        )
        selected_analysis = list(execution_plan.selected_plugins)
        raw_puncta_line_width = request.session.get(
            'stats_puncta_line_width_value',
            request.session.get('punctaLineWidth', request.session.get('redLineWidth', request.session.get('mCherryWidth', 1))),
        )
        raw_cen_dot_distance = request.session.get(
            'stats_cen_dot_distance_value',
            request.session.get('cenDotDistance', request.session.get('distance', 37)),
        )
        puncta_line_width_unit = request.session.get(
            'stats_puncta_line_width_unit',
            request.session.get('stats_red_line_width_unit', request.session.get('stats_mcherry_width_unit', 'px')),
        )
        cen_dot_distance_unit = request.session.get(
            'stats_cen_dot_distance_unit',
            request.session.get('stats_gfp_distance_unit', 'px'),
        )
        session_manual_scale = request.session.get('stats_microns_per_pixel', 0.1)
        scale_info = normalize_scale_info(
            uploaded_image.scale_info,
            manual_default=session_manual_scale,
            prefer_metadata_default=bool(request.session.get("stats_use_metadata_scale", True)),
        )
        if uploaded_image.scale_info != scale_info:
            uploaded_image.scale_info = scale_info
            uploaded_image.save(update_fields=["scale_info"])
        scale_context = resolve_scale_context(
            scale_info,
            manual_default=session_manual_scale,
            prefer_metadata_default=bool(request.session.get("stats_use_metadata_scale", True)),
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
        cen_dot_collinearity_threshold = request.session.get(
            'cenDotCollinearityThreshold',
            request.session.get('threshold', 66),
        )
        try:
            cen_dot_collinearity_threshold = int(cen_dot_collinearity_threshold)
        except (TypeError, ValueError):
            cen_dot_collinearity_threshold = 66
        if cen_dot_collinearity_threshold < 0:
            cen_dot_collinearity_threshold = 66
        raw_cen_dot_proximity_radius = request.session.get(
            'stats_cen_dot_proximity_radius_value',
            request.session.get('cenDotProximityRadius', 13),
        )
        cen_dot_proximity_radius_unit = normalize_length_unit(
            request.session.get('stats_cen_dot_proximity_radius_unit', 'px'),
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
        green_contour_filter_enabled = request.session.get(
            'greenContourFilterEnabled',
            request.session.get('gfpFilterEnabled', 'False'),
        )
        alternate_red_detection = request.session.get(
            'alternateRedDetection',
            request.session.get('alternateMCherryDetection', 'False'),
        )

        configured_puncta_line_width = _process_config_value(
            configuration,
            "puncta_line_width",
            "red_line_width",
            DEFAULT_PROCESS_CONFIG.get("puncta_line_width", 1),
        )

        # Build a proper 'conf' dict with required keys for get_stats
        conf = {
            'input_dir': input_dir,
            'output_dir': os.path.join(str(settings.MEDIA_ROOT), str(uuid)),
            'kernel_size': configuration["kernel_size"],
            'puncta_line_width': configured_puncta_line_width,
            'kernel_deviation': configuration["kernel_deviation"],
            'arrested': configuration["arrested"],
            'analysis' : selected_analysis,
            'puncta_line_mode': normalize_puncta_line_mode(
                request.session.get("puncta_line_mode"),
                default=DEFAULT_PUNCTA_LINE_MODE,
            ),
            'nuclear_cell_pair_mode': request.session.get(
                "nuclear_cell_pair_mode",
                request.session.get("nuclear_cellular_mode", "green_nucleus"),
            ),
            'green_contour_filter_enabled': green_contour_filter_enabled,
            'alternate_red_detection': alternate_red_detection,
        }
        write_overlay_render_config(
            uuid,
            build_overlay_render_config(
                image_stem=DV_Name,
                channel_config=channel_config,
                kernel_size=configuration["kernel_size"],
                kernel_deviation=configuration["kernel_deviation"],
                puncta_line_width=configured_puncta_line_width,
                arrested=configuration["arrested"],
                selected_analysis=selected_analysis,
                puncta_line_mode=normalize_puncta_line_mode(
                    request.session.get("puncta_line_mode"),
                    default=DEFAULT_PUNCTA_LINE_MODE,
                ),
                nuclear_cell_pair_mode=request.session.get(
                    "nuclear_cell_pair_mode",
                    request.session.get("nuclear_cellular_mode", "green_nucleus"),
                ),
                puncta_line_width_px=puncta_line_width,
                cen_dot_distance_value_used=cen_dot_distance,
                cen_dot_collinearity_threshold=cen_dot_collinearity_threshold,
                green_contour_filter_enabled=(
                    green_contour_filter_enabled
                    if isinstance(green_contour_filter_enabled, bool)
                    else str(green_contour_filter_enabled).strip().lower() in {"1", "true", "yes", "on"}
                ),
                alternate_red_detection=(
                    alternate_red_detection
                    if isinstance(alternate_red_detection, bool)
                    else str(alternate_red_detection).strip().lower() in {"1", "true", "yes", "on"}
                ),
                puncta_line_width_unit=puncta_line_width_unit,
                cen_dot_distance_unit=cen_dot_distance_unit,
                cen_dot_proximity_radius=cen_dot_proximity_radius,
                cen_dot_proximity_radius_unit=cen_dot_proximity_radius_unit,
            ),
        )

        if cancelled():
            write_progress(uuids, "Cancelled")
            clear_cancelled(uuids)
            return cancel_response()

        # Mark accurate phase for UI only if user selected analyses
        if selected_analysis:
            write_progress(uuids, "Calculating Statistics")

        # For each cell_number in the segmentation, create/fetch a CellStatistics object
        # and call get_stats so it can mutate the fields on cp.
        for cell_number in range(1, int(np.max(seg)) + 1):
            logger.debug(
                "Calculating statistics for cell %s in image %s (UUID: %s)",
                cell_number,
                DV_Name,
                uuid,
            )

            # Create or get a CellStatistics row
            cp, created = CellStatistics.objects.get_or_create(
                segmented_image=instance,
                cell_id=cell_number,
                defaults={
                    # Cell statistics numerical defaults
                    'puncta_distance': 0.0,
                    'puncta_line_intensity': 0.0,
                    'nucleus_intensity_sum': 0.0,
                    'cell_pair_intensity_sum': 0.0,
                    'green_red_intensity_1': 0.0,
                    'green_red_intensity_2': 0.0,
                    'green_red_intensity_3': 0.0,

                    # Store file path information
                    'dv_file_path': str(DV_path),
                    'image_name': DV_Name + '.dv',
                }
            )

            # Now pass the real model object + conf to get_stats
            # This modifies cp's fields in place
            cp.properties = dict(cp.properties or {})
            cp.properties["puncta_line_mode"] = normalize_puncta_line_mode(
                request.session.get("puncta_line_mode"),
                default=DEFAULT_PUNCTA_LINE_MODE,
            )
            cp.properties["nuclear_cell_pair_mode"] = request.session.get(
                "nuclear_cell_pair_mode",
                request.session.get("nuclear_cellular_mode", "green_nucleus"),
            )
            cp.properties["scale_effective_um_per_px"] = effective_um_per_px
            cp.properties["scale_source"] = scale_info.get("source", "manual_global")
            cp.properties["scale_status"] = scale_info.get("status", "missing")
            cp.properties["scale_note"] = scale_info.get("note", "")
            cp.properties["scale_manual_um_per_px"] = scale_info.get("manual_um_per_px")
            cp.properties["scale_metadata_um_per_px"] = scale_info.get("metadata_um_per_px")
            cp.properties["scale_x_um_per_px"] = x_um_per_px
            cp.properties["scale_y_um_per_px"] = y_um_per_px
            cp.properties["scale_is_anisotropic"] = bool(scale_context.get("is_anisotropic", False))
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
            # Call get_stats to do the real work
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

            try:
                persist_overlay_cache_images(
                    uuid,
                    cell_number,
                    {
                        "red": debug_red,
                        "green": debug_green,
                        "blue": debug_blue,
                    },
                    overwrite=False,
                )
            except Exception as exc:
                if is_storage_full_error(exc):
                    return storage_full_response(exc)
                raise

            if settings.SEGMENT_SAVE_DEBUG_ARTIFACTS:
                try:
                    persist_debug_overlay_exports(
                        uuid,
                        DV_Name,
                        cell_number,
                        {
                            "red": debug_red,
                            "green": debug_green,
                            "blue": debug_blue,
                        },
                    )
                except Exception as exc:
                    if is_storage_full_error(exc):
                        return storage_full_response(exc)
                    raise

            # Save the updated fields to the DB
            cp.save()

        if cancelled():
            write_progress(uuids, "Cancelled")
            clear_cancelled(uuids)
            return cancel_response()

        cleanup_transient_processing_artifacts(
            uuid,
            remove_preview_assets=True,
        )

    # saving processing time
    duration = time.time() - start_time
    if request.user.is_authenticated:
        user = request.user
        user.processing_used += duration
        user.save()

    finalize_segmented_run_batch(
        request,
        uuid_list,
        auto_save_experiments=auto_save_experiments,
    )

    write_progress(uuids, "Completed")
    clear_cancelled(uuids)
    return redirect("display", uuids=uuids)
