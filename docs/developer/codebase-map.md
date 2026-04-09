# Codebase Map

## Purpose

This document provides a practical map of the current repository structure.

## Top-Level Repository Structure

- `cytocv/`
  Django project root containing the apps, templates, media, cache, and `manage.py`
- `docs/`
  project documentation and research deliverables
- `Test_Files/`
  local testing input material
- `requirements.txt`
  Python dependency lock surface for the application environment
- `Dockerfile` and `compose.yml`
  containerization and service bootstrap material

## Django Project Package

Inside `cytocv/`:

- `cytocv/cytocv/`
  Django settings, URL configuration, and WSGI entrypoint
- `cytocv/accounts/`
  auth model, preferences, signup/login/profile views, security helpers
- `cytocv/core/`
  scientific workflow, models, services, views, analysis logic, and tests
- `cytocv/templates/`
  shared templates for the UI
- `cytocv/media/`
  runtime media storage root
- `cytocv/cache/`
  file-based Django cache backend

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
- `core/services/artifact_storage.py`

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
- tables
- stats validation
- scale initialization
- upload length and scale behavior

## Related Documents

- [`architecture-overview.md`](architecture-overview.md)
- [`testing-guide.md`](testing-guide.md)
- [`../reference/routes-and-endpoints.md`](../reference/routes-and-endpoints.md)

