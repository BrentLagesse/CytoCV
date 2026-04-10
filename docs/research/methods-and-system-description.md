# Methods And System Description

## Abstract

CytoCV is a web-based analysis system for DeltaVision microscopy of mitotic yeast cells. The platform integrates authenticated web workflows, DeltaVision-specific metadata parsing, Mask R-CNN-based segmentation, plugin-scoped per-cell quantification, and retention-aware result management in a single Django application. The current codebase supports four logical channel roles (`DIC`, `Blue`, `Red`, and `Green`), but only `DIC` is universally required. Additional fluorescence requirements are derived from the selected analysis plugins and optional upload-time validation policy.

## System Objective

The system is designed to reduce manual analysis effort while preserving the relationship between source microscopy stacks, derived segmentation artifacts, and exported measurements. CytoCV therefore treats run configuration, channel mapping, scale context, and plugin selection as first-class workflow state rather than transient UI detail.

## Input Model

CytoCV ingests DeltaVision (`.dv`) files that can be interpreted as channel stacks. The implementation recognizes four logical channel roles:

- `DIC`, used for structural segmentation and CNN preprocessing
- `Blue`, used for legacy nucleus-related measurements
- `Red`, used for red-signal contour and intensity measurements
- `Green`, used for green-signal contour, intensity, and dot-classification measurements

The software does not require all four roles in every run. The minimum baseline requirement is `DIC`. The default modern configuration requires `DIC`, `Red`, and `Green`. `Blue` becomes required only when a legacy Blue-channel legacy plugin is selected or when full-wavelength validation is enabled.

## Validation Logic

Upload-time validation is controlled by the effective requirement set assembled in `core.views.experiment` and `core.metadata_processing.error_handling.dv_validation`.

The effective required channels are formed as:

1. the baseline segmentation requirement `DIC`
2. the union of required channels declared by the selected plugins
3. any manual required channels, if the validation module is enabled
4. all four logical roles, if `enforce_wavelengths=True`

Exact four-layer validation is separate. It is applied only when `enforce_layer_count=True`.

This distinction matters scientifically and operationally. The codebase supports four logical roles, but the baseline workflow does not equate "supported" with "universally required."

## Measurement Model

Per-cell quantification is plugin driven. The current implementation exposes the following plugin definitions.

| Plugin | Additional channels beyond `DIC` | Legacy | Default modern configuration |
| --- | --- | --- | --- |
| `PunctaDistance` | `Red`, `Green` | No | Yes |
| `CENDot` | `Red`, `Green` | No | Yes |
| `GreenRedIntensity` | `Red`, `Green` | No | Yes |
| `NuclearCellPairIntensity` | `Red`, `Green` | No | Yes |
| `NucleusIntensity` | `Blue`, `Green` | Yes | No |
| `BlueNucleusIntensity` | `Blue` | Yes | No |
| `RedBlueIntensity` | `Red`, `Blue` | Yes | No |

The default modern workflow is therefore centered on `DIC`, `Red`, and `Green`. Blue-channel legacy analyses remain available for backward compatibility, but they are legacy paths rather than the primary current workflow.

## Computational Workflow

### 1. Upload And Validation

The upload stage creates a run UUID, persists the source file, resolves the effective required channel set, validates the DV structure, extracts channel-mapping information, and stores scale metadata when available.

### 2. Preview Generation

Browser-friendly PNG previews are generated per detected layer so that the operator can review channel ordering and file state before inference.

### 3. Preprocessing And Inference

The preprocess stage converts the structural channel input into the inference-ready representation and invokes the Mask R-CNN pipeline, producing a segmentation mask for downstream analysis.

### 4. Segmentation Product Assembly

The segmentation stage combines the generated mask with the original DV stack to produce outlined full-frame views, per-cell cropped outputs, and plugin-dependent debug overlays.

### 5. Per-Cell Quantification

The plugin layer computes cell-level values such as puncta distance, puncta-line intensity, green and red contour summaries, nuclear or cell-pair intensity measurements, and CEN dot classification outputs.

### 6. Review, Export, And Retention

The display and dashboard views expose run outputs, table exports, and the save-versus-transient retention model.

## Software Architecture

The application is implemented as a Django project with two main application domains:

- `accounts`, responsible for identity, preferences, dashboard behavior, and account lifecycle
- `core`, responsible for upload handling, processing, storage, segmentation, display, and scientific measurement

Persistent state is divided between database rows and filesystem-backed media artifacts.

## Reproducibility-Relevant Characteristics

The current codebase captures several features that support reproducible interpretation:

- a fixed Python target of `3.11.5`
- explicit database backend selection
- fail-fast environment validation
- deterministic plugin metadata registration in `core.stats_plugins`
- per-run saved scale context in `UploadedImage.scale_info`
- per-cell contextual metadata in `CellStatistics.properties`

## Limitations

- inference depends on external project-specific weights
- the TensorFlow-based analysis path requires a host with `AVX` CPU support
- artifact retention depends on filesystem capacity and account storage quotas
- Blue-channel legacy measurements coexist with a newer modern workflow and must be interpreted as legacy analyses

## Conclusion

CytoCV is best understood as a domain-specific analysis platform rather than a generic microscopy framework. Its architecture is optimized around the current yeast mitosis workflow, with `DIC`-driven segmentation, modern `Red` and `Green` measurements as the default path, and legacy Blue analyses preserved for backward compatibility.

