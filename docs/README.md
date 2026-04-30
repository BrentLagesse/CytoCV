# CytoCV Documentation

This directory is the canonical documentation home for CytoCV. The root `README.md` is intentionally brief. Detailed operational, scientific, and developer material lives here.

## Audience

- `docs/user/` is the main researcher-facing guide set. `getting-started.md` is for local checkout, evaluation, or maintainer-led setup. `workflow-guide.md` and the related user pages are the main references for researchers using a deployed CytoCV site.
- `docs/developer/`, `docs/reference/`, and `docs/ops/` are maintainer-oriented. They may describe internals, routes, configuration, and deployment behavior, but they should not contain live secrets or environment-specific private values.
- `docs/vm-deployment-*` files are sanitized historical notes. They are not the canonical deployment source of truth.

## Conventions

- Markdown is the canonical source format.
- PDFs in `docs/research/` are derived formal deliverables.
- Diagrams live in `docs/diagrams/`.
- Obsolete or superseded material should move to `docs/archive/`.
- Historical project records that should remain readable but are not part of the active doc system may remain in dedicated subfolders such as `docs/vm-deployment-record/`, `docs/vm-deployment-record-cytocv2/`, and dated follow-up record folders.

## User Documentation

- [`user/getting-started.md`](user/getting-started.md)
- [`user/workflow-guide.md`](user/workflow-guide.md)
- [`user/account-and-dashboard.md`](user/account-and-dashboard.md)
- [`user/analysis-options.md`](user/analysis-options.md)
- [`user/output-guide.md`](user/output-guide.md)
- [`user/troubleshooting.md`](user/troubleshooting.md)

## Developer Documentation

- [`developer/architecture-overview.md`](developer/architecture-overview.md)
- [`developer/codebase-map.md`](developer/codebase-map.md)
- [`developer/local-installation-and-troubleshooting.md`](developer/local-installation-and-troubleshooting.md)
- [`developer/windows-local-installer-design.md`](developer/windows-local-installer-design.md)
- [`developer/request-flows.md`](developer/request-flows.md)
- [`developer/data-flow-and-artifacts.md`](developer/data-flow-and-artifacts.md)
- [`developer/extending-analysis.md`](developer/extending-analysis.md)
- [`developer/testing-guide.md`](developer/testing-guide.md)
- [`developer/contributing.md`](developer/contributing.md)

## Operations Documentation

- [`ops/environment-reference.md`](ops/environment-reference.md)
- [`ops/deployment-guide.md`](ops/deployment-guide.md)
- [`ops/postgres-setup.md`](ops/postgres-setup.md)
- [`ops/security-and-privacy.md`](ops/security-and-privacy.md)
- [`ops/backup-retention-and-storage.md`](ops/backup-retention-and-storage.md)

## Reference Documentation

- [`reference/routes-and-endpoints.md`](reference/routes-and-endpoints.md)
- [`reference/data-model.md`](reference/data-model.md)
- [`reference/file-format-and-artifact-spec.md`](reference/file-format-and-artifact-spec.md)
- [`reference/glossary.md`](reference/glossary.md)

## Research Documentation

- [`research/methods-and-system-description.md`](research/methods-and-system-description.md)
- [`research/reproducibility-and-validation.md`](research/reproducibility-and-validation.md)
- [`research/figure-catalog.md`](research/figure-catalog.md)

Formal PDF deliverables:

- [`research/methods-and-system-description.pdf`](research/methods-and-system-description.pdf)
- [`research/reproducibility-and-validation.pdf`](research/reproducibility-and-validation.pdf)
- [`research/figure-catalog.pdf`](research/figure-catalog.pdf)

## Supporting Material

- Diagram catalog: [`diagrams/README.md`](diagrams/README.md)
- Documentation standards: [`templates/document-style-guide.md`](templates/document-style-guide.md)
- License: [`license/README.md`](license/README.md)
- Historical deployment record (first VM): [`vm-deployment-record/README.md`](vm-deployment-record/README.md)
- Historical deployment record (replacement VM): [`vm-deployment-record-cytocv2/README.md`](vm-deployment-record-cytocv2/README.md)
- Historical deployment record (cytocv2 April 2026 maintenance refresh): [`vm-deployment-record-cytocv2-2026-04-maintenance/README.md`](vm-deployment-record-cytocv2-2026-04-maintenance/README.md)
