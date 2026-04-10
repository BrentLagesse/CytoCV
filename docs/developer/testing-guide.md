# Testing Guide

## Purpose

This document explains the current automated test surface and the expected validation workflow for code changes.

## Test Location

The active test suite is under `cytocv/core/tests/`.

Current test modules:

- `test_accounts_preferences.py`
- `test_artifact_storage.py`
- `test_core_app.py`
- `test_mrcnn_inference.py`
- `test_nuclear_cell_pair_intensity.py`
- `test_scale_upload_initialization.py`
- `test_stats_cache.py`
- `test_stats_validation.py`
- `test_tables.py`
- `test_upload_length_scale.py`

## What The Tests Cover

- normalization and persistence of account preferences
- artifact storage cleanup and quota behavior
- inference-path behavior
- table rendering and export support
- scale initialization and upload-time scale handling
- plugin and stats validation behavior

## Standard Validation Workflow

From `cytocv/`:

```powershell
python manage.py test
```

When working on a narrower area, run the relevant subset first and then rerun the full suite before finalizing.

## High-Risk Areas Requiring Extra Manual Review

- upload validation rules
- scale conversion and metadata fallback behavior
- save versus transient ownership transitions
- display serialization for new statistics fields
- auth and account flows with reCAPTCHA or provider login enabled

## Documentation Validation

For documentation changes, verify:

- every link in `README.md` and `docs/README.md`
- route names and endpoint semantics against current code
- environment variables against `settings.py` and `.env.example`
- diagram file names against the actual diagram catalog

## Related Documents

- [`contributing.md`](contributing.md)
- [`../ops/environment-reference.md`](../ops/environment-reference.md)

