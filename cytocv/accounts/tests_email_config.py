from django.test import SimpleTestCase, override_settings

from accounts.views.login import _recovery_sender_email
from accounts.views.signup import _sender_email


class AuthEmailSenderConfigTests(SimpleTestCase):
    @override_settings(
        DEFAULT_FROM_EMAIL="cytocv@uw.edu",
        EMAIL_HOST_USER="cytocv",
    )
    def test_auth_flows_prefer_default_from_email_over_smtp_username(self):
        self.assertEqual(_sender_email(), "cytocv@uw.edu")
        self.assertEqual(_recovery_sender_email(), "cytocv@uw.edu")

    @override_settings(
        DEFAULT_FROM_EMAIL="",
        EMAIL_HOST_USER="cytocv",
    )
    def test_auth_flows_fall_back_to_smtp_username_when_from_email_missing(self):
        self.assertEqual(_sender_email(), "cytocv")
        self.assertEqual(_recovery_sender_email(), "cytocv")
