from core.models import UploadedImage
from django import forms

class UploadImageForm(forms.Form):
    name = forms.CharField(required=False, label="Folder Name", max_length=100)  # Optional folder name
    file = forms.FileField()  # Single file field, we'll handle multiple files in the view
