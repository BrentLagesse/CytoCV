"""Template context helpers for account security policy."""

from django.conf import settings


def auth_verification_policy(request):
    """Expose account verification expiry copy to auth templates."""
    minutes = settings.AUTH_VERIFICATION_EXPIRY_MINUTES
    label = "1 minute" if minutes == 1 else f"{minutes} minutes"
    return {
        "auth_verification_expiry_label": label,
        "auth_verification_expiry_minutes": minutes,
    }
