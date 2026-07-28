# Diagrams For CytoCV

This folder contains the active CytoCV diagram catalog for implementation documentation, manuscript figures, and supplementary publication material. Editable Mermaid sources (`.mmd`) and rendered PNG outputs live together in this folder so captions, source diagrams, and publication-ready raster files can be updated as one set.

The diagrams use current CytoCV terminology:

- input sources: DeltaVision `.dv` and stack TIFF `.tif/.tiff`
- logical channel roles: `DIC`, `Blue`, `Red`, and `Green`
- universally required channel: `DIC`
- measurement model: plugin-based statistics with applicability-aware display and export
- run storage: saved or transient analyses
- exports: CSV and XLSX
- spatial units: pixels or microns, depending on active scale settings

## Primary Manuscript Figures

1. `01-system-architecture.mmd`

   - Use for: software overview.
   - Caption-ready focus: Layered CytoCV architecture showing the browser workflow, Django application services, job processing, scientific image analysis services, and database/media persistence boundaries.

2. `02-end-to-end-workflow.mmd`

   - Use for: methods overview.
   - Caption-ready focus: End-to-end workflow from `.dv` or stack TIFF upload through validation, channel mapping, DIC-guided segmentation, plugin measurements, review, saved/transient storage, and CSV/XLSX export.

3. `03-cell-analysis-flow.mmd`

   - Use for: per-cell measurement methods.
   - Caption-ready focus: Per-cell analysis flow showing retained DIC masks, canonical fluorescence contours, puncta modes, contour intensity statistics, CEN-dot classification, biorientation, nuclear-cell-pair intensity, and legacy Blue modules.

4. `11-data-model.mmd`

   - Use for: reproducibility or implementation appendix.
   - Caption-ready focus: Core database and artifact relationships linking uploaded source runs, preparation jobs, analysis jobs, previews, segmented outputs, and per-cell statistics.

## Supplementary Diagram Catalog

5. `04-artifact-lifecycle.mmd`

   - Focus: run artifacts, saved/transient retention, cleanup, and generated result files.

6. `05-plugin-channel-map.mmd`

   - Focus: DIC baseline requirement, plugin-specific fluorescence requirements, single-channel puncta modes, and legacy Blue paths.

7. `06-upload-validation-flow.mmd`

   - Focus: `.dv`/stack TIFF validation, metadata-assisted channel role mapping, plugin-derived required channels, scale extraction, and preview generation.

8. `07-scale-channel-resolution.mmd`

   - Focus: DV/TIFF scale metadata, manual overrides, x/y scale context, pixel/micron conversion, and threshold conversion.

9. `08-preprocess-inference-flow.mmd`

   - Focus: preprocessing and DIC-guided Mask R-CNN inference through `output/mask.tif`.

10. `09-segmentation-output-flow.mmd`

    - Focus: retained cell masks, cell inclusion mode, pair geometry, canonical contours, overlays, crops, and persisted statistics.

11. `10-display-export-flow.mmd`

    - Focus: Display/Dashboard review, row/metric filters, saved/transient actions, spatial units, and CSV/XLSX export.

12. `12-progress-cancellation-state.mmd`

    - Focus: worker-backed progress phases, terminal states, cancellation, and failure states.

13. `13-run-ownership-retention-state.mmd`

    - Focus: saved versus transient run ownership, save/unsave/sync behavior, and retention cleanup.

14. `14-authentication-account-flow.mmd`

    - Focus: supplementary account flow, optional reCAPTCHA, native email flow, and optional Google/Microsoft provider sign-in.

15. `15-legacy-blue-measurements.mmd`

    - Focus: supplementary legacy Blue-channel measurements and their relationship to the current configurable nuclear-cell-pair path.

## Rendering And Validation

Each `.mmd` file must have a same-stem `.png` rendered beside it.

Regenerate all PNGs from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\docs\diagrams\render-mermaid.ps1
```

The render script uses Mermaid CLI with the local Microsoft Edge executable, renders with a white background at publication-oriented scale, and validates every generated PNG. Validation fails if a file has an invalid PNG signature, cannot be decoded, has zero dimensions, or renders below the minimum publication size threshold.

Before using diagrams in a manuscript, inspect the rendered PNGs at 100% zoom and confirm that labels are readable, nodes do not overlap, and the caption language matches the current manuscript claims.
