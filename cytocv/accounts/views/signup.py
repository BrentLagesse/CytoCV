"""Signup view with step-by-step email verification flow."""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from email.utils import parseaddr

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import EmailValidator
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone

from accounts.email_content import (
    AuthEmailContent,
    attach_auth_email_logo,
    build_auth_email_logo_src,
    build_signup_verification_email,
)
from accounts.email_lookup import email_matches_existing_account, normalize_auth_email
from accounts.security.recaptcha import recaptcha_enabled, verify_recaptcha_response
from core.security.rate_limit import get_client_ip

VERIFY_CODE_TTL_SECONDS = settings.AUTH_VERIFICATION_EXPIRY_SECONDS
VERIFY_CODE_MAX_ATTEMPTS = 5
VERIFY_CODE_RESEND_SECONDS = 10 if settings.DEBUG else 60
AUTH_RECAPTCHA_GATE_SESSION_KEY = "auth_recaptcha_gate_verified_at"
logger = logging.getLogger(__name__)


def _generate_verify_code() -> str:
    """Return a cryptographically generated 6-digit verification code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _clear_verify_session(request: HttpRequest) -> None:
    """Remove verification-code-related session state."""
    for key in (
        "verify_code",
        "verify_code_sent_at",
        "verify_code_attempts",
        "verify_code_locked",
    ):
        request.session.pop(key, None)


def _expire_verify_code(request: HttpRequest) -> None:
    """Clear a stale verification code and its attempt counter."""
    for key in ("verify_code", "verify_code_attempts"):
        request.session.pop(key, None)


def _render_signup(
    request: HttpRequest,
    *,
    step: int,
    step_total: int,
    values: dict[str, str],
    errors: dict[str, list[str]],
    page_error: str | None = None,
    code_sent: bool = False,
    code_notice: str | None = None,
    code_verified: bool = False,
    resend_available_in: int = 0,
    code_locked: bool = False,
    sender_email: str | None = None,
    clear_password: bool = False,
    clear_confirm: bool = False,
    confirm_outline: bool = False,
    recaptcha_error: str | None = None,
) -> HttpResponse:
    """Render the signup template with shared context."""
    context = {
        "step": step,
        "step_total": step_total,
        "values": values,
        "errors": errors,
        "page_error": page_error,
        "code_sent": code_sent,
        "code_notice": code_notice,
        "code_verified": code_verified,
        "resend_available_in": resend_available_in,
        "code_locked": code_locked,
        "sender_email": sender_email,
        "clear_password": clear_password,
        "clear_confirm": clear_confirm,
        "confirm_outline": confirm_outline,
        "recaptcha_enabled": recaptcha_enabled(),
        "recaptcha_site_key": getattr(settings, "RECAPTCHA_SITE_KEY", ""),
        "recaptcha_error": recaptcha_error,
    }
    return TemplateResponse(request, "registration/signup.html", context)


def _add_error(errors: dict[str, list[str]], field: str, message: str) -> None:
    """Append a field-level error message."""
    errors.setdefault(field, []).append(message)


def _is_code_active(request: HttpRequest) -> bool:
    """Return True when a verification code exists and is not expired."""
    stored_code = request.session.get("verify_code")
    sent_at = request.session.get("verify_code_sent_at")
    if not stored_code or not sent_at:
        return False
    now_ts = int(timezone.now().timestamp())
    if now_ts - int(sent_at) > VERIFY_CODE_TTL_SECONDS:
        _expire_verify_code(request)
        return False
    return True


def _clear_signup_session(request: HttpRequest) -> None:
    """Clear all signup-related session state."""
    for key in (
        "signup_step",
        "signup_first_name",
        "signup_last_name",
        "signup_email",
        "signup_code_verified",
    ):
        request.session.pop(key, None)
    _clear_verify_session(request)


def _code_sent_flag(request: HttpRequest) -> bool:
    """Return True when a verification code send timestamp exists."""
    return bool(request.session.get("verify_code_sent_at"))


def _normalize_email(email: str) -> str:
    """Normalize user-provided email input."""
    return normalize_auth_email(email)


def _should_reset_signup(request: HttpRequest) -> bool:
    """Decide whether to restart the signup flow for a GET request.

    Args:
        request: Incoming HTTP request.

    Returns:
        True when the flow should be reset, otherwise False.
    """
    if request.method != "GET":
        return False
    if request.GET.get("fresh") == "1":
        return True
    referer = request.META.get("HTTP_REFERER", "")
    if referer and "/signup" not in referer:
        return True
    return False


def _resend_wait_seconds(request: HttpRequest) -> int:
    """Return seconds remaining before another code can be resent.

    Args:
        request: Incoming HTTP request.

    Returns:
        Number of seconds remaining before resend is allowed.
    """
    sent_at = request.session.get("verify_code_sent_at")
    if not sent_at:
        return 0
    now_ts = int(timezone.now().timestamp())
    remaining = VERIFY_CODE_RESEND_SECONDS - (now_ts - int(sent_at))
    return max(0, int(remaining))


def _sender_email() -> str:
    """Return the from address used for verification emails."""
    return (
        (getattr(settings, "AUTH_EMAIL_FROM", "") or "").strip()
        or (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
        or (getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
    )


def _sender_display_email() -> str:
    """Return the plain address shown in the signup UI."""
    return parseaddr(_sender_email())[1] or _sender_email()


def _reply_to_list() -> list[str] | None:
    """Return a normalized reply-to list for outbound auth emails."""
    reply_to = _sender_email()
    return [reply_to] if reply_to else None


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


def _build_verification_email(
    *,
    code: str,
    minutes_valid: int,
    subject_prefix: str,
    recipient_name: str | None = None,
    logo_url: str = "",
    sender_email: str = "",
) -> AuthEmailContent:
    """Build a verification email subject/body pair.

    Args:
        code: Verification code to include.
        minutes_valid: Number of minutes the code remains valid.
        subject_prefix: Prefix for the subject line.
        recipient_name: Optional first name for a personalized greeting.

    Returns:
        Subject, text body, and HTML body.
    """
    return build_signup_verification_email(
        code=code,
        minutes_valid=minutes_valid,
        subject_prefix=subject_prefix,
        recipient_name=recipient_name,
        logo_url=logo_url,
        sender_email=sender_email,
    )


def _send_auth_email(
    *,
    email_content: AuthEmailContent,
    from_email: str,
    recipient: str,
    reply_to: list[str] | None,
) -> None:
    """Send a multipart account email with text and HTML alternatives."""
    message = EmailMultiAlternatives(
        email_content.subject,
        email_content.text_body,
        from_email,
        [recipient],
        reply_to=reply_to,
    )
    message.attach_alternative(email_content.html_body, "text/html")
    attach_auth_email_logo(message)
    message.send(fail_silently=False)


def _is_recaptcha_gate_verified(request: HttpRequest, *, session_key: str) -> bool:
    """Return True when the reCAPTCHA gate has been passed within TTL."""
    if not recaptcha_enabled():
        return True
    raw_ts = request.session.get(session_key)
    if not raw_ts:
        return False
    try:
        verified_at = timezone.datetime.fromisoformat(str(raw_ts))
    except (ValueError, TypeError):
        request.session.pop(session_key, None)
        return False
    if timezone.is_naive(verified_at):
        verified_at = timezone.make_aware(verified_at, timezone.get_current_timezone())
    ttl_seconds = int(getattr(settings, "RECAPTCHA_GATE_TTL_SECONDS", 1800))
    if timezone.now() - verified_at > timedelta(seconds=max(60, ttl_seconds)):
        request.session.pop(session_key, None)
        return False
    return True


def _mark_recaptcha_gate_verified(request: HttpRequest, *, session_key: str) -> None:
    """Persist successful reCAPTCHA gate verification timestamp."""
    request.session[session_key] = timezone.now().isoformat()


def signup(request: HttpRequest) -> HttpResponse:
    """Handle the multi-step signup flow.

    Steps:
      1) Collect first and last name.
      2) Collect email and send verification code.
      3) Verify the code.
      4) Set password and create account.
    """
    if _should_reset_signup(request):
        _clear_signup_session(request)

    if recaptcha_enabled() and not _is_recaptcha_gate_verified(
        request, session_key=AUTH_RECAPTCHA_GATE_SESSION_KEY
    ):
        gate_error = None
        if request.method == "POST" and request.POST.get("pass_captcha_gate") == "1":
            token = request.POST.get("g-recaptcha-response", "")
            if verify_recaptcha_response(
                token,
                get_client_ip(request),
                request.get_host(),
            ):
                _mark_recaptcha_gate_verified(
                    request, session_key=AUTH_RECAPTCHA_GATE_SESSION_KEY
                )
                return redirect(request.path)
            gate_error = "Please complete the reCAPTCHA challenge."
        return TemplateResponse(
            request,
            "registration/signup.html",
            {
                "recaptcha_gate_mode": True,
                "recaptcha_gate_error": gate_error,
                "recaptcha_enabled": recaptcha_enabled(),
                "recaptcha_site_key": getattr(settings, "RECAPTCHA_SITE_KEY", ""),
            },
        )

    user_model = get_user_model()
    session = request.session
    step_total = 4
    step = int(session.get("signup_step", 1))

    values = {
        "first_name": session.get("signup_first_name", ""),
        "last_name": session.get("signup_last_name", ""),
        "email": session.get("signup_email", ""),
        "verify_code": "",
    }
    errors: dict[str, list[str]] = {}
    page_error = None
    code_notice = None
    clear_password = False
    clear_confirm = False
    confirm_outline = False
    recaptcha_error = None

    # Normalize computed state derived from the session.
    _is_code_active(request)
    code_sent = _code_sent_flag(request)
    code_verified = bool(session.get("signup_code_verified", False))
    code_locked = bool(session.get("verify_code_locked", False))
    resend_available_in = _resend_wait_seconds(request)
    sender_email = _sender_display_email()
    if code_locked:
        values["verify_code"] = ""

    # Keep the step consistent with data already collected.
    if step > 1 and (not values["first_name"] or not values["last_name"]):
        step = 1
    if step > 2 and not values["email"]:
        step = 2
    if step > 2 and not session.get("verify_code_sent_at"):
        step = 2
    if step > 3 and not code_verified:
        step = 3
    session["signup_step"] = step

    def render_current(**overrides: object) -> HttpResponse:
        """Render the signup page with optional overrides."""
        return _render_signup(
            request,
            step=overrides.get("step", step),
            step_total=step_total,
            values=overrides.get("values", values),
            errors=overrides.get("errors", errors),
            page_error=overrides.get("page_error", page_error),
            code_sent=overrides.get("code_sent", code_sent),
            code_notice=overrides.get("code_notice", code_notice),
            code_verified=overrides.get("code_verified", code_verified),
            resend_available_in=overrides.get("resend_available_in", resend_available_in),
            code_locked=overrides.get("code_locked", code_locked),
            sender_email=overrides.get("sender_email", sender_email),
            clear_password=overrides.get("clear_password", clear_password),
            clear_confirm=overrides.get("clear_confirm", clear_confirm),
            confirm_outline=overrides.get("confirm_outline", confirm_outline),
            recaptcha_error=overrides.get("recaptcha_error", recaptcha_error),
        )

    if request.method == "POST":
        # Navigation controls do not perform validation.
        if "back_name" in request.POST:
            session["signup_step"] = 1
            step = 1
            return render_current()
        if "back_email" in request.POST:
            _clear_verify_session(request)
            session.pop("signup_code_verified", None)
            session["signup_step"] = 2
            step = 2
            return render_current()
        if "back_code" in request.POST:
            session["signup_step"] = 3
            step = 3
            return render_current()

        if "next_step" in request.POST:
            values["first_name"] = (request.POST.get("first_name") or "").strip()
            values["last_name"] = (request.POST.get("last_name") or "").strip()
            session["signup_first_name"] = values["first_name"]
            session["signup_last_name"] = values["last_name"]

            if not values["first_name"]:
                _add_error(errors, "first_name", "Enter your first name")
            if not values["last_name"]:
                _add_error(errors, "last_name", "Enter your last name")

            if errors:
                step = 1
                return render_current()

            session["signup_step"] = 2
            step = 2
            return render_current(code_sent=_code_sent_flag(request))

        if "send_code" in request.POST:
            # Step 2: validate email, then send a new verification code.
            values["email"] = _normalize_email(request.POST.get("email") or "")
            session["signup_email"] = values["email"]
            session.pop("signup_code_verified", None)
            session.pop("verify_code_locked", None)

            def validate_email_address(email: str) -> None:
                """Validate format and uniqueness for the email field."""
                try:
                    EmailValidator()(email)
                except ValidationError:
                    _add_error(errors, "email", "Enter a valid email address")
                    return
                if email_matches_existing_account(email):
                    _add_error(errors, "email", "That email is already in use. Sign In instead.")

            if not values["email"]:
                _add_error(errors, "email", "Enter a valid email address")
            else:
                validate_email_address(values["email"])

            if errors:
                step = 2
                return render_current()

            if _resend_wait_seconds(request) > 0:
                page_error = "Please wait before requesting another verification code."
                step = 2
                resend_available_in = _resend_wait_seconds(request)
                return render_current()

            verify_code = _generate_verify_code()
            from_email = _sender_email()
            email_content = build_signup_verification_email(
                code=verify_code,
                minutes_valid=VERIFY_CODE_TTL_SECONDS // 60,
                subject_prefix="CytoCV",
                recipient_name=values.get("first_name", ""),
                logo_url=build_auth_email_logo_src(request),
                sender_email=from_email,
            )

            reply_to_list = _reply_to_list()

            try:
                _send_auth_email(
                    email_content=email_content,
                    from_email=from_email,
                    recipient=values["email"],
                    reply_to=reply_to_list,
                )
            except Exception:
                logger.exception("Failed to send signup verification email.")
                page_error = "We couldn't send a verification code right now. Try again."
                step = 2
                return render_current()

            session["verify_code"] = verify_code
            session["verify_code_sent_at"] = int(timezone.now().timestamp())
            session["verify_code_attempts"] = 0
            code_notice = f"Verification code sent to {values['email']}."
            code_sent = True
            resend_available_in = VERIFY_CODE_RESEND_SECONDS
            code_locked = False
            values["verify_code"] = ""

            session["signup_step"] = 3
            step = 3
            return render_current()

        if "resend_code" in request.POST:
            # Step 3: resend generates a new code and invalidates the old one.
            values["email"] = session.get("signup_email", values["email"])
            if not values["email"]:
                session["signup_step"] = 2
                step = 2
                return render_current()

            resend_available_in = _resend_wait_seconds(request)
            if resend_available_in > 0:
                page_error = "Please wait before requesting another verification code."
                step = 3
                return render_current()

            verify_code = _generate_verify_code()
            from_email = _sender_email()
            email_content = build_signup_verification_email(
                code=verify_code,
                minutes_valid=VERIFY_CODE_TTL_SECONDS // 60,
                subject_prefix="CytoCV",
                recipient_name=values.get("first_name", ""),
                logo_url=build_auth_email_logo_src(request),
                sender_email=from_email,
            )

            reply_to_list = _reply_to_list()

            try:
                _send_auth_email(
                    email_content=email_content,
                    from_email=from_email,
                    recipient=values["email"],
                    reply_to=reply_to_list,
                )
            except Exception:
                logger.exception("Failed to resend signup verification email.")
                page_error = "We couldn't resend the verification code right now. Try again."
                step = 3
                return render_current()

            session["verify_code"] = verify_code
            session["verify_code_sent_at"] = int(timezone.now().timestamp())
            session["verify_code_attempts"] = 0
            session.pop("signup_code_verified", None)
            session.pop("verify_code_locked", None)
            code_notice = f"Verification code resent to {values['email']}."
            code_sent = True
            resend_available_in = VERIFY_CODE_RESEND_SECONDS
            code_locked = False
            values["verify_code"] = ""
            step = 3
            return render_current()

        if "verify_code_submit" in request.POST:
            # Step 3: validate and verify the submitted code.
            if code_locked:
                _add_error(errors, "verify_code", "Too many attempts. Resend a new verification code.")
                step = 3
                return render_current()
            if code_verified:
                session["signup_step"] = 4
                step = 4
                return render_current()

            code = (request.POST.get("verify_code") or "").strip()
            values["verify_code"] = code
            if not code:
                _add_error(errors, "verify_code", "Enter the 6-digit code")
            elif not code.isdigit() or len(code) != 6:
                _add_error(errors, "verify_code", "Enter the 6-digit code")

            stored_code = session.get("verify_code")
            sent_at = session.get("verify_code_sent_at")
            attempts = int(session.get("verify_code_attempts", 0))

            if stored_code and sent_at and code and not errors.get("verify_code"):
                now_ts = int(timezone.now().timestamp())
                if now_ts - int(sent_at) > VERIFY_CODE_TTL_SECONDS:
                    _expire_verify_code(request)
                    _add_error(errors, "verify_code", "That verification code expired. Resend a new one.")
                elif not secrets.compare_digest(code, stored_code):
                    attempts += 1
                    session["verify_code_attempts"] = attempts
                    if attempts >= VERIFY_CODE_MAX_ATTEMPTS:
                        session["verify_code_locked"] = True
                        code_locked = True
                        _expire_verify_code(request)
                        _add_error(errors, "verify_code", "Too many attempts. Resend a new verification code.")
                        values["verify_code"] = ""
                    else:
                        _add_error(errors, "verify_code", "That verification code is incorrect.")
            elif code:
                _add_error(errors, "verify_code", "That verification code expired. Resend a new one.")

            if errors:
                step = 3
                return render_current(code_sent=_code_sent_flag(request), code_locked=code_locked)

            session["signup_code_verified"] = True
            code_verified = True
            session["signup_step"] = 4
            step = 4
            return render_current()

        if "create_account" in request.POST:
            # Step 4: validate passwords and create the user account.
            if not code_verified:
                page_error = "Enter the verification code before creating your account."
                session["signup_step"] = 3
                step = 3
                return render_current()

            password = request.POST.get("password") or ""
            verify_password = request.POST.get("verify_password") or ""
            password_errors: list[str] = []

            if not password:
                password_errors.append("Enter a password")
            else:
                dummy = user_model(
                    email=values["email"],
                    first_name=values["first_name"],
                    last_name=values["last_name"],
                )
                try:
                    validate_password(password, user=dummy)
                except ValidationError as exc:
                    password_errors.append(_summarize_password_errors(exc.messages))

            if password_errors:
                for message in password_errors:
                    _add_error(errors, "password", message)
                confirm_outline = True
                clear_password = True
                clear_confirm = True
            else:
                if not verify_password:
                    _add_error(errors, "verify_password", "Confirm your password")
                    clear_confirm = True
                elif password != verify_password:
                    _add_error(errors, "verify_password", "Passwords do not match")
                    clear_confirm = True

            if errors:
                step = 4
                return render_current(
                    clear_password=clear_password,
                    clear_confirm=clear_confirm,
                    confirm_outline=confirm_outline,
                )

            try:
                values["email"] = _normalize_email(values["email"])
                session["signup_email"] = values["email"]
                EmailValidator()(values["email"])
            except ValidationError:
                _add_error(errors, "email", "Enter a valid email address")
                step = 2
                session["signup_step"] = 2
                return render_current()

            if email_matches_existing_account(values["email"]):
                _add_error(errors, "email", "That email is already in use. Sign In instead.")
                step = 2
                session["signup_step"] = 2
                return render_current()

            try:
                user = user_model(
                    email=values["email"],
                    first_name=values["first_name"],
                    last_name=values["last_name"],
                )
                user.set_password(password)
                user.save()
            except IntegrityError:
                _add_error(errors, "email", "That email is already in use. Sign In instead.")
                step = 2
                session["signup_step"] = 2
                return render_current()
            except Exception:
                logger.exception("Failed to create user during signup.")
                page_error = "We couldn't create your account right now. Try again."
                step = 4
                return render_current()

            login(request, user, backend="accounts.backends.EmailBackend")
            _clear_signup_session(request)
            return redirect("home")

    return render_current()
