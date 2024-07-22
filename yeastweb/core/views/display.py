from core.models import UploadedImage
from django.template.response import TemplateResponse
from pathlib import Path
from yeastweb.settings import MEDIA_ROOT

# It might be smart to have a sort of display driver, where we can easily swap directories 

def display_cell(request, uuid):
    # We need to send the outlined image, and all of the segmented images to the html template
    Image_Name = UploadedImage.objects.get(pk=uuid).name
    full_outlined =  str(Path(MEDIA_ROOT)) + '/' + str(uuid) + '/output/' + Image_Name + '.png'
    return TemplateResponse(request, "display_cell.html", {'main_image' : full_outlined})