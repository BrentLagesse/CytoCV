# Workflow Guide

## Purpose

This guide documents the end-to-end user workflow from upload through review and export.

## Prerequisites

- an account or a valid authenticated session
- one or more supported `.dv` files
- a working CytoCV deployment

## Step 1: Upload Files

Use the `Experiment` page to submit one or more `.dv` files. During upload, CytoCV:

- creates a UUID for each run
- stores the source file under the run media namespace
- derives the required channel set from `DIC`, the selected plugins, and any enabled validation overrides
- validates the DV structure according to the selected validation options
- extracts a channel configuration file
- extracts scale metadata when available
- generates preview assets

Validation failures are reported immediately. Invalid files are removed from the active queue.

## Step 2: Choose Analysis Options

The upload step also captures the active analysis configuration. This includes:

- selected statistics plugins
- mCherry line width
- GFP distance threshold
- GFP threshold
- nuclear or cellular mode selection
- optional GFP contour filtering
- scale behavior, including metadata preference and manual microns-per-pixel fallback

These selections are stored in session state and reused in later steps.

At the default modern settings, the run requires `DIC`, `mCherry`, and `GFP`. `DAPI` becomes required only when a legacy plugin or all-wavelength enforcement is active.

## Step 3: Review Preprocess Sidebar

The preprocess view shows:

- the active file list
- detected channel order per file
- preview images for the current file
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
- computes the selected statistics plugins
- writes per-cell debug images when the active plugins need them
- persists `SegmentedImage` and `CellStatistics` rows

If autosave is enabled and the account has remaining storage, finished runs are retained under the user account. Otherwise, finished runs remain transient and can still be viewed in the current session.

## Step 6: Review Results In Display

The display view provides:

- one main outlined image per file
- per-cell image panels in channel order
- statistics for each cell
- export support through `django-tables2`
- save, unsave, and selection synchronization actions

Main display frames can be switched by channel, and channel order is based on the stored `channel_config.json`.

## Step 7: Save Or Export

From display or dashboard, users can:

- export table data
- save transient runs to their account if quota allows
- unsave retained runs back to transient status
- bulk-delete saved runs from the dashboard

## Expected Outputs

- saved or transient segmentation results
- per-cell statistics in the database
- exportable tabular summaries
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
- [`output-guide.md`](output-guide.md)
- [`../developer/request-flows.md`](../developer/request-flows.md)
