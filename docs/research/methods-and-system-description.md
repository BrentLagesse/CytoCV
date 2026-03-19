# Methods And System Description

## Abstract

CytoCV is a web-based analysis system for four-channel DeltaVision microscopy stacks of mitotic yeast cells. The software combines authenticated web workflows, DV-specific metadata parsing, Mask R-CNN-based segmentation, per-cell measurement plugins, and retention-aware result management in a single Django application.

## System Objective

The system is designed to reduce manual analysis effort when processing mitotic yeast microscopy data. It provides a structured path from raw DV upload to per-cell statistical output while preserving the relationship between source image stacks, channel mapping, segmentation products, and exported measurements.

## Input Assumptions

The active workflow assumes a four-channel stack composed of:

- DIC
- DAPI
- mCherry
- GFP

The software can enforce exact layer count, required wavelengths, and plugin-driven channel requirements during upload.

## Computational Workflow

### 1. Upload And Validation

The upload stage creates a run UUID, persists the source file, validates the DV structure, extracts channel mapping information, and stores scale metadata when available.

### 2. Preview Generation

Browser-friendly PNG previews are generated per layer so that the operator can review channel ordering and file state before inference.

### 3. Preprocessing And Inference

The preprocess stage converts the relevant structural data into the inference-ready representation and invokes the Mask R-CNN pipeline, producing a segmentation mask for downstream analysis.

### 4. Segmentation Product Assembly

The segmentation stage combines the generated mask with the original DV stack to produce outlined full-frame views, per-cell cropped outputs, and channel-specific debug overlays.

### 5. Per-Cell Quantification

A plugin-based measurement layer computes cell-level values such as red-dot distance, line GFP intensity, nuclear and cellular intensity summaries, and GFP dot classification outputs.

### 6. Review, Export, And Retention

The display and dashboard views expose the run outputs, table exports, and save-versus-transient retention model.

## Software Architecture

The application is implemented as a Django project with two main application domains:

- `accounts` for identity, preferences, dashboard behavior, and account lifecycle
- `core` for upload handling, processing, storage, segmentation, display, and scientific measurement

Persistent state is divided between database rows and filesystem-backed media artifacts.

## Reproducibility-Relevant Characteristics

- exact Python version expectation: `3.11.5`
- explicit database backend selection
- fail-fast environment validation
- deterministic plugin metadata registration
- per-run saved scale context in `UploadedImage.scale_info`
- per-cell contextual measurement metadata in `CellStatistics.properties`

## Limitations

- the active workflow is tightly centered on the four expected channel roles
- inference depends on external project-specific weights
- artifact retention depends on available filesystem capacity and account storage quota
- some legacy measurement paths coexist with a newer nuclear/cellular workflow and require careful interpretation

## Conclusion

CytoCV is best understood as a domain-specific analysis platform rather than a generic microscopy framework. Its architecture is optimized around the concrete imaging assumptions, channel semantics, and review or export needs present in the current yeast mitosis workflow.
