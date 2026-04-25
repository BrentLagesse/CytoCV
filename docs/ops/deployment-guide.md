# Deployment Guide

## Purpose

This guide summarizes supported local and production deployment shapes for the current codebase.

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
- a running `run_analysis_worker` process; staged uploads queue upload preparation there before the preprocess page is shown

## Container Artifacts

The repository includes:

- `Dockerfile`
- `compose.yml`
- `start.sh`

These artifacts support containerized deployment, but the final environment still depends on correct `.env` provisioning and accessible media storage.

Optional worker startup paths:

- Docker Compose includes an optional `analysis-worker` service profile
- local or server installs can run `python manage.py run_analysis_worker`
- production should supervise the worker separately from Gunicorn
- repo-owned example `systemd` units live under `deploy/systemd/`

## Application Startup Sequence

At startup, the Django settings module:

- loads `.env` values without overriding explicit process environment values
- validates database backend selection
- validates production secret-key safety
- configures provider auth, email, reCAPTCHA, CSP, and security headers

## Operational Concerns

Production deployment should account for:

- media storage capacity
- retained storage quotas
- backup of media and database data
- presence of required ML weights
- email connectivity if recovery and verification flows are active
- separate supervision for the background upload-preparation and analysis worker
- an upload batch target below the reverse proxy body-size limit, for example default `CYTOCV_UPLOAD_BATCH_TARGET_BYTES=83886080` with Nginx `client_max_body_size 100M`

## Worker Deployment

Recommended production shape:

1. keep the web process on Gunicorn
2. set `CYTOCV_ANALYSIS_EXECUTION_MODE=worker`
3. run a separate long-lived worker process for upload preparation and analysis:
   `python manage.py run_analysis_worker`
4. restart both web and worker after deploying code or migrations

Example `systemd` service command:

`/path/to/venv/bin/python /path/to/repo/cytocv/manage.py run_analysis_worker`

Repository examples:

- `deploy/systemd/cytocv.service.example`
- `deploy/systemd/cytocv-worker.service.example`

These example units should be copied to `/etc/systemd/system/` and adjusted for
the actual deploy user and checkout path.

Rollback guidance:

- if the worker is unavailable, new staged uploads will remain queued; restore or restart the worker before accepting production traffic
- `CYTOCV_ANALYSIS_EXECUTION_MODE=sync` only falls analysis back to the request-owned path after upload preparation has already completed
- keep `CYTOCV_SEGMENT_SAVE_DEBUG_ARTIFACTS=0` unless you explicitly need debug overlays

## Root Cause Note

Heavy upload preparation, segmentation, and statistics work should not run in production Gunicorn workers. The upload flow now sends selected files in bounded browser requests, then queues validation, scale extraction, channel config writing, and preview generation to the background worker. Worker mode also moves the long-running analysis pipeline out of the request path.

## Verification Checklist

After deployment:

1. run migrations
2. run `python manage.py check`
3. if worker mode is enabled, start `python manage.py run_analysis_worker`
4. confirm the worker can process a staged upload-preparation job
5. confirm login works
6. confirm upload and preprocess pages render
7. confirm one test `.dv` file can complete the full workflow
8. confirm protected media access works after login

## Related Documents

- [`environment-reference.md`](environment-reference.md)
- [`postgres-setup.md`](postgres-setup.md)
- [`backup-retention-and-storage.md`](backup-retention-and-storage.md)
