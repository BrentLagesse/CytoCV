# CytoCV VM Deployment Guide (UWB Ubuntu VM)

Maintainer: Nicolas Gioanni

This is the clean deployment guide for bringing CytoCV up on a fresh Ubuntu VM. It is intentionally separate from the historical rollout log.

Use this guide for the intended command sequence.

Use the historical records for the exact March 2026 rollouts, dead ends, and recovery work:
- [`../vm-deployment-record/README.md`](../vm-deployment-record/README.md)
- [`../vm-deployment-record-cytocv2/README.md`](../vm-deployment-record-cytocv2/README.md)

## Before You Start

You need all of the following before this deployment will succeed:

- a Linux VM with `sudo` access
- Python 3.11 available on the VM
- DNS for `cytocv.uwb.edu` pointed at the VM before HTTPS setup
- access to the `deepretina_final.h5` weight file
- a CPU that exposes `AVX`

### AVX Requirement

This matters before anything else. The web app can run without AVX, but the TensorFlow-based analysis pipeline cannot.

Run this immediately after SSH'ing into the VM:

```bash
lscpu | grep -i avx
```

If that prints nothing, stop here. The deployment can still serve the website, but analysis will fail because TensorFlow import will crash with:

```text
Illegal instruction (core dumped)
```

That exact issue happened on the March 2026 VM rollout.

## 1. SSH Into the VM

From your local machine:

```bash
ssh ngioanni@cytocv.uwb.edu
```

If the host key changed because UW IT moved the VM to a new public IP, clear the old SSH host entry first:

```bash
ssh-keygen -R cytocv.uwb.edu
```

## 2. Clone or Update the Repository

If the repository is not already on the VM:

```bash
cd ~
git clone https://github.com/BrentLagesse/CytoCV.git
cd ~/CytoCV
```

If the repository is already there:

```bash
cd ~/CytoCV
git pull
```

## 3. Create the Virtual Environment

For a fresh deployment, create the Python virtual environment in the repository root:

```bash
cd ~/CytoCV
python3.11 -m venv cyto_cv
source cyto_cv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt --no-cache-dir
```

If you need to rebuild the environment from scratch:

```bash
cd ~/CytoCV
rm -rf cyto_cv
python3.11 -m venv cyto_cv
source cyto_cv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt --no-cache-dir
```

Expected Linux behavior during dependency install:

```text
Ignoring tensorflow-intel: markers 'sys_platform == "win32"' don't match your environment
```

That is correct. `tensorflow-intel` is Windows-only.

### Ubuntu 24.04 Note: `python3.11` Package May Be Missing

On Ubuntu `24.04.4`, the default system Python may be `3.12.x`, and `apt` may not provide `python3.11` or `python3.11-venv` directly.

If that happens, do not continue with Python `3.12` for this deployment. Build Python `3.11.5` from source and create the venv from that interpreter instead:

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
cd ~/CytoCV
/opt/python3115/bin/python3.11 -m venv cyto_cv
source cyto_cv/bin/activate
python --version
```

## 4. Download the Model Weights

The current deployed runtime expects `deepretina_final.h5` under `cytocv/core/weights/`.

If `gdown` is not already installed in the venv:

```bash
python -m pip install gdown
```

Download the weights:

```bash
gdown --fuzzy "https://drive.google.com/file/d/1moUKvWFYQoWg0z63F0JcSd3WaEPa4UY7/view?usp=sharing" -O ~/CytoCV/cytocv/core/weights/deepretina_final.h5
ls -lh ~/CytoCV/cytocv/core/weights/deepretina_final.h5
```

Important:

- do not assume that placing the file only under `cytocv/core/mrcnn/weights/` is sufficient
- the runtime used during the `cytocv2` rollout looked specifically for:

```text
~/CytoCV/cytocv/core/weights/deepretina_final.h5
```

## 5. Generate Secret Values

Generate a PostgreSQL password:

```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

Generate a Django secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Keep both values. You will use them in PostgreSQL and in `~/CytoCV/.env`.

## 6. Create the Production `.env`

Create or replace the server `.env` file in the repository root:

```bash
cat > ~/CytoCV/.env <<'EOF'
CYTOCV_SECRET_KEY=PASTE_SECRET_KEY_HERE
CYTOCV_DEBUG=0
CYTOCV_ALLOWED_HOSTS=cytocv.uwb.edu,140.142.158.14
CYTOCV_DB_BACKEND=postgres
CYTOCV_DB_NAME=cytocv
CYTOCV_DB_USER=cytocv_user
CYTOCV_DB_PASSWORD=PASTE_DB_PASSWORD_HERE
CYTOCV_DB_HOST=127.0.0.1
CYTOCV_DB_PORT=5432
CYTOCV_DB_CONN_MAX_AGE=60
CYTOCV_DB_ATOMIC_REQUESTS=0
CYTOCV_DB_SSLMODE=prefer
CYTOCV_GOOGLE_CLIENT_ID=
CYTOCV_GOOGLE_CLIENT_SECRET=
CYTOCV_MICROSOFT_CLIENT_ID=
CYTOCV_MICROSOFT_CLIENT_SECRET=
CYTOCV_MICROSOFT_TENANT=organizations
CYTOCV_MICROSOFT_LOGIN_URL=https://login.microsoftonline.com
CYTOCV_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
CYTOCV_EMAIL_HOST=127.0.0.1
CYTOCV_EMAIL_HOST_USER=
CYTOCV_EMAIL_HOST_PASSWORD=
CYTOCV_EMAIL_PORT=25
CYTOCV_EMAIL_USE_TLS=0
CYTOCV_EMAIL_USE_SSL=0
CYTOCV_EMAIL_TIMEOUT=30
CYTOCV_ACCOUNT_EMAIL_VERIFICATION=optional
CYTOCV_DEFAULT_FROM_EMAIL=cytocv@uw.edu
CYTOCV_EMAIL_REPLY_TO=cytocv@uw.edu
CYTOCV_RECAPTCHA_ENABLED=1
CYTOCV_RECAPTCHA_SITE_KEY=
CYTOCV_RECAPTCHA_SECRET_KEY=
CYTOCV_RECAPTCHA_VERIFY_URL=https://www.google.com/recaptcha/api/siteverify
CYTOCV_RECAPTCHA_ALLOW_VERIFY_URL_OVERRIDE=0
CYTOCV_RECAPTCHA_EXPECTED_HOSTNAMES=cytocv.uwb.edu
CYTOCV_SECURITY_STRICT=0
EOF
```

Replace:

- `PASTE_SECRET_KEY_HERE`
- `PASTE_DB_PASSWORD_HERE`

### Why `CYTOCV_ACCOUNT_EMAIL_VERIFICATION=optional` Here

Do not set `mandatory` unless SMTP is actually working. If SMTP is not configured yet, OAuth sign-ins can fail after successful provider authentication because allauth tries to send verification mail.

Once UW IT provides a real approved sender and SMTP credentials, this can be changed back to:

```env
CYTOCV_ACCOUNT_EMAIL_VERIFICATION=mandatory
```

## 7. Install and Start PostgreSQL

Install PostgreSQL on the VM:

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
sudo systemctl status postgresql --no-pager
```

## 8. Create the PostgreSQL Role and Database

Create the application role:

```bash
sudo -u postgres psql -c "CREATE ROLE cytocv_user WITH LOGIN PASSWORD 'PASTE_DB_PASSWORD_HERE';"
```

Create the application database:

```bash
sudo -u postgres psql -c "CREATE DATABASE cytocv OWNER cytocv_user;"
```

Verify both:

```bash
sudo -u postgres psql -c "\du"
sudo -u postgres psql -c "\l"
```

If the role already exists, set the password explicitly:

```bash
sudo -u postgres psql -c "ALTER ROLE cytocv_user WITH LOGIN PASSWORD 'PASTE_DB_PASSWORD_HERE';"
```

If the database already exists, that is fine. Continue.

## 9. Apply Migrations

Run the normal migration path first:

```bash
cd ~/CytoCV/cytocv
source ~/CytoCV/cyto_cv/bin/activate
python manage.py migrate
python manage.py check
```

### Current Repository Caveat

As of the March 2026 deployment, the repository had a migration tracking problem:

- `cytocv/accounts/migrations/` was not fully tracked
- `cytocv/core/migrations/` was not fully tracked
- an orphaned `core/migrations/0007_uploadedimage_scale_info.py` caused graph inconsistencies

If the normal migrate command fails with errors like:

```text
App 'accounts' does not have migrations.
App 'core' does not have migrations.
```

or:

```text
NodeNotFoundError: Migration core.0007_uploadedimage_scale_info dependencies reference nonexistent parent node
```

use the current deployment workaround:

```bash
cd ~/CytoCV
rm -f cytocv/accounts/migrations/0001_initial.py
rm -f cytocv/core/migrations/0001_initial.py
rm -f cytocv/core/migrations/0007_uploadedimage_scale_info.py
cd ~/CytoCV/cytocv
source ~/CytoCV/cyto_cv/bin/activate
python manage.py makemigrations accounts core
python manage.py migrate
python manage.py check
```

This is a deployment workaround, not the real long-term repository fix.

### Linux Case-Sensitivity Caveat

The repo also contains a Linux-sensitive import path in `cytocv/core/cell_analysis/`.

Imports currently expect:

```python
from .analysis import Analysis
```

That means the file must be named:

```text
cytocv/core/cell_analysis/analysis.py
```

If the file is named `Analysis.py`, Windows development may appear to work, but Linux deployment can fail with:

```text
ModuleNotFoundError: No module named 'core.cell_analysis.analysis'
```

If that happens on the VM, rename the file to lowercase before retrying the workflow.

## 10. Smoke Test With Django `runserver`

Before introducing Gunicorn and Nginx, verify that Django boots and can serve requests:

```bash
cd ~/CytoCV/cytocv
source ~/CytoCV/cyto_cv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

Open:

```text
http://cytocv.uwb.edu:8000/
http://140.142.158.14:8000/
```

If the server starts cleanly, stop it with:

```bash
Ctrl+C
```

## 11. Manual Gunicorn Test

Run Gunicorn directly first so you can debug startup without `systemd` in the way:

```bash
cd ~/CytoCV/cytocv
source ~/CytoCV/cyto_cv/bin/activate
gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 120 cytocv.wsgi:application
```

In a second SSH session, verify it is listening:

```bash
ss -ltnp | grep 8000
```

Once confirmed, stop the manual Gunicorn process with:

```bash
Ctrl+C
```

Important:

- do not leave the manual Gunicorn process running before starting the `systemd` service
- if it is still bound to `0.0.0.0:8000`, the `cytocv` service can fail with `Address already in use`

## 12. Create the Gunicorn `systemd` Service

Create the service file:

```bash
sudo nano /etc/systemd/system/cytocv.service
```

Paste this:

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

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cytocv
sudo systemctl start cytocv
sudo systemctl status cytocv --no-pager
```

## 13. Install and Configure Nginx

Install Nginx:

```bash
sudo apt install -y nginx
sudo systemctl enable --now nginx
```

Create the site config:

```bash
sudo nano /etc/nginx/sites-available/cytocv
```

Paste this:

```nginx
server {
    listen 80;
    server_name cytocv.uwb.edu 140.142.158.14;

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

Important:

- do not add a `location /media/ { alias ... }` block here
- CytoCV serves `/media/...` through Django, not directly through Nginx

### Static Files in Production

If the site loads but favicon or static assets return `404`, configure Django static collection explicitly.

In `cytocv/cytocv/settings.py`, make sure you have:

```python
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
```

Then collect static files:

```bash
cd ~/CytoCV/cytocv
source ~/CytoCV/cyto_cv/bin/activate
python manage.py collectstatic --noinput
```

Add this block inside the active HTTPS Nginx `server { ... }` block:

```nginx
location /static/ {
    alias /home/NETID/ngioanni/CytoCV/cytocv/staticfiles/;
}
```

If the browser is also requesting `/favicon.ico`, you may need to serve that explicitly:

```nginx
location = /favicon.ico {
    alias /home/NETID/ngioanni/CytoCV/cytocv/staticfiles/favicon.ico;
}
```

If Nginx still returns `403` for `/static/...`, inspect filesystem traversal permissions on every parent directory. During the `cytocv2` rollout, the blocking path was:

```text
/home/NETID/ngioanni
```

and the fix was to allow directory traversal so Nginx could reach the collected static files.

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/cytocv /etc/nginx/sites-enabled/cytocv
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status nginx --no-pager
```

## 14. Enable HTTPS With Certbot

Install Certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

Request and install the certificate:

```bash
sudo certbot --nginx -d cytocv.uwb.edu
```

During the interactive prompts:

- enter a monitored email address
- accept the Let's Encrypt terms
- opt in or out of EFF mail as you prefer
- choose HTTPS redirect when prompted

Verify:

```bash
curl -I https://cytocv.uwb.edu
```

### Firewall and Certbot Troubleshooting

If Certbot times out while trying to validate `http://<host>/.well-known/acme-challenge/...`, first check whether the VM firewall is blocking HTTP:

```bash
sudo ufw status
sudo ufw allow 'Nginx Full'
sudo ufw status
```

If UFW is already open and Certbot still times out, the remaining blocker is likely upstream network/firewall policy outside the VM.

If Certbot successfully issues the certificate but fails to install it automatically, make sure the Nginx site has an exact matching `server_name` for the target host, then retry:

```bash
sudo certbot install --cert-name cytocv.uwb.edu
```

## 15. OAuth and reCAPTCHA Production Values

These steps are external to the VM, but they are required for auth to work correctly.

### Google reCAPTCHA

Use:

- type: `v2 Checkbox`
- domain:

```text
cytocv.uwb.edu
```

Do not use:

- `https://cytocv.uwb.edu/`
- `cytocv.uwb.edu/`
- `localhost:8000`

VM `.env` values:

```env
CYTOCV_RECAPTCHA_ENABLED=1
CYTOCV_RECAPTCHA_SITE_KEY=<your site key>
CYTOCV_RECAPTCHA_SECRET_KEY=<your secret key>
CYTOCV_RECAPTCHA_EXPECTED_HOSTNAMES=cytocv.uwb.edu
```

After changing `.env`:

```bash
sudo systemctl restart cytocv
```

### Google OAuth

In Google Cloud Console, use:

- Authorized JavaScript origin:

```text
https://cytocv.uwb.edu
```

- Authorized redirect URI:

```text
https://cytocv.uwb.edu/signin/oauth/google/login/callback/
```

And make sure the VM `.env` has the matching client values:

```env
CYTOCV_GOOGLE_CLIENT_ID=<google client id>
CYTOCV_GOOGLE_CLIENT_SECRET=<google client secret>
```

### Microsoft Entra

In the Entra app registration, add this Web redirect URI:

```text
https://cytocv.uwb.edu/signin/oauth/microsoft/login/callback/
```

And make sure the VM `.env` contains:

```env
CYTOCV_MICROSOFT_CLIENT_ID=<entra client id>
CYTOCV_MICROSOFT_CLIENT_SECRET=<entra client secret>
CYTOCV_MICROSOFT_TENANT=organizations
CYTOCV_MICROSOFT_LOGIN_URL=https://login.microsoftonline.com
```

## 16. Email Configuration

If SMTP is not ready yet, keep:

```env
CYTOCV_ACCOUNT_EMAIL_VERIFICATION=optional
CYTOCV_DEFAULT_FROM_EMAIL=cytocv@uw.edu
CYTOCV_EMAIL_REPLY_TO=cytocv@uw.edu
```

Do not set `mandatory` until you have:

- an approved sender address
- either local Postfix relay on the VM or direct SMTP settings
- any SMTP credential required by the relay you are using

For the local Postfix relay setup, keep Django on localhost and configure Postfix separately:

```env
CYTOCV_EMAIL_HOST=127.0.0.1
CYTOCV_EMAIL_HOST_USER=
CYTOCV_EMAIL_HOST_PASSWORD=
CYTOCV_EMAIL_PORT=25
CYTOCV_EMAIL_USE_TLS=0
CYTOCV_EMAIL_USE_SSL=0
CYTOCV_ACCOUNT_EMAIL_VERIFICATION=mandatory
```

Then restart:

```bash
sudo systemctl restart cytocv
```

The `cytocv2` redeploy still did not have final SMTP credentials from UW IT. Until those details are provided, email sign-up, verification, and recovery flows should still be treated as incomplete even if the rest of the deployment stack is healthy.

## 17. Verification Commands

Run these after deployment:

```bash
curl -I https://cytocv.uwb.edu
sudo systemctl status cytocv --no-pager
sudo systemctl status nginx --no-pager
sudo journalctl -u cytocv -n 100 --no-pager
```

Optional quick checks:

```bash
curl -I http://127.0.0.1:8000
curl -I http://127.0.0.1
curl -I http://140.142.158.14
```

If you intentionally lock `CYTOCV_ALLOWED_HOSTS` to the production hostname only, raw IP access may correctly fail with `DisallowedHost`. That is expected and safer than allowing the public IP unnecessarily.

## 18. Known Blocker: TensorFlow and Non-AVX CPUs

If `Start Analysis` causes the page to appear to reload and Gunicorn workers die, test TensorFlow directly:

```bash
cd ~/CytoCV
source cyto_cv/bin/activate
python -c "import tensorflow as tf; print(tf.__version__)"
```

If you get:

```text
Illegal instruction (core dumped)
```

the VM CPU is not compatible with the TensorFlow wheel in this deployment.

Confirm the CPU flags:

```bash
lscpu | grep -i avx
lscpu
```

If `AVX` is absent, the deployment can host the website, but analysis cannot run on that VM. The fix is infrastructure, not Django configuration.

## 19. Additional Runtime Troubleshooting

### OpenCV Import Fails With `libGL.so.1`

If `python manage.py migrate` or app startup fails with:

```text
ImportError: libGL.so.1: cannot open shared object file: No such file or directory
```

install the OpenCV runtime libraries:

```bash
sudo apt install -y libgl1 libglib2.0-0
```

Then rerun the Django command.

### Browser Tab Icon Still Missing After Staticfiles Are Working

Even after `collectstatic` and Nginx aliasing are fixed, favicon behavior can still be affected by:

- browser cache
- requests to `/favicon.ico` instead of the template-linked asset path
- an icon file that is visually too subtle at favicon size

If the icon asset is correct but still does not appear, test the direct URLs in the browser and consider using a PNG favicon link instead of the ICO file.

## 20. Recommended Deployment Order Summary

Use this order:

1. Verify the VM CPU exposes `AVX`
2. Clone the repo
3. Create the Python virtual environment
4. Install Python dependencies
5. Download the model weights
6. Create `~/CytoCV/.env`
7. Install PostgreSQL
8. Create the PostgreSQL role and database
9. Run migrations
10. Smoke test with `runserver`
11. Smoke test with manual Gunicorn
12. Create the Gunicorn `systemd` service
13. Install and configure Nginx
14. Enable HTTPS with Certbot
15. Configure reCAPTCHA and OAuth providers
16. Configure SMTP and tighten email verification when ready

## 21. Post-Deployment Recommendations

After the server is up:

1. Fix the repository migration tracking problem properly.
2. Lock provider settings to the production domain only.
3. Finish SMTP configuration with UW IT.
4. Confirm the VM or analysis host has AVX-capable CPU support before expecting image analysis to work.

