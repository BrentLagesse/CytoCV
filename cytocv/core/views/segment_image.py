# =========================
# Standard library imports
# =========================
import csv
import importlib
import logging
import math
import os
import pkgutil
import sys
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
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone

# =========================
# Local application imports
# =========================
from cytocv.settings import BASE_DIR, MEDIA_ROOT, MEDIA_URL
from .utils import write_progress, is_cancelled, clear_cancelled
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
from core.cell_analysis import Analysis
from core.stats_plugins import build_requirement_summary

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

## progress helpers moved to core.views.utils

def _current_owner_filter(request) -> dict:
    """Return queryset filter args for the current upload owner."""

    if request.user.is_authenticated:
        return {"user": request.user}
    return {"user_id": get_guest_user()}


def set_options(opt):
    """
    This function sets global variables based on parsed arguments (like the old legacy code).
    """
    global input_dir, output_dir, ignore_btn, current_image, current_cell, outline_dict, image_dict, cp_dict, n
    input_dir = opt['input_dir']
    output_dir = opt['output_dir']
    kernel_size_input = opt['kernel_size']
    mcherry_line_width_input = opt['mCherry_line_width']
    kernel_deviation_input = opt['kernel_deviation']
    choice_var = opt['arrested']
    return kernel_size_input, mcherry_line_width_input, kernel_deviation_input, choice_var

def import_analyses(path:str, selected_analysis:list) -> list:
    """
    This function dynamically load the list of analyses from the path folder
    :param path: Path the analysis folder
    :return: List of the object of the analyses
    """
    analyses = []
    sys.path.append(str(path))
    print(path)

    modules = pkgutil.iter_modules(path=[path])
    for loader, mod_name, ispkg in modules:
        # Ensure that module isn't already loaded
        loaded_mod = None
        if mod_name not in sys.modules:
            # Import module
            loaded_mod = importlib.import_module('.cell_analysis','core')
        if loaded_mod is None: continue
        if mod_name != 'Analysis' and mod_name in selected_analysis:
            loaded_class = getattr(loaded_mod, mod_name)
            instanceOfClass = loaded_class()
            if isinstance(instanceOfClass, Analysis):
                print('Imported Plugin -- ' + mod_name)
                analyses.append(instanceOfClass)
            else:
                print
                mod_name + " was not an instance of Analysis"

    return analyses

def get_stats(cp, conf, selected_analysis, gfp_distance):
    # loading configuration
    kernel_size_input, mcherry_line_width_input, kernel_deviation_input, _ = set_options(conf)

    requirement_summary = build_requirement_summary(selected_analysis)
    stats_required_channels = {
        channel for channel in requirement_summary["required_channels"] if channel in {"mCherry", "GFP", "DAPI"}
    }
    # Always try to load all analysis channels if present so debug images remain available.
    channels_to_load = {"mCherry", "GFP", "DAPI", "DIC"} | stats_required_channels
    images = load_image(cp, output_dir, required_channels=channels_to_load)

    available_image_keys = [key for key in ("mCherry", "GFP", "DAPI", "DIC") if key in images]
    if not available_image_keys:
        blank = np.zeros((64, 64, 3), dtype=np.uint8)
        return Image.fromarray(blank), Image.fromarray(blank), Image.fromarray(blank)

    reference = images[available_image_keys[0]]

    def _canvas_for(channel_key: str) -> np.ndarray:
        base = images.get(channel_key, reference)
        return ensure_3channel_bgr(np.array(base, copy=True))

    edit_mCherry_img = _canvas_for("mCherry")
    edit_GFP_img = _canvas_for("GFP")
    edit_DAPI_img = _canvas_for("DAPI")

    if not selected_analysis:
        # No selected statistics: keep defaults and return plain debug frames.
        edit_testing_rgb = cv2.cvtColor(edit_mCherry_img, cv2.COLOR_BGR2RGB)
        edit_GFP_img_rgb = cv2.cvtColor(edit_GFP_img, cv2.COLOR_BGR2RGB)
        edit_DAPI_img_rgb = cv2.cvtColor(edit_DAPI_img, cv2.COLOR_BGR2RGB)
        return Image.fromarray(edit_testing_rgb), Image.fromarray(edit_GFP_img_rgb), Image.fromarray(edit_DAPI_img_rgb)

    preprocessed_images = preprocess_image_to_gray(images, kernel_deviation_input, kernel_size_input)
    contours_data = find_contours(preprocessed_images)

    best_contour_data = {}
    best_contour_dapi = None
    if contours_data.get("bestContours_dapi") and contours_data.get("contours_dapi"):
        best_index = contours_data["bestContours_dapi"][0]
        if len(contours_data["contours_dapi"]) > best_index:
            best_contour_dapi = contours_data["contours_dapi"][best_index]
            best_contour_data["DAPI"] = best_contour_dapi
            cp.blue_contour_size = cv2.contourArea(best_contour_dapi)
    else:
        cp.blue_contour_size = 0.0

    for i, contour in enumerate(contours_data.get("dot_contours", [])):
        area = cv2.contourArea(contour)
        setattr(cp, f"red_contour_{i+1}_size", area)

    if contours_data.get("dot_contours"):
        cv2.drawContours(edit_mCherry_img, contours_data["dot_contours"], -1, (0, 0, 255), 1)
        cv2.drawContours(edit_GFP_img, contours_data["dot_contours"], -1, (0, 0, 255), 1)
        cv2.drawContours(edit_DAPI_img, contours_data["dot_contours"], -1, (0, 0, 255), 1)

    if best_contour_dapi is not None:
        cv2.drawContours(edit_GFP_img, [best_contour_dapi], 0, (255, 0, 0), 1)
        cv2.drawContours(edit_DAPI_img, [best_contour_dapi], 0, (255, 0, 0), 1)

    if contours_data.get("contours_gfp"):
        cv2.drawContours(edit_mCherry_img, contours_data["contours_gfp"], -1, (0, 255, 0), 1)
        cv2.drawContours(edit_GFP_img, contours_data["contours_gfp"], -1, (0, 255, 0), 1)
        cv2.drawContours(edit_DAPI_img, contours_data["contours_gfp"], -1, (0, 255, 0), 1)

    import_path = BASE_DIR / 'core/cell_analysis'
    analyses = import_analyses(import_path, selected_analysis)
    dapi_contour_required_plugins = {"NucleusIntensity", "DAPI_NucleusIntensity"}
    for analysis in analyses:
        analysis_name = analysis.__class__.__name__
        if analysis_name in dapi_contour_required_plugins and "DAPI" not in best_contour_data:
            continue
        analysis.setting_up(cp, preprocessed_images, output_dir)
        analysis.calculate_statistics(
            best_contour_data,
            contours_data,
            edit_mCherry_img,
            edit_GFP_img,
            mcherry_line_width_input,
            gfp_distance,
        )

    # Convert BGR back to RGB so PIL shows correct colors
    edit_testing_rgb = cv2.cvtColor(edit_mCherry_img, cv2.COLOR_BGR2RGB)
    edit_GFP_img_rgb = cv2.cvtColor(edit_GFP_img, cv2.COLOR_BGR2RGB)
    edit_DAPI_img_rgb = cv2.cvtColor(edit_DAPI_img, cv2.COLOR_BGR2RGB)

    return Image.fromarray(edit_testing_rgb), Image.fromarray(edit_GFP_img_rgb), Image.fromarray(edit_DAPI_img_rgb)

'''Get file size of a directory recursively'''
def get_dir_size(path):
    """
    Calculate the size of a directory recursively
    """
    total = 0
    with os.scandir(path) as it:
        for entry in it:
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    return total

'''Creates image "segments" from the desired image'''
def segment_image(request, uuids):
    """
    Handles segmentation cell_analysis for multiple images passed as UUIDs.
    """
    uuid_list = uuids.split(',')
    owner_filter = _current_owner_filter(request)
    cancelled = lambda: is_cancelled(uuids)

    if cancelled():
        write_progress(uuids, "Cancelled")
        clear_cancelled(uuids)
        return HttpResponse("Cancelled")

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
            return HttpResponse("Cancelled")
        uploaded_image = get_object_or_404(UploadedImage, pk=uuid, **owner_filter)
        DV_Name = uploaded_image.name
        image_dict = dict()
        image_dict[DV_Name] = list()

        # Need to grab the original DV file
        # Load the original raw image and rescale its intensity values
        DV_path = str(Path(MEDIA_ROOT)) + '/' + str(uuid) + '/' + DV_Name + '.dv'
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

                # open the mcherry
                #TODO: open mcherry from dv stack

                # basename = image_name.split('_R3D_REF')[0]
                # mcherry_dir = input_dir + basename + '_PRJ_TIFFS/'
                # mcherry_image_name = basename + '_PRJ' + '_w625' + '.tif'
                # mcherry_image = np.array(Image.open(mcherry_dir + mcherry_image_name))

                # Which file are we trying to find here?
                f = DVFile(DV_path)
                try:
                    channel_config = get_channel_config_for_uuid(uuid)
                    mcherry_index = channel_config.get("mCherry")
                    mcherry_image = f.asarray()[mcherry_index]
                finally:
                    f.close()

                # mcherry_image = skimage.exposure.rescale_intensity(mcherry_np.float32(image), out_range=(0, 1))
                mcherry_image = np.round(mcherry_image * 255).astype(np.uint8)

                # Convert the image to an RGB image, if necessary
                if len(mcherry_image.shape) == 3 and mcherry_image.shape[2] == 3:
                    pass
                else:
                    mcherry_image = np.expand_dims(mcherry_image, axis=-1)
                    mcherry_image = np.tile(mcherry_image, 3)
                # find contours
                mcherry_image_gray = cv2.cvtColor(mcherry_image, cv2.COLOR_RGB2GRAY)
                mcherry_image_gray, background = subtract_background_rolling_ball(mcherry_image_gray, 50,
                                                                                    light_background=False,
                                                                                    use_paraboloid=False,
                                                                                    do_presmooth=True)

                debug = False
                if debug:
                    plt.figure(dpi=600)
                    plt.title("mcherry")
                    plt.imshow(mcherry_image_gray, cmap='gray')
                    plt.show()

                #mcherry_image_gray = cv2.GaussianBlur(mcherry_image_gray, (1, 1), 0)
                mcherry_image_ret, mcherry_image_thresh = cv2.threshold(mcherry_image_gray, 0, 1, cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU)
                mcherry_image_cont, mcherry_image_h = cv2.findContours(mcherry_image_thresh, 1, 2)

                if debug:
                    cv2.drawContours(image, mcherry_image_cont, -1, 255, 1)
                    plt.figure(dpi=600)
                    plt.title("ref image with contours")
                    plt.imshow(image, cmap='gray')
                    plt.show()


                #921,800

                min_mcherry_distance = dict()
                min_mcherry_loc = dict()   # maps an mcherry dot to its closest mcherry dot in terms of cell id
                for cnt1 in mcherry_image_cont:
                    try:
                        contourArea = cv2.contourArea(cnt1)
                        if contourArea > 100000:   #test for the big box, TODO: fix this to be adaptive
                            print('threw out the bounding box for the entire image')
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
                    for cnt2 in mcherry_image_cont:
                        try:
                            coordinate = get_contour_center(cnt2)
                            # find center of each contour
                            c2y = coordinate[0][0]
                            c2x = coordinate[0][1]

                        except:
                            continue #no moment found
                        if int(seg[c2x][c2y]) == 0:
                            continue
                        if seg[c1x][c1y] == seg[c2x][c2y]:   #these are ihe same cell already -- Maybe this is ok?  TODO:  Figure out hwo to handle this because some of the mcherry signals are in the same cell
                            continue
                        # find the closest point to each center
                        d = math.sqrt(pow(c1x - c2x, 2) + pow(c1y - c2y, 2))
                        if min_mcherry_distance.get(c_id) == None:
                            min_mcherry_distance[c_id] = d
                            min_mcherry_loc[c_id] = int(seg[c2x][c2y])
                            lines_to_draw[c_id] = ((c1y,c1x), (c2y, c2x))
                        else:
                            if d < min_mcherry_distance[c_id]:
                                min_mcherry_distance[c_id] = d
                                min_mcherry_loc[c_id] = int(seg[c2x][c2y])
                                lines_to_draw[c_id] = ((c1y, c1x), (c2y, c2x))  #flip it back here
                            elif d == min_mcherry_distance[c_id]:
                                print('This is unexpected, we had two mcherry red dots in cells {} and {} at the same distance from ('.format(seg[c1x][c1y], seg[c2x][c2y]) + str(min_mcherry_loc[c_id]) + ', ' + str((c2x, c2y)) + ') to ' + str((c1x, c1y)) + ' at a distance of ' + str(d))

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
                            if int(v) in min_mcherry_loc:    #if we merge them here, we don't need to do it with mcherry
                                del min_mcherry_loc[int(v)]
                            if int(k) in min_mcherry_loc:
                                del min_mcherry_loc[int(k)]
                        for update in zip(to_update[0], to_update[1]):
                            seg[update[0]][update[1]] = k

                    elif int(k) not in ignore_list and not resolve_cells_using_spc110:
                        single_cell_list.append(int(k))


                elif int(k) not in ignore_list and not resolve_cells_using_spc110:
                    single_cell_list.append(int(k))

            if resolve_cells_using_spc110:
                for c_id, nearest_cid in min_mcherry_loc.items():
                    if int(c_id) in ignore_list:    # if we have already paired this one, ignore it
                        continue
                    if int(nearest_cid) in min_mcherry_loc:  #make sure teh reciprocal exists
                        if min_mcherry_loc[int(nearest_cid)] == int(c_id) and int(c_id) not in ignore_list:   # if it is mutual
                            #print('added a cell pair in image {} using the mcherry technique {} and {}'.format(image_name, int(nearest_cid),
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
                            print('could not add cell pair because cell {} and cell {} were not mutually closest'.format(nearest_cid, int(v)))
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
            seg_image.save(str(outputdirectory) + "\\cellpairs.tif")
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
                tmp = tmp - skimage.morphology.binary_erosion(tmp)
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

            # debugging to see where the mcherry signals connect
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
                    print('could not find cell id ' + str(i))

            output_file = os.path.join(outputdirectory, f"{DV_Name}_frame_{frame_idx}.png")
            fig.savefig(output_file, dpi=600, bbox_inches='tight', pad_inches=0)
            plt.close(fig)

        #plt.show()

        #TODO:  Combine the two iterations over the input directory images

        # This is where we overlay what we learned in the DIC onto the other images
        
        #filter_dir = input_dir  + base_image_name + '_PRJ_TIFFS/'
        segmented_directory = Path(MEDIA_ROOT) / str(uuid) / 'segmented'
        # Ensure directory exists
        segmented_directory.mkdir(parents=True, exist_ok=True)

        # Iterate over the segmented cells
        for cell_number in range(1, int(np.max(seg)) + 1):
            cell_image = np.zeros_like(seg)
            cell_image[seg == cell_number] = 255  # Mark cell areas

            # File paths
            cell_image_path = segmented_directory / f"cell_{cell_number}.png"

            # Save each cell image as PNG
            Image.fromarray(cell_image.astype(np.uint8)).save(cell_image_path)
        
        os.makedirs(segmented_directory, exist_ok=True)
        f = DVFile(DV_path)
        try:
            image_stack = f.asarray()
        finally:
            f.close()

        if image_stack.ndim == 2:
            image_stack = np.expand_dims(image_stack, axis=0)

        for image_num in range(image_stack.shape[0]):
            if cancelled():
                write_progress(uuids, "Cancelled")
                clear_cancelled(uuids)
                return HttpResponse("Cancelled")
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

            outlines = np.zeros(seg.shape)
            # Iterate over each integer in the segmentation and save the outline of each cell onto the outline file
            for i in range(1, int(np.max(seg) + 1)):
                tmp = np.zeros(seg.shape)
                tmp[np.where(seg == i)] = 1
                tmp = tmp - skimage.morphology.binary_erosion(tmp)
                outlines += tmp
            
            # Overlay the outlines on the original image in green
            image_outlined = image.copy()
            # image_outlined[outlines > 0] = (0, 255, 0)
            # NOTE: Temporarily changing to cyan to debug GFP
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
                    with open(str(outputdirectory) + DV_Name + '-' + str(i) + '.outline', 'w') as csvfile:
                        csvwriter = csv.writer(csvfile, lineterminator='\n')
                        csvwriter.writerows(zip(a[0] - min_x, a[1] - min_y))

                cellpair_image = image_outlined[min_x: max_x, min_y:max_y]
                not_outlined_image = image[min_x: max_x, min_y:max_y]
                if not os.path.exists(segmented_directory / cell_tif_image) or not use_cache:  # don't redo things we already have
                    plt.imsave(segmented_directory / cell_tif_image, cellpair_image, dpi=600, format='PNG')
                    plt.clf()
                if not os.path.exists(segmented_directory / no_outline_image) or not use_cache:  # don't redo things we already have
                    plt.imsave(segmented_directory / no_outline_image, not_outlined_image, dpi=600, format='PNG')
                    plt.clf()

            # Assign SegmentedImage to a user
            num_cells = max(int(np.max(seg)), 0)
            if request.user.is_authenticated:
                user = request.user
                instance = SegmentedImage(UUID = uuid, user=user,
                                        ImagePath = (MEDIA_URL  + str(uuid) + '/output/' + DV_Name + '.png'),
                                        CellPairPrefix=(MEDIA_URL + str(uuid) + '/segmented/cell_'),
                                        NumCells = num_cells,
                                        uploaded_date=timezone.now())
            else:
                # this would save to a guest user for now
                instance = SegmentedImage(UUID=uuid,
                                          ImagePath=(MEDIA_URL + str(uuid) + '/output/' + DV_Name + '.png'),
                                          CellPairPrefix=(MEDIA_URL + str(uuid) + '/segmented/cell_'),
                                          NumCells=num_cells,
                                          uploaded_date=timezone.now())
            instance.save()

        # ================================================
        # Calculate statistics for each cell only once after the loop
        # ================================================

        configuration = DEFAULT_PROCESS_CONFIG
        if request.user.is_authenticated:
            configuration = request.user.config
        else:
            configuration = settings.DEFAULT_SEGMENT_CONFIG

        selected_analysis = request.session.get('selected_analysis', [])
        # Build a proper 'conf' dict with required keys for get_stats
        conf = {
            'input_dir': input_dir,
            'output_dir': os.path.join(str(settings.MEDIA_ROOT), str(uuid)),
            'kernel_size': configuration["kernel_size"],
            'mCherry_line_width': configuration["mCherry_line_width"],
            'kernel_deviation': configuration["kernel_deviation"],
            'arrested': configuration["arrested"],
            'analysis' : selected_analysis,
        }

        if cancelled():
            write_progress(uuids, "Cancelled")
            clear_cancelled(uuids)
            return HttpResponse("Cancelled")

        # Mark accurate phase for UI only if user selected analyses
        if selected_analysis:
            write_progress(uuids, "Calculating Statistics")

        # For each cell_number in the segmentation, create/fetch a CellStatistics object
        # and call get_stats so it can mutate the fields on cp.
        for cell_number in range(1, int(np.max(seg)) + 1):
            print(f"Calculating statistics for cell {cell_number} in image {DV_Name} (UUID: {uuid})")

            # Create or get a CellStatistics row
            cp, created = CellStatistics.objects.get_or_create(
                segmented_image=instance,
                cell_id=cell_number,
                defaults={
                    # Cell statistics numerical defaults
                    'distance': 0.0,
                    'line_gfp_intensity': 0.0,
                    'nucleus_intensity_sum': 0.0,
                    'cellular_intensity_sum': 0.0,
                    'green_red_intensity_1': 0.0,
                    'green_red_intensity_2': 0.0,
                    'green_red_intensity_3': 0.0,

                    # Store file path information
                    'dv_file_path': DV_path,
                    'image_name': DV_Name + '.dv',
                }
            )

            # Now pass the real model object + conf to get_stats
            # This modifies cp's fields in place
            selected_analysis = request.session.get('selected_analysis',[])
            gfp_distance = request.session.get('distance', 37)
            try:
                gfp_distance = int(gfp_distance)
            except ValueError:
                gfp_distance = 37
            # Call get_stats to do the real work
            debug_mcherry, debug_gfp, debug_dapi = get_stats(cp, conf,selected_analysis, gfp_distance)

            # Save the debug images so we can view them later
            debug_mcherry_path = segmented_directory / f"{DV_Name}-{cell_number}-mCherry_debug.png"
            debug_gfp_path = segmented_directory / f"{DV_Name}-{cell_number}-GFP_debug.png"
            debug_dapi_path = segmented_directory / f"{DV_Name}-{cell_number}-DAPI_debug.png"

            debug_mcherry.save(debug_mcherry_path)
            debug_gfp.save(debug_gfp_path)
            debug_dapi.save(debug_dapi_path)

            # Save the updated fields to the DB
            cp.save()

        if cancelled():
            write_progress(uuids, "Cancelled")
            clear_cancelled(uuids)
            return HttpResponse("Cancelled")

        # if the image_dict is empty, then we didn't get anything interesting from the directory
        #print("image_dict123", image_dict)
        #if len(image_dict) > 0:
        #    k, v = list(image_dict.items())[0]
        #    print("displaycell",k,v[0])
        #    display_cell(k, v[0])
        #else: show error message'''

        # calculate storage size for this uuid
        if request.user.is_authenticated:
            stored_path = Path(str(MEDIA_ROOT), str(uuid))
            storing_size = get_dir_size(stored_path)
            user = request.user
            user.available_storage -= storing_size
            user.used_storage += storing_size
            user.save()

    # saving processing time
    duration = time.time() - start_time
    if request.user.is_authenticated:
        user = request.user
        user.processing_used += duration
        user.save()


    write_progress(uuids, "Completed")
    clear_cancelled(uuids)
    return redirect(f'/image/{uuids}/display/')
