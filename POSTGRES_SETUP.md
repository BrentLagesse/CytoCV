# PostgreSQL Setup for CytoCV

This guide covers:
- Local developer setup (Windows PowerShell)
- Production VM setup (Ubuntu/Debian style)
- Teammate onboarding steps

Database policy:
- PostgreSQL is the production backend.
- SQLite is local dev/test convenience only and is blocked when `CYTOCV_DEBUG=0`.

## 1) App Env Variables (required)

CytoCV uses these keys when `CYTOCV_DB_BACKEND=postgres`:

```env
CYTOCV_DB_BACKEND=postgres
CYTOCV_DB_NAME=cytocv
CYTOCV_DB_USER=cytocv_user
CYTOCV_DB_PASSWORD=<strong-password>
CYTOCV_DB_HOST=127.0.0.1
CYTOCV_DB_PORT=5432
CYTOCV_DB_CONN_MAX_AGE=60
CYTOCV_DB_ATOMIC_REQUESTS=0
CYTOCV_DB_SSLMODE=prefer
```

Notes:
- `CYTOCV_DB_NAME`, `CYTOCV_DB_USER`, `CYTOCV_DB_PASSWORD` are required.
- `CYTOCV_DB_HOST=127.0.0.1` is correct when DB is on same machine as app.
- In production, SQLite is blocked when `CYTOCV_DEBUG=0`.

## 2) Local Setup (Windows)

### 2.1 Ensure Postgres is running
- If installed as a service, start it from Services.
- If using extracted binaries, start `postgres` for your initialized data directory.

### 2.2 Create role + database

Open `psql` as an admin/superuser and run:

```sql
CREATE ROLE cytocv_user WITH LOGIN PASSWORD 'replace_with_strong_password';
CREATE DATABASE cytocv OWNER cytocv_user;
```

### 2.3 Update `.env`

Set:

```env
CYTOCV_DB_BACKEND=postgres
CYTOCV_DB_NAME=cytocv
CYTOCV_DB_USER=cytocv_user
CYTOCV_DB_PASSWORD=replace_with_strong_password
CYTOCV_DB_HOST=127.0.0.1
CYTOCV_DB_PORT=5432
CYTOCV_DB_CONN_MAX_AGE=60
CYTOCV_DB_ATOMIC_REQUESTS=0
CYTOCV_DB_SSLMODE=prefer
```

### 2.4 Apply schema and verify

From `cytocv/`:

```powershell
python manage.py migrate
python manage.py check
```

## 3) Production VM Setup (Linux)

### 3.1 Install and start PostgreSQL

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
```

### 3.2 Create least-privileged app role + DB

```bash
sudo -u postgres psql -c "CREATE ROLE cytocv_user WITH LOGIN PASSWORD 'replace_with_strong_password';"
sudo -u postgres psql -c "CREATE DATABASE cytocv OWNER cytocv_user;"
```

### 3.3 Use local-only DB networking (same VM deployment)

In `postgresql.conf`, keep:

```conf
listen_addresses = '127.0.0.1'
```

Then reload:

```bash
sudo systemctl reload postgresql
```

### 3.4 Fill production env on server

In server `.env` (or equivalent systemd env file):

```env
CYTOCV_DB_BACKEND=postgres
CYTOCV_DB_NAME=cytocv
CYTOCV_DB_USER=cytocv_user
CYTOCV_DB_PASSWORD=replace_with_strong_password
CYTOCV_DB_HOST=127.0.0.1
CYTOCV_DB_PORT=5432
CYTOCV_DB_CONN_MAX_AGE=60
CYTOCV_DB_ATOMIC_REQUESTS=0
CYTOCV_DB_SSLMODE=prefer
```

### 3.5 Migrate and verify app DB connectivity

```bash
python manage.py migrate
python manage.py check
```

## 4) Teammate Onboarding (quick)

If a teammate pulls your branch, they still must provision Postgres locally.

Minimum steps:
1. Install/start Postgres.
2. Create `cytocv_user` role and `cytocv` database.
3. Set DB vars in their `.env`.
4. Run:
   - `python manage.py migrate`
   - `python manage.py check`

## 5) Common Errors

- `ImproperlyConfigured: Missing required PostgreSQL settings`:
  - One of `CYTOCV_DB_NAME`, `CYTOCV_DB_USER`, `CYTOCV_DB_PASSWORD` is empty.

- `connection refused`:
  - Postgres not running or wrong host/port.

- `password authentication failed for user`:
  - `CYTOCV_DB_PASSWORD` does not match role password.

- `database "cytocv" does not exist`:
  - Create DB and rerun migrations.
