"""Custom django-allauth adapters for CytoCV account and OAuth flows."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse

from allauth.account import app_settings
from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from accounts.email_content import (
    attach_auth_email_logo,
    build_auth_email_logo_src,
    build_email_confirmation_email,
    normalize_recipient_name,
)
from accounts.email_lookup import (
    find_user_by_email,
    normalize_auth_email,
    resolve_user_by_email,
)


def _auth_sender_email() -> str:
    """Return the sender address used for account security emails."""
    return (
        (getattr(settings, "AUTH_EMAIL_FROM", "") or "").strip()
        or (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
        or (getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
    )


def _auth_reply_to_list() -> list[str] | None:
    """Return the Reply-To list used for account security emails."""
    sender_email = _auth_sender_email()
    return [sender_email] if sender_email else None


def _user_display_name(user: Any) -> str:
    """Return a short personal name for account email greetings."""
    first_name = normalize_recipient_name(getattr(user, "first_name", ""))
    if first_name:
        return first_name
    full_name = ""
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = normalize_recipient_name(get_full_name())
    return full_name


class CustomAccountAdapter(DefaultAccountAdapter):
    """Send django-allauth account emails through CytoCV branded templates."""

    def send_confirmation_mail(self, request, emailconfirmation, signup) -> None:
        """Send a branded email-confirmation link email."""
        if app_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED:
            super().send_confirmation_mail(request, emailconfirmation, signup)
            return

        from_email = _auth_sender_email()
        recipient = emailconfirmation.email_address.email
        user = emailconfirmation.email_address.user
        email_content = build_email_confirmation_email(
            activate_url=self.get_email_confirmation_url(request, emailconfirmation),
            minutes_valid=settings.AUTH_VERIFICATION_EXPIRY_MINUTES,
            recipient_email=recipient,
            recipient_name=_user_display_name(user),
            logo_url=build_auth_email_logo_src(request) if request else "",
            sender_email=from_email,
        )
        message = EmailMultiAlternatives(
            email_content.subject,
            email_content.text_body,
            from_email,
            [recipient],
            reply_to=_auth_reply_to_list(),
        )
        message.attach_alternative(email_content.html_body, "text/html")
        attach_auth_email_logo(message)
        message.send()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Redirects social auth errors to sign-in with provider context."""

    @staticmethod
    def _normalized_social_email(sociallogin) -> str:
        """Return the best available social email in normalized form."""
        email = normalize_auth_email(sociallogin.user.email)
        if email:
            return email
        for addr in getattr(sociallogin, "email_addresses", []):
            candidate = normalize_auth_email(getattr(addr, "email", ""))
            if candidate:
                return candidate
        return ""

    def save_user(self, request: HttpRequest, sociallogin, form=None):
        """Persist new social users with normalized email fields."""
        sociallogin.user.email = normalize_auth_email(sociallogin.user.email)
        for addr in getattr(sociallogin, "email_addresses", []):
            addr.email = normalize_auth_email(getattr(addr, "email", ""))
        return super().save_user(request, sociallogin, form)

    def pre_social_login(self, request: HttpRequest, sociallogin) -> None:
        """Connect a social login to an existing user by email."""
        if sociallogin.is_existing:
            return

        email = self._normalized_social_email(sociallogin)
        if not email:
            return

        # Match an existing account by primary email or verified email alias.
        user = find_user_by_email(email)
        if user is None:
            return

        sociallogin.connect(request, user)

    def is_auto_signup_allowed(self, request: HttpRequest, sociallogin) -> bool:
        """Allow automatic signup when the provider supplies any email."""
        email = self._normalized_social_email(sociallogin)
        if not email:
            return False
        lookup = resolve_user_by_email(email)
        return not lookup.ambiguous

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
