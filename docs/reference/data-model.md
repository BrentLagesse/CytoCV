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

## `core.UploadPreparationJob`

Purpose:

- represent background upload validation and preview-preparation work
- preserve safe user-facing upload-preparation errors

Important fields:

- `job_uuid`
- `user`
- `new_run_uuids`
- `restored_run_uuids`
- `valid_run_uuids`
- `config_snapshot`
- `error_lines`
- `status`
- `current_phase`
- `cancellation_requested`
- `failure_summary`
- `created_at`
- `started_at`
- `finished_at`

## `core.AnalysisJob`

Purpose:

- represent one background analysis batch after preprocess review
- persist worker progress and terminal state for polling

Important fields:

- `job_uuid`
- `batch_key`
- `user`
- `run_uuids`
- `status`
- `current_phase`
- `config_snapshot`
- `cancellation_requested`
- `failure_summary`
- `created_at`
- `started_at`
- `finished_at`

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
- `cell_inclusion_mode`

`cell_inclusion_mode` stores the resolved analysis-time retention mode for the
run. Current values are `cell_pairs_only`, `single_cells_only`, and
`single_cells_and_cell_pairs`; the default is `cell_pairs_only`.

## `core.CellStatistics`

Purpose:

- one row per segmented cell containing computed measurements and contextual metadata

Important direct fields include:

- `puncta_distance`
- `puncta_line_intensity`
- `nucleus_intensity_sum`
- `cell_pair_intensity_sum`
- `cytoplasmic_intensity`
- contour sizes
- Cell Type in `cell_type`
- red, green, and mixed Total/Max/Average intensity fields
- legacy Blue-derived fields when corresponding legacy plugins are selected
- DIC-derived mother/daughter parentage in `properties.cell_parentage`
- CEN dot classification fields when `CENDot` is selected
- `properties`

`properties` carries dynamic run context such as:

- nuclear or cell-pair mode
- cell inclusion mode and cell type context
- cell parentage status, mode, method, lobe areas, and label positions
- scale source and effective scale
- line width and distance threshold context
- final Puncta Source contour count metadata used by Display/Dashboard row filters
- contour center coordinate metadata:
  - `contour_center_schema_version`
  - `contour_center_origin`, currently `main_image_bottom_left`
  - `contour_center_method`, currently `filled_mask_geometric_centroid`
  - crop offset and main-image shape values used for the coordinate transform
- per-contour full-image center coordinates such as:
  - `blue_contour_center_x_px` and `blue_contour_center_y_px`
  - `red_contour_1_center_x_px` and `red_contour_1_center_y_px`
  - `green_contour_1_center_x_px` and `green_contour_1_center_y_px`

Contour center coordinates remain property-backed because they are derived display/export values tied to dynamic contour slots. No migration is required unless a future workflow needs them as queryable model fields.

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
