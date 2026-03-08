"""Server-side Google reCAPTCHA verification helpers."""

from __future__ import annotations

import json
import logging
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


def _normalize_hostname(hostname: str | None) -> str:
    """Normalize request/response hostnames for comparison."""
    value = str(hostname or "").strip().lower()
    if not value:
        return ""
    if value.startswith("[") and "]" in value:
        return value[1:].split("]", 1)[0]
    if value.count(":") == 1:
        return value.split(":", 1)[0]
    return value


def recaptcha_enabled() -> bool:
    """Return True when reCAPTCHA verification is enabled and configured."""
    return bool(
        getattr(settings, "RECAPTCHA_ENABLED", False)
        and getattr(settings, "RECAPTCHA_SITE_KEY", "")
        and getattr(settings, "RECAPTCHA_SECRET_KEY", "")
    )


def verify_recaptcha_response(
    response_token: str,
    remote_ip: str | None = None,
    request_host: str | None = None,
) -> bool:
    """Verify a reCAPTCHA response token with Google's verification API."""
    if not recaptcha_enabled():
        return True

    token = (response_token or "").strip()
    if not token:
        logger.warning("reCAPTCHA verification failed: missing response token")
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
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("reCAPTCHA verification request failed: %s", exc)
        return False

    if not bool(parsed.get("success")):
        logger.warning("reCAPTCHA verification rejected by Google: %s", parsed)
        return False

    expected_hosts = getattr(settings, "RECAPTCHA_EXPECTED_HOSTNAMES", ())
    if expected_hosts:
        response_hostname = _normalize_hostname(parsed.get("hostname", ""))
        allowed = {_normalize_hostname(host) for host in expected_hosts if str(host).strip()}
        if not response_hostname or response_hostname not in allowed:
            logger.warning(
                "reCAPTCHA hostname mismatch: response=%r request=%r allowed=%r",
                response_hostname,
                _normalize_hostname(request_host),
                sorted(host for host in allowed if host),
            )
            return False

    return True
