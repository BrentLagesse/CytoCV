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
- separate supervision for the background analysis worker when `CYTOCV_ANALYSIS_EXECUTION_MODE=worker`

## Worker Deployment

Recommended production shape:

1. keep the web process on Gunicorn
2. set `CYTOCV_ANALYSIS_EXECUTION_MODE=worker`
3. run a separate long-lived worker process:
   `python manage.py run_analysis_worker`
4. restart both web and worker after deploying code or migrations

Example `systemd` service command:

`/path/to/venv/bin/python /path/to/repo/cytocv/manage.py run_analysis_worker`

Rollback guidance:

- if the worker is unavailable, set `CYTOCV_ANALYSIS_EXECUTION_MODE=sync` and restart the web process to fall back to the legacy request-driven flow
- keep `CYTOCV_SEGMENT_SAVE_DEBUG_ARTIFACTS=0` unless you explicitly need debug overlays

## Root Cause Note

Heavy segmentation and statistics work should not run in production Gunicorn workers. The original timeout came from request-owned PNG generation and statistics execution exceeding the Gunicorn worker timeout, which then killed the worker mid-write. Worker mode moves that long-running compute out of the request path.

## Verification Checklist

After deployment:

1. run migrations
2. run `python manage.py check`
3. if worker mode is enabled, start `python manage.py run_analysis_worker`
4. confirm login works
5. confirm upload and preprocess pages render
6. confirm one test `.dv` file can complete the full workflow
7. confirm protected media access works after login

## Related Documents

- [`environment-reference.md`](environment-reference.md)
- [`postgres-setup.md`](postgres-setup.md)
- [`backup-retention-and-storage.md`](backup-retention-and-storage.md)

