# Methods and System Description

## Abstract

CytoCV is a web-based research workflow for DeltaVision microscopy of mitotic yeast cells. It combines authenticated access, upload validation, DIC-guided segmentation, configurable red/green analysis modules, legacy blue-channel analyses, and exportable per-cell measurements in one application. Throughout this document, channel terminology follows the current user-facing interface: DIC, Blue, Red, and Green. When instrument metadata uses names such as DAPI, mCherry, or GFP, CytoCV attempts to normalize those labels into the Blue, Red, and Green roles before validation and analysis continue.

## System Objective

The platform is designed to reduce manual image-review effort while preserving the relationship between the source microscopy stack, the segmentation output, and the exported measurements. CytoCV therefore treats channel mapping, scale context, selected analyses, and saved results as part of the workflow record rather than disposable interface state.

## Channel Model

CytoCV presents four logical channel roles to users:

- DIC is the structural or reference channel used for segmentation and preprocessing.
- Blue is an optional fluorescence role reserved for legacy nucleus-oriented analyses.
- Red is a fluorescence role used by the current default puncta, contour, and intensity measurements.
- Green is a fluorescence role used by the current default puncta, contour, intensity, and dot-classification measurements.

Not every run requires all four roles. DIC is the only universally required channel. The current default workflow for new accounts requires DIC, Red, and Green. Blue becomes required only when a legacy analysis is intentionally enabled or when stricter all-channel validation is turned on.

## Validation Model

CytoCV builds the required channel set from four layers of logic:

1. DIC is always required because segmentation depends on it.
2. Each selected analysis module adds the channel roles it needs.
3. Optional manual channel requirements can add extra roles when the validation override module is enabled.
4. Optional all-channel enforcement can require DIC, Blue, Red, and Green together.

Exact four-layer validation is separate from channel-role validation. It is available as a stricter policy, but it is not the baseline rule for every run.

## Analysis Modules

The current analysis modules fall into a default modern set and a legacy blue-channel set.

| Analysis module | Channel roles beyond DIC | Default in new accounts | Notes |
| --- | --- | --- | --- |
| Puncta Distance | Red, Green | Yes | Measures the distance between puncta in one channel and samples signal from the opposite channel along that line. |
| Cen Dot Location | Red, Green | Yes | Classifies green-dot localization relative to the red puncta pair and the segmented cell geometry. |
| Biorientation | Red, Green | Yes | Counts green dots relative to the red puncta axis after distance and collinearity checks. |
| Red/Green Contour Intensities | Red, Green | Yes | Computes contour-based raw intensity summaries across the red and green channels. |
| Nuclear and Cell-Pair Intensity | Red, Green | Yes | Uses either the red or green channel as the nuclear contour source and measures the opposite channel in nucleus and cell-pair regions. |
| Nucleus Green Intensity | Blue, Green | No | Legacy analysis that uses the Blue channel as the contour reference for Green measurements. |
| Nucleus Blue Intensity | Blue | No | Legacy analysis that measures Blue intensity using Blue-derived nucleus and cytoplasm regions. |
| Red-in-Blue Intensity | Red, Blue | No | Legacy analysis that measures Blue signal around red-dot contour locations. |

## Workflow Overview

1. Upload and validation: the run is created, the DeltaVision file is checked, channel roles are resolved, and scale metadata is stored when available.
2. Preview and review: browser-friendly previews help the user confirm channel ordering and file state before analysis starts.
3. DIC-based preprocessing and segmentation: the structural channel is prepared for the Mask R-CNN pipeline, which produces the segmentation mask used downstream.
4. Per-cell measurement: selected modules compute puncta, contour, nuclear, cell-pair, or localization measurements for each segmented cell.
5. Review, export, and retention: users inspect overlays and tabular outputs, then either keep the run with their account or allow it to remain transient according to the configured workflow.

## Architecture and Record Keeping

CytoCV is implemented as a Django application with an account-oriented web layer and an analysis layer that handles upload parsing, segmentation, measurement, and artifact storage. Each run retains the resolved channel mapping, selected analyses, relevant scale context, and per-cell measurement records so exported results can be traced back to the analysis configuration that produced them.

## Scope and Limits

- CytoCV depends on project-specific model weights that are not bundled with the public repository.
- Analysis hosts must satisfy the machine-learning runtime requirements used by the segmentation pipeline.
- Legacy Blue analyses remain available for backward compatibility, but they are not the default research path.
- The exported values are computed measurements and derived visualization artifacts. They support interpretation, but they are not a substitute for final biological judgment.

## Conclusion

CytoCV is best understood as a domain-specific analysis platform for a defined microscopy workflow. Its current default path centers on DIC for segmentation and on Red and Green for most contemporary measurements, while Blue-channel analyses remain available only for legacy or explicitly selected use cases.
