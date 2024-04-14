from django.http import HttpResponse
from django.shortcuts import render
from ..forms import UploadFileForm

# Create your views here.
def upload_file(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        file = request.FILES['file']
        return HttpResponse("The name of uploaded file is ", str(file))
        if form.is_valid():
            #Handle image upload
            print("hello")
    else:
        form = UploadFileForm()
    form = UploadFileForm()
    return render(request, 'form/uploadImage.html', {'form' : form})
    print("hello")