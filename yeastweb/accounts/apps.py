"""App configuration for the accounts application."""

from __future__ import annotations

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Accounts app configuration and startup hooks."""

    name = "accounts"

    def ready(self) -> None:
        """Ensure a disabled guest user exists for anonymous workflows."""
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        try:
            user_model.objects.get_or_create(
                username="guest",
                defaults={"is_active": False},
            )
        except Exception:
            pass
