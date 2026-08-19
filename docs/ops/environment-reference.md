# Environment Reference

## Purpose

This document is the authoritative reference for environment variables consumed by the current application code.

This is a maintainer reference. Document variable names and behavior here, but do not record live production values, private hostnames, copied secret material, or organization-specific credentials in versioned documentation.

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
- Notes:
  - `SECURITY_STRICT` requires explicit non-wildcard hosts
  - keep the actual production host list in deployment-managed configuration, not in shared docs

### `CYTOCV_ANALYSIS_EXECUTION_MODE`

- Required: no
- Type: enum
- Allowed values: `sync`, `worker`
- Default: `sync`
- Effect: selects whether upload preparation and heavy analysis run inline in the web flow or are queued for the database-backed worker
- Notes:
  - `sync` preserves the local-development-friendly request flow for upload preparation and analysis
  - `worker` is the recommended production mode because it keeps Gunicorn from owning upload validation, preview generation, segmentation, and statistics work
  - when set to `worker`, the full upload workflow needs `python manage.py run_analysis_worker` running

### `CYTOCV_ANALYSIS_QUEUE_STALE_SECONDS`

- Required: no
- Type: positive integer seconds
- Default: `300`
- Effect: maximum age before a queued `AnalysisJob` is reported as stale
- Notes: used by the progress API and stale-job reaping helpers

### `CYTOCV_ANALYSIS_RUNNING_STALE_SECONDS`

- Required: no
- Type: positive integer seconds
- Default: `7200`
- Effect: maximum runtime before an active `AnalysisJob` is reported as stale
- Notes: long production analyses should stay below this or the value should be raised intentionally

### `CYTOCV_UPLOAD_PREPARATION_QUEUE_STALE_SECONDS`

- Required: no
- Type: positive integer seconds
- Default: `300`
- Effect: maximum age before a queued `UploadPreparationJob` is reported as stale
- Notes: used by upload-preparation status reads and stale-job reaping helpers

### `CYTOCV_UPLOAD_PREPARATION_RUNNING_STALE_SECONDS`

- Required: no
- Type: positive integer seconds
- Default: `1800`
- Effect: maximum runtime before an active `UploadPreparationJob` is reported as stale
- Notes: set this high enough for preview generation on the deployed host

### `CYTOCV_UPLOAD_BATCH_TARGET_BYTES`

- Required: no
- Type: positive integer bytes
- Default: `83886080` (`80 MiB`)
- Effect: browser-side target for splitting selected `.dv` files into multiple upload requests
- Notes:
  - keep this below the reverse proxy body-size limit, for example below `client_max_body_size 100M`
  - `client_max_body_size` is set in Nginx on the deployed VM or reverse proxy host, not in Django settings
  - the repo includes an example reverse-proxy fragment at `deploy/nginx/cytocv.nginx.conf.example`
  - this repo does not currently override Django `DATA_UPLOAD_MAX_MEMORY_SIZE` or `FILE_UPLOAD_MAX_MEMORY_SIZE`
  - this does not implement resumable chunking for a single oversized file; one file must fit inside one request

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
- Notes: CytoCV requests Microsoft's account picker on OAuth start with `prompt=select_account`. Microsoft still owns its browser session, so the provider may use its own session rules after the picker is shown.

## Account And Email Settings

### `CYTOCV_ACCOUNT_EMAIL_VERIFICATION`

- Required: no
- Type: enum
- Allowed values: `none`, `optional`, `mandatory`
- Default: `none` when debug is on, `optional` otherwise
- Effect: allauth email verification mode for Google/Microsoft provider accounts
- Notes:
  - native CytoCV signup and password recovery use the application's own verification-code flow
  - keep this setting aligned with working email delivery and the intended sign-in policy for the deployment

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

### `CYTOCV_AUTH_VERIFICATION_EXPIRY_MINUTES`

- Required: no
- Type: positive integer
- Default: `5`
- Effect: expiry window, in minutes, for native signup verification codes, password-recovery verification codes, and Google/Microsoft provider confirmation links
- Notes: this is separate from `CYTOCV_EMAIL_TIMEOUT`, which only controls SMTP connection/send timeout.

### `CYTOCV_DEFAULT_FROM_EMAIL`

- Required: no
- Type: string
- Default: empty, then falls back to `CYTOCV_SUPPORT_EMAIL`, then `CYTOCV_EMAIL_HOST_USER`
- Effect: general Django default sender for non-auth emails
- Notes: legacy/general fallback; normal CytoCV deployments should usually set only `CYTOCV_SUPPORT_EMAIL` and `CYTOCV_AUTH_EMAIL_FROM`

### `CYTOCV_EMAIL_REPLY_TO`

- Required: no
- Type: string
- Default: empty, then falls back to `CYTOCV_SUPPORT_EMAIL`, then `CYTOCV_DEFAULT_FROM_EMAIL`
- Effect: general Django reply-to address for non-auth emails
- Notes: legacy/general fallback; verification and password-reset emails intentionally use `CYTOCV_AUTH_EMAIL_FROM` as their reply-to address

### `CYTOCV_SUPPORT_EMAIL`

- Required: no
- Type: string
- Default: empty, then falls back to `CYTOCV_EMAIL_REPLY_TO`
- Effect: public CytoCV support contact available for future support pages and fallback sender behavior
- Example: `support@institution.example`

### `CYTOCV_AUTH_EMAIL_FROM`

- Required: no
- Type: string
- Default: empty, then falls back to `CYTOCV_DEFAULT_FROM_EMAIL`
- Effect: sender used for account verification and password recovery emails
- Notes: may include a display name, for example `"CytoCV <noreply@institution.example>"`, if the SMTP relay is authorized to send as that address.

### `CYTOCV_PUBLIC_BASE_URL`

- Required: no
- Type: URL
- Default: empty
- Effect: trusted public origin used for canonical page URLs, sitemap and `robots.txt` discovery URLs, and absolute static asset links in account emails
- Notes:
  - set this to the production HTTP(S) origin without a path, query string, fragment, or credentials
  - production CytoCV uses `https://cytocv.uwb.edu`
  - when empty, a request-origin fallback supports local development, but production deployments should set it explicitly so every discovery signal uses the same trusted host

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

## Access Tier Settings

### `CYTOCV_ACCESS_UNRESTRICTED_EMAILS`

- Required: no
- Type: comma-separated email list
- Default: empty
- Effect: exact-email allowlist that bypasses the upload file cap and the active analysis job cap
- Notes: matching is case-insensitive and invalid entries fail startup

### `CYTOCV_UPLOAD_LIMIT_DEFAULT_MAX_FILES`

- Required: no
- Type: positive integer
- Default: `1`
- Effect: maximum total files per upload-preparation submission for accounts outside the unrestricted allowlist and outside `CYTOCV_QUOTA_EDU_SUFFIXES`

### `CYTOCV_UPLOAD_LIMIT_EDU_MAX_FILES`

- Required: no
- Type: positive integer
- Default: `20`
- Effect: maximum total files per upload-preparation submission for accounts whose domain matches `CYTOCV_QUOTA_EDU_SUFFIXES`

### `CYTOCV_ANALYSIS_LIMIT_DEFAULT_MAX_ACTIVE_JOBS`

- Required: no
- Type: positive integer
- Default: `1`
- Effect: maximum active analysis jobs (`queued`, `running`, or `cancelling`) for accounts outside the unrestricted allowlist and outside `CYTOCV_QUOTA_EDU_SUFFIXES`

### `CYTOCV_ANALYSIS_LIMIT_EDU_MAX_ACTIVE_JOBS`

- Required: no
- Type: positive integer
- Default: `2`
- Effect: maximum active analysis jobs (`queued`, `running`, or `cancelling`) for accounts whose domain matches `CYTOCV_QUOTA_EDU_SUFFIXES`

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
- Notes: advanced override for controlled testing only; avoid custom values in normal production deployments

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
- Notes: set explicit approved public hostnames for deployed environments

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
- Default: maintainer-defined in settings
- Effect: max attempts in the configured rate-limit window
- Notes: keep the deployment's actual threshold in private operational records rather than shared repository documentation

### `CYTOCV_RATE_LIMIT_WINDOW`

- Required: no
- Type: integer
- Default: maintainer-defined in settings
- Effect: rate-limit window in seconds
- Notes: keep the deployment's actual threshold in private operational records rather than shared repository documentation

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
- `CYTOCV_ACCESS_UNRESTRICTED_EMAILS` contains an invalid email address
- any upload or analysis tier cap is less than `1`

## Related Documents

- [`deployment-guide.md`](deployment-guide.md)
- [`postgres-setup.md`](postgres-setup.md)
- [`security-and-privacy.md`](security-and-privacy.md)
