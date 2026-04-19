from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from accounts.email_content import (
    AUTH_EMAIL_LOGO_CID,
    AUTH_EMAIL_LOGO_CID_URL,
    build_auth_email_logo_src,
    build_auth_email_logo_url,
    _formatted_email_date,
)
from accounts.views.login import _recovery_sender_email
from accounts.views.login import _recovery_sender_display_email
from accounts.views.login import _build_recovery_email
from accounts.views.signup import _sender_display_email
from accounts.views.signup import _build_verification_email
from accounts.views.signup import _sender_email


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


class AuthEmailContentTests(SimpleTestCase):
    def test_signup_verification_email_includes_institutional_text_and_html(self):
        email = _build_verification_email(
            code="123456",
            minutes_valid=30,
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
        self.assertIn("This code expires in 30 minutes.", email.text_body)
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
        self.assertIn("This code expires in 30 minutes.", email.html_body)
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
            minutes_valid=30,
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
        self.assertIn("This code expires in 30 minutes.", email.text_body)
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
        self.assertIn("This code expires in 30 minutes.", message.body)
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
        self.assertIn("This code expires in 30 minutes.", message.body)
        self.assertIn(
            "If you did not request this code, you can safely ignore this email.",
            message.body,
        )
        content = response.content.decode()
        self.assertIn("from <strong>cytocv-noreply@uw.edu</strong>", content)
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
