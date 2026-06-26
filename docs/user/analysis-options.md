# Analysis Options

## Purpose

This guide explains the user-visible analysis controls that affect validation, scaling, segmentation-side measurement configuration, and plugin execution.

## Prerequisites

- access to the upload page or workflow defaults interface
- familiarity with the logical channel roles `DIC`, `Blue`, `Red`, and `Green`

## Default Plugin Configuration

The current workflow defaults select:

- `PunctaDistance`
- `CENDot`
- `Biorientation`
- `GreenRedIntensity`
- `NuclearCellPairIntensity`

These defaults require `DIC`, `Red`, and `Green`. They do not require `Blue`.

Legacy plugins remain available when legacy visibility is enabled:

- `NucleusIntensity`
- `BlueNucleusIntensity`
- `RedBlueIntensity`

## Cell Detection And Inclusion

Cell Inclusion Mode is an analysis-time setting. It controls which DIC-detected
cell candidates are retained before crops, statistics, Display rows, Dashboard
rows, and exports are created.

The supported modes are:

- Cell pairs only, the default and closest match to the historical workflow
- Single cells only, which retains detected single-cell candidates and excludes pairs
- Single cells and cell pairs, which retains both supported candidate types

Candidates that are unknown or ambiguous are excluded by default. A Display or
Dashboard Cell Type Filter can hide or show retained rows, but it cannot recover
cells that were excluded before analysis. Single-cell rows are structurally
supported for review and export; pair-specific outputs such as parentage, CEN
dot location, biorientation, and nuclear/cell-pair intensity are shown as `N/A`
when they do not apply.

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
| `PunctaDistance` | `Red`, `Green` | No | Yes |
| `CENDot` | `Red`, `Green` | No | Yes |
| `Biorientation` | `Red`, `Green` | No | Yes |
| `GreenRedIntensity` | `Red`, `Green` | No | Yes |
| `NuclearCellPairIntensity` | `Red`, `Green` | No | Yes |
| `NucleusIntensity` | `Blue`, `Green` | Yes | No |
| `BlueNucleusIntensity` | `Blue` | Yes | No |
| `RedBlueIntensity` | `Red`, `Blue` | Yes | No |

The nuclear or cell-pair plugin family is exclusive in the current implementation. If multiple plugins from that family are selected, the first one in the stable plugin order remains active.

CytoCV computes mother/daughter assignment automatically from DIC cell-pair geometry. The larger inferred lobe is reported as mother and the smaller inferred lobe as daughter. `CENDot` consumes that automatic parentage result, but its own output can still be `N/A` when Red or Green evidence fails validation.

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

## Puncta & Contour Detection And Measurement Controls

The active measurement-related controls include:

- puncta source selection for `Puncta Distance`
- Puncta line width
- CEN dot distance threshold
- CEN dot proximity radius
- Biorientation minimum Red distance
- Biorientation maximum Red distance
- Biorientation collinearity threshold
- nuclear or cell-pair mode selection
- optional Green dot splitting and split mode
- optional Green contour filtering
- optional alternate Red detection

The puncta-line mode currently supports:

- `red_puncta`
- `green_puncta`

The nuclear or cell-pair mode currently supports:

- `green_nucleus`
- `red_nucleus`

For the modern red/green measurements, CytoCV uses canonical contour slots across the shared statistics path. Each detected Red or Green contour is filled, clipped to the segmented cell, and ranked by clipped area, then center `x`, then center `y`. Slot numbers therefore stay consistent across:

- contour size outputs
- full-main-image contour center coordinate outputs
- raw total, maximum, and average contour intensity outputs
- Red-line and CEN-dot puncta selection
- nucleus measurements in `red_nucleus` and `green_nucleus` mode

In `red_nucleus`, nuclear intensity uses canonical Red slot `1`. In `green_nucleus`, nuclear intensity uses canonical Green slot `1`.

Contour center coordinates use the same canonical slots as the size and intensity fields. Coordinates are reported relative to the full main image with a bottom-left origin, and the display/export unit toggle converts them from raw pixels to micrometers when requested.

Red/Green Contour Intensities report Total, Max, and Average per contour slot.
Total Intensity is the integrated raw pixel sum inside the contour mask. Max
Intensity is the maximum raw pixel value inside the same mask. Average Intensity
is the mean raw pixel value inside the same mask. Selected CSV/XLSX exports can
include Total, Max, and Average independently rather than as one inseparable
group.

## Expected Outputs

The selected options influence:

- upload validation outcomes
- effective required channel enforcement
- saved scale context for each run
- saved measurement context used during review and export
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
