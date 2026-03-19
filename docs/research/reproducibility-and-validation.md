# Reproducibility And Validation

## Abstract

This document summarizes the practical requirements and limits on reproducing CytoCV results and deployments.

## Environment Constraints

CytoCV is currently sensitive to environment consistency. The codebase expects:

- Python `3.11.5`
- the dependency set in `requirements.txt`
- project-specific ML weights present in the expected weights directory
- a valid `.env` configuration

SQLite is allowed for local development and testing. PostgreSQL is required for production operation.

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
- threshold and length parameters saved in session and ultimately copied into per-cell properties

CytoCV stores scale context and measurement context directly alongside run data, which helps preserve interpretability after processing completes.

## Validation Coverage In Code

Existing automated coverage includes:

- upload-time scale initialization
- preferences normalization
- artifact storage behavior
- inference and stats-related logic
- table behavior
- validation-related unit tests

This is useful but not exhaustive. End-to-end reproducibility still depends on the exact runtime environment and the presence of the same model weights and input data.

## Known Limits

- external model weights are required and are not embedded into the repository
- transient artifacts may be cleaned automatically and are not a stable archival record
- some outputs are graphical derivatives, not raw numerical primitives
- local and production environments differ in database backend and security profile

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

CytoCV is reproducible when environment, model, input, and run configuration are treated as part of the result definition. The application already stores some of this context internally, but disciplined deployment and archival practice remain necessary for formal reproducibility.
