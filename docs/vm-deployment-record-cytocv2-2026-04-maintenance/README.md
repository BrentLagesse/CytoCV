# CytoCV VM Deployment Record (cytocv2 Maintenance Refresh, April 2026)

This is a sanitized historical summary of the April 2026 maintenance refresh on
the replacement CytoCV Linux VM. It preserves operational lessons without
recording live hostnames, IP addresses, usernames, passwords, key material,
database credentials, or exact private filesystem paths.

This document is historical context, not the active deployment recipe. For
current deployment guidance, use:

- [`../vm-deployment-guide/README.md`](../vm-deployment-guide/README.md)
- [`../ops/deployment-guide.md`](../ops/deployment-guide.md)
- [`../ops/environment-reference.md`](../ops/environment-reference.md)
- [`../../deploy/systemd/README.md`](../../deploy/systemd/README.md)

## What This Maintenance Refresh Achieved

This refresh brought the existing VM deployment back in line with the current
repository state and intentionally reset stored application data:

- confirmed interactive SSH access to the replacement VM
- added a dedicated operator SSH key path for future access
- located the active repository checkout and deployment `.env`
- fast-forwarded the deployed checkout to `origin/main`
- preserved the existing PostgreSQL database and schema while deleting stored
  application rows through Django
- confirmed `migrate` and `check` completed successfully
- restarted the web service, upload-preparation worker, analysis worker, and
  artifact-maintenance timer
- confirmed the expected `systemd` services were active after restart

## Access And Checkout Discovery

The initial access issue was not network reachability. Verbose SSH output showed
that the client could reach the server and that the server allowed public-key
and password authentication, but no local private keys were available. Password
access succeeded after confirming the correct replacement-VM hostname.

The maintenance path then created a dedicated Ed25519 SSH key on the operator
machine and installed the public key for the deploy account. Two details matter
for future maintainers:

- the `Host ...` SSH alias block belongs in the client-side SSH config, not in
  the remote Linux shell
- `authorized_keys` on the VM should contain the full one-line public key,
  starting with `ssh-ed25519`, with no shell prompt text copied into the file

If the local SSH agent cannot be started because of workstation permissions,
the key can still be used explicitly with `ssh -i` until the agent is configured
by an administrator.

The active checkout was not in the shell's current directory. The reliable
discovery command was:

```bash
find ~ -maxdepth 3 -type d -name "CytoCV"
```

The `.env` file was then edited from the real checkout path. Placeholder paths
such as `/path/to/CytoCV/.env` should never be used literally.

## Code Refresh Path

The deployed repository was on a maintainer/deployment branch name rather than
a local branch named `main`. The update was still clean because the checkout
could fast-forward to `origin/main`.

The safe command pattern was:

```bash
cd /path/to/CytoCV
git status
git branch --show-current
git fetch origin
git pull --ff-only origin main
git log --oneline -5
```

An untracked `cytocv/staticfiles/` directory was present. That directory is
expected when collected static files are generated on the VM and should not be
deleted as part of a normal code refresh.

After the pull, the deployment path remained:

```bash
source cyto_cv/bin/activate
cd cytocv
python manage.py migrate
python manage.py check
python manage.py collectstatic --noinput
```

For this refresh, migrations reported no pending work and Django checks passed.

## Database Reset Path

The goal was to delete application data while keeping the PostgreSQL database
itself. The services were stopped first so Gunicorn and the workers could not
read or write jobs during the reset:

```bash
sudo systemctl stop cytocv
sudo systemctl stop cytocv-upload-prep-worker
sudo systemctl stop cytocv-analysis-worker
sudo systemctl stop cytocv-artifact-maintenance.timer
```

The data reset used Django's schema-preserving flush path:

```bash
cd /path/to/CytoCV
source cyto_cv/bin/activate
cd /path/to/CytoCV/cytocv
python manage.py flush
python manage.py migrate
python manage.py check
```

This removed database rows but kept the database and schema. It did not remove
uploaded media or collected static files from disk.

A backup command was attempted after the flush and failed because `pg_dump`
defaulted to the Linux account instead of the configured PostgreSQL role. That
did not modify the database. For future resets, run the backup before flushing
and pass the configured database user explicitly:

```bash
cd /path/to/CytoCV
set -a
source .env
set +a

PGPASSWORD="$CYTOCV_DB_PASSWORD" pg_dump \
  -h "${CYTOCV_DB_HOST:-127.0.0.1}" \
  -p "${CYTOCV_DB_PORT:-5432}" \
  -U "$CYTOCV_DB_USER" \
  "$CYTOCV_DB_NAME" > cytocv-before-flush.sql
```

## Service Restart And Verification

After the flush, the deployment services were started again:

```bash
sudo systemctl start cytocv
sudo systemctl start cytocv-upload-prep-worker
sudo systemctl start cytocv-analysis-worker
sudo systemctl start cytocv-artifact-maintenance.timer
```

The expected final service state was:

- `cytocv.service` active with Gunicorn workers running
- `cytocv-upload-prep-worker.service` active
- `cytocv-analysis-worker.service` active
- `cytocv-artifact-maintenance.timer` active and waiting for its next run

The web-service journal showed clean Gunicorn startup after the refresh. Older
pre-refresh logs still contained an account-email logo MIME subtype error; the
code refresh included the related fix, and the latest checked startup logs did
not show a current service failure. A full signup/email smoke test should remain
part of final user-facing validation whenever account email behavior changes.

Nginx configuration was not changed during this maintenance refresh. The
documented verification path remains:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Issues Encountered And Resolved

- A placeholder `.env` path was initially used literally. The resolution was to
  locate the real checkout and edit `.env` from the actual repository path.
- SSH authentication initially failed against an earlier host target. Verbose
  SSH confirmed the failure was authentication-related rather than a network
  problem; the replacement-VM hostname and a dedicated SSH key path resolved the
  access workflow.
- The client-side SSH config block was accidentally pasted into the remote
  shell. The resolution was to keep `Host`, `HostName`, `User`, and
  `IdentityFile` in the workstation SSH config only.
- Windows SSH agent setup required elevated permissions. The immediate
  resolution was to use `ssh -i` explicitly; agent setup can be handled later
  from an elevated shell.
- The deployed checkout was not named `main`, but it fast-forwarded cleanly to
  `origin/main`. Future maintainers should stop if `--ff-only` fails.
- A post-flush `pg_dump` attempt failed because it used the default Linux user
  instead of the configured PostgreSQL role. Future backup commands should load
  `.env` and pass `-U "$CYTOCV_DB_USER"` before any destructive reset.

## What To Carry Forward

- Confirm the exact VM hostname before debugging credentials.
- Prefer dedicated SSH keys and keep public key material as a single line in
  `authorized_keys`.
- Locate existing checkouts with `find` before editing deployment files.
- Use `git pull --ff-only origin main` for clean updates and stop on divergence.
- Run `migrate`, `check`, and `collectstatic` after code refreshes.
- Stop Gunicorn and both workers before intentionally flushing production data.
- Back up PostgreSQL with the configured database role before flushing.
- Treat `cytocv/staticfiles/` as deployment-generated output unless there is a
  deliberate static-file cleanup plan.
