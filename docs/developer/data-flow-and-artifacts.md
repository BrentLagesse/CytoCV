# Data Flow And Artifacts

## Purpose

This document tracks how files and persisted state move through the system from upload to retention or deletion.

## Upload Intake

Input enters through the `experiment` view as a browser-uploaded `.dv` file.

Primary persisted outputs at intake:

- one `UploadedImage` row
- one source DV file under the run UUID namespace
- one `channel_config.json`
- preview PNG assets
- `scale_info` metadata saved on `UploadedImage`

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
- generated temporary image assets
- CSV helper artifacts such as `compressed_masks.csv`

These can be deleted after successful segmentation or when a failed run is cleaned up.

## Segmentation Artifacts

Persistent segmentation-stage outputs include:

- full-frame outlined PNGs in `output/`
- segmented cell masks and crops in `segmented/`
- fluorescence debug overlays
- `SegmentedImage` row
- `CellStatistics` rows

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

Cleanup is designed to preserve the source upload and previews when only partial processing failed, and remove regenerable preprocessing artifacts after successful segmentation.

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
