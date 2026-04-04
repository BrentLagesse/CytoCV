"""Helpers for parsing and normalizing storage quota configuration."""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email

BYTES_PER_MB = 1024 * 1024


def normalize_quota_email(email: str | None) -> str:
    """Return a normalized email key for quota policy lookups."""

    return str(email or "").strip().lower()


def parse_quota_mb_value(*, raw_value: object, var_name: str) -> int:
    """Parse a non-negative megabyte value for a quota setting."""

    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(f"{var_name} must be a non-negative integer.") from exc
    if value < 0:
        raise ImproperlyConfigured(f"{var_name} must be a non-negative integer.")
    return value


def parse_quota_suffixes(
    raw_value: str | None,
    *,
    var_name: str = "CYTOCV_QUOTA_EDU_SUFFIXES",
) -> tuple[str, ...]:
    """Parse a comma-separated quota suffix list."""

    raw_tokens = [token.strip().lower() for token in str(raw_value or "").split(",")]
    suffixes = [token for token in raw_tokens if token]
    if not suffixes:
        raise ImproperlyConfigured(f"{var_name} must include at least one suffix.")

    normalized: list[str] = []
    seen: set[str] = set()
    for token in suffixes:
        if token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return tuple(normalized)


def parse_user_fixed_quota_map(
    raw_value: str | None,
    *,
    var_name: str = "CYTOCV_QUOTA_USER_FIXED_MB",
) -> dict[str, int]:
    """Parse a comma-separated email-to-quota map into bytes."""

    mapping: dict[str, int] = {}
    entries = [entry.strip() for entry in str(raw_value or "").split(",") if entry.strip()]
    for entry in entries:
        if ":" not in entry:
            raise ImproperlyConfigured(
                f"{var_name} entry '{entry}' must use the format email:mb."
            )
        email_part, mb_part = entry.split(":", 1)
        email = normalize_quota_email(email_part)
        if not email:
            raise ImproperlyConfigured(
                f"{var_name} entry '{entry}' is missing an email address."
            )
        try:
            validate_email(email)
        except ValidationError as exc:
            raise ImproperlyConfigured(
                f"{var_name} entry '{entry}' has an invalid email address."
            ) from exc
        if email in mapping:
            raise ImproperlyConfigured(
                f"{var_name} contains duplicate quota entries for '{email}'."
            )
        quota_mb = parse_quota_mb_value(raw_value=mb_part, var_name=var_name)
        mapping[email] = quota_mb * BYTES_PER_MB
    return mapping
