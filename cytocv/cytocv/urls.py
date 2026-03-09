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
from django.contrib.auth.decorators import login_required
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from accounts.views import (
    account_settings_view,
    auth_login,
    auth_logout,
    dashboard_bulk_delete_view,
    dashboard_channel_visibility_view,
    dashboard_view,
    preferences_view,
    profile_view,
    signup,
)
from core.views import (
    convert_to_image,
    display,
    homepage,
    pre_process_step,
    segment_image,
    upload_images,
)
from core.views.media import serve_media
from core.views.pre_process_step import (
    cancel_progress,
    get_progress,
    set_progress,
    update_channel_order,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', homepage, name="homepage"),
    path('signin/', auth_login, name="signin"),
    path(
        'login/',
        RedirectView.as_view(pattern_name="signin", permanent=False, query_string=True),
        name="login",
    ),
    path('login/oauth/', include('allauth.urls')),
    re_path(
        r'^signin/oauth/?(?P<path>.*)$',
        RedirectView.as_view(
            url="/login/oauth/%(path)s",
            permanent=False,
            query_string=True,
        ),
    ),
    path('logout/', auth_logout, name="logout"),
    path('signup/', signup, name="signup"),
    path('profile/', login_required(profile_view), name="profile"),
    path('settings/', login_required(account_settings_view), name="account_settings"),
    path('dashboard/', login_required(dashboard_view), name="dashboard"),
    path(
        'dashboard/files/delete/',
        login_required(dashboard_bulk_delete_view),
        name="dashboard_bulk_delete",
    ),
    path(
        'dashboard/preferences/channels/',
        login_required(dashboard_channel_visibility_view),
        name="dashboard_channel_visibility",
    ),
    path('preferences/', login_required(preferences_view), name="preferences"),
    path('image/upload/', login_required(upload_images), name="image_upload"),
    path('image/preprocess/', login_required(pre_process_step), name="pre_process_step"),
    path('image/preprocess/<str:uuids>/', login_required(pre_process_step), name="pre_process_step"),
    path('image/<str:uuids>/convert/', login_required(convert_to_image.convert_to_image)),
    path('image/<str:uuids>/segment/', login_required(segment_image.segment_image)),
    path('image/<str:uuids>/display/', login_required(display.display_cell), name='display'),
    path('image/<str:uuid>/main-channel/', login_required(display.main_image_channel), name='main_image_channel'),
    path('api/update-channel-order/<str:uuid>/', login_required(update_channel_order), name='update_channel_order'),
    path('api/progress/<str:uuids>/', login_required(get_progress), name='analysis_progress'),
    path('api/progress/<str:key>/set/', login_required(set_progress), name='set_progress'),
    path('api/progress/<str:uuids>/cancel/', login_required(cancel_progress), name='cancel_progress'),
    path('media/<path:relative_path>', login_required(serve_media), name='protected_media'),
]
