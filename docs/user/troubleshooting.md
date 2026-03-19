# Troubleshooting

## Purpose

This guide lists common user-visible failures and the expected corrective action.

## Prerequisites

- access to the active CytoCV deployment
- the relevant error text or failing workflow step

## Upload Failures

### Symptom

The upload page reports invalid DV files or rejects files immediately.

### Likely Causes

- the file does not parse as a valid DeltaVision stack
- the file does not satisfy enforced layer-count requirements
- required wavelengths are missing
- a selected plugin requires a channel that is not present

### Corrective Action

- verify the file is a supported `.dv` file
- verify the current plugin selection
- disable unneeded validation controls
- confirm the run uses the intended DIC, DAPI, mCherry, and GFP mapping

## Preprocess And Inference Failures

### Symptom

The preprocess step does not advance or returns to the preprocess page.

### Likely Causes

- missing or incompatible model weights
- a filesystem storage-full condition
- user cancellation

### Corrective Action

- confirm the expected model weights exist under `cytocv/core/weights`
- free disk space
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
- confirm you are signed into the expected account

## Account Access Problems

### Symptom

Login, signup, or password recovery fails.

### Likely Causes

- reCAPTCHA is enabled and failing hostname validation
- email configuration is incomplete
- provider OAuth credentials are missing or invalid

### Corrective Action

- verify the auth environment configuration
- check that email settings are populated
- confirm the correct hostnames are configured for reCAPTCHA

## Related Documents

- [`getting-started.md`](getting-started.md)
- [`../ops/environment-reference.md`](../ops/environment-reference.md)
- [`../ops/security-and-privacy.md`](../ops/security-and-privacy.md)
