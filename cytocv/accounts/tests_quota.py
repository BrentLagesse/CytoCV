from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from accounts.admin import CustomUserAdminForm
from accounts.quota import (
    get_base_quota_bytes_for_email,
    get_base_quota_source_for_email,
    get_effective_quota_bytes,
)
from accounts.quota_config import BYTES_PER_MB, parse_user_fixed_quota_map


@override_settings(
    STORAGE_QUOTA_DEFAULT_BYTES=100 * BYTES_PER_MB,
    STORAGE_QUOTA_EDU_BYTES=1024 * BYTES_PER_MB,
    STORAGE_QUOTA_EDU_SUFFIXES=(".edu",),
    STORAGE_QUOTA_USER_FIXED_BYTES={
        "ngioanni@uw.edu": 3072 * BYTES_PER_MB,
        "lagesse@uw.edu": 3072 * BYTES_PER_MB,
        "u0463089@umail.utah.edu": 3072 * BYTES_PER_MB,
    },
)
class UserQuotaPolicyTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()

    def test_new_non_edu_user_gets_default_quota(self):
        user = self.user_model.objects.create_user(
            email="researcher@example.com",
            password="TestPass123!",
        )

        self.assertEqual(user.total_storage, 100 * BYTES_PER_MB)
        self.assertEqual(user.available_storage, 100 * BYTES_PER_MB)
        self.assertEqual(get_base_quota_source_for_email(user.email), "Env default rule")

    def test_new_edu_user_gets_edu_quota(self):
        user = self.user_model.objects.create_user(
            email="student@school.edu",
            password="TestPass123!",
        )

        self.assertEqual(user.total_storage, 1024 * BYTES_PER_MB)
        self.assertEqual(user.available_storage, 1024 * BYTES_PER_MB)
        self.assertEqual(
            get_base_quota_source_for_email(user.email),
            "Env domain rule (.edu)",
        )

    def test_env_fixed_email_quota_wins_over_domain_rule(self):
        for email in (
            "ngioanni@uw.edu",
            "lagesse@uw.edu",
            "u0463089@umail.utah.edu",
        ):
            user = self.user_model.objects.create_user(
                email=email,
                password="TestPass123!",
            )
            self.assertEqual(user.total_storage, 3072 * BYTES_PER_MB)
            self.assertEqual(
                get_base_quota_bytes_for_email(email),
                3072 * BYTES_PER_MB,
            )

    def test_email_change_reapplies_base_quota_when_mode_is_default(self):
        user = self.user_model.objects.create_user(
            email="person@example.com",
            password="TestPass123!",
        )

        user.email = "person@campus.edu"
        user.save(update_fields=["email"])
        user.refresh_from_db()

        self.assertEqual(user.total_storage, 1024 * BYTES_PER_MB)

    def test_bonus_override_adds_to_env_fixed_quota(self):
        user = self.user_model.objects.create_user(
            email="ngioanni@uw.edu",
            password="TestPass123!",
            quota_override_mode=self.user_model.QuotaOverrideMode.BONUS,
            quota_override_bytes=512 * BYTES_PER_MB,
        )
        user.refresh_from_db()

        self.assertEqual(user.total_storage, (3072 + 512) * BYTES_PER_MB)
        self.assertEqual(get_effective_quota_bytes(user), (3072 + 512) * BYTES_PER_MB)

    def test_fixed_override_wins_and_clearing_it_restores_env_quota(self):
        user = self.user_model.objects.create_user(
            email="lagesse@uw.edu",
            password="TestPass123!",
        )
        self.assertEqual(user.total_storage, 3072 * BYTES_PER_MB)

        user.quota_override_mode = self.user_model.QuotaOverrideMode.FIXED
        user.quota_override_bytes = 5120 * BYTES_PER_MB
        user.save(update_fields=["quota_override_mode", "quota_override_bytes"])
        user.refresh_from_db()
        self.assertEqual(user.total_storage, 5120 * BYTES_PER_MB)

        user.quota_override_mode = self.user_model.QuotaOverrideMode.DEFAULT
        user.quota_override_bytes = None
        user.save(update_fields=["quota_override_mode", "quota_override_bytes"])
        user.refresh_from_db()
        self.assertEqual(user.total_storage, 3072 * BYTES_PER_MB)

    def test_admin_form_converts_override_mb_to_bytes(self):
        user = self.user_model.objects.create_user(
            email="admin-target@example.com",
            password="TestPass123!",
        )
        form = CustomUserAdminForm(
            data={
                "email": user.email,
                "password": user.password,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "is_active": user.is_active,
                "groups": [],
                "user_permissions": [],
                "quota_override_mode": self.user_model.QuotaOverrideMode.FIXED,
                "quota_override_mb": 2048,
                "total_storage": user.total_storage,
                "used_storage": user.used_storage,
                "available_storage": user.available_storage,
                "processing_used": user.processing_used,
                "config": user.config,
                "date_joined": user.date_joined,
            },
            instance=user,
        )

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        saved.refresh_from_db()
        self.assertEqual(saved.quota_override_bytes, 2048 * BYTES_PER_MB)
        self.assertEqual(saved.total_storage, 2048 * BYTES_PER_MB)


class QuotaConfigParsingTests(TestCase):
    def test_parse_user_fixed_quota_map_rejects_invalid_entries(self):
        with self.assertRaises(ImproperlyConfigured):
            parse_user_fixed_quota_map("invalid-entry-without-colon")

        with self.assertRaises(ImproperlyConfigured):
            parse_user_fixed_quota_map("bad-email:100")

        with self.assertRaises(ImproperlyConfigured):
            parse_user_fixed_quota_map("user@example.com:not-a-number")

        with self.assertRaises(ImproperlyConfigured):
            parse_user_fixed_quota_map("user@example.com:100,user@example.com:200")
