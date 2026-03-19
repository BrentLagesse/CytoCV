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
- security-strict behavior enabled by default when debug is off
- correct email, OAuth, and reCAPTCHA settings if those features are active

## Container Artifacts

The repository includes:

- `Dockerfile`
- `compose.yml`
- `start.sh`

These artifacts support containerized deployment, but the final environment still depends on correct `.env` provisioning and accessible media storage.

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

## Verification Checklist

After deployment:

1. run migrations
2. run `python manage.py check`
3. confirm login works
4. confirm upload and preprocess pages render
5. confirm one test `.dv` file can complete the full workflow
6. confirm protected media access works after login

## Related Documents

- [`environment-reference.md`](environment-reference.md)
- [`postgres-setup.md`](postgres-setup.md)
- [`backup-retention-and-storage.md`](backup-retention-and-storage.md)
