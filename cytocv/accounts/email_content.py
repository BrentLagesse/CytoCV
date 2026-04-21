"""Shared builders for CytoCV account emails."""

from __future__ import annotations

from dataclasses import dataclass
from email.mime.image import MIMEImage
from email.utils import parseaddr
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives
from django.http import HttpRequest
from django.templatetags.static import static
from django.utils import timezone
from django.utils.html import escape


AUTH_EMAIL_LOGO_ALT = "University of Washington Bothell School of STEM"
AUTH_EMAIL_LOGO_PATH = "assets/UWBSTEM.png"
AUTH_EMAIL_LOGO_CID = "cytocv-uwb-stem-logo"
AUTH_EMAIL_LOGO_CID_URL = f"cid:{AUTH_EMAIL_LOGO_CID}"
INSTITUTION_LINES = (
    "CytoCV Account Services",
    "University of Washington Bothell",
    "School of Science, Technology, Engineering & Mathematics",
    "Department of Computing & Software Systems",
)
UWB_STEM_URL = "https://www.uwb.edu/stem"
AUTH_EMAIL_WARNING_TITLE = "Do not share this email"
AUTH_EMAIL_WARNING_TEXT = (
    "University of Washington Bothell will never ask you to share this email or its contents."
)
PLACEHOLDER_RECIPIENT_NAMES = {
    "-",
    "--",
    "_",
    "n/a",
    "na",
    "none",
    "null",
    "\u2013",
    "\u2014",
}


@dataclass(frozen=True)
class AuthEmailContent:
    """Subject plus text and HTML alternatives for an account email."""

    subject: str
    text_body: str
    html_body: str


def build_auth_email_logo_url(request: HttpRequest) -> str:
    """Return an absolute URL for the UWB STEM email logo."""
    logo_path = static(AUTH_EMAIL_LOGO_PATH)
    if logo_path.startswith(("http://", "https://")):
        return logo_path

    public_base_url = (getattr(settings, "PUBLIC_BASE_URL", "") or "").strip()
    if public_base_url:
        return urljoin(public_base_url.rstrip("/") + "/", logo_path.lstrip("/"))

    return request.build_absolute_uri(logo_path)


def build_auth_email_logo_src(request: HttpRequest) -> str:
    """Return an embedded logo source when available, otherwise an absolute URL."""
    if finders.find(AUTH_EMAIL_LOGO_PATH):
        return AUTH_EMAIL_LOGO_CID_URL
    return build_auth_email_logo_url(request)


def attach_auth_email_logo(message: EmailMultiAlternatives) -> bool:
    """Attach the UWB STEM logo as an inline image when the asset can be found."""
    logo_path = finders.find(AUTH_EMAIL_LOGO_PATH)
    if not logo_path:
        return False

    with open(logo_path, "rb") as logo_file:
        logo = MIMEImage(logo_file.read())
    logo.add_header("Content-ID", f"<{AUTH_EMAIL_LOGO_CID}>")
    logo.add_header("Content-Disposition", "inline", filename="UWBSTEM.png")
    message.attach(logo)
    return True


def build_signup_verification_email(
    *,
    code: str,
    minutes_valid: int,
    subject_prefix: str,
    recipient_name: str | None = None,
    logo_url: str = "",
    sender_email: str = "",
) -> AuthEmailContent:
    """Build the signup verification email."""
    subject = f"Your {subject_prefix} verification code"
    return _build_branded_auth_email(
        subject=subject,
        title="Your verification code",
        code=code,
        minutes_valid=minutes_valid,
        instruction="Enter this verification code to continue signing in to CytoCV:",
        recipient_name=recipient_name,
        logo_url=logo_url,
        sender_email=sender_email,
    )


def build_password_recovery_email(
    *,
    code: str,
    minutes_valid: int,
    recipient_name: str | None = None,
    logo_url: str = "",
    sender_email: str = "",
) -> AuthEmailContent:
    """Build the password recovery verification email."""
    subject = "Your CytoCV password reset code"
    return _build_branded_auth_email(
        subject=subject,
        title="Your verification code",
        code=code,
        minutes_valid=minutes_valid,
        instruction="Enter this verification code to reset your CytoCV password:",
        recipient_name=recipient_name,
        logo_url=logo_url,
        sender_email=sender_email,
    )


def build_email_confirmation_email(
    *,
    activate_url: str,
    minutes_valid: int,
    recipient_email: str = "",
    recipient_name: str | None = None,
    logo_url: str = "",
    sender_email: str = "",
) -> AuthEmailContent:
    """Build the OAuth/allauth email-confirmation email."""
    title = "Verify your email address"
    instruction = (
        "Open the secure link below to verify your email address and finish signing in to CytoCV."
    )
    validity_line = _confirmation_validity_line(minutes_valid)
    sender_address = _email_address(sender_email)
    automated_notice = _automated_notice(sender_address)
    security_note = "If you did not request this email, you can safely ignore it."
    email_date = _formatted_email_date()
    safe_name = normalize_recipient_name(recipient_name)
    greeting = f"Hello {safe_name}," if safe_name else "Hello,"

    text_parts = [
        f"CytoCV | {email_date}",
        "",
        title,
        "University of Washington Bothell School of STEM",
        "",
        greeting,
        "",
        instruction,
        "",
        f"Warning: {AUTH_EMAIL_WARNING_TITLE}",
        AUTH_EMAIL_WARNING_TEXT,
        "",
        "Verify email address:",
        activate_url,
        "",
        "If the button in the HTML email does not work, copy and paste this link into your browser:",
        activate_url,
        "",
        validity_line,
        "",
        security_note,
    ]
    if recipient_email:
        text_parts.extend(["", f"Email address: {recipient_email}"])
    text_parts.extend(["", "--"])
    text_parts.extend(INSTITUTION_LINES)
    text_parts.append(f"School of STEM website: {UWB_STEM_URL}")
    text_parts.append(automated_notice)

    html_body = _render_html_link_email(
        title=title,
        greeting=greeting,
        instruction=instruction,
        activate_url=activate_url,
        validity_line=validity_line,
        logo_url=logo_url,
        sender_address=sender_address,
        security_note=security_note,
        email_date=email_date,
        recipient_email=recipient_email,
    )
    return AuthEmailContent(
        subject="Verify your CytoCV email address",
        text_body="\n".join(text_parts),
        html_body=html_body,
    )


def _build_branded_auth_email(
    *,
    subject: str,
    title: str,
    code: str,
    minutes_valid: int,
    instruction: str,
    recipient_name: str | None,
    logo_url: str,
    sender_email: str,
) -> AuthEmailContent:
    """Build text and HTML alternatives for a verification-code email."""
    safe_name = normalize_recipient_name(recipient_name)
    greeting = f"Hello {safe_name}," if safe_name else "Hello,"
    validity_line = f"This code expires in {minutes_valid} minutes."
    sender_address = _email_address(sender_email)
    automated_notice = _automated_notice(sender_address)
    security_note = "If you did not request this code, you can safely ignore this email."
    email_date = _formatted_email_date()

    text_parts = [
        f"CytoCV | {email_date}",
        "",
        title,
        "University of Washington Bothell School of STEM",
        "",
        greeting,
        "",
        instruction,
        "",
        f"Warning: {AUTH_EMAIL_WARNING_TITLE}",
        AUTH_EMAIL_WARNING_TEXT,
        "",
        code,
        "",
        validity_line,
        "",
        security_note,
    ]
    text_parts.extend(["", "--"])
    text_parts.extend(INSTITUTION_LINES)
    text_parts.append(f"School of STEM website: {UWB_STEM_URL}")
    text_parts.append(automated_notice)

    html_body = _render_html_email(
        title=title,
        greeting=greeting,
        code=code,
        validity_line=validity_line,
        instruction=instruction,
        logo_url=logo_url,
        sender_address=sender_address,
        security_note=security_note,
        email_date=email_date,
    )
    return AuthEmailContent(subject=subject, text_body="\n".join(text_parts), html_body=html_body)


def _render_html_email(
    *,
    title: str,
    greeting: str,
    code: str,
    validity_line: str,
    instruction: str,
    logo_url: str,
    sender_address: str,
    security_note: str,
    email_date: str,
) -> str:
    """Render a conservative HTML email with inline styles."""
    logo_markup = ""
    if logo_url:
        logo_markup = (
            '<img src="{logo_url}" width="160" alt="{alt}" '
            'style="display:block;width:160px;max-width:100%;height:auto;border:0;outline:none;text-decoration:none;">'
        ).format(logo_url=escape(logo_url), alt=AUTH_EMAIL_LOGO_ALT)

    security_markup = ""
    if security_note:
        security_markup = (
            '<p style="margin:18px 0 0;color:#374151;font-size:15px;line-height:1.6;">'
            f"{escape(security_note)}</p>"
        )

    automated_notice = _automated_notice(sender_address)

    return f"""<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Verdana,sans-serif;color:#111827;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;background:#f3f4f6;">
      <tr>
        <td align="center" style="padding:28px 16px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;max-width:620px;background:#ffffff;border:1px solid #d1d5db;">
            <tr>
              <td style="padding:28px 32px 22px;border-top:6px solid #4b2e83;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:0 0 24px;">
                  <tr>
                    <td style="padding:0;color:#4b2e83;font-size:18px;line-height:1.3;font-weight:800;letter-spacing:.01em;">CytoCV</td>
                    <td align="right" style="padding:0;color:#6b7280;font-size:14px;line-height:1.3;font-weight:400;">{escape(email_date)}</td>
                  </tr>
                </table>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
                  <tr>
                    <td style="vertical-align:middle;width:185px;padding:0 24px 0 0;">
                      {logo_markup}
                    </td>
                    <td style="vertical-align:middle;padding:0;">
                      <p style="margin:0;color:#4b2e83;font-size:13px;line-height:1.2;font-weight:700;text-transform:uppercase;letter-spacing:.08em;">University of Washington Bothell</p>
                      <p style="margin:6px 0 0;color:#4b2e83;font-size:20px;line-height:1.25;font-weight:700;">School of STEM</p>
                      <p style="margin:6px 0 0;color:#4b5563;font-size:13px;line-height:1.45;">School of Science, Technology, Engineering &amp; Mathematics</p>
                      <p style="margin:3px 0 0;color:#4b5563;font-size:13px;line-height:1.45;">Department of Computing &amp; Software Systems</p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:0 32px 28px;">
                <h1 style="margin:0 0 18px;color:#111827;font-size:24px;line-height:1.25;font-weight:700;">{escape(title)}</h1>
                <p style="margin:0 0 18px;color:#374151;font-size:16px;line-height:1.6;">{escape(greeting)}</p>
                <p style="margin:0;color:#374151;font-size:16px;line-height:1.6;">{escape(instruction)}</p>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:18px 0 0;background:#fffbeb;border:1px solid #f59e0b;">
                  <tr>
                    <td style="width:34px;padding:14px 0 14px 16px;vertical-align:top;color:#92400e;font-size:20px;line-height:1;">&#9888;</td>
                    <td style="padding:14px 16px 14px 10px;vertical-align:top;">
                      <p style="margin:0;color:#92400e;font-size:15px;line-height:1.35;font-weight:700;">Do not share this email</p>
                      <p style="margin:4px 0 0;color:#78350f;font-size:14px;line-height:1.5;">University of Washington Bothell will never ask you to share this email or its contents.</p>
                    </td>
                  </tr>
                </table>
                <p style="margin:18px 0 18px;padding:16px 20px;background:#f9fafb;border:1px solid #d1d5db;color:#111827;font-size:30px;line-height:1.1;font-weight:700;letter-spacing:4px;text-align:center;">{escape(code)}</p>
                <p style="margin:0;color:#374151;font-size:15px;line-height:1.6;">{escape(validity_line)}</p>
                {security_markup}
              </td>
            </tr>
            <tr>
              <td style="padding:24px 32px 28px;background:#f9fafb;border-top:1px solid #e5e7eb;">
                <p style="margin:0;color:#111827;font-size:15px;line-height:1.45;font-weight:700;">CytoCV Account Services</p>
                <p style="margin:4px 0 0;color:#374151;font-size:13px;line-height:1.45;">University of Washington Bothell</p>
                <p style="margin:0;color:#374151;font-size:13px;line-height:1.45;">School of Science, Technology, Engineering &amp; Mathematics</p>
                <p style="margin:0;color:#374151;font-size:13px;line-height:1.45;">Department of Computing &amp; Software Systems</p>
                <p style="margin:10px 0 0;color:#374151;font-size:13px;line-height:1.45;"><a href="{UWB_STEM_URL}" style="color:#4b2e83;text-decoration:underline;">School of STEM website</a></p>
                <p style="margin:14px 0 0;color:#6b7280;font-size:13px;line-height:1.5;">{escape(automated_notice)}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _render_html_link_email(
    *,
    title: str,
    greeting: str,
    instruction: str,
    activate_url: str,
    validity_line: str,
    logo_url: str,
    sender_address: str,
    security_note: str,
    email_date: str,
    recipient_email: str,
) -> str:
    """Render an HTML email with a secure verification-link CTA."""
    logo_markup = ""
    if logo_url:
        logo_markup = (
            '<img src="{logo_url}" width="160" alt="{alt}" '
            'style="display:block;width:160px;max-width:100%;height:auto;border:0;outline:none;text-decoration:none;">'
        ).format(logo_url=escape(logo_url), alt=AUTH_EMAIL_LOGO_ALT)

    recipient_markup = ""
    if recipient_email:
        recipient_markup = (
            '<p style="margin:18px 0 0;color:#4b5563;font-size:14px;line-height:1.5;">'
            f"Email address: <strong style=\"color:#111827;\">{escape(recipient_email)}</strong></p>"
        )

    automated_notice = _automated_notice(sender_address)

    return f"""<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Verdana,sans-serif;color:#111827;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;background:#f3f4f6;">
      <tr>
        <td align="center" style="padding:28px 16px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;max-width:620px;background:#ffffff;border:1px solid #d1d5db;">
            <tr>
              <td style="padding:28px 32px 22px;border-top:6px solid #4b2e83;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:0 0 24px;">
                  <tr>
                    <td style="padding:0;color:#4b2e83;font-size:18px;line-height:1.3;font-weight:800;letter-spacing:.01em;">CytoCV</td>
                    <td align="right" style="padding:0;color:#6b7280;font-size:14px;line-height:1.3;font-weight:400;">{escape(email_date)}</td>
                  </tr>
                </table>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
                  <tr>
                    <td style="vertical-align:middle;width:185px;padding:0 24px 0 0;">
                      {logo_markup}
                    </td>
                    <td style="vertical-align:middle;padding:0;">
                      <p style="margin:0;color:#4b2e83;font-size:13px;line-height:1.2;font-weight:700;text-transform:uppercase;letter-spacing:.08em;">University of Washington Bothell</p>
                      <p style="margin:6px 0 0;color:#4b2e83;font-size:20px;line-height:1.25;font-weight:700;">School of STEM</p>
                      <p style="margin:6px 0 0;color:#4b5563;font-size:13px;line-height:1.45;">School of Science, Technology, Engineering &amp; Mathematics</p>
                      <p style="margin:3px 0 0;color:#4b5563;font-size:13px;line-height:1.45;">Department of Computing &amp; Software Systems</p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:0 32px 28px;">
                <h1 style="margin:0 0 18px;color:#111827;font-size:24px;line-height:1.25;font-weight:700;">{escape(title)}</h1>
                <p style="margin:0 0 18px;color:#374151;font-size:16px;line-height:1.6;">{escape(greeting)}</p>
                <p style="margin:0;color:#374151;font-size:16px;line-height:1.6;">{escape(instruction)}</p>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:18px 0 0;background:#fffbeb;border:1px solid #f59e0b;">
                  <tr>
                    <td style="width:34px;padding:14px 0 14px 16px;vertical-align:top;color:#92400e;font-size:20px;line-height:1;">&#9888;</td>
                    <td style="padding:14px 16px 14px 10px;vertical-align:top;">
                      <p style="margin:0;color:#92400e;font-size:15px;line-height:1.35;font-weight:700;">Do not share this email</p>
                      <p style="margin:4px 0 0;color:#78350f;font-size:14px;line-height:1.5;">University of Washington Bothell will never ask you to share this email or its contents.</p>
                    </td>
                  </tr>
                </table>
                <p style="margin:22px 0 0;text-align:center;">
                  <a href="{escape(activate_url)}" style="display:inline-block;padding:13px 24px;background:#4b2e83;color:#ffffff;font-size:15px;line-height:1.2;font-weight:700;text-decoration:none;border-radius:4px;">Verify email address</a>
                </p>
                <p style="margin:20px 0 0;color:#374151;font-size:15px;line-height:1.6;">{escape(validity_line)}</p>
                <p style="margin:12px 0 0;color:#374151;font-size:15px;line-height:1.6;">{escape(security_note)}</p>
                {recipient_markup}
                <p style="margin:18px 0 0;color:#6b7280;font-size:13px;line-height:1.5;">If the button does not work, copy and paste this link into your browser:</p>
                <p style="margin:6px 0 0;padding:12px;background:#f9fafb;border:1px solid #e5e7eb;color:#4b5563;font-size:12px;line-height:1.5;word-break:break-all;">{escape(activate_url)}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:24px 32px 28px;background:#f9fafb;border-top:1px solid #e5e7eb;">
                <p style="margin:0;color:#111827;font-size:15px;line-height:1.45;font-weight:700;">CytoCV Account Services</p>
                <p style="margin:4px 0 0;color:#374151;font-size:13px;line-height:1.45;">University of Washington Bothell</p>
                <p style="margin:0;color:#374151;font-size:13px;line-height:1.45;">School of Science, Technology, Engineering &amp; Mathematics</p>
                <p style="margin:0;color:#374151;font-size:13px;line-height:1.45;">Department of Computing &amp; Software Systems</p>
                <p style="margin:10px 0 0;color:#374151;font-size:13px;line-height:1.45;"><a href="{UWB_STEM_URL}" style="color:#4b2e83;text-decoration:underline;">School of STEM website</a></p>
                <p style="margin:14px 0 0;color:#6b7280;font-size:13px;line-height:1.5;">{escape(automated_notice)}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _email_address(value: str) -> str:
    """Extract the address from a plain or display-name email value."""
    return parseaddr(value or "")[1]


def normalize_recipient_name(value: str | None) -> str:
    """Return a usable greeting name, excluding provider placeholder values."""
    normalized = " ".join((value or "").strip().split())
    if not normalized:
        return ""
    if normalized.lower() in PLACEHOLDER_RECIPIENT_NAMES:
        return ""
    if not any(char.isalnum() for char in normalized):
        return ""
    return normalized


def _automated_notice(sender_address: str) -> str:
    """Return the automated-message notice, optionally including sender identity."""
    if sender_address:
        return (
            f"This is an automated account security email from {sender_address}. "
            "Please do not reply to this message."
        )
    return "This is an automated account security email. Please do not reply to this message."


def _formatted_email_date() -> str:
    """Return the current local date for the email header."""
    today = timezone.localdate()
    return f"{today:%B} {today.day}, {today:%Y}"


def _confirmation_validity_line(minutes_valid: int) -> str:
    """Return a concise expiration sentence for confirmation-link emails."""
    if minutes_valid == 1:
        return "This verification link expires in 1 minute."
    return f"This verification link expires in {minutes_valid} minutes."
