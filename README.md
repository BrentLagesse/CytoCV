# YeastAnalysisTool
Automated analysis of **DeltaVision (DV)** fluorescent microscopy stacks of yeast cells in mitosis. Quantifies points of interest across **DIC, DAPI, mCherry, GFP** channels with a Django web UI and a ML segmentation workflow (Mask R-CNN).

> **Version:** 1.0
> **Repo:** https://github.com/BrentLagesse/Yeast-Web  
> **Python:** **3.11.5** (exact)  
> **DB:** SQLite (default)  
> **OS:** Windows (native) / Linux (via Docker)


<details open>
<summary><h2>Table of Contents</h2></summary>
   
- [Overview](#overview)
- [Key features](#key-features)
- [Installation](#installation)
  - [Environment Setup](#environment-setup)
  - [Installing Dependencies](#installing-dependencies)
  - [Migrations](#migrations)
  - [Launching project](#launching-project)
- [Configuration](#configuration)
- [Project layout](#project-layout)
- [Data & artifacts](#data--artifacts)
- [Workflow](#workflow)
  - [Uploading (UI & API)](#uploading-ui--api)
  - [Image processing](#image-processing)
  - [Outputs & schemas](#outputs--schemas)
- [HTTP routes](#http-routes)
- [Examples](#examples)
- [Benchmarks](#benchmarks)
- [Testing](#testing)
- [Deployment](#deployment)
- [Operations](#operations)
- [Security checklist](#security-checklist)
- [Troubleshooting](#troubleshooting)
- [Versioning & releases](#versioning--releases)
- [Contributing](#contributing)
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
- **Mask R-CNN inference** (CPU), **RLE→TIFF** conversion.
- **Segmentation** with Gaussian blur, Otsu, rolling-ball BG subtraction, region merges.
- **Per-cell metrics** stored in DB:
  - `distance` (mCherry dot distance)
  - `line_gfp_intensity` (sum along mCherry line)
  - `nucleus_intensity_sum`
  - `cellular_intensity_sum`
- **Web UI** to upload, preprocess, select analyses, display, and export tables.

## Installation 
You need to make sure git, virtualenv, and python3 (currently using 3.11.5) are installed and are in the $PATH (you can type those command names on the commandline and your computer finds them).

1. Download the file "deepretina_final.h5" in the link below and place it in the weights directory under yeastweb/core/weights (may need to create the folder manually):

   https://drive.google.com/file/d/1moUKvWFYQoWg0z63F0JcSd3WaEPa4UY7/view?usp=sharing


### Environment Setup

1. Confirm Python is exactly 3.11.5; Python version  **NEEDS TO BE 3.11.5** or else it will not work:
   ```bash
   python --version

2. Clone the Github repository:
   ```bash
   git clone https://github.com/BrentLagesse/Yeast-Web.git

3. Navigate to the Directory:
   ```bash
   cd Yeast-Web

4. Create virtual environment:
    ```bash
   python -m venv yeast_web

5. Activate virtual environment:
   ```bash
   source yeast_web/Scripts/activate
   ```
   or
   ```bash
   yeast_web\Scripts\activate
   ```
6. Make sure pip exists in the virtual environment:
    ```bash
   python -m ensurepip --upgrade

7. Upgrade base tools:
    ```bash
   python -m pip install --upgrade pip setuptools wheel

8. Check that pip is from the virtual environment:
   ```bash
   python -m pip --version   # path should point into Yeast-Web/.venv


### Installing Dependencies
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

5. Remove the temporary list of requirements:
   ```bash
   del deleteRequirements.txt

### Migrations
You must have your virtual environment activated to make the respective migrations. Please refer to the previous steps under **Environment Setup**.


1. Delete the local SQLite database (If the file does not exist, no output or a “cannot find path” message is fine):
   ```bash
   Remove-Item .\db.sqlite3 -Force

2. Create migrations for specific apps (accounts, core):
   ```bash
   python manage.py makemigrations accounts core

3. Apply migrations to build the schema:
   ```bash
   python manage.py migrate


## Launching project

1. Navigate to the yeastweb directory:
   ```bash
   cd yeastweb

2. Run the application:
   ```bash
   python manage.py runserver



## Configuration
**No `.env` file is required.** The current repo ships with working defaults defined directly in:
```
yeastweb/yeastweb/settings.py
```
- Local development works out of the box (SQLite, DEBUG on, email/Gmail placeholders, OAuth provider stubs).
- If you only run locally, you **do not need to configure anything** here.



## Project layout
```
Yeast-Web/
├─ Dockerfile         # python:3.11.5-slim
├─ compose.yml
├─ start.sh           # run migrations, launch gunicorn
└─ yeastweb/
   ├─ accounts/       # auth, profile, config UI
   ├─ core/           # upload, preprocess, convert, segment, display, stats
   │  ├─ image_processing/
   │  ├─ contour_processing/
   │  ├─ cell_analysis/
   │  └─ mrcnn/
   │     ├─ weights/deepretina_final.h5
   │     └─ my_inference.py
   ├─ templates/      # upload/preprocess/display pages
   └─ yeastweb/       # settings, urls, wsgi, asgi
```

Entry points: `manage.py` (CLI), `yeastweb/urls.py` (routes), `wsgi.py/asgi.py` (servers)


## Data & artifacts
- **Inputs**: DV `.dv` with **exactly** 4 layers (DIC + three fluorescence).
- **Storage**: `MEDIA_ROOT/<uuid>/<original>.dv` (UUID per upload).
- **Metadata**: `channel_config.json` (wavelengths/order).
- **Preprocessing**: `preprocessed_images/`, `preprocessed_images_list.csv`, `compressed_masks.csv`, `output/mask.tif`.
- **Segmentation**: per-cell PNGs in `segmented/`, outline CSVs, debug overlays.
- **DB**: `CellStatistics` rows for per-cell metrics.
- **Samples**: `example-dv-file/`.



## Workflow
1. **Upload** DV stack(s): `/image/upload/`  
2. **Preprocess** and choose analyses: `/image/preprocess/<uuids>/`  
3. **Inference** (Mask R-CNN) and **RLE→TIFF** conversion  
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
- Write `preprocessed_images_list.csv` (dimensions, metadata)

**Mask R-CNN (CPU)**
- Min dim 512, anchors 8–128, confidence ≥ 0.9
- Weights: `core/mrcnn/weights/deepretina_final.h5`
- `CUDA_VISIBLE_DEVICES` disabled

**RLE to TIFF**
- Convert to binary TIFFs (optional rescale)

**Segmentation**
- Gaussian blur + Otsu threshold
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
- `preprocessed_images_list.csv`: `image_id, width, height, channel, dtype, path`
- `compressed_masks.csv`: `image_id, EncodedRLE`
- Outline/metrics CSVs: `cell_id, x/y coords, area, intensity, distance, notes`

**Table export (UI)**
- `django-tables2` supports CSV/XLSX via `_export` query param.



## HTTP routes
- **Core**:  
  - `/image/upload/`  
  - `/image/preprocess/<uuids>/`  
  - `/image/<uuids>/segment/`  
  - `/image/<uuids>/display/`
- **Auth**: `/login/`, `/signup/`, OAuth (Google/Microsoft) if configured.  
- Internal JSON endpoints are CSRF-protected. No versioned public REST API.



## Examples








## License



### Notes
- **Exact Python** is non-negotiable here. If you must change TF/NumPy pins, expect breakage.  
- Keep the weights path and Mask R-CNN config consistent unless you also update docs and sample results.
