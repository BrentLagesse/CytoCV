# Getting Started

## Purpose

This guide explains how to reach the first successful CytoCV run from a fresh local checkout.

## Prerequisites

- Windows PowerShell or a Linux shell
- Python `3.11.5`
- a virtual environment for this project
- the project dependencies from `requirements.txt`
- a configured `.env` file at the repository root
- the required Mask R-CNN weights file under `cytocv/core/weights`
- at least one supported DeltaVision `.dv` file

## Supported Input Model

CytoCV supports four logical channel roles:

- `DIC`
- `DAPI`
- `mCherry`
- `GFP`

Only `DIC` is universally required because the segmentation and CNN preprocessing path depends on it. Additional channels are conditional:

- the default modern plugin set requires `mCherry` and `GFP` in addition to `DIC`
- legacy DAPI plugins require `DAPI`
- manual required channels are added only when the validation module is enabled
- exact four-layer enforcement occurs only when `enforce_layer_count` is enabled
- all-four-role enforcement occurs only when `enforce_wavelengths` is enabled

## Local Startup Procedure

1. Create `.env` from `.env.example`.
2. Set `CYTOCV_DB_BACKEND=sqlite` for local development unless you are intentionally testing PostgreSQL.
3. Activate the project virtual environment.
4. Change into the Django project directory:

```powershell
cd .\cytocv
```

5. Apply migrations:

```powershell
python manage.py migrate
```

6. Start the development server:

```powershell
python manage.py runserver
```

7. Open the local site and sign in or create an account.

## First Successful Run

1. Open the `Experiment` page.
2. Upload one or more `.dv` files.
3. Leave the default modern plugins enabled unless you are intentionally testing a legacy DAPI workflow.
4. Confirm that the file provides `DIC` plus any channels required by the selected plugin set.
5. Review scale settings and, if needed, advanced validation toggles.
6. Continue to preprocessing.
7. Review previews and per-file detected channel order.
8. Run preprocessing and inference.
9. Continue to segmentation and statistics.
10. Open the display view and verify that the outlined frame, cell crops, and statistics table load as expected.

## Expected Outputs

After a successful run, CytoCV should produce:

- preview images for the uploaded stack
- `channel_config.json` for the run
- preprocessed and inference outputs under the run media directory
- `mask.tif`
- outlined output frames
- segmented cell crops
- plugin-dependent debug overlays
- `SegmentedImage` and `CellStatistics` database rows

## Common Errors

- `CYTOCV_DB_BACKEND is required`
  Your `.env` file is missing a required database backend selector.
- `SQLite is not allowed when CYTOCV_DEBUG=0`
  Production-like mode requires PostgreSQL.
- invalid or missing channels during upload
  The file does not satisfy the selected plugin requirements or enabled validation rules.
- missing weights file
  The ML inference path cannot run until the expected weights are present.

## Related Documents

- [`../developer/local-installation-and-troubleshooting.md`](../developer/local-installation-and-troubleshooting.md)
- [`workflow-guide.md`](workflow-guide.md)
- [`analysis-options.md`](analysis-options.md)
- [`troubleshooting.md`](troubleshooting.md)
- [`../ops/deployment-guide.md`](../ops/deployment-guide.md)
