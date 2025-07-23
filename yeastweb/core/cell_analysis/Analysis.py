from abc import abstractmethod

from core.image_processing.GrayImage import GrayImage

from core.models import CellStatistics

class Analysis:
    cp = None
    preprocessed_images = GrayImage()
    output_dir = None
    name = ""

    def __init__(self, cp:CellStatistics=None,image:GrayImage=None, output_dir=None):
        if(cp != None and image != None and output_dir != None):
            self.cp = cp
            self.preprocessed_images = image
            self.output_dir = output_dir
    def setting_up(self, cp,preprocessed_images,output_dir):
        self.cp = cp
        self.preprocessed_images = preprocessed_images
        self.output_dir = output_dir

    @abstractmethod
    def calculate_statistics(self, best_contours, contours_data,red_image, green_image,mcherry_line_width_input):
        pass