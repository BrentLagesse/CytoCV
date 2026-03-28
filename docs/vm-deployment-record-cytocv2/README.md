# CytoCV VM Deployment Record (`cytocv2.uwb.edu`, March 2026)

Maintainer: Nicolas Gioanni

This document is a deployment record, not a generic setup guide. It records what was actually done to bring CytoCV up on the replacement UWB VM at `cytocv2.uwb.edu`, the commands that were used, the failures that appeared, and the exact fixes that were applied.

Use this as the historical log for the replacement VM rollout.

For the clean step-by-step guide, see:
- [`../vm-deployment-guide/README.md`](../vm-deployment-guide/README.md)

For the first March 2026 UWB VM rollout record, see:
- [`../vm-deployment-record/README.md`](../vm-deployment-record/README.md)

## Scope

- Target host: `cytocv2.uwb.edu`
- Public IP during deployment: `128.95.57.95`
- OS: Ubuntu 24.04.4 LTS
- Default system Python on host: `3.12.3`
- Installed deployment Python: `3.11.5` built from source under `/opt/python3115`
- App stack:
  - Django
  - PostgreSQL
  - Gunicorn managed by `systemd`
  - Nginx reverse proxy
  - Let's Encrypt HTTPS

## Final State Reached

By the end of this work:

- the site was reachable at `https://cytocv2.uwb.edu`
- PostgreSQL was installed and the `cytocv` database was created
- Gunicorn was running under a `systemd` service named `cytocv`
- Nginx was proxying traffic correctly and serving collected static files
- HTTPS was enabled successfully with Certbot
- TensorFlow imported successfully on this VM
- the analysis pipeline was able to execute on the replacement VM
- email/SMTP remained incomplete because production SMTP/account details were still missing

## Important Caveats Exposed by This Deployment

This rollout succeeded, but it exposed several repository and runtime issues that are easy to hit again on future Linux redeployments:

- Ubuntu `24.04.4` did not provide `python3.11` via the expected apt package names, so Python `3.11.5` had to be built from source
- the repository migration problem from the first VM still existed and required the same local migration recovery
- the runtime expected Mask R-CNN weights at `cytocv/core/weights/deepretina_final.h5`
- Linux case sensitivity broke `core.cell_analysis.analysis` because the file was named `Analysis.py`
- production staticfiles were not fully configured until `STATIC_ROOT`, `collectstatic`, Nginx `/static/`, and filesystem traversal permissions were added

## 1. AVX Check Succeeded on the Replacement VM

The first check on the replacement VM was to make sure the CPU exposed `AVX`, because that had blocked TensorFlow on the first VM.

Command used:

```bash
lscpu | grep -i avx
```

Observed result:

- `avx`, `avx2`, and additional vector flags were present

That established that this replacement VM was a valid TensorFlow host candidate.

## 2. Ubuntu 24.04 Defaulted to Python 3.12, Not 3.11

The expected apt packages for Python `3.11` were not available on this host.

Commands used:

```bash
python3 --version
lsb_release -a
apt-cache policy python3
apt-cache search python3-venv
sudo apt install -y python3.11 python3.11-venv
```

Observed result:

- `python3 --version` showed `Python 3.12.3`
- `apt` could not locate `python3.11` or `python3.11-venv`

That meant the deployment could not continue with the documented `python3.11` package path.

## 3. Python 3.11.5 Was Built From Source

To keep the deployment on the required interpreter version, Python `3.11.5` was built manually under `/opt/python3115`.

Commands used:

```bash
sudo apt update
sudo apt install -y \
  build-essential curl wget git nginx postgresql postgresql-contrib certbot python3-certbot-nginx \
  libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
  libncurses-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
  libffi-dev liblzma-dev uuid-dev

cd /tmp
wget https://www.python.org/ftp/python/3.11.5/Python-3.11.5.tgz
tar -xzf Python-3.11.5.tgz
cd Python-3.11.5
./configure --prefix=/opt/python3115 --enable-optimizations
make -j"$(nproc)"
sudo make altinstall
/opt/python3115/bin/python3.11 --version
```

Observed result:

```text
Python 3.11.5
```

## 4. Repository Clone and Virtual Environment Creation

The repo was cloned and the venv was created from the newly built interpreter.

Commands used:

```bash
cd ~
git clone https://github.com/BrentLagesse/CytoCV.git
cd ~/CytoCV
/opt/python3115/bin/python3.11 -m venv cyto_cv
source cyto_cv/bin/activate
python --version
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt --no-cache-dir
python -m pip install gdown
```

Observed result:

- `python --version` inside the venv showed `Python 3.11.5`
- dependency installation completed successfully

## 5. Initial Model Weight Download Used the Wrong Directory

At first, the weights were downloaded into `cytocv/core/mrcnn/weights/`, which existed in the code layout but was not the path actually used by the deployed runtime.

Commands used:

```bash
mkdir -p ~/CytoCV/cytocv/core/mrcnn/weights
gdown --fuzzy "https://drive.google.com/file/d/1moUKvWFYQoWg0z63F0JcSd3WaEPa4UY7/view?usp=sharing" -O ~/CytoCV/cytocv/core/mrcnn/weights/deepretina_final.h5
ls -lh ~/CytoCV/cytocv/core/mrcnn/weights/deepretina_final.h5
```

Later, runtime logs showed the app was actually looking for:

```text
/home/NETID/ngioanni/CytoCV/cytocv/core/weights/deepretina_final.h5
```

The weights file was eventually copied there:

```bash
mkdir -p ~/CytoCV/cytocv/core/weights
cp ~/CytoCV/cytocv/core/mrcnn/weights/deepretina_final.h5 ~/CytoCV/cytocv/core/weights/deepretina_final.h5
ls -lh ~/CytoCV/cytocv/core/weights/deepretina_final.h5
```

## 6. Production `.env` Was Created for the Replacement Host

Secret values were generated and a production `.env` was created for `cytocv2.uwb.edu`.

Commands used:

```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
python -c "import secrets; print(secrets.token_urlsafe(50))"
nano ~/CytoCV/.env
```

Important values used during the replacement rollout included:

```env
CYTOCV_SECRET_KEY=<generated secret>
CYTOCV_DEBUG=0
CYTOCV_ALLOWED_HOSTS=cytocv2.uwb.edu
CYTOCV_DB_BACKEND=postgres
CYTOCV_DB_NAME=cytocv
CYTOCV_DB_USER=cytocv_user
CYTOCV_DB_PASSWORD=<generated db password>
CYTOCV_DB_HOST=127.0.0.1
CYTOCV_DB_PORT=5432
CYTOCV_DB_CONN_MAX_AGE=60
CYTOCV_DB_ATOMIC_REQUESTS=0
CYTOCV_DB_SSLMODE=prefer
CYTOCV_ACCOUNT_EMAIL_VERIFICATION=optional
CYTOCV_RECAPTCHA_EXPECTED_HOSTNAMES=cytocv2.uwb.edu
CYTOCV_SECURITY_STRICT=0
```

The important operational choice here was to keep `CYTOCV_ACCOUNT_EMAIL_VERIFICATION=optional`, because SMTP was still not fully configured.

## 7. PostgreSQL Installation and Database Creation

PostgreSQL was installed and the application role/database were created.

Commands used:

```bash
sudo systemctl enable --now postgresql
sudo -u postgres psql -c "CREATE ROLE cytocv_user WITH LOGIN PASSWORD 'PASTE_DB_PASSWORD_HERE';"
sudo -u postgres psql -c "CREATE DATABASE cytocv OWNER cytocv_user;"
sudo -u postgres psql -c "\du"
sudo -u postgres psql -c "\l"
```

Observed result:

- role `cytocv_user` existed
- database `cytocv` existed

## 8. Django Failed Initially Because `libGL.so.1` Was Missing

The first Django migration attempt on the new VM failed before migrations could run because OpenCV could not load.

Commands used:

```bash
cd ~/CytoCV/cytocv
python manage.py migrate
python manage.py check
```

Important error:

```text
ImportError: libGL.so.1: cannot open shared object file: No such file or directory
```

Fix used:

```bash
sudo apt install -y libgl1 libglib2.0-0
```

After that, Django could boot far enough to hit the next issue.

## 9. Migration Recovery Was Required Again

The migration-tracking issue from the first VM still existed on the replacement VM.

Observed failure:

```text
django.db.utils.ProgrammingError: relation "accounts_customuser" does not exist
```

The recovery path used again was:

```bash
cd ~/CytoCV
rm -f cytocv/accounts/migrations/0001_initial.py
rm -f cytocv/core/migrations/0001_initial.py
rm -f cytocv/core/migrations/0007_uploadedimage_scale_info.py
cd ~/CytoCV/cytocv
python manage.py makemigrations accounts core
python manage.py migrate
python manage.py check
```

Observed result:

- migrations for `accounts` and `core` were regenerated locally
- the full migration chain then applied successfully
- `python manage.py check` reported no issues

## 10. Gunicorn Was Validated Manually First

Before creating the service, Gunicorn was started manually to confirm the WSGI app booted correctly.

Commands used:

```bash
cd ~/CytoCV/cytocv
gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 120 cytocv.wsgi:application
ss -ltnp | grep 8000
```

Observed result:

```text
LISTEN ... 0.0.0.0:8000 ... users:(("gunicorn",pid=...,fd=3), ...)
```

This validated Gunicorn, but that manual process later had to be stopped before the `systemd` service could take over the port.

## 11. Gunicorn `systemd` Service Was Created

The permanent service was created at:

```text
/etc/systemd/system/cytocv.service
```

Service contents used:

```ini
[Unit]
Description=CytoCV Gunicorn
After=network.target postgresql.service

[Service]
User=ngioanni
Group=ngioanni
WorkingDirectory=/home/NETID/ngioanni/CytoCV/cytocv
Environment="PATH=/home/NETID/ngioanni/CytoCV/cyto_cv/bin"
ExecStart=/home/NETID/ngioanni/CytoCV/cyto_cv/bin/gunicorn --workers 3 --timeout 120 --bind 127.0.0.1:8000 cytocv.wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Commands used:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cytocv
sudo systemctl start cytocv
sudo systemctl status cytocv --no-pager
```

At first, the service hit `Address already in use` because the manual Gunicorn process was still bound to port `8000`. The fix was:

```bash
sudo pkill -f "gunicorn --bind 0.0.0.0:8000"
sudo systemctl restart cytocv
sudo systemctl status cytocv --no-pager
sudo ss -ltnp | grep 8000
```

Final observed state:

- Gunicorn was listening at `127.0.0.1:8000` under `systemd`

## 12. Nginx Was Configured as the Reverse Proxy

The public Nginx site config was created at:

```text
/etc/nginx/sites-available/cytocv
```

Core config used:

```nginx
server {
    server_name cytocv2.uwb.edu;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The site was enabled with:

```bash
sudo ln -s /etc/nginx/sites-available/cytocv /etc/nginx/sites-enabled/cytocv
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status nginx --no-pager
```

## 13. Host Validation Was Tightened to Hostname-Only Access

The replacement deployment was intentionally hardened to accept only the hostname rather than the raw public IP.

Relevant `.env` values:

```env
CYTOCV_ALLOWED_HOSTS=cytocv2.uwb.edu
CYTOCV_RECAPTCHA_EXPECTED_HOSTNAMES=cytocv2.uwb.edu
```

Practical effect:

- requests made directly to `128.95.57.95` were rejected with `DisallowedHost`
- requests made to `cytocv2.uwb.edu` succeeded

This was expected and intentional after the final production hostname was in place.

## 14. Certbot Initially Failed Because Port 80 Was Blocked by UFW

The first Certbot attempt failed with an ACME timeout.

Command used:

```bash
sudo certbot --nginx -d cytocv2.uwb.edu
```

Important error:

```text
Timeout during connect (likely firewall problem)
```

The VM was listening on port `80`, but UFW only allowed SSH.

Commands used to confirm and fix:

```bash
sudo ss -ltnp | grep ':80'
sudo ufw status
sudo ufw allow 'Nginx Full'
sudo ufw status
```

After that, Certbot could reach the VM.

## 15. Certbot Issued the Certificate but Could Not Install It Automatically

After port `80` was opened, Certbot successfully issued the certificate but failed to install it into Nginx.

Observed error:

```text
Could not automatically find a matching server block for cytocv2.uwb.edu
```

Fix used:

1. Make sure the active Nginx site had an exact `server_name cytocv2.uwb.edu;`
2. Re-run installation explicitly

Command used:

```bash
sudo certbot install --cert-name cytocv2.uwb.edu
```

Observed result:

```text
Successfully deployed certificate for cytocv2.uwb.edu to /etc/nginx/sites-enabled/cytocv
```

Final verification:

```bash
curl -I https://cytocv2.uwb.edu
```

Observed result:

```text
HTTP/1.1 200 OK
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

## 16. Analysis First Failed Because the Runtime Could Not Find the Weights File

Once the web stack was online, the first preprocess/analysis attempt failed inside the Mask R-CNN runtime.

Logs used:

```bash
sudo journalctl -u cytocv -f
```

Important error:

```text
FileNotFoundError: Mask R-CNN weights file not found: /home/NETID/ngioanni/CytoCV/cytocv/core/weights/deepretina_final.h5
```

Fix used:

```bash
mkdir -p ~/CytoCV/cytocv/core/weights
cp ~/CytoCV/cytocv/core/mrcnn/weights/deepretina_final.h5 ~/CytoCV/cytocv/core/weights/deepretina_final.h5
sudo systemctl restart cytocv
```

That resolved the missing-weights error.

## 17. Linux Case Sensitivity Broke `core.cell_analysis.analysis`

The next analysis failure was Linux-specific.

Important error:

```text
ModuleNotFoundError: No module named 'core.cell_analysis.analysis'
```

Cause:

- imports expected `from .analysis import Analysis`
- the file on disk was `Analysis.py`
- Windows tolerated this mismatch, Linux did not

Fix used:

```bash
cd ~/CytoCV/cytocv/core/cell_analysis
mv Analysis.py analysis.py
sudo systemctl restart cytocv
```

Verification command:

```bash
cd ~/CytoCV/cytocv
python manage.py shell -c "from core.cell_analysis.analysis import Analysis; print(Analysis)"
```

Observed result:

```text
<class 'core.cell_analysis.analysis.Analysis'>
```

## 18. TensorFlow Was Confirmed to Work on the Replacement VM

Unlike the first UWB VM, this host could import TensorFlow successfully.

Command used:

```bash
cd ~/CytoCV
source cyto_cv/bin/activate
python -c "import tensorflow as tf; print(tf.__version__)"
```

Observed result:

```text
2.15.1
```

There were CPU-only warnings and TensorFlow startup noise, but not the fatal `Illegal instruction` seen on the first VM.

## 19. Staticfiles Had to Be Configured Explicitly for Production

The application templates referenced `UWBSTEM.ico` and `UWBSTEM.png`, and those files existed in the repository, but production static serving was not fully configured initially.

The fix required four pieces:

1. set `STATIC_ROOT`
2. run `collectstatic`
3. add an Nginx `/static/` alias
4. allow directory traversal so Nginx could actually reach the files

The settings change used was:

```python
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
```

Then:

```bash
cd ~/CytoCV/cytocv
source ~/CytoCV/cyto_cv/bin/activate
python manage.py collectstatic --noinput
```

Observed result:

```text
142 static files copied to '/home/NETID/ngioanni/CytoCV/cytocv/staticfiles'.
```

The Nginx HTTPS server then added:

```nginx
location /static/ {
    alias /home/NETID/ngioanni/CytoCV/cytocv/staticfiles/;
}
```

Direct file checks confirmed the assets existed:

```bash
ls -lh /home/NETID/ngioanni/CytoCV/cytocv/staticfiles/assets/UWBSTEM.ico
ls -lh /home/NETID/ngioanni/CytoCV/cytocv/staticfiles/assets/UWBSTEM.png
```

But initial requests still returned `403`, which led to the final permission fix.

## 20. Staticfile `403` Was Caused by Home Directory Traversal Permissions

Even after `collectstatic` and Nginx aliasing, static requests initially failed with `403 Forbidden`.

Diagnostic commands used:

```bash
curl -I -k https://127.0.0.1/static/assets/UWBSTEM.ico -H "Host: cytocv2.uwb.edu"
namei -l /home/NETID/ngioanni/CytoCV/cytocv/staticfiles/assets/UWBSTEM.ico
```

The important path segment was:

```text
drwx------ ngioanni ngioanni /home/NETID/ngioanni
```

Fix used:

```bash
chmod o+x /home/NETID/ngioanni
```

After that, the static assets were reachable:

```bash
curl -I https://cytocv2.uwb.edu/static/assets/UWBSTEM.ico
curl -I https://cytocv2.uwb.edu/static/assets/UWBSTEM.png
```

Observed result:

```text
HTTP/1.1 200 OK
```

## 21. `/favicon.ico` Also Needed Explicit Handling

Browsers still requested `/favicon.ico` even after `/static/assets/UWBSTEM.ico` was working.

The favicon file was copied into the collected static root:

```bash
cp /home/NETID/ngioanni/CytoCV/cytocv/staticfiles/assets/UWBSTEM.ico /home/NETID/ngioanni/CytoCV/cytocv/staticfiles/favicon.ico
```

And Nginx added:

```nginx
location = /favicon.ico {
    alias /home/NETID/ngioanni/CytoCV/cytocv/staticfiles/favicon.ico;
}
```

The remaining favicon problem turned out to be largely asset/browser-behavior related rather than a deployment outage. The browser tab icon was later switched to the PNG path in the template for more reliable display.

## 22. Email and SMTP Remained Incomplete

This redeploy did not receive the production SMTP/account details needed to finish email-backed account flows.

Practical implication:

- OAuth sign-in was the working path
- email sign-up, email verification, and email recovery should still be treated as incomplete until the UW IT SMTP details are provided

## 23. Final Verification Commands Used

These commands were used to verify the final deployed state:

```bash
curl -I https://cytocv2.uwb.edu
sudo systemctl status cytocv --no-pager
sudo systemctl status nginx --no-pager
sudo ss -ltnp | grep 8000
python -c "import tensorflow as tf; print(tf.__version__)"
curl -I https://cytocv2.uwb.edu/static/assets/UWBSTEM.ico
curl -I https://cytocv2.uwb.edu/static/assets/UWBSTEM.png
```

Important observed successful state:

- `https://cytocv2.uwb.edu` returned `HTTP/1.1 200 OK`
- `cytocv.service` was active and listening on `127.0.0.1:8000`
- `nginx.service` was active
- TensorFlow printed version `2.15.1`
- static favicon/logo assets returned `200 OK`

## 24. Differences From the First UWB VM

Compared with the first March 2026 rollout at `cytocv.uwb.edu`, the replacement `cytocv2` rollout differed in these important ways:

- the replacement VM exposed `AVX`, so TensorFlow could run
- Ubuntu `24.04.4` required building Python `3.11.5` from source because the expected `python3.11` apt packages were unavailable
- the same migration-tracking problem still existed and required local recovery again
- additional Linux runtime issues surfaced and were fixed:
  - missing `libGL.so.1` dependencies for OpenCV
  - wrong runtime weights path
  - case-sensitive import failure for `analysis.py`
  - production staticfiles setup and permission problems
- the stack ultimately reached a stronger final state than the first VM because the analysis runtime itself was able to execute on this host

## 25. One-Paragraph Summary

CytoCV was successfully redeployed on the replacement UWB VM at `https://cytocv2.uwb.edu` with PostgreSQL, Gunicorn under `systemd`, Nginx, HTTPS, working staticfiles, and a TensorFlow-capable CPU environment. The deployment required building Python `3.11.5` from source on Ubuntu `24.04.4`, recovering the database schema again from the repository migration problem, fixing missing OpenCV libraries, correcting the runtime Mask R-CNN weights path, renaming `Analysis.py` to `analysis.py` for Linux compatibility, opening UFW for Certbot validation, and explicitly configuring collected static files and directory traversal permissions for Nginx. The result was a working replacement deployment in which the analysis pipeline could run, although email/SMTP-backed account flows remained incomplete pending final production SMTP details.
