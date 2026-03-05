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
    """Redirects social auth errors to sign-in with provider context."""

    @staticmethod
    def _normalized_social_email(sociallogin) -> str:
        """Return the best available social email in normalized form."""
        email = (sociallogin.user.email or "").strip().lower()
        if email:
            return email
        for addr in getattr(sociallogin, "email_addresses", []):
            candidate = (getattr(addr, "email", "") or "").strip().lower()
            if candidate:
                return candidate
        return ""

    def pre_social_login(self, request: HttpRequest, sociallogin) -> None:
        """Connect a social login to an existing user by email."""
        if sociallogin.is_existing:
            return

        email = self._normalized_social_email(sociallogin)
        if not email:
            return

        # Match a local account by email to avoid duplicate signups.
        user_model = get_user_model()
        try:
            user = user_model.objects.get(email__iexact=email)
        except user_model.DoesNotExist:
            return

        sociallogin.connect(request, user)

    def is_auto_signup_allowed(self, request: HttpRequest, sociallogin) -> bool:
        """Allow automatic signup when the provider supplies any email."""
        return bool(self._normalized_social_email(sociallogin))

    def on_authentication_error(
        self,
        request: HttpRequest,
        provider: Any | None,
        error: object | None = None,
        exception: BaseException | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> None:
        """Handle OAuth errors by redirecting to sign-in with a hint.

        Adds `oauth_error=1` and, when available, `provider=<id>` so the
        sign-in page can show the right error message.

        Args:
            request: Django HttpRequest.
            provider: Social provider instance (may be None).
            error: Optional error code/message.
            exception: Optional exception raised during auth.
            extra_context: Optional context dict from the process.

        Raises:
            ImmediateHttpResponse: Always raised to redirect to sign-in.
        """
        signin_url = reverse("signin")
        provider_id = getattr(provider, "id", None) if provider else None
        if provider_id:
            signin_url = f"{signin_url}?oauth_error=1&provider={provider_id}"
        else:
            signin_url = f"{signin_url}?oauth_error=1"
        raise ImmediateHttpResponse(redirect(signin_url))
