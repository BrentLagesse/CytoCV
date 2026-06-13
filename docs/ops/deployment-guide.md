# Deployment Guide

## Purpose

This guide summarizes supported local and production deployment shapes for the current codebase.

Use this as the active deployment summary. Keep host-specific rollout notes, credentials, and infrastructure-specific values out of this file.

## Supported Deployment Shapes

- local development with SQLite
- local or server deployment with PostgreSQL
- containerized deployment with the included Docker artifacts

## Local Development

Recommended local development flow:

1. use Python `3.11.5`
2. create a virtual environment
3. install dependencies from `requirements.txt`
4. copy `.env.example` to `.env`
5. set `CYTOCV_DB_BACKEND=sqlite`
6. run migrations from `cytocv/`
7. start `runserver`
8. start `python manage.py run_analysis_worker` in a second terminal when testing upload preparation or worker-mode analysis

SQLite is intended only for development and testing.

## Production Expectations

Production expectations in the current codebase:

- PostgreSQL backend
- `CYTOCV_DEBUG=0`
- strong non-default `CYTOCV_SECRET_KEY`
- explicit `CYTOCV_ALLOWED_HOSTS`
- `CYTOCV_ANALYSIS_EXECUTION_MODE=worker`
- security-strict behavior enabled by default when debug is off
- correct email, OAuth, and reCAPTCHA settings if those features are active
- a running upload-preparation worker plus a running analysis worker
- a timer-driven artifact-maintenance sweep

## Container Artifacts

The repository includes:

- `Dockerfile`
- `compose.yml`
- `start.sh`

These artifacts support containerized deployment, but the final environment still depends on correct `.env` provisioning and accessible media storage.
The current `start.sh` runs `makemigrations` for `accounts` and `core` before
`migrate` and Gunicorn. Treat that as current runtime behavior when using this
script; controlled production deployments should still review generated
migration changes before rollout rather than relying on startup-time migration
generation.

Optional worker startup paths:

- Docker Compose includes an optional `analysis-worker` service profile
- local or server installs can run `python manage.py run_analysis_worker`
- production should supervise the split workers separately from Gunicorn
- repo-owned example `systemd` units live under `deploy/systemd/`

## Application Startup Sequence

At startup, the Django settings module:

- loads `.env` values without overriding explicit process environment values
- validates database backend selection
- validates production secret-key safety
- configures provider auth, email, reCAPTCHA, CSP, and security headers

## Existing VM Code Update

For an already provisioned `systemd` / Nginx VM, update the existing checkout
rather than recloning the application.

If the checkout path is uncertain, locate the repository first:

```bash
find ~ -maxdepth 3 -type d -name ".git" 2>/dev/null
```

Then move to the parent directory of the `.git` path and verify the branch:

```bash
cd /path/to/CytoCV
git status
git branch --show-current
git fetch origin
git pull --ff-only origin main
```

`git pull --ff-only origin main` is appropriate when the deployed checkout can
advance directly to `origin/main`, even if the local branch is named for the
deployment or maintainer. If this command fails, stop and reconcile the branch
state instead of forcing a reset. Untracked `cytocv/staticfiles/` content is
normal on deployments that run `collectstatic` locally.

After pulling code, run the Django deployment checks from the virtual
environment:

```bash
source cyto_cv/bin/activate
cd cytocv
python manage.py migrate
python manage.py check
python manage.py collectstatic --noinput
```

Restart the supervised processes:

```bash
sudo systemctl restart cytocv
sudo systemctl restart cytocv-upload-prep-worker
sudo systemctl restart cytocv-analysis-worker
sudo systemctl restart cytocv-artifact-maintenance.timer
```

Validate and reload Nginx when proxy configuration or static-file handling may
have changed:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

If the deployment `.env` needs editing, open the actual repository path, not a
placeholder path:

```bash
cd /actual/CytoCV/checkout
nano .env
```

## Operational Concerns

Production deployment should account for:

- media storage capacity
- retained storage quotas
- email-tier upload and analysis caps if the deployment wants differentiated limits for unrestricted exact-email allowlists, `.edu` domains, and everyone else
- backup of media and database data
- presence of required ML weights
- email connectivity if recovery and verification flows are active
- separate supervision for the upload-preparation worker, analysis worker, and artifact-maintenance timer
- an upload batch target below the reverse proxy body-size limit, for example default `CYTOCV_UPLOAD_BATCH_TARGET_BYTES=83886080` with Nginx `client_max_body_size 100M`

## Reverse Proxy Upload Limits

Large uploads can be rejected by Nginx before Django or the background worker
ever sees the request. That limit must be configured on the deployed VM or
whatever reverse proxy host sits in front of Gunicorn.

Current upload-size relationship:

- browser upload batch target: `CYTOCV_UPLOAD_BATCH_TARGET_BYTES=83886080` (`80 MiB`)
- documented minimum Nginx headroom for that default: `client_max_body_size 100M`
- if you raise `CYTOCV_UPLOAD_BATCH_TARGET_BYTES`, raise `client_max_body_size` too

Repository support:

- repo-owned Nginx example: `deploy/nginx/cytocv.nginx.conf.example`
- repo-owned Gunicorn / worker examples: `deploy/systemd/`

Django notes:

- this repo does not currently override `DATA_UPLOAD_MAX_MEMORY_SIZE` or `FILE_UPLOAD_MAX_MEMORY_SIZE`
- the current app behavior relies on Django's normal upload handling plus the browser-side batch target
- in practice, Nginx `client_max_body_size` is the first hard limit that must be aligned in production

## Access Tier Limits

The current codebase can enforce differentiated upload and analysis limits by
email tier:

- unrestricted exact-email allowlist: `CYTOCV_ACCESS_UNRESTRICTED_EMAILS`
- education domains: `CYTOCV_QUOTA_EDU_SUFFIXES`
- default tier: everyone else

Default limits in the repo template:

- default tier: `CYTOCV_UPLOAD_LIMIT_DEFAULT_MAX_FILES=1`
- education tier: `CYTOCV_UPLOAD_LIMIT_EDU_MAX_FILES=20`
- default tier: `CYTOCV_ANALYSIS_LIMIT_DEFAULT_MAX_ACTIVE_JOBS=1`
- education tier: `CYTOCV_ANALYSIS_LIMIT_EDU_MAX_ACTIVE_JOBS=2`

Exact-email allowlist matches bypass both caps entirely. Domain matching is
case-insensitive and reuses the same `.edu` suffix list already used for stored
quota policy.

## Worker Deployment

Recommended production shape:

1. keep the web process on Gunicorn with `--workers 3` on the current VM
2. set `CYTOCV_ANALYSIS_EXECUTION_MODE=worker`
3. run a dedicated upload-preparation worker:
   `python manage.py run_analysis_worker --job-type upload-preparation --skip-maintenance`
4. run a dedicated analysis worker:
   `python manage.py run_analysis_worker --job-type analysis --skip-maintenance`
5. run `python manage.py run_artifact_maintenance` from a timer every 5 minutes
6. restart web, both workers, and the maintenance timer after deploying code or migrations

Example `systemd` service commands:

- `/path/to/venv/bin/gunicorn --workers 3 --timeout 120 --bind 127.0.0.1:8000 cytocv.wsgi:application`
- `/path/to/venv/bin/python /path/to/repo/cytocv/manage.py run_analysis_worker --job-type upload-preparation --skip-maintenance`
- `/path/to/venv/bin/python /path/to/repo/cytocv/manage.py run_analysis_worker --job-type analysis --skip-maintenance`
- `/path/to/venv/bin/python /path/to/repo/cytocv/manage.py run_artifact_maintenance`

Repository examples:

- `deploy/systemd/cytocv.service.example`
- `deploy/systemd/cytocv-upload-prep-worker.service.example`
- `deploy/systemd/cytocv-analysis-worker.service.example`
- `deploy/systemd/cytocv-artifact-maintenance.service.example`
- `deploy/systemd/cytocv-artifact-maintenance.timer.example`
- `deploy/nginx/cytocv.nginx.conf.example`

These example units should be copied to `/etc/systemd/system/` and adjusted for
the actual deploy user and checkout path.

Rollback guidance:

- if the upload-preparation worker is unavailable, new staged uploads will remain queued; restore or restart that worker before accepting production traffic
- if the analysis worker is unavailable, upload preparation still completes but analysis batches remain queued until that worker returns
- `CYTOCV_ANALYSIS_EXECUTION_MODE=sync` falls upload preparation and analysis back to the request-owned path
- keep `CYTOCV_SEGMENT_SAVE_DEBUG_ARTIFACTS=0` unless you explicitly need debug overlays

## Intentional Database Data Reset

Use this path only when the intended result is an empty production database
while keeping the PostgreSQL database, schema, and service configuration. This
deletes application data such as users, uploads, jobs, sessions, and auth
records. It does not remove uploaded media or collected static files from disk.

Create a backup before flushing. `pg_dump` must connect with the configured
PostgreSQL role from `.env`; otherwise it may default to the Linux account and
fail with a missing-role error.

```bash
cd /path/to/CytoCV
set -a
source .env
set +a

PGPASSWORD="$CYTOCV_DB_PASSWORD" pg_dump \
  -h "${CYTOCV_DB_HOST:-127.0.0.1}" \
  -p "${CYTOCV_DB_PORT:-5432}" \
  -U "$CYTOCV_DB_USER" \
  "$CYTOCV_DB_NAME" > cytocv-before-flush.sql
```

Stop the web process and workers before deleting data:

```bash
sudo systemctl stop cytocv
sudo systemctl stop cytocv-upload-prep-worker
sudo systemctl stop cytocv-analysis-worker
sudo systemctl stop cytocv-artifact-maintenance.timer
```

Flush through Django so the schema remains intact:

```bash
source cyto_cv/bin/activate
cd cytocv
python manage.py flush
python manage.py migrate
python manage.py check
```

Restart the deployment:

```bash
sudo systemctl start cytocv
sudo systemctl start cytocv-upload-prep-worker
sudo systemctl start cytocv-analysis-worker
sudo systemctl start cytocv-artifact-maintenance.timer
```

## Root Cause Note

Heavy upload preparation, segmentation, and statistics work should not run in production Gunicorn workers. The upload flow now sends selected files in bounded browser requests, then queues validation, scale extraction, channel config writing, and preview generation to the background worker. Worker mode also moves the long-running analysis pipeline out of the request path.

## Verification Checklist

After deployment:

1. run migrations
2. run `python manage.py check`
3. if worker mode is enabled, start both split worker services and the artifact-maintenance timer
4. confirm the upload-preparation worker can process a staged upload-preparation job
5. confirm the analysis worker can process a queued analysis batch
6. confirm the maintenance timer fires successfully
7. confirm login works
8. confirm upload and preprocess pages render
9. confirm one test `.dv` file can complete the full workflow
10. confirm protected media access works after login

## Related Documents

- [`environment-reference.md`](environment-reference.md)
- [`postgres-setup.md`](postgres-setup.md)
- [`backup-retention-and-storage.md`](backup-retention-and-storage.md)
