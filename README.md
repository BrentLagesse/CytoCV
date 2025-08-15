# YeastAnalysisTool

## Overview of Project

The project is a tool to automatically analyze WIDE-fluorescent microscopy images of yeast cells undergoing mitosis. The biologist uses yeast cells that have a controlled mutation in them. The biologists then use fluorescent labeling to point of interest (POI) like a specific protein and this program automatically analyzes those POI to collect useful data that can maybe be used to find the cause of cellular mutation. The user will upload a special DV (Delta Vision) file that has multiple images that are taken at the same time; thus, allowing them to be overlapped. One of them is a Differential interference contrast (DIC) image, which basically is a clear image of the cells, and multiple images of the cells through different wavelengths which excite the fluorescent labels separately, leading to the POI being brightened (small dots). Currently, the fluorescent labels being used are DAPI, mcherry, and GFP.


| DIC | DAPI | mCherry | GFP |
|:--:|:--:|:--:|:--:|
| <img width="250" alt="DIC" src="https://github.com/user-attachments/assets/1830b15d-d0cf-4558-ba3f-7d45462e0a13" /> | <img width="250" alt="DAPI" src="https://github.com/user-attachments/assets/0b6dc954-ed78-4abf-b9c9-436ded7551fa" /> | <img width="250" alt="mCherry" src="https://github.com/user-attachments/assets/68767176-2aec-4634-9b74-de8c085e32a4" /> | <img width="250" alt="GFP" src="https://github.com/user-attachments/assets/67e9c4f4-f520-422e-9a0b-48fa9fd370c0" /> |


## Installation (Windows)
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
   source .venv/Scripts/activate
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
You must have your virtual environemnt activated to make the respective migrations. Please refer to the previous steps under **Environment Setup**.


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
