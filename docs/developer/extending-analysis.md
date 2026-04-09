# Extending Analysis

## Purpose

This document explains how to add or modify analysis behavior in the current plugin-based system.

## Current Plugin Model

Plugin metadata is declared centrally in `core.stats_plugins`. Each plugin definition includes:

- stable plugin ID
- user-facing label
- description
- module name
- class name
- required channels
- optional dependencies
- legacy status
- optional exclusive group

Execution uses `build_stats_execution_plan`, which normalizes selections and instantiates analysis classes once per run.

## Adding A New Plugin

1. Create the analysis implementation in `core/cell_analysis/`.
2. Implement the class expected by the plugin metadata.
3. Ensure the class supports the current setup and execution pattern used by `segment_image.get_stats`.
4. Register the plugin in `core.stats_plugins.PLUGIN_DEFINITIONS`.
5. Add the plugin ID to `PLUGIN_ORDER`.
6. Declare required channels and any exclusive-group behavior.
7. Verify the plugin appears in both workflow defaults and upload-time UI payloads.

## Validation Implications

Any plugin added to the metadata table automatically participates in:

- upload-time channel requirement summaries
- optional upload-time wavelength enforcement
- workflow-defaults dependency messaging

This means channel requirements must be correct at registration time.

`DIC` remains part of the baseline requirement through `ALWAYS_REQUIRED_CHANNELS`, and plugin registration is responsible only for the additional channels beyond that baseline.

## Statistics Output Implications

If a plugin writes new values into `CellStatistics`, decide whether those values belong in:

- an existing numeric field
- `properties`
- a new model field

If a new model field is required:

- add the field to `CellStatistics`
- create a migration
- update display and dashboard serializers
- update tables and reference docs

## Preferred Extension Pattern

Use the plugin metadata layer as the single source of truth for user-facing plugin identity and required channels. Avoid scattering plugin registration logic across templates and views.

## Regression Areas To Check

- upload validation
- workflow defaults UI
- display statistics rendering
- dashboard exports
- tests for plugin normalization or channel validation

## Related Documents

- [`testing-guide.md`](testing-guide.md)
- [`../reference/data-model.md`](../reference/data-model.md)
- [`../reference/file-format-and-artifact-spec.md`](../reference/file-format-and-artifact-spec.md)

