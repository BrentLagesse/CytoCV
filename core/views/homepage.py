from django.shortcuts import render
from core.models import UploadedImage 
from django.template.response import TemplateResponse
# chose function for https request because https://spookylukey.github.io/django-views-the-right-way/context-data.html
def homepage(request):
    return TemplateResponse(request, "home.html")