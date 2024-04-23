import uuid
from django.db import models
# https://docs.djangoproject.com/en/5.0/topics/forms/modelforms/#django.forms.ModelForm
from django.forms import ModelForm


class Image(models.Model):
    name = models.TextField()
    uuid = models.UUIDField(primary_key=False, default=uuid.uuid4, editable=False)
    cover = models.ImageField(upload_to='images/')
    def __str__(self):
        return self.name


# class ImageForm(ModelForm): 
#     class Meta:
#         model = Image
#         fields = ['name', 'cover']
# class Test(models.Model):
#     name = models.TextField()