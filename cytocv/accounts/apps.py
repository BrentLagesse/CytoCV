"""App configuration for the accounts application."""

from __future__ import annotations

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Accounts app configuration."""

    name = "accounts"

    def ready(self) -> None:
        """Register account-related signal handlers."""

        import accounts.signals  # noqa: F401
