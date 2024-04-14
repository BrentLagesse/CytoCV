from django.shortcuts import render
from core.models import Image 
# from ..models import Image 
from django.template.response import TemplateResponse
# Create your views here.
# chose function because https://spookylukey.github.io/django-views-the-right-way/context-data.html
def homepage(request):
    return TemplateResponse(request, "home.html", {'images' : Image.objects.all()})
# class HomePageView(ListView) :
#     model = Test
#     template_name = "home.html"