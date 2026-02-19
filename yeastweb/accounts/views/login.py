"""Authentication views for sign-in, password recovery, and logout."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import EmailValidator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from core.security.rate_limit import (
    build_rate_limit_keys,
    check_rate_limit,
    get_client_ip,
    register_failure,
    reset_limits,
)

from .signup import (
    VERIFY_CODE_MAX_ATTEMPTS,
    VERIFY_CODE_RESEND_SECONDS,
    VERIFY_CODE_TTL_SECONDS,
)

RECOVERY_CODE_TTL_SECONDS = VERIFY_CODE_TTL_SECONDS
RECOVERY_CODE_MAX_ATTEMPTS = VERIFY_CODE_MAX_ATTEMPTS
RECOVERY_CODE_RESEND_SECONDS = VERIFY_CODE_RESEND_SECONDS


def _normalize_email(email: str) -> str:
    """Normalize user-provided email input."""
    return email.strip().lower()


def _generate_recovery_code() -> str:
    """Return a cryptographically generated 6-digit verification code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _clear_recovery_verify_session(request: HttpRequest) -> None:
    """Remove password-recovery verification session state."""
    for key in (
        "recovery_verify_code",
        "recovery_verify_code_sent_at",
        "recovery_verify_code_attempts",
        "recovery_verify_code_locked",
    ):
        request.session.pop(key, None)


def _clear_recovery_session(request: HttpRequest) -> None:
    """Clear all password-recovery-related session state."""
    for key in ("recovery_step", "recovery_email", "recovery_code_verified"):
        request.session.pop(key, None)
    _clear_recovery_verify_session(request)


def _expire_recovery_code(request: HttpRequest) -> None:
    """Clear a stale or exhausted verification code."""
    for key in ("recovery_verify_code", "recovery_verify_code_attempts"):
        request.session.pop(key, None)


def _is_recovery_code_active(request: HttpRequest) -> bool:
    """Return True when a recovery code exists and is not expired."""
    stored_code = request.session.get("recovery_verify_code")
    sent_at = request.session.get("recovery_verify_code_sent_at")
    if not stored_code or not sent_at:
        return False
    now_ts = int(timezone.now().timestamp())
    if now_ts - int(sent_at) > RECOVERY_CODE_TTL_SECONDS:
        _expire_recovery_code(request)
        return False
    return True


def _recovery_resend_wait_seconds(request: HttpRequest) -> int:
    """Return seconds remaining before another recovery code can be resent."""
    sent_at = request.session.get("recovery_verify_code_sent_at")
    if not sent_at:
        return 0
    now_ts = int(timezone.now().timestamp())
    remaining = RECOVERY_CODE_RESEND_SECONDS - (now_ts - int(sent_at))
    return max(0, int(remaining))


def _recovery_sender_email() -> str:
    """Return the sender address used for password recovery emails."""
    return settings.EMAIL_HOST_USER


def _add_error(errors: dict[str, list[str]], field: str, message: str) -> None:
    """Append a field-level error message."""
    errors.setdefault(field, []).append(message)


def _summarize_password_errors(messages: list[str]) -> str:
    """Combine password validation messages into a single sentence."""
    flags: set[str] = set()
    extras: list[str] = []
    for message in messages:
        lower_msg = message.lower()
        if "too short" in lower_msg or "at least" in lower_msg:
            flags.add("length")
        elif "too common" in lower_msg or "common password" in lower_msg:
            flags.add("common")
        elif "entirely numeric" in lower_msg:
            flags.add("numeric")
        else:
            extras.append(message.rstrip("."))

    parts: list[str] = []
    if "length" in flags:
        parts.append("be at least 8 characters")
    if "common" in flags:
        parts.append("not be a common password")
    if "numeric" in flags:
        parts.append("not be entirely numeric")

    summary = ""
    if parts:
        if len(parts) == 1:
            summary = f"Password must {parts[0]}."
        elif len(parts) == 2:
            summary = f"Password must {parts[0]} and {parts[1]}."
        else:
            summary = f"Password must {parts[0]}, {parts[1]}, and {parts[2]}."

    if extras:
        extra = extras[0]
        if summary:
            summary = summary.rstrip(".") + f" and {extra}."
        else:
            summary = f"{extra}."

    return summary or "Password is not strong enough."


def _build_recovery_email(
    *,
    code: str,
    minutes_valid: int,
    recipient_name: str | None = None,
) -> tuple[str, str]:
    """Build the password recovery email subject/body pair."""
    safe_name = (recipient_name or "").strip()
    greeting = f"Hello {safe_name},\n\n" if safe_name else "Hello,\n\n"
    subject = f"YeastWeb password reset verification code: {code}"
    body = greeting + (
        f"Your password reset verification code is: {code}\n\n"
        f"The verification code is valid for {minutes_valid} minutes. "
        "Please complete password recovery as soon as possible.\n\n"
        "If you did not request this change, you can ignore this email.\n\n"
        "Kind regards,\n"
        "YeastWeb Team"
    )
    return subject, body


def _render_recovery(
    request: HttpRequest,
    *,
    step: int,
    step_total: int,
    values: dict[str, str],
    errors: dict[str, list[str]],
    page_error: str | None = None,
    code_notice: str | None = None,
    code_sent: bool = False,
    code_verified: bool = False,
    resend_available_in: int = 0,
    code_locked: bool = False,
    sender_email: str | None = None,
    confirm_outline: bool = False,
) -> TemplateResponse:
    """Render the sign-in template in password recovery mode."""
    return TemplateResponse(
        request,
        "registration/login.html",
        {
            "recovery_mode": True,
            "recovery_step": step,
            "recovery_step_total": step_total,
            "recovery_values": values,
            "recovery_errors": errors,
            "recovery_page_error": page_error,
            "recovery_code_notice": code_notice,
            "recovery_code_sent": code_sent,
            "recovery_code_verified": code_verified,
            "recovery_resend_available_in": resend_available_in,
            "recovery_code_locked": code_locked,
            "recovery_sender_email": sender_email,
            "recovery_confirm_outline": confirm_outline,
            "rate_limit_active": False,
            "rate_limit_retry_after": 0,
            "login_failed": False,
        },
    )


def _is_recovery_request(request: HttpRequest) -> bool:
    """Return True when the request targets the recovery flow."""
    return request.POST.get("flow") == "recovery" or request.GET.get("recover") == "1"


def _should_reset_recovery(request: HttpRequest) -> bool:
    """Return True when the password recovery flow should reset."""
    return request.method == "GET" and request.GET.get("fresh") == "1"


def _handle_password_recovery(request: HttpRequest) -> HttpResponse:
    """Handle the multi-step password recovery flow on the sign-in page."""
    if _should_reset_recovery(request):
        _clear_recovery_session(request)

    user_model = get_user_model()
    session = request.session
    step_total = 3
    step = int(session.get("recovery_step", 1))

    values = {
        "email": session.get("recovery_email", ""),
        "verify_code": "",
    }
    errors: dict[str, list[str]] = {}
    page_error = None
    code_notice = None
    confirm_outline = False

    # Normalize computed state derived from the session.
    _is_recovery_code_active(request)
    code_sent = bool(session.get("recovery_verify_code_sent_at"))
    code_verified = bool(session.get("recovery_code_verified", False))
    code_locked = bool(session.get("recovery_verify_code_locked", False))
    resend_available_in = _recovery_resend_wait_seconds(request)
    sender_email = _recovery_sender_email()
    if code_locked:
        values["verify_code"] = ""

    # Keep the step consistent with data already collected.
    if step > 1 and not values["email"]:
        step = 1
    if step > 1 and not session.get("recovery_verify_code_sent_at"):
        step = 1
    if step > 2 and not code_verified:
        step = 2
    session["recovery_step"] = step

    def render_current(**overrides: object) -> HttpResponse:
        """Render the current recovery step with optional overrides."""
        return _render_recovery(
            request,
            step=overrides.get("step", step),
            step_total=step_total,
            values=overrides.get("values", values),
            errors=overrides.get("errors", errors),
            page_error=overrides.get("page_error", page_error),
            code_notice=overrides.get("code_notice", code_notice),
            code_sent=overrides.get("code_sent", code_sent),
            code_verified=overrides.get("code_verified", code_verified),
            resend_available_in=overrides.get(
                "resend_available_in", resend_available_in
            ),
            code_locked=overrides.get("code_locked", code_locked),
            sender_email=overrides.get("sender_email", sender_email),
            confirm_outline=overrides.get("confirm_outline", confirm_outline),
        )

    def send_code_email(email: str, code: str) -> bool:
        """Send a password recovery code email."""
        recipient_name = (
            user_model.objects.filter(email__iexact=email)
            .values_list("first_name", flat=True)
            .first()
            or ""
        )
        subject, message = _build_recovery_email(
            code=code,
            minutes_valid=RECOVERY_CODE_TTL_SECONDS // 60,
            recipient_name=recipient_name,
        )
        from_email = settings.EMAIL_HOST_USER
        reply_to = getattr(settings, "EMAIL_REPLY_TO", None)
        reply_to_list = [reply_to] if reply_to else None
        try:
            email_message = EmailMessage(
                subject,
                message,
                from_email,
                [email],
                reply_to=reply_to_list,
            )
            email_message.send(fail_silently=False)
            return True
        except Exception:
            return False

    if request.method == "POST":
        # Navigation controls do not perform field validation.
        if "cancel_recovery" in request.POST:
            _clear_recovery_session(request)
            return redirect("signin")
        if "back_email" in request.POST:
            _clear_recovery_verify_session(request)
            session.pop("recovery_code_verified", None)
            session["recovery_step"] = 1
            step = 1
            return render_current()
        if "back_code" in request.POST:
            session["recovery_step"] = 2
            step = 2
            return render_current()

        if "send_code" in request.POST:
            # Step 1: validate email, then send a verification code.
            values["email"] = _normalize_email(request.POST.get("email") or "")
            session["recovery_email"] = values["email"]
            session.pop("recovery_code_verified", None)
            session.pop("recovery_verify_code_locked", None)

            if not values["email"]:
                _add_error(errors, "email", "Enter a valid email address")
            else:
                try:
                    EmailValidator()(values["email"])
                except ValidationError:
                    _add_error(errors, "email", "Enter a valid email address")
                else:
                    if not user_model.objects.filter(email__iexact=values["email"]).exists():
                        _add_error(errors, "email", "No account was found for that email.")
                        page_error = "No account was found for that email."
                        values["email"] = ""
                        session.pop("recovery_email", None)

            if errors:
                step = 1
                return render_current()

            if _recovery_resend_wait_seconds(request) > 0:
                page_error = "Please wait before requesting another verification code."
                step = 1
                resend_available_in = _recovery_resend_wait_seconds(request)
                return render_current()

            verify_code = _generate_recovery_code()
            if not send_code_email(values["email"], verify_code):
                page_error = "Something went wrong. Try again."
                step = 1
                return render_current()

            session["recovery_verify_code"] = verify_code
            session["recovery_verify_code_sent_at"] = int(timezone.now().timestamp())
            session["recovery_verify_code_attempts"] = 0
            code_notice = f"Verification code sent to {values['email']}."
            code_sent = True
            resend_available_in = RECOVERY_CODE_RESEND_SECONDS
            code_locked = False
            values["verify_code"] = ""
            session["recovery_step"] = 2
            step = 2
            return render_current()

        if "resend_code" in request.POST:
            # Step 2: resend generates a new code and invalidates the old one.
            values["email"] = session.get("recovery_email", values["email"])
            if not values["email"]:
                session["recovery_step"] = 1
                step = 1
                return render_current()

            resend_available_in = _recovery_resend_wait_seconds(request)
            if resend_available_in > 0:
                page_error = "Please wait before requesting another verification code."
                step = 2
                return render_current()

            verify_code = _generate_recovery_code()
            if not send_code_email(values["email"], verify_code):
                page_error = "Something went wrong. Try again."
                step = 2
                return render_current()

            session["recovery_verify_code"] = verify_code
            session["recovery_verify_code_sent_at"] = int(timezone.now().timestamp())
            session["recovery_verify_code_attempts"] = 0
            session.pop("recovery_code_verified", None)
            session.pop("recovery_verify_code_locked", None)
            code_notice = f"Verification code resent to {values['email']}."
            code_sent = True
            resend_available_in = RECOVERY_CODE_RESEND_SECONDS
            code_locked = False
            values["verify_code"] = ""
            step = 2
            return render_current()

        if "verify_code_submit" in request.POST:
            # Step 2: validate and verify the submitted code.
            if code_locked:
                _add_error(
                    errors,
                    "verify_code",
                    "Too many attempts. Resend a new verification code.",
                )
                step = 2
                return render_current()
            if code_verified:
                session["recovery_step"] = 3
                step = 3
                return render_current()

            code = (request.POST.get("verify_code") or "").strip()
            values["verify_code"] = code
            if not code:
                _add_error(errors, "verify_code", "Enter the 6-digit code")
            elif not code.isdigit() or len(code) != 6:
                _add_error(errors, "verify_code", "Enter the 6-digit code")

            stored_code = session.get("recovery_verify_code")
            sent_at = session.get("recovery_verify_code_sent_at")
            attempts = int(session.get("recovery_verify_code_attempts", 0))

            if stored_code and sent_at and code and not errors.get("verify_code"):
                now_ts = int(timezone.now().timestamp())
                if now_ts - int(sent_at) > RECOVERY_CODE_TTL_SECONDS:
                    _expire_recovery_code(request)
                    _add_error(
                        errors,
                        "verify_code",
                        "That verification code expired. Resend a new one.",
                    )
                elif not secrets.compare_digest(code, stored_code):
                    attempts += 1
                    session["recovery_verify_code_attempts"] = attempts
                    if attempts >= RECOVERY_CODE_MAX_ATTEMPTS:
                        session["recovery_verify_code_locked"] = True
                        code_locked = True
                        _expire_recovery_code(request)
                        _add_error(
                            errors,
                            "verify_code",
                            "Too many attempts. Resend a new verification code.",
                        )
                        values["verify_code"] = ""
                    else:
                        _add_error(
                            errors,
                            "verify_code",
                            "That verification code is incorrect.",
                        )
            elif code:
                _add_error(
                    errors,
                    "verify_code",
                    "That verification code expired. Resend a new one.",
                )

            if errors:
                step = 2
                return render_current(code_sent=code_sent, code_locked=code_locked)

            session["recovery_code_verified"] = True
            code_verified = True
            session["recovery_step"] = 3
            step = 3
            return render_current()

        if "reset_password" in request.POST:
            # Step 3: validate passwords and update the account password.
            if not code_verified:
                page_error = "Verify your email before changing the password."
                session["recovery_step"] = 2
                step = 2
                return render_current()

            email = session.get("recovery_email", values["email"])
            if not email:
                session["recovery_step"] = 1
                step = 1
                return render_current()

            try:
                user = user_model.objects.get(email__iexact=email)
            except user_model.DoesNotExist:
                _add_error(errors, "email", "No account was found for that email.")
                page_error = "No account was found for that email."
                values["email"] = ""
                session.pop("recovery_email", None)
                session["recovery_step"] = 1
                step = 1
                return render_current()

            password = request.POST.get("password") or ""
            verify_password = request.POST.get("verify_password") or ""

            if not password:
                _add_error(errors, "password", "Enter a password")
            else:
                try:
                    validate_password(password, user=user)
                except ValidationError as exc:
                    _add_error(errors, "password", _summarize_password_errors(exc.messages))
                    confirm_outline = True

            if not errors.get("password"):
                if not verify_password:
                    _add_error(errors, "verify_password", "Confirm your password")
                elif password != verify_password:
                    _add_error(errors, "verify_password", "Passwords do not match")

            if errors:
                step = 3
                return render_current(confirm_outline=confirm_outline)

            try:
                user.set_password(password)
                user.save(update_fields=["password"])
            except Exception:
                page_error = "Something went wrong. Try again."
                step = 3
                return render_current()

            login(request, user, backend="accounts.backends.EmailBackend")
            messages.success(request, f"Successfully signed in as {user.email}.")
            _clear_recovery_session(request)
            return redirect("profile")

    return render_current()


@ensure_csrf_cookie
def auth_login(request: HttpRequest) -> HttpResponse:
    """Handle sign-in with optional rate limiting and password recovery."""
    if _is_recovery_request(request):
        return _handle_password_recovery(request)

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
        """Render the sign-in page with rate-limit context."""
        return TemplateResponse(
            request,
            "registration/login.html",
            {
                "recovery_mode": False,
                "rate_limit_active": rate_limit_active,
                "rate_limit_retry_after": retry_after,
                "login_failed": login_failed,
            },
        )

    def redirect_login() -> HttpResponse:
        """Redirect back to the sign-in page."""
        return redirect("signin")

    # Resolve the best-guess client IP for rate limiting.
    ip = get_client_ip(request)

    if request.method == "POST":
        # Normalize user input to keep rate-limit keys and auth consistent.
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""
        keys = build_rate_limit_keys(ip, email)
        request.session["login_last_email"] = email

        if rate_limit_enabled:
            limited, retry_after, _ = check_rate_limit(
                keys, max_attempts, window_seconds, lockout_schedule, mode
            )
            if limited:
                return redirect_login()

        # Authenticate against the email-based backend.
        user = authenticate(request, email=email, password=password)
        if user is not None:
            if rate_limit_enabled:
                reset_limits(keys)
            login(request, user)
            messages.success(request, f"Successfully signed in as {user.email}.")
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
        last_email = request.session.get("login_last_email", "")
        keys = build_rate_limit_keys(ip, last_email)
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
