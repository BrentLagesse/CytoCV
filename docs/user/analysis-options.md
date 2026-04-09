# Analysis Options

## Purpose

This guide explains the user-visible analysis controls that affect validation, scaling, segmentation-side measurement configuration, and plugin execution.

## Prerequisites

- access to the upload page or workflow defaults interface
- familiarity with the logical channel roles `DIC`, `Blue`, `Red`, and `Green`

## Default Plugin Configuration

The current default modern plugin set is:

- `RedLineIntensity`
- `CENDot`
- `GreenRedIntensity`
- `NuclearCellularIntensity`

These defaults require `DIC`, `Red`, and `Green`. They do not require `Blue`.

Legacy plugins remain available when legacy visibility is enabled:

- `NucleusIntensity`
- `BlueNucleusIntensity`
- `RedBlueIntensity`

## Channel Requirement Model

CytoCV derives required channels in layers:

1. `DIC` is always required because segmentation and CNN preprocessing depend on it.
2. Each selected plugin contributes its own required channels.
3. Manual required channels are added only when the validation module is enabled.
4. `enforce_wavelengths` expands the requirement to all four logical roles: `DIC`, `Blue`, `Red`, and `Green`.
5. `enforce_layer_count` requires exactly four layers only when it is enabled.

If no plugins are selected and no validation overrides are enabled, the enforced requirement set is `DIC` only.

### Plugin-Specific Channel Requirements

| Plugin | Required channels beyond `DIC` | Legacy | Included in modern defaults |
| --- | --- | --- | --- |
| `RedLineIntensity` | `Red`, `Green` | No | Yes |
| `CENDot` | `Red`, `Green` | No | Yes |
| `GreenRedIntensity` | `Red`, `Green` | No | Yes |
| `NuclearCellularIntensity` | `Red`, `Green` | No | Yes |
| `NucleusIntensity` | `Blue`, `Green` | Yes | No |
| `BlueNucleusIntensity` | `Blue` | Yes | No |
| `RedBlueIntensity` | `Red`, `Blue` | Yes | No |

The nuclear or cellular plugin family is exclusive in the current implementation. If multiple plugins from that family are selected, the first one in the stable plugin order remains active.

## Validation Module Controls

Advanced settings can turn on:

- the validation module itself
- exact layer-count enforcement
- all-wavelength enforcement
- manual required channels
- legacy plugin visibility

The validation module does not replace plugin-driven requirements. It augments them.

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

- puncta source selection for `Puncta Distance`
- Red line width
- CEN dot distance threshold
- CEN dot collinearity threshold
- nuclear or cellular mode selection
- optional Green contour filtering

The puncta-line mode currently supports:

- `red_puncta`
- `green_puncta`

The nuclear or cellular mode currently supports:

- `green_nucleus`
- `red_nucleus`

For the modern red/green measurements, CytoCV uses canonical contour slots across the shared statistics path. Each detected Red or Green contour is filled, clipped to the segmented cell, and ranked by clipped area, then center `x`, then center `y`. Slot numbers therefore stay consistent across:

- contour size outputs
- raw integrated contour intensity outputs
- Red-line and CEN-dot puncta selection
- nucleus measurements in `red_nucleus` and `green_nucleus` mode

In `red_nucleus`, nuclear intensity uses canonical Red slot `1`. In `green_nucleus`, nuclear intensity uses canonical Green slot `1`.

## Expected Outputs

The selected options influence:

- upload validation outcomes
- effective required channel enforcement
- scale information saved to `UploadedImage.scale_info`
- `CellStatistics.properties`
- per-cell plugin execution and debug imagery

## Common Errors

- missing required wavelengths
  Upload validation rejects the run before it enters the processing queue.
- unexpected Blue requirement
  A legacy plugin or all-wavelength enforcement is active.
- invalid unit or negative numeric values
  The application normalizes or falls back to safe defaults.

## Related Documents

- [`workflow-guide.md`](workflow-guide.md)
- [`output-guide.md`](output-guide.md)
- [`../reference/file-format-and-artifact-spec.md`](../reference/file-format-and-artifact-spec.md)

