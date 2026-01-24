from django.conf import settings


def _format_sources(sources):
    return " ".join(sources)


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.policy = self._build_policy()

    def __call__(self, request):
        response = self.get_response(request)
        if not (
            response.has_header("Content-Security-Policy")
            or response.has_header("Content-Security-Policy-Report-Only")
        ):
            response["Content-Security-Policy"] = self.policy
        return response

    def _build_policy(self):
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
