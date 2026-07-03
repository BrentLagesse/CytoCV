"""Helpers for email-tier upload and analysis access policies."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from accounts.quota_config import normalize_quota_email


ACCESS_TIER_STANDARD = "standard"
ACCESS_TIER_EDUCATION = "education"
ACCESS_TIER_UNRESTRICTED = "unrestricted"


@dataclass(frozen=True)
class AccessPolicy:
    """Resolved access policy for one authenticated user email."""

    tier: str
    upload_max_files: int | None
    analysis_max_active_jobs: int | None
    upload_limit_message: str | None
    analysis_limit_message: str | None

    @property
    def is_unrestricted(self) -> bool:
        """Return whether the policy removes upload and analysis caps."""

        return self.tier == ACCESS_TIER_UNRESTRICTED


def _normalized_domain(email: str | None) -> str:
    """Return the lower-cased domain portion used for tier matching."""

    normalized_email = normalize_quota_email(email)
    if "@" not in normalized_email:
        return ""
    return normalized_email.rsplit("@", 1)[1]


def _domain_matches_suffix(domain: str, suffix: str) -> bool:
    """Return whether an email domain matches an exact or dotted suffix rule."""

    token = str(suffix or "").strip().lower()
    if not domain or not token:
        return False
    bare = token.lstrip(".")
    compare = token if token.startswith(".") else f".{token}"
    return domain == bare or domain.endswith(compare)


def _education_domain_matches(email: str | None) -> bool:
    """Return whether the email belongs to an education-domain quota tier."""

    domain = _normalized_domain(email)
    suffixes = tuple(getattr(settings, "STORAGE_QUOTA_EDU_SUFFIXES", ()))
    for suffix in suffixes:
        if _domain_matches_suffix(domain, suffix):
            return True
    return False


def get_access_policy_for_email(email: str | None) -> AccessPolicy:
    """Resolve the upload/analysis access tier for an email."""

    normalized_email = normalize_quota_email(email)
    unrestricted_emails = set(getattr(settings, "ACCESS_UNRESTRICTED_EMAILS", ()))
    if normalized_email and normalized_email in unrestricted_emails:
        # Exact email allowlist wins over domain rules so specific collaborators
        # can be granted uncapped uploads without changing global tier settings.
        return AccessPolicy(
            tier=ACCESS_TIER_UNRESTRICTED,
            upload_max_files=None,
            analysis_max_active_jobs=None,
            upload_limit_message=None,
            analysis_limit_message=None,
        )

    if _education_domain_matches(normalized_email):
        # Education-tier caps are intentionally higher but still finite to protect
        # worker and storage capacity for shared deployments.
        upload_max_files = int(getattr(settings, "UPLOAD_LIMIT_EDU_MAX_FILES", 20))
        analysis_max_active_jobs = int(
            getattr(settings, "ANALYSIS_LIMIT_EDU_MAX_ACTIVE_JOBS", 2)
        )
        return AccessPolicy(
            tier=ACCESS_TIER_EDUCATION,
            upload_max_files=upload_max_files,
            analysis_max_active_jobs=analysis_max_active_jobs,
            upload_limit_message=(
                f"Education accounts can preprocess up to {upload_max_files} "
                f"{'file' if upload_max_files == 1 else 'files'} at a time."
            ),
            analysis_limit_message=(
                f"Education accounts can have up to {analysis_max_active_jobs} active "
                f"analysis {'job' if analysis_max_active_jobs == 1 else 'jobs'} at a time."
            ),
        )

    upload_max_files = int(getattr(settings, "UPLOAD_LIMIT_DEFAULT_MAX_FILES", 1))
    analysis_max_active_jobs = int(
        getattr(settings, "ANALYSIS_LIMIT_DEFAULT_MAX_ACTIVE_JOBS", 1)
    )
    return AccessPolicy(
        tier=ACCESS_TIER_STANDARD,
        upload_max_files=upload_max_files,
        analysis_max_active_jobs=analysis_max_active_jobs,
        upload_limit_message=(
            f"Standard accounts can preprocess {upload_max_files} "
            f"{'file' if upload_max_files == 1 else 'files'} at a time."
        ),
        analysis_limit_message=(
            f"Standard accounts can have {analysis_max_active_jobs} active analysis "
            f"{'job' if analysis_max_active_jobs == 1 else 'jobs'} at a time."
        ),
    )


def get_access_policy_for_user(user: object) -> AccessPolicy:
    """Resolve the access policy for a user-like object."""

    return get_access_policy_for_email(getattr(user, "email", ""))


def build_upload_limit_error_lines(
    policy: AccessPolicy,
    *,
    requested_files: int,
) -> list[str]:
    """Return user-facing upload cap lines for a blocked submission."""

    if policy.upload_limit_message is None:
        return []
    file_word = "file" if requested_files == 1 else "files"
    return [
        policy.upload_limit_message,
        f"This submission includes {requested_files} {file_word} total.",
        "Reduce the selection and try again.",
    ]


def build_analysis_limit_error_message(policy: AccessPolicy) -> str:
    """Return a user-facing analysis queue cap message."""

    if policy.analysis_limit_message is None:
        return "You cannot start another analysis right now."
    return (
        f"{policy.analysis_limit_message} "
        "Wait for a running analysis to finish or cancel one before starting another."
    )
