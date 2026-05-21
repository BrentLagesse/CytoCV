# Troubleshooting

## Purpose

This guide lists common user-visible failures and the expected corrective action.

## Prerequisites

- access to the active CytoCV deployment
- the relevant error text or failing workflow step

## Upload Failures

### Symptom

The upload page reports invalid source image files or rejects files immediately.

### Likely Causes

- the file does not parse as a valid supported `.dv`, `.tif`, or `.tiff` stack
- the file does not satisfy enforced layer-count requirements
- required wavelengths are missing
- a selected plugin requires a channel that is not present
- separate single-channel TIFFs were uploaded with the expectation that CytoCV would combine them into one multi-channel file

### Corrective Action

- verify the file is a supported `.dv`, `.tif`, or `.tiff` file
- verify the current plugin selection
- disable unneeded validation controls
- confirm that `DIC` is present
- confirm that any plugin-required channels are present
- if all-wavelength enforcement is enabled, confirm that all four logical channel roles are present
- for TIFF workflows, use a TIFF stack that contains the needed channels; CytoCV does not assemble separate wavelength TIFF files into one run by filename
- if TIFF channel order looks wrong, check for ImageJ labels such as `w625`, `w525`, `w435`, and `R3D_REF`, or adjust the channel mapping before analysis

### Symptom

The upload button stays on `Queued`, `Validating Files`, or `Preparing Previews`.

### Likely Causes

- the background worker is not running
- the worker is busy with older upload-preparation or analysis jobs
- the selected upload set is large and preview generation is still in progress

### Corrective Action

- ask an operator to confirm `run_analysis_worker` is running
- wait for the current queued jobs to finish
- retry with a smaller selection if the job eventually fails with a storage or validation message

## Preprocess And Inference Failures

### Symptom

The preprocess step does not advance or returns to the preprocess page.

### Likely Causes

- missing or incompatible model weights
- incompatible TensorFlow or CPU environment, including missing `AVX` support
- a filesystem storage-full condition
- user cancellation
- the background worker is unavailable when analysis execution mode is `worker`

### Corrective Action

- confirm the expected model weights exist under `cytocv/core/weights`
- confirm the analysis host exposes `AVX` if TensorFlow fails with `Illegal instruction`
- free disk space
- ask an operator to confirm `run_analysis_worker` is running when the button remains queued
- rerun the pipeline from preprocess

## Display Shows No Cells

### Symptom

The display page loads but warns that no segmented cells were produced.

### Likely Causes

- inference produced a mask with no usable cells
- segmentation could not construct valid downstream regions
- channel mapping was incorrect

### Corrective Action

- verify the DIC channel mapping
- verify the input file quality
- rerun with simpler plugin selections if the primary goal is structural segmentation validation

## Save Or Unsave Fails

### Symptom

Saving files to the dashboard returns a storage error or unavailable-file message.

### Likely Causes

- the run is no longer available to the current session
- retained storage quota would be exceeded
- the selected UUID is not owned by the current account

### Corrective Action

- retry while the display session is still active
- free space by deleting saved runs
- if autosave was skipped because quota is full, open the transient run from the current session and save it later after freeing space
- confirm you are signed into the expected account

## Account Access Problems

### Symptom

Login, signup, or password recovery fails.

### Likely Causes

- the deployment's email, provider sign-in, or anti-abuse settings are incomplete
- the selected sign-in method is not enabled on that site
- a verification step was not completed successfully

### Corrective Action

- confirm that the site supports the sign-in method you are trying to use
- complete any requested verification step in the same browser session when possible; if you opened the email link elsewhere, return and sign in again
- ask a maintainer to review email, provider, or anti-abuse configuration if the site relies on those features

## Related Documents

- [`getting-started.md`](getting-started.md)
- [`workflow-guide.md`](workflow-guide.md)
- [`account-and-dashboard.md`](account-and-dashboard.md)
