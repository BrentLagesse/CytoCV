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
- plugin-dependent debug overlays

The `DIC` channel generally provides the structural crop view. `mCherry` and `GFP` debug overlays are common in the modern workflow. `DAPI` debug overlays are associated with legacy DAPI-centered measurements or DAPI contour-dependent paths.

## Database Outputs

Each successful run can create:

- one `SegmentedImage` row
- multiple `CellStatistics` rows, one per segmented cell

Important `CellStatistics` fields include:

- `distance`
- `line_gfp_intensity`
- `nucleus_intensity_sum`
- `cellular_intensity_sum`
- `cytoplasmic_intensity`
- legacy DAPI-derived and red-in-blue fields
- GFP dot classification fields

`CellStatistics.properties` also stores contextual information such as:

- nuclear or cellular mode
- scale source and effective scale
- pixel-equivalent threshold settings

## Exports

CytoCV supports table exports through `django-tables2`. Export behavior is available in:

- the display view for the first UUID with statistics
- the dashboard for a selected saved file

## Expected Outputs

After a fully successful run you should expect:

- one run UUID namespace under media storage
- one stored channel configuration file
- one mask file
- one or more outlined output frames
- segmented cell imagery
- plugin-dependent debug overlays
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
