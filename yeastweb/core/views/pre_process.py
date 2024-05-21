from django.shortcuts import  get_object_or_404, render
from django.http import HttpResponse
from core.models import UploadedImage 
# from ..models import Image 
from django.template.response import TemplateResponse
# Create your views here.
# chose function because https://spookylukey.github.io/django-views-the-right-way/context-data.html
def pre_process(request, uuid):
    image = get_object_or_404(UploadedImage, uuid=uuid)
    if request.method == "POST":
        preprocess_images(uuid, image)
        # form = UploadImageForm(request.POST, request.FILES)
        return HttpResponse("Preprocess completed")
    else:
        print("testing", uuid)
        print(image.file_location)
        # context = {'image' :}
        return TemplateResponse(request, "pre-process.html", {'image' : image})
# class HomePageView(ListView) :
#     model = Test
#     template_name = "home.html"


import numpy as np
from PIL import Image
import os
import skimage.exposure
import skimage.filters
from mrc import DVFile
from yeastweb.settings import MEDIA_ROOT
# def preprocess_images(inputdirectory, mask_dir, outputdirectory, outputfile, verbose = False, use_cache=True):
def preprocess_images(uuid, uploaded_image : UploadedImage):
    # constants, easily can be changed 
    PRE_PROCESS_FOLDER_NAME = "preprocessed_images"
    CSV_NAME = 'preprocessed_images_list.csv'
    
    #converts windows file path to linux path 
    output_directory = os.path.join(MEDIA_ROOT, str(uuid))
    csv_path = os.path.join(output_directory, CSV_NAME)
    print("output_directory", output_directory)

    # Creates csv file and writes in first 2 columns ImageId and EncodedRLE
    csv = open(csv_path, "w")
    csv.write("ImageId, EncodedRLE" + "\n")
    csv.close()
    
    #converts windows file path to linux path and joins 
    image_path = os.path.join(MEDIA_ROOT, str(uploaded_image.file_location).replace("/", "\\"))
    f = DVFile(image_path)
    # gets raw image from uploaded dv file
    image = f.asarray()[0]
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
    pre_process_folder_path = os.path.join(output_directory, PRE_PROCESS_FOLDER_NAME)
    os.makedirs(pre_process_folder_path)
    image_name = uploaded_image.name.split(".")[0] + ".tif"
    rgb_image.save(os.path.join(pre_process_folder_path, image_name))
    
    # output = open(outputfile, "a")
    # output.write(imagename + ", " + str(height) + " " + str(width) + "\n")
    # output.close()
    print('Pre-process completed FINISHED')
    # except IOError:
    #     pass

