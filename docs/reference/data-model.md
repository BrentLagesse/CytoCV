# Data Model

## Purpose

This document summarizes the primary persisted entities used by the current application.

## `accounts.CustomUser`

Purpose:

- authenticated identity
- storage tracking
- workflow and UI preference persistence

Important fields:

- `id`
- `email`
- `first_name`
- `last_name`
- `is_staff`
- `is_active`
- `total_storage`
- `available_storage`
- `used_storage`
- `quota_override_mode`
- `quota_override_bytes`
- `processing_used`
- `config`

`config` stores normalized preference payloads, including workflow defaults.

## `core.UploadedImage`

Purpose:

- represent one uploaded source file and its metadata

Important fields:

- `user`
- `created_at`
- `name`
- `uuid`
- `file_location`
- `scale_info`

## `core.DVLayerTifPreview`

Purpose:

- represent generated preview rows for an uploaded DV file

Important fields:

- `wavelength`
- `uploaded_image_uuid`
- `file_location`

## `core.SegmentedImage`

Purpose:

- represent a completed segmented run and its retained or transient ownership state

Important fields:

- `user`
- `UUID`
- `uploaded_date`
- `file_location`
- `ImagePath`
- `CellPairPrefix`
- `NumCells`

## `core.CellStatistics`

Purpose:

- one row per segmented cell containing computed measurements and contextual metadata

Important direct fields include:

- `distance`
- `line_gfp_intensity`
- `nucleus_intensity_sum`
- `cellular_intensity_sum`
- `cytoplasmic_intensity`
- contour sizes
- red, green, and mixed intensity fields
- legacy DAPI-derived fields when corresponding legacy plugins are selected
- GFP dot classification fields when `GFPDot` is selected
- `properties`

`properties` carries dynamic run context such as:

- nuclear or cellular mode
- scale source and effective scale
- line width and distance threshold context

## Ownership Model

Two models carry user ownership:

- `UploadedImage.user`
- `SegmentedImage.user`

These can temporarily differ, especially when a run is transient:

- the source upload may belong to the authenticated user
- the segmented output may remain guest-owned until explicitly saved or autosaved

## Related Documents

- [`routes-and-endpoints.md`](routes-and-endpoints.md)
- [`file-format-and-artifact-spec.md`](file-format-and-artifact-spec.md)
- [`../developer/data-flow-and-artifacts.md`](../developer/data-flow-and-artifacts.md)
