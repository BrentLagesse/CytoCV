# Windows Local Installer Design

## Purpose

This document explains the design and implementation of the rerunnable Windows local installer:

- [`../../scripts/local-install-windows.sh`](../../scripts/local-install-windows.sh)

It exists to make the standard local SQLite setup reproducible for native Windows development without turning the installer into a risky repair tool.

## Design Goals

The installer was built around these constraints:

- support native Windows development with Git Bash
- install the standard local SQLite workflow end to end
- be safe to rerun after partial progress or failure
- use real environment checks instead of trusting checkpoints blindly
- preserve existing local secrets and provider credentials in `.env`
- stop on risky failures instead of mutating tracked files automatically

This means the installer is intentionally conservative. It automates the common path aggressively, but it does not attempt to repair migration history or rewrite repo-tracked Django migration files.

## Scope

Current scope:

- native Windows checkout only
- Git Bash only
- exact Python `3.11.5`
- local SQLite setup only
- automatic model-weight download
- Django migration and system-check validation
- basic runtime validation for `cv2` and `tensorflow`

Current non-goals:

- WSL support
- Linux/macOS support
- local PostgreSQL installation or provisioning
- automatic migration recovery when the repository migration graph is broken
- automatic server startup after install

## Why Git Bash

Git Bash was chosen because it matches the existing Windows-native development posture in this repository while still allowing a single Bash entrypoint.

The script rejects:

- WSL
- generic Linux shells
- non-Git-Bash environments without `cygpath`

That decision keeps path handling predictable for:

- spaces in Windows paths
- `winget.exe`
- `py.exe`
- the venv under `cyto_cv/`

## Why the Installer Is "Smart"

The rerun model is state-aware, but state files are not the source of truth.

The installer uses actual checks before each step:

- Python:
  - validate that exact `3.11.5` is available
- Virtual environment:
  - validate that `cyto_cv/Scripts/python.exe` exists and reports `3.11.5`
- Dependencies:
  - compare a stored `requirements.txt` hash
  - run `pip check`
- `.env`:
  - detect whether the file exists
  - patch only missing keys
  - stop on conflicting local-mode values
- Weights:
  - validate that `cytocv/core/weights/deepretina_final.h5` exists and is large enough
- Django:
  - rerun `python manage.py migrate`
  - rerun `python manage.py check`

The state directory `.cytocv-local-install/` is used for:

- `install.log`
- `summary.txt`
- `requirements.sha256`

Those files improve observability, but they do not override live validation.

## Step-By-Step Implementation

### 1. Shell and platform gating

The script verifies:

- `uname -s` starts with `MINGW` or `MSYS`
- `WSL_DISTRO_NAME` is not set
- `cygpath` is available

This prevents subtle differences between Git Bash and WSL from leaking into the installer logic.

### 2. Python bootstrapping

The installer requires exact Python `3.11.5`.

Lookup order:

- `py.exe -3.11`
- `python.exe`

If neither yields exact `3.11.5`, the script attempts:

```bash
winget.exe install --id Python.Python.3.11 --version 3.11.5 --exact
```

After bootstrapping, it validates the version again. If the environment still does not expose exact `3.11.5`, the script stops.

This strict version gate aligns with the project's existing documentation and avoids silently drifting onto `3.12.x` or an arbitrary `3.11.x` patch release.

### 3. Virtual environment management

The installer creates:

```text
cyto_cv/
```

It does not activate the environment internally. Instead, it calls:

- `cyto_cv/Scripts/python.exe`
- `cyto_cv/Scripts/pip.exe`

That avoids shell-state bugs and makes the script easier to rerun reliably.

If `cyto_cv/` already exists but is not using Python `3.11.5`, the installer stops and asks for manual cleanup.

### 4. Dependency installation

Dependency installation is skipped only when:

- the venv exists
- the stored `requirements.txt` hash matches
- `pip check` passes

Otherwise the installer reruns:

```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt --no-cache-dir
```

This design avoids a false "already installed" result when the environment is partially broken.

### 5. `.env` handling

The installer creates `.env` from `.env.example` if it is missing.

If `.env` already exists:

- missing local-safe keys are appended
- existing values are preserved
- conflicting local-mode values stop the script

Conflicts currently treated as hard stops:

- `CYTOCV_DB_BACKEND` is present and not `sqlite`
- `CYTOCV_DEBUG` is present and not `1`

This prevents the installer from silently converting an intentionally different environment.

### 6. Weights handling

The runtime expects the model weights at:

```text
cytocv/core/weights/deepretina_final.h5
```

The installer validates that exact path, not `core/mrcnn/weights/`.

If the file is missing or clearly incomplete, the installer:

- installs `gdown` into the venv if needed
- downloads the weights automatically from the current Google Drive source

The validation is intentionally simple and practical: it checks existence plus a minimum file size threshold.

### 7. Django setup

The installer always runs:

```bash
cd cytocv
python manage.py migrate
python manage.py check
```

This is safe because `migrate` is idempotent for successful states and catches broken states early.

If migrations fail, the installer prints the documented manual recovery path and exits.

It does not automatically:

- delete migration files
- regenerate migrations
- rewrite tracked repository state

That boundary is deliberate because the repository has known migration-history sensitivity.

### 8. Runtime validation

At the end, the installer performs a light import test:

```bash
python -c "import cv2, tensorflow as tf; ..."
```

This catches the most common "setup succeeded but runtime is still broken" cases before the user starts the dev server manually.

## Failure Philosophy

The installer is intentionally opinionated about what it should and should not repair.

It will repair:

- missing Python `3.11.5` via `winget`
- missing venv
- missing dependencies
- missing `.env`
- missing local-safe `.env` keys
- missing weights

It will not repair automatically:

- a conflicting existing `.env`
- a wrong-version existing venv
- broken Django migration history
- non-Windows or WSL shell/runtime mismatches

The rule is:

- recover automatically when the fix is local, reversible, and unambiguous
- stop when the fix would mutate tracked project state or override user intent

## Repo Integration

Supporting repo changes for this installer:

- `.gitignore` now ignores:
  - `cyto_cv/`
  - `.cytocv-local-install/`
- local setup docs now include the installer

This keeps the installer's artifacts out of normal Git status noise.

## Extension Points

Reasonable future extensions:

- optional local PostgreSQL mode that assumes Postgres is already installed
- an optional `--start-server` flag after validation
- a companion PowerShell entrypoint that delegates into the Bash installer
- richer validation for weights integrity
- structured JSON summary output for automation

Deliberately postponed:

- automatic Postgres installation on Windows
- automatic migration recovery
- cross-platform unification into one installer script

## Related Documents

- [`local-installation-and-troubleshooting.md`](local-installation-and-troubleshooting.md)
- [`contributing.md`](contributing.md)
- [`../ops/postgres-setup.md`](../ops/postgres-setup.md)
- [`../vm-deployment-guide/README.md`](../vm-deployment-guide/README.md)
