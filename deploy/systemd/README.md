# CytoCV `systemd` Units

These files are production-oriented example units for Linux hosts that run:

- Gunicorn for the web process
- a dedicated upload-preparation worker
- a dedicated analysis worker
- a timer-driven artifact-maintenance sweep

They are intentionally checked into the repository so redeployments do not
depend on hand-recreated service files.

## Usage

1. Copy the desired unit file to `/etc/systemd/system/`.
2. Replace `REPLACE_WITH_DEPLOY_USER` with the actual Linux user that owns the
   checkout and virtual environment.
3. Replace `/home/REPLACE_WITH_DEPLOY_USER/CytoCV/...` paths if the repository
   lives elsewhere.
4. Run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cytocv
sudo systemctl disable --now cytocv-worker || true
sudo systemctl enable cytocv-upload-prep-worker
sudo systemctl enable cytocv-analysis-worker
sudo systemctl enable cytocv-artifact-maintenance.timer
sudo systemctl restart cytocv
sudo systemctl restart cytocv-upload-prep-worker
sudo systemctl restart cytocv-analysis-worker
sudo systemctl restart cytocv-artifact-maintenance.timer
```

## Notes

- The Django application reads `~/CytoCV/.env` directly, so these units do not
  require an `EnvironmentFile=` entry just to load application settings.
- Keep `CYTOCV_ANALYSIS_EXECUTION_MODE=worker` in the deployed `.env` for
  production analysis.
- The upload-preparation worker uses:
  `manage.py run_analysis_worker --job-type upload-preparation --skip-maintenance`
- The analysis worker uses:
  `manage.py run_analysis_worker --job-type analysis --skip-maintenance`
- The maintenance timer uses `manage.py run_artifact_maintenance` every 5 minutes.
- The example Gunicorn unit is intentionally set to `--workers 3` for the
  current production VM sizing. Re-evaluate that number if the host changes.
