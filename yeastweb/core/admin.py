"""Admin registrations for core models."""

from django.contrib import admin

from core.models import DVLayerTifPreview, UploadedImage

admin.site.register(UploadedImage)
admin.site.register(DVLayerTifPreview)
