# File Format And Artifact Spec

## Purpose

This document defines the key input assumptions and generated artifact patterns used by the current codebase.

## Input File Assumptions

Primary input format:

- DeltaVision `.dv`

Current workflow assumptions:

- the upload can be interpreted as a channel stack
- CytoCV supports four logical channel roles: `DIC`, `DAPI`, `mCherry`, and `GFP`
- only `DIC` is universally required
- additional required channels are derived from the selected plugin set and optional validation settings
- channel order can be remapped through `channel_config.json`
- exact four-layer enforcement occurs only when `enforce_layer_count` is enabled

## Channel Roles

- `DIC`: segmentation and morphology reference
- `DAPI`: legacy nucleus-related and blue-channel measurements
- `mCherry`: red fluorescence measurements
- `GFP`: green fluorescence measurements

## Run-Level Generated Files

Common artifacts under `MEDIA_ROOT/<uuid>/`:

- source upload file
- `channel_config.json`
- preview PNG files
- preprocess intermediates
- `output/mask.tif`
- `output/*_frame_<n>.png`
- `segmented/cell_<n>.png`
- `segmented/*-no_outline.png`
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
  "DAPI": 1,
  "mCherry": 2,
  "GFP": 3
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
- debug overlays when the corresponding plugin path is active: `<image>-<cell>-mCherry_debug.png`, `<image>-<cell>-GFP_debug.png`, `<image>-<cell>-DAPI_debug.png`

## Export Output

Table exports are generated through `django-tables2` and use the uploaded image stem as the basis of the download name where possible.

## Related Documents

- [`data-model.md`](data-model.md)
- [`glossary.md`](glossary.md)
- [`../developer/data-flow-and-artifacts.md`](../developer/data-flow-and-artifacts.md)
