# Analysis Options

## Purpose

This guide explains the user-visible analysis controls that affect validation, scaling, segmentation-side measurement configuration, and plugin execution.

## Prerequisites

- access to the upload or workflow defaults interface
- familiarity with the four active channels: `DIC`, `DAPI`, `mCherry`, and `GFP`

## Plugin Selection

CytoCV exposes the following plugin identifiers in the current implementation:

- `MCherryLine`
- `GFPDot`
- `GreenRedIntensity`
- `NuclearCellularIntensity`
- `NucleusIntensity`
- `DAPI_NucleusIntensity`
- `RedBlueIntensity`

The first four are the main modern workflow options. The last three are legacy DAPI-related measurements.

## Channel Requirements

`DIC` is always required for segmentation.

Plugin-driven required channels:

- `MCherryLine`: `mCherry`, `GFP`
- `GFPDot`: `mCherry`, `GFP`
- `GreenRedIntensity`: `mCherry`, `GFP`
- `NuclearCellularIntensity`: `mCherry`, `GFP`
- `NucleusIntensity`: `DAPI`, `GFP`
- `DAPI_NucleusIntensity`: `DAPI`
- `RedBlueIntensity`: `mCherry`, `DAPI`

If the validation module is enabled, user-selected manual required channels can add to the enforced set.

## Validation Module Controls

Advanced settings can turn on:

- the validation module itself
- layer-count enforcement
- wavelength enforcement
- manual channel requirements
- display of legacy plugins

If wavelength enforcement is enabled while the module is disabled, the requirement can remain saved but paused.

## Scale Controls

CytoCV supports:

- a global manual microns-per-pixel value
- file-specific metadata extraction from DV headers
- a `prefer metadata scale` flag
- per-file manual override from the preprocess stage

Length inputs can use:

- `px`
- `um`

When `um` is used, values are converted to pixel-space thresholds using the effective scale context saved for the run.

## Measurement Controls

The active measurement-related controls include:

- mCherry line width
- GFP distance threshold
- GFP threshold
- nuclear or cellular mode selection
- optional GFP contour filtering

The nuclear or cellular mode currently supports:

- `green_nucleus`
- `red_nucleus`

## Expected Outputs

The selected options influence:

- upload validation outcomes
- required channel enforcement
- scale information saved to `UploadedImage.scale_info`
- `CellStatistics.properties`
- per-cell plugin execution and debug imagery

## Common Errors

- plugin removed by advanced settings
  This happens when a manually overridden required channel conflicts with a selected plugin.
- invalid unit or negative numeric values
  The application normalizes or falls back to safe defaults.
- missing required wavelengths
  Upload validation rejects the run before it enters the processing queue.

## Related Documents

- [`workflow-guide.md`](workflow-guide.md)
- [`output-guide.md`](output-guide.md)
- [`../reference/file-format-and-artifact-spec.md`](../reference/file-format-and-artifact-spec.md)
