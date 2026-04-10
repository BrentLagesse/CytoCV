# Diagrams For CytoCV

This folder contains the active diagram catalog for the current codebase. It serves both implementation documentation and manuscript-style figure preparation.

They are based on the current implementation in:

- `cytocv/core/views/experiment.py`
- `cytocv/core/views/pre_process.py`
- `cytocv/core/views/convert_to_image.py`
- `cytocv/core/views/segment_image.py`
- `cytocv/core/views/display.py`
- `cytocv/core/views/utils.py`
- `cytocv/core/services/artifact_storage.py`
- `cytocv/core/models.py`
- `cytocv/core/stats_plugins.py`
- `cytocv/core/metadata_processing/`
- `cytocv/accounts/views/`
- `cytocv/accounts/models.py`

## Primary Diagram Groups

- architecture
- workflow
- data model
- authentication and account flow
- artifact lifecycle and retention
- display and export
- progress and cancellation

## Core Paper Figures

1. `01-system-architecture.mmd`
   Use for: software overview.
   Caption idea: "Layered architecture of CytoCV showing the web tier, scientific services, and persistent storage."

2. `02-end-to-end-workflow.mmd`
   Use for: methods overview.
   Caption idea: "End-to-end workflow from DV ingestion through validation, segmentation, quantification, and review."

3. `08-preprocess-inference-flow.mmd`
   Use for: ML pipeline subsection.
   Caption idea: "Preprocessing and Mask R-CNN inference pipeline used to convert DIC input into segmentation masks."

4. `09-segmentation-output-flow.mmd`
   Use for: segmentation subsection.
   Caption idea: "Segmentation and result assembly pipeline, including whole-frame overlays, cell crops, and persisted outputs."

5. `03-cell-analysis-flow.mmd`
   Use for: feature extraction subsection.
   Caption idea: "Per-cell analysis pipeline used to derive distances, intensities, and optional legacy Blue measurements from segmented crops."

6. `11-data-model.mmd`
   Use for: implementation or reproducibility section.
   Caption idea: "Core data model for uploaded files, preview assets, segmented runs, and per-cell statistics."

## Extended Diagram Catalog

7. `04-artifact-lifecycle.mmd`
   Focus: file lifecycle and cleanup.

8. `05-plugin-channel-map.mmd`
   Focus: `DIC` baseline requirements, plugin-driven fluorescence dependencies, legacy Blue paths, and validation overrides.

9. `06-upload-validation-flow.mmd`
   Focus: upload handling and configurable DV validation logic.

10. `07-scale-channel-resolution.mmd`
    Focus: scale metadata, overrides, and threshold conversion.

11. `10-display-export-flow.mmd`
    Focus: result review, export, and saved-file state changes.

12. `12-progress-cancellation-state.mmd`
    Focus: progress phases and cancellation behavior.

13. `13-run-ownership-retention-state.mmd`
    Focus: transient versus saved result ownership and retention.

14. `14-authentication-account-flow.mmd`
    Focus: reCAPTCHA-gated authentication, provider SSO, signup, recovery, and account areas.

15. `15-legacy-blue-measurements.mmd`
    Focus: legacy Blue-driven measurements versus the modern `Red` and `Green` path.

## Rendered PNGs

Each `.mmd` file should have a matching `.png` rendered beside it.

To regenerate all PNGs:

```powershell
powershell -ExecutionPolicy Bypass -File .\docs\diagrams\render-mermaid.ps1
```

The renderer uses Mermaid CLI with the local Edge executable and writes white-background PNGs suitable for manuscript drafts.

