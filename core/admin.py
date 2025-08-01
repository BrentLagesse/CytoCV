from django.contrib import admin

from core.models import UploadedImage, DVLayerTifPreview

# Register your models here.
admin.site.register(UploadedImage)
admin.site.register(DVLayerTifPreview)