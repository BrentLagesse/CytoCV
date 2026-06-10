# Testing Guide

## Purpose

This document explains the current automated test surface and the expected validation workflow for code changes.

## Test Location

The active test suite is under `cytocv/core/tests/`.

Current test modules:

- `test_accounts_preferences.py`
- `test_artifact_storage.py`
- `test_core_app.py`
- `test_frontend_export_contracts.py`
- `test_frontend_json_contracts.py`
- `test_frontend_js_contracts.py`
- `test_frontend_static_contracts.py`
- `test_frontend_template_contracts.py`
- `test_frontend_viewer_contracts.py`
- `test_frontend_workflow_contracts.py`
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
- frontend rendered-template contracts, static asset references, JSON config blocks, shared JavaScript globals, and frontend-facing response shapes

## Frontend Contract Tests

The frontend is Django-rendered HTML plus static CSS/JS, so regression coverage is centered on rendered contracts instead of browser snapshots.

- Template contract tests verify major pages render the expected template, CSS/JS includes, DOM hooks, JSON config scripts, and no inline styles.
- Static contract tests verify template `{% static %}` references resolve, CSS `url(...)` references exist, static JS contains no Django syntax, and debug/conflict markers are absent.
- JSON contract tests parse frontend config scripts and assert stable IDs, required keys, and basic value types.
- JavaScript contract tests verify owner files for public globals and run `node --check` when Node is available.
- Viewer/workflow/export contract tests cover page-specific hooks and frontend-facing endpoint response shapes without duplicating deeper backend behavior tests.

When adding a new frontend page, add a rendered-template contract for the page CSS/JS, required JSON config IDs, durable DOM hooks, and any shared-before-page load order that matters. When adding a config block, document the ID in `frontend-architecture.md` and add a JSON contract test for required keys and types. Avoid whole-response HTML snapshots and repeated status-only tests.

## Standard Validation Workflow

From `cytocv/`:

```powershell
python manage.py test
```

When working on a narrower area, run the relevant subset first and then rerun the full suite before finalizing.

For frontend template/static changes, run:

```powershell
Get-ChildItem -Path core/static/js -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
python manage.py check
python manage.py collectstatic --dry-run --noinput
python manage.py test core.tests.test_frontend_template_contracts
python manage.py test core.tests.test_frontend_static_contracts
python manage.py test core.tests.test_frontend_json_contracts
python manage.py test core.tests.test_frontend_js_contracts
python manage.py test core.tests.test_frontend_workflow_contracts
python manage.py test core.tests.test_frontend_viewer_contracts
python manage.py test core.tests.test_frontend_export_contracts
python manage.py test core.tests.test_core_app
python manage.py test core.tests.test_accounts_preferences
python manage.py test
```

There is no npm build, lint, or typecheck step. If Node is available, use `node --check` as the static JavaScript syntax check.

Browser automation is not part of the current dependency surface. After frontend refactors, manually smoke-test: home/about/auth pages, upload, workflow defaults, preprocess, display viewer, dashboard viewer, export modal, save/delete modals, previous/next navigation, image/table/stat controls, and a narrow responsive layout check.

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
