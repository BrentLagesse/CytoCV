"""Django models for uploads, previews, and analysis outputs."""
# https://docs.djangoproject.com/en/5.0/topics/forms/modelforms/#django.forms.ModelForm

from __future__ import annotations

import os
import uuid
from enum import Enum

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from mrc import DVFile
from PIL import Image

from core.config import get_channel_config_for_uuid


def get_guest_user() -> int:
    """Return the guest user id for unauthenticated runs."""
    user_model = get_user_model()
    guest = user_model.objects.filter(email="guest@local.invalid").only("id").first()
    if guest:
        return guest.id
    guest = user_model.objects.create_user(
        email="guest@local.invalid",
        password=None,
        first_name="Guest",
        last_name="User",
        is_active=False,
    )
    return guest.id


class UploadedImage(models.Model):
    """Stores an uploaded image and its on-disk location."""

    def upload_to(instance: "UploadedImage", filename: str) -> str:
        """Build the storage path for an uploaded file."""
        file_extension = "." + filename.split(".")[-1]
        return f"{instance.uuid}/{instance.name}{file_extension}"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        to_field="id",
        default=get_guest_user,
    )
    name = models.TextField()
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file_location = models.FileField(upload_to=upload_to)

    def __str__(self) -> str:
        return f"User: {self.user_id} Name: {self.name} UUID: {self.uuid}"


def user_directory_path(instance: "SegmentedImage", filename: str) -> str:
    """Build the storage path for a segmented image file."""
    return f"user_{instance.uuid}/{filename}"


class SegmentedImage(models.Model):
    """Stores segmentation outputs and metadata for a user run."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        to_field="id",
        default=get_guest_user,
    )

    UUID = models.UUIDField(primary_key=True)
    uploaded_date = models.DateTimeField(auto_now_add=True)
    file_location = models.FileField(upload_to=user_directory_path)
    ImagePath = models.FilePathField()
    CellPairPrefix = models.FilePathField()
    NumCells = models.IntegerField()

    def __str__(self) -> str:
        return (
            f"UUID: {self.UUID} Path: {self.ImagePath} "
            f"Prefix: {self.CellPairPrefix} Number of Cells: {self.NumCells}"
        )


class DVLayerTifPreview(models.Model):
    """Stores a single channel preview for a DV file."""

    wavelength = models.CharField(max_length=30)
    uploaded_image_uuid = models.ForeignKey(UploadedImage, on_delete=models.CASCADE)
    file_location = models.ImageField()


class Contour(Enum):
    """Contour selection modes used in legacy processing."""

    CONTOUR = 0
    CONVEX = 1
    CIRCLE = 2


class CategoryGFPDot(models.IntegerChoices):
    """Categories for GFP dot analysis classification."""

    ONEEACH = 1, "One green dot with each red dot"
    ONEONE = 2, "One green dot with one red dot"
    TWOONE = 3, "Two green dots with one red dot"
    NONE = 4, "N/A"

class CellStatistics(models.Model):
    """Stores per-cell statistics derived from segmentation output."""

    segmented_image = models.ForeignKey("SegmentedImage", on_delete=models.CASCADE)
    cell_id = models.IntegerField()
    distance = models.FloatField()
    line_gfp_intensity = models.FloatField()
    nucleus_intensity_sum = models.FloatField()
    cellular_intensity_sum = models.FloatField()
    cytoplasmic_intensity = models.FloatField(default=0.0)

    blue_contour_size = models.FloatField(default=0.0)

    red_contour_1_size = models.FloatField(default=0.0)
    red_contour_2_size = models.FloatField(default=0.0)
    red_contour_3_size = models.FloatField(default=0.0)

    red_intensity_1 = models.FloatField(default=0.0)
    red_intensity_2 = models.FloatField(default=0.0)
    red_intensity_3 = models.FloatField(default=0.0)

    green_intensity_1 = models.FloatField(default=0.0)
    green_intensity_2 = models.FloatField(default=0.0)
    green_intensity_3 = models.FloatField(default=0.0)

    green_red_intensity_1 = models.FloatField(default=0.0)
    green_red_intensity_2 = models.FloatField(default=0.0)
    green_red_intensity_3 = models.FloatField(default=0.0)

    red_blue_intensity_1 = models.FloatField(default=0.0)
    red_blue_intensity_2 = models.FloatField(default=0.0)
    red_blue_intensity_3 = models.FloatField(default=0.0)

    cellular_intensity_sum_DAPI = models.FloatField(default=0.0)
    nucleus_intensity_sum_DAPI = models.FloatField(default=0.0)
    cytoplasmic_intensity_DAPI = models.FloatField(default=0.0)

    # Category in GFP Dot Analysis
    category_GFP_dot = models.IntegerField(
        choices = CategoryGFPDot.choices,
        default = CategoryGFPDot.NONE,
    )

    # Biorientation in GFP Dot Analysis
    biorientation = models.IntegerField(default=0)

    dv_file_path = models.TextField(default="")
    image_name = models.TextField(default="")

    is_correct = models.BooleanField(default=True)
    nuclei_count = models.IntegerField(default=1)
    gfp_dot_count = models.IntegerField(default=0)
    red_dot_distance = models.FloatField(default=0.0)
    gfp_red_dot_distance = models.FloatField(default=0.0)
    cyan_dot_count = models.IntegerField(default=1)
    ground_truth = models.BooleanField(default=False)
    nucleus_intensity = models.JSONField(default=dict)
    nucleus_total_points = models.IntegerField(default=0)
    cell_intensity = models.JSONField(default=dict)
    cell_total_points = models.IntegerField(default=0)
    ignored = models.BooleanField(default=False)
    mcherry_line_gfp_intensity = models.FloatField(default=0.0)
    gfp_line_gfp_intensity = models.FloatField(default=0.0)
    properties = models.JSONField(default=dict)

    def __str__(self) -> str:
        return (
            f"Cell ID: {self.cell_id} - Dist: {self.distance}, "
            f"Line GFP: {self.line_gfp_intensity}"
        )

    def get_base_name(self) -> str:
        """Return the base name before the '_PRJ' suffix."""
        return self.image_name.split("_PRJ")[0]

    def get_image(
        self,
        channel: str,
        use_id: bool = False,
        outline: bool = True,
    ) -> Image.Image | str:
        """Fetch the image or filename for a given channel.

        Args:
            channel: Channel name to retrieve (e.g., "mCherry", "GFP").
            use_id: Whether to include the cell_id in the filename.
            outline: Whether to include the outline suffix for filenames.

        Returns:
            A PIL Image when reading from a DV file, or a filename string.
        """
        channel_config = get_channel_config_for_uuid(self.segmented_image.UUID)
        image_channel = channel_config.get(channel)
        print(f"Using channel for {channel}" + str(image_channel))

        outlinestr = ""
        if not outline:
            outlinestr = "-no_outline"
        if use_id:
            return f"{self.get_base_name()}_PRJ-{image_channel}-{self.cell_id}{outlinestr}.png"
        extspl = os.path.splitext(self.image_name)
        if extspl[1] == ".dv":
            f = DVFile(self.dv_file_path)
            image = f.asarray()
            img = Image.fromarray(image[image_channel])
            return img
        return f"{self.get_base_name()}_PRJ-{image_channel}{outlinestr}.png"


# class FileHandler(models.Model):
#     FILE_TYPES_CHOICES = {
#      "UpI"  : "UploadedImage",
#      "PrePI" : "PreProcessedImage",
#      "CSV" : "CSV",
#      "SegI" : "SegmentedImage",
#      "SegIO" : "SegmentedImageOutlined"
#     #  Add more when needed
#     }
#     name = models.TextField()
#     type = models.CharField(max_length=5, choices = FILE_TYPES_CHOICES)
#     file_path = models.FileField()
#     uploadedImageId = models.ForeignKey(UploadedImage, on_delete =models.CASCADE)
# class Contour(Enum):
#     CONTOUR = 0
#     CONVEX = 1
#     CIRCLE = 2

# class CellPair:
#     def __init__(self, image_name, id):
#         # https://docs.opencv.org/4.x/d4/d61/tutorial_warp_affine.html
#         self.is_correct = True # if is affine and is separable
#         self.image_name = image_name # 20_1212_M1914_001_R3D_REF.tif
#         self.id = id # number of cells undergoing mitosis
#         self.nuclei_count = 1 
#         self.red_dot_count = 1
#         self.gfp_dot_count = 0
#         self.red_dot_distance = 0
#         self.gfp_red_dot_distance = 0
#         self.cyan_dot_count = 1
#         self.green_dot_count = 1
#         self.ground_truth = False
#         self.nucleus_intensity = {}
#         self.nucleus_total_points = 0
#         self.cell_intensity = {}
#         self.cell_total_points = 0
#         self.ignored = False
#         self.mcherry_line_gfp_intensity = 0
#         self.gfp_line_gfp_intensity = 0
#         self.properties = dict()
