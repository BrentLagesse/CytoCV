"""Legacy red-in-blue contour intensity statistics plugin."""

from core.image_processing import calculate_intensity_mask
from core.services.canonical_contours import get_canonical_red_slots
from .analysis import Analysis


class RedBlueIntensity(Analysis):
    """Measure blue-channel intensity under canonical red contour slots."""

    name = 'Red In Blue Intensity'

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
        """Populate legacy Red-in-Blue contour intensity triplet fields."""

        # Always initialize all three export columns so cells with fewer red
        # contours do not leak previous values in reused statistics objects.
        for idx in range(1, 4):
            setattr(self.cp, f'red_blue_intensity_{idx}', 0.0)

        blue_gray = self.preprocessed_images.get_image('raw_blue')
        if blue_gray is None:
            # Blue legacy measurements predate raw-plane payloads; the blurred
            # grayscale fallback keeps old runs exportable.
            blue_gray = self.preprocessed_images.get_image('gray_blue')
        if blue_gray is None:
            return

        # Canonical red slots define the stable one-to-three field mapping used by
        # the result table and CSV/XLSX exports.
        red_slots = get_canonical_red_slots(contours_data, blue_gray.shape, limit=3)

        for i, slot in enumerate(red_slots):
            red_intensity = calculate_intensity_mask(blue_gray, slot.mask)
            setattr(self.cp, f'red_blue_intensity_{i+1}', red_intensity)
