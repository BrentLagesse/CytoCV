from django import forms

# https://docs.djangoproject.com/en/5.0/topics/http/file-uploads/#uploading-multiple-files
class UploadFileForm(forms.Form):
    file = forms.FileField()