# CytoCV VM Deployment Guide

This is a sanitized maintainer guide for deploying CytoCV on a Linux VM. Use it alongside the canonical operations docs:

- [`../ops/deployment-guide.md`](../ops/deployment-guide.md)
- [`../ops/environment-reference.md`](../ops/environment-reference.md)
- [`../ops/postgres-setup.md`](../ops/postgres-setup.md)
- [`../../deploy/systemd/README.md`](../../deploy/systemd/README.md)

Do not record live hostnames, IP addresses, usernames, secrets, provider credentials, or organization-specific email settings in this file.

## Before You Start

You should have all of the following before treating a VM as deployment-ready:

- a Linux VM with `sudo` access
- a public hostname prepared for HTTPS
- Python `3.11.5`, or an approved maintainer process for installing that exact interpreter
- PostgreSQL for production data
- access to the required Mask R-CNN weights file
- an analysis-capable CPU environment
- a supervision path for both the web process and the background worker

If a deployment will enable email, OAuth providers, or reCAPTCHA, gather those settings separately and keep the live values in deployment-managed configuration rather than repository documentation.

## 1. Verify CPU Capability

The analysis pipeline depends on a TensorFlow-compatible CPU environment. Verify `AVX` support before spending time on the rest of the rollout:

```bash
lscpu | grep -i avx
```

If this returns nothing, the VM may still be able to host the web interface, but it should not be treated as analysis-capable.

## 2. Clone The Repository And Create The Environment

Typical setup flow:

```bash
git clone https://github.com/BrentLagesse/CytoCV.git
cd CytoCV
python3.11 -m venv cyto_cv
source cyto_cv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt --no-cache-dir
```

If the base distribution does not provide Python `3.11.5` directly, install that interpreter through an approved maintainer process before continuing. Do not silently switch the deployment to Python `3.12` without revalidating the scientific stack.

## 3. Place The Required Model Weights

The active runtime expects the weights file here:

```text
cytocv/core/weights/deepretina_final.h5
```

Do not assume that an alternate weights directory is sufficient unless the runtime has been intentionally changed.

## 4. Configure The Environment

Create the deployment `.env` from your deployment-managed template or from `.env.example`, then set at minimum:

- `CYTOCV_DEBUG=0`
- explicit `CYTOCV_ALLOWED_HOSTS`
- `CYTOCV_DB_BACKEND=postgres`
- a strong `CYTOCV_SECRET_KEY`
- production-appropriate email, provider, and reCAPTCHA settings only if those features are enabled
- `CYTOCV_ANALYSIS_EXECUTION_MODE=worker` for production analysis

Use [`../ops/environment-reference.md`](../ops/environment-reference.md) for variable meanings. Keep live values out of shared docs.

## 5. Provision PostgreSQL And Apply The Schema

Use [`../ops/postgres-setup.md`](../ops/postgres-setup.md) for the PostgreSQL setup steps.

After PostgreSQL is ready, apply the standard Django schema path:

```bash
cd cytocv
python manage.py migrate
python manage.py check
```

The current repository includes tracked migrations for `accounts` and `core`, so a clean checkout should use the normal `migrate` path first.

## 6. Smoke-Test Django Before Adding Process Supervision

Before adding Gunicorn, the worker, or the reverse proxy, confirm that Django boots cleanly:

```bash
cd cytocv
python manage.py runserver 0.0.0.0:8000
```

Verify at least:

- the homepage loads
- sign-in renders
- the authenticated upload page is reachable

Stop the development server before moving on.

## 7. Configure Gunicorn And The Background Worker

Production should not leave upload preparation or long-running analysis inside request-owned web workers.

Use the repository-owned `systemd` examples under [`../../deploy/systemd/`](../../deploy/systemd/) and replace the placeholder user and path values with deployment-specific values outside this document.

Operational expectations:

- run Gunicorn or an equivalent supervised web process
- run a dedicated upload-preparation worker
- run a dedicated analysis worker
- run a timer-driven artifact-maintenance sweep
- restart web, both workers, and the timer after code or migration updates

The upload-preparation worker is required for staged uploads. In worker analysis mode, the analysis worker owns queued analysis jobs after preprocess review.

## 8. Configure The Reverse Proxy And HTTPS

At the proxy layer:

- forward application traffic to the local web service
- keep the upload body limit above the configured upload batch target
- serve collected static files if the deployment uses proxy-level static handling
- terminate HTTPS for the intended public hostname

Do not expose protected run media directly through a public proxy alias. Protected result assets should continue to flow through the authenticated application route.

## 9. Configure Auth-Related Integrations Only If Needed

If a deployment enables provider sign-in, reCAPTCHA, or email-backed verification:

- keep redirect URIs and expected hostnames aligned with the deployed hostname
- keep secrets in deployment-managed configuration only
- keep the email verification policy compatible with working email delivery

If email delivery is not yet operational, do not enable a stricter verification mode that blocks legitimate sign-in or recovery flows.

## 10. Verification Checklist

After deployment, verify:

1. `python manage.py migrate` and `python manage.py check` succeed
2. the web service is running
3. the background worker is running
4. one staged upload-preparation job completes
5. one known-good `.dv` file can reach preprocess
6. one known-good `.dv` file can complete analysis on an AVX-capable host
7. display, dashboard, and CSV/XLSX export work for a signed-in account
8. protected result assets load only through authenticated access

## 11. Existing VM Maintenance

For an already deployed VM, use the active operations guide rather than
re-running the new-host provisioning sequence:

- existing checkout update path: [`../ops/deployment-guide.md#existing-vm-code-update`](../ops/deployment-guide.md#existing-vm-code-update)
- intentional data reset path: [`../ops/deployment-guide.md#intentional-database-data-reset`](../ops/deployment-guide.md#intentional-database-data-reset)

When the checkout path is uncertain, locate the repository before editing
deployment files:

```bash
find ~ -maxdepth 3 -type d -name "CytoCV"
```

Keep exact hostnames, account names, absolute paths, and SSH key material in
private operational records rather than shared repository documentation.

## Historical Lessons Preserved Here

- A VM can host the website but still fail analysis if the CPU environment is not compatible with the ML runtime.
- Protected media should stay behind application-controlled access checks.
- Linux deployment can surface filesystem permission or static-file issues that do not appear in local Windows development.
- Host-specific rollout notes belong in private operational records, not in shared repository documentation.
