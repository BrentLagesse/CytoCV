"""Server-side Google reCAPTCHA verification helpers."""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


def recaptcha_enabled() -> bool:
    """Return True when reCAPTCHA verification is enabled and configured."""
    return bool(
        getattr(settings, "RECAPTCHA_ENABLED", False)
        and getattr(settings, "RECAPTCHA_SITE_KEY", "")
        and getattr(settings, "RECAPTCHA_SECRET_KEY", "")
    )


def verify_recaptcha_response(response_token: str, remote_ip: str | None = None) -> bool:
    """Verify a reCAPTCHA response token with Google's verification API."""
    if not recaptcha_enabled():
        return True

    token = (response_token or "").strip()
    if not token:
        return False

    payload = {
        "secret": settings.RECAPTCHA_SECRET_KEY,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    request_data = urlencode(payload).encode("utf-8")
    request = Request(
        getattr(settings, "RECAPTCHA_VERIFY_URL", "https://www.google.com/recaptcha/api/siteverify"),
        data=request_data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body)
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return False

    if not bool(parsed.get("success")):
        return False

    expected_hosts = getattr(settings, "RECAPTCHA_EXPECTED_HOSTNAMES", ())
    if expected_hosts:
        response_hostname = str(parsed.get("hostname", "")).strip().lower()
        allowed = {str(host).strip().lower() for host in expected_hosts if str(host).strip()}
        if not response_hostname or response_hostname not in allowed:
            return False

    return True
