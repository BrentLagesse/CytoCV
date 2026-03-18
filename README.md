# CytoCV
Automated analysis of **DeltaVision (DV)** fluorescent microscopy stacks of yeast cells in mitosis. Quantifies points of interest across **DIC, DAPI, mCherry, GFP** channels with a Django web UI and a ML segmentation workflow (Mask R-CNN).

> **Version:** 1.0  
> **Repo:** https://github.com/BrentLagesse/CytoCV  
> **Python:** **3.11.5** (exact)  
> **DB:** PostgreSQL in production; SQLite for local dev/test only  
> **OS:** Windows (native) / Linux (via Docker)


<details open>
<summary><h2>Table of Contents</h2></summary>
   
- [Overview](#overview)
- [Key features](#key-features)
- [Local deployment & installation](#local-deployment--installation)
  - [Environment setup](#environment-setup)
  - [Installing dependencies](#installing-dependencies)
  - [Migrations](#migrations)
  - [Launching project](#launching-project)
- [Configuration](#configuration)
- [Architecture](#architecture)
  - [Project layout](#project-layout)
- [Data & artifacts](#data--artifacts)
- [Workflow](#workflow)
  - [Uploading (UI & API)](#uploading-ui--api)
  - [Image processing](#image-processing)
  - [Outputs & schemas](#outputs--schemas)
- [HTTP routes](#http-routes)
- [Examples](#examples)
- [Testing](#testing)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [License](#license)


</details>

## Overview
The project is a tool to automatically analyze WIDE-fluorescent microscopy images of yeast cells undergoing mitosis. The biologist uses yeast cells that have a controlled mutation in them. The biologists then use fluorescent labeling to point of interest (POI) like a specific protein and this program automatically analyzes those POI to collect useful data that can maybe be used to find the cause of cellular mutation. The user will upload a special DV (Delta Vision) file that has multiple images that are taken at the same time; thus, allowing them to be overlapped. One of them is a Differential interference contrast (DIC) image, which basically is a clear image of the cells, and multiple images of the cells through different wavelengths which excite the fluorescent labels separately, leading to the POI being brightened (small dots). Currently, the fluorescent labels being used are DAPI, mcherry, and GFP.

| DIC | DAPI | mCherry | GFP |
|:--:|:--:|:--:|:--:|
| <img width="250" alt="DIC" src="https://github.com/user-attachments/assets/1830b15d-d0cf-4558-ba3f-7d45462e0a13" /> | <img width="250" alt="DAPI" src="https://github.com/user-attachments/assets/0b6dc954-ed78-4abf-b9c9-436ded7551fa" /> | <img width="250" alt="mCherry" src="https://github.com/user-attachments/assets/68767176-2aec-4634-9b74-de8c085e32a4" /> | <img width="250" alt="GFP" src="https://github.com/user-attachments/assets/67e9c4f4-f520-422e-9a0b-48fa9fd370c0" /> |

## Key features
- **DV ingestion** with strict validation (exactly 4 layers).
- **Previews** and channel mapping (writes `channel_config.json`).
- **Mask R-CNN inference** (CPU) with direct `mask.tif` output.
- **Segmentation** with Gaussian blur, Otsu, rolling-ball BG subtraction, region merges.
- **Per-cell metrics** stored in DB:
  - `distance` (mCherry dot distance)
  - `line_gfp_intensity` (sum along mCherry line)
  - `nucleus_intensity_sum`
  - `cellular_intensity_sum`
- **Web UI** to upload, preprocess, select analyses, display, and export tables.

## Local deployment & installation 
You need to make sure git, virtualenv, and python3 (currently using 3.11.5) are installed and are in the $PATH (you can type those command names on the commandline and your computer finds them).

1. Download the file "deepretina_final.h5" in the link below and place it in the weights directory under `cytocv/core/weights` (may need to create the folder manually):

   https://drive.google.com/file/d/1moUKvWFYQoWg0z63F0JcSd3WaEPa4UY7/view?usp=sharing


### Environment setup

1. Confirm Python is exactly 3.11.5; Python version  **NEEDS TO BE 3.11.5** or else it will not work:
   ```bash
   python --version

2. Clone the Github repository:
   ```bash
   git clone https://github.com/BrentLagesse/CytoCV.git

3. Navigate to the Directory:
   ```bash
   cd <repo-root>

4. Create virtual environment:
    ```bash
   python -m venv cyto_cv

5. Activate virtual environment:
   ```bash
   source cyto_cv/bin/activate
   ```
   or
   ```bash
   cyto_cv\Scripts\activate
   ```
6. Make sure pip exists in the virtual environment:
    ```bash
   python -m ensurepip --upgrade

7. Upgrade base tools:
    ```bash
   python -m pip install --upgrade pip setuptools wheel

8. Check that pip is from the virtual environment:
   ```bash
   python -m pip --version   # path should point into <repo-root>/cyto_cv


### Installing dependencies
Due to the machine learning part only works on certain versions of packages, we have to specifically use them. The easiest way do to do is to delete all your personal pip packages and reinstall them.


1. Export all personal packages into deleteRequirements.txt:
   ```bash
   pip freeze --all > deleteRequirements.txt

2. Uninstall all packages listed:
   ```bash
   pip uninstall -r deleteRequirements.txt
   
3. Install this repository's dependencies. If this fails, you may be using the wrong Python version or try deleting the line with pip in deleteRequirements.txt and trying again:
    ```bash
   pip install -r ./requirements.txt --no-cache-dir
   ```
   PostgreSQL support uses `psycopg` (psycopg3) only.
   `tensorflow-intel` is installed only on Windows; Linux uses `tensorflow`.

5. Remove the temporary list of requirements:
   ```bash
   del deleteRequirements.txt

### Migrations
You must have your virtual environment activated to make the respective migrations. Please refer to the previous steps under **Environment setup**.


1. Ensure your `.env` includes `CYTOCV_DB_BACKEND`:
   - Local dev quickstart: `CYTOCV_DB_BACKEND=sqlite`
   - VM/prod: `CYTOCV_DB_BACKEND=postgres` with PostgreSQL credentials
   - Detailed Postgres provisioning steps: see `POSTGRES_SETUP.md`

2. Optional SQLite reset (only if using `CYTOCV_DB_BACKEND=sqlite`):
   ```bash
   Remove-Item .\db.sqlite3 -Force
   ```

3. Create migrations for specific apps (accounts, core):
   ```bash
   cd cytocv
   python manage.py makemigrations accounts core
   ```

4. Apply migrations to build the schema:
   ```bash
   python manage.py migrate
   ```


## Launching project

1. Navigate to the project directory:
   ```bash
   cd <repo-root>/cytocv
   ```

2. Run the application:
   ```bash
   python manage.py runserver
   ```



## Configuration
Create a `.env` file in the repository root. `cytocv/cytocv/settings.py` loads this file automatically.

Database policy:
- Production backend: PostgreSQL
- Local development/testing convenience: SQLite
- Enforcement: SQLite is blocked when `CYTOCV_DEBUG=0`

Required core keys:
```bash
CYTOCV_SECRET_KEY=change-me
CYTOCV_DEBUG=1
CYTOCV_ALLOWED_HOSTS=localhost,127.0.0.1
CYTOCV_DB_BACKEND=sqlite
```

Database backend selection:
```bash
# Required selector (must be one of: sqlite, postgres)
CYTOCV_DB_BACKEND=sqlite
```
For full Postgres setup commands, see `POSTGRES_SETUP.md`.

Local development (SQLite, explicit):
```bash
CYTOCV_DB_BACKEND=sqlite
```

VM / production (PostgreSQL):
```bash
CYTOCV_DB_BACKEND=postgres
CYTOCV_DB_NAME=cytocv
CYTOCV_DB_USER=cytocv_user
CYTOCV_DB_PASSWORD=change-me
CYTOCV_DB_HOST=127.0.0.1
CYTOCV_DB_PORT=5432
CYTOCV_DB_CONN_MAX_AGE=60
CYTOCV_DB_ATOMIC_REQUESTS=0
CYTOCV_DB_SSLMODE=prefer
```
Driver policy:
- Use `psycopg` (psycopg3) only.

Fail-fast behavior:
- If `CYTOCV_DB_BACKEND` is missing or invalid, startup fails immediately.
- If `CYTOCV_DB_BACKEND=postgres` and required DB credentials are missing, startup fails immediately.
- If `CYTOCV_DEBUG=0` and `CYTOCV_DB_BACKEND=sqlite`, startup fails (SQLite is blocked in production mode).
- If `CYTOCV_DEBUG=0` and `CYTOCV_SECRET_KEY` is blank/default/placeholder, startup fails immediately.

OAuth / provider keys:
```bash
CYTOCV_GOOGLE_CLIENT_ID=
CYTOCV_GOOGLE_CLIENT_SECRET=
CYTOCV_MICROSOFT_CLIENT_ID=
CYTOCV_MICROSOFT_CLIENT_SECRET=
CYTOCV_MICROSOFT_TENANT=organizations
CYTOCV_MICROSOFT_LOGIN_URL=https://login.microsoftonline.com
```

Email keys:
```bash
CYTOCV_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
CYTOCV_EMAIL_HOST=smtp.gmail.com
CYTOCV_EMAIL_HOST_USER=
CYTOCV_EMAIL_HOST_PASSWORD=
CYTOCV_EMAIL_PORT=587
CYTOCV_EMAIL_USE_TLS=1
CYTOCV_EMAIL_USE_SSL=0
CYTOCV_EMAIL_TIMEOUT=
CYTOCV_ACCOUNT_EMAIL_VERIFICATION=optional
CYTOCV_DEFAULT_FROM_EMAIL=no-reply@noreply.x.edu
CYTOCV_EMAIL_REPLY_TO=no-reply@noreply.x.edu
```
Notes:
- `CYTOCV_EMAIL_USE_TLS` and `CYTOCV_EMAIL_USE_SSL` cannot both be `1`.
- Use `CYTOCV_ACCOUNT_EMAIL_VERIFICATION=mandatory` for stricter production policy.

Use `.env.example` as the template.



## Architecture
The server follows a layered architecture:

```
┌──────────────────────────────┐
│       Presentation/UI        │  Django templates and JS  
├──────────────────────────────┤
│     Web/Application Layer    │  Request handlers  
├──────────────────────────────┤
│    Domain/Service Layer      │  Scientific/processing modules
├──────────────────────────────┤
│  Data & Infrastructure Layer │  Django models 
└──────────────────────────────┘
```
**Flow**
- UI
- Views
- Processing services
- Models, database, and media



### Project Layout
```
<repo-root>/
├─ Dockerfile         # python:3.11.5-slim
├─ compose.yml
├─ start.sh           # run migrations, launch gunicorn
└─ cytocv/
   ├─ accounts/       # auth, profile, config UI
   ├─ core/           # upload, preprocess, convert, segment, display, stats
   │  ├─ image_processing/
   │  ├─ contour_processing/
   │  ├─ cell_analysis/
   │  └─ mrcnn/
   │     ├─ weights/deepretina_final.h5
   │     └─ my_inference.py
   ├─ templates/      # upload/preprocess/display pages
   └─ cytocv/       # settings, urls, wsgi, asgi
```

Entry points: `manage.py` (CLI), `cytocv/urls.py` (routes), `wsgi.py/asgi.py` (servers)


## Data & artifacts
- **Inputs**: DV `.dv` with **exactly** 4 layers (DIC + three fluorescence).
- **Storage**: `MEDIA_ROOT/<uuid>/<original>.dv` (UUID per upload).
- **Metadata**: `channel_config.json` (wavelengths/order).
- **Preprocessing**: `preprocessed_images/`, direct mask generation to `output/mask.tif`.
- **Segmentation**: per-cell PNGs in `segmented/`, outline CSVs, debug overlays.
- **DB**: `CellStatistics` rows for per-cell metrics.
- **Samples**: `example-dv-file/`.



## Workflow
1. **Upload** DV stack(s): `/image/upload/`  
2. **Preprocess** and choose analyses: `/image/preprocess/<uuids>/`  
3. **Inference** (Mask R-CNN) and direct `mask.tif` generation  
4. **Segmentation & analysis**: `/image/<uuids>/segment/`  
5. **Display & export**: `/image/<uuids>/display/`

Progress is tracked under `MEDIA_ROOT/progress/<hash>.json`.  
Caching can reuse artifacts when `use_cache=True`.



## Uploading (UI & API)

**UI**
- Drag/drop or folder input
- Duplicate suppression
- Client-side polling keyed by session

**Server**
- Requires minimum 1 file and rejects wrong layer counts with details
- UUID partitioning, original filenames preserved
- Heavy preprocessing happens after user confirms settings



## Image processing

**Channel mapping**
- Parse DV headers
- Write `channel_config.json`

**Preprocessing**
- Intensity rescale, RGB TIFF previews
- Write preprocessed PNG inputs for inference

**Mask R-CNN (CPU)**
- Min dim 512, anchors 8–128, confidence ≥ 0.9
- Weights: `core/mrcnn/weights/deepretina_final.h5`
- `CUDA_VISIBLE_DEVICES` disabled

**Mask output**
- Write `output/mask.tif` directly from predicted instance masks

**Segmentation**
- Gaussian blur + Canny/Otsu threshold
- Rolling-ball background subtraction
- Neighbor merges, plugin analyses

**Per-cell metrics (DB)**
- `distance`, `line_gfp_intensity`, `nucleus_intensity_sum`, `cellular_intensity_sum`



## Outputs & schemas

**Folder layout (per UUID)**
```
<MEDIA_ROOT>/<uuid>/
  original.dv
  channel_config.json
  preprocessed_images/
  segmented/
  output/
  progress/
```

**CSV schemas (typical)**
- Outline/metrics CSVs: `cell_id, x/y coords, area, intensity, distance, notes`

**Table export (UI)**
- `django-tables2` supports CSV/XLSX via `_export` query param.



## HTTP routes
- **Core**:  
  - `/image/upload/`  
  - `/image/preprocess/<uuids>/`  
  - `/image/<uuids>/segment/`  
  - `/image/<uuids>/display/`
- **Auth**: `/signin/`, `/signup/`, OAuth (Google/Microsoft) if configured.  
- Internal JSON endpoints are CSRF-protected. No versioned public REST API.



## Examples
### 1) UI Upload (UI, single/multi file)

**Start server**
```bash
python -m venv cyto_cv
# bash
source cyto_cv/bin/activate
# PowerShell alternative:
# .\cyto_cv\Scripts\Activate.ps1

python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt --no-cache-dir

cd cytocv
python manage.py makemigrations accounts core
python manage.py migrate
python manage.py runserver
```

**Process the sample**
1. Open http://localhost:8000/image/upload/
2. Upload `example-dv-file/M3850/M3850_001_PRJ.dv`
3. On **Preprocess**: verify channel order (DIC, DAPI, mCherry, GFP), then continue
4. On **Display**: inspect per-cell outputs; export CSV/XLSX from the table

**Expected artifacts**
```
media/<uuid>/
├─ M3850_001_PRJ.dv
├─ channel_config.json
├─ preprocessed_images/
│  ├─ DIC.tif
│  ├─ DAPI.tif
│  ├─ mCherry.tif
│  └─ GFP.tif
├─ output/
│  └─ mask.tif
└─ segmented/
   ├─ cell_0001.png
   ├─ cell_0002.png
   ├─ ...
   └─ overlay_debug_*.png
```

### 2) Programmatic Upload (Python)

```python
# save as upload_sample.py and run with the server up
import requests

url = "http://localhost:8000/image/upload/"
with open("example-dv-file/250307_M2472_N1_5_002_PRJ.dv", "rb") as f:
    r = requests.post(url, files={"files": ("250307_M2472_N1_5_002_PRJ.dv", f, "application/octet-stream")}, allow_redirects=False)

print("Status:", r.status_code)
print("Next:", r.headers.get("Location") or r.text[:2000])  # open this URL in a browser to continue
```


## Testing
Recommended:
- **Fixtures**: tiny DV stacks for unit tests.
- **Units**: channel parser, preprocessing transforms, direct mask generation.
- **Integration**: upload, to preprocess, to segment, to display (mock weights).
- **CI**: Windows/Linux, Python 3.11.5.

Run:
```bash
python manage.py test
```



## Security
- If deploying, move secrets out of the repo (env vars or secret store) and rotate existing keys.
- Set `CYTOCV_DEBUG=0` in production and populate `CYTOCV_ALLOWED_HOSTS`.
- Enforce HTTPS at the proxy. Add HSTS and a strict CSP.
- Add signup rate-limits or CAPTCHA.
- Enable dependency and secret scanning.
- Verify access control on display routes (already checks ownership).


## Troubleshooting
- **TensorFlow or import errors**: Use **Python 3.11.5** in a clean venv.
- **Missing weights**: Put `core/mrcnn/weights/deepretina_final.h5`.
- **DV rejected**: File must have exactly 4 layers.
- **No outputs / blank display**: Check console and `debug.log`. Confirm `output/mask.tif` was written.
- **Cache mismatch**: Turn off `use_cache` if parameters changed.
- **401 on display**: You are not the owner of the data.



## Roadmap
- Metrics endpoints and dashboards.
- Object storage support.
- Replace file-based progress with Redis/DB for better scale.
- Accessibility review and responsive UI fixes.



## License



### Notes
- **Exact Python** is non-negotiable here. If you must change TF/NumPy pins, expect breakage.  
- Keep the weights path and Mask R-CNN config consistent unless you also update docs and sample results.
