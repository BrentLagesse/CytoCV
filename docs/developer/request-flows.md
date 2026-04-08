# Request Flows

## Purpose

This document describes the major request and workflow flows implemented by the current views.

## Upload Flow

Primary handler: `core.views.experiment.experiment`

Sequence:

1. ensure a session key exists
2. load normalized user preferences
3. parse selected plugins and measurement controls
4. derive validation requirements from selected plugins and optional advanced settings
5. create an `UploadedImage` per valid new file
6. validate the DV file
7. resolve scale metadata and save `scale_info`
8. write `channel_config.json`
9. generate preview assets
10. redirect to preprocess for the surviving UUID set

Failure modes:

- invalid DV files are removed from the queue
- storage-full errors trigger upload cleanup
- mixed valid and invalid uploads still preserve valid files

## Preprocess And Inference Flow

Primary handler: `core.views.pre_process.pre_process`

GET responsibilities:

- load queued UUIDs
- build sidebar state
- ensure preview assets exist
- expose per-file scale state

POST responsibilities:

- validate per-file scale override payloads
- save selected scale overrides
- normalize persisted measurement values back into session state
- choose execution mode from `CYTOCV_ANALYSIS_EXECUTION_MODE`
- in `sync` mode:
  - run preprocess and inference for each UUID
  - write progress phases
  - honor cancellation requests
  - redirect to segmentation
- in `worker` mode:
  - persist a whitelisted batch config snapshot
  - enqueue one `AnalysisJob`
  - return immediately so the frontend can poll progress

## Segmentation And Statistics Flow

Primary handler: `core.views.segment_image.segment_image`

Sequence:

1. resolve ownership and access to each queued upload
2. open the DV stack and the generated mask
3. construct full-frame outlined result images
4. create segmented cell crops and no-outline variants
5. cache channel imagery when possible
6. create or update `SegmentedImage`
7. create per-cell `CellStatistics`
8. execute selected plugins
9. write `overlay-render-config.json` so fluorescence overlays can be replayed exactly later without request/session state
10. in `worker` mode, prewarm the exact fluorescence overlay cache from the same rendered `get_stats()` images
11. save optional legacy debug overlays only when explicitly enabled
12. clean transient preprocess artifacts
13. autosave or mark transient based on account settings and quota
14. redirect to display

Measurement note:

- the red/green contour plugin stores raw masked pixel sums for each contour-channel combination (`red in red`, `green in red`, `red in green`, `green in green`)
- the legacy-compatible `green_red_intensity_*` values remain a derived ratio of `green in red / red in red`
- these masked contour values are integrated sums, not mean intensities

Worker-backed production flow:

- `core.views.pre_process.pre_process` enqueues the full batch
- `core.management.commands.run_analysis_worker` claims the queued `AnalysisJob`
- `core.services.analysis_pipeline.run_analysis_batch` orchestrates preprocess, inference, segmentation, statistics, cleanup, and final status
- `core.services.segmentation_pipeline.run_segmentation_batch` is the shared segmentation/statistics implementation used by the worker

Compatibility note:

- the legacy `/segment/` route remains available for the existing sync flow and manual/local compatibility
- production deployments should prefer `worker` mode so Gunicorn does not block on segmentation/statistics

## Display Flow

Primary handler: `core.views.display.display`

Sequence:

1. normalize UUID list
2. sweep stale artifacts while protecting active UUIDs
3. validate access per UUID
4. read channel config and output frames
5. scan segmented cell imagery
6. load `CellStatistics`
7. emit fluorescence contour-on URLs through the protected exact overlay endpoint
8. render the main display payload and statistics table

Related write actions:

- `save_display_files`
- `unsave_display_files`
- `sync_display_file_selection`
- `main_image_channel`

## Dashboard Flow

Primary handler: `accounts.views.profile.dashboard_view`

Sequence:

1. sweep stale artifacts
2. rebuild saved-run dashboard payload
3. expose storage usage and file-capacity projection
4. support export of table data for a selected saved run

Related write actions:

- `dashboard_bulk_delete_view`
- `dashboard_channel_visibility_view`
- `preferences_view`
- `account_settings_view`

## Authentication Flows

Primary handlers:

- `accounts.views.login.auth_login`
- `accounts.views.signup.signup`

Key behaviors:

- email-based auth is primary
- allauth provider sign-in is included
- recovery and signup can be gated by reCAPTCHA
- verification and recovery state is held in session data

## Related Documents

- [`architecture-overview.md`](architecture-overview.md)
- [`../reference/routes-and-endpoints.md`](../reference/routes-and-endpoints.md)
- [`../diagrams/README.md`](../diagrams/README.md)
