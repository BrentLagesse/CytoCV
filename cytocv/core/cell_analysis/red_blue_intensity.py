from core.image_processing import calculate_intensity_mask
from core.services.canonical_contours import get_canonical_red_slots
from .analysis import Analysis

class RedBlueIntensity(Analysis):
    name = 'Red in Blue Intensity'

    def calculate_statistics(
        self,
        best_contours,
        contours_data,
        red_image,
        green_image,
        puncta_line_width_input,
        cen_dot_distance,
        cen_dot_collinearity_threshold,
        cen_dot_proximity_radius=13,
    ):
        """
        """
        blue_gray = self.preprocessed_images.get_image('gray_blue')
        red_slots = get_canonical_red_slots(contours_data, blue_gray.shape, limit=3)

        for idx in range(1, 4):
            setattr(self.cp, f'red_blue_intensity_{idx}', 0.0)

        for i, slot in enumerate(red_slots):
            red_intensity = calculate_intensity_mask(blue_gray, slot.mask)
            setattr(self.cp, f'red_blue_intensity_{i+1}', red_intensity)
