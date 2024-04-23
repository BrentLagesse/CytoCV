from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from core.forms import UploadImageForm
from core.models import Image
import uuid

# Create your views here.
def upload_file(request):
    if request.method == "POST":
        # form = UploadImageForm(request.POST, request.FILES)
        form = UploadImageForm(request.POST, request.FILES)
        if form.is_valid():
            name = form.cleaned_data['name']
            file = request.FILES['file']
            imageUuid= uuid.uuid4()
            instance = Image(name=name, uuid=imageUuid, cover=file )
            instance.save()
            # instance = Image(cover=request.FILES["file"])
            # handle_uploaded_file(file)
            # form.save()
            return redirect(f'/image/{imageUuid}/')
            return HttpResponse("Image successfully uploaded")
    else:
        form = UploadImageForm()
    form = UploadImageForm()
    return render(request, 'form/uploadImage.html', {'form' : form})
    print("hello")
    
# https://docs.djangoproject.com/en/5.0/topics/http/file-uploads/
def handle_uploaded_file(file):
    with open("some/file/name.txt", "wb+") as destination:
        for chunk in file.chunks():
            destination.write(chunk)