"""Shared email normalization and account lookup helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.utils.crypto import salted_hmac

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailLookupResult:
    """Result of resolving a submitted email address to an account."""

    normalized_email: str
    user: Any | None = None
    source: str = ""
    exists: bool = False
    ambiguous: bool = False


def normalize_auth_email(email: str | None) -> str:
    """Normalize user-provided account email input for auth lookups."""
    return str(email or "").strip().lower()


def _email_fingerprint(normalized_email: str) -> str:
    """Return a stable, non-reversible fingerprint for auth diagnostics."""
    if not normalized_email:
        return ""
    return salted_hmac("accounts.email_lookup", normalized_email).hexdigest()[:16]


def _log_ambiguous_email_lookup(normalized_email: str, *, source: str) -> None:
    """Log an ambiguous account lookup without exposing the email address."""
    logger.warning(
        "Ambiguous account email lookup.",
        extra={
            "email_fingerprint": _email_fingerprint(normalized_email),
            "lookup_source": source,
        },
    )


def _ambiguous_result(normalized_email: str, *, source: str) -> EmailLookupResult:
    """Return an ambiguous lookup result and emit safe diagnostics."""
    _log_ambiguous_email_lookup(normalized_email, source=source)
    return EmailLookupResult(
        normalized_email=normalized_email,
        exists=True,
        ambiguous=True,
        source=source,
    )


def _matched_result(
    normalized_email: str,
    *,
    user: Any,
    source: str,
) -> EmailLookupResult:
    """Return a successful single-account lookup result."""
    return EmailLookupResult(
        normalized_email=normalized_email,
        user=user,
        exists=True,
        source=source,
    )


def resolve_user_by_email(
    email: str | None,
    *,
    include_verified_aliases: bool = True,
) -> EmailLookupResult:
    """Resolve an email to a single account using case-insensitive matching.

    The primary user email is preferred. Verified allauth email addresses are
    treated as safe aliases. Ambiguous matches are reported but not selected.
    """
    normalized_email = normalize_auth_email(email)
    if not normalized_email:
        return EmailLookupResult(normalized_email=normalized_email)

    user_model = get_user_model()
    direct_matches = list(
        user_model.objects.filter(email__iexact=normalized_email).order_by(
            "date_joined",
            "pk",
        )[:2]
    )
    if len(direct_matches) > 1:
        return _ambiguous_result(normalized_email, source="custom_user")
    if direct_matches:
        return _matched_result(
            normalized_email,
            user=direct_matches[0],
            source="custom_user",
        )

    if not include_verified_aliases:
        return EmailLookupResult(normalized_email=normalized_email)

    try:
        from allauth.account.models import EmailAddress
    except Exception:
        logger.exception("Unable to import allauth EmailAddress for account lookup.")
        return EmailLookupResult(normalized_email=normalized_email)

    verified_aliases = list(
        EmailAddress.objects.filter(
            email__iexact=normalized_email,
            verified=True,
        )
        .select_related("user")
        .order_by("user_id", "pk")
    )
    if not verified_aliases:
        return EmailLookupResult(normalized_email=normalized_email)

    users_by_id: dict[Any, Any] = {}
    for alias in verified_aliases:
        if alias.user_id not in users_by_id:
            users_by_id[alias.user_id] = alias.user

    if len(users_by_id) > 1:
        return _ambiguous_result(normalized_email, source="verified_email_alias")

    return _matched_result(
        normalized_email,
        user=next(iter(users_by_id.values())),
        source="verified_email_alias",
    )


def find_user_by_email(
    email: str | None,
    *,
    include_verified_aliases: bool = True,
) -> Any | None:
    """Return the unambiguous account for an email, if one exists."""
    return resolve_user_by_email(
        email,
        include_verified_aliases=include_verified_aliases,
    ).user


def email_matches_existing_account(
    email: str | None,
    *,
    include_verified_aliases: bool = True,
) -> bool:
    """Return True when an email belongs to any existing account."""
    return resolve_user_by_email(
        email,
        include_verified_aliases=include_verified_aliases,
    ).exists
