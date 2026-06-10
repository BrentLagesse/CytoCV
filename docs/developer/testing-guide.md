# Testing Guide

## Purpose

This document explains the current automated test surface and the expected validation workflow for code changes.

## Test Location

The active test suite is under `cytocv/core/tests/`.

Current test modules:

- `test_accounts_preferences.py`
- `test_artifact_storage.py`
- `test_core_app.py`
- `test_mrcnn_inference.py`
- `test_nuclear_cell_pair_intensity.py`
- `test_scale_upload_initialization.py`
- `test_stats_cache.py`
- `test_stats_validation.py`
- `test_tables.py`
- `test_upload_preparation.py`
- `test_upload_length_scale.py`

## What The Tests Cover

- normalization and persistence of account preferences
- artifact storage cleanup and quota behavior
- inference-path behavior
- staged upload-preparation APIs and worker jobs
- async analysis jobs, worker claiming, and progress endpoints
- table rendering and export support
- scale initialization and upload-time scale handling
- plugin and stats validation behavior

## Standard Validation Workflow

From `cytocv/`:

```powershell
python manage.py test
```

When working on a narrower area, run the relevant subset first and then rerun the full suite before finalizing.

For frontend template/static changes, run:

```powershell
python manage.py check
python manage.py collectstatic --dry-run --noinput
python manage.py test core.tests.test_core_app
python manage.py test core.tests.test_accounts_preferences
python manage.py test
```

There is no npm build, lint, or typecheck step. If Node is available, `node --check` is useful as an additional syntax check for changed static JavaScript files.

## High-Risk Areas Requiring Extra Manual Review

- upload validation rules
- scale conversion and metadata fallback behavior
- save versus transient ownership transitions
- display serialization for new statistics fields
- template JSON config blocks and page-controller expectations
- auth and account flows with reCAPTCHA or provider login enabled

## Documentation Validation

For documentation changes, verify:

- every link in `README.md` and `docs/README.md`
- route names and endpoint semantics against current code
- environment variables against `settings.py` and `.env.example`
- diagram file names against the actual diagram catalog

## Related Documents

- [`contributing.md`](contributing.md)
- [`frontend-architecture.md`](frontend-architecture.md)
- [`../ops/environment-reference.md`](../ops/environment-reference.md)
