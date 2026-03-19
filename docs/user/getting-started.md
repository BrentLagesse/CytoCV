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

## Supported Input Expectations

CytoCV expects DeltaVision files that can be interpreted as a four-layer imaging stack. The active workflow assumes these channels are available and can be mapped correctly:

- `DIC`
- `DAPI`
- `mCherry`
- `GFP`

Validation behavior depends on the upload settings and saved workflow defaults. The validation module can enforce:

- exact layer count
- required wavelength presence
- plugin-driven required channels
- manually required channels

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
3. Choose the desired analysis plugins.
4. Confirm channel requirements and scale settings.
5. Continue to preprocessing.
6. Review previews and per-file detected channel order.
7. Run preprocessing and inference.
8. Continue to segmentation and statistics.
9. Open the display view and verify:
   - the main outlined frame loads
   - cell crops exist
   - the statistics table is populated when cells were found

## Expected Outputs

After a successful run, CytoCV should produce:

- preview images for the uploaded stack
- `channel_config.json` for the run
- preprocessed and inference outputs under the run media directory
- `mask.tif`
- outlined output frames
- segmented cell crops
- per-cell debug overlays for fluorescence channels
- `SegmentedImage` and `CellStatistics` database rows

## Common Errors

- `CYTOCV_DB_BACKEND is required`
  Your `.env` file is missing a required database backend selector.
- `SQLite is not allowed when CYTOCV_DEBUG=0`
  Production-like mode requires PostgreSQL.
- invalid or missing channels during upload
  The file does not satisfy the selected validation rules or selected plugin requirements.
- missing weights file
  The ML inference path cannot run until the expected weights are present.

## Related Documents

- [`workflow-guide.md`](workflow-guide.md)
- [`analysis-options.md`](analysis-options.md)
- [`troubleshooting.md`](troubleshooting.md)
- [`../ops/deployment-guide.md`](../ops/deployment-guide.md)
