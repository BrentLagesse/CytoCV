# https://docs.djangoproject.com/en/5.0/topics/forms/modelforms/#django.forms.ModelForm
from django.forms import ModelForm
from functools import partial
import uuid, os, json
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from yeastweb.settings import MEDIA_ROOT, MEDIA_URL
from enum import Enum
from PIL import Image
from mrc import DVFile
from core.config import input_dir, get_channel_config_for_uuid


class UploadedImage(models.Model):
    # stores image in its own uuid folder along with its name
    def upload_to(instance, filename):
        uuid = instance.uuid
        name = instance.name
        # file cannot have . in its
        file_extension = '.' + filename.split('.')[-1]
        return f'{uuid}/{name}{file_extension}'
    name = models.TextField()
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file_location = models.FileField(upload_to=upload_to)

    def __str__(self):
        return 'Name: ' + self.name + ' UUID: ' + str(self.uuid)


def get_guest_user():
    return get_user_model().objects.get(username='guest').id  # this is for not logged in user

def user_directory_path(instance, filename):
    uuid = instance.uuid
    return f'user_{uuid}/{filename}'

class SegmentedImage(models.Model):
    # This will be point to user primary key
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             to_field='id', default=get_guest_user) # call get_guest_user at runtime

    UUID = models.UUIDField(primary_key=True)
    uploaded_date = models.DateTimeField(auto_now_add=True)
    file_location = models.FileField(upload_to=user_directory_path)
    ImagePath = models.FilePathField()
    CellPairPrefix = models.FilePathField()
    NumCells = models.IntegerField()

    def __str__(self):
        return 'UUID: ' + self.UUID + ' Path: ' + self.ImagePath + ' Prefix: ' + self.CellPairPrefix + ' Number of Cells: ' + self.NumCells


class DVLayerTifPreview(models.Model):
    wavelength = models.CharField(max_length=30)
    uploaded_image_uuid = models.ForeignKey(UploadedImage, on_delete=models.CASCADE)
    # since the tif is already generated, manually set to path 
    file_location = models.ImageField()

class Contour(Enum):
    CONTOUR = 0
    CONVEX = 1
    CIRCLE = 2

class CellStatistics(models.Model):
    segmented_image = models.ForeignKey("SegmentedImage", on_delete=models.CASCADE)
    cell_id = models.IntegerField()
    distance = models.FloatField()
    line_gfp_intensity = models.FloatField()
    nucleus_intensity_sum = models.FloatField()
    cellular_intensity_sum = models.FloatField()
    green_red_intensity = models.FloatField()

    dv_file_path = models.TextField(default="")

    # Not sure why needed, included to maintain consistency with legacy code
    image_name = models.TextField(default="")

    # Additional fields migrated from CellPair:
    is_correct = models.BooleanField(default=True)
    nuclei_count = models.IntegerField(default=1)
    red_dot_count = models.IntegerField(default=1)
    gfp_dot_count = models.IntegerField(default=0)
    red_dot_distance = models.FloatField(default=0.0)
    gfp_red_dot_distance = models.FloatField(default=0.0)
    cyan_dot_count = models.IntegerField(default=1)
    green_dot_count = models.IntegerField(default=1)
    ground_truth = models.BooleanField(default=False)
    nucleus_intensity = models.JSONField(default=dict)   # For storing intensities by contour type
    nucleus_total_points = models.IntegerField(default=0)
    cell_intensity = models.JSONField(default=dict)      # For storing intensities (if keeping it as dict)
    cell_total_points = models.IntegerField(default=0)
    ignored = models.BooleanField(default=False)
    mcherry_line_gfp_intensity = models.FloatField(default=0.0)
    gfp_line_gfp_intensity = models.FloatField(default=0.0)
    properties = models.JSONField(default=dict)

    def __str__(self):
        return f"Cell ID: {self.cell_id} - Dist: {self.distance}, Line GFP: {self.line_gfp_intensity}"

    #
    # Legacy "getter" methods moved into the model:
    #
    def get_base_name(self):
        """
        Legacy helper to extract the base name before '_PRJ' in self.image_name.
        """
        return self.image_name.split('_PRJ')[0]

    def get_mCherry(self, use_id=False, outline=True):
        # Retrieve the per‑file configuration using the DV file's UUID.
        # We assume that the associated SegmentedImage's UUID stores the DV file's UUID.
        channel_config = get_channel_config_for_uuid(self.segmented_image.UUID)
        mcherry_channel = channel_config.get("mCherry")
        print('Using channel for mCherry: ' + str(mcherry_channel))
        
        outlinestr = ''
        if not outline:
            outlinestr = '-no_outline'
        if use_id:
            # Return the pre-split PNG file that includes the cell_id.
            return f"{self.get_base_name()}_PRJ-{mcherry_channel}-{self.cell_id}{outlinestr}.png"
        else:
            extspl = os.path.splitext(self.image_name)
            if extspl[1] == '.dv':
                f = DVFile(self.dv_file_path)
                image = f.asarray()
                # Use the per‑file configured channel index for mCherry.
                img = Image.fromarray(image[mcherry_channel])
                return img
            else:
                return f"{self.get_base_name()}_PRJ-{mcherry_channel}{outlinestr}.png"


    def get_GFP(self, use_id=False, outline=True):
        # Retrieve the per‑file configuration using the DV file's UUID.
        channel_config = get_channel_config_for_uuid(self.segmented_image.UUID)
        gfp_channel = channel_config.get("GFP")
        print('Using channel for GFP: ' + str(gfp_channel))
        
        outlinestr = ''
        if not outline:
            outlinestr = '-no_outline'
        if use_id:
            # Return the pre-split PNG file that includes the cell_id.
            return f"{self.get_base_name()}_PRJ-{gfp_channel}-{self.cell_id}{outlinestr}.png"
        else:
            extspl = os.path.splitext(self.image_name)
            if extspl[1] == '.dv':
                f = DVFile(self.dv_file_path)
                image = f.asarray()
                # Use the per‑file configured channel index for GFP.
                img = Image.fromarray(image[gfp_channel])
                return img
            else:
                return f"{self.get_base_name()}_PRJ-{gfp_channel}{outlinestr}.png"




# class PreprocessImage(models.Model):
#     uploaded_image_uuid = models.OneToOneField(UploadedImage, on_delete = models.CASCADE, primary_key = True)
#     file_location = models.FileField(upload_to=update_to)
    


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
        


