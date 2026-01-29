"""Custom django-allauth adapter for OAuth error redirects."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Redirects social auth errors to login with provider context."""
    def on_authentication_error(
        self,
        request: HttpRequest,
        provider: Any | None,
        error: object | None = None,
        exception: BaseException | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> None:
        """Handle OAuth errors by redirecting to login with a hint.

        Adds `oauth_error=1` and, when available, `provider=<id>` so the
        login page can show the right error message.

        Args:
            request: Django HttpRequest.
            provider: Social provider instance (may be None).
            error: Optional error code/message.
            exception: Optional exception raised during auth.
            extra_context: Optional context dict from the process.

        Raises:
            ImmediateHttpResponse: Always raised to redirect to login.
        """
        login_url = reverse("login")
        provider_id = getattr(provider, "id", None) if provider else None
        if provider_id:
            login_url = f"{login_url}?oauth_error=1&provider={provider_id}"
        else:
            login_url = f"{login_url}?oauth_error=1"
        raise ImmediateHttpResponse(redirect(login_url))
