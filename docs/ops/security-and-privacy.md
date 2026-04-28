# Security And Privacy

## Purpose

This document summarizes the main security controls and privacy-relevant behaviors visible in the current codebase.

It is maintainer-facing and intentionally keeps live secrets, host-specific values, and exact operational tuning out of the text.

## Authentication

CytoCV uses:

- a custom email-based user model
- a custom email authentication backend
- django-allauth provider support for Google and Microsoft
- optional email verification behavior
- optional reCAPTCHA gating for signup, login, and recovery flows

## Protected Media

Media is not assumed to be public. Protected media access is mediated through a login-protected application route that validates ownership before serving run-related assets.

## Security Headers

The settings module configures:

- content security policy directives
- `X-Frame-Options=DENY`
- content-type nosniff
- same-origin referrer policy
- same-origin cross-origin opener policy

When `SECURITY_STRICT` is enabled, CytoCV also enables:

- secure cookies
- SSL redirect
- HSTS

## Rate Limiting

Rate limiting is configurable in the settings layer and enforced through dedicated security helpers. Public documentation intentionally does not publish live tuning values or deployment-specific thresholds.

## Secrets Handling

Sensitive values that must remain outside source control:

- `CYTOCV_SECRET_KEY`
- database credentials
- OAuth client secrets
- SMTP credentials
- reCAPTCHA secret key

`.env` should never be committed.

## Ownership And Data Visibility

Run visibility is governed by:

- authenticated user ownership on `UploadedImage`
- authenticated or guest ownership on `SegmentedImage`
- transient session UUID membership

This prevents one user from reading another user's retained outputs through normal routes.

## Privacy-Relevant Stored Data

CytoCV stores:

- account email addresses
- workflow preference payloads
- uploaded scientific image files
- derived images and measurement outputs

The application does not currently present itself as a general-purpose PHI or regulated-clinical system. Deployment owners must still define their own retention and access-control policy for stored scientific data.

## Related Documents

- [`environment-reference.md`](environment-reference.md)
- [`backup-retention-and-storage.md`](backup-retention-and-storage.md)
- [`../reference/data-model.md`](../reference/data-model.md)
