# Local Installation And Troubleshooting

## Purpose

This guide is the in-depth local installation reference for running CytoCV from a fresh checkout. It covers the intended local setup path and the most common local errors that appear during installation, startup, migration, and the first analysis run.

This document is for local development and local validation. For VM/server deployment, use:

- [`../vm-deployment-guide/README.md`](../vm-deployment-guide/README.md)
- [`../ops/deployment-guide.md`](../ops/deployment-guide.md)

## Recommended Local Shape

Use this as the default local configuration:

- Python `3.11.5`
- project-specific virtual environment
- SQLite backend
- `.env` copied from `.env.example`
- Mask R-CNN weights file under `cytocv/core/weights/deepretina_final.h5`
- run commands from `cytocv/` when using `manage.py`

SQLite is the intended local-development database. PostgreSQL should be treated as an explicit local validation path, not the default local setup.

## Smart Windows Installer

For native Windows development, the repo now includes a rerunnable Git Bash installer:

```bash
bash scripts/local-install-windows.sh
```

What it does:

- requires Git Bash on a native Windows checkout
- checks for exact Python `3.11.5`
- bootstraps Python `3.11.5` with `winget` if it is missing
- creates `cyto_cv/` only if a valid `3.11.5` environment is not already present
- installs dependencies only when the venv or `requirements.txt` state requires it
- creates `.env` if missing and patches only missing local-safe keys
- auto-downloads `cytocv/core/weights/deepretina_final.h5` if needed
- runs `python manage.py migrate` and `python manage.py check`
- validates `cv2` and `tensorflow` imports at the end

What it does not do:

- it does not support WSL
- it does not configure local PostgreSQL in v1
- it does not auto-repair tracked migration files if Django migrations fail

Installer state:

- rerun-safe logs and step summaries are written under `.cytocv-local-install/`
- reruns use real checks instead of trusting checkpoints blindly
- steps are skipped only when the current environment still validates

If the script stops on a migration failure, fix the issue manually using the documented recovery path in this guide and then rerun the same installer command.

## Fresh Local Install

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv cyto_cv
.\cyto_cv\Scripts\Activate.ps1
python --version
```

Linux shell:

```bash
python3.11 -m venv cyto_cv
source cyto_cv/bin/activate
python --version
```

Expected result:

```text
Python 3.11.5
```

If your default interpreter is not `3.11.5`, stop and fix that first.

Windows Git Bash shortcut:

```bash
bash scripts/local-install-windows.sh
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt --no-cache-dir
```

On Linux, seeing this line is expected:

```text
Ignoring tensorflow-intel: markers 'sys_platform == "win32"' don't match your environment
```

### 3. Create `.env`

Copy `.env.example` to `.env` in the repository root.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux shell:

```bash
cp .env.example .env
```

For a standard local install, make sure at least these values are set:

```env
CYTOCV_SECRET_KEY=change-me-local
CYTOCV_DEBUG=1
CYTOCV_ALLOWED_HOSTS=localhost,127.0.0.1
CYTOCV_DB_BACKEND=sqlite
CYTOCV_ACCOUNT_EMAIL_VERIFICATION=none
CYTOCV_RECAPTCHA_ENABLED=0
```

Local notes:

- keep `CYTOCV_DB_BACKEND=sqlite` unless you are intentionally validating PostgreSQL
- keep auth-provider credentials blank unless you are actively testing OAuth
- keep reCAPTCHA disabled locally unless you are intentionally testing that flow

### 4. Add the required weights file

The current runtime expects the Mask R-CNN weights file here:

```text
cytocv/core/weights/deepretina_final.h5
```

Do not rely on `cytocv/core/mrcnn/weights/` alone. The active inference runtime resolves the weights from `cytocv/core/weights/`.

If `gdown` is not installed yet:

```bash
python -m pip install gdown
```

Then download the file:

```bash
gdown --fuzzy "https://drive.google.com/file/d/1moUKvWFYQoWg0z63F0JcSd3WaEPa4UY7/view?usp=sharing" -O ./cytocv/core/weights/deepretina_final.h5
```

Verify:

```bash
python -c "from pathlib import Path; print(Path('cytocv/core/weights/deepretina_final.h5').resolve())"
```

### 5. Run migrations

Change into the Django project directory first:

Windows PowerShell:

```powershell
cd .\cytocv
```

Linux shell:

```bash
cd ./cytocv
```

Then try the normal path:

```bash
python manage.py migrate
python manage.py check
```

### 6. Start the local server

```bash
python manage.py runserver
```

Open:

```text
http://localhost:8000/
```

## Optional: Local PostgreSQL Validation

Only use this if you are intentionally validating production-like database behavior.

When using PostgreSQL locally:

- set `CYTOCV_DB_BACKEND=postgres`
- fill in `CYTOCV_DB_NAME`, `CYTOCV_DB_USER`, `CYTOCV_DB_PASSWORD`, `CYTOCV_DB_HOST`, and `CYTOCV_DB_PORT`
- use the setup in [`../ops/postgres-setup.md`](../ops/postgres-setup.md)

If you are not specifically testing PostgreSQL, use SQLite locally instead.

## Most Common Local Errors

### 1. Wrong Python Version

Symptom:

```text
Python 3.12.x
```

or imports/builds behave unexpectedly.

Cause:

- CytoCV is pinned to Python `3.11.5`

Fix:

- recreate the venv with Python `3.11.5`
- do not continue on `3.12`

### 2. `CYTOCV_DB_BACKEND is required`

Symptom:

```text
CYTOCV_DB_BACKEND is required and must be set to 'sqlite' or 'postgres'
```

Cause:

- `.env` is missing or does not define `CYTOCV_DB_BACKEND`

Fix:

```env
CYTOCV_DB_BACKEND=sqlite
```

for standard local development.

### 3. `SQLite is not allowed when CYTOCV_DEBUG=0`

Symptom:

```text
Set CYTOCV_DB_BACKEND=postgres for production.
```

Cause:

- local `.env` is using `CYTOCV_DEBUG=0` with SQLite

Fix:

- use `CYTOCV_DEBUG=1` locally, or
- switch fully to PostgreSQL if you need production-like mode

### 4. Missing Weights File

Symptom:

```text
FileNotFoundError: Mask R-CNN weights file not found: .../cytocv/core/weights/deepretina_final.h5
```

Cause:

- weights file is missing
- file was placed only under `core/mrcnn/weights/`

Fix:

- put the file at `cytocv/core/weights/deepretina_final.h5`

### 5. Migration Chain Problems

Symptoms:

```text
App 'accounts' does not have migrations.
App 'core' does not have migrations.
```

or:

```text
NodeNotFoundError: Migration core.0007_uploadedimage_scale_info dependencies reference nonexistent parent node
```

Cause:

- the repository migration tracking is currently incomplete

Local recovery path:

```bash
cd ..
rm -f cytocv/accounts/migrations/0001_initial.py
rm -f cytocv/core/migrations/0001_initial.py
rm -f cytocv/core/migrations/0007_uploadedimage_scale_info.py
cd cytocv
python manage.py makemigrations accounts core
python manage.py migrate
python manage.py check
```

Important:

- this is a local recovery workaround
- it does not fix the underlying repository migration-tracking problem
- the smart Windows installer intentionally stops here and asks you to resolve this manually before rerunning it

### 6. `no such table: accounts_customuser`

Symptom:

```text
sqlite3.OperationalError: no such table: accounts_customuser
```

or the PostgreSQL equivalent.

Cause:

- migrations have not been applied cleanly

Fix:

- rerun `python manage.py migrate`
- if the migration graph is broken, use the migration recovery path above

### 7. `ImportError: libGL.so.1`

This is primarily a Linux local-development issue.

Symptom:

```text
ImportError: libGL.so.1: cannot open shared object file: No such file or directory
```

Cause:

- OpenCV runtime library is missing

Fix on Ubuntu/Debian:

```bash
sudo apt install -y libgl1 libglib2.0-0
```

### 8. `ModuleNotFoundError: No module named 'core.cell_analysis.analysis'`

This is a Linux case-sensitivity issue.

Cause:

- imports expect `analysis.py`
- the file is named `Analysis.py`

Fix:

- ensure the file is named:

```text
cytocv/core/cell_analysis/analysis.py
```

Windows can mask this problem. Linux will not.

### 9. `Requested setting AUTH_USER_MODEL, but settings are not configured`

Symptom:

```text
django.core.exceptions.ImproperlyConfigured: Requested setting AUTH_USER_MODEL, but settings are not configured.
```

Cause:

- Django-dependent imports are being run from a plain `python -c ...` command outside the Django context

Fix:

- run those checks through `manage.py shell -c ...`
- and run them from the `cytocv/` directory

Example:

```bash
cd cytocv
python manage.py shell -c "from core.mrcnn.inference_runtime import get_inference_runtime; print(get_inference_runtime())"
```

## First Analysis Validation

After the site boots, validate the actual analysis path, not just the homepage.

Recommended quick check:

1. open `http://localhost:8000/`
2. upload one known-good `.dv` file
3. preprocess the file
4. run analysis
5. confirm the display page shows:
   - segmented cells
   - `mask.tif`
   - statistics or expected empty-state behavior

If the browser appears to reload or stall during analysis, inspect the server-side error immediately in the same terminal where `runserver` is active.

## Local Verification Checklist

Use this checklist after a fresh local install:

```bash
python --version
cd cytocv
python manage.py migrate
python manage.py check
python manage.py runserver
```

Then verify:

- homepage loads
- sign-in page loads
- experiment page loads after login
- one local `.dv` test file can reach preprocess
- the weights file is found and inference can start

For Windows Git Bash users, the installer can be rerun after any resolved error:

```bash
bash scripts/local-install-windows.sh
```

## Related Documents

- [`contributing.md`](contributing.md)
- [`windows-local-installer-design.md`](windows-local-installer-design.md)
- [`testing-guide.md`](testing-guide.md)
- [`../user/getting-started.md`](../user/getting-started.md)
- [`../user/troubleshooting.md`](../user/troubleshooting.md)
- [`../ops/postgres-setup.md`](../ops/postgres-setup.md)
