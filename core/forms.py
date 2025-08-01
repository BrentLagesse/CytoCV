from core.models import UploadedImage
from django import forms

class UploadImageForm(forms.Form):
    file = forms.FileField()  # Single file field, we'll handle multiple files in the view
