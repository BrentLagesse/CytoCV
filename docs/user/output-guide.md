# Output Guide

## Purpose

This guide explains what CytoCV writes for each run and how to interpret the major outputs.

## Prerequisites

- a completed run in display or dashboard

## Output Categories

CytoCV produces outputs in four broad categories:

- upload preview assets
- segmentation and display assets
- database records
- exported tables

## Preview Assets

For each valid upload, CytoCV generates browser-friendly preview PNG files under the run preview directory. The current implementation writes one preview per detected layer up to the first four layers. These previews are used in the preprocess page.

## Full-Frame Result Images

The segmentation stage writes outlined frames under the run `output` directory. These images represent full-run output frames for the mapped channel indices and are used as the main display image.

## Segmented Cell Assets

The segmentation stage also writes:

- `cell_<n>.png` binary cell masks
- outlined per-cell channel crops
- no-outline per-cell channel crops
- an overlay render snapshot and cached fluorescence overlay images
- optional raster debug overlays when debug export is enabled

The `DIC` channel generally provides the structural crop view. Fluorescence contour-rich views for `Red`, `Green`, and `Blue` are now replayed from the exact server render path used during analysis, so those contour views remain available even when optional debug PNG export is disabled.

## Database Outputs

Each successful run can create one stored run record and multiple per-cell measurement records.

Important stored measurement families include:

- Cell Type, reported as Single Cell, Cell Pair, or Unknown near Cell ID
- puncta distance and puncta-line intensity
- raw red/green contour intensity sums, including cross-channel contour measurements
- full-main-image contour center coordinates for the same canonical contour slots
- nuclear, cell-pair, and cytoplasmic intensity summaries
- legacy Blue-derived outputs when legacy plugins are enabled
- CEN dot location and classification outputs
- Biorientation count fields such as `colinear_dots` and `off_axis_dots`

For the red/green contour metrics, CytoCV reports total, maximum, and average intensity inside the same contour mask. Total Intensity is the integrated raw sum previously reported by the red/green contour workflow. Max Intensity is the maximum raw pixel value inside the same contour mask. Average Intensity is the mean raw pixel value inside the same contour mask. These values use the same raw measurement image and fallback chain as the workflow; they are not measured from normalized display images, preview images, threshold masks, or cached thumbnails.

These values are software-generated measurements. They support review and downstream analysis, but they should still be interpreted alongside the source images, overlays, and experimental context.

For the puncta-line measurement, the persisted fields are `puncta_distance` and `puncta_line_intensity`, and the public labels are mode-driven:

- `red_puncta`: `Distance between Red Puncta` and `Green Intensity over Red Line`
- `green_puncta`: `Distance between Green Puncta` and `Red Intensity over Green Line`

For the modern red/green statistics, contour slots `1/2/3` are canonical ranked slots. Each raw detected contour is filled, clipped to the segmented cell mask, and then ranked by clipped area, then center `x`, then center `y`. This means:

- `red_contour_1_size`, `red_in_red_total_intensity_1`, and `green_in_red_total_intensity_1` all refer to the same clipped Red contour slot
- `green_contour_1_size`, `red_in_green_total_intensity_1`, and `green_in_green_total_intensity_1` all refer to the same clipped Green contour slot
- `red_contour_1_center_xy` and `green_contour_1_center_xy` report the center of those same slot `1` masks
- in `red_nucleus` mode, `nucleus_intensity_sum` uses Red slot `1`
- in `green_nucleus` mode, `nucleus_intensity_sum` uses Green slot `1`

Contour center coordinates are measured relative to the full main image, not the cropped cell-pair image. They use a bottom-left origin: the bottom-left pixel center is `(0, 0)`, `x` increases to the right, and `y` increases upward. The center is the filled-contour geometric centroid after clipping to the segmented cell mask, so it is shape-based rather than brightness-weighted.

As a result, when one contour defines the selected nucleus family, the matching nuclear measurement and cross-channel contour measurement can match exactly because they come from the same canonical contour slot:

- `red_nucleus`: `Green nuclear intensity` matches `Green In Red Total Intensity 1`
- `green_nucleus`: `Red nuclear intensity` matches `Red In Green Total Intensity 1`

The viewer, statistics table, and CSV/XLSX exports show three derived `Measurement/Contour Ratio` values. Their meaning follows the selected nucleus/cell-pair mode:

- `red_nucleus`: `Green in Red / Red in Red`
- `green_nucleus`: `Red in Green / Green in Green`

These ratios are derived values and should be interpreted as secondary output, not as replacements for the raw total, maximum, and average intensity summaries. Older internal field names may not match the current public table labels exactly.

Run metadata also stores contextual information such as:

- nuclear or cell-pair mode
- scale source and effective scale
- pixel-equivalent threshold settings

## Exports

CytoCV supports CSV and XLSX table exports. Export behavior is available in:

- the display view for the current statistics table
- the dashboard for a selected saved file
- combined statistics downloads for selected files in Display or Dashboard

Exports apply row filters before writing rows. Deleted cells are excluded first.
The Cell Type Filter is a row filter over already-analyzed rows; it can show all
retained cell types, single-cell rows, or cell-pair rows when both known types
exist. If a result contains only one cell type, only unknown rows, or no rows,
the effective Cell Type Filter is all rows. The Puncta Source / Source Contour
Count filter is also a row filter. It uses final canonical source contour slots
clipped to the retained row mask and composes with the Cell Type Filter.

Selected metrics are column selection only. Selecting or clearing Total, Max, or
Average intensity fields changes export columns, not which rows are exported.
Display exports, Dashboard exports, and combined multi-file exports use the
same distinction between row filters and selected metric columns.

The on-page statistics tables and the CSV/XLSX exports include both:

- the raw total, maximum, and average contour intensity summaries as primary table/export values
- the full-main-image contour center coordinate columns after the matching Red or Green size group
- the three mode-driven `Measurement/Contour Ratio` columns as explicitly labeled derived values
- canonical contour slot numbering, so size, center-coordinate, intensity, line-distance, and nucleus-derived modern red/green outputs stay aligned

The four Red/Green Contour Intensity combinations are exported in this order:
Red In Red, Green In Red, Red In Green, and Green In Green. Within each
combination, each slot is ordered Total Intensity, Max Intensity, then Average
Intensity for slots 1 through 3.

Spatial units can be changed from the page-level Spatial Unit controls or directly inside the Download Statistics modal. The selected unit applies to spatial measurements in CSV and XLSX exports, including distances, contour sizes, and contour center coordinates. When the statistics unit toggle is set to pixels, coordinate columns show full-image pixel coordinates. When the unit is set to micrometers, `x` and `y` are converted with the file's per-axis scale metadata or manual fallback scale.

Intensity values, ratios, classifications, file names, and cell IDs are not spatial-unit-dependent. Combined exports apply the selected unit to every included file using each file's existing scale metadata or fallback behavior.

Statistics downloads can include all metrics or a selected subset. Selected
CSV/XLSX exports can include Total, Max, and Average intensity independently;
they are not bundled into one inseparable export group. Export filenames follow:

`cytocv_<all-or-selected>_cell-metrics_<number>files_<YYYY-MM-DD_HHMM>.<extension>`

The `all` or `selected` token describes whether all cell metrics or only selected metrics were exported. The file count separately reflects how many files were included. In combined exports, `File Name` appears only on the first row for each file group, with later rows for that same file left blank until the next file begins.

## Expected Outputs

After a fully successful run you should expect:

- one run UUID namespace under media storage
- one stored channel configuration file
- one mask file
- one or more outlined output frames
- segmented cell imagery
- exact fluorescence contour views in display and dashboard
- a populated statistics table when cells were found

## Common Errors

- no cells warning

  The run finished but segmentation did not produce cell instances.

- missing preview assets

  The dashboard may still show table data even when preview imagery has been cleaned up.

- missing main frame for a chosen channel

  CytoCV falls back to another available output frame when possible.

## Related Documents

- [`workflow-guide.md`](workflow-guide.md)
- [`../reference/data-model.md`](../reference/data-model.md)
- [`../reference/file-format-and-artifact-spec.md`](../reference/file-format-and-artifact-spec.md)
