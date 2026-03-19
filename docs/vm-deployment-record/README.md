# CytoCV VM Deployment Record (UWB VM, March 2026)

Maintainer: Nicolas Gioanni

This document is a deployment record, not a generic setup guide. It records what was actually done to get CytoCV running on the UWB VM, the exact commands that were used, the exact failure modes that appeared, and the fixes that were applied.

Use this as a historical log for future redeployments, troubleshooting, or handing the system off to another person.

For the clean step-by-step deployment guide, see:
- [`../vm-deployment-guide/README.md`](../vm-deployment-guide/README.md)

## Scope

- Target host: `cytocv.uwb.edu`
- Public IP during deployment: `140.142.158.14`
- OS: Ubuntu 24.04.4 LTS
- Python: 3.11.5 / 3.11.x virtual environment
- App stack:
  - Django
  - PostgreSQL
  - Gunicorn managed by `systemd`
  - Nginx reverse proxy
  - Let's Encrypt HTTPS

## Final State Reached

By the end of this work:

- The site was reachable at `https://cytocv.uwb.edu`
- PostgreSQL was installed and the `cytocv` database was created
- Gunicorn was running under a `systemd` service named `cytocv`
- Nginx was proxying traffic to Gunicorn
- HTTPS was enabled successfully with Certbot
- Google reCAPTCHA and OAuth configuration debugging was partially completed
- Microsoft Entra callback was working through the provider, but app-side email verification remained blocked by missing SMTP configuration
- The analysis pipeline was still blocked because the VM CPU did not expose `AVX`, causing TensorFlow to crash with `Illegal instruction`

## Important Caveat About This Deployment

This VM deployment was recovered successfully, but it exposed a repository issue:

- the repo's `.gitignore` excludes most migration files
- this caused the migration chain on the VM to be incomplete
- a local VM-only migration recovery was required to get the schema built

That means this deployment worked, but future clean redeployments can fail again unless migration tracking in the repository is fixed properly.

## 1. Initial Python Environment Recreation

The first action on the VM was to delete and recreate the virtual environment from scratch.

Commands used:

```bash
rm -rf cyto_cv
python3.11 -m venv cyto_cv
source cyto_cv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt --no-cache-dir
```

Observed details:

- `pip`, `setuptools`, and `wheel` upgraded successfully inside `./cyto_cv`
- Linux correctly ignored the Windows-only dependency marker:

```text
Ignoring tensorflow-intel: markers 'sys_platform == "win32"' don't match your environment
```

- The Python package install completed successfully

## 2. Model Weight Download

The project requires the Mask R-CNN weights file `deepretina_final.h5`. That file was downloaded directly into the repo on the VM.

Commands used:

```bash
gdown --fuzzy "https://drive.google.com/file/d/1moUKvWFYQoWg0z63F0JcSd3WaEPa4UY7/view?usp=sharing" -O ~/CytoCV/cytocv/core/weights/deepretina_final.h5
ls -lh ~/CytoCV/cytocv/core/weights/deepretina_final.h5
```

Observed result:

```text
100%|████████████████████████████████████████████████████████████████████| 256M/256M [00:03<00:00, 77.9MB/s]
-rw-r--r-- 1 ngioanni ngioanni 245M Aug  3  2021 /home/NETID/ngioanni/CytoCV/cytocv/core/weights/deepretina_final.h5
```

## 3. First Migration Attempt Failed Under the Initial DB Configuration

After dependencies and weights were in place, the first migration attempt was run from the Django project directory.

Commands used:

```bash
cd ~/CytoCV/cytocv
python manage.py migrate
```

The migration failed. The important part of the error was:

```text
sqlite3.OperationalError: no such table: accounts_customuser
django.db.utils.OperationalError: no such table: accounts_customuser
```

This showed that the app was not in a clean production database state and that the current database path was not going to work as-is.

## 4. Switched to PostgreSQL on the VM

The deployment was then switched over to the intended production database backend: PostgreSQL.

Commands used:

```bash
cd ~/CytoCV
deactivate 2>/dev/null || true
source cyto_cv/bin/activate
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
sudo systemctl status postgresql --no-pager
```

Observed result:

- PostgreSQL installed successfully
- `postgresql.service` was enabled
- service status showed active

Relevant status line:

```text
Active: active (exited)
```

That is normal for the top-level PostgreSQL service wrapper on Ubuntu.

## 5. Database Role and Database Creation

At first, only the PostgreSQL role was created or altered, but the database itself had not yet been created. That caused confusion until the database list was checked explicitly.

Commands used during this phase:

```bash
sudo -u postgres psql -c "CREATE ROLE cytocv_user WITH LOGIN PASSWORD 'YOUR_DB_PASSWORD';"
sudo -u postgres psql -c "ALTER ROLE cytocv_user WITH LOGIN PASSWORD 'YOUR_DB_PASSWORD';"
sudo -u postgres psql -c "\du"
sudo -u postgres psql -c "\l"
```

Important observed state:

- `cytocv_user` existed
- `cytocv` did not yet exist
- the database list initially only showed:
  - `postgres`
  - `template0`
  - `template1`

The missing database was then created.

Command used:

```bash
sudo -u postgres psql -c "CREATE DATABASE cytocv OWNER cytocv_user;"
sudo -u postgres psql -c "\l"
```

Observed result:

```text
cytocv    | cytocv_user | UTF8
```

At that point the PostgreSQL side was correct:

- role: `cytocv_user`
- database: `cytocv`

## 6. `.env` Handling During Production Setup

The server already had a `.env` file, so it was not overwritten wholesale with a heredoc. Instead, the file was edited in place.

Command used:

```bash
nano ~/CytoCV/.env
```

Key production settings that needed to exist in that file:

```env
CYTOCV_SECRET_KEY=<generated secret>
CYTOCV_DEBUG=0
CYTOCV_ALLOWED_HOSTS=localhost,127.0.0.1,140.142.158.14,cytocv.uwb.edu
CYTOCV_DB_BACKEND=postgres
CYTOCV_DB_NAME=cytocv
CYTOCV_DB_USER=cytocv_user
CYTOCV_DB_PASSWORD=<db password>
CYTOCV_DB_HOST=127.0.0.1
CYTOCV_DB_PORT=5432
CYTOCV_DB_CONN_MAX_AGE=60
CYTOCV_DB_ATOMIC_REQUESTS=0
CYTOCV_DB_SSLMODE=prefer
```

Two generated secret values were needed during this work:

```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

These were used for:

- PostgreSQL password
- `CYTOCV_SECRET_KEY`

## 7. Password Authentication Failure Against PostgreSQL

Once Django was pointed at PostgreSQL, the next failure was an authentication mismatch between the password stored in `.env` and the password stored on the PostgreSQL role.

The failing command was:

```bash
cd ~/CytoCV/cytocv
python manage.py migrate
```

Important error:

```text
psycopg.OperationalError: connection failed
FATAL:  password authentication failed for user "cytocv_user"
```

Fix used:

1. Read the password from `.env`
2. Make PostgreSQL use that exact same password

Commands used:

```bash
grep '^CYTOCV_DB_PASSWORD=' ~/CytoCV/.env
sudo -u postgres psql -c "ALTER ROLE cytocv_user WITH LOGIN PASSWORD 'PASTE_THE_EXACT_PASSWORD_FROM_ENV_HERE';"
```

After that, password mismatch was resolved.

## 8. Migration Graph Failure Caused by Missing Tracked Migrations

The next major problem was not PostgreSQL. It was the migration graph inside the repository.

Commands used:

```bash
cd ~/CytoCV/cytocv
python manage.py migrate
python manage.py migrate accounts
python manage.py migrate core
python manage.py makemigrations accounts core
python manage.py migrate
```

Observed failures:

1. App-specific migrate commands failed because Django did not see migrations for those apps:

```text
CommandError: App 'accounts' does not have migrations.
CommandError: App 'core' does not have migrations.
```

2. After creating local migrations, the migration graph still failed:

```text
django.db.migrations.exceptions.NodeNotFoundError:
Migration core.0007_uploadedimage_scale_info dependencies reference nonexistent parent node
('core', '0006_remove_cellstatistics_gfp_drift_any_and_more')
```

At that point the migration directories were inspected.

Commands used:

```bash
cd ~/CytoCV
find cytocv/accounts/migrations -maxdepth 1 -type f | sort
find cytocv/core/migrations -maxdepth 1 -type f | sort
git status --short
git restore cytocv/accounts/migrations cytocv/core/migrations
```

Observed result:

```text
cytocv/accounts/migrations/0001_initial.py
cytocv/accounts/migrations/__init__.py
cytocv/core/migrations/0001_initial.py
cytocv/core/migrations/0007_uploadedimage_scale_info.py
cytocv/core/migrations/__init__.py
error: pathspec 'cytocv/accounts/migrations' did not match any file(s) known to git
```

That proved the problem was repository-side:

- Git was not tracking the real migration chain
- the VM only had:
  - newly generated `0001_initial.py` files
  - an orphaned tracked `core/migrations/0007_uploadedimage_scale_info.py`

## 9. VM-Only Migration Recovery Used to Get the Schema Built

The repo could not be restored cleanly from Git on the VM, so the deployment used a local recovery path to unblock the server.

Commands used:

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

This was the recovery that allowed the VM database schema to be created.

Important note:

- this fixed the deployed VM
- this did not fix the underlying repository migration tracking issue

## 10. Initial App Launch Under Django `runserver`

Once the migrations were recovered and applied, the app was first launched with Django's development server.

Command used:

```bash
python manage.py runserver 0.0.0.0:8000
```

This confirmed that the application could boot, but it immediately exposed an external host validation issue.

## 11. `DisallowedHost` on Public IP Access

When browsing to the server by IP, Django rejected the host header.

Observed error:

```text
DisallowedHost at /
Invalid HTTP_HOST header: '140.142.158.14:8000'. You may need to add '140.142.158.14' to ALLOWED_HOSTS.
```

This was fixed by editing `.env` again and making the production host list explicit.

Command used:

```bash
nano ~/CytoCV/.env
```

Relevant values:

```env
CYTOCV_DEBUG=0
CYTOCV_ALLOWED_HOSTS=localhost,127.0.0.1,140.142.158.14,cytocv.uwb.edu
CYTOCV_RECAPTCHA_EXPECTED_HOSTNAMES=localhost,127.0.0.1,140.142.158.14,cytocv.uwb.edu
```

After editing `.env`, the server was restarted and the external host error was resolved.

## 12. Gunicorn Validation Before `systemd`

Before creating a permanent service, Gunicorn was started manually to confirm the WSGI app could boot correctly.

Commands used:

```bash
cd ~/CytoCV
source cyto_cv/bin/activate
cd ~/CytoCV/cytocv
gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 120 cytocv.wsgi:application
```

Observed result:

```text
[INFO] Starting gunicorn 25.1.0
[INFO] Listening at: http://0.0.0.0:8000
[INFO] Booting worker with pid: ...
```

Verification command from a second SSH session:

```bash
ss -ltnp | grep 8000
```

Observed result:

```text
LISTEN 0 2048 0.0.0.0:8000 0.0.0.0:* users:(("gunicorn",pid=...,fd=3), ...)
```

That validated Gunicorn before committing it to `systemd`.

## 13. Gunicorn `systemd` Service Creation

After the manual Gunicorn test succeeded, a permanent `systemd` service was created.

Service file path:

```text
/etc/systemd/system/cytocv.service
```

Service file contents used:

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

Observed result:

```text
Active: active (running)
Listening at: http://127.0.0.1:8000
```

At that point Gunicorn was running correctly behind the local interface.

## 14. Nginx Installation and Reverse Proxy Setup

Nginx was installed next and configured as the public-facing reverse proxy.

Commands used:

```bash
sudo apt install -y nginx
sudo systemctl enable --now nginx
```

Initial Nginx site config was created at:

```text
/etc/nginx/sites-available/cytocv
```

Initial config content used:

```nginx
server {
    listen 80;
    server_name cytocv.uwb.edu 140.142.158.14;

    client_max_body_size 100M;

    location /media/ {
        alias /home/NETID/ngioanni/CytoCV/cytocv/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Commands used to enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/cytocv /etc/nginx/sites-enabled/cytocv
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status nginx --no-pager
```

Observed result:

```text
nginx: configuration file /etc/nginx/nginx.conf test is successful
Active: active (running)
```

## 15. HTTPS With Certbot

Once HTTP reverse proxying was working, HTTPS was enabled with Let's Encrypt.

Commands used:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d cytocv.uwb.edu
```

Interactive answers used:

- email: `ngioanni@uw.edu`
- terms of service: `Y`
- EFF emails: `N`

Observed result:

```text
Successfully received certificate.
Successfully deployed certificate for cytocv.uwb.edu to /etc/nginx/sites-enabled/cytocv
Congratulations! You have successfully enabled HTTPS on https://cytocv.uwb.edu
```

Verification command:

```bash
curl -I https://cytocv.uwb.edu
```

Observed result:

```text
HTTP/1.1 200 OK
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

## 16. reCAPTCHA Domain Debugging

After the site was live, the login page showed:

```text
ERROR for site owner:
Invalid domain for site key
```

The root mistake was that the reCAPTCHA admin console had been given a full URL rather than a hostname.

Incorrect format:

```text
https://cytocv.uwb.edu/
```

Correct format:

```text
cytocv.uwb.edu
```

The reCAPTCHA key type also mattered. The working requirement for the current app is:

- reCAPTCHA v2
- Checkbox widget

The app is using the classic browser-side widget and classic `siteverify` backend flow, not a native reCAPTCHA Enterprise integration flow.

Relevant `.env` values:

```env
CYTOCV_RECAPTCHA_ENABLED=1
CYTOCV_RECAPTCHA_SITE_KEY=<site key>
CYTOCV_RECAPTCHA_SECRET_KEY=<secret key>
CYTOCV_RECAPTCHA_EXPECTED_HOSTNAMES=cytocv.uwb.edu
```

## 17. Google OAuth Redirect URI Debugging

Google sign-in initially failed with:

```text
Error 400: redirect_uri_mismatch
```

The important request detail reported by Google was:

```text
redirect_uri=https://cytocv.uwb.edu/signin/oauth/google/login/callback/
```

That meant the app's actual Google callback path was:

```text
https://cytocv.uwb.edu/signin/oauth/google/login/callback/
```

The matching Google OAuth configuration that had to be added was:

- Authorized JavaScript origin:

```text
https://cytocv.uwb.edu
```

- Authorized redirect URI:

```text
https://cytocv.uwb.edu/signin/oauth/google/login/callback/
```

Later, Google also returned:

```text
Error 401: invalid_client
The OAuth client was not found.
```

That indicated the VM `.env` values for:

```env
CYTOCV_GOOGLE_CLIENT_ID
CYTOCV_GOOGLE_CLIENT_SECRET
```

still needed to match the actual Google OAuth client being edited in Google Cloud.

## 18. Microsoft Entra Redirect URI and App-Side Failure

Microsoft Entra sign-in got further than Google. Provider-side auth succeeded, but the callback failed inside the Django app.

The callback URI used for Entra was:

```text
https://cytocv.uwb.edu/signin/oauth/microsoft/login/callback/
```

Commands used to inspect the failure:

```bash
sudo journalctl -u cytocv -n 100 --no-pager
sudo journalctl -u cytocv -n 200 --no-pager
```

Important log findings:

- token exchange succeeded
- `graph.microsoft.com /me` succeeded
- the app then crashed while trying to send a verification email

Critical traceback portion:

```text
send_verification_email_at_login
...
django.core.mail.backends.smtp.py
...
OSError: [Errno 16] Device or resource busy
```

This established that the Entra failure was not primarily an OAuth routing problem. It was an email verification / SMTP problem.

## 19. Email Verification and SMTP Were Not Yet Production-Ready

The app was configured in a way that still expected working SMTP for verification flows.

Relevant email keys discussed:

```env
CYTOCV_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
CYTOCV_EMAIL_HOST=smtp.gmail.com
CYTOCV_EMAIL_HOST_USER=
CYTOCV_EMAIL_HOST_PASSWORD=
CYTOCV_EMAIL_PORT=587
CYTOCV_EMAIL_USE_TLS=1
CYTOCV_EMAIL_USE_SSL=0
CYTOCV_EMAIL_TIMEOUT=
CYTOCV_ACCOUNT_EMAIL_VERIFICATION=mandatory
CYTOCV_DEFAULT_FROM_EMAIL=no-reply@cytocv.uwb.edu
CYTOCV_EMAIL_REPLY_TO=no-reply@cytocv.uwb.edu
```

The deployment conclusion here was:

- the app still needed UW IT help to provide:
  - an approved sender address such as `no-reply@cytocv.uwb.edu`
  - SMTP host/port/TLS settings
  - account credentials or app password

Until SMTP is configured correctly, `mandatory` email verification can break provider login flows even when OAuth itself succeeds.

## 20. Protected Media Route Conflict With Nginx

After deployment, some image assets in the app were not rendering correctly.

The cause was the initial Nginx config:

```nginx
location /media/ {
    alias /home/NETID/ngioanni/CytoCV/cytocv/media/;
}
```

The application actually serves `/media/...` through Django with login and ownership checks, so Nginx was short-circuiting the protected route.

Fix used:

- remove the `/media/` alias block from the Nginx site config
- keep the main `location /` proxy block so `/media/...` requests go to Django

Commands used:

```bash
sudo nano /etc/nginx/sites-available/cytocv
sudo nginx -t
sudo systemctl reload nginx
```

## 21. Start Analysis Appeared to "Reload the Page"

Once the web app was deployed, clicking `Start Analysis` on the preprocess page did not move the workflow forward. It appeared to just reload the page.

To debug this, live logs were tailed:

```bash
sudo journalctl -u cytocv -f
```

The important log lines were not Django form errors. They were Gunicorn worker crashes:

```text
[WARNING] Worker (pid:...) was sent SIGILL!
```

That was the critical clue that the failure was happening inside native code used by the ML pipeline.

## 22. TensorFlow Crash and AVX-Incompatible VM CPU

This was the decisive blocker for the analysis pipeline.

Commands used:

```bash
cd ~/CytoCV
source cyto_cv/bin/activate
python -c "import tensorflow as tf; print(tf.__version__)"
```

Observed result:

```text
Illegal instruction (core dumped)
```

The next direct runtime test also crashed:

```bash
cd ~/CytoCV/cytocv
python manage.py shell -c "from core.mrcnn.inference_runtime import get_inference_runtime; print('loading runtime'); get_inference_runtime(); print('runtime ok')"
```

Observed result:

```text
loading runtime
Illegal instruction (core dumped)
```

The import-only test below did not prove anything about TensorFlow because it failed earlier on missing Django settings:

```bash
python -c "from core.mrcnn.my_inference import predict_images; print('predict import ok')"
```

Observed error:

```text
django.core.exceptions.ImproperlyConfigured:
Requested setting AUTH_USER_MODEL, but settings are not configured.
```

That error was unrelated to the native TensorFlow crash.

The CPU flags were then inspected.

Commands used:

```bash
lscpu | grep -i avx
lscpu
```

Observed result:

- `lscpu | grep -i avx` returned nothing
- the VM showed:

```text
Model name: QEMU Virtual CPU version 2.5+
Flags: fpu de pse tsc ... sse4_1 sse4_2 ...
```

but no `avx` or `avx2`

### Conclusion

The web deployment succeeded, but the analysis pipeline cannot run on this VM as currently provisioned because:

- TensorFlow crashes on import
- the VM CPU does not expose `AVX`
- the deployed TensorFlow wheel requires CPU features this VM does not provide

### Practical implication

The app stack is deployed, but scientific analysis is still blocked until one of these happens:

1. UW IT provides a VM/host with AVX-capable CPU features exposed
2. the analysis workload is moved to separate compatible compute infrastructure
3. the Python/ML runtime is rebuilt around a TensorFlow build that works on a non-AVX CPU, which is a much less attractive path

## 23. Commands Used for Final Service Verification

These commands were used to confirm the deployed stack was alive:

```bash
curl -I https://cytocv.uwb.edu
sudo systemctl status cytocv --no-pager
sudo systemctl status nginx --no-pager
sudo journalctl -u cytocv -n 100 --no-pager
```

Important observed successful state:

- `https://cytocv.uwb.edu` returned `HTTP/1.1 200 OK`
- `cytocv.service` was active
- `nginx.service` was active

## 24. Follow-Up Work Still Needed After This Deployment

This deployment got the app online, but the following work remained:

1. Fix migration tracking in the repository.
- The VM recovery worked locally, but the repo still needs proper migration files committed and tracked.

2. Finish production email setup.
- Need UW IT-approved sender address and SMTP settings.

3. Finish provider auth alignment.
- Make sure Google and Microsoft `.env` client values exactly match the cloud-side app registrations.

4. Resolve the compute blocker.
- Move analysis to AVX-capable infrastructure or re-provision the VM accordingly.

## 25. One-Paragraph Summary

CytoCV was successfully deployed on the UWB VM with PostgreSQL, Gunicorn under `systemd`, Nginx, and HTTPS at `https://cytocv.uwb.edu`. The deployment required recovering from a broken migration situation caused by missing tracked migrations in the repository, fixing PostgreSQL role/database configuration, correcting `ALLOWED_HOSTS`, and configuring Gunicorn, Nginx, and Certbot manually. Post-deployment debugging showed reCAPTCHA and OAuth still needed cloud-side configuration cleanup, Microsoft Entra login was blocked by missing SMTP/email verification infrastructure, and the analysis pipeline itself cannot run on the current VM because TensorFlow crashes with `Illegal instruction` on a CPU that does not expose `AVX`.
