"""Protect account email backend configuration and verification send behavior."""

import time
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from allauth.account.internal.stagekit import LOGIN_SESSION_KEY
from allauth.account.models import EmailAddress, EmailConfirmationHMAC, Login
from allauth.account.stages import EmailVerificationStage

from accounts.email_content import (
    AUTH_EMAIL_LOGO_CID,
    AUTH_EMAIL_LOGO_CID_URL,
    build_email_confirmation_email,
    build_auth_email_logo_src,
    build_auth_email_logo_url,
    normalize_recipient_name,
    _formatted_email_date,
)
from accounts.adapters import CustomAccountAdapter, CustomSocialAccountAdapter
from accounts.views.login import _recovery_sender_email
from accounts.views.login import _recovery_sender_display_email
from accounts.views.login import _build_recovery_email
from accounts.views.login import RECOVERY_CODE_TTL_SECONDS
from accounts.views.signup import _sender_display_email
from accounts.views.signup import _build_verification_email
from accounts.views.signup import _sender_email
from accounts.views.signup import VERIFY_CODE_TTL_SECONDS


class AuthEmailSenderConfigTests(SimpleTestCase):
    @override_settings(
        AUTH_EMAIL_FROM="CytoCV<cytocv-noreply@uw.edu>",
        DEFAULT_FROM_EMAIL="cytocv@uw.edu",
        EMAIL_HOST_USER="cytocv",
    )
    def test_auth_flows_prefer_auth_from_email(self):
        self.assertEqual(_sender_email(), "CytoCV<cytocv-noreply@uw.edu>")
        self.assertEqual(_sender_display_email(), "cytocv-noreply@uw.edu")
        self.assertEqual(
            _recovery_sender_email(),
            "CytoCV<cytocv-noreply@uw.edu>",
        )
        self.assertEqual(
            _recovery_sender_display_email(),
            "cytocv-noreply@uw.edu",
        )

    @override_settings(
        AUTH_EMAIL_FROM="",
        DEFAULT_FROM_EMAIL="cytocv@uw.edu",
        EMAIL_HOST_USER="cytocv",
    )
    def test_auth_flows_fall_back_to_default_from_email(self):
        self.assertEqual(_sender_email(), "cytocv@uw.edu")
        self.assertEqual(_recovery_sender_email(), "cytocv@uw.edu")

    @override_settings(
        AUTH_EMAIL_FROM="",
        DEFAULT_FROM_EMAIL="",
        EMAIL_HOST_USER="cytocv",
    )
    def test_auth_flows_fall_back_to_smtp_username_when_from_email_missing(self):
        self.assertEqual(_sender_email(), "cytocv")
        self.assertEqual(_recovery_sender_email(), "cytocv")


class AuthGlobalMessagingTests(SimpleTestCase):
    def test_global_info_messages_use_success_treatment(self):
        base_css = (
            settings.BASE_DIR / "core" / "static" / "css" / "base.css"
        ).read_text(encoding="utf-8")
        signin_css = (
            settings.BASE_DIR / "core" / "static" / "css" / "pages" / "signin.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".message.success,\n        .message.info", base_css)
        self.assertIn(".message.info .message-close", base_css)
        self.assertIn("rgba(34, 197, 94, 0.16)", base_css)
        self.assertIn(".message.info", signin_css)
        self.assertIn("rgba(0, 123, 255, 0.2)", signin_css)


class OAuthProviderConfigTests(SimpleTestCase):
    def test_microsoft_provider_requests_account_picker(self):
        provider_settings = settings.SOCIALACCOUNT_PROVIDERS["microsoft"]

        self.assertEqual(
            provider_settings["AUTH_PARAMS"],
            {"prompt": "select_account"},
        )


class AuthVerificationExpiryPolicyTests(SimpleTestCase):
    def test_account_verification_expiry_policy_is_five_minutes(self):
        self.assertEqual(settings.AUTH_VERIFICATION_EXPIRY_MINUTES, 5)
        self.assertEqual(settings.AUTH_VERIFICATION_EXPIRY_SECONDS, 300)
        self.assertEqual(VERIFY_CODE_TTL_SECONDS, 300)
        self.assertEqual(RECOVERY_CODE_TTL_SECONDS, 300)
        self.assertEqual(settings.ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS, 5 / 1440)


class AuthEmailContentTests(SimpleTestCase):
    def test_recipient_name_normalization_drops_placeholder_provider_names(self):
        self.assertEqual(normalize_recipient_name("Ada Lovelace"), "Ada Lovelace")
        self.assertEqual(normalize_recipient_name("  Ada   Lovelace  "), "Ada Lovelace")
        self.assertEqual(normalize_recipient_name(""), "")
        self.assertEqual(normalize_recipient_name("   "), "")
        self.assertEqual(normalize_recipient_name("-"), "")
        self.assertEqual(normalize_recipient_name("--"), "")
        self.assertEqual(normalize_recipient_name("_"), "")
        self.assertEqual(normalize_recipient_name("n/a"), "")

    def test_signup_verification_email_includes_institutional_text_and_html(self):
        email = _build_verification_email(
            code="123456",
            minutes_valid=5,
            subject_prefix="CytoCV",
            recipient_name="Ada",
            logo_url="https://cytocv.uwb.edu/static/assets/UWBSTEM.png",
            sender_email="CytoCV<cytocv-noreply@uw.edu>",
        )

        self.assertEqual(email.subject, "Your CytoCV verification code")
        email_date = _formatted_email_date()
        self.assertIn(f"CytoCV | {email_date}", email.text_body)
        self.assertIn("Your verification code", email.text_body)
        self.assertNotIn("CytoCV Account Verification", email.text_body)
        self.assertIn("Hello Ada,", email.text_body)
        self.assertIn(
            "Enter this verification code to continue signing in to CytoCV:",
            email.text_body,
        )
        self.assertIn("Warning: Do not share this email", email.text_body)
        self.assertIn(
            "University of Washington Bothell will never ask you to share this email or its contents.",
            email.text_body,
        )
        self.assertIn("123456", email.text_body)
        self.assertIn("This code expires in 5 minutes.", email.text_body)
        self.assertNotIn("This code expires in 30 minutes.", email.text_body)
        self.assertIn(
            "If you did not request this code, you can safely ignore this email.",
            email.text_body,
        )
        self.assertIn("CytoCV Account Services", email.text_body)
        self.assertIn("University of Washington Bothell", email.text_body)
        self.assertIn("cytocv-noreply@uw.edu", email.text_body)
        self.assertNotIn("CytoCV<cytocv-noreply@uw.edu>", email.text_body)
        self.assertIn(
            "School of Science, Technology, Engineering & Mathematics",
            email.text_body,
        )
        self.assertIn("Department of Computing & Software Systems", email.text_body)
        self.assertIn("School of STEM website", email.text_body)
        self.assertNotIn("18115 Campus Way NE", email.text_body)
        self.assertNotIn("UW Bothell campus", email.text_body)
        self.assertNotIn("cytocv-support@uw.edu", email.text_body)
        self.assertIn("CytoCV", email.html_body)
        self.assertIn(email_date, email.html_body)
        self.assertIn("Your verification code", email.html_body)
        self.assertNotIn("CytoCV Account Verification", email.html_body)
        self.assertIn("CytoCV Account Services", email.html_body)
        self.assertIn("123456", email.html_body)
        self.assertIn(
            "Enter this verification code to continue signing in to CytoCV:",
            email.html_body,
        )
        self.assertIn("&#9888;", email.html_body)
        self.assertIn("Do not share this email", email.html_body)
        self.assertIn(
            "University of Washington Bothell will never ask you to share this email or its contents.",
            email.html_body,
        )
        self.assertIn("This code expires in 5 minutes.", email.html_body)
        self.assertNotIn("This code expires in 30 minutes.", email.html_body)
        self.assertIn(
            "If you did not request this code, you can safely ignore this email.",
            email.html_body,
        )
        self.assertIn(
            "This is an automated account security email from cytocv-noreply@uw.edu.",
            email.html_body,
        )
        self.assertIn("Department of Computing &amp; Software Systems", email.html_body)
        self.assertIn("School of STEM website", email.html_body)
        self.assertNotIn("CytoCV&lt;cytocv-noreply@uw.edu&gt;", email.html_body)
        self.assertNotIn("18115 Campus Way NE", email.html_body)
        self.assertNotIn("UW Bothell campus", email.html_body)
        self.assertIn(
            'alt="University of Washington Bothell School of STEM"',
            email.html_body,
        )

    def test_recovery_email_includes_security_note_and_footer(self):
        email = _build_recovery_email(
            code="654321",
            minutes_valid=5,
            recipient_name="Grace",
            logo_url="https://cytocv.uwb.edu/static/assets/UWBSTEM.png",
            sender_email="cytocv-noreply@uw.edu",
        )

        self.assertEqual(email.subject, "Your CytoCV password reset code")
        self.assertIn("Your verification code", email.text_body)
        self.assertNotIn("CytoCV Password Reset Verification", email.text_body)
        self.assertIn(
            "Enter this verification code to reset your CytoCV password:",
            email.text_body,
        )
        self.assertIn("Warning: Do not share this email", email.text_body)
        self.assertIn("654321", email.text_body)
        self.assertIn("This code expires in 5 minutes.", email.text_body)
        self.assertNotIn("This code expires in 30 minutes.", email.text_body)
        self.assertIn(
            "If you did not request this code, you can safely ignore this email.",
            email.text_body,
        )
        self.assertIn("CytoCV Account Services", email.text_body)
        self.assertIn("Department of Computing & Software Systems", email.text_body)
        self.assertIn("University of Washington Bothell", email.html_body)
        self.assertIn("cytocv-noreply@uw.edu", email.html_body)
        self.assertIn("654321", email.html_body)
        self.assertIn("Your verification code", email.html_body)
        self.assertNotIn("CytoCV Password Reset Verification", email.html_body)
        self.assertIn(
            "Enter this verification code to reset your CytoCV password:",
            email.html_body,
        )
        self.assertIn("Do not share this email", email.html_body)
        self.assertIn(
            "If you did not request this code, you can safely ignore this email.",
            email.html_body,
        )
        self.assertIn("Department of Computing &amp; Software Systems", email.html_body)
        self.assertIn("School of STEM website", email.html_body)
        self.assertNotIn("18115 Campus Way NE", email.html_body)
        self.assertNotIn("UW Bothell campus", email.html_body)

    @override_settings(PUBLIC_BASE_URL="https://cytocv.uwb.edu")
    def test_logo_url_prefers_public_base_url(self):
        request = RequestFactory().get("/signup/")

        self.assertEqual(
            build_auth_email_logo_url(request),
            "https://cytocv.uwb.edu/static/assets/UWBSTEM.png",
        )

    def test_logo_src_prefers_inline_content_id_when_asset_is_available(self):
        request = RequestFactory().get("/signup/")

        self.assertEqual(build_auth_email_logo_src(request), AUTH_EMAIL_LOGO_CID_URL)

    def test_email_confirmation_email_includes_link_cta_and_institutional_footer(self):
        email = build_email_confirmation_email(
            activate_url="https://cytocv.uwb.edu/signin/oauth/confirm-email/key/",
            minutes_valid=5,
            recipient_email="ada@example.com",
            recipient_name="Ada",
            logo_url="https://cytocv.uwb.edu/static/assets/UWBSTEM.png",
            sender_email="CytoCV<cytocv-noreply@uw.edu>",
        )

        self.assertEqual(email.subject, "Verify your CytoCV email address")
        self.assertIn("Verify your email address", email.text_body)
        self.assertIn("Hello Ada,", email.text_body)
        self.assertIn(
            "Open the secure link below to verify your email address and finish signing in to CytoCV.",
            email.text_body,
        )
        self.assertIn("Verify email address:", email.text_body)
        self.assertIn(
            "https://cytocv.uwb.edu/signin/oauth/confirm-email/key/",
            email.text_body,
        )
        self.assertIn("This verification link expires in 5 minutes.", email.text_body)
        self.assertNotIn("This verification link expires in 3 days.", email.text_body)
        self.assertIn("If you did not request this email, you can safely ignore it.", email.text_body)
        self.assertIn("Warning: Do not share this email", email.text_body)
        self.assertIn(
            "University of Washington Bothell will never ask you to share this email or its contents.",
            email.text_body,
        )
        self.assertIn("Email address: ada@example.com", email.text_body)
        self.assertIn("cytocv-noreply@uw.edu", email.text_body)
        self.assertNotIn("CytoCV<cytocv-noreply@uw.edu>", email.text_body)
        self.assertIn("CytoCV Account Services", email.text_body)
        self.assertIn("Department of Computing & Software Systems", email.text_body)
        self.assertNotIn("18115 Campus Way NE", email.text_body)
        self.assertIn("Verify email address", email.html_body)
        self.assertIn(
            "https://cytocv.uwb.edu/signin/oauth/confirm-email/key/",
            email.html_body,
        )
        self.assertIn("This verification link expires in 5 minutes.", email.html_body)
        self.assertNotIn("This verification link expires in 3 days.", email.html_body)
        self.assertIn("If you did not request this email, you can safely ignore it.", email.html_body)
        self.assertIn("Do not share this email", email.html_body)
        self.assertIn("ada@example.com", email.html_body)
        self.assertIn("Department of Computing &amp; Software Systems", email.html_body)
        self.assertIn("School of STEM website", email.html_body)
        self.assertIn(
            "This is an automated account security email from cytocv-noreply@uw.edu.",
            email.html_body,
        )
        self.assertNotIn("CytoCV&lt;cytocv-noreply@uw.edu&gt;", email.html_body)
        self.assertNotIn("18115 Campus Way NE", email.html_body)

    def test_confirmation_email_uses_plain_greeting_for_placeholder_name(self):
        email = build_email_confirmation_email(
            activate_url="https://cytocv.uwb.edu/signin/oauth/confirm-email/key/",
            minutes_valid=5,
            recipient_email="placeholder@example.com",
            recipient_name="-",
            logo_url="https://cytocv.uwb.edu/static/assets/UWBSTEM.png",
            sender_email="CytoCV<cytocv-noreply@uw.edu>",
        )

        self.assertIn("Hello,", email.text_body)
        self.assertNotIn("Hello -,", email.text_body)
        self.assertIn("Hello,", email.html_body)
        self.assertNotIn("Hello -,", email.html_body)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SUPPORT_EMAIL="cytocv@uw.edu",
    AUTH_EMAIL_FROM="CytoCV<cytocv-noreply@uw.edu>",
    PUBLIC_BASE_URL="https://cytocv.uwb.edu",
    RECAPTCHA_ENABLED=False,
)
class AuthEmailViewSendTests(TestCase):
    def test_signup_send_code_sends_multipart_email(self):
        response = self.client.post(
            f"{reverse('signup')}?fresh=1",
            {
                "send_code": "1",
                "email": "new-user@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.from_email, "CytoCV<cytocv-noreply@uw.edu>")
        self.assertEqual(message.reply_to, ["CytoCV<cytocv-noreply@uw.edu>"])
        self.assertEqual(message.subject, "Your CytoCV verification code")
        self.assertIn(
            "Enter this verification code to continue signing in to CytoCV:",
            message.body,
        )
        self.assertIn("Warning: Do not share this email", message.body)
        self.assertIn("This code expires in 5 minutes.", message.body)
        self.assertNotIn("This code expires in 30 minutes.", message.body)
        self.assertIn(
            "If you did not request this code, you can safely ignore this email.",
            message.body,
        )
        self.assertIn("cytocv-noreply@uw.edu", message.body)
        self.assertNotIn("CytoCV<cytocv-noreply@uw.edu>", message.body)
        self.assertIn("CytoCV Account Services", message.body)
        self.assertIn("Department of Computing & Software Systems", message.body)
        self.assertNotIn("cytocv@uw.edu", message.body)
        content = response.content.decode()
        self.assertIn("from <strong>cytocv-noreply@uw.edu</strong>", content)
        self.assertIn("This code expires in 5 minutes.", content)
        self.assertNotIn("This code expires in 30 minutes.", content)
        self.assertNotIn("CytoCV&lt;cytocv-noreply@uw.edu&gt;", content)
        self.assertEqual(len(message.alternatives), 1)
        html_body, mime_type = message.alternatives[0]
        self.assertEqual(mime_type, "text/html")
        self.assertIn(AUTH_EMAIL_LOGO_CID_URL, html_body)
        self.assertIn("University of Washington Bothell", html_body)
        self.assertIn("CytoCV Account Services", html_body)
        self.assertIn("Department of Computing &amp; Software Systems", html_body)
        self.assertIn("Do not share this email", html_body)
        self.assertNotIn("CytoCV&lt;cytocv-noreply@uw.edu&gt;", html_body)
        self.assertNotIn("18115 Campus Way NE", html_body)
        self.assertNotIn("UW Bothell campus", html_body)
        self.assertTrue(
            any(
                attachment.get("Content-ID") == f"<{AUTH_EMAIL_LOGO_CID}>"
                for attachment in message.attachments
            )
        )

    def test_recovery_send_code_sends_multipart_email(self):
        get_user_model().objects.create_user(
            email="recover@example.com",
            password="TestPass123!",
            first_name="Grace",
        )

        response = self.client.post(
            f"{reverse('signin')}?recover=1",
            {
                "flow": "recovery",
                "send_code": "1",
                "email": "recover@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.from_email, "CytoCV<cytocv-noreply@uw.edu>")
        self.assertEqual(message.reply_to, ["CytoCV<cytocv-noreply@uw.edu>"])
        self.assertEqual(message.subject, "Your CytoCV password reset code")
        self.assertIn(
            "Enter this verification code to reset your CytoCV password:",
            message.body,
        )
        self.assertIn("Warning: Do not share this email", message.body)
        self.assertIn("This code expires in 5 minutes.", message.body)
        self.assertNotIn("This code expires in 30 minutes.", message.body)
        self.assertIn(
            "If you did not request this code, you can safely ignore this email.",
            message.body,
        )
        content = response.content.decode()
        self.assertIn("from <strong>cytocv-noreply@uw.edu</strong>", content)
        self.assertIn("The code expires in 5 minutes.", content)
        self.assertNotIn("This code expires in 30 minutes.", content)
        self.assertNotIn("CytoCV&lt;cytocv-noreply@uw.edu&gt;", content)
        self.assertEqual(len(message.alternatives), 1)
        html_body, mime_type = message.alternatives[0]
        self.assertEqual(mime_type, "text/html")
        self.assertIn(AUTH_EMAIL_LOGO_CID_URL, html_body)
        self.assertIn(
            "If you did not request this code, you can safely ignore this email.",
            html_body,
        )
        self.assertIn("cytocv-noreply@uw.edu", html_body)
        self.assertNotIn("CytoCV&lt;cytocv-noreply@uw.edu&gt;", html_body)
        self.assertIn("CytoCV Account Services", html_body)
        self.assertIn("Department of Computing &amp; Software Systems", html_body)
        self.assertIn("Do not share this email", html_body)
        self.assertNotIn("18115 Campus Way NE", html_body)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    RECAPTCHA_ENABLED=False,
)
class AuthEmailResolutionTests(TestCase):
    def test_direct_login_normalizes_email_case_and_spaces(self):
        get_user_model().objects.create_user(
            email="researcher@uw.edu",
            password="TestPass123!",
        )

        response = self.client.post(
            reverse("signin"),
            {
                "email": "  Researcher@UW.EDU  ",
                "password": "TestPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

    def test_recovery_finds_verified_provider_email_alias(self):
        user = get_user_model().objects.create_user(
            email="provider-primary@example.com",
            password=None,
            first_name="Pat",
        )
        EmailAddress.objects.create(
            user=user,
            email="Pat.Researcher@UW.EDU",
            verified=True,
        )

        response = self.client.post(
            f"{reverse('signin')}?recover=1",
            {
                "flow": "recovery",
                "send_code": "1",
                "email": "  pat.researcher@uw.edu  ",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn(
            "We couldn't find an account for that email address.",
            response.content.decode(),
        )
        self.assertEqual(self.client.session["recovery_email"], "pat.researcher@uw.edu")

    def test_recovery_ignores_unverified_provider_email_alias(self):
        user = get_user_model().objects.create_user(
            email="unverified-primary@example.com",
            password=None,
        )
        EmailAddress.objects.create(
            user=user,
            email="unverified-alias@uw.edu",
            verified=False,
        )

        response = self.client.post(
            f"{reverse('signin')}?recover=1",
            {
                "flow": "recovery",
                "send_code": "1",
                "email": "unverified-alias@uw.edu",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(
            response,
            "We couldn&#x27;t start password recovery for that email.",
        )

    def test_oauth_only_account_is_not_treated_as_nonexistent_in_recovery(self):
        user = get_user_model().objects.create_user(
            email="oauth-only@uw.edu",
            password=None,
        )
        self.assertFalse(user.has_usable_password())
        EmailAddress.objects.filter(user=user, email="oauth-only@uw.edu").update(
            verified=True,
            primary=True,
        )

        response = self.client.post(
            f"{reverse('signin')}?recover=1",
            {
                "flow": "recovery",
                "send_code": "1",
                "email": "OAUTH-ONLY@UW.EDU",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn(
            "We couldn't find an account for that email address.",
            response.content.decode(),
        )

    def test_signup_rejects_duplicate_email_differing_only_by_case(self):
        get_user_model().objects.create_user(
            email="CaseSensitive@uw.edu",
            password="TestPass123!",
        )

        response = self.client.post(
            f"{reverse('signup')}?fresh=1",
            {
                "send_code": "1",
                "email": "casesensitive@UW.EDU",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(response, "That email is already in use. Sign In instead.")

    def test_social_pre_login_links_existing_user_case_insensitively(self):
        existing_user = get_user_model().objects.create_user(
            email="linked-user@uw.edu",
            password="TestPass123!",
        )

        class FakeSocialLogin:
            is_existing = False

            def __init__(self):
                self.user = get_user_model()(email="  LINKED-USER@UW.EDU  ")
                self.email_addresses = []
                self.connected_user = None

            def connect(self, request, user):
                self.connected_user = user

        sociallogin = FakeSocialLogin()

        CustomSocialAccountAdapter().pre_social_login(
            RequestFactory().get("/signin/oauth/"),
            sociallogin,
        )

        self.assertEqual(sociallogin.connected_user, existing_user)
        self.assertEqual(
            get_user_model().objects.filter(email__iexact="linked-user@uw.edu").count(),
            1,
        )

    def test_inactive_recovery_account_is_not_reset_or_logged_in(self):
        user = get_user_model().objects.create_user(
            email="inactive@uw.edu",
            password="OldPass123!",
            is_active=False,
        )
        session = self.client.session
        session["recovery_step"] = 3
        session["recovery_email"] = "inactive@uw.edu"
        session["recovery_code_verified"] = True
        session["recovery_verify_code_sent_at"] = int(timezone.now().timestamp())
        session.save()

        response = self.client.post(
            f"{reverse('signin')}?recover=1",
            {
                "flow": "recovery",
                "reset_password": "1",
                "password": "NewPass123!",
                "verify_password": "NewPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "We couldn&#x27;t start password recovery for that email.",
        )
        user.refresh_from_db()
        self.assertTrue(user.check_password("OldPass123!"))
        self.assertNotIn("_auth_user_id", self.client.session)


@override_settings(
    ACCOUNT_ADAPTER="accounts.adapters.CustomAccountAdapter",
    ACCOUNT_CONFIRM_EMAIL_ON_GET=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    AUTH_EMAIL_FROM="CytoCV<cytocv-noreply@uw.edu>",
    DEFAULT_FROM_EMAIL="cytocv@uw.edu",
    EMAIL_HOST_USER="cytocv",
    PUBLIC_BASE_URL="https://cytocv.uwb.edu",
    ALLOWED_HOSTS=["testserver", "localhost", "cytocv.uwb.edu"],
)
class AllauthEmailConfirmationTests(TestCase):
    def test_adapter_sends_branded_multipart_confirmation_email(self):
        user = get_user_model().objects.create_user(
            email="oauth-user@example.com",
            password="TestPass123!",
            first_name="Nicolas",
        )
        email_address = EmailAddress.objects.get(
            user=user,
            email="oauth-user@example.com",
        )
        email_address.primary = True
        email_address.verified = False
        email_address.save(update_fields=["primary", "verified"])
        request = RequestFactory().get("/signin/oauth/confirm-email/")

        EmailConfirmationHMAC(email_address).send(request=request, signup=True)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Verify your CytoCV email address")
        self.assertEqual(message.from_email, "CytoCV<cytocv-noreply@uw.edu>")
        self.assertEqual(message.reply_to, ["CytoCV<cytocv-noreply@uw.edu>"])
        self.assertEqual(message.to, ["oauth-user@example.com"])
        self.assertIn("Hello Nicolas,", message.body)
        self.assertIn("Verify email address:", message.body)
        self.assertIn("/signin/oauth/confirm-email/", message.body)
        self.assertIn("This verification link expires in 5 minutes.", message.body)
        self.assertNotIn("This verification link expires in 3 days.", message.body)
        self.assertIn("cytocv-noreply@uw.edu", message.body)
        self.assertNotIn("CytoCV<cytocv-noreply@uw.edu>", message.body)
        self.assertEqual(len(message.alternatives), 1)
        html_body, mime_type = message.alternatives[0]
        self.assertEqual(mime_type, "text/html")
        self.assertIn(AUTH_EMAIL_LOGO_CID_URL, html_body)
        self.assertIn("Verify email address", html_body)
        self.assertIn("/signin/oauth/confirm-email/", html_body)
        self.assertIn("This verification link expires in 5 minutes.", html_body)
        self.assertNotIn("This verification link expires in 3 days.", html_body)
        self.assertIn("Do not share this email", html_body)
        self.assertIn("Department of Computing &amp; Software Systems", html_body)
        self.assertNotIn("18115 Campus Way NE", html_body)
        self.assertTrue(
            any(
                attachment.get("Content-ID") == f"<{AUTH_EMAIL_LOGO_CID}>"
                for attachment in message.attachments
            )
        )

    def test_account_adapter_setting_points_to_custom_adapter(self):
        adapter = CustomAccountAdapter(RequestFactory().get("/"))

        self.assertIsInstance(adapter, CustomAccountAdapter)

    def test_confirmation_email_links_follow_request_host_and_scheme(self):
        local_user = get_user_model().objects.create_user(
            email="local-oauth@example.com",
            password="TestPass123!",
        )
        local_address = EmailAddress.objects.get(
            user=local_user,
            email="local-oauth@example.com",
        )
        local_address.primary = True
        local_address.verified = False
        local_address.save(update_fields=["primary", "verified"])
        local_request = RequestFactory().get(
            "/signin/oauth/confirm-email/",
            HTTP_HOST="localhost:8000",
        )

        EmailConfirmationHMAC(local_address).send(request=local_request, signup=True)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "http://localhost:8000/signin/oauth/confirm-email/",
            mail.outbox[0].body,
        )
        self.assertNotIn("https://cytocv.uwb.edu", mail.outbox[0].body)

        mail.outbox.clear()
        deployed_user = get_user_model().objects.create_user(
            email="deployed-oauth@example.com",
            password="TestPass123!",
        )
        deployed_address = EmailAddress.objects.get(
            user=deployed_user,
            email="deployed-oauth@example.com",
        )
        deployed_address.primary = True
        deployed_address.verified = False
        deployed_address.save(update_fields=["primary", "verified"])
        deployed_request = RequestFactory().get(
            "/signin/oauth/confirm-email/",
            secure=True,
            HTTP_HOST="cytocv.uwb.edu",
        )

        EmailConfirmationHMAC(deployed_address).send(
            request=deployed_request,
            signup=True,
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "https://cytocv.uwb.edu/signin/oauth/confirm-email/",
            mail.outbox[0].body,
        )
        self.assertNotIn("http://localhost:8000", mail.outbox[0].body)

    def test_verification_sent_page_uses_cytocv_auth_card(self):
        response = self.client.get(reverse("account_email_verification_sent"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Check your email", content)
        self.assertIn("secure verification link", content)
        self.assertIn("This verification link expires in 5 minutes.", content)
        self.assertIn(
            "Open the newest email link in this browser to finish signing in.",
            content,
        )
        self.assertIn(
            "Automatic sign-in only works if you open the newest verification link in this same browser session.",
            content,
        )
        self.assertIn("auth-card", content)
        self.assertIn(">Back<", content)
        self.assertIn("I verified", content)
        self.assertIn(reverse("oauth_verification_status"), content)
        self.assertIn("verifiedCheckButton", content)
        self.assertIn("js/pages/account-verification-sent.js", content)
        verification_source = (
            settings.BASE_DIR
            / "core"
            / "static"
            / "js"
            / "pages"
            / "account-verification-sent.js"
        ).read_text(encoding="utf-8")
        self.assertIn("setInterval", verification_source)
        self.assertIn(
            "If you opened it elsewhere, return to sign in again.",
            verification_source,
        )
        self.assertNotIn("Follow the link provided to finalize the signup process", content)

    def test_verification_status_endpoint_reports_anonymous_session_only(self):
        response = self.client.get(reverse("oauth_verification_status"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            response.json(),
            {
                "authenticated": False,
                "redirect_url": "",
            },
        )

    def test_verification_status_endpoint_reports_authenticated_session_redirect(self):
        user = get_user_model().objects.create_user(
            email="signed-in@example.com",
            password="TestPass123!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("oauth_verification_status"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            response.json(),
            {
                "authenticated": True,
                "redirect_url": reverse("dashboard"),
            },
        )

    def test_invalid_confirmation_link_uses_styled_expired_page(self):
        response = self.client.get(reverse("account_confirm_email", args=["invalid-key"]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Verification link expired", content)
        self.assertIn("Back to sign in", content)
        self.assertIn("auth-card", content)
        self.assertNotIn("issue a new email confirmation request", content)

    def test_confirmation_get_resumes_same_session_login_after_verification(self):
        user = get_user_model().objects.create_user(
            email="resume-oauth@example.com",
            password="TestPass123!",
        )
        email_address = EmailAddress.objects.get(
            user=user,
            email="resume-oauth@example.com",
        )
        email_address.primary = True
        email_address.verified = False
        email_address.save(update_fields=["primary", "verified"])
        confirmation = EmailConfirmationHMAC(email_address)
        login = Login(
            user=user,
            email=user.email,
            redirect_url=reverse("dashboard"),
            signup=True,
            state={"stages": {"current": EmailVerificationStage.key}},
        )
        session = self.client.session
        session[LOGIN_SESSION_KEY] = login.serialize()
        session.save()

        response = self.client.get(reverse("account_confirm_email", args=[confirmation.key]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))
        email_address.refresh_from_db()
        self.assertTrue(email_address.verified)

        status_response = self.client.get(reverse("oauth_verification_status"))

        self.assertEqual(
            status_response.json(),
            {
                "authenticated": True,
                "redirect_url": reverse("dashboard"),
            },
        )

    def test_confirmation_get_verifies_email_without_pending_login_session(self):
        user = get_user_model().objects.create_user(
            email="confirm-oauth@example.com",
            password="TestPass123!",
        )
        email_address = EmailAddress.objects.get(
            user=user,
            email="confirm-oauth@example.com",
        )
        email_address.primary = True
        email_address.verified = False
        email_address.save(update_fields=["primary", "verified"])
        confirmation = EmailConfirmationHMAC(email_address)

        response = self.client.get(reverse("account_confirm_email", args=[confirmation.key]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("signin"))
        email_address.refresh_from_db()
        self.assertTrue(email_address.verified)

        status_response = self.client.get(reverse("oauth_verification_status"))

        self.assertEqual(
            status_response.json(),
            {
                "authenticated": False,
                "redirect_url": "",
            },
        )

    def test_confirmation_get_rejects_expired_email_link(self):
        user = get_user_model().objects.create_user(
            email="expired-oauth@example.com",
            password="TestPass123!",
        )
        email_address = EmailAddress.objects.get(
            user=user,
            email="expired-oauth@example.com",
        )
        email_address.primary = True
        email_address.verified = False
        email_address.save(update_fields=["primary", "verified"])
        confirmation = EmailConfirmationHMAC(email_address)
        key = confirmation.key

        with patch("django.core.signing.time.time", return_value=time.time() + 301):
            response = self.client.get(reverse("account_confirm_email", args=[key]))

        self.assertEqual(response.status_code, 200)
        email_address.refresh_from_db()
        self.assertFalse(email_address.verified)
        self.assertIn("Verification link expired", response.content.decode())
