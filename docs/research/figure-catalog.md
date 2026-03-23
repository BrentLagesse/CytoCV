# Figure Catalog

## Purpose

This catalog maps the current diagram set to manuscript, report, or appendix usage.

## Primary Figures

### Figure 1: System Architecture

- Source: `docs/diagrams/01-system-architecture.mmd`
- Rendered: `docs/diagrams/01-system-architecture.png`
- Recommended use: overall software architecture
- Suggested caption: Layered architecture of CytoCV showing the web tier, scientific processing services, and persistence boundaries.

### Figure 2: End-To-End Workflow

- Source: `docs/diagrams/02-end-to-end-workflow.mmd`
- Rendered: `docs/diagrams/02-end-to-end-workflow.png`
- Recommended use: methods overview
- Suggested caption: End-to-end workflow from DeltaVision ingestion through validation, segmentation, quantification, and review.

### Figure 3: Cell Analysis Flow

- Source: `docs/diagrams/03-cell-analysis-flow.mmd`
- Rendered: `docs/diagrams/03-cell-analysis-flow.png`
- Recommended use: per-cell measurement subsection
- Suggested caption: Per-cell analysis pipeline used to derive contour, distance, and intensity measurements from segmented cell crops, including optional legacy DAPI contour handling.

### Figure 4: Data Model

- Source: `docs/diagrams/11-data-model.mmd`
- Rendered: `docs/diagrams/11-data-model.png`
- Recommended use: implementation or reproducibility section
- Suggested caption: Core persistent entities for uploads, previews, segmented runs, and cell-level statistics.

## Supplementary Figures

### Validation, Requirements, And Scale

- `docs/diagrams/05-plugin-channel-map.mmd`
  Suggested caption: Channel requirement model showing `DIC` as the universal segmentation dependency, plugin-driven fluorescence requirements, legacy DAPI analyses, and optional validation expansion to all four logical roles.
- `docs/diagrams/06-upload-validation-flow.mmd`
  Suggested caption: Upload-time validation flow showing configurable layer-count and effective channel-requirement checks before a run enters preprocessing.
- `docs/diagrams/07-scale-channel-resolution.mmd`
  Suggested caption: Scale resolution and channel-mapping path from DeltaVision metadata through per-run threshold conversion.

### Processing And Output

- `docs/diagrams/08-preprocess-inference-flow.mmd`
- `docs/diagrams/09-segmentation-output-flow.mmd`
- `docs/diagrams/10-display-export-flow.mmd`

### Retention And Control Flow

- `docs/diagrams/04-artifact-lifecycle.mmd`
- `docs/diagrams/12-progress-cancellation-state.mmd`
- `docs/diagrams/13-run-ownership-retention-state.mmd`

### Authentication And Legacy Behavior

- `docs/diagrams/14-authentication-account-flow.mmd`
- `docs/diagrams/15-legacy-dapi-measurements.mmd`

## Figure Usage Notes

- Use the first four figures for the main narrative.
- Use the supplementary figures for validation logic, appendix material, or implementation detail.
- Keep Markdown captions as the editable source of truth.
- Regenerate PNGs when the underlying flow or model changes.

## Regeneration

Diagram PNG regeneration is documented in [`../diagrams/README.md`](../diagrams/README.md).
