import matplotlib.patheffects as PathEffects
import matplotlib.pyplot as plt
import numpy as np
import os, csv, math, cv2, skimage, logging, time

from skimage import io
from django.conf import settings

from core.models import UploadedImage, SegmentedImage, CellStatistics, Contour
from core.config import input_dir, output_dir
from cv2_rolling_ball import subtract_background_rolling_ball
from django.http import HttpResponse
from django.shortcuts import redirect
from mrc import DVFile
from pathlib import Path
from PIL import Image
from yeastweb.settings import MEDIA_ROOT, MEDIA_URL

from scipy.spatial.distance import euclidean  
from collections import defaultdict

from scipy.spatial.distance import euclidean
from cv2_rolling_ball import subtract_background_rolling_ball

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

def set_options(opt):
    """
    This function sets global variables based on parsed arguments (like the old legacy code).
    """
    global input_dir, output_dir, ignore_btn, current_image, current_cell, outline_dict, image_dict, cp_dict, n
    input_dir = opt.input_directory
    output_dir = opt.output_directory

def get_stats(cp, conf):
    data = conf
    print(data)
    global input_dir 
    input_dir = data['input_dir']
    global output_dir 
    output_dir = data['output_dir']
    kernel_size_input = data['kernel_size']
    mcherry_line_width_input = data['mCherry_line_width']
    kernel_deviation_input = data['kernel_diviation']
    choice_var = data['arrested']
    
    # outlines screw up the analysis
    print("test123", 'segmented/' + cp.get_mCherry(use_id=True, outline=False))
    im = Image.open(output_dir + '/segmented/' + cp.get_mCherry(use_id=True, outline=False))
    im_GFP = Image.open(output_dir + '/segmented/' + cp.get_GFP(use_id=True, outline=False))
    im_GFP_for_cellular_intensity = Image.open(output_dir + '/segmented/' + cp.get_GFP(use_id=True))  # has outline
    testimg = np.array(im)
    GFP_img = np.array(im_GFP)
    img_for_cell_intensity = np.array(im_GFP_for_cellular_intensity)

    cell_intensity_gray = cv2.cvtColor(img_for_cell_intensity, cv2.COLOR_RGB2GRAY)

    # was RGBA2GRAY
    orig_gray_GFP = cv2.cvtColor(GFP_img, cv2.COLOR_RGB2GRAY)
    orig_gray_GFP_no_bg, background = subtract_background_rolling_ball(orig_gray_GFP, 50, light_background=False,
                                                                       use_paraboloid=False, do_presmooth=True)
    orig_gray = cv2.cvtColor(testimg, cv2.COLOR_RGB2GRAY)
    kdev = int(kernel_deviation_input)
    ksize = int(kernel_size_input)
    # ksize must be odd
    if ksize % 2 == 0:
        ksize += 1
        print("You used an even ksize, updating to odd number +1")

    gray_mcherry = cv2.GaussianBlur(orig_gray, (3,3), 1)
    ret_mcherry, thresh_mcherry = cv2.threshold(gray_mcherry, 0, 1,
                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU)
    gray = cv2.GaussianBlur(orig_gray, (ksize, ksize), kdev)
    ret, thresh = cv2.threshold(gray, 0, 1,
                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU)

    # Some of the cell outlines are split into two circles. Blur so that the contour covers both
    cell_intensity_gray = cv2.GaussianBlur(cell_intensity_gray, (3,3), 1)
    cell_int_ret, cell_int_thresh = cv2.threshold(cell_intensity_gray, 0, 1,
                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C | cv2.THRESH_OTSU)
    cell_int_cont, cell_int_h = cv2.findContours(cell_int_thresh, 1, 2)

    # Biggest contour for the cellular intensity boundary
    largest = 0
    largest_cell_cnt = None
    # TODO: In the future, handle multiple large contours more robustly
    for i, cnt in enumerate(cell_int_cont):
        area = cv2.contourArea(cnt)
        if area > largest:
            largest = area
            largest_cell_cnt = cnt

    contours, h = cv2.findContours(thresh, 1, 2)
    contours_mcherry = cv2.findContours(thresh_mcherry, 1, 2)

    # Identify the two largest contours in each set
    bestContours = []
    bestArea = []
    for i, cnt in enumerate(contours):
        if len(cnt) == 0:
            continue
        if i == len(contours) - 1:  # not robust #TODO fix it
            continue
        area = cv2.contourArea(cnt)
        if len(bestContours) == 0:
            bestContours.append(i)
            bestArea.append(area)
            continue
        if len(bestContours) == 1:
            bestContours.append(i)
            bestArea.append(area)

        if area > bestArea[0]:
            bestArea[1] = bestArea[0]
            bestArea[0] = area
            bestContours[1] = bestContours[0]
            bestContours[0] = i
        elif area > bestArea[1]:
            bestArea[1] = area
            bestContours[1] = i

    if len(bestContours) == 0:
        print("we didn't find any contours")
        return im, im_GFP  # returns original images if no contours found

    bestContours_mcherry = []
    bestArea_mcherry = []
    for i, cnt in enumerate(contours_mcherry[0]):
        if len(cnt) == 0:
            continue
        if i == len(contours_mcherry[0]) - 1:  # not robust #TODO fix it
            continue
        try:
            area = cv2.contourArea(cnt)
        except:
            continue

        if len(bestContours_mcherry) == 0:
            bestContours_mcherry.append(i)
            bestArea_mcherry.append(area)
            continue
        if len(bestContours_mcherry) == 1:
            bestContours_mcherry.append(i)
            bestArea_mcherry.append(area)

        if area > bestArea_mcherry[0]:
            bestArea_mcherry[1] = bestArea_mcherry[0]
            bestArea_mcherry[0] = area
            bestContours_mcherry[1] = bestContours_mcherry[0]
            bestContours_mcherry[0] = i
        elif area > bestArea_mcherry[1]:
            bestArea_mcherry[1] = area
            bestContours_mcherry[1] = i

    edit_im = Image.open(output_dir + '/segmented/' + cp.get_mCherry(use_id=True))
    edit_im_GFP = Image.open(output_dir + '/segmented/' + cp.get_GFP(use_id=True))
    edit_testimg = np.array(edit_im)
    edit_GFP_img = np.array(edit_im_GFP)

    mcherry_line_pts = []
    if len(bestContours_mcherry) == 2:
        c1 = contours_mcherry[0][bestContours_mcherry[0]]
        c2 = contours_mcherry[0][bestContours_mcherry[1]]
        M1 = cv2.moments(c1)
        M2 = cv2.moments(c2)

        if M1['m00'] == 0 or M2['m00'] == 0:
            print("Warning:  The m00 moment = 0")
        else:
            c1x = int(M1['m10'] / M1['m00'])
            c1y = int(M1['m01'] / M1['m00'])
            c2x = int(M2['m10'] / M2['m00'])
            c2y = int(M2['m01'] / M2['m00'])
            d = math.sqrt((c1x - c2x)**2 + (c1y - c2y)**2)

            # Directly assign to cp.red_dot_distance (instead of cp.set_red_dot_distance(d))
            cp.red_dot_distance = d

            cv2.line(edit_testimg, (c1x, c1y), (c2x, c2y), 255, int(mcherry_line_width_input))
            mcherry_line_mask = np.zeros(gray.shape, np.uint8)
            cv2.line(mcherry_line_mask, (c1x, c1y), (c2x, c2y), 255, int(mcherry_line_width_input))
            mcherry_line_pts = np.transpose(np.nonzero(mcherry_line_mask))

    best_contour = None
    if len(bestContours) == 2:
        c1 = contours[bestContours[0]]
        c2 = contours[bestContours[1]]
        MERGE_CLOSEST = True
        if MERGE_CLOSEST:
            smallest_distance = 999999999
            second_smallest_distance = 999999999
            smallest_pair = (-1, -1)

            for pt1 in c1:
                for i, pt2 in enumerate(c2):
                    d = math.sqrt((pt1[0][0] - pt2[0][0])**2 + (pt1[0][1] - pt2[0][1])**2)
                    if d < smallest_distance:
                        second_smallest_distance = smallest_distance
                        second_smallest_pair = smallest_pair
                        smallest_distance = d
                        smallest_pair = (pt1, pt2, i)
                    elif d < second_smallest_distance:
                        second_smallest_distance = d
                        second_smallest_pair = (pt1, pt2, i)

            # Merge c2 into c1 at the closest points
            best_contour = []
            for pt1 in c1:
                best_contour.append(pt1)
                if pt1[0].tolist() != smallest_pair[0][0].tolist():
                    continue
                # we are at the closest p1
                start_loc = smallest_pair[2]
                finish_loc = start_loc - 1
                if start_loc == 0:
                    finish_loc = len(c2) - 1
                current_loc = start_loc
                while current_loc != finish_loc:
                    best_contour.append(c2[current_loc])
                    current_loc += 1
                    if current_loc >= len(c2):
                        current_loc = 0
                best_contour.append(c2[finish_loc])

            best_contour = np.array(best_contour).reshape((-1, 1, 2)).astype(np.int32)

    if len(bestContours) == 1:
        best_contour = contours[bestContours[0]]

    print("only 1 contour found")
    cv2.drawContours(edit_testimg, [best_contour], 0, (0, 255, 0), 1)
    cv2.drawContours(edit_GFP_img, [best_contour], 0, (0, 255, 0), 1)

    mask_contour = np.zeros(gray.shape, np.uint8)
    cv2.fillPoly(mask_contour, [best_contour], 255)
    pts_contour = np.transpose(np.nonzero(mask_contour))

    border_cells = []
    with open(output_dir + '/masks/' + cp.get_base_name() + '-' + str(cp.cell_id) + '.outline', 'r') as csvfile:
        csvreader = csv.reader(csvfile)
        for row in csvreader:
            border_cells.append([int(row[0]), int(row[1])])

    # Calculate nucleus intensity inside the best_contour
    intensity_sum = 0
    for p in pts_contour:
        intensity_sum += orig_gray_GFP_no_bg[p[0]][p[1]]

    cp.nucleus_intensity[Contour.CONTOUR.name] = intensity_sum
    cp.nucleus_total_points = len(pts_contour)

    # Calculate cell intensity from the "border_cells" list
    cell_intensity_sum = 0
    for p in border_cells:
        cell_intensity_sum += orig_gray_GFP_no_bg[p[0]][p[1]]

    cp.cell_intensity = cell_intensity_sum  # or store as dict
    cp.cell_total_points = len(border_cells)

    # Calculate mCherry line intensity
    mcherry_line_intensity_sum = 0
    for p in mcherry_line_pts:
        mcherry_line_intensity_sum += orig_gray_GFP_no_bg[p[0]][p[1]]

    cp.mcherry_line_gfp_intensity = mcherry_line_intensity_sum

    return Image.fromarray(edit_testimg), Image.fromarray(edit_GFP_img)


def get_neighbor_count(seg_image, center, radius=1, loss=0):
    #TODO:  account for loss as distance gets larger
    neighbor_list = list()
    neighbors = seg_image[center[0] - radius:center[0] + radius + 1, center[1] - radius:center[1] + radius + 1]
    for x, row in enumerate(neighbors):
        for y, val in enumerate(row):
            if (x, y) != (radius, radius) and int(val) != 0 and int(val) != int(seg_image[center[0], center[1]]):
                neighbor_list.append(val)
    return neighbor_list

'''Creates image "segments" from the desired image'''
def segment_image(request, uuids):
    """
    Handles segmentation analysis for multiple images passed as UUIDs.
    """
    uuid_list = uuids.split(',')

    # Initialize some variables that would normally be a part of config
    choice_var = "Metaphase Arrested" # We need to be able to change this
    seg = None
    use_cache = True

    # Configuations for statistic calculation
    kernel_size = 3
    deviation = 1
    mcherry_line_width = 1

    # We're gonna use image_dict to store all of the cell pairs (i think?)
    for uuid in uuid_list:
        DV_Name = UploadedImage.objects.get(pk=uuid).name
        image_dict = dict()
        image_dict[DV_Name] = list()

        # Need to grab the original DV file
        # Load the original raw image and rescale its intensity values
        DV_path = str(Path(MEDIA_ROOT)) + '/' + str(uuid) + '/' + DV_Name + '.dv'
        f = DVFile(DV_path)
        im = f.asarray()

        gfp_channel = im[0] # subject to change 
        nucleus_channel = im[0] # subject to change 

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

        # Open the segmentation file (the mask generated in convert_to_image)    # TODO -- make it show it is choosing the correct segmented
        seg = np.array(Image.open(Path(MEDIA_ROOT) / str(uuid) / "output" / "mask.tif"))   #TODO:  on first run, this can't find outputs/masks/M***.tif'

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
                        neighbor_list = get_neighbor_count(seg, cell, 3)
                    except:
                        continue

                    for neighbor in neighbor_list:
                        if int(neighbor) == i or int(neighbor) == 0:
                            continue
                        if neighbor in neighbor_count:
                            neighbor_count[neighbor] += 1
                        else:
                            neighbor_count[neighbor] = 1

                sorted_dict = {k: v for k, v in sorted(neighbor_count.items(), key=lambda item: item[1])}
                if len(sorted_dict) == 0:
                    print('found single cell at: ' + str(cell))
                    single_cell_list.append(int(i))
                else:
                    if len(sorted_dict) == 1:
                        closest_neighbors[i] = list(sorted_dict.items())[0][0]
                    else:
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
            resolve_cells_using_spc110 = True # Hard coding this for now but will have to use a config file in the future
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
                mcherry_image = f.asarray()[3]

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
                        M1 = cv2.moments(cnt1)
                        # These are opposite of what we would expect
                        c1y = int(M1['m10'] / M1['m00'])
                        c1x = int(M1['m01'] / M1['m00'])


                    except:  #no moment found
                        continue
                    c_id = int(seg[c1x][c1y])
                    if c_id == 0:
                        continue
                    for cnt2 in mcherry_image_cont:
                        try:
                            M2 = cv2.moments(cnt2)
                            # find center of each contour
                            c2y = int(M2['m10'] / M2['m00'])
                            c2x = int(M2['m01'] / M2['m00'])

                            

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
        im = f.asarray()
        image = Image.fromarray(im[0])
        image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1))
        image = np.round(image * 255).astype(np.uint8)

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
        image_outlined[outlines > 0] = (0, 255, 0)

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

        fig.savefig(str(outputdirectory) + DV_Name, dpi=600, bbox_inches='tight', pad_inches=0)

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
        for image_num in range(4):
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
            image = np.array(f.asarray()[image_num])
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
            image_outlined[outlines > 0] = (0, 255, 0)

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

            instance = SegmentedImage(UUID = uuid, 
                                    ImagePath = (MEDIA_URL  + str(uuid) + '/output/' + DV_Name + '.png'), 
                                    CellPairPrefix=(MEDIA_URL + str(uuid) + '/segmented/cell_'),
                                    NumCells = int(np.max(seg) + 1))
            instance.save()

        # ================================================
        # Calculate statistics for each cell only once after the loop
        # ================================================
        
        # Build a proper 'conf' dict with required keys for get_stats
        conf = {
            'input_dir': input_dir,
            'output_dir': os.path.join(str(settings.MEDIA_ROOT), str(uuid)),
            'kernel_size': kernel_size,      
            'mCherry_line_width': mcherry_line_width,  
            'kernel_diviation': deviation,       
            'arrested': choice_var               
        }

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

                    # Store file path information
                    'dv_file_path': DV_path,
                    'image_name': DV_Name + '.dv',
                }
            )

            # Now pass the real model object + conf to get_stats
            # This modifies cp's fields in place
            get_stats(cp, conf)

            # Save the updated fields to the DB
            cp.save()

        # if the image_dict is empty, then we didn't get anything interesting from the directory
        #print("image_dict123", image_dict)
        #if len(image_dict) > 0:
        #    k, v = list(image_dict.items())[0]
        #    print("displaycell",k,v[0])
        #    display_cell(k, v[0])
        #else: show error message'''

    return redirect(f'/image/{uuids}/display/')
    return HttpResponse("Congrats")