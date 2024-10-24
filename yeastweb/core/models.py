import uuid
import json
from django.db import models
# https://docs.djangoproject.com/en/5.0/topics/forms/modelforms/#django.forms.ModelForm
from django.forms import ModelForm
from functools import partial

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
    
class SegmentedImage(models.Model):
    UUID = models.UUIDField(primary_key=True)
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
        



