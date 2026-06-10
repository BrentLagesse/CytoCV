# Codebase Map

## Purpose

This document provides a practical map of the current repository structure.

## Top-Level Repository Structure

- `cytocv/`

  Django project root containing the apps, templates, media, cache, and `manage.py`

- `docs/`

  Project documentation and research deliverables

- `Test_Files/`

  Local testing input material

- `requirements.txt`

  Python dependency lock surface for the application environment

- `Dockerfile` and `compose.yml`

  Containerization and service bootstrap material

## Django Project Package

Inside `cytocv/`:

- `cytocv/cytocv/`

  Django settings, URL configuration, and WSGI entrypoint

- `cytocv/accounts/`

  Auth model, preferences, signup/login/profile views, security helpers

- `cytocv/core/`

  Scientific workflow, models, services, views, analysis logic, and tests

- `cytocv/templates/`

  Shared templates for the UI

- `cytocv/core/static/css/`

  Source CSS organized into global, component, and page-level stylesheets

- `cytocv/core/static/js/`

  Source JavaScript organized into shared controllers/utilities and page controllers. Results-viewer shared behavior lives in `js/shared/results-viewer.js`; dashboard/display page-specific behavior stays in `js/pages/`.

- `cytocv/media/`

  Runtime media storage root

- `cytocv/cache/`

  File-based Django cache backend

## Accounts App

Important areas:

- `accounts/models.py`
- `accounts/preferences.py`
- `accounts/views/login.py`
- `accounts/views/signup.py`
- `accounts/views/profile.py`

## Core App

Important areas:

- `core/models.py`
- `core/views/experiment.py`
- `core/views/pre_process.py`
- `core/views/segment_image.py`
- `core/views/display.py`
- `core/management/commands/run_analysis_worker.py`
- `core/services/artifact_storage.py`
- `core/services/upload_preparation.py`
- `core/services/upload_preparation_jobs.py`
- `core/services/analysis_jobs.py`
- `core/services/analysis_pipeline.py`

## Analysis And Processing Subpackages

- `core/cell_analysis/`
- `core/mrcnn/`
- `core/image_processing/`
- `core/contour_processing/`
- `core/metadata_processing/`

## Tests

Current tests live in `cytocv/core/tests/` and focus on:

- preferences
- artifact storage
- inference
- upload-preparation jobs and staged upload APIs
- async analysis jobs and worker progress
- tables
- stats validation
- scale initialization
- upload length and scale behavior

## Related Documents

- [`architecture-overview.md`](architecture-overview.md)
- [`frontend-architecture.md`](frontend-architecture.md)
- [`testing-guide.md`](testing-guide.md)
- [`../reference/routes-and-endpoints.md`](../reference/routes-and-endpoints.md)
