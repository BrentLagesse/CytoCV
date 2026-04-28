# Reproducibility and Validation

## Abstract

This document summarizes the practical conditions required to reproduce CytoCV analyses. Reproducibility in CytoCV depends on matching the source DeltaVision input, the resolved channel mapping, the selected analysis modules, the stored scale context, the software revision, and the model weights used during segmentation.

## Verified Workflow Defaults

The current implementation and automated tests support the following statements:

- DIC is the only universally required channel.
- If no analysis modules are selected, the required channel set is DIC only.
- The standard new-account workflow enables Puncta Distance, Cen Dot Location, Biorientation, Red/Green Contour Intensities, and Nuclear and Cell-Pair Intensity.
- The standard new-account workflow therefore requires DIC, Red, and Green.
- Blue becomes required only when a legacy analysis is enabled or when all-channel enforcement is turned on.
- Exact four-layer validation is optional and separate from the baseline channel-role check.

## Default Research Settings

The normalized default preference state defines the baseline workflow for a new account.

| Setting | Default state | Practical effect |
| --- | --- | --- |
| Default analyses | Puncta Distance; Cen Dot Location; Biorientation; Red/Green Contour Intensities; Nuclear and Cell-Pair Intensity | A standard new-account run requires DIC, Red, and Green. |
| Validation override module | Off | Manual channel additions and stricter validation toggles remain inactive until explicitly enabled. |
| Exact four-layer validation | Off | A run is not rejected solely for having fewer than four layers unless the stricter layer-count rule is turned on. |
| All-channel enforcement | Off | Blue is not required unless a legacy analysis or stricter all-channel validation is selected. |
| Show legacy analyses | Off | Blue-channel analyses stay hidden unless intentionally enabled. |
| Manual channel additions | None | No extra channel roles are added beyond the selected analysis requirements. |
| Nuclear measurement mode | Green nucleus measures Red | The modern nuclear or cell-pair workflow uses the green-defined nucleus contour unless the user changes the mode. |
| Use metadata-derived scale | On | Stored microscope scale metadata is preferred when available. |

## Context Recorded With Each Run

Interpretation of a CytoCV result depends on the information saved with the run:

- the original DeltaVision input
- the resolved DIC, Blue, Red, and Green channel mapping
- the selected analysis modules and their relevant settings
- the effective scale used for spatial measurements
- the exported per-cell measurement table

This stored context is important because CytoCV reports computed measurements, not final biological conclusions.

## Environment and Runtime Constraints

The reference software environment currently targets Python 3.11.5 together with the project dependency set and the expected model weights. Reproducible execution also depends on analysis hardware that satisfies the machine-learning runtime requirements used by the segmentation path. Shared deployments should preserve authenticated access, server-side validation, and protected result access so that users review the same files and outputs that were actually processed.

## Recommended Result Package

For a formal result package, preserve:

- the exact software revision
- the environment description and dependency set
- the model weight identifier or checksum used for segmentation
- the selected analysis modules and any non-default overrides
- the resolved channel-role mapping
- the stored scale context
- the exported measurement table and any reviewed overlays kept with the run

## Limits and Interpretation

- Transient previews or intermediate artifacts may be cleaned automatically and should not be treated as the archival record.
- A reproduced run can still differ if the underlying model weights, hardware compatibility, or saved settings differ.
- Public summaries should describe outputs as computed measurements and segmentation-derived artifacts rather than validated biological truth.

## Conclusion

CytoCV is reproducible when the input data, software revision, model weights, channel mapping, analysis selections, and scale context are treated as part of the result definition. The current implementation already records much of that context, but disciplined archival practice is still required for formal comparison or review.
