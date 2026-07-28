# Workflow Guide

## Purpose

This guide documents the end-to-end user workflow from upload through review and export.

## Prerequisites

- a signed-in account
- one or more supported `.dv`, `.tif`, or `.tiff` files
- a working CytoCV deployment

## Step 1: Upload Files

Use the `Experiment` page to submit one or more supported microscopy stack files. During upload, CytoCV:

- assigns a run UUID to each uploaded file
- stores the source `.dv` file in protected run storage
- sends large selections as multiple bounded upload requests
- queues background upload preparation after the bytes are saved
- derives the required channel set from `DIC`, the selected plugins, and any enabled validation overrides
- validates the DV structure according to the selected validation options
- extracts channel-order information and scale metadata when available
- generates preview images for preprocess review

Validation failures are reported after the background preparation job finishes. Invalid newly uploaded files are removed from the active queue, while valid files continue to preprocess review.

## Step 2: Choose Analysis Options

The upload step also captures the active analysis configuration. This includes:

- selected statistics plugins
- Cell Inclusion Mode
- puncta source mode and Puncta line width
- CEN dot distance threshold and proximity radius
- Biorientation minimum and maximum Red-distance settings
- Biorientation collinearity threshold
- nuclear or cell-pair mode selection
- optional Green dot splitting and split mode
- optional Green contour filtering
- optional alternate Red detection
- scale behavior, including metadata preference and manual microns-per-pixel fallback

These selections are stored with the current workflow state and reused in later steps. Signed-in users can also save them as workflow defaults for future runs.

The current workflow defaults select `PunctaDistance`, `CENDot`, `Biorientation`, `GreenRedIntensity`, and `NuclearCellPairIntensity`. That default set requires `DIC`, `Red`, and `Green`. Mother/daughter parentage is computed automatically from DIC geometry and consumed by `CENDot`. `Blue` becomes required only when a legacy plugin or all-wavelength enforcement is active.

Cell Inclusion Mode is resolved at analysis time. The default is Cell pairs
only. Single cells only and Single cells and cell pairs can be selected when the
review task needs single-cell rows. Display and Dashboard filters cannot recover
cells that were excluded by this analysis-time setting.

## Step 3: Review Preprocess Sidebar

The preprocess view shows:

- the active file list
- detected channel order per file
- preview images for the current file, typically covering the first available layers up to four previews
- per-file scale state and optional manual override controls

Use this stage to confirm that each file has the expected `DIC` mapping and any additional channels needed by the selected workflow.

## Step 4: Run Preprocessing And Inference

When preprocessing starts, CytoCV:

- converts the structural input into the model-ready representation
- writes progress updates
- supports cancellation through the progress API
- runs Mask R-CNN inference
- writes a `mask.tif` output for each run

If processing is cancelled, the current run set is deleted from the queue. If the filesystem is full, partial processing artifacts are cleaned up and the user is redirected back to preprocess.

## Step 5: Run Segmentation And Statistics

During segmentation, CytoCV:

- opens the saved mask output
- builds outlined full-frame result images
- writes segmented cell crops
- caches per-cell channel imagery when possible
- retains only the cell candidate types allowed by Cell Inclusion Mode
- computes the selected statistics plugins
- writes per-cell debug images when the active plugins need them
- stores run-level and per-cell results for later review

If autosave is enabled and the account has remaining storage, finished runs are retained under the user account. Otherwise, finished runs remain transient and can still be viewed in the current session.

## Step 6: Review Results In Display

The display view provides:

- one main outlined image per file
- per-cell image panels in channel order
- a compact Overlays menu for independently showing Cell boundary, Red
  contours, Green contours, Blue contour, and analysis annotations when those
  layers are available
- software-generated measurements for each cell
- a Cell Type Filter for retained single-cell and cell-pair rows
- a Puncta Source / Red or Green Source Contour Count row filter when source contour count data is available
- CSV and XLSX statistics export for the current table, with optional metric selection
- save, unsave, and selection synchronization actions

Main display frames can be switched by channel, and channel order is based on the stored `channel_config.json`.

The Overlays menu starts at `All` on each page load. `Select all` reproduces
the previous outlined presentation, while `Clear` shows no-outline cell crops.
Selections remain active while moving between cells and files on the same
page. A family can stay selected when a file lacks its source channel; it is
temporarily unavailable for that file and becomes active again on a compatible
file. Older saved runs without current replay metadata remain viewable with
aggregate `All` and `None` behavior.

Changing one family updates only the image columns where that family is drawn.
Other columns keep the same crop and presentation. Rectangular cell crops and
their annotations retain the same aspect ratio instead of stretching to fill
the square viewer card.

Changing overlay visibility affects only the pictures shown in Display or
Dashboard. It does not change segmentation, measurements, saved statistics,
or exported values.

## Step 7: Save Or Export

From display or dashboard, users can:

- export single-file or selected-file statistics as CSV or XLSX
- choose all metrics or a selected subset of metrics for statistics downloads
- apply effective row filters before export while keeping selected metrics as column selection only
- save transient runs to their account if quota allows
- unsave retained runs back to transient status
- bulk-delete saved runs from the dashboard

## Expected Outputs

- saved or transient segmentation results
- per-cell software-generated measurements saved with the run
- exportable tabular summaries with filenames that indicate metric scope, file count, and timestamp
- dashboard-visible history for retained runs

## Common Errors

- unauthorized access to a display UUID

  The run is not owned by the current user or is no longer transiently available in the session.

- storage full while saving

  The selected set exceeds remaining quota.

- no segmented cells produced

  The model or downstream segmentation did not produce usable cell instances.

## Related Documents

- [`account-and-dashboard.md`](account-and-dashboard.md)
- [`analysis-options.md`](analysis-options.md)
- [`output-guide.md`](output-guide.md)
