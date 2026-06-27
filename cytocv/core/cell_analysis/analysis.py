"""Base class for per-cell statistics plugins."""

from abc import abstractmethod

from core.image_processing import GrayImage

from core.models import CellStatistics


class Analysis:
    """Shared mutable context used by concrete cell-analysis plugins."""

    cp = None
    preprocessed_images = GrayImage()
    output_dir = None
    name = ""

    def __init__(self, cp: CellStatistics = None, image: GrayImage = None, output_dir=None):
        if cp is not None and image is not None and output_dir is not None:
            self.cp = cp
            self.preprocessed_images = image
            self.output_dir = output_dir

    def setting_up(self, cp, preprocessed_images, output_dir):
        """Attach the current statistics row and image bundle before execution."""

        self.cp = cp
        self.preprocessed_images = preprocessed_images
        self.output_dir = output_dir

    @abstractmethod
    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image,
        green_image,
        puncta_line_width_input,
        cen_dot_distance,
        cen_dot_proximity_radius=13,
    ):
        """Mutate ``self.cp`` with plugin-specific statistics."""

        pass
