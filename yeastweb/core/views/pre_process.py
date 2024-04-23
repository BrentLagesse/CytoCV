from django.shortcuts import  get_object_or_404, render
from core.models import Image 
# from ..models import Image 
from django.template.response import TemplateResponse
# Create your views here.
# chose function because https://spookylukey.github.io/django-views-the-right-way/context-data.html
def pre_process(request, uuid):
    # print(Image.objects.all())
    image = get_object_or_404(Image, uuid=uuid)
    print("testing", uuid)
    print(image.cover)
    # context = {'image' :}
    return TemplateResponse(request, "pre-process.html", {'image' : image})
# class HomePageView(ListView) :
#     model = Test
#     template_name = "home.html"