"""
URL configuration for CytoCV project.

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
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from accounts.views import auth_login, auth_logout, profile_view, signup
from core.views import (
    convert_to_image,
    display,
    homepage,
    pre_process_step,
    segment_image,
    upload_images,
)
from core.views.pre_process_step import (
    cancel_progress,
    get_progress,
    set_progress,
    update_channel_order,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', homepage, name="homepage"),
    path('signin/', auth_login, name="signin"),
    path(
        'login/',
        RedirectView.as_view(pattern_name="signin", permanent=False, query_string=True),
        name="login",
    ),
    path('login/oauth', include('allauth.urls')),
    re_path(
        r'^signin/oauth/?(?P<path>.*)$',
        RedirectView.as_view(
            url="/login/oauth%(path)s",
            permanent=False,
            query_string=True,
        ),
    ),
    path('logout/',auth_logout, name="logout"),
    path('signup/',signup, name="signup"),
    path('profile/',profile_view ,name="profile"),
    path('image/upload/', upload_images, name="image_upload"),
    path('image/preprocess/', pre_process_step, name="pre_process_step"),  
    path('image/preprocess/<str:uuids>/', pre_process_step, name="pre_process_step"),  # Multiple UUIDs
    path('image/<str:uuids>/convert/', convert_to_image.convert_to_image),
    path('image/<str:uuids>/segment/', segment_image.segment_image),
    path('image/<str:uuids>/display/', display.display_cell, name='display'),  # Accepting multiple UUIDs as a comma-separated string
    path('image/<str:uuid>/main-channel/', display.main_image_channel, name='main_image_channel'),
    path('api/update-channel-order/<str:uuid>/', update_channel_order, name='update_channel_order'),
    path('api/progress/<str:uuids>/', get_progress, name='analysis_progress'),
    path('api/progress/<str:key>/set/', set_progress, name='set_progress'),
    path('api/progress/<str:uuids>/cancel/', cancel_progress, name='cancel_progress'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

