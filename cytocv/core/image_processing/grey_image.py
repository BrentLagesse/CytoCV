"""Container for preprocessed grayscale planes used during statistics."""

import numpy as np

class GrayImage:
    """Store optional grayscale images under the historical plugin key names."""

    _image_storage = {}
    def __init__(self, img:dict = None):
        """Initialize the plugin image store with caller data or default keys."""

        if img:
            self._image_storage = img
        else:
            # Plugin implementations still request these exact keys, including
            # legacy blurred/background-subtracted names.
            self._image_storage = {
                'gray_red_3': None,
                'gray_red': None,
                'gray_blue': None,
                'gray_blue_3': None,
                'green': None,
                'green_no_bg': None,
                'red_no_bg': None,
                'raw_red': None,
                'raw_green': None,
                'raw_blue': None,
            }
    def set_image(self, key:str, image:np.ndarray):
        """Legacy key-based setter retained for callers that pass one image."""

        self._image_storage[key] = image

    def set_image(self, images:dict):
        """Replace the full image map used by statistics plugins."""

        self._image_storage = images

    def get_image(self, key):
        """Return a plugin image by historical key, or ``None`` when unavailable."""

        return self._image_storage.get(key)
