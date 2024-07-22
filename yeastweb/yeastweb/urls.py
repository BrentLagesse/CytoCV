"""
URL configuration for yeastweb project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from core.views import upload_images, homepage, pre_process_step, convert_to_image, segment_image, display
from django.conf import settings
from django.conf.urls.static import static  # new

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', homepage, name="homepage"),
    path('image/upload/', upload_images, name="image_upload" ),
    path('image/<uuid:uuid>/', pre_process_step, name="pre_process"),
    path('image/<uuid:uuid>/convert/', convert_to_image.convert_to_image),
    path('image/<uuid:uuid>/segment/', segment_image.segment_image),
    path('image/<uuid:uuid>/display/', display.display_cell)
]

if settings.DEBUG:  # new
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)