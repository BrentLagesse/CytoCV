# CytoCV VM Deployment Record (Historical Replacement VM, March 2026)

This is a sanitized historical summary of the replacement Linux VM rollout for CytoCV. It keeps the main technical lessons without retaining live hostnames, IP addresses, user paths, service file paths, or secret configuration.

This document is historical context, not the active deployment recipe. For current deployment guidance, use:

- [`../vm-deployment-guide/README.md`](../vm-deployment-guide/README.md)
- [`../ops/deployment-guide.md`](../ops/deployment-guide.md)
- [`../ops/environment-reference.md`](../ops/environment-reference.md)

## What This Rollout Achieved

The replacement VM reached a stronger final state than the first attempt:

- the web stack was deployed successfully
- HTTPS and reverse proxying were working
- the host CPU environment was compatible with the ML runtime
- the analysis pipeline could execute on that host

## Main Constraints Observed

This rollout still exposed several maintainer-relevant issues:

- the base operating system did not provide the exact required Python interpreter through the expected package path, so Python `3.11.5` had to be installed through a custom maintainer process
- Linux-specific runtime dependencies for image-processing libraries had to be present
- production static-file serving required explicit collection and proxy configuration
- email-backed account flows remained operationally incomplete until email delivery details were finalized

## Historical Repository Note

During that March 2026 rollout, the deployment again needed migration recovery work on the VM.

That issue should be treated as historical context for that deployment period. The current repository now includes tracked migrations for `accounts` and `core`, so modern deployments should use the standard `python manage.py migrate` path first.

## What To Carry Forward

- Confirm the exact Python interpreter version before provisioning the VM.
- Keep the model weights at `cytocv/core/weights/deepretina_final.h5` unless the runtime is intentionally changed.
- Expect Linux deployment to surface path, case-sensitivity, runtime-library, or static-file issues that may not appear in local Windows development.
- Serve collected static assets and protected run media through separate policies: static assets may be served directly, but protected result assets should continue to require authenticated access through the application.
- Treat email, provider sign-in, and anti-abuse configuration as separate operational milestones rather than assuming they are complete when the web stack first comes up.
