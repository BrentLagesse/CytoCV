# Testing Guide

## Purpose

This document explains the current automated test surface and the expected validation workflow for code changes.

## Test Locations

The active Django test suite is split across:

- `cytocv/core/tests/`
- `cytocv/accounts/tests_*.py`

The current baseline is 774 tests: 703 under `core` and 71 under `accounts`.
The suite includes upload preparation, TIFF/DV parsing, artifact storage,
progress and worker behavior, scientific-stat calculations, exports, frontend
contracts, account preferences, email alias behavior, and quota policy.

## What The Tests Cover

- normalization and persistence of account preferences
- artifact storage cleanup and quota behavior
- inference-path behavior
- staged upload-preparation APIs and worker jobs
- async analysis jobs, worker claiming, and progress endpoints
- table rendering and export support
- scale initialization and upload-time scale handling
- plugin and stats validation behavior
- exact artifact path contracts for generated media and overlay files
- protected media access, ownership, missing-file, and traversal contracts
- job status names and default queued-state fields for analysis and upload-preparation work
- Backend CI command and frontend-contract step contracts
- settings import behavior for CI/test SQLite and production SQLite rejection
- display/dashboard JSON payload keys used by the viewers
- supported source image extension contracts
- frontend rendered-template contracts, static asset references, JSON config blocks, shared JavaScript globals, and frontend-facing response shapes

## Frontend Contract Tests

The frontend is Django-rendered HTML plus static CSS/JS, so regression coverage is centered on rendered contracts instead of browser snapshots.

- Template contract tests verify major pages render the expected template, CSS/JS includes, DOM hooks, JSON config scripts, and no inline styles.
- Static contract tests verify template `{% static %}` references resolve, CSS `url(...)` references exist, static JS contains no Django syntax, and debug/conflict markers are absent.
- Dashboard quota fill width is rendered as a data attribute and applied by static JavaScript so templates keep the no-inline-style contract.
- JSON contract tests parse frontend config scripts and assert stable IDs, required keys, and basic value types.
- JavaScript contract tests verify owner files for public globals and run `node --check` when Node is available.
- Viewer/workflow/export contract tests cover page-specific hooks and frontend-facing endpoint response shapes without duplicating deeper backend behavior tests.

When adding a new frontend page, add a rendered-template contract for the page CSS/JS, required JSON config IDs, durable DOM hooks, and any shared-before-page load order that matters. When adding a config block, document the ID in `frontend-architecture.md` and add a JSON contract test for required keys and types. Avoid whole-response HTML snapshots and repeated status-only tests.

## Standard Validation Workflow

From `cytocv/`:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --dry-run --noinput
python manage.py test core
python manage.py test accounts
python manage.py test
```

When working on a narrower area, run the relevant subset first and then rerun the full suite before finalizing.

## Backend CI

GitHub Actions runs the backend safety gate in `.github/workflows/backend-ci.yml`.
The workflow uses Python 3.11.5 from `.python-version`, installs
`requirements.txt`, and runs `manage.py check`,
`manage.py makemigrations --check --dry-run`,
`manage.py collectstatic --dry-run --noinput`, explicit Django frontend-contract
tests, `manage.py test core`, `manage.py test accounts`, and the full
`manage.py test` suite.

There is no separate Node frontend toolchain or frontend build CI. The
frontend safety rail in CI is contract coverage for Django-rendered templates,
static CSS/JS references, JSON config blocks, JavaScript globals, viewer hooks,
workflow responses, and export hooks. It is not browser E2E coverage and does
not run an npm build.

Coverage reporting remains deferred because `coverage.py` is not currently a
project dependency. Add coverage as a test/development dependency before
introducing an informational coverage step in Backend CI. Lint/format gates,
typechecking, browser E2E, Docker build, and deployment validation are also
deferred until the baseline CI stays stable.

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
