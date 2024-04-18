from django.db import models

# # Create your models here.

class Image(models.Model):
    name = models.TextField()
    cover = models.ImageField(upload_to='images/')
    def __str__(self):
        return self.name
    
# class Test(models.Model):
#     name = models.TextField()