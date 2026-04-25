# CytoCV `systemd` Units

These files are production-oriented example units for Linux hosts that run:

- Gunicorn for the web process
- a separate long-lived background worker for upload preparation and analysis

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
sudo systemctl enable cytocv-worker
sudo systemctl restart cytocv
sudo systemctl restart cytocv-worker
```

## Notes

- The Django application reads `~/CytoCV/.env` directly, so these units do not
  require an `EnvironmentFile=` entry just to load application settings.
- Keep `CYTOCV_ANALYSIS_EXECUTION_MODE=worker` in the deployed `.env` for
  production analysis. The worker service should still be enabled because
  staged upload preparation uses it in both analysis modes.
- Adjust Gunicorn worker count and timeout to match the deployment host.
