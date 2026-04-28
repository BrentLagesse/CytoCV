# CytoCV VM Deployment Record (Historical First VM, March 2026)

This is a sanitized historical summary of the first Linux VM rollout for CytoCV. It preserves the main lessons without retaining live hostnames, IP addresses, user paths, secrets, or provider configuration details.

This document is historical context, not the active deployment recipe. For current deployment guidance, use:

- [`../vm-deployment-guide/README.md`](../vm-deployment-guide/README.md)
- [`../ops/deployment-guide.md`](../ops/deployment-guide.md)
- [`../ops/environment-reference.md`](../ops/environment-reference.md)

## What This Rollout Achieved

The first VM rollout successfully brought up the main web stack:

- Django application startup
- PostgreSQL-backed production data
- supervised web serving
- reverse proxy and HTTPS

The deployment reached a usable website state, but it did not reach a fully analysis-capable final state.

## Main Constraints Observed

The key blocker was infrastructure-level, not user-workflow logic:

- the VM CPU environment did not expose `AVX`
- TensorFlow-based analysis could not run on that host
- the site could serve web pages, but image analysis should not have been considered operational there

This is the main lesson to carry forward from the first VM attempt: verify CPU compatibility before treating a host as analysis-ready.

## Other Lessons From That Rollout

- Protected result media needed to stay behind the authenticated application route rather than being exposed directly by the reverse proxy.
- Email-backed verification and provider sign-in depended on separate operational readiness for email delivery and external auth configuration.
- Production deployment still required PostgreSQL, explicit host configuration, and supervised background processing for the worker-owned workflow stages.

## Historical Repository Note

During that March 2026 rollout, the repository state on the VM required migration recovery work.

That migration issue should be treated as historical context for that specific deployment period. The current repository now includes tracked migrations for `accounts` and `core`, so modern deployments should use the normal `python manage.py migrate` path first.

## What To Carry Forward

- Verify `AVX` before treating a VM as analysis-capable.
- Keep protected media behind authenticated access.
- Align email verification policy with working email delivery.
- Keep host-specific commands, service paths, and secrets in private operational records rather than shared repo docs.
