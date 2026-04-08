# Environment Reference

## Purpose

This document is the authoritative reference for environment variables consumed by the current application code.

## Core Settings

### `CYTOCV_SECRET_KEY`

- Required: yes in production
- Type: string
- Default: `django-insecure-change-me-in-env`
- Effect: Django secret key
- Notes: production startup fails if `CYTOCV_DEBUG=0` and the value is blank or a known placeholder

### `CYTOCV_DEBUG`

- Required: yes in practice
- Type: boolean-like string
- Default: `1`
- Effect: enables debug mode and relaxes several production protections

### `CYTOCV_ALLOWED_HOSTS`

- Required: yes in production
- Type: comma-separated host list
- Default: empty string
- Effect: populates Django `ALLOWED_HOSTS`
- Notes: `SECURITY_STRICT` requires explicit non-wildcard hosts

### `CYTOCV_ANALYSIS_EXECUTION_MODE`

- Required: no
- Type: enum
- Allowed values: `sync`, `worker`
- Default: `sync`
- Effect: selects whether heavy analysis runs inline in the web flow or is queued for the database-backed worker
- Notes:
  - `sync` preserves the local-development-friendly request flow
  - `worker` is the recommended production mode because it keeps Gunicorn from owning long-running segmentation/statistics work

### `CYTOCV_SEGMENT_SAVE_DEBUG_ARTIFACTS`

- Required: no
- Type: boolean-like string
- Default: `0`
- Effect: enables per-cell debug overlay PNG writes during segmentation
- Notes:
  - keep disabled in production unless you are actively debugging segmentation output or need raster debug exports
  - disabling this setting removes unnecessary PNG work from the hot path
  - fluorescence contours remain available in the UI even when this is disabled because contour-on views are rendered through the exact overlay replay endpoint

## Database Settings

### `CYTOCV_DB_BACKEND`

- Required: yes
- Type: enum
- Allowed values: `sqlite`, `postgres`
- Effect: selects the active database backend

### `CYTOCV_DB_NAME`

- Required: yes when backend is `postgres`
- Type: string
- Effect: PostgreSQL database name

### `CYTOCV_DB_USER`

- Required: yes when backend is `postgres`
- Type: string
- Effect: PostgreSQL username

### `CYTOCV_DB_PASSWORD`

- Required: yes when backend is `postgres`
- Type: string
- Effect: PostgreSQL password

### `CYTOCV_DB_HOST`

- Required: no
- Type: string
- Default: `127.0.0.1`
- Effect: PostgreSQL host

### `CYTOCV_DB_PORT`

- Required: no
- Type: integer
- Default: `5432`
- Effect: PostgreSQL port

### `CYTOCV_DB_CONN_MAX_AGE`

- Required: no
- Type: integer
- Default: `60`
- Effect: Django persistent connection age for PostgreSQL

### `CYTOCV_DB_ATOMIC_REQUESTS`

- Required: no
- Type: boolean-like string
- Default: `0`
- Effect: toggles Django atomic requests for PostgreSQL

### `CYTOCV_DB_SSLMODE`

- Required: no
- Type: string
- Default: `prefer`
- Effect: PostgreSQL SSL mode passed through `OPTIONS`

## OAuth Provider Settings

### `CYTOCV_GOOGLE_CLIENT_ID`

- Required: no
- Type: string
- Effect: Google OAuth client identifier

### `CYTOCV_GOOGLE_CLIENT_SECRET`

- Required: no
- Type: string
- Effect: Google OAuth client secret

### `CYTOCV_MICROSOFT_CLIENT_ID`

- Required: no
- Type: string
- Effect: Microsoft OAuth client identifier

### `CYTOCV_MICROSOFT_CLIENT_SECRET`

- Required: no
- Type: string
- Effect: Microsoft OAuth client secret

### `CYTOCV_MICROSOFT_TENANT`

- Required: no
- Type: string
- Default: `organizations`
- Effect: tenant selector for the Microsoft provider

### `CYTOCV_MICROSOFT_LOGIN_URL`

- Required: no
- Type: string
- Default: `https://login.microsoftonline.com`
- Effect: Microsoft identity endpoint base URL

## Account And Email Settings

### `CYTOCV_ACCOUNT_EMAIL_VERIFICATION`

- Required: no
- Type: enum
- Allowed values: `none`, `optional`, `mandatory`
- Default: `none` when debug is on, `optional` otherwise
- Effect: allauth email verification mode

### `CYTOCV_EMAIL_BACKEND`

- Required: no
- Type: string
- Default: `django.core.mail.backends.smtp.EmailBackend`
- Effect: Django email backend class

### `CYTOCV_EMAIL_HOST`

- Required: no
- Type: string
- Default: `127.0.0.1`
- Effect: SMTP host

### `CYTOCV_EMAIL_HOST_USER`

- Required: no
- Type: string
- Default: empty
- Effect: SMTP username

### `CYTOCV_EMAIL_HOST_PASSWORD`

- Required: no
- Type: string
- Default: empty
- Effect: SMTP password or app password

### `CYTOCV_EMAIL_PORT`

- Required: no
- Type: integer
- Default: `25`
- Effect: SMTP port

### `CYTOCV_EMAIL_USE_TLS`

- Required: no
- Type: boolean-like string
- Default: `0`
- Effect: enables TLS
- Notes: cannot be enabled together with `CYTOCV_EMAIL_USE_SSL`

### `CYTOCV_EMAIL_USE_SSL`

- Required: no
- Type: boolean-like string
- Default: `0`
- Effect: enables SSL

### `CYTOCV_EMAIL_TIMEOUT`

- Required: no
- Type: integer or blank
- Default: blank, which maps to Django default timeout behavior
- Effect: SMTP timeout

### `CYTOCV_DEFAULT_FROM_EMAIL`

- Required: no
- Type: string
- Default: empty, then falls back to `CYTOCV_EMAIL_HOST_USER`
- Effect: default sender

### `CYTOCV_EMAIL_REPLY_TO`

- Required: no
- Type: string
- Default: empty, then falls back to `CYTOCV_DEFAULT_FROM_EMAIL`
- Effect: reply-to address

## Storage Quota Settings

### `CYTOCV_QUOTA_DEFAULT_MB`

- Required: no
- Type: non-negative integer
- Default: `100`
- Effect: saved-storage quota in MB for accounts that do not match an education suffix

### `CYTOCV_QUOTA_EDU_MB`

- Required: no
- Type: non-negative integer
- Default: `1024`
- Effect: saved-storage quota in MB for accounts whose domain matches `CYTOCV_QUOTA_EDU_SUFFIXES`

### `CYTOCV_QUOTA_EDU_SUFFIXES`

- Required: no
- Type: comma-separated suffix list
- Default: `.edu`
- Effect: domain suffixes that receive the education quota
- Notes: matching is case-insensitive and treats each suffix as a domain ending

### `CYTOCV_QUOTA_USER_FIXED_MB`

- Required: no
- Type: comma-separated `email:mb` list
- Default: empty
- Effect: assigns fixed total quotas in MB to specific email addresses before any admin override applies
- Notes: matching is case-insensitive and invalid or duplicate entries fail startup

## reCAPTCHA Settings

### `CYTOCV_RECAPTCHA_ENABLED`

- Required: no
- Type: boolean-like string
- Default: `0`
- Effect: enables reCAPTCHA validation in auth flows

### `CYTOCV_RECAPTCHA_SITE_KEY`

- Required: no
- Type: string
- Effect: frontend site key

### `CYTOCV_RECAPTCHA_SECRET_KEY`

- Required: no
- Type: string
- Effect: backend verification key

### `CYTOCV_RECAPTCHA_VERIFY_URL`

- Required: no
- Type: string
- Default: Google siteverify endpoint
- Effect: reCAPTCHA backend verify URL
- Notes: only honored outside production strict behavior when override is allowed or debug is enabled

### `CYTOCV_RECAPTCHA_ALLOW_VERIFY_URL_OVERRIDE`

- Required: no
- Type: boolean-like string
- Default: `0`
- Effect: allows non-default verify URL override

### `CYTOCV_RECAPTCHA_EXPECTED_HOSTNAMES`

- Required: no
- Type: comma-separated host list
- Default: `localhost,127.0.0.1` in debug, otherwise derived from allowed hosts
- Effect: expected hostnames for reCAPTCHA token validation

## Security And Rate Limit Settings

### `CYTOCV_SECURITY_STRICT`

- Required: no
- Type: boolean-like string
- Default: unset, which resolves to `not DEBUG`
- Effect: enables production-grade secure cookie, HSTS, SSL redirect, and host validation behavior

### `CYTOCV_RATE_LIMIT_ENABLED`

- Required: no
- Type: boolean-like string
- Default: `1`
- Effect: enables security rate limiting

### `CYTOCV_RATE_LIMIT_MODE`

- Required: no
- Type: string
- Default: `sliding`
- Effect: rate-limit mode stored in the security config payload

### `CYTOCV_RATE_LIMIT_MAX`

- Required: no
- Type: integer
- Default: `15`
- Effect: max attempts in the configured rate-limit window

### `CYTOCV_RATE_LIMIT_WINDOW`

- Required: no
- Type: integer
- Default: `60`
- Effect: rate-limit window in seconds

## Artifact Retention Setting

### `TRANSIENT_RUN_RETENTION_HOURS`

- Required: no
- Type: integer
- Default: `24` through code fallback
- Effect: stale transient run retention window used by artifact sweeping helpers
- Notes: this is read via `getattr(settings, ...)` and is not currently exposed in `.env.example`

## Validation Rules

Startup fails when:

- `CYTOCV_DB_BACKEND` is missing or invalid
- PostgreSQL is selected without required database credentials
- `CYTOCV_DEBUG=0` and SQLite is selected
- `CYTOCV_DEBUG=0` and the secret key remains insecure
- both `CYTOCV_EMAIL_USE_TLS` and `CYTOCV_EMAIL_USE_SSL` are enabled
- `CYTOCV_ACCOUNT_EMAIL_VERIFICATION` has an invalid value
- any storage quota MB value is negative or not an integer
- `CYTOCV_QUOTA_EDU_SUFFIXES` is empty
- `CYTOCV_QUOTA_USER_FIXED_MB` contains an invalid, malformed, or duplicate `email:mb` entry

## Related Documents

- [`deployment-guide.md`](deployment-guide.md)
- [`postgres-setup.md`](postgres-setup.md)
- [`security-and-privacy.md`](security-and-privacy.md)
