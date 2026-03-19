# PostgreSQL Setup For CytoCV

## Purpose

This guide covers the PostgreSQL configuration required when `CYTOCV_DB_BACKEND=postgres`.

## Required Environment Variables

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

Required fields:

- `CYTOCV_DB_NAME`
- `CYTOCV_DB_USER`
- `CYTOCV_DB_PASSWORD`

## Local Windows Setup

### Step 1: Ensure PostgreSQL Is Running

- start the PostgreSQL Windows service, or
- start the database manually if you use an extracted installation

### Step 2: Create Role And Database

Open `psql` as an administrative user and run:

```sql
CREATE ROLE cytocv_user WITH LOGIN PASSWORD 'replace_with_strong_password';
CREATE DATABASE cytocv OWNER cytocv_user;
```

### Step 3: Update `.env`

Set the PostgreSQL environment values shown above.

### Step 4: Apply Schema

From `cytocv/`:

```powershell
python manage.py migrate
python manage.py check
```

## Production VM Setup

### Step 1: Install PostgreSQL

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
```

### Step 2: Create App Role And Database

```bash
sudo -u postgres psql -c "CREATE ROLE cytocv_user WITH LOGIN PASSWORD 'replace_with_strong_password';"
sudo -u postgres psql -c "CREATE DATABASE cytocv OWNER cytocv_user;"
```

### Step 3: Keep Database Networking Local To The Host

Recommended `postgresql.conf` value for same-host deployment:

```conf
listen_addresses = '127.0.0.1'
```

Reload:

```bash
sudo systemctl reload postgresql
```

### Step 4: Apply App Schema

```bash
python manage.py migrate
python manage.py check
```

## Common Errors

- missing required PostgreSQL settings
  One of the required DB variables is blank.
- connection refused
  PostgreSQL is not running or the host and port are incorrect.
- password authentication failed
  The configured password does not match the role.
- database does not exist
  The target database was not created before migration.

## Related Documents

- [`environment-reference.md`](environment-reference.md)
- [`deployment-guide.md`](deployment-guide.md)
