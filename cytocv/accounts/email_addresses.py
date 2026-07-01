"""Utilities for keeping user email aliases aligned with django-allauth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from accounts.email_lookup import normalize_auth_email


@dataclass
class EmailAddressSyncResult:
    """Outcome of syncing one user's primary account email alias."""

    user: Any
    normalized_email: str
    email_address: Any | None = None
    created: bool = False
    updated: bool = False
    skipped: bool = False
    conflict: bool = False
    message: str = ""

    @property
    def already_present(self) -> bool:
        """Return True when a matching alias already existed unchanged."""

        return (
            self.email_address is not None
            and not self.created
            and not self.updated
            and not self.skipped
            and not self.conflict
        )


class EmailAddressConflictError(ValueError):
    """Raised when an email alias already belongs to another user."""


def normalize_account_email(email: str | None) -> str:
    """Normalize account email addresses consistently across auth code."""

    return normalize_auth_email(email)


def sync_user_email_address(
    user: Any,
    *,
    verified: bool | None = True,
    primary: bool = True,
    dry_run: bool = False,
) -> EmailAddressSyncResult:
    """Ensure a user has an allauth EmailAddress for their primary email.

    The sync is intentionally conservative. If the target email already belongs
    to another user, the alias is not reassigned.
    """

    normalized_email = normalize_account_email(getattr(user, "email", None))
    if not normalized_email:
        # Blank emails cannot participate in email login/recovery and are reported
        # as skipped instead of creating invalid allauth aliases.
        return EmailAddressSyncResult(
            user=user,
            normalized_email=normalized_email,
            skipped=True,
            message="blank email",
        )
    if getattr(user, "pk", None) is None:
        # Unsaved users are skipped because allauth aliases require a persisted
        # foreign key and signals will retry after save.
        return EmailAddressSyncResult(
            user=user,
            normalized_email=normalized_email,
            skipped=True,
            message="unsaved user",
        )

    from allauth.account.models import EmailAddress

    conflicting_alias = (
        EmailAddress.objects.filter(email__iexact=normalized_email)
        .exclude(user=user)
        .select_related("user")
        .first()
    )
    if conflicting_alias is not None:
        # Conflicts are never repaired automatically because moving an alias could
        # break login/recovery for another account.
        return EmailAddressSyncResult(
            user=user,
            normalized_email=normalized_email,
            email_address=conflicting_alias,
            conflict=True,
            message=(
                "email alias already belongs to user "
                f"{getattr(conflicting_alias, 'user_id', '')}"
            ),
        )

    email_address = (
        EmailAddress.objects.filter(user=user, email__iexact=normalized_email)
        .order_by("pk")
        .first()
    )

    if email_address is None:
        if dry_run:
            # Dry-run reports the intended create without demoting any existing
            # primary alias or inserting an EmailAddress row.
            return EmailAddressSyncResult(
                user=user,
                normalized_email=normalized_email,
                created=True,
                message="would create alias",
            )
        with transaction.atomic():
            # Primary alias updates and creation are atomic so allauth never sees
            # two primary aliases for one account mid-repair.
            if primary:
                EmailAddress.objects.filter(user=user, primary=True).update(primary=False)
            email_address = EmailAddress.objects.create(
                user=user,
                email=normalized_email,
                verified=bool(verified) if verified is not None else False,
                primary=primary,
            )
        return EmailAddressSyncResult(
            user=user,
            normalized_email=normalized_email,
            email_address=email_address,
            created=True,
            message="created alias",
        )

    update_fields: list[str] = []
    if email_address.email != normalized_email:
        email_address.email = normalized_email
        update_fields.append("email")
    if verified is not None and email_address.verified != verified:
        email_address.verified = verified
        update_fields.append("verified")
    if primary and not email_address.primary:
        email_address.primary = True
        update_fields.append("primary")

    if dry_run:
        # Dry-run reports whether the row would change but leaves verified/primary
        # flags untouched.
        return EmailAddressSyncResult(
            user=user,
            normalized_email=normalized_email,
            email_address=email_address,
            updated=bool(update_fields),
            message="would update alias" if update_fields else "alias already present",
        )

    if update_fields:
        with transaction.atomic():
            # Demote any other primary alias in the same transaction as the target
            # alias update so password recovery resolves a single primary address.
            if primary:
                EmailAddress.objects.filter(user=user, primary=True).exclude(
                    pk=email_address.pk
                ).update(primary=False)
            email_address.save(update_fields=update_fields)
        return EmailAddressSyncResult(
            user=user,
            normalized_email=normalized_email,
            email_address=email_address,
            updated=True,
            message="updated alias",
        )

    return EmailAddressSyncResult(
        user=user,
        normalized_email=normalized_email,
        email_address=email_address,
        message="alias already present",
    )


def ensure_user_email_address(
    user: Any,
    *,
    verified: bool | None = True,
    primary: bool = True,
    dry_run: bool = False,
    raise_on_conflict: bool = True,
) -> Any | None:
    """Return the synced EmailAddress, or None for blank/skipped users."""

    result = sync_user_email_address(
        user,
        verified=verified,
        primary=primary,
        dry_run=dry_run,
    )
    if result.conflict and raise_on_conflict:
        # Callers that run in account-creation paths need a hard failure so they
        # cannot silently create an ambiguous email-login state.
        raise EmailAddressConflictError(result.message)
    return result.email_address
