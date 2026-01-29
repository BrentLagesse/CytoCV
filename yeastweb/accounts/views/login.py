"""Authentication views for login and logout."""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from core.security.rate_limit import (
    build_rate_limit_keys,
    check_rate_limit,
    get_client_ip,
    register_failure,
    reset_limits,
)


@ensure_csrf_cookie
def auth_login(request: HttpRequest) -> HttpResponse:
    """Handle login with optional rate limiting and feedback."""
    rate_limit_cfg = getattr(settings, "SECURITY_RATE_LIMIT", {})
    rate_limit_enabled = getattr(settings, "SECURITY_RATE_LIMIT_ENABLED", False)
    mode = rate_limit_cfg.get("mode", "sliding")
    lockout_schedule = rate_limit_cfg.get(
        "lockout_schedule", [60, 180, 300, 600, 1800, 3600]
    )
    max_attempts = int(rate_limit_cfg.get("max_attempts", 5))
    window_seconds = int(rate_limit_cfg.get("window_seconds", 300))

    def render_login(
        rate_limit_active: bool = False,
        retry_after: int = 0,
        login_failed: bool = False,
    ) -> TemplateResponse:
        """Render the login page with rate-limit context."""
        return TemplateResponse(
            request,
            "registration/login.html",
            {
                "rate_limit_active": rate_limit_active,
                "rate_limit_retry_after": retry_after,
                "login_failed": login_failed,
            },
        )

    def redirect_login() -> HttpResponse:
        """Redirect back to the login page."""
        return redirect("login")

    ip = get_client_ip(request)

    if request.method == "POST":
        username = request.POST.get("username") or ""
        password = request.POST.get("password") or ""
        keys = build_rate_limit_keys(ip, username)
        request.session["login_last_username"] = username

        if rate_limit_enabled:
            limited, retry_after, _ = check_rate_limit(
                keys, max_attempts, window_seconds, lockout_schedule, mode
            )
            if limited:
                return redirect_login()

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if rate_limit_enabled:
                reset_limits(keys)
            login(request, user)
            return redirect("profile")

        if rate_limit_enabled:
            register_failure(
                keys, max_attempts, window_seconds, lockout_schedule, mode
            )
            limited, retry_after, _ = check_rate_limit(
                keys, max_attempts, window_seconds, lockout_schedule, mode
            )
            if limited:
                return redirect_login()

        messages.error(request, "Invalid credentials.", extra_tags="login-error")
        request.session["login_failed"] = True
        return redirect_login()

    login_failed = bool(request.session.pop("login_failed", False))
    if rate_limit_enabled:
        last_username = request.session.get("login_last_username", "")
        keys = build_rate_limit_keys(ip, last_username)
        limited, retry_after, _ = check_rate_limit(
            keys, max_attempts, window_seconds, lockout_schedule, mode
        )
        if limited:
            return render_login(
                rate_limit_active=True,
                retry_after=retry_after,
                login_failed=login_failed,
            )

    return render_login(login_failed=login_failed)


def auth_logout(request: HttpRequest) -> HttpResponse:
    """Log out the current user and return to the homepage."""
    logout(request)
    return redirect("homepage")
