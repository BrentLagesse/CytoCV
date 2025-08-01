import cv2
from pathlib import Path    

# base_path = "data/images/"
# new_path = "data/ims/"
# for infile in os.listdir(base_path):
#     print ("file : " + infile)
#     read = cv2.imread(base_path + infile)
#     outfile = infile.split('.')[0] + '.jpg'
#     cv2.imwrite(new_path+outfile,read,[int(cv2.IMWRITE_JPEG_QUALITY), 200])


def tif_to_jpg(tif_path :Path, output_dir :Path) -> Path:
    filename = tif_path.stem
    read = cv2.imread(str(tif_path))
    temp =filename+ '.jpg'
    jpg_path = Path(output_dir / temp)
    cv2.imwrite(str(jpg_path), read,[int(cv2.IMWRITE_JPEG_QUALITY), 100])
    return jpg_path