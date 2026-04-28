# Figure Catalog

## Purpose

This catalog summarizes the current CytoCV diagram set for reports, appendices, collaborator packets, and research-facing documentation. It uses the same public terminology as the current interface: DIC, Blue, Red, and Green.

## Primary Figures

| Figure | Recommended use | Caption focus |
| --- | --- | --- |
| Figure 1. System architecture | Overall software architecture | Layered view of the web interface, scientific processing components, and persistent storage boundaries. |
| Figure 2. End-to-end workflow | Methods overview | DeltaVision ingestion through validation, segmentation, quantification, review, and export. |
| Figure 3. Cell analysis flow | Per-cell measurement section | How DIC-based segmentation and channel-specific measurements combine at the single-cell level. |
| Figure 4. Data model | Reproducibility or implementation appendix | Relationships among uploaded runs, previews, segmented outputs, and per-cell statistics. |

## Supplementary Figures

| Topic group | Figures | Typical use |
| --- | --- | --- |
| Validation and channel rules | Plugin-channel map; upload validation flow; scale and channel resolution | Appendix material for required-channel logic, metadata interpretation, and scale handling. |
| Processing and output | Preprocess and inference flow; segmentation output flow; display and export flow | Detailed workflow explanation beyond the main narrative figure set. |
| Retention and control | Artifact lifecycle; progress and cancellation state; run ownership and retention state | Operational context for run persistence, cancellation, and saved-result handling. |
| Access and legacy context | Authentication and account flow; legacy Blue measurements | Account-based access overview and legacy analysis behavior when Blue-channel workflows are still needed. |

## Figure Usage Notes

- Use the first four figures for the primary narrative in a manuscript, thesis chapter, or software appendix.
- Use the supplementary figures when reviewers or collaborators need more detail on validation rules, workflow control, or legacy analysis paths.
- Keep figure captions aligned with the current public channel terms Blue, Red, Green, and DIC rather than older instrument-specific names.
- Revise the figure set whenever the workflow, validation policy, or measurement terminology changes.

## Maintenance Note

Editable diagram sources and rendered PNG assets are maintained alongside the rest of the repository documentation so that captions and diagrams can be updated together.
