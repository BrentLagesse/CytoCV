"""Admin registrations for the custom user model."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin configuration for the email-based user model."""

    model = CustomUser
    ordering = ("email",)
    # Keep list displays concise for fast admin scans.
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active")
    # Support email-based lookups and name filtering.
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        # Core identity and credential fields.
        (None, {"fields": ("email", "password")}),
        # Profile attributes shown in admin.
        ("Personal info", {"fields": ("first_name", "last_name")}),
        # Permission management controls access and staff status.
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        # Timestamps for audit and account history.
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        # Admin-only flow for creating new accounts.
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "is_staff", "is_superuser", "is_active"),
        }),
    )
