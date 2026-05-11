# File Format And Artifact Spec

## Purpose

This document defines the key input assumptions and generated artifact patterns used by the current codebase.

## Input File Assumptions

Primary input format:

- DeltaVision `.dv`

Current workflow assumptions:

- the upload can be interpreted as a channel stack
- CytoCV supports four logical channel roles: `DIC`, `Blue`, `Red`, and `Green`
- only `DIC` is universally required
- additional required channels are derived from the selected plugin set and optional validation settings
- channel order can be remapped through `channel_config.json`
- exact four-layer enforcement occurs only when `enforce_layer_count` is enabled

## Channel Roles

- `DIC`: segmentation and morphology reference
- `Blue`: legacy nucleus-related and blue-channel measurements
- `Red`: red fluorescence measurements
- `Green`: green fluorescence measurements

## Run-Level Generated Files

Common artifacts under `MEDIA_ROOT/<uuid>/`:

- source upload file
- `channel_config.json`
- preview PNG files
- preprocess intermediates
- `output/mask.tif`

  Labeled segmentation mask written after mask postprocessing; enclosed interior holes are filled before downstream outlines, crops, and contour clipping use it.

- `output/*_frame_<n>.png`
- `segmented/cell_<n>.png`
- `segmented/*-no_outline.png`
- `segmented/overlay-render-config.json`
- `segmented/overlay-cache-v1/*.png`
- `segmented/*_debug.png`

## Channel Configuration File

`channel_config.json` stores a mapping from channel name to layer index.

Minimal structural-only example:

```json
{
  "DIC": 0
}
```

Full four-role example:

```json
{
  "DIC": 0,
  "Blue": 1,
  "Red": 2,
  "Green": 3
}
```

This mapping is used by preprocess, segmentation, display, and dynamic main-image channel selection.

## Scale Metadata

`UploadedImage.scale_info` stores:

- effective scale
- manual fallback scale
- metadata-derived scale
- source and status fields
- optional axis-specific values such as `dx`, `dy`, and `dz`

## Segmented Output Naming

Observed output naming patterns include:

- full frames: `*_frame_<n>.png`
- binary cell masks: `cell_<n>.png`
- channel-indexed outlined crops: `<image>-<channel_index>-<cell>.png`
- channel-indexed no-outline crops: `<image>-<channel_index>-<cell>-no_outline.png`
- exact overlay render snapshot: `overlay-render-config.json`
- exact overlay cache entries: `overlay-cache-v1/cell-<cell>-<channel>.png`
- optional legacy debug overlays when raster export is enabled: `<image>-<cell>-Red_debug.png`, `<image>-<cell>-Green_debug.png`, `<image>-<cell>-Blue_debug.png`

## Export Output

CytoCV exports statistics tables as CSV and XLSX files from both Display and Dashboard. Single-file exports contain one statistics table. Multi-file exports contain one combined table with `File Name` as the first column, `Cell ID` as the second column, and selected metric columns after that. In combined exports, `File Name` is written only on the first row for each file group; following rows for the same file leave that cell blank.

Download filenames use:

`cytocv_<all-or-selected>_cell-metrics_<number>files_<YYYY-MM-DD_HHMM>.<extension>`

The `all` or `selected` token describes metric scope, not file scope. `all` means every user-selectable cell metric was included. `selected` means the export includes only a subset of cell metrics. The `<number>files` token is the actual number of files included in the export, and the extension is `.csv` or `.xlsx`.

Spatial table and export headers include the active unit. Contour area columns use square units, distance columns use length units, and contour center columns use coordinate length units. Red and Green contour columns are grouped by metric family: all three size columns first, then all three center coordinate columns for that color. Blue keeps its single center column after its single size column. Example order:

- `Blue Contour Size (px^2)` followed by `Blue Contour Center (x,y) (px)`
- `Red Contour 1 Size (px^2)`, `Red Contour 2 Size (px^2)`, `Red Contour 3 Size (px^2)`
- `Red Contour 1 Center (x,y) (px)`, `Red Contour 2 Center (x,y) (px)`, `Red Contour 3 Center (x,y) (px)`
- `Green Contour 1 Size (px^2)`, `Green Contour 2 Size (px^2)`, `Green Contour 3 Size (px^2)`
- `Green Contour 1 Center (x,y) (px)`, `Green Contour 2 Center (x,y) (px)`, `Green Contour 3 Center (x,y) (px)`

When the spatial unit is pixels, coordinate values are raw full-main-image pixel coordinates formatted as `x, y`. When the unit is micrometers, `x` is converted with the run's x-axis scale and `y` is converted with the run's y-axis scale. Missing or non-calculated contour centers are exported as `N/A`.

## Related Documents

- [`data-model.md`](data-model.md)
- [`glossary.md`](glossary.md)
- [`../developer/data-flow-and-artifacts.md`](../developer/data-flow-and-artifacts.md)
