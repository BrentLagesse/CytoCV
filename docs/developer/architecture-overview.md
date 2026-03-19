# Architecture Overview

## Purpose

This document describes the current system architecture as implemented in the codebase.

## System Shape

CytoCV is a Django web application with two primary app-level domains:

- `accounts`
- `core`

The system combines:

- authenticated web flows
- file-backed media processing
- a Mask R-CNN inference path
- database-backed run and cell statistics

## Major Layers

### Presentation Layer

HTML templates under `cytocv/templates/` render:

- auth views
- experiment upload and preprocess views
- display view
- dashboard
- account settings
- workflow defaults

### Request And Workflow Layer

The main route map is in `cytocv/cytocv/urls.py`. Request handlers are split across:

- `accounts.views.*`
- `core.views.*`

The core scientific workflow spans:

- `core.views.experiment`
- `core.views.pre_process`
- `core.views.segment_image`
- `core.views.display`

### Domain And Persistence Layer

Primary persistence models live in `core.models`:

- `UploadedImage`
- `SegmentedImage`
- `DVLayerTifPreview`
- `CellStatistics`

User-level preferences and storage limits live in `accounts.models.CustomUser`.

### Scientific Processing Layer

Scientific and image-processing responsibilities are distributed across:

- `core.mrcnn.*`
- `core.image_processing.*`
- `core.contour_processing.*`
- `core.cell_analysis.*`
- `core.stats_plugins`
- `core.metadata_processing.*`
- `core.scale`

### Media And Retention Layer

Media artifact generation, cleanup, quota projection, and retention logic are centralized in `core.services.artifact_storage`.

## Security-Relevant Components

- protected media serving through `core.views.media`
- custom email authentication backend
- optional Google and Microsoft allauth providers
- optional reCAPTCHA gating
- CSP and browser security header middleware
- rate-limiting configuration in settings and security helpers

## Related Documents

- [`codebase-map.md`](codebase-map.md)
- [`request-flows.md`](request-flows.md)
- [`data-flow-and-artifacts.md`](data-flow-and-artifacts.md)
