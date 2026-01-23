import numpy as np
from PIL import Image
import os
import skimage.exposure
import skimage.filters
from mrc import DVFile
from yeastweb.settings import MEDIA_ROOT
from core.models import UploadedImage
from pathlib import Path
from core.views.variables import PRE_PROCESS_FOLDER_NAME
#Original header
# def preprocess_images(inputdirectory, mask_dir, outputdirectory, outputfile, verbose = False, use_cache=True):
def preprocess_images(
    uuid,
    uploaded_image: UploadedImage,
    output_dir: Path,
    cancel_check=None,
) -> tuple[str, str]:
    """
        Most commented lines are from the old code base. Have kept until we have the entire product working
    """
    if cancel_check and cancel_check():
        return None, None

    # constants, easily can be changed 
    print("output_directory", output_dir)

    # Creates csv file and writes in first 2 columns ImageId and EncodedRLE for each image
    CSV_NAME = 'preprocessed_images_list.csv'
    preprocessed_image_list_path = Path(output_dir, CSV_NAME)
    preprocessed_image_list = open(preprocessed_image_list_path, "w")
    preprocessed_image_list.write("ImageId, EncodedRLE" + "\n")
    preprocessed_image_list.close()
    
    #converts windows file path to linux path and joins 
    image_path = Path(MEDIA_ROOT, str(uploaded_image.file_location)) #.replace("/", "\\")
    f = DVFile(image_path)
    # gets raw image from uploaded dv file
    image = f.asarray()[3]
    # fileSize = os.path.getsize(uploaded_image.file_location)
    # if fileSize > 8230000:
        #File is a live cell imaging that has more than 4 images
    #     f = DVFile(uploaded_image)
    #     image = f.asarray()[0]
    # if extspl[1] == '.dv':
    #     f = DVFile(uploaded_image)
    #     image = f.asarray()[0]
        #if we don't have .dv files, see if there are tifs in the directory with the proper name structure

        # elif len(extspl) != 2 or extspl[1] != '.tif':  # ignore files that aren't tifs
        #     continue
        # else:
        #     image = np.array(Image.open(inputdirectory + imagename))
    # try:
        # if verbose:
        # print ("Preprocessing ", imagename)
        # existing_files = os.listdir(mask_dir)
        # if imagename in existing_files and use_cache:   #skip this if we have a mask already
            # continue
    # outputdirectory = imagePath
    # grabs only file name
 
    if len(image.shape) > 2:
        image = image[:, :, 0]
    height = image.shape[0]
    width = image.shape[1]

    # Preprocessing operations
    image = skimage.exposure.rescale_intensity(np.float32(image), out_range=(0, 1))
    image = np.round(image * 255).astype(np.uint8)        #convert to 8 bit
    image = np.expand_dims(image, axis=-1)
    rgb_image = np.tile(image, 3)                          #convert to RGB
    #rgbimage = skimage.filters.gaussian(rgbimage, sigma=(1,1))   # blur it first?

    # if not os.path.exists(outputdirectory + imagename) or not use_cache:
    # if not os.path.exists(outputdirectory + imagename):
    # os.makedirs(outputdirectory + imagename)
    # os.makedirs(outputdirectory + imagename + "/images/")
    rgb_image = Image.fromarray(rgb_image)
    # pre_process_dir_path = os.path.join(output_directory, PRE_PROCESS_FOLDER_NAME)
    pre_process_dir_path = Path(output_dir / PRE_PROCESS_FOLDER_NAME)
    # makes dir if it already doesn't exist
    pre_process_dir_path.mkdir(parents=True, exist_ok=True)
    # if not pre_process_dir_path.is_dir():
    # os.makedirs(pre_process_dir_path)
    if cancel_check and cancel_check():
        return None, None

    image_name = uploaded_image.name.split(".")[0] + ".tif"
    pre_process_image_path = os.path.join(pre_process_dir_path, image_name)
    rgb_image.save(pre_process_image_path)
    
    preprocessed_image_list = open(preprocessed_image_list_path, "a")
    preprocessed_image_list.write(uploaded_image.name + ", " + str(height) + " " + str(width) + "\n")
    preprocessed_image_list.close()
    print('Pre-process completed FINISHED')
    return pre_process_image_path, preprocessed_image_list_path
    # except IOError:
    #     pass
