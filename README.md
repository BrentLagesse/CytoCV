# YeastAnalysisTool

You need to make sure git, virtualenv, and python3 (currently using 3.11.5) are installed and are in the $PATH (you can type those command names on the commandline and your computer finds them).

###########################################################################################################################################################

Running on Windows
Having the same assumptions that Python(3.11.5) is installed in the machine

1. git clone https://github.com/BrentLagesse/Yeast-Web.git #Clone github Repo using

2. curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py #Download pip

3. python get-pip.py

4. py -m pip install --upgrade pip

5. py -m pip install --user virtualenv #install virtual environment

6. py -m venv venv #create venv folder

7. .\venv\Scripts\activate #activate venv

## Due to the machine learning part only works on certain versions of packages, we have to specifically use them

#### the easiest way do to do is to delete all your personal pip packages and reinstall them

```bash
# puts all personal packages into deleteRequirements.txt
1. pip freeze --all > deleteRequirements.txt
# uninstalls all packages
2. pip uninstall -r deleteRequirements.txt
# installs repo's pip packages
3. pip install -r ./requirements.txt --no-cache-dir
#deletes temporary Requirements
4. del deleteRequirements.txt
```

## Launching project

11. Download this link https://drive.google.com/file/d/1moUKvWFYQoWg0z63F0JcSd3WaEPa4UY7/view?usp=sharing and put it in the weights directory under yeastweb/core/weights

```
1. cd yeastweb

2. python manage.py runserver

```
