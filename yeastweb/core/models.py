import uuid
from django.db import models
# https://docs.djangoproject.com/en/5.0/topics/forms/modelforms/#django.forms.ModelForm
from django.forms import ModelForm
from functools import partial
import os

# helper method to 


# # 
# def upload_to_root(new_file_name :str):
#     return partial(_update_filename, new_file_name=new_file_name)

# def upload_to_directory(new_file_name :str, directory_name :str):
#     return partial(_update_filename, new_file_name=new_file_name)

class UploadedImage(models.Model):
    def update_to(instance, filename):
        uuid = instance.uuid
        name = instance.name
        # file cannot have . in its
        file_extension = '.' + filename.split('.')[-1]
        return f'{uuid}/{name}{file_extension}'

    name = models.TextField()
    uuid = models.UUIDField(primary_key=False, default=uuid.uuid4, editable=False)
    file_location = models.FileField(upload_to=update_to)
    def __str__(self):
        return self.name
    
# class PreprocessImage(models.Model):
#     uploaded_image_id = models.OneToOneField(UploadedImage, on_delete = models.CASCADE, primary_key = True)
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
        




