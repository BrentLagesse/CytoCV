# Data Flow And Artifacts

## Purpose

This document tracks how files and persisted state move through the system from upload to retention or deletion.

## Upload Intake

Input enters through the `experiment` view as a browser-uploaded `.dv` file.

Primary persisted outputs at request-time intake:

- one `UploadedImage` row
- one source DV file under the run UUID namespace

Upload preparation then runs in the background worker through `UploadPreparationJob`.
Worker-generated upload-prep outputs are:

- one `channel_config.json`
- preview PNG assets
- `scale_info` metadata saved on `UploadedImage`

The worker deletes invalid newly uploaded files, skips invalid restored files, and preserves safe user-facing validation errors on the job.

## Run Media Namespaces

Artifact storage uses these major path helpers:

- run root: `MEDIA_ROOT/<uuid>/`
- preview directory: `MEDIA_ROOT/<uuid>/preview/`
- preprocess directory: `MEDIA_ROOT/<uuid>/pre_process/`
- output directory: `MEDIA_ROOT/<uuid>/output/`
- segmented directory: `MEDIA_ROOT/<uuid>/segmented/`
- user namespace: `MEDIA_ROOT/user_<uuid>/`

## Preprocess And Inference Artifacts

Generated transient or regenerable artifacts may include:

- preprocess images
- inference logs
- `mask.tif`

  Written from the postprocessed Mask R-CNN output; enclosed interior holes are filled so later DIC outlines and fluorescence contour clipping operate on solid cell regions.

- generated temporary image assets
- CSV helper artifacts such as `compressed_masks.csv`

These can be deleted after successful segmentation or when a failed run is cleaned up.

Execution ownership:

- in `sync` mode, preprocess and inference are still request-owned
- in `worker` mode, the full batch is owned by an `AnalysisJob` and executed by the background worker
- upload validation, metadata extraction, channel config writes, and preview generation are always owned by `UploadPreparationJob` and executed by the same background worker command

## Segmentation Artifacts

Persistent segmentation-stage outputs include:

- full-frame outlined PNGs in `output/`
- segmented cell masks and crops in `segmented/`
- `segmented/overlay-render-config.json`
- `segmented/overlay-cache-v1/` exact fluorescence overlay PNG cache
- optional legacy fluorescence debug overlays
- `SegmentedImage` row
- `CellStatistics` rows

Performance note:

- live analysis artifacts use a fast PNG save profile to reduce request/worker CPU cost
- the old second-pass PNG optimization step is no longer part of the live analysis path
- the display/dashboard fluorescence contour view is now driven by exact server replay through `get_stats()`, not by eagerly written debug PNGs
- debug overlays are disabled by default and should remain off in production unless raster debug exports are explicitly needed
- in `worker` mode, the overlay cache is prewarmed during analysis completion so Gunicorn does not absorb contour replay cost on first view

## Saved Versus Transient Retention

Retention state is implemented through a combination of:

- `SegmentedImage.user`
- the current authenticated user
- guest ownership for transient runs
- session-held `transient_experiment_uuids`

Saved runs count against retained storage quota. Transient runs remain viewable during the active session but are candidates for cleanup.

## Cleanup Paths

Artifact cleanup helpers include:

- preview deletion
- transient processing cleanup
- processing-result cleanup
- failed-processing cleanup
- full uploaded-run deletion
- stale transient run sweeping

Cleanup is designed to preserve the source upload and previews when only partial processing failed, and remove regenerable preprocessing artifacts after successful segmentation. The worker maintenance pass protects UUIDs that are still referenced by active upload-preparation or analysis jobs.

## Storage Accounting

Quota projections and enforcement use:

- total retained storage on `CustomUser`
- recalculated used and available storage
- estimated bytes for candidate saved runs
- average saved run size for projection

## Related Documents

- [`request-flows.md`](request-flows.md)
- [`../ops/backup-retention-and-storage.md`](../ops/backup-retention-and-storage.md)
- [`../reference/file-format-and-artifact-spec.md`](../reference/file-format-and-artifact-spec.md)
