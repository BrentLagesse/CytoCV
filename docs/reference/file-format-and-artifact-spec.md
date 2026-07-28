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
- `segmented/overlay-layers-v1/*.png` (lazy, transparent display-only layers)
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
- selective overlay layer entries:
  `overlay-layers-v1/cell-<cell>-<family>-<display-channel>.png`
- optional legacy debug overlays when raster export is enabled: `<image>-<cell>-Red_debug.png`, `<image>-<cell>-Green_debug.png`, `<image>-<cell>-Blue_debug.png`

## Cell Viewer Overlay Contract

`CellPairImages` remains an eight-entry array in this exact order:

1. DIC outlined
2. DIC no-outline
3. Blue outlined
4. Blue no-outline
5. Red outlined
6. Red no-outline
7. Green outlined
8. Green no-outline

Display and Dashboard add an `OverlayLayers` object without changing those
entries. Schema version `1` contains `selective`, `aggregateAvailable`,
`availableFamilies`, and sparse `layerUrlTemplates`. URL templates contain the
literal `{cellId}` placeholder.

The viewer's logical families are:

- `cellBoundary`: DIC external cell or cell-pair boundary, neck seam, and
  mother/daughter labels
- `redContours`: canonical or selected alternate Red contour geometry,
  wherever it is drawn on Blue, Red, or Green display crops
- `greenContours`: canonical or selected alternate Green contour geometry,
  wherever it is drawn on Blue, Red, or Green display crops
- `blueContour`: canonical Blue contour geometry on the Blue display crop
- `analysisAnnotations`: the independently drawn puncta measurement line on
  available Red and/or Green display crops, including single-channel puncta runs

Layer PNGs are transparent RGBA annotations and never contain the base
microscopy pixels. Schema `v1` uses the renderer's existing colors: Red
`(255, 0, 0)`, Green `(0, 255, 0)`, Blue `(0, 0, 255)`, and puncta-line white
`(255, 255, 255)`. The DIC family preserves all changed pixels from the stored
outlined DIC crop, including anti-aliased labels and their black stroke, rather
than trying to classify those pixels by color.

Current DIC morphology consists of the cyan external boundary at one-pixel
thickness, the cyan one-pixel neck seam with two-pixel dash/gap spacing, and
white `M`/`D` labels with a one-pixel black stroke. Canonical Red, Green, and
Blue contours and alternate nucleus contours use one-pixel lines. The puncta
measurement line uses the run's configured line thickness. Red and Green
geometry can appear on several fluorescence display channels; family identity
is therefore independent of the displayed column.

Layers are generated lazily with a per-cell/family lock and atomic PNG writes.
One request can write that family's applicable display-channel layers, but no
filename or file contains a visibility combination. A four-channel run has at
most ten sparse layer files per cell: one Cell boundary, three Red, three
Green, one Blue, and two Analysis annotations.

`All` continues to use the existing outlined or exact aggregate overlay image,
so it is pixel-identical to the previous checked Contours state. `None` uses
the existing no-outline crop. Mixed selections resolve each displayed channel
independently: channels whose applicable families remain fully selected keep
their aggregate source, while affected channels use the no-outline crop plus
only the chosen transparent layers. Base crops and layers are centered with the
same contain geometry, so rectangular cell crops retain their coordinate
system and aspect ratio. Runs without a current replay snapshot remain
aggregate-only: their best outlined/debug image is used for `All`, and their
no-outline image is used for `None` when present. A restored run whose snapshot
survives but whose required no-outline source crops do not is likewise treated
as aggregate-only.

Overlay visibility is display-only. It does not rerun segmentation, alter
contour detection, update `CellStatistics`, or change table/export values.

Layer bytes live under the normal run namespace, so saved-run quota usage and
storage projections include them automatically. Per-cell deletion removes
layer PNGs and locks across schema-versioned `overlay-layers-v*` directories.
File deletion, failed-run cleanup, stale transient deletion, and account
deletion remove the containing run namespace and therefore remove the layers.

### Representative Storage Verification

A temporary-copy replay of three current four-channel cells produced ten layer
PNGs per cell after generating every family. It did not write to the retained
run. For the two sampled cells that already had a complete three-file
`overlay-cache-v4` entry, the comparison was:

| Artifact set per cell | Files | Average bytes |
| --- | ---: | ---: |
| Existing four no-outline crops | 4 | 24,821.5 |
| Existing complete aggregate fluorescence cache | 3 | 14,608 |
| All new transparent family layers | 10 | 4,016.5 |

Across all three sampled cells, the full ten-layer set averaged 3,935.7 bytes.
Transparent pixels store zero RGB rather than hidden base microscopy pixels.
The Cell boundary layer was still the largest individual layer because it
preserves anti-aliased DIC labels; fluorescence layers were smaller.
Exercising all menu combinations cannot increase the per-cell layer count
beyond those ten family/channel files, because selection combinations are
never persisted. These layer bytes are additional to any retained aggregate
cache: the three-file aggregate remains necessary for exact `All` rendering
and legacy fallback, while the ten-file figure remains the lazy artifact upper
bound if every family is requested for that cell. Per-channel aggregate reuse
can avoid requesting families that do not need layered composition.

## Export Output

CytoCV exports statistics tables as CSV and XLSX files from both Display and Dashboard. Single-file exports contain one statistics table. Multi-file exports contain `Cell ID`, `Cell Type`, and the included metric columns. Multi-file exports contain one combined table with `File Name` as the first column, `Cell ID` as the second column, `Cell Type` as the third column, and selected metric columns after that. In combined exports, `File Name` is written only on the first row for each file group; following rows for the same file leave that cell blank.

Download filenames use:

`cytocv_<all-or-selected>_cell-metrics_<number>files_<YYYY-MM-DD_HHMM>.<extension>`

The `all` or `selected` token describes metric scope, not file scope. `all` means every user-selectable cell metric was included. `selected` means the export includes only a subset of cell metrics. The `<number>files` token is the actual number of files included in the export, and the extension is `.csv` or `.xlsx`.

Export row filters are separate from metric-column selection:

- `_cell_type` filters retained serialized rows by Cell Type when both Single Cell and Cell Pair rows are present; otherwise it effectively behaves as all rows.
- `_puncta_source_contour_count` filters retained rows by final valid Puncta Source contour count when source contour count data exists.
- `_columns` selects metric columns and never changes which rows are exported.
- deleted cells are excluded before Cell Type and source contour count filters are applied.

The source contour count filter uses final canonical Red or Green source
contour slots clipped to the retained cell mask. For single-cell rows, the
count is inside the single-cell mask. For cell-pair rows, the count is inside
the cell-pair mask. It does not use mother/daughter subregions for the generic
row filter.

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
