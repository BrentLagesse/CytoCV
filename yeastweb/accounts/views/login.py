from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.decorators.csrf import ensure_csrf_cookie

from core.security.rate_limit import (
    clear_attempts,
    get_rate_limit_state,
    record_failed_attempt,
)


def _rate_limit_config():
    max_attempts = getattr(settings, "LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 15)
    window_seconds = getattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 600)
    if settings.DEBUG:
        window_seconds = getattr(
            settings, "LOGIN_RATE_LIMIT_DEBUG_WINDOW_SECONDS", window_seconds
        )
    return window_seconds, max_attempts

@ensure_csrf_cookie
def auth_login(request):
    window_seconds, max_attempts = _rate_limit_config()
    rate_state = get_rate_limit_state(request, window_seconds, max_attempts)

    if request.method == "POST":
        if rate_state.limited:
            return redirect("login")

        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            clear_attempts(request)
            login(request, user)
            return redirect("profile")

        rate_state = record_failed_attempt(request, window_seconds, max_attempts)
        if rate_state.limited:
            return redirect("login")

        messages.error(request, "Invalid credentials", extra_tags="auto-dismiss login-error")
        return redirect("login")

    rate_state = get_rate_limit_state(request, window_seconds, max_attempts)
    context = {
        "rate_limit_active": rate_state.limited,
        "rate_limit_retry_after": rate_state.retry_after_seconds,
        "rate_limit_reset_at": int(rate_state.reset_at_epoch * 1000),
    }
    return TemplateResponse(request, "registration/login.html", context)

def auth_logout(request):
    logout(request)
    return redirect('homepage')
