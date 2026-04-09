# Reproducibility And Validation

## Abstract

This document summarizes the practical requirements and implementation-specific limits on reproducing CytoCV results and deployments. It is grounded in the active code paths for plugin registration, upload validation, workflow defaults, and validation-related tests.

## Environment Constraints

CytoCV is sensitive to environment consistency. The codebase expects:

- Python `3.11.5`
- the dependency set in `requirements.txt`
- project-specific ML weights present in the expected weights directory
- a valid `.env` configuration

SQLite is acceptable for local development and testing. PostgreSQL is required for production operation.

## Validation Semantics Verified Against Code

The implemented requirement model is defined across `core.stats_plugins`, `core.views.experiment`, `core.metadata_processing.error_handling.dv_validation`, and `core.tests.test_stats_validation`.

The verified behaviors are:

- `DIC` is the only universally required channel
- if no plugins are selected, the required channel set is `["DIC"]`
- the default modern selected plugins require `DIC`, `Red`, and `Green`
- Blue requirements are introduced by legacy plugins or by optional all-wavelength enforcement
- `enforce_wavelengths=True` expands the required set to all four logical roles
- `enforce_layer_count=True` enables exact four-layer validation; it is not a universal baseline rule

These behaviors are test-backed and should be treated as the documentation source of truth until the implementation changes.

## Default Preference State

The normalized default preference payload in `accounts.preferences` establishes the baseline workflow policy.

| Setting | Default value | Reproducibility implication |
| --- | --- | --- |
| `selected_plugins` | `RedLineIntensity`, `CENDot`, `GreenRedIntensity`, `NuclearCellularIntensity` | Baseline modern run requires `DIC`, `Red`, and `Green` |
| `module_enabled` | `False` | Validation overrides are disabled by default |
| `enforce_layer_count` | `False` | Exact four-layer enforcement is off by default |
| `enforce_wavelengths` | `False` | All-four-role enforcement is off by default |
| `show_legacy_plugins` | `False` | Legacy Blue analyses are hidden by default |
| `manual_required_channels` | empty list | No extra manual channel requirements are applied |
| `nuclear_cellular_mode` | `green_nucleus` | Modern nuclear or cellular measurements use the green-nucleus mode unless overridden |
| `use_metadata_scale` | `True` | Metadata-derived scale is preferred when available |

## Configuration Validation

The settings layer performs fail-fast validation for:

- database backend selection
- required PostgreSQL credentials
- production secret-key safety
- email transport toggle consistency
- allowed account email verification modes

This reduces configuration ambiguity and improves reproducibility across deployments.

## Data And Scale Reproducibility

Reproducibility of measurements depends on:

- the original DV input
- the resolved channel mapping
- the effective scale selected for the run
- the selected plugin set
- threshold and length parameters saved in session and copied into per-cell properties

CytoCV stores scale context and measurement context directly alongside run data, which preserves interpretability after processing completes.

## Test Coverage Relevant To Validation

The active automated suite includes coverage for:

- upload-time scale initialization
- preferences normalization
- artifact storage behavior
- inference and statistics-related logic
- table behavior
- validation-related unit tests, including channel requirement behavior

This coverage is useful but not exhaustive. End-to-end reproducibility still depends on the exact runtime environment, the presence of the same model weights, and the same input data.

## Runtime Constraints

Two runtime constraints are especially important for reproducible scientific execution:

- the model weights file must be present and unchanged
- the TensorFlow-based analysis host must expose `AVX`

A server can host the web interface without `AVX`, but the analysis pipeline will fail with `Illegal instruction` if the CPU does not support the required instruction set.

## Known Limits

- external model weights are required and are not embedded into the repository
- transient artifacts may be cleaned automatically and are not a stable archival record
- some outputs are graphical derivatives rather than raw numerical primitives
- local and production environments differ in database backend and security posture

## Recommended Reproducibility Practice

For any formal result package, preserve:

- exact commit hash
- `.env` policy with secrets removed but settings retained
- Python version
- dependency set
- model weight identifier
- selected plugin set
- run scale context
- exported table output

## Conclusion

CytoCV is reproducible when environment, model, input, and run configuration are treated as part of the result definition. The current codebase already stores part of that context internally, but disciplined deployment, archival practice, and CPU compatibility remain necessary for formal reproducibility.

