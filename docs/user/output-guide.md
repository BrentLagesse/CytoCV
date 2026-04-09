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

For each valid upload, CytoCV generates preview images under the run preview directory. The exact count depends on the detected layer structure and validation settings. These previews are browser-friendly PNG representations of the raw DV layers and are used in the preprocess page.

## Full-Frame Result Images

The segmentation stage writes outlined frames under the run `output` directory. These images represent full-run output frames for the mapped channel indices and are used as the main display image.

## Segmented Cell Assets

The segmentation stage also writes:

- `cell_<n>.png` binary cell masks
- outlined per-cell channel crops
- no-outline per-cell channel crops
- an exact fluorescence overlay replay snapshot and cache
- optional raster debug overlays when debug export is enabled

The `DIC` channel generally provides the structural crop view. Fluorescence contour-rich views for `mCherry`, `GFP`, and `DAPI` are now replayed from the exact server render path used during analysis, so those contour views remain available even when optional debug PNG export is disabled.

## Database Outputs

Each successful run can create:

- one `SegmentedImage` row
- multiple `CellStatistics` rows, one per segmented cell

Important `CellStatistics` fields include:

- `distance`
- `line_gfp_intensity`
- raw red/green contour intensity sums such as `red_intensity_1`, `green_intensity_1`, `red_in_green_intensity_1`, and `green_in_green_intensity_1`
- the secondary compatibility ratio fields `green_red_intensity_1` through `green_red_intensity_3`
- `nucleus_intensity_sum`
- `cellular_intensity_sum`
- `cytoplasmic_intensity`
- legacy DAPI-derived and red-in-blue fields
- GFP dot classification fields

For the red/green contour metrics, CytoCV stores integrated intensity sums inside the contour mask. These raw integrated sums are the primary output. They are not mean intensities, and they are not ratios.

The only ratio fields in this area are the explicitly named green/red compatibility fields:

- `green_red_intensity_1`
- `green_red_intensity_2`
- `green_red_intensity_3`

These ratio fields are derived values and should be interpreted as secondary compatibility output, not as replacements for the raw integrated sums.

`CellStatistics.properties` also stores contextual information such as:

- nuclear or cellular mode
- scale source and effective scale
- pixel-equivalent threshold settings

## Exports

CytoCV supports table exports through `django-tables2`. Export behavior is available in:

- the display view for the first UUID with statistics
- the dashboard for a selected saved file

The on-page statistics tables and the CSV/XLSX exports include both:

- the raw integrated contour intensity sums as the primary table/export values
- the three green/red ratio compatibility columns as explicitly labeled derived values

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
