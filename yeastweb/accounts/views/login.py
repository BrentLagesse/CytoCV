from django.conf import settings
from django.contrib import messages
from django.contrib.messages import get_messages
from django.template.response import TemplateResponse
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect

from core.security.rate_limit import (
    build_rate_limit_keys,
    check_rate_limit,
    get_client_ip,
    register_failure,
    reset_limits,
)

def auth_login(request):
    rate_limit_cfg = getattr(settings, "SECURITY_RATE_LIMIT", {})
    rate_limit_enabled = getattr(settings, "SECURITY_RATE_LIMIT_ENABLED", False)
    mode = rate_limit_cfg.get("mode", "sliding")
    lockout_schedule = rate_limit_cfg.get(
        "lockout_schedule", [60, 180, 300, 600, 1800, 3600]
    )
    max_attempts = int(rate_limit_cfg.get("max_attempts", 5))
    window_seconds = int(rate_limit_cfg.get("window_seconds", 300))

    def render_login(rate_limit_active=False, retry_after=0, login_failed=False):
        return TemplateResponse(
            request,
            "registration/login.html",
            {
                "rate_limit_active": rate_limit_active,
                "rate_limit_retry_after": retry_after,
                "login_failed": login_failed,
            },
        )

    def redirect_login():
        return redirect("login")

    def queue_rate_limit_message(wait_mins: int) -> None:
        storage = get_messages(request)
        kept = []
        for msg in storage:
            if "rate-limit" not in msg.tags.split():
                kept.append(msg)
        for msg in kept:
            messages.add_message(
                request, msg.level, msg.message, extra_tags=msg.tags
            )
        messages.error(
            request,
            f"Too many login attempts. Try again in {wait_mins} minute(s).",
            extra_tags="rate-limit",
        )

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
            wait_mins = max(1, int((retry_after + 59) / 60))
            queue_rate_limit_message(wait_mins)
            return render_login(
                rate_limit_active=True,
                retry_after=retry_after,
                login_failed=login_failed,
            )

    return render_login(login_failed=login_failed)

def auth_logout(request):
    logout(request)
    return redirect('homepage')
