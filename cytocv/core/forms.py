"""Forms used by upload intake views."""

from core.models import UploadedImage
from django import forms

class UploadImageForm(forms.Form):
    """Minimal upload form; multi-file handling is owned by the view layer."""

    file = forms.FileField()  # Single file field, we'll handle multiple files in the view
