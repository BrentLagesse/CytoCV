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
from django.urls import include, path

from accounts.views import (
    account_settings_view,
    auth_login,
    auth_logout,
    dashboard_bulk_delete_view,
    dashboard_channel_visibility_view,
    dashboard_view,
    preferences_view,
    signup,
)
from core.views import (
    cancel_progress,
    convert_to_image,
    display,
    experiment,
    get_progress,
    home,
    main_image_channel,
    pre_process,
    save_display_files,
    segment_image,
    set_progress,
    sync_display_file_selection,
    unsave_display_files,
    update_channel_order,
)
from core.views.media import serve_media

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name="home"),
    path('signin/', auth_login, name="signin"),
    path('signin/oauth/', include('allauth.urls')),
    path('logout/', auth_logout, name="logout"),
    path('signup/', signup, name="signup"),
    path('account-settings/', login_required(account_settings_view), name="account_settings"),
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
    path('workflow-defaults/', login_required(preferences_view), name="workflow_defaults"),
    path('experiment/', login_required(experiment), name="experiment"),
    path(
        'experiment/<str:uuids>/pre-process/',
        login_required(pre_process),
        name="pre_process",
    ),
    path(
        'experiment/<str:uuids>/convert/',
        login_required(convert_to_image),
        name="experiment_convert",
    ),
    path(
        'experiment/<str:uuids>/segment/',
        login_required(segment_image),
        name="experiment_segment",
    ),
    path(
        'experiment/<str:uuids>/display/',
        login_required(display),
        name='display',
    ),
    path(
        'experiment/display/files/save/',
        login_required(save_display_files),
        name='display_save_files',
    ),
    path(
        'experiment/display/files/unsave/',
        login_required(unsave_display_files),
        name='display_unsave_files',
    ),
    path(
        'experiment/display/files/sync-selection/',
        login_required(sync_display_file_selection),
        name='display_sync_file_selection',
    ),
    path(
        'experiment/<str:uuid>/main-channel/',
        login_required(main_image_channel),
        name='main_image_channel',
    ),
    path('api/update-channel-order/<str:uuid>/', login_required(update_channel_order), name='update_channel_order'),
    path('api/progress/<str:uuids>/', login_required(get_progress), name='analysis_progress'),
    path('api/progress/<str:key>/set/', login_required(set_progress), name='set_progress'),
    path('api/progress/<str:uuids>/cancel/', login_required(cancel_progress), name='cancel_progress'),
    path('media/<path:relative_path>', login_required(serve_media), name='protected_media'),
]
