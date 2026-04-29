# Request Flows

## Purpose

This document describes the major request and workflow flows implemented by the current views.

## Upload Flow

Primary handlers:

- `core.views.experiment.experiment`
- `core.views.experiment.upload_file_batch`
- `core.views.experiment.enqueue_upload_preparation`
- `core.views.experiment.upload_preparation_status`

Sequence:

1. ensure a session key exists
2. load normalized user preferences
3. parse selected plugins and measurement controls
4. derive validation requirements from selected plugins and optional advanced settings
5. split selected browser files into safe-size upload batches
6. `POST /api/experiment/uploads/` saves each small `.dv` batch and creates one `UploadedImage` row per file
7. `POST /api/experiment/upload-prep/` enqueues one `UploadPreparationJob` with new and restored run UUIDs plus the whitelisted config snapshot
8. the background worker validates each DV file one at a time
9. the worker resolves scale metadata, writes `scale_info`, writes `channel_config.json`, and generates preview assets
10. the browser polls `GET /api/experiment/upload-prep/<job_uuid>/`
11. on success, the browser redirects to preprocess for the worker-approved UUID set

Failure modes:

- invalid DV files are removed from the queue
- invalid restored files are skipped but not deleted
- storage-full errors trigger upload cleanup
- mixed valid and invalid uploads still preserve valid files
- if the worker is not running, upload preparation stays queued and the browser keeps polling

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
  - run the full preprocess, inference, segmentation, and statistics batch in the preprocess POST
  - write progress phases through the shared analysis pipeline
  - honor cancellation requests
  - reconcile transient session access from final segmented-image ownership before redirecting
  - return directly to display when the batch completes
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
- modern Red and Green contour families are normalized into canonical ranked slots before plugin execution
- each canonical slot is built by filling the raw contour, clipping it to the segmented cell mask, extracting the clipped contour geometry, and ranking by clipped area, then center `x`, then center `y`
- slot numbers are shared across size fields, raw intensity fields, Red-line selection, CEN-dot selection, and modern nucleus measurements
- `NuclearCellPairIntensity` now uses canonical slot `1` from the selected contour family (`red_nucleus` => Red slot `1`, `green_nucleus` => Green slot `1`)
- the legacy storage fields `green_red_intensity_*` now persist the public toggle-driven measurement/contour ratio
- `red_nucleus` mode stores `green in red / red in red`
- `green_nucleus` mode stores `red in green / green in green`
- these masked contour values are integrated sums, not mean intensities

Worker-backed production flow:

- `core.views.experiment.enqueue_upload_preparation` enqueues upload validation and preview generation as `UploadPreparationJob`
- `core.views.pre_process.pre_process` enqueues the full analysis batch as `AnalysisJob`
- `core.management.commands.run_analysis_worker` claims the oldest queued upload-preparation or analysis job across both queues
- `core.services.upload_preparation.run_upload_preparation_job` validates files, extracts metadata, writes channel config, generates previews, and cleans invalid new uploads
- `core.services.analysis_pipeline.run_analysis_batch` orchestrates preprocess, inference, segmentation, statistics, cleanup, and final status
- `core.services.segmentation_pipeline.run_segmentation_batch` is the shared segmentation/statistics implementation used by the worker

Compatibility note:

- the legacy `/segment/` route remains available for the existing sync flow and manual/local compatibility
- preprocess AJAX no longer uses `/segment/` as its normal success path in `sync` mode
- production deployments need the worker process running so Gunicorn does not block on upload preparation, segmentation, or statistics

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
- native signup and password recovery send numeric verification-code emails
- provider email verification sends signed allauth confirmation links through the CytoCV branded multipart email builder
- `/signin/oauth/verification-status/` reports only the current session authentication state so the check-email page can redirect after the same browser session resumes the staged login and becomes authenticated

All account verification codes and provider confirmation links use the shared expiry policy from `CYTOCV_AUTH_VERIFICATION_EXPIRY_MINUTES`, which defaults to 5 minutes.

The OAuth confirmation link is generated by allauth from the active request, not from a hard-coded domain. Local flows therefore produce local confirmation links, and production flows depend on the deployed host/proxy settings being correct.

## Related Documents

- [`architecture-overview.md`](architecture-overview.md)
- [`../reference/routes-and-endpoints.md`](../reference/routes-and-endpoints.md)
- [`../diagrams/README.md`](../diagrams/README.md)
