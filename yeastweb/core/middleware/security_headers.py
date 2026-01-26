"""Middleware for setting security-related response headers."""

from __future__ import annotations

from typing import Callable, Iterable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


def _format_sources(sources: Iterable[str]) -> str:
    """Format a list of CSP sources into a directive string.

    Args:
        sources: Iterable of CSP source values.

    Returns:
        A space-delimited string of sources.
    """
    return " ".join(sources)


class ContentSecurityPolicyMiddleware:
    """Attach CSP and optional Permissions-Policy headers to responses."""

    def __init__(self, get_response):
        """Initialize the middleware and build the CSP policy.

        Args:
            get_response: Django's next middleware or view callable.
        """
        self.get_response = get_response
        self.policy = self._build_policy()
        self.enable_headers = getattr(settings, "SECURITY_HEADERS_ENABLED", True)
        self.permissions_policy = getattr(settings, "SECURITY_PERMISSIONS_POLICY", "")

    def __call__(self, request):
        """Handle the request and append security headers to the response.

        Args:
            request: Incoming Django request.

        Returns:
            The response with security headers applied when absent.
        """
        response = self.get_response(request)
        if not (
            response.has_header("Content-Security-Policy")
            or response.has_header("Content-Security-Policy-Report-Only")
        ):
            response["Content-Security-Policy"] = self.policy
        if self.enable_headers and self.permissions_policy:
            if not response.has_header("Permissions-Policy"):
                response["Permissions-Policy"] = self.permissions_policy
        return response

    def _build_policy(self):
        """Build the CSP header value from settings.

        Returns:
            A fully formatted CSP policy string.
        """
        directives = {
            "default-src": _format_sources(getattr(settings, "CSP_DEFAULT_SRC", ("'self'",))),
            "script-src": _format_sources(getattr(settings, "CSP_SCRIPT_SRC", ("'self'",))),
            "style-src": _format_sources(getattr(settings, "CSP_STYLE_SRC", ("'self'",))),
            "img-src": _format_sources(getattr(settings, "CSP_IMG_SRC", ("'self'",))),
            "font-src": _format_sources(getattr(settings, "CSP_FONT_SRC", ("'self'",))),
            "connect-src": _format_sources(getattr(settings, "CSP_CONNECT_SRC", ("'self'",))),
            "frame-ancestors": _format_sources(getattr(settings, "CSP_FRAME_ANCESTORS", ("'self'",))),
            "base-uri": _format_sources(getattr(settings, "CSP_BASE_URI", ("'self'",))),
            "form-action": _format_sources(getattr(settings, "CSP_FORM_ACTION", ("'self'",))),
            "object-src": _format_sources(getattr(settings, "CSP_OBJECT_SRC", ("'none'",))),
        }
        parts = []
        for directive, value in directives.items():
            if value:
                parts.append(f"{directive} {value}")
        return "; ".join(parts)
