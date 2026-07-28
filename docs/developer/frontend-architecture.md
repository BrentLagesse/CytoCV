# Frontend Architecture

## Purpose

CytoCV's frontend is Django-rendered HTML plus source static assets. It does not use npm, a bundler, TypeScript, or a client framework. Keep changes compatible with Django templates, Django staticfiles, and the backend API contracts documented in the route and request-flow references.

## Folder Structure

- `cytocv/templates/`
  Server-rendered pages, shared layout, and small reusable partials.
- `cytocv/templates/base.html`
  Global page shell, navigation, footer slot, modal shell, and shared static includes.
- `cytocv/templates/partials/`
  Reusable template fragments. The export-selection modal lives here because dashboard and display both render it.
- `cytocv/core/static/css/base.css`
  Global design tokens, layout primitives, navigation, shared messages, modals, and cross-page utilities.
- `cytocv/core/static/css/base-overrides.css`
  Late-loaded global overrides that must remain after page CSS in the cascade.
- `cytocv/core/static/css/components/`
  Shared component CSS used by more than one page or partial. Current shared component files include `results-viewer.css`, `export-selection-modal.css`, and `workflow-controls.css`.
- `cytocv/core/static/css/pages/`
  Page-scoped CSS. A page template should generally load only its matching page file plus needed component CSS.
- `cytocv/core/static/js/shared/`
  Shared browser utilities with stable global APIs.
- `cytocv/core/static/js/pages/`
  Page controllers. These own DOM behavior for one page or one narrow page concern.
- `cytocv/core/static/js/shared/results-cell-actions.js`
  Shared dashboard/display cell action controller, initialized by thin page wrappers.
- `cytocv/core/static/js/export_selection_modal.js`
  Shared export-selection controller. It remains outside `pages/` because both display and dashboard use it.
- `cytocv/core/static/js/viewer_overlay_prefetch.js`
  Shared overlay prefetch controller used by results viewers.
- `cytocv/core/static/js/workflow_defaults.js`
  Existing workflow-defaults controller for account preference editing.

## Template And Static Ownership

Templates own server-rendered markup, forms, Django URL resolution, CSRF tokens, and JSON configuration blocks. Static JavaScript owns browser behavior and must not contain Django template syntax.

When static JavaScript needs server data, add a `script type="application/json"` block with a stable ID in the template and read it from the controller. Current examples:

- `statsPluginPayload`, `restoredQueuePayload`, `serverPreferenceDefaults`, `uploadQuotaProjection`, `uploadAccessPolicy`, `uploadResumePayload`, and `uploadPreparationConfig` in `form/experiment.html`
- `pluginDependencyPayload` in `workflow_defaults.html`
- `preprocessScalePayload` and `preprocessPageConfig` in `pre_process.html`
- `displayFilesData` and `displayPageConfig` in `display.html`
- `dashboardFilesData` and `dashboardPageConfig` in `dashboard.html`
- `exportSelectionConfig` in `partials/export_selection_modal.html`
- `accountSettingsConfig` in `account_settings.html`

Keep request payload names, endpoint paths, response field names, form field names, and template context expectations unchanged unless a backend contract change is intentional and documented.

Frontend contract tests in `core/tests/test_frontend_*_contracts.py` parse these blocks, verify static include order, and check public JavaScript globals. Add or update those tests when adding a page controller, component stylesheet, shared global, or JSON config block.

## Main Data Flow

1. A Django view normalizes preferences, workflow state, files, statistics, and route URLs.
2. The template renders markup and JSON config blocks.
3. Static page controllers parse those config blocks on load.
4. Controllers update DOM state, call existing endpoints, and preserve server-rendered fallback links where present.
5. The backend remains the source of truth for validation, queue state, ownership, storage quota, and serialized analysis results.

Shared globals that must remain stable:

- `window.CytoCVExportSelection`
- `window.CytoCVOverlayPrefetch`
- `window.CytoCVResultsViewerShared`
- `window.CytoCVResultsCellActions`
- `window.CytoCVAsyncProgress`
- `window.showGlobalMessage`

## Upload Flow

`form/experiment.html` renders the upload form and `uploadPreparationConfig`. `js/pages/experiment.js` reads endpoint URLs and limits from that config, splits selected files into upload batches, posts each batch to `experiment_upload_batch`, and starts upload preparation through `experiment_upload_prepare`.

In `sync` mode the upload-preparation request can return a terminal result. In `worker` mode the frontend polls `experiment_upload_prepare_status` until the job finishes or fails. Successful preparation redirects to `pre_process` for the approved UUID set.

The frontend assumes upload-preparation responses keep the existing fields for status, job UUID, valid UUIDs, redirect URL, messages, and resumable-job state.

Upload and workflow-default pages share reusable control styling through `css/components/workflow-controls.css`. Keep page layout, modal state, and responsive overrides in `css/pages/experiment.css` or `css/pages/workflow-defaults.css`.

## Verification And Preprocess Flow

`pre_process.html` renders file previews, channel and scale controls, selected-stat context, and `preprocessPageConfig`. `js/pages/pre-process.js` reads that config, keeps client-side scale state in sync with hidden form fields, and submits the preprocess form without changing server validation semantics.

When worker-backed analysis is enabled, the frontend polls `analysis_progress` and can request cancellation through `cancel_progress`. In sync mode, progress is still written through the same progress contract while the request runs.

The frontend assumes progress responses keep the existing phase, status, detail, message, redirect URL, and failure fields.

## Queue And Batch Verification Flow

Upload preparation and analysis can run through background jobs selected by `CYTOCV_ANALYSIS_EXECUTION_MODE`. The browser does not decide queue behavior. It only starts jobs, polls status endpoints, displays progress, handles cancellation, and follows redirect URLs returned by the backend.

Batch verification preserves the backend-owned UUID list. Frontend code must not invent, reorder for API payloads, or authorize UUIDs beyond the data emitted by the server.

## Results Viewer Flow

`display.html` and `dashboard.html` both render results-viewer data and use shared results-viewer utilities, shared results-viewer component CSS, and the shared export-selection modal. Their page controllers intentionally remain separate because saved-file dashboard behavior and transient display behavior are not identical.

Common contracts:

- `displayFilesData` and `dashboardFilesData` serialize files, channel paths, scale context, cell images, and statistics.
- each file retains the eight-entry `CellPairImages` pairs and adds a versioned
  `OverlayLayers` contract describing selective support, family availability,
  and protected layer URL templates
- `displayPageConfig` and `dashboardPageConfig` serialize deletion preferences, sidebar unit preference, preferred main image channel, and table UUID.
- `viewer_overlay_prefetch.js` owns overlay warmup helpers.
- `js/shared/results-viewer.js` owns duplicate viewer utilities such as blend transitions, image preloading, stat formatting, spatial-unit table formatting, and main-image warmup helpers.
- `js/shared/results-cell-actions.js` owns the shared cell delete/select modal and context-menu controller. `dashboard-cell-actions.js` and `display-cell-actions.js` only pass the page config into that shared controller.
- `css/components/results-viewer.css` owns exact shared dashboard/display viewer selectors.
- `partials/overlay_visibility_control.html` is the single shared Overlays
  multi-select markup used by both pages
- `export_selection_modal.js` owns selectable column/file export behavior.

`js/shared/results-viewer.js` owns overlay selection normalization, stable
signatures, availability intersection, compact summary labels, legacy
aggregate fallback, image/layer resolution, and menu behavior. Display and
Dashboard each keep one page-level selected state, default it to all families
on page load, and never store it per file or per cell. File availability
produces an effective state without erasing unavailable selections.

The outlined member remains the exact `All` source and the no-outline member is
the `None` source. Mixed states resolve each displayed channel independently.
A channel whose applicable families are all still selected keeps its aggregate
source; only an affected channel switches to its no-outline crop plus protected
transparent PNG layers in renderer draw order. Base images and layers share the
same centered `contain` geometry, which is required because cell crops are
usually rectangular. Overlay-only changes preload only changed stack URLs and
apply without a whole-image blend. Selecting no overlays does not request
dynamic overlay resources. Render tokens prevent an older preload from
overwriting a newer file, cell, or visibility selection.

Only factor display/dashboard code when the DOM, payload, preference, and save/delete behavior contracts are identical.

`display.html` still has inline `onclick` handlers for previous/next cell navigation because those handlers depend on page-local navigation functions. Keep them until the display viewer controller is deliberately converted to event-listener wiring with browser smoke coverage.

## Organization Rules

- Put page-only CSS in `css/pages/<page>.css`.
- Put reused component CSS in `css/components/`.
- Load component CSS before page CSS so page-owned overrides keep the final cascade.
- Put page-only JavaScript in `js/pages/`.
- Put reused utilities in `js/shared/` only when at least two pages use them or when they expose a stable global API.
- Keep backend route names resolved in templates, then pass URLs to static JS through JSON config.
- Keep business, validation, queue, and ownership logic in Django views/services.
- Keep presentational components free of request-shape assumptions where practical.
- Do not delete CSS or JS unless direct template references, dynamic selectors, tests, docs, and global side effects have been checked.

## Adding A Frontend Feature

1. Start with the owning Django view and template.
2. Add or extend a page CSS file rather than embedding styles.
3. Add page JavaScript in `js/pages/` unless the behavior is demonstrably shared.
4. Pass server data through a JSON config block with a stable ID.
5. Preserve form field names, endpoint URLs, payload shapes, and response parsing.
6. Add tests that assert the rendered config and static controller behavior when the feature depends on JS contracts.
7. Run the frontend validation commands below.

## Validation Commands

Run from `cytocv/`:

```powershell
Get-ChildItem -Path core/static/js -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
python manage.py check
python manage.py collectstatic --dry-run --noinput
python manage.py test core.tests.test_core_app
python manage.py test core.tests.test_accounts_preferences
python manage.py test
```

There is no npm lint, build, or typecheck pipeline. If Node is available, `node --check` can be used as an extra syntax check for the static JavaScript files.

## Frontend-Relevant Environment Variables

- `CYTOCV_ANALYSIS_EXECUTION_MODE`: selects sync versus worker-backed upload preparation and analysis.
- `CYTOCV_UPLOAD_BATCH_TARGET_BYTES`: controls browser upload batching target size emitted to the upload page.
- `CYTOCV_UPLOAD_LIMIT_DEFAULT_MAX_FILES` and `CYTOCV_UPLOAD_LIMIT_EDU_MAX_FILES`: affect upload-limit messages and backend validation.
- `CYTOCV_ANALYSIS_LIMIT_DEFAULT_MAX_ACTIVE_JOBS` and `CYTOCV_ANALYSIS_LIMIT_EDU_MAX_ACTIVE_JOBS`: affect queue-limit responses shown by the frontend.
- `CYTOCV_QUOTA_DEFAULT_MB`, `CYTOCV_QUOTA_EDU_MB`, `CYTOCV_QUOTA_EDU_SUFFIXES`, and `CYTOCV_ACCESS_UNRESTRICTED_EMAILS`: affect dashboard and save/autosave messaging.
- `CYTOCV_RECAPTCHA_ENABLED` and `CYTOCV_RECAPTCHA_SITE_KEY`: affect signin/signup widgets.
- `STATIC_URL`: controls static asset URLs.
- `CYTOCV_SECURITY_STRICT` and CSP settings: affect allowed script, style, image, font, connect, and frame sources.

See `docs/ops/environment-reference.md` for the complete environment reference.

## Backend Response Assumptions

Frontend controllers assume backend endpoints continue to return JSON objects with the documented field names, HTTP status codes that distinguish validation and permission failures, and redirect URLs for completed upload/preprocess flows. Result viewers assume serialized file payloads include stable keys for main image paths, channel config, scale context, statistics, cell image maps, and no-cell warnings.

## Candidate Cleanup

No frontend files or selectors were deleted during the modularization pass because the goal was behavior-preserving extraction. Future cleanup candidates should be verified separately:

- display/dashboard page controllers still have intentional duplication where saved-file and transient-display behavior diverges
- large page CSS files can be split further only when a repeated component boundary is proven and cascade order can be preserved; current page-owned examples include modal animation rules, responsive channel-order rules, and order-sensitive `.length-unit-option` state rules
- `cytocv/core/static/assets/UWBSTEM-badge-white.png` appears less prominent than the active UWB assets but should not be removed without checking external references and deployed branding needs
