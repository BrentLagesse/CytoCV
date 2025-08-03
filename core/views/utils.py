from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import cv2
from pathlib import Path
from core.file.azure import temp_blob
import os
from io import BytesIO

# base_path = "data/images/"
# new_path = "data/ims/"
# for infile in os.listdir(base_path):
#     print ("file : " + infile)
#     read = cv2.imread(base_path + infile)
#     outfile = infile.split('.')[0] + '.jpg'
#     cv2.imwrite(new_path+outfile,read,[int(cv2.IMWRITE_JPEG_QUALITY), 200])


def tif_to_jpg(tif_path, output_dir):
    no_extension = os.path.splitext(tif_path)[0]
    filename = os.path.basename(no_extension)
    try:
        with temp_blob(tif_path, ".tif") as temp_tif_path:
            read = cv2.imread(str(temp_tif_path))
            temp = filename + ".jpg"
            jpg_path = output_dir + "/" + temp
            success, buffer = cv2.imencode(
                ext=".jpg", img=read, params=[int(cv2.IMWRITE_JPEG_QUALITY), 100]
            )
            content = ContentFile(buffer)
            jpg_path = default_storage.save(jpg_path, content)

            # cv2.imwrite(str(jpg_path), read, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
            return jpg_path

    except Exception as e:
        print(f"Can not conread tif file: {e}")
        return None
