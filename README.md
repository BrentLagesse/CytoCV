# CytoCV

CytoCV is a Django-based analysis platform for DeltaVision (`.dv`) and stack TIFF (`.tif`, `.tiff`) microscopy files of yeast cells. The application supports four logical channel roles (`DIC`, `Blue`, `Red`, and `Green`), but only `DIC` is universally required. Additional channels are enforced by the selected statistics plugins and, when enabled, the upload validation module.

> **Version:** 2.0.0
>
> **Hosted application:** https://cytocv.uwb.edu/
>
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
- [Historical Notes](#historical-notes)
- [Citation](#citation)
- [License](#license)

## Overview

CytoCV combines:

- upload-time DV/TIFF validation and preview generation
- Mask R-CNN-driven segmentation built around the `DIC` structural channel
- plugin-based per-cell quantification
- database-backed review, retention, and export workflows

CytoCV exposes two primary Signal Quantification modes:

- `PunctaDistance` (`Puncta Distance`), which is the default primary mode.
- `NuclearCellPairIntensity` (`Nuclear, Cell-Pair Intensity`), which is a
  fully supported selectable primary mode.

The default puncta-oriented plugin selection also includes:

- `CENDot`
- `Biorientation`
- `GreenRedIntensity`

Mode selection determines which measurements and controls are active.
Selecting `NuclearCellPairIntensity` activates the nuclear/cell-pair intensity
workflow and its nucleus-contour configuration controls.

The current default puncta-oriented selection requires `DIC`, `Red`, and
`Green`. The nuclear/cell-pair workflow also uses the channels required by its
configured contour and measurement modes. `Blue` remains supported for
backward-compatible measurements and optional full-wavelength validation.
These outputs are software-generated measurements intended to support review and downstream research analysis. They should not be treated as final biological conclusions on their own.

## System Scope

CytoCV is intended for research workflows built around yeast-cell microscopy stacks. The application can process anything from a DIC-only structural run to a full four-role stack, depending on the selected plugin set and validation policy. In the current implementation, the platform coordinates:

- DV/TIFF ingestion and configurable validation
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

On native Windows with Git Bash, you can use the rerunnable local installer:

```bash
bash scripts/local-install-windows.sh
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

Start the background worker in a second terminal when `CYTOCV_ANALYSIS_EXECUTION_MODE=worker`:

```bash
python manage.py run_analysis_worker --poll-interval 1
```

In worker mode, the worker prepares staged uploads by validating DV files, extracting metadata, writing channel config, and generating previews. It also runs Start Analysis jobs.

For production or VM deployment, use the dedicated operational documentation instead of the local workflow above.

## Documentation Map

The canonical documentation home is [docs/README.md](docs/README.md).

Primary entry points:

- User documentation: [docs/user/getting-started.md](docs/user/getting-started.md)
- Developer architecture: [docs/developer/architecture-overview.md](docs/developer/architecture-overview.md)
- Local installation and troubleshooting: [docs/developer/local-installation-and-troubleshooting.md](docs/developer/local-installation-and-troubleshooting.md)
- Windows installer design: [docs/developer/windows-local-installer-design.md](docs/developer/windows-local-installer-design.md)
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
- Example `systemd` units: [deploy/systemd/README.md](deploy/systemd/README.md)
- Sanitized VM deployment guide: [docs/vm-deployment-guide/README.md](docs/vm-deployment-guide/README.md)
- Historical first VM deployment record: [docs/vm-deployment-record/README.md](docs/vm-deployment-record/README.md)
- Historical replacement VM deployment record: [docs/vm-deployment-record-cytocv2/README.md](docs/vm-deployment-record-cytocv2/README.md)
- Historical cytocv2 maintenance refresh record: [docs/vm-deployment-record-cytocv2-2026-04-maintenance/README.md](docs/vm-deployment-record-cytocv2-2026-04-maintenance/README.md)
- Historical cytocv2 code refresh record: [docs/vm-deployment-record-cytocv2-2026-05-code-refresh/README.md](docs/vm-deployment-record-cytocv2-2026-05-code-refresh/README.md)

The VM-specific documents are retained as sanitized historical maintainer notes. Use the core operations docs above as the current source of truth for active deployments.

## Runtime Requirements

The following requirements are operationally significant:

- Python must remain at `3.11.5` unless the scientific stack is revalidated.
- Production should use PostgreSQL, not SQLite.
- Production should run `run_analysis_worker` as a supervised process when `CYTOCV_ANALYSIS_EXECUTION_MODE=worker`.
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

## Historical Notes

This tool derived from the python application found at https://github.com/BrentLagesse/YeastAnalysisTool.  That tool is no longer maintained, but is still available for historical development purposes.

## Citation

The current CytoCV v2.0.0 software record is identified by:

**DOI:** [10.5281/zenodo.21988218](https://doi.org/10.5281/zenodo.21988218)

Citation metadata are also provided in
[`CITATION.cff`](CITATION.cff).

When reporting analyses, cite the exact CytoCV version used. Later releases may
change interfaces, dependencies, outputs, or scientific workflow behavior and
should be cited separately.

## License

CytoCV is free and open-source software licensed under the **GNU Affero General Public License v3.0 or later** (`AGPL-3.0-or-later`).

Commercial use, paid hosting, consulting, support, modification, and redistribution are permitted, subject to the license terms. If a covered modified version is distributed or made available for users to interact with over a network, the corresponding source must be offered as required by the AGPL.

See [LICENSE](LICENSE) for the complete legal terms and [docs/license/README.md](docs/license/README.md) for a plain-language compliance summary. The full legal text controls over the summary.

Third-party dependencies, model weights, datasets, and assets remain governed by their respective licenses.

University of Washington names, logos, and marks are addressed separately in [TRADEMARKS.md](TRADEMARKS.md).
