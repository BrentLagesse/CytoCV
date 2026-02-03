"""Authentication backend for email-based login."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailBackend(ModelBackend):
    """Authenticate users using their email address."""

    def authenticate(
        self,
        request,
        email: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ):
        user_model = get_user_model()
        identifier = email
        if identifier is None:
            identifier = kwargs.get(user_model.USERNAME_FIELD)
        if not identifier or password is None:
            return None
        try:
            user = user_model.objects.get(email__iexact=identifier)
        except user_model.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
