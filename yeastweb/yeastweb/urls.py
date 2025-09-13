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
from django.urls import path, include
from core.views import upload_images, homepage, pre_process_step, convert_to_image, segment_image, display
from accounts.views import profile_view, auth_login, auth_logout, signup
from django.conf import settings
from django.conf.urls.static import static  
from django.urls import path
from core.views.pre_process_step import update_channel_order, get_progress, set_progress

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', homepage, name="homepage"),
    path('login/',auth_login, name="login"),
    path('login/oauth',include('allauth.urls'), name="oauth_login"),
    path('logout/',auth_logout, name="logout"),
    path('signup/',signup, name="signup"),
    path('profile/',profile_view ,name="profile"),
    path('image/upload/', upload_images, name="image_upload"),
    path('image/preprocess/', pre_process_step, name="pre_process_step"),  
    path('image/preprocess/<str:uuids>/', pre_process_step, name="pre_process_step"),  # Multiple UUIDs
    path('image/<str:uuids>/convert/', convert_to_image.convert_to_image),
    path('image/<str:uuids>/segment/', segment_image.segment_image),
    path('image/<str:uuids>/display/', display.display_cell, name='display'),  # Accepting multiple UUIDs as a comma-separated string
    path('api/update-channel-order/<str:uuid>/', update_channel_order, name='update_channel_order'),
    path('api/progress/<str:uuids>/', get_progress, name='analysis_progress'),
    path('api/progress/<str:key>/set/', set_progress, name='set_progress'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
