"""Backfill allauth EmailAddress aliases from CustomUser.email."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from accounts.email_addresses import (
    normalize_account_email,
    sync_user_email_address,
)


class Command(BaseCommand):
    """Backfill the allauth alias table from the canonical account email field."""

    help = "Create or repair django-allauth EmailAddress aliases for users."

    def add_arguments(self, parser):
        """Register optional email filter and dry-run mode."""

        parser.add_argument(
            "--email",
            help="Limit sync to one user email address, matched case-insensitively.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        """Backfill allauth aliases while reporting skipped/conflicting rows."""

        target_email = normalize_account_email(options.get("email"))
        dry_run = bool(options.get("dry_run"))
        user_model = get_user_model()

        users = user_model.objects.all()
        if target_email:
            # Email filters are case-insensitive to match login and recovery
            # lookup behavior.
            users = users.filter(email__iexact=target_email)
        elif options.get("email") is not None:
            raise CommandError("--email cannot be blank.")

        counts = {
            "users_scanned": 0,
            "aliases_created": 0,
            "aliases_already_present": 0,
            "aliases_updated": 0,
            "skipped_users": 0,
            "conflicts": 0,
        }
        conflict_lines: list[str] = []

        for user in users.order_by("email", "pk").iterator():
            # Iterator use keeps the command safe for larger deployments while
            # sync_user_email_address owns per-user mutation/transaction rules.
            counts["users_scanned"] += 1
            result = sync_user_email_address(
                user,
                verified=True,
                primary=True,
                dry_run=dry_run,
            )
            if result.conflict:
                counts["conflicts"] += 1
                conflict_lines.append(
                    f"{result.normalized_email}: user {user.pk} conflicts with "
                    f"EmailAddress {getattr(result.email_address, 'pk', '')}"
                )
            elif result.skipped:
                counts["skipped_users"] += 1
            elif result.created:
                counts["aliases_created"] += 1
            elif result.updated:
                counts["aliases_updated"] += 1
            elif result.already_present:
                counts["aliases_already_present"] += 1

        prefix = "DRY RUN: " if dry_run else ""
        for key, value in counts.items():
            self.stdout.write(f"{prefix}{key}: {value}")

        if conflict_lines:
            self.stdout.write("conflict details:")
            for line in conflict_lines:
                self.stdout.write(f"- {line}")

        if target_email and counts["users_scanned"] == 0:
            self.stdout.write(f"No user found for {target_email}.")
