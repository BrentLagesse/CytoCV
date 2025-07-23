import numpy as np

class GrayImage:
    _image_storage = {}
    def __init__(self, img:dict = None):
        if img:
            self._image_storage = img
        else:
            self._image_storage = {
                'gray_mcherry_3': None,
                'gray_mcherry': None,
                'gray_dapi': None,
                'gray_dapi_3': None,
                'GFP': None,
                'GFP_no_bg': None,
            }
    def set_image(self, key:str, image:np.ndarray):
        self._image_storage[key] = image

    def set_image(self, images:dict):
        self._image_storage = images

    def get_image(self, key):
        return self._image_storage[key]