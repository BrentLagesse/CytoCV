# YeastAnalysisTool

## Overview of Project

The project is a tool to automatically analyze WIDE-fluorescent microscopy images of yeast cells undergoing mitosis. The biologist uses yeast cells that have a controlled mutation in them. The biologists then use fluorescent labeling to point of interest (POI) like a specific protein and this program automatically analyzes those POI to collect useful data that can maybe be used to find the cause of cellular mutation. The user will upload a special DV (Delta Vision) file that has multiple images that are taken at the same time; thus, allowing them to be overlapped. One of them is a Differential interference contrast (DIC) image, which basically is a clear image of the cells, and multiple images of the cells through different wavelengths which excite the fluorescent labels separately, leading to the POI being brightened (small dots). Currently, the fluorescent labels being used are DAPI, mcherry, and GFP.


| DIC | DAPI | mCherry | GFP |
|:--:|:--:|:--:|:--:|
| <img width="250" alt="DIC" src="https://github.com/user-attachments/assets/1830b15d-d0cf-4558-ba3f-7d45462e0a13" /> | <img width="250" alt="DAPI" src="https://github.com/user-attachments/assets/0b6dc954-ed78-4abf-b9c9-436ded7551fa" /> | <img width="250" alt="mCherry" src="https://github.com/user-attachments/assets/68767176-2aec-4634-9b74-de8c085e32a4" /> | <img width="250" alt="GFP" src="https://github.com/user-attachments/assets/67e9c4f4-f520-422e-9a0b-48fa9fd370c0" /> |


## Installation
You need to make sure git, virtualenv, and python3 (currently using 3.11.5) are installed and are in the $PATH (you can type those command names on the commandline and your computer finds them).

1. Download this link https://drive.google.com/file/d/1moUKvWFYQoWg0z63F0JcSd3WaEPa4UY7/view?usp=sharing and put it in the weights directory under yeastweb/core/weights (might need to create folder manually)

### Running on Windows
Python version  **NEEDS TO BE 3.11.5** or else it will not work <br/>

1. git clone https://github.com/BrentLagesse/Yeast-Web.git #Clone github Repo using

2. curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py #Download pip

3. python get-pip.py

4. py -m pip install --upgrade pip

5. py -m pip install --user virtualenv #install virtual environment

6. py -m venv yeast_web

7. yeast_web\Scripts\activate #activate venv

Due to the machine learning part only works on certain versions of packages, we have to specifically use them 

###the easiest way do to do is to delete all your personal pip packages and reinstall them

```bash
# puts all personal packages into deleteRequirements.txt
1. pip freeze --all > deleteRequirements.txt
# uninstalls all packages
2. pip uninstall -r deleteRequirements.txt
# installs repo's pip packages
3. pip install -r ./requirements.txt --no-cache-dir
    * If fails, might be using the wrong Python version or go into deleteRequirments.txt and delete the line with pip
#deletes temporary Requirements
4. del deleteRequirements.txt
```

## Launching project

1. Navigate to the yeastweb directory:
   ```bash
   cd yeastweb

2. Run the application:
   ```bash
   python manage.py runserver
