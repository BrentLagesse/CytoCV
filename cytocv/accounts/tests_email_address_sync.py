"""Account email alias synchronization and login/reset compatibility tests."""

from __future__ import annotations

from io import StringIO

from allauth.account.models import EmailAddress
from django.contrib.auth import authenticate, get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.email_addresses import (
    EmailAddressConflictError,
    ensure_user_email_address,
    normalize_account_email,
    sync_user_email_address,
)


def create_legacy_user(email: str, password: str | None = "TestPass123!", **extra):
    """Create a user before signal-driven allauth alias repair is applied."""

    user_model = get_user_model()
    user = user_model(email=email, **extra)
    if password is None:
        user.set_unusable_password()
    else:
        user.set_password(password)
    user._skip_email_address_sync = True
    user.save()
    return user


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    RECAPTCHA_ENABLED=False,
)
class EmailAddressSyncTests(TestCase):
    """Verify CustomUser.email and allauth EmailAddress stay in sync."""

    def test_normalize_account_email_strips_lowercases_and_blanks_null(self):
        # Normalization is the first account-enumeration safety layer: every
        # lookup path compares canonical lower-case emails.
        self.assertEqual(
            normalize_account_email("  Researcher@Example.EDU  "),
            "researcher@example.edu",
        )
        self.assertEqual(normalize_account_email("  "), "")
        self.assertEqual(normalize_account_email(None), "")

    def test_existing_user_missing_alias_gets_repaired(self):
        # Legacy users may predate allauth EmailAddress aliases; the command
        # backfills the alias without changing the CustomUser primary key.
        user = create_legacy_user("active-user@example.edu")
        self.assertFalse(EmailAddress.objects.filter(user=user).exists())

        call_command(
            "sync_user_email_addresses",
            "--email",
            "active-user@example.edu",
            stdout=StringIO(),
        )

        alias = EmailAddress.objects.get(email="active-user@example.edu")
        self.assertEqual(alias.user, user)
        self.assertEqual(alias.email, "active-user@example.edu")
        self.assertTrue(alias.verified)
        self.assertTrue(alias.primary)

    def test_helper_dry_run_create_reports_without_mutation(self):
        user = create_legacy_user("dry-run-create@example.edu")

        result = sync_user_email_address(user, dry_run=True)

        self.assertTrue(result.created)
        self.assertEqual(result.message, "would create alias")
        self.assertFalse(EmailAddress.objects.filter(user=user).exists())

    def test_helper_dry_run_update_reports_without_mutation(self):
        user = create_legacy_user("dry-run-update@example.edu")
        alias = EmailAddress.objects.create(
            user=user,
            email="dry-run-update@example.edu",
            verified=False,
            primary=False,
        )

        result = sync_user_email_address(user, dry_run=True)

        self.assertTrue(result.updated)
        self.assertEqual(result.message, "would update alias")
        alias.refresh_from_db()
        self.assertFalse(alias.verified)
        self.assertFalse(alias.primary)

    def test_sync_command_dry_run_reports_without_creating_alias(self):
        user = create_legacy_user("dry-run-command@example.edu")

        out = StringIO()
        call_command(
            "sync_user_email_addresses",
            "--email",
            "dry-run-command@example.edu",
            "--dry-run",
            stdout=out,
        )

        self.assertIn("DRY RUN: aliases_created: 1", out.getvalue())
        self.assertFalse(EmailAddress.objects.filter(user=user).exists())

        call_command(
            "sync_user_email_addresses",
            "--email",
            "dry-run-command@example.edu",
            stdout=StringIO(),
        )
        self.assertTrue(EmailAddress.objects.filter(user=user).exists())

    def test_sync_command_is_idempotent_and_reports_already_present(self):
        user = create_legacy_user("idempotent@example.edu")

        first = StringIO()
        second = StringIO()
        call_command("sync_user_email_addresses", "--email", user.email, stdout=first)
        call_command("sync_user_email_addresses", "--email", user.email, stdout=second)

        self.assertIn("aliases_created: 1", first.getvalue())
        self.assertIn("aliases_already_present: 1", second.getvalue())
        self.assertEqual(
            EmailAddress.objects.filter(
                user=user,
                email__iexact="idempotent@example.edu",
            ).count(),
            1,
        )

    def test_sync_command_email_filter_repairs_only_matching_user_case_insensitively(self):
        repaired = create_legacy_user("filter-one@example.edu")
        untouched = create_legacy_user("filter-two@example.edu")

        call_command(
            "sync_user_email_addresses",
            "--email",
            "FILTER-ONE@EXAMPLE.EDU",
            stdout=StringIO(),
        )

        self.assertTrue(EmailAddress.objects.filter(user=repaired).exists())
        self.assertFalse(EmailAddress.objects.filter(user=untouched).exists())

    def test_case_insensitive_existing_alias_is_updated_without_duplicate(self):
        user = create_legacy_user("MixedCase@Example.EDU")
        EmailAddress.objects.create(
            user=user,
            email="mixedcase@example.edu",
            verified=True,
            primary=True,
        )

        call_command(
            "sync_user_email_addresses",
            "--email",
            "mixedcase@example.edu",
            stdout=StringIO(),
        )

        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)
        alias = EmailAddress.objects.get(user=user)
        self.assertEqual(alias.email, "mixedcase@example.edu")
        self.assertTrue(alias.verified)
        self.assertTrue(alias.primary)

    def test_blank_email_is_skipped_by_helper_and_command_summary(self):
        user = create_legacy_user("")

        result = sync_user_email_address(user)
        self.assertTrue(result.skipped)
        self.assertEqual(result.message, "blank email")
        self.assertFalse(EmailAddress.objects.filter(user=user).exists())

        out = StringIO()
        call_command("sync_user_email_addresses", stdout=out)
        self.assertIn("skipped_users: 1", out.getvalue())

    def test_verified_false_policy_can_be_requested_explicitly(self):
        user = create_legacy_user("unverified-policy@example.edu")

        result = sync_user_email_address(user, verified=False)

        self.assertTrue(result.created)
        alias = EmailAddress.objects.get(user=user)
        self.assertFalse(alias.verified)
        self.assertTrue(alias.primary)

    def test_existing_non_primary_alias_is_promoted_and_verified(self):
        user = create_legacy_user("promote-alias@example.edu")
        alias = EmailAddress.objects.create(
            user=user,
            email="promote-alias@example.edu",
            verified=False,
            primary=False,
        )

        result = sync_user_email_address(user)

        self.assertTrue(result.updated)
        alias.refresh_from_db()
        self.assertTrue(alias.verified)
        self.assertTrue(alias.primary)

    def test_conflict_is_reported_without_reassigning_alias(self):
        holder = create_legacy_user("holder@example.edu")
        target = create_legacy_user("conflict@example.edu")
        alias = EmailAddress.objects.create(
            user=holder,
            email="conflict@example.edu",
            verified=True,
            primary=True,
        )

        out = StringIO()
        call_command(
            "sync_user_email_addresses",
            "--email",
            "conflict@example.edu",
            stdout=out,
        )

        alias.refresh_from_db()
        self.assertEqual(alias.user, holder)
        self.assertFalse(
            EmailAddress.objects.filter(
                user=target,
                email__iexact="conflict@example.edu",
            ).exists()
        )
        self.assertIn("conflicts: 1", out.getvalue())

    def test_ensure_user_email_address_raises_on_conflict(self):
        holder = create_legacy_user("conflict-holder@example.edu")
        target = create_legacy_user("ensure-conflict@example.edu")
        EmailAddress.objects.create(
            user=holder,
            email="ensure-conflict@example.edu",
            verified=True,
            primary=True,
        )

        with self.assertRaises(EmailAddressConflictError):
            ensure_user_email_address(target)

    def test_manager_created_user_creates_verified_primary_alias(self):
        user = get_user_model().objects.create_user(
            email="manager-created@example.edu",
            password="TestPass123!",
        )

        alias = EmailAddress.objects.get(user=user)
        self.assertEqual(alias.email, "manager-created@example.edu")
        self.assertTrue(alias.verified)
        self.assertTrue(alias.primary)

    def test_direct_saved_user_creates_verified_primary_alias(self):
        user = get_user_model()(email="AdminCreated@Example.EDU")
        user.set_password("TestPass123!")
        user.save()

        alias = EmailAddress.objects.get(user=user)
        self.assertEqual(user.email, "admincreated@example.edu")
        self.assertEqual(alias.email, "admincreated@example.edu")
        self.assertTrue(alias.verified)
        self.assertTrue(alias.primary)

    def test_user_email_update_normalizes_and_creates_new_primary_alias(self):
        user = get_user_model().objects.create_user(
            email="old-address@example.edu",
            password="TestPass123!",
        )

        user.email = "  Updated-Address@Example.EDU  "
        user.save(update_fields=["email"])

        user.refresh_from_db()
        self.assertEqual(user.email, "updated-address@example.edu")
        new_alias = EmailAddress.objects.get(
            user=user,
            email="updated-address@example.edu",
        )
        old_alias = EmailAddress.objects.get(
            user=user,
            email="old-address@example.edu",
        )
        self.assertTrue(new_alias.primary)
        self.assertFalse(old_alias.primary)

    def test_user_email_update_conflict_does_not_reassign_existing_alias(self):
        holder = get_user_model().objects.create_user(
            email="alias-holder@example.edu",
            password="TestPass123!",
        )
        target = get_user_model().objects.create_user(
            email="email-update-target@example.edu",
            password="TestPass123!",
        )
        conflict_alias = EmailAddress.objects.create(
            user=holder,
            email="blocked-update@example.edu",
            verified=True,
            primary=False,
        )

        target.email = "blocked-update@example.edu"
        target.save(update_fields=["email"])

        conflict_alias.refresh_from_db()
        self.assertEqual(conflict_alias.user, holder)
        self.assertFalse(
            EmailAddress.objects.filter(
                user=target,
                email="blocked-update@example.edu",
            ).exists()
        )

    def test_native_signup_creates_verified_primary_alias(self):
        session = self.client.session
        session["signup_step"] = 4
        session["signup_first_name"] = "Native"
        session["signup_last_name"] = "Signup"
        session["signup_email"] = "native-signup@example.edu"
        session["signup_code_verified"] = True
        session["verify_code_sent_at"] = int(timezone.now().timestamp())
        session.save()

        response = self.client.post(
            reverse("signup"),
            {
                "create_account": "1",
                "password": "TestPass123!",
                "verify_password": "TestPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(email="native-signup@example.edu")
        alias = EmailAddress.objects.get(user=user)
        self.assertTrue(alias.verified)
        self.assertTrue(alias.primary)

    def test_create_or_invite_user_creates_active_user_with_unusable_password_and_alias(self):
        out = StringIO()

        call_command(
            "create_or_invite_user",
            "--email",
            "invited-user@example.edu",
            "--first-name",
            "Invited",
            stdout=out,
        )

        user = get_user_model().objects.get(email="invited-user@example.edu")
        self.assertTrue(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.first_name, "Invited")
        alias = EmailAddress.objects.get(user=user)
        self.assertEqual(alias.email, "invited-user@example.edu")
        self.assertTrue(alias.verified)
        self.assertTrue(alias.primary)
        self.assertIn("Created active user with unusable password", out.getvalue())

    def test_create_or_invite_user_dry_run_does_not_create_user_or_alias(self):
        out = StringIO()

        call_command(
            "create_or_invite_user",
            "--email",
            "dry-run-invite@example.edu",
            "--dry-run",
            stdout=out,
        )

        self.assertIn("Would create active user", out.getvalue())
        self.assertFalse(
            get_user_model().objects.filter(email="dry-run-invite@example.edu").exists()
        )
        self.assertFalse(
            EmailAddress.objects.filter(email="dry-run-invite@example.edu").exists()
        )

    def test_unknown_recovery_email_does_not_create_user_alias_or_send_mail(self):
        response = self.client.post(
            f"{reverse('signin')}?recover=1",
            {
                "flow": "recovery",
                "send_code": "1",
                "email": "missing-user@example.edu",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(
            get_user_model().objects.filter(
                email__iexact="missing-user@example.edu"
            ).exists()
        )
        self.assertFalse(
            EmailAddress.objects.filter(
                email__iexact="missing-user@example.edu"
            ).exists()
        )
        content = response.content.decode()
        self.assertIn("We couldn&#x27;t start password recovery", content)
        self.assertNotIn("We couldn&#x27;t find an account", content)

    def test_recovery_works_after_existing_user_alias_sync_case_insensitively(self):
        user = create_legacy_user(
            "active-recovery@example.edu",
            password="TestPass123!",
            first_name="Active",
        )
        call_command(
            "sync_user_email_addresses",
            "--email",
            "active-recovery@example.edu",
            stdout=StringIO(),
        )

        response = self.client.post(
            f"{reverse('signin')}?recover=1",
            {
                "flow": "recovery",
                "send_code": "1",
                "email": "ACTIVE-RECOVERY@EXAMPLE.EDU",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            self.client.session["recovery_email"],
            "active-recovery@example.edu",
        )
        self.assertTrue(
            EmailAddress.objects.filter(
                user=user,
                email__iexact="active-recovery@example.edu",
                verified=True,
                primary=True,
            ).exists()
        )

    def test_verified_alias_recovery_works(self):
        user = get_user_model().objects.create_user(
            email="provider-primary@example.edu",
            password="TestPass123!",
        )
        EmailAddress.objects.create(
            user=user,
            email="verified-alias@example.edu",
            verified=True,
            primary=False,
        )

        response = self.client.post(
            f"{reverse('signin')}?recover=1",
            {
                "flow": "recovery",
                "send_code": "1",
                "email": "VERIFIED-ALIAS@EXAMPLE.EDU",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            self.client.session["recovery_email"],
            "verified-alias@example.edu",
        )

    def test_unverified_alias_recovery_is_ignored(self):
        user = get_user_model().objects.create_user(
            email="unverified-primary@example.edu",
            password="TestPass123!",
        )
        EmailAddress.objects.create(
            user=user,
            email="unverified-alias@example.edu",
            verified=False,
            primary=False,
        )

        response = self.client.post(
            f"{reverse('signin')}?recover=1",
            {
                "flow": "recovery",
                "send_code": "1",
                "email": "unverified-alias@example.edu",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotIn("recovery_email", self.client.session)

    def test_case_insensitive_direct_login_still_works(self):
        get_user_model().objects.create_user(
            email="login-user@example.edu",
            password="TestPass123!",
        )

        response = self.client.post(
            reverse("signin"),
            {
                "email": "  LOGIN-USER@EXAMPLE.EDU  ",
                "password": "TestPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

    def test_ambiguous_direct_and_alias_match_does_not_authenticate_alias_owner(self):
        direct_user = create_legacy_user(
            "shared-login@example.edu",
            password="DirectPass123!",
        )
        alias_owner = get_user_model().objects.create_user(
            email="alias-owner@example.edu",
            password="AliasPass123!",
        )
        EmailAddress.objects.create(
            user=alias_owner,
            email="shared-login@example.edu",
            verified=True,
            primary=False,
        )

        self.assertIsNone(
            authenticate(email="shared-login@example.edu", password="AliasPass123!")
        )
        self.assertEqual(
            authenticate(email="shared-login@example.edu", password="DirectPass123!"),
            direct_user,
        )
