from core.models import UploadedImage
from django import forms

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class UploadImageForm(forms.Form):
    class Meta:
        model = UploadedImage
        fields = ['name', 'files']

    name = forms.CharField(label="Picture Name", max_length=100)
    files = MultipleFileField(label='Select files', required=False)



