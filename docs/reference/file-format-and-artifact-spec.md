# File Format And Artifact Spec

## Purpose

This document defines the key input assumptions and generated artifact patterns used by the current codebase.

## Input File Assumptions

Supported input formats:

- DeltaVision `.dv`
- TIFF `.tif`
- TIFF `.tiff`

Current workflow assumptions:

- each uploaded file is interpreted as one independent run-level channel stack
- CytoCV supports four logical channel roles: `DIC`, `Blue`, `Red`, and `Green`
- only `DIC` is universally required
- additional required channels are derived from the selected plugin set and optional validation settings
- channel order can be remapped through `channel_config.json`
- exact four-layer enforcement occurs only when `enforce_layer_count` is enabled

CytoCV does not group multiple separate TIFF files into one multi-channel run based on filename similarity. When a user selects several source files, each file is saved, validated, previewed, processed, and displayed as its own run with its own UUID and `channel_config.json`.

## TIFF Channel Detection

TIFF uploads are expected to be stack files when more than one channel is needed. The stack can be a multi-page or otherwise channel-axis TIFF that `tifffile` can normalize into a channel-first image stack.

TIFF channel order is resolved in this order:

1. Read ImageJ metadata labels from `Labels` or `labels`.
2. If the labels form a complete, unambiguous four-channel set, build `channel_config.json` from those labels.
3. If metadata labels are missing, incomplete, duplicated, or ambiguous, fall back to the default channel order.

The recognized TIFF label patterns are:

- Red: a wavelength token near `w625`, within 12 nm of 625
- Green: a wavelength token near `w525`, within 12 nm of 525
- Blue: a wavelength token near `w435`, within 12 nm of 435
- DIC: labels containing `DIC`, `brightfield`, `transmission`, `r3dref`, `_ref`, or ending in `ref.tif`

The wavelength token matcher accepts `w625`, `w_625`, `w-625`, and `w 625` when the token is separated from surrounding letters or digits. Example softWoRx/ImageJ label metadata that maps successfully:

```text
sample_PRJ_w625.tif
sample_PRJ_w435.tif
sample_PRJ_w525.tif
sample_R3D_REF.tif
```

In that example, the source upload is still one TIFF stack. The filenames above are metadata labels inside the TIFF, not separate files that CytoCV assembles.

Default fallback order is:

```json
{
  "channel_red": 3,
  "channel_green": 2,
  "channel_blue": 1,
  "DIC": 0
}
```

Because required-channel validation checks the mapped channel index against the actual layer count, a one-layer TIFF with fallback mapping only provides `DIC` for validation purposes. It will fail workflows that require Red, Green, or Blue unless those channels are present in the stack and mapped by metadata or manual channel configuration.

## Channel Roles

- `DIC`: segmentation and morphology reference
- `Blue`: legacy nucleus-related and blue-channel measurements
- `Red`: red fluorescence measurements
- `Green`: green fluorescence measurements

## Run-Level Generated Files

Common artifacts under `MEDIA_ROOT/<uuid>/`:

- source upload file
- `channel_config.json`
- `preview_images/preview-layer<n>.png`
- `preprocessed_images/<source-stem>.png`
- `output/mask.tif`

  Labeled segmentation mask written after mask postprocessing; enclosed interior holes are filled before downstream outlines, crops, and contour clipping use it.

- `output/cellpairs.tif`
- `output/*_frame_<n>.png`
- `output/pair-geometry.json`
- `output/<image>-<cell>.neck_split`
- `output/<image>-<cell>.outline`
- `segmented/cell_<n>.png`
- `segmented/*-no_outline.png`
- `segmented/overlay-render-config.json`
- `segmented/overlay-cache-v4/*.png`
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
  "channel_blue": 1,
  "channel_red": 2,
  "channel_green": 3
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
- cell-pair geometry manifest: `output/pair-geometry.json`
- neck split sidecar: `output/<image>-<cell>.neck_split`
- outline coordinates: `output/<image>-<cell>.outline`; legacy segmented
  outline patterns are still checked by cleanup/deletion paths
- exact overlay render snapshot: `overlay-render-config.json`
- exact overlay cache entries: `overlay-cache-v4/cell-<cell>-<channel>.png`
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
