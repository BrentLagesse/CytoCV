import numpy as np

class GrayImage:
    _image_storage = {}
    def __init__(self, img:dict = None):
        if img:
            self._image_storage = img
        else:
            self._image_storage = {
                'gray_red_3': None,
                'gray_red': None,
                'gray_blue': None,
                'gray_blue_3': None,
                'green': None,
                'green_no_bg': None,
                'red_no_bg': None,
            }
    def set_image(self, key:str, image:np.ndarray):
        self._image_storage[key] = image

    def set_image(self, images:dict):
        self._image_storage = images

    def get_image(self, key):
        return self._image_storage.get(key)
