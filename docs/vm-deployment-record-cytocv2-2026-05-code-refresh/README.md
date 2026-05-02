# CytoCV VM Deployment Record (cytocv2 Code Refresh, May 2026)

This is a sanitized historical summary of the May 2026 production code refresh
on the replacement CytoCV Linux VM. It documents what was deployed, how the
existing deployment was updated, what data was preserved, and what verification
was completed without recording live hostnames, IP addresses, usernames,
passwords, SSH key paths, database credentials, or exact private filesystem
paths.

This document is historical context, not the active deployment recipe. For
current deployment guidance, use:

- [`../vm-deployment-guide/README.md`](../vm-deployment-guide/README.md)
- [`../ops/deployment-guide.md`](../ops/deployment-guide.md)
- [`../ops/environment-reference.md`](../ops/environment-reference.md)
- [`../../deploy/systemd/README.md`](../../deploy/systemd/README.md)

## What This Code Refresh Achieved

This refresh updated the existing production VM after pull request `#234`
merged into `main`. The deployed application moved from the previous production
commit to the new `main` merge commit `9018881e`.

The update preserved existing user data:

- no database flush was run
- no media cleanup was run
- no `git clean` or destructive filesystem cleanup was run
- the PostgreSQL database, uploaded media, collected static output, and local
  deployment artifacts were left in place

The deployment brought the VM onto the code that includes:

- raw-channel intensity measurement improvements for analysis plugins
- automatic cell parentage support and expanded parentage metadata
- plugin dependency expansion and plugin UI ordering improvements
- consolidated dot-detection and contour option handling
- clarified execution-mode documentation for upload preparation and analysis
- public page, collaborators page, navigation, and copy refinements
- additional automated test coverage for parentage, statistics, upload
  preparation, preferences, and tables

## Update Path Used

The VM was accessed through the previously prepared SSH key workflow. The
checkout was an existing deployment checkout, not a fresh clone.

The update started by checking the repository state and fetching upstream
changes:

```bash
cd /path/to/CytoCV
git status
git fetch origin
git pull --ff-only origin main
```

The deployed checkout was on a maintainer/deployment branch name rather than a
local branch named `main`. That did not block deployment because the checkout
could fast-forward cleanly to `origin/main`.

Two untracked deployment-local paths were present:

- a local SQL backup artifact from an earlier maintenance session
- the generated `cytocv/staticfiles/` directory

Both were intentionally preserved. The staticfiles directory is expected on
this VM because collected static assets are generated locally during deployment.

## Django Validation And Static Assets

After the fast-forward, the virtual environment was activated and Django checks
were run from the project directory:

```bash
source cyto_cv/bin/activate
cd cytocv

python manage.py migrate
python manage.py check
python manage.py collectstatic --noinput
```

The result was:

- migrations reported no pending work
- `python manage.py check` reported no issues
- `collectstatic` completed successfully
- four static files were copied and the remaining collected files were already
  current

Because no migrations were pending and no reset command was run, the database
schema and existing application data remained intact.

## Process Restart And Nginx Reload

The supervised services were restarted through `systemd`:

```bash
sudo systemctl restart cytocv
sudo systemctl restart cytocv-upload-prep-worker
sudo systemctl restart cytocv-analysis-worker
sudo systemctl restart cytocv-artifact-maintenance.timer
```

Nginx was validated and reloaded:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

The Nginx syntax check succeeded before reload.

## Final Service State

Post-restart status checks showed the expected active deployment shape:

- `cytocv.service` was active with Gunicorn master and worker processes running
- `cytocv-upload-prep-worker.service` was active
- `cytocv-analysis-worker.service` was active
- `cytocv-artifact-maintenance.timer` was active and waiting for its next run

The current web-service journal after the restart showed clean Gunicorn startup
and worker boot messages. An older pre-refresh reCAPTCHA log entry was visible
in the journal history, but it preceded the deployment restart and was not a
service startup failure.

## Issues Encountered And Resolved

- The checkout reported that its local branch was ahead of the branch it
  tracked. The deployment was still safe because `git pull --ff-only origin
  main` advanced the checkout cleanly to the merged production commit.
- Untracked deployment-local files were present. They were reviewed and left in
  place because they represented local backup/static output rather than source
  conflicts.
- The goal was a code refresh with user data preservation. The earlier
  destructive reset path was intentionally not used, so existing PostgreSQL and
  media state remained available after the update.
- Service output included older journal history. The relevant post-refresh
  entries showed clean process startup for the web service and active state for
  both workers and the maintenance timer.

## What To Carry Forward

- For data-preserving updates, use the existing-VM code update path and avoid
  `flush`, `git clean`, media deletion, or manual database cleanup.
- Treat `cytocv/staticfiles/` as deployment-generated output unless there is a
  specific static-file cleanup plan.
- A local deployment branch name does not need to be `main`, but the update
  should stop if `git pull --ff-only origin main` cannot fast-forward.
- Run `migrate`, `check`, and `collectstatic` after pulling new code.
- Restart the web service, upload-preparation worker, analysis worker, and
  artifact-maintenance timer together after a code update.
- Validate Nginx before reloading it.
- Review current post-restart log entries rather than treating older journal
  history as evidence of a current deployment failure.
