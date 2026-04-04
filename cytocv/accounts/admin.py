"""Admin registrations for the custom user model."""

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model

from accounts.quota import (
    get_base_quota_bytes_for_email,
    get_base_quota_source_for_email,
    get_effective_quota_bytes,
)
from accounts.quota_config import BYTES_PER_MB

CustomUser = get_user_model()


def _bytes_to_mb(value: int | None) -> float:
    """Convert a byte value into megabytes for admin display."""

    return round(float(int(value or 0)) / BYTES_PER_MB, 2)


class CustomUserAdminForm(UserChangeForm):
    """Admin change form that edits quota overrides in MB."""

    quota_override_mb = forms.IntegerField(
        label="Override amount (MB)",
        min_value=0,
        required=False,
        help_text="For bonus mode, add this many MB. For fixed mode, set the final total MB.",
    )

    class Meta(UserChangeForm.Meta):
        model = CustomUser
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        override_bytes = getattr(self.instance, "quota_override_bytes", None)
        if override_bytes is not None:
            self.fields["quota_override_mb"].initial = int(int(override_bytes) / BYTES_PER_MB)

    def clean(self):
        cleaned_data = super().clean()
        mode = cleaned_data.get(
            "quota_override_mode",
            CustomUser.QuotaOverrideMode.DEFAULT,
        )
        override_mb = cleaned_data.get("quota_override_mb")

        if mode in {
            CustomUser.QuotaOverrideMode.BONUS,
            CustomUser.QuotaOverrideMode.FIXED,
        } and override_mb is None:
            self.add_error("quota_override_mb", "Enter an override amount in MB.")

        if mode == CustomUser.QuotaOverrideMode.DEFAULT:
            cleaned_data["quota_override_bytes"] = None
        elif override_mb is not None:
            cleaned_data["quota_override_bytes"] = int(override_mb) * BYTES_PER_MB
        return cleaned_data

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        mode = self.cleaned_data.get(
            "quota_override_mode",
            CustomUser.QuotaOverrideMode.DEFAULT,
        )
        if mode == CustomUser.QuotaOverrideMode.DEFAULT:
            user.quota_override_bytes = None
        else:
            user.quota_override_bytes = self.cleaned_data.get("quota_override_bytes")

        if commit:
            user.save()
            self.save_m2m()
        return user


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin configuration for the email-based user model."""

    model = CustomUser
    form = CustomUserAdminForm
    add_form = AdminUserCreationForm
    ordering = ("email",)
    # Keep list displays concise for fast admin scans.
    list_display = (
        "email",
        "first_name",
        "last_name",
        "quota_override_mode",
        "effective_quota_gb",
        "is_staff",
        "is_active",
    )
    # Support email-based lookups and name filtering.
    search_fields = ("email", "first_name", "last_name")
    readonly_fields = (
        "base_quota_source",
        "base_quota_mb",
        "effective_quota_mb",
        "total_storage_mb_display",
        "used_storage_mb_display",
        "available_storage_mb_display",
        "total_storage",
        "used_storage",
        "available_storage",
        "last_login",
        "date_joined",
    )
    fieldsets = (
        # Core identity and credential fields.
        (None, {"fields": ("email", "password")}),
        # Profile attributes shown in admin.
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Storage policy",
            {
                "fields": (
                    "base_quota_source",
                    "base_quota_mb",
                    "quota_override_mode",
                    "quota_override_mb",
                    "effective_quota_mb",
                )
            },
        ),
        (
            "Storage usage",
            {
                "fields": (
                    "total_storage_mb_display",
                    "used_storage_mb_display",
                    "available_storage_mb_display",
                    "total_storage",
                    "used_storage",
                    "available_storage",
                )
            },
        ),
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

    @admin.display(description="Base quota source")
    def base_quota_source(self, obj) -> str:
        return get_base_quota_source_for_email(getattr(obj, "email", ""))

    @admin.display(description="Base quota (MB)")
    def base_quota_mb(self, obj) -> float:
        return _bytes_to_mb(get_base_quota_bytes_for_email(getattr(obj, "email", "")))

    @admin.display(description="Effective quota (MB)")
    def effective_quota_mb(self, obj) -> float:
        return _bytes_to_mb(get_effective_quota_bytes(obj))

    @admin.display(description="Effective quota (GB)")
    def effective_quota_gb(self, obj) -> float:
        return round(_bytes_to_mb(get_effective_quota_bytes(obj)) / 1024, 2)

    @admin.display(description="Total storage (MB)")
    def total_storage_mb_display(self, obj) -> float:
        return _bytes_to_mb(getattr(obj, "total_storage", 0))

    @admin.display(description="Used storage (MB)")
    def used_storage_mb_display(self, obj) -> float:
        return _bytes_to_mb(getattr(obj, "used_storage", 0))

    @admin.display(description="Available storage (MB)")
    def available_storage_mb_display(self, obj) -> float:
        return _bytes_to_mb(getattr(obj, "available_storage", 0))
