"""Storage quota policy helpers for environment defaults and admin overrides."""

from __future__ import annotations

from django.conf import settings

from accounts.quota_config import normalize_quota_email
from core.services.artifact_storage import refresh_user_storage_usage


def _normalized_domain(email: str | None) -> str:
    normalized_email = normalize_quota_email(email)
    if "@" not in normalized_email:
        return ""
    return normalized_email.rsplit("@", 1)[1]


def _domain_matches_suffix(domain: str, suffix: str) -> bool:
    token = str(suffix or "").strip().lower()
    if not domain or not token:
        return False
    bare = token.lstrip(".")
    compare = token if token.startswith(".") else f".{token}"
    return domain == bare or domain.endswith(compare)


def get_env_fixed_quota_bytes_for_email(email: str | None) -> int | None:
    """Return an env-configured fixed quota for an email, if present."""

    normalized_email = normalize_quota_email(email)
    return getattr(settings, "STORAGE_QUOTA_USER_FIXED_BYTES", {}).get(normalized_email)


def get_base_quota_source_for_email(email: str | None) -> str:
    """Describe the env policy source that contributes the base quota."""

    normalized_email = normalize_quota_email(email)
    fixed_quota = get_env_fixed_quota_bytes_for_email(normalized_email)
    if fixed_quota is not None:
        return f"Env fixed-email override ({normalized_email})"

    domain = _normalized_domain(normalized_email)
    suffixes = tuple(getattr(settings, "STORAGE_QUOTA_EDU_SUFFIXES", ()))
    for suffix in suffixes:
        if _domain_matches_suffix(domain, suffix):
            return f"Env domain rule ({suffix})"
    return "Env default rule"


def get_base_quota_bytes_for_email(email: str | None) -> int:
    """Return the env-derived base quota for an email."""

    fixed_quota = get_env_fixed_quota_bytes_for_email(email)
    if fixed_quota is not None:
        return int(fixed_quota)

    domain = _normalized_domain(email)
    suffixes = tuple(getattr(settings, "STORAGE_QUOTA_EDU_SUFFIXES", ()))
    for suffix in suffixes:
        if _domain_matches_suffix(domain, suffix):
            return int(getattr(settings, "STORAGE_QUOTA_EDU_BYTES", 0))
    return int(getattr(settings, "STORAGE_QUOTA_DEFAULT_BYTES", 0))


def get_effective_quota_bytes(user: object) -> int:
    """Return the final quota after admin overrides are applied."""

    base_quota = get_base_quota_bytes_for_email(getattr(user, "email", ""))
    mode = str(
        getattr(
            user,
            "quota_override_mode",
            getattr(getattr(user, "QuotaOverrideMode", object), "DEFAULT", "default"),
        )
        or "default"
    )
    override_bytes = getattr(user, "quota_override_bytes", None)
    normalized_override = (
        max(int(override_bytes), 0)
        if override_bytes is not None
        else None
    )

    if mode == "fixed" and normalized_override is not None:
        return normalized_override
    if mode == "bonus" and normalized_override is not None:
        return base_quota + normalized_override
    return base_quota


def sync_user_quota(user: object, *, refresh_usage: bool = True) -> int:
    """Persist the effective quota onto the user row and update cached usage."""

    effective_quota = max(int(get_effective_quota_bytes(user)), 0)
    current_used = max(int(getattr(user, "used_storage", 0) or 0), 0)
    current_available = max(effective_quota - current_used, 0)

    if getattr(user, "pk", None) is None:
        user.total_storage = effective_quota
        user.available_storage = current_available
        return effective_quota

    update_payload: dict[str, int] = {}
    if int(getattr(user, "total_storage", 0) or 0) != effective_quota:
        update_payload["total_storage"] = effective_quota
        user.total_storage = effective_quota
    if not refresh_usage and int(getattr(user, "available_storage", 0) or 0) != current_available:
        update_payload["available_storage"] = current_available
        user.available_storage = current_available
    if update_payload:
        user.__class__.objects.filter(pk=user.pk).update(**update_payload)

    if refresh_usage:
        refreshed = refresh_user_storage_usage(user)
        user.available_storage = int(refreshed.get("available_storage", 0) or 0)
        user.used_storage = int(refreshed.get("used_storage", 0) or 0)
    return effective_quota
