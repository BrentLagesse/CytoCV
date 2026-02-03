"""Custom django-allauth adapter for OAuth error redirects and linking."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Redirects social auth errors to login with provider context."""

    def pre_social_login(self, request: HttpRequest, sociallogin) -> None:
        """Connect a social login to an existing user with a verified email."""
        if sociallogin.is_existing:
            return

        email = (sociallogin.user.email or "").strip().lower()
        if not email:
            return

        # Only link accounts when the provider asserts the email is verified.
        verified = any(
            addr.email and addr.verified and addr.email.lower() == email
            for addr in sociallogin.email_addresses
        )
        if not verified:
            return

        # Match a local account by email to avoid duplicate signups.
        user_model = get_user_model()
        try:
            user = user_model.objects.get(email__iexact=email)
        except user_model.DoesNotExist:
            return

        sociallogin.connect(request, user)

    def is_auto_signup_allowed(self, request: HttpRequest, sociallogin) -> bool:
        """Allow automatic signup when the provider supplies a verified email."""
        email = (sociallogin.user.email or "").strip()
        if not email:
            return False
        # Require a verified address to avoid creating accounts with untrusted emails.
        return any(addr.verified for addr in sociallogin.email_addresses)
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
