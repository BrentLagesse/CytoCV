# Figure Catalog

## Purpose

This catalog identifies the current CytoCV diagram set for manuscript figures, supplementary figures, reports, appendices, and collaborator packets. It uses the same public terminology as the current application and documentation: DIC, Blue, Red, Green, `.dv`, stack TIFF, plugin-based statistics, Display/Dashboard review, CSV/XLSX export, and saved/transient runs.

## Recommended Primary Figures

| Figure | Source | Recommended use | Caption focus |
| --- | --- | --- | --- |
| Figure 1. System architecture | `docs/diagrams/01-system-architecture.png` | Overall software architecture | Browser workflow, Django services, job processing, scientific image-analysis services, and persistence boundaries. |
| Figure 2. End-to-end workflow | `docs/diagrams/02-end-to-end-workflow.png` | Methods overview | `.dv` or stack TIFF upload through validation, channel mapping, DIC-guided segmentation, plugin measurement, review, saved/transient storage, and CSV/XLSX export. |
| Figure 3. Cell analysis flow | `docs/diagrams/03-cell-analysis-flow.png` | Per-cell measurement section | Retained DIC masks, canonical fluorescence contours, puncta modes, contour intensities, CEN-dot classification, biorientation, nuclear-cell-pair intensity, and legacy Blue modules. |
| Figure 4. Data model | `docs/diagrams/11-data-model.png` | Reproducibility or implementation appendix | Relationships among uploaded runs, upload-preparation jobs, analysis jobs, previews, segmented outputs, and per-cell statistics. |

## Supplementary Figures

| Topic group | Figure sources | Typical use |
| --- | --- | --- |
| Artifacts and retention | `04-artifact-lifecycle.png`; `13-run-ownership-retention-state.png` | Explain saved/transient result storage, generated artifacts, and cleanup behavior. |
| Channel and validation rules | `05-plugin-channel-map.png`; `06-upload-validation-flow.png`; `07-scale-channel-resolution.png` | Document required-channel logic, metadata interpretation, TIFF/DV scale handling, and pixel/micron conversion. |
| Processing and output | `08-preprocess-inference-flow.png`; `09-segmentation-output-flow.png`; `10-display-export-flow.png` | Provide detailed workflow explanation beyond the main narrative figure set. |
| Progress and cancellation | `12-progress-cancellation-state.png` | Explain worker-backed progress phases, cancellation, terminal states, and failure handling. |
| Access and legacy context | `14-authentication-account-flow.png`; `15-legacy-blue-measurements.png` | Supplementary account-flow overview and backward-compatible legacy Blue measurement context. |

## Figure Usage Notes

- Use Figures 1-4 for the primary manuscript narrative unless the target journal requests fewer software architecture figures.
- Use supplementary figures for reviewer questions about validation rules, workflow control, generated artifacts, access control, or legacy behavior.
- Treat CEN-dot, biorientation, puncta, and nuclear-cell-pair outputs as software-generated measurements unless biology-side validation is described separately.
- Keep figure captions aligned with current logical channel terms rather than older fluorophore-specific or instrument-only terms.
- Regenerate all PNGs after any `.mmd` change and verify the images open in ordinary PNG viewers before submission.

## Maintenance Note

Editable diagram sources and rendered PNG assets are maintained in `docs/diagrams/`. The render script in that folder validates PNG compatibility so corrupted raster files cannot silently remain in the repository.
