# CytoCV

CytoCV is a Django-based analysis platform for DeltaVision (`.dv`) microscopy stacks of mitotic yeast cells. The application supports four logical channel roles (`DIC`, `DAPI`, `mCherry`, and `GFP`), but only `DIC` is universally required. Additional channels are enforced by the selected statistics plugins and, when enabled, the upload validation module.

> **Version:** 1.0  
> **Python:** 3.11.5  
> **Database:** PostgreSQL in production; SQLite for local development only  
> **Platform:** Windows-native development and Linux-compatible deployment

## Table of Contents

- [Overview](#overview)
- [System Scope](#system-scope)
- [Local Installation](#local-installation)
- [Documentation Map](#documentation-map)
- [Deployment](#deployment)
- [Runtime Requirements](#runtime-requirements)
- [Security Notes](#security-notes)
- [License](#license)

## Overview

CytoCV combines:

- upload-time DeltaVision validation and preview generation
- Mask R-CNN-driven segmentation built around the `DIC` structural channel
- plugin-based per-cell quantification
- database-backed review, retention, and export workflows

The code-defined default modern workflow enables these plugins:

- `MCherryLine`
- `GFPDot`
- `GreenRedIntensity`
- `NuclearCellularIntensity`

That default set requires `DIC`, `mCherry`, and `GFP`. `DAPI` remains supported for legacy measurements and for optional full-wavelength validation.

## System Scope

CytoCV is intended for research workflows built around DeltaVision microscopy of mitotic yeast cells. The application can process anything from a DIC-only structural run to a full four-role stack, depending on the selected plugin set and validation policy. In the current implementation, the platform coordinates:

- DeltaVision ingestion and configurable validation
- channel interpretation and preview generation
- machine-learning-driven cell segmentation
- plugin-scoped downstream measurements
- result review, export, and retention

The primary scientific workflow is documented in:

- [docs/user/workflow-guide.md](docs/user/workflow-guide.md)
- [docs/research/methods-and-system-description.md](docs/research/methods-and-system-description.md)

## Local Installation

The root README is intentionally concise, but the local installation path should remain explicit.

### 1. Clone the Repository

```bash
git clone https://github.com/BrentLagesse/CytoCV.git
cd CytoCV
```

### 2. Create and Activate the Python Environment

CytoCV expects Python `3.11.5`.

Create the virtual environment:

```bash
python -m venv cyto_cv
```

Activate it on macOS or Linux:

```bash
source cyto_cv/bin/activate
```

Activate it on Windows PowerShell:

```powershell
.\cyto_cv\Scripts\Activate.ps1
```

Upgrade the base packaging tools:

```bash
python -m pip install --upgrade pip setuptools wheel
```

### 3. Install Project Requirements

Install the pinned Python dependencies:

```bash
python -m pip install -r requirements.txt --no-cache-dir
```

### 4. Create the Local Environment File

Copy the example configuration:

```bash
cp .env.example .env
```

For Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` and confirm the local database backend is SQLite:

```env
CYTOCV_DB_BACKEND=sqlite
```

### 5. Download the Required Model Weights

Place the Mask R-CNN weights file at:

```text
cytocv/core/weights/deepretina_final.h5
```

The weights file is required for preprocessing and inference.

### 6. Apply Database Migrations

Move into the Django project directory:

```bash
cd cytocv
```

Apply the database schema:

```bash
python manage.py migrate
```

### 7. Start the Local Development Server

Run the application:

```bash
python manage.py runserver
```

The default local URL is:

```text
http://127.0.0.1:8000/
```

For production or VM deployment, use the dedicated operational documentation instead of the local workflow above.

## Documentation Map

The canonical documentation home is [docs/README.md](docs/README.md).

Primary entry points:

- User documentation: [docs/user/getting-started.md](docs/user/getting-started.md)
- Developer architecture: [docs/developer/architecture-overview.md](docs/developer/architecture-overview.md)
- Local installation and troubleshooting: [docs/developer/local-installation-and-troubleshooting.md](docs/developer/local-installation-and-troubleshooting.md)
- Developer codebase map: [docs/developer/codebase-map.md](docs/developer/codebase-map.md)
- Operations deployment guide: [docs/ops/deployment-guide.md](docs/ops/deployment-guide.md)
- Operations environment reference: [docs/ops/environment-reference.md](docs/ops/environment-reference.md)
- Route and endpoint reference: [docs/reference/routes-and-endpoints.md](docs/reference/routes-and-endpoints.md)
- Diagram catalog: [docs/diagrams/README.md](docs/diagrams/README.md)

Research-oriented documents:

- [docs/research/methods-and-system-description.md](docs/research/methods-and-system-description.md)
- [docs/research/reproducibility-and-validation.md](docs/research/reproducibility-and-validation.md)
- [docs/research/figure-catalog.md](docs/research/figure-catalog.md)

## Deployment

For operational deployment material, use these documents:

- General deployment guide: [docs/ops/deployment-guide.md](docs/ops/deployment-guide.md)
- PostgreSQL setup: [docs/ops/postgres-setup.md](docs/ops/postgres-setup.md)
- March 2026 VM step-by-step guide: [docs/vm-deployment-guide/README.md](docs/vm-deployment-guide/README.md)
- March 2026 VM rollout record: [docs/vm-deployment-record/README.md](docs/vm-deployment-record/README.md)
- Replacement `cytocv2.uwb.edu` VM rollout record: [docs/vm-deployment-record-cytocv2/README.md](docs/vm-deployment-record-cytocv2/README.md)

The VM-specific documents are especially important for infrastructure similar to the UWB VM used during the March 2026 rollout.

## Runtime Requirements

The following requirements are operationally significant:

- Python must remain at `3.11.5` unless the scientific stack is revalidated.
- Production should use PostgreSQL, not SQLite.
- The Mask R-CNN workflow requires `deepretina_final.h5` under `cytocv/core/weights/`.
- TensorFlow-based analysis requires a CPU that exposes `AVX`. A server can host the web application without `AVX`, but the analysis pipeline will fail with `Illegal instruction` if the CPU does not support the required instruction set.

If you are deploying to a new VM, check CPU flags before treating the system as analysis-capable:

```bash
lscpu | grep -i avx
```

If that command returns nothing, review the AVX section in [docs/vm-deployment-guide/README.md](docs/vm-deployment-guide/README.md) before proceeding.

## Security Notes

For production use:

- set `CYTOCV_DEBUG=0`
- configure `CYTOCV_ALLOWED_HOSTS` explicitly
- keep secrets out of the repository and rotate exposed values
- use PostgreSQL with least-privileged credentials
- terminate traffic over HTTPS
- configure provider credentials and reCAPTCHA only for approved production domains
- enable mandatory email verification only after SMTP is configured correctly

Detailed operational guidance is documented in:

- [docs/ops/security-and-privacy.md](docs/ops/security-and-privacy.md)
- [docs/ops/environment-reference.md](docs/ops/environment-reference.md)

## License

CytoCV is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License (CC BY-NC-SA 4.0)**.

License reference:

- [docs/license/README.md](docs/license/README.md)
- <https://creativecommons.org/licenses/by-nc-sa/4.0/>
