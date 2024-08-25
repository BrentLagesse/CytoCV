from core.models import UploadedImage, SegmentedImage
from django.shortcuts import render
from django.template.response import TemplateResponse
from pathlib import Path
from yeastweb.settings import MEDIA_URL

# It might be smart to have a sort of display driver, where we can easily swap directories 

def display_cell(request, uuid):
    # We need to send the outlined image, and all of the segmented images to the html template
    Image_Name = UploadedImage.objects.get(pk=uuid).name
    full_outlined =  str(Path(MEDIA_URL)) + '\\' + str(uuid) + '\\output\\' + Image_Name + '.png'
    CellImage = SegmentedImage.objects.get(pk=uuid)
    Images = {}

    for i in range(0, CellImage.NumCells):
        Images[str(i)] = []
        Images[str(i)].append(CellImage.CellPairPrefix + '-0-' + str(i))
        Images[str(i)].append(CellImage.CellPairPrefix + '-1-' + str(i))
        Images[str(i)].append(CellImage.CellPairPrefix + '-2-' + str(i))
        Images[str(i)].append(CellImage.CellPairPrefix + '-3-' + str(i))
    

    content = {'MainImagePath' : CellImage.ImagePath, 'NumberOfCells' : CellImage.NumCells, 'CellPairPath' : CellImage.CellPairPrefix}
    return TemplateResponse(request, "display_cell.html", content)