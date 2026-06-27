"""Create an operator-managed user account ready for password recovery."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from accounts.email_addresses import (
    normalize_account_email,
    sync_user_email_address,
)


class Command(BaseCommand):
    """Create or repair a user plus the allauth alias used for email login."""

    help = "Create an active user with an unusable password and synced email alias."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Email address for the user.")
        parser.add_argument("--first-name", default="", help="Optional first name.")
        parser.add_argument("--last-name", default="", help="Optional last name.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without writing to the database.",
        )

    def handle(self, *args, **options):
        email = normalize_account_email(options["email"])
        if not email:
            raise CommandError("--email cannot be blank.")

        user_model = get_user_model()
        existing_user = user_model.objects.filter(email__iexact=email).first()
        dry_run = bool(options.get("dry_run"))

        from allauth.account.models import EmailAddress

        # CustomUser.email and allauth EmailAddress must not point the same
        # address at different accounts; password reset and login both rely on
        # that alias remaining unambiguous.
        conflicting_alias = (
            EmailAddress.objects.filter(email__iexact=email)
            .select_related("user")
            .first()
        )
        if (
            conflicting_alias is not None
            and existing_user is not None
            and conflicting_alias.user_id != existing_user.pk
        ):
            raise CommandError(
                f"Email alias {email} already belongs to another user."
            )
        if conflicting_alias is not None and existing_user is None:
            raise CommandError(
                f"Email alias {email} already belongs to another user."
            )

        if existing_user is not None:
            result = sync_user_email_address(
                existing_user,
                verified=True,
                primary=True,
                dry_run=dry_run,
            )
            if result.conflict:
                raise CommandError(result.message)
            action = "Would repair existing user" if dry_run else "Repaired existing user"
            self.stdout.write(f"{action}: {existing_user.pk} {email}")
            return

        if dry_run:
            self.stdout.write(f"Would create active user with unusable password: {email}")
            return

        user = user_model.objects.create_user(
            email=email,
            password=None,
            first_name=(options.get("first_name") or "").strip(),
            last_name=(options.get("last_name") or "").strip(),
            is_active=True,
        )
        result = sync_user_email_address(
            user,
            verified=True,
            primary=True,
        )
        if result.conflict:
            raise CommandError(result.message)
        self.stdout.write(
            f"Created active user with unusable password: {user.pk} {email}"
        )
