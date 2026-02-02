"""Signup view with email verification code flow."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.core.mail import EmailMessage
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone

from .forms import SignupForm

VERIFY_CODE_TTL_SECONDS = 10 * 60
VERIFY_CODE_MAX_ATTEMPTS = 5


def _generate_verify_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _clear_verify_session(request: HttpRequest) -> None:
    for key in ("verify_code", "verify_email", "verify_code_sent_at", "verify_code_attempts"):
        request.session.pop(key, None)


def _render_signup(
    request: HttpRequest,
    form: SignupForm,
    *,
    error: str | None = None,
    notice: str | None = None,
) -> HttpResponse:
    context = {"form": form}
    if error:
        context["error"] = error
    if notice:
        context["notice"] = notice
    return TemplateResponse(request, "registration/signup.html", context)


def signup(request: HttpRequest) -> HttpResponse:
    """Handle signup form submission and email verification."""
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            if 'submit' in request.POST:
                code = (form.cleaned_data.get('verify_code') or "").strip()
                if not code:
                    return _render_signup(request, form, error="Please enter the 6-digit code")

                stored_code = request.session.get("verify_code")
                stored_email = request.session.get("verify_email")
                sent_at = request.session.get("verify_code_sent_at")
                attempts = int(request.session.get("verify_code_attempts", 0))

                if not stored_code or not stored_email or not sent_at:
                    return _render_signup(request, form, error="Please send a verification code")

                submitted_email = (form.cleaned_data.get("email") or "").strip().lower()
                if stored_email.strip().lower() != submitted_email:
                    return _render_signup(
                        request,
                        form,
                        error="Verification code was sent to a different email. Please resend.",
                    )

                now_ts = int(timezone.now().timestamp())
                if now_ts - int(sent_at) > VERIFY_CODE_TTL_SECONDS:
                    _clear_verify_session(request)
                    return _render_signup(request, form, error="Verification code expired. Please resend.")

                if attempts >= VERIFY_CODE_MAX_ATTEMPTS:
                    _clear_verify_session(request)
                    return _render_signup(request, form, error="Too many attempts. Please resend.")

                if secrets.compare_digest(code, stored_code):
                    form.save()
                    _clear_verify_session(request)
                    return redirect('login')

                attempts += 1
                request.session["verify_code_attempts"] = attempts
                if attempts >= VERIFY_CODE_MAX_ATTEMPTS:
                    _clear_verify_session(request)
                    return _render_signup(request, form, error="Too many attempts. Please resend.")
                return _render_signup(request, form, error="Invalid verification code.")

            if 'send_code' in request.POST:
                verify_code = _generate_verify_code()
                email = (form.cleaned_data.get('email') or "").strip()
                request.session['verify_code'] = verify_code
                request.session['verify_email'] = email
                request.session['verify_code_sent_at'] = int(timezone.now().timestamp())
                request.session['verify_code_attempts'] = 0

                message = (
                    f"Your verification code is {verify_code}.\n"
                    f"This code expires in {VERIFY_CODE_TTL_SECONDS // 60} minutes.\n"
                    "If you did not request this email, you can ignore it."
                )

                from_email = getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER)
                reply_to = getattr(settings, "EMAIL_REPLY_TO", None)
                reply_to_list = [reply_to] if reply_to else None

                email_message = EmailMessage(
                    "Yeast Analysis Tools verification code",
                    message,
                    from_email,
                    [email],
                    reply_to=reply_to_list,
                )
                email_message.send(fail_silently=False)

                return _render_signup(request, form, notice="Code sent to your email.")
        return _render_signup(request, form)

    form = SignupForm()
    return _render_signup(request, form)
