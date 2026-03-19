# CytoCV

CytoCV is a Django-based analysis system for DeltaVision (`.dv`) fluorescent microscopy stacks of mitotic yeast cells. It ingests four-channel image sets, runs preprocessing and Mask R-CNN segmentation, computes per-cell measurements, and presents the results through a web interface for review and export.

> **Version:** 1.0  
> **Python:** 3.11.5  
> **Database:** PostgreSQL in production; SQLite for local development only  
> **Platform:** Windows native development and Linux-compatible deployment

Deployment documentation:
- [`docs/vm-deployment-guide/README.md`](docs/vm-deployment-guide/README.md)
- [`docs/vm-deployment-record/README.md`](docs/vm-deployment-record/README.md)

## Scope

CytoCV currently targets workflows built around these channels:

- `DIC`
- `DAPI`
- `mCherry`
- `GFP`

High-level outputs include:

- upload preview images
- per-run segmentation masks and outlined frames
- per-cell crops and debug overlays
- database-backed cell statistics
- exportable tables from the display and dashboard views

## Quickstart

1. Use Python `3.11.5`.
2. Create and activate a virtual environment.
3. Install `requirements.txt`.
4. Copy `.env.example` to `.env`.
5. Set `CYTOCV_DB_BACKEND=sqlite` for local development or `postgres` for production.
6. From `cytocv/`, run:

```powershell
python manage.py migrate
python manage.py runserver
```

## Documentation

Detailed documentation is organized under [`docs/README.md`](docs/README.md).

Primary entrypoints:

- User docs: [`docs/user/getting-started.md`](docs/user/getting-started.md)
- Developer docs: [`docs/developer/architecture-overview.md`](docs/developer/architecture-overview.md)
- Deployment and environment: [`docs/ops/deployment-guide.md`](docs/ops/deployment-guide.md)
- Environment variable reference: [`docs/ops/environment-reference.md`](docs/ops/environment-reference.md)
- Route and API reference: [`docs/reference/routes-and-endpoints.md`](docs/reference/routes-and-endpoints.md)
- Diagram catalog: [`docs/diagrams/README.md`](docs/diagrams/README.md)

Formal research-style documents:

- [`docs/research/methods-and-system-description.md`](docs/research/methods-and-system-description.md)
- [`docs/research/reproducibility-and-validation.md`](docs/research/reproducibility-and-validation.md)
- [`docs/research/figure-catalog.md`](docs/research/figure-catalog.md)

Generated PDF deliverables:

- [`docs/research/methods-and-system-description.pdf`](docs/research/methods-and-system-description.pdf)
- [`docs/research/reproducibility-and-validation.pdf`](docs/research/reproducibility-and-validation.pdf)
- [`docs/research/figure-catalog.pdf`](docs/research/figure-catalog.pdf)

Historical deployment record for the March 2026 UWB VM rollout:

- [`docs/vm-deployment-record/README.md`](docs/vm-deployment-record/README.md)

## Notes

- The Mask R-CNN workflow depends on project-specific weights under `cytocv/core/weights`.
- PostgreSQL setup details are documented in [`docs/ops/postgres-setup.md`](docs/ops/postgres-setup.md).
- Markdown documents are the maintained source of truth. PDF documents in `docs/research/` are derived formal deliverables.



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
