# CytoCV

CytoCV is a Django-based analysis platform for DeltaVision (`.dv`) fluorescent microscopy stacks of mitotic yeast cells. The system ingests four-channel image sets, performs preprocessing and Mask R-CNN-based segmentation, computes per-cell measurements, and presents results through a web interface for review and export.

> **Version:** 1.0  
> **Python:** 3.11.5  
> **Database:** PostgreSQL in production; SQLite for local development only  
> **Platform:** Windows native development and Linux-compatible deployment

## Table of Contents

- [Overview](#overview)
- [System Scope](#system-scope)
- [Quick Start](#quick-start)
- [Documentation Map](#documentation-map)
- [Deployment](#deployment)
- [Runtime Requirements](#runtime-requirements)
- [Security Notes](#security-notes)
- [License](#license)

## Overview

CytoCV supports microscopy workflows built around these channels:

- `DIC`
- `DAPI`
- `mCherry`
- `GFP`

At a high level, the platform provides:

- upload-time validation and preview generation for DeltaVision files
- preprocessing artifacts and segmentation masks per run
- per-cell crops, overlays, and derived measurements
- database-backed review and export workflows through the web UI

## System Scope

CytoCV is intended for research workflows in which a DeltaVision stack contains one structural image channel and three fluorescence channels. The application coordinates:

- ingestion of four-layer DeltaVision image sets
- channel interpretation and preprocessing
- machine-learning-driven cell segmentation
- downstream per-cell analysis and export

The primary scientific workflow is documented in:

- [docs/user/workflow-guide.md](docs/user/workflow-guide.md)
- [docs/research/methods-and-system-description.md](docs/research/methods-and-system-description.md)

## Quick Start

The root README is intentionally concise. For detailed environment and deployment instructions, use the documentation linked below.

Local development quick start:

1. Clone the repository.
2. Create and activate a Python `3.11.5` virtual environment.
3. Install `requirements.txt`.
4. Copy `.env.example` to `.env`.
5. Set `CYTOCV_DB_BACKEND=sqlite` for local development.
6. Download the required Mask R-CNN weights file into `cytocv/core/weights/`.
7. From `cytocv/`, run migrations and start the server.

Typical local commands:

```bash
git clone https://github.com/BrentLagesse/CytoCV.git
cd CytoCV
python -m venv cyto_cv
source cyto_cv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt --no-cache-dir
cp .env.example .env
cd cytocv
python manage.py migrate
python manage.py runserver
```

For production or VM deployment, do not rely on the quick start above. Use the dedicated deployment documentation.

## Documentation Map

The canonical documentation home is [docs/README.md](docs/README.md).

Primary entry points:

- User documentation: [docs/user/getting-started.md](docs/user/getting-started.md)
- Developer architecture: [docs/developer/architecture-overview.md](docs/developer/architecture-overview.md)
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

The VM-specific documents are especially important if you are deploying to infrastructure similar to the UWB VM used during the March 2026 rollout.

## Runtime Requirements

The following requirements are operationally significant:

- Python must remain at `3.11.5` unless the scientific stack is revalidated.
- Production should use PostgreSQL, not SQLite.
- The Mask R-CNN workflow requires the `deepretina_final.h5` weights file under `cytocv/core/weights/`.
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
