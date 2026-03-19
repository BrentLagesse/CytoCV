# Routes And Endpoints

## Purpose

This document lists the current public routes and route-level behavior defined in `cytocv/cytocv/urls.py`.

## Public Or Auth Entry Routes

### `GET /`

- Name: `home`
- Auth: public
- Purpose: landing page

### `GET|POST /signin/`

- Name: `signin`
- Auth: public
- Purpose: email sign-in and recovery flow handling

### `/signin/oauth/`

- Name: delegated to `allauth.urls`
- Auth: provider dependent
- Purpose: provider login and account integration

### `POST|GET /logout/`

- Name: `logout`
- Auth: authenticated session
- Purpose: sign out

### `GET|POST /signup/`

- Name: `signup`
- Auth: public
- Purpose: signup and verification flow

## Authenticated Account Routes

### `GET|POST /account-settings/`

- Name: `account_settings`
- Auth: required
- Purpose: account display and deletion confirmation

### `GET /dashboard/`

- Name: `dashboard`
- Auth: required
- Purpose: saved-run dashboard and optional export

### `POST /dashboard/files/delete/`

- Name: `dashboard_bulk_delete`
- Auth: required
- Purpose: delete selected saved files
- Input: JSON payload of UUIDs

### `POST /dashboard/preferences/channels/`

- Name: `dashboard_channel_visibility`
- Auth: required
- Purpose: persist dashboard visibility preferences

### `GET|POST /workflow-defaults/`

- Name: `workflow_defaults`
- Auth: required
- Purpose: save plugin defaults, advanced settings, and behavior preferences

## Experiment Workflow Routes

### `GET|POST /experiment/`

- Name: `experiment`
- Auth: required in route configuration
- Purpose: upload queue setup, validation, preview generation

### `GET|POST /experiment/<uuids>/pre-process/`

- Name: `pre_process`
- Auth: required
- Purpose: preview review, scale overrides, preprocess and inference kickoff

### `GET /experiment/<uuids>/convert/`

- Name: `experiment_convert`
- Auth: required
- Purpose: conversion step endpoint

### `GET /experiment/<uuids>/segment/`

- Name: `experiment_segment`
- Auth: required
- Purpose: segmentation, artifact generation, and statistics persistence

### `GET|POST /experiment/<uuids>/display/`

- Name: `display`
- Auth: required
- Purpose: result review and export

### `POST /experiment/display/files/save/`

- Name: `display_save_files`
- Auth: required
- Purpose: convert transient runs to saved runs

### `POST /experiment/display/files/unsave/`

- Name: `display_unsave_files`
- Auth: required
- Purpose: convert saved runs back to transient

### `POST /experiment/display/files/sync-selection/`

- Name: `display_sync_file_selection`
- Auth: required
- Purpose: apply save state to all visible display files

### `GET /experiment/<uuid>/main-channel/`

- Name: `main_image_channel`
- Auth: required
- Purpose: fetch the main display image URL for a chosen channel

## API-Style Utility Routes

### `POST /api/update-channel-order/<uuid>/`

- Name: `update_channel_order`
- Auth: required
- Purpose: overwrite `channel_config.json` for the run

### `GET /api/progress/<uuids>/`

- Name: `analysis_progress`
- Auth: required
- Purpose: return current progress phase

### `POST /api/progress/<key>/set/`

- Name: `set_progress`
- Auth: required
- Purpose: explicitly write a progress phase

### `POST /api/progress/<uuids>/cancel/`

- Name: `cancel_progress`
- Auth: required
- Purpose: cancel or finalize a cancellable run

### `GET /media/<relative_path>`

- Name: `protected_media`
- Auth: required
- Purpose: serve protected media assets after ownership checks

## Notes

- All experiment, dashboard, and media routes are login-protected in the URL map.
- Several authenticated views still distinguish between retained user ownership and guest-owned transient outputs.

## Related Documents

- [`data-model.md`](data-model.md)
- [`file-format-and-artifact-spec.md`](file-format-and-artifact-spec.md)
- [`../developer/request-flows.md`](../developer/request-flows.md)
