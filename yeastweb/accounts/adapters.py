from django.shortcuts import redirect
from django.urls import reverse

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def on_authentication_error(
        self,
        request,
        provider,
        error=None,
        exception=None,
        extra_context=None,
    ):
        login_url = reverse("login")
        provider_id = getattr(provider, "id", None) if provider else None
        if provider_id:
            login_url = f"{login_url}?oauth_error=1&provider={provider_id}"
        else:
            login_url = f"{login_url}?oauth_error=1"
        raise ImmediateHttpResponse(redirect(login_url))
