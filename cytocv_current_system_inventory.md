# CytoCV Current System Inventory

Audit target: `BrentLagesse/CytoCV` local checkout at commit `a3ed23ed3b861729d2caa960524e55e17c4d9977` (local `git rev-parse HEAD`, 2026-07-06).

This is a read-only repository audit except for this generated Markdown deliverable. Code behavior was not changed.

## 1. Version And Identity

| Item | Current value | Evidence |
|---|---:|---|
| Current product name in root docs | `CytoCV` | `README.md:1`; `README.md:3` |
| README version string | `1.0` | `README.md:5` |
| Latest local git tag visible in this checkout | `v1.8.1` | local `git tag --list --sort=-creatordate` output |
| Current commit | `a3ed23ed3b861729d2caa960524e55e17c4d9977` | local `git rev-parse HEAD` output |
| Package-level version constant | None found in inspected Python/package metadata | repository-wide `rg "__version__|VERSION|version ="`; only schema constants such as `CEN_DOT_SCHEMA_VERSION` are present in `cytocv/core/models.py:242` and `cytocv/core/services/contour_coordinates.py:12` |
| Manuscript mismatch risk | The old manuscript should not describe the system as YeastWeb, DeltaVision-only, fixed four-channel-only, or limited to legacy mCherry/GFP/DAPI measurements. The current README describes CytoCV, DV/TIFF inputs, logical channel roles, plugin-driven validation, and DIC as the only universally required channel. | `README.md:1`; `README.md:3`; `cytocv/core/stats_plugins.py:240-253` |
| Documentation mismatch to fix | `docs/user/workflow-guide.md` says the default selected plugins include `NuclearCellPairIntensity`, but code defaults do not include it. | docs claim: `docs/user/workflow-guide.md:46`; code defaults: `cytocv/core/services/signal_quantification.py:52-57`; account defaults use those defaults: `cytocv/accounts/preferences.py:65-68` |
| Documentation mismatch to fix | Some research/workflow docs still phrase ingestion as DeltaVision-only even though code and README support TIFF stacks. | `docs/research/methods-and-system-description.md:5`; `docs/research/methods-and-system-description.md:50`; current support in `README.md:3`; `cytocv/core/image_sources.py:11-14` |

## 2. Supported Input Formats

CytoCV recognizes DeltaVision `.dv` and stack TIFF `.tif`/`.tiff` source images. The extension constants are `DV_IMAGE_EXTENSION = ".dv"` and `TIFF_IMAGE_EXTENSIONS = {".tif", ".tiff"}`; `SUPPORTED_SOURCE_IMAGE_EXTENSIONS` is their union. Source recognition is case-insensitive through `source_image_extension()` and `is_supported_image_filename()`. (`cytocv/core/image_sources.py:11-30`)

DeltaVision files are loaded with `mrc.DVFile(...).asarray()` and normalized to an image stack; TIFF files are loaded through `tifffile.TiffFile(...).series[0].asarray()` and normalized into channel-first order. (`cytocv/core/image_sources.py:33-40`; `cytocv/core/image_sources.py:149-168`)

TIFF assumptions and limits:

- A 2D TIFF is treated as a one-layer stack. (`cytocv/core/image_sources.py:67-73`; `cytocv/core/image_sources.py:105-110`)
- TIFF axes metadata is honored when present; Y and X axes are required, one stack axis is moved to channel-first order, and RGB/sample TIFFs are rejected as unsupported microscopy layer stacks. (`cytocv/core/image_sources.py:67-102`)
- Without axes metadata, a 3D TIFF is accepted when the smallest axis can be inferred as the channel axis and is at most 16 planes; other shapes are rejected. (`cytocv/core/image_sources.py:105-122`)
- Upload validation for channel-dependent workflows accepts three- or four-layer stacks when layer-count enforcement is not enabled; a workflow with required channels rejects other layer counts. (`cytocv/core/metadata_processing/error_handling/source_image_validation.py:110-146`)
- Three-layer stacks require reliable metadata to identify DIC and the missing optional fluorescence role; ambiguous three-layer stacks fail required-channel validation rather than guessing. (`cytocv/core/metadata_processing/error_handling/source_image_validation.py:161-197`; `cytocv/core/services/channel_presence.py:303-319`)
- CytoCV processes each selected source file as its own run; it does not assemble separate single-channel TIFF files into one run. (`docs/reference/file-format-and-artifact-spec.md:24`)

## 3. Current Channel Model

The current logical channel roles are `DIC`, `channel_blue`, `channel_red`, and `channel_green`; display labels are `DIC`, `Blue`, `Red`, and `Green`. (`cytocv/core/channel_roles.py:5-21`)

Only `DIC` is universally required, because it is the segmentation channel. Plugin and puncta-mode choices add fluorescence requirements. (`cytocv/core/stats_plugins.py:31-39`; `cytocv/core/stats_plugins.py:240-253`)

Metadata normalization:

- Generic aliases normalize `dapi` and `hoechst` to Blue, `mcherry`, `m-cherry`, and `cherry` to Red, and `gfp` to Green. (`cytocv/core/channel_roles.py:39-54`)
- Free-text role normalization also accepts substring matches for DIC/brightfield/transmission, blue, red, and green. (`cytocv/core/channel_roles.py:67-89`)
- DV metadata prefers wavelength mapping: about 625 nm -> Red, 525 nm -> Green, 435 nm -> Blue, and negative or tiny positive wavelength values -> DIC; name aliases are used as fallback. (`cytocv/core/metadata_processing/dv_channel_parser.py:34-63`)
- TIFF ImageJ labels are read from `Labels`/`labels`; `w625`, `w525`, and `w435` map to Red, Green, and Blue, while DIC is inferred from DIC/brightfield/transmission or `R3D_REF`-style labels. (`cytocv/core/metadata_processing/tiff_channel_parser.py:27-41`; `cytocv/core/metadata_processing/tiff_channel_parser.py:44-75`)
- Four-layer metadata must identify all roles to be used as a complete TIFF mapping; three-label TIFF metadata is accepted only when DIC plus two fluorescence channels are identified. (`cytocv/core/metadata_processing/tiff_channel_parser.py:78-101`)

Plugin channel requirements:

| Plugin/mode | User-facing label | Required channels beyond DIC | Evidence |
|---|---|---|---|
| `PunctaDistance`, `red_puncta` | Red Puncta (Measure Green) | Red, Green | `cytocv/core/services/puncta_line_mode.py:38-43`; `cytocv/core/services/puncta_line_mode.py:87-95` |
| `PunctaDistance`, `green_puncta` | Green Puncta (Measure Red) | Green, Red | `cytocv/core/services/puncta_line_mode.py:44-48`; `cytocv/core/services/puncta_line_mode.py:87-95` |
| `PunctaDistance`, `red_puncta_only` | Red Puncta Only | Red | `cytocv/core/services/puncta_line_mode.py:49-53`; `cytocv/core/services/puncta_line_mode.py:87-95` |
| `PunctaDistance`, `green_puncta_only` | Green Puncta Only | Green | `cytocv/core/services/puncta_line_mode.py:54-58`; `cytocv/core/services/puncta_line_mode.py:87-95` |
| `CENDot` | Cen Dot Location | Red, Green | `cytocv/core/stats_plugins.py:115-127` |
| `Biorientation` | Biorientation | Red, Green | `cytocv/core/stats_plugins.py:128-140` |
| `GreenRedIntensity` | Red/Green Contour Intensities | Red, Green | `cytocv/core/stats_plugins.py:142-151` |
| `NuclearCellPairIntensity` | Nuclear, Cell-Pair Intensity | Red, Green | `cytocv/core/stats_plugins.py:153-164` |
| `NucleusIntensity` legacy | Nucleus Green Intensity | Blue, Green | `cytocv/core/stats_plugins.py:165-174` |
| `BlueNucleusIntensity` legacy | Nucleus Blue Intensity | Blue | `cytocv/core/stats_plugins.py:175-184` |
| `RedBlueIntensity` legacy | Red-in-Blue Intensity | Red, Blue | `cytocv/core/stats_plugins.py:185-194` |

The UI payload exposes plugin labels, descriptions, required channels, puncta-line-mode requirements, legacy flags, and exclusive groups from the same registry. (`cytocv/core/stats_plugins.py:343-405`)

## 4. Current Workflow

1. Upload: the Experiment page accepts supported source files, stores each upload as an `UploadedImage`, and keeps source files under `<uuid>/<name>.<ext>`. (`cytocv/core/models.py:57-75`; `cytocv/core/views/experiment.py:899-1020`; `cytocv/core/models.py:60-63`)
2. Validation: upload preparation builds `SourceImageValidationOptions` from the submitted snapshot, checks file recognition, layer count when needed, and required channels. (`cytocv/core/services/upload_preparation.py:57-109`; `cytocv/core/metadata_processing/error_handling/source_image_validation.py:92-233`)
3. Channel/scale sidecars: upload preparation extracts scale metadata, resolves channel config/presence, writes `channel_config.json`, writes `channel_presence.json`, and saves `UploadedImage.scale_info`. (`cytocv/core/services/upload_preparation.py:189-225`; `cytocv/core/services/channel_presence.py:341-390`)
4. Preview: upload preparation generates browser preview assets after validation; previews are capped at the historical first four preview slots. (`cytocv/core/services/upload_preparation.py:228-234`; `cytocv/core/services/artifact_storage.py:544-577`)
5. Preprocess review: the preprocess view renders per-file channel order and scale sidebar payloads, accepts manual scale overrides/reverts, and starts analysis in sync or worker mode. (`cytocv/core/views/pre_process.py:305-400`; `cytocv/core/views/pre_process.py:422-492`; `cytocv/core/views/pre_process.py:828-878`)
6. DIC preprocessing: preprocessing selects the DIC layer from `channel_config.json`, normalizes it to RGB PNG form, and writes the Mask R-CNN input artifact. (`cytocv/core/mrcnn/preprocess_images.py:60-100`)
7. Mask R-CNN inference: the shared analysis pipeline runs preprocessing and inference as the first batch stage, checking cooperative cancellation before/between stages. (`cytocv/core/services/analysis_pipeline.py:92-164`)
8. Mask post-processing: raw masks can be dilated, hole-filled, overlap-deduplicated, convex-hull-filled, converted into a label image, and written as `mask.tif`. (`cytocv/core/mrcnn/mask_processing.py:42-172`; `cytocv/core/mrcnn/mask_processing.py:175-244`)
9. Segmentation/cell candidate selection: the shared segmentation batch loads `mask.tif`, applies Cell Inclusion Mode to retain single cells and/or cell pairs, refines pair labels, writes `cellpairs.tif`, generates full-frame overlays and per-cell crops, writes outline CSVs, and creates a `SegmentedImage`. (`cytocv/core/services/segmentation_pipeline.py:533-620`; `cytocv/core/services/segmentation_pipeline.py:630-789`)
10. Statistics plugins: the segmentation pipeline creates one `CellStatistics` row per retained label, stores run configuration in `properties`, builds a per-row execution plan, and calls `get_stats()` to run selected plugin classes. (`cytocv/core/services/segmentation_pipeline.py:799-813`; `cytocv/core/services/segmentation_pipeline.py:1209-1376`; `cytocv/core/views/segment_image.py:647-748`)
11. Canonical contours: `get_stats()` detects channel-specific contour families, converts them to canonical slots clipped to the DIC cell mask, stores parentage, stores contour counts, draws debug overlays, and executes plugin `calculate_statistics()` methods. (`cytocv/core/views/segment_image.py:647-676`; `cytocv/core/views/segment_image.py:706-748`)
12. Debug artifacts: optional overlay/debug files are controlled by `SEGMENT_SAVE_DEBUG_ARTIFACTS`; overlay replay config is always written for protected media replay. (`cytocv/cytocv/settings.py:134-142`; `cytocv/core/services/segmentation_pipeline.py:1106-1147`; `cytocv/core/services/segmentation_pipeline.py:1368-1374`)
13. Display/Dashboard review: Display authorizes saved or session-transient runs, loads scale/sidebar data, filters table rows, renders `CellTable`, and supports protected overlay media. (`cytocv/core/views/display.py:146-155`; `cytocv/core/views/display.py:163-312`; `cytocv/cytocv/urls.py:148-156`; `cytocv/cytocv/urls.py:196`)
14. Save/unsave/transient storage: completed results are autosaved when enabled and quota allows; otherwise they stay guest-owned and visible through the session transient UUID set. Display save/unsave endpoints move runs between authenticated ownership and guest/transient state. (`cytocv/core/services/segmentation_pipeline.py:482-520`; `cytocv/core/services/segmentation_pipeline.py:1387-1393`; `cytocv/core/views/display.py:487-592`; `cytocv/core/views/display.py:600-691`)
15. Export: Display can export the current table as CSV/XLSX, and Display/Dashboard can build combined multi-file CSV/XLSX exports with row filters and selected metric columns. (`cytocv/core/views/display.py:369-436`; `cytocv/core/views/display.py:829-913`; `cytocv/core/services/combined_stat_export.py:148-210`)

## 5. Architecture

CytoCV is a Django project with app-level domains `core` and `accounts`. `INSTALLED_APPS` includes Django core apps, `django_tables2`, `core`, `accounts`, and allauth providers. (`cytocv/cytocv/settings.py:205-222`; `cytocv/core/apps.py:1-9`; `cytocv/accounts/apps.py:1-16`)

Primary routes include Experiment upload/preparation, preprocess, convert, segment, display, overlay, cell deletion, save/unsave/sync, combined export, channel-order updates, progress polling, progress write, cancellation, and protected media. (`cytocv/cytocv/urls.py:106-196`)

Major services:

- `core.services.upload_preparation` validates uploads, extracts metadata, writes channel config/presence, and generates previews. (`cytocv/core/services/upload_preparation.py:1-35`; `cytocv/core/services/upload_preparation.py:237-408`)
- `core.services.analysis_pipeline` orchestrates preprocess, inference, segmentation, progress, cancellation, and cleanup for sync and worker execution. (`cytocv/core/services/analysis_pipeline.py:1-18`; `cytocv/core/services/analysis_pipeline.py:92-224`)
- `core.services.segmentation_pipeline` runs shared segmentation/statistics and final autosave/transient decisions. (`cytocv/core/services/segmentation_pipeline.py:533-540`; `cytocv/core/services/segmentation_pipeline.py:1387-1393`)
- `core.services.artifact_storage` owns media paths, preview generation, PNG persistence, quota calculation, cleanup, and stale transient sweeps. (`cytocv/core/services/artifact_storage.py:147-183`; `cytocv/core/services/artifact_storage.py:214-358`; `cytocv/core/services/artifact_storage.py:615-802`)
- `core.services.canonical_contours`, `contour_coordinates`, `signal_quantification`, `puncta_line_mode`, `measurement_contour_ratio`, and `scale` are the main reusable scientific/statistics support services. (`cytocv/core/services/canonical_contours.py:149-186`; `cytocv/core/services/contour_coordinates.py:88-117`; `cytocv/core/services/signal_quantification.py:242-386`; `cytocv/core/services/puncta_line_mode.py:38-122`; `cytocv/core/services/measurement_contour_ratio.py:9-46`; `cytocv/core/scale.py:268-335`)

Database models:

- `UploadedImage`: source upload ownership, name, UUID, source file location, and `scale_info`. (`cytocv/core/models.py:57-75`)
- `SegmentedImage`: segmented output UUID, image paths, cell count, and persisted `cell_inclusion_mode`. (`cytocv/core/models.py:88-108`)
- `AnalysisJob`: queued/running/succeeded/failed/cancelling/cancelled worker state, batch key, run UUIDs, config snapshot, progress detail, and cooperative cancellation flag. (`cytocv/core/models.py:119-165`)
- `UploadPreparationJob`: analogous upload-prep worker state, new/restored/valid run UUIDs, config snapshot, error lines, progress, and cancellation flag. (`cytocv/core/models.py:178-212`)
- `DVLayerTifPreview`: per-layer upload preview rows. (`cytocv/core/models.py:226-231`)
- `CellStatistics`: per-cell numeric fields, classification fields, file metadata, deletion flag, and JSON `properties`. (`cytocv/core/models.py:287-397`)

Filesystem artifacts:

- Run media root: `<MEDIA_ROOT>/<uuid>/`; preview directory, preprocess directory, output directory, segmented directory, and user directory are centralized in `artifact_storage`. (`cytocv/core/services/artifact_storage.py:147-183`)
- `channel_config.json` is written atomically during upload preparation; `channel_presence.json` is written atomically by the channel-presence service. (`cytocv/core/services/upload_preparation.py:127-135`; `cytocv/core/services/channel_presence.py:137-146`)
- Preview PNGs are stored under the run preview directory and recorded as `DVLayerTifPreview` rows. (`cytocv/core/services/artifact_storage.py:544-577`)
- Segmentation writes `mask.tif`, `cellpairs.tif`, full-frame output images, per-cell channel crops, no-outline crops, outline CSV files, overlay cache files, optional debug overlays, and neck-split manifests/sidecars. (`cytocv/core/mrcnn/mask_processing.py:238-244`; `cytocv/core/services/segmentation_pipeline.py:617-620`; `cytocv/core/services/segmentation_pipeline.py:630-789`; `cytocv/core/services/segmentation_pipeline.py:1361-1374`)

Worker/background behavior:

- `ANALYSIS_EXECUTION_MODE` is `sync` or `worker`, default `sync`; analysis and upload-prep stale thresholds are configurable. (`cytocv/cytocv/settings.py:138-155`)
- Analysis jobs and upload-preparation jobs have active/terminal statuses and can be claimed by workers. (`cytocv/core/models.py:119-152`; `cytocv/core/models.py:178-212`; `cytocv/core/services/analysis_jobs.py:87-129`; `cytocv/core/services/upload_preparation_jobs.py:49-95`)
- Progress is mirrored both in database job fields and filesystem JSON under `MEDIA_ROOT/progress`; cancellation uses both database flags and legacy filesystem cancel markers. (`cytocv/core/services/analysis_progress.py:103-182`; `cytocv/core/services/analysis_progress.py:199-281`)
- Cancelled analysis batches remove newly uploaded/transient runs; non-cancel failures preserve uploads/previews for retry while removing derived processing results. (`cytocv/core/services/analysis_pipeline.py:74-82`; `cytocv/core/services/analysis_pipeline.py:197-224`; `cytocv/core/services/artifact_storage.py:673-687`)

## 6. User-Facing Controls

| Control | Current behavior | Evidence |
|---|---|---|
| Selected statistics plugins | Plugin selection is normalized, dependency-expanded, and converted to an execution plan. | `cytocv/core/stats_plugins.py:204-253`; `cytocv/core/stats_plugins.py:321-340` |
| Signal Quantification Mode | Active modes are puncta distance and nuclear/cell-pair; mode controls effective selected plugins and stat visibility. | `cytocv/core/services/signal_quantification.py:21-31`; `cytocv/core/services/signal_quantification.py:242-386` |
| Current code defaults | Default signal plugins are `PunctaDistance`, `CENDot`, `Biorientation`, and `GreenRedIntensity`; account defaults use this tuple. | `cytocv/core/services/signal_quantification.py:52-57`; `cytocv/accounts/preferences.py:65-68` |
| Cell Inclusion Mode | Values are cell pairs only, single cells only, and single cells plus cell pairs; invalid values default to pairs only. | `cytocv/core/cell_types.py:20-31`; `cytocv/core/cell_types.py:60-66` |
| Puncta source/line width | Puncta source modes are red puncta, green puncta, red-only, green-only; line width can be entered in px or um and is converted to integer pixels with minimum 1. | `cytocv/core/services/puncta_line_mode.py:15-58`; `cytocv/core/scale.py:477-503`; `cytocv/core/services/segmentation_pipeline.py:871-879` |
| CEN dot thresholds | CEN dot distance and proximity radius accept px or um; pixel equivalents are stored and original units are preserved in properties. | `cytocv/core/services/segmentation_pipeline.py:880-906`; `cytocv/core/services/segmentation_pipeline.py:907-942`; `cytocv/core/services/segmentation_pipeline.py:1248-1262` |
| Biorientation thresholds | Red min/max distance values and units plus collinearity threshold are parsed, normalized, and stored. | `cytocv/core/services/segmentation_pipeline.py:1011-1055`; `cytocv/core/services/segmentation_pipeline.py:1263-1276` |
| Nuclear/cell-pair mode | `green_nucleus` uses Green as contour source and Red as measurement channel; `red_nucleus` reverses the source/measurement roles. | `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py:35-48` |
| Dot splitting and split modes | Green and red dot splitting can be enabled/disabled, and modes are normalized before contour processing. | `cytocv/core/services/segmentation_pipeline.py:1056-1068`; `cytocv/core/contour_processing/contour_operations.py:45-130` |
| Green contour filtering | Optional green contour filtering rejects weak/small green contours with shape and local ring-background evidence. | `cytocv/core/contour_processing/contour_operations.py:2741-2791`; `cytocv/core/contour_processing/contour_operations.py:2866-2983` |
| Alternate red/nucleus detection | Alternate nucleus detection only runs in nuclear/cell-pair signal mode; stale requested channel values are corrected to the channel implied by nuclear mode. | `cytocv/core/services/signal_quantification.py:183-225`; `cytocv/core/services/segmentation_pipeline.py:989-1010` |
| Scale/micron settings | Metadata scale is preferred when requested; manual fallback/override are supported; anisotropic dx/dy is retained for distance and area conversion. | `cytocv/core/scale.py:101-157`; `cytocv/core/scale.py:268-335`; `cytocv/core/views/pre_process.py:422-492` |
| Table/download filters | Cell type and puncta-source contour count filters apply to Display/Dashboard tables and exports. | `cytocv/core/cell_types.py:99-144`; `cytocv/core/services/puncta_source_contour_count_filter.py:167-218`; `cytocv/core/views/display.py:285-312`; `cytocv/core/views/display.py:369-436` |
| Export column selection | `cell_id` and `cell_type` are always included; metric columns are selectable and normalized in table order. | `cytocv/core/services/stat_export_selection.py:19-27`; `cytocv/core/services/stat_export_selection.py:71-80`; `cytocv/core/services/stat_export_selection.py:206-241` |

## 7. Current Outputs

Per-cell database fields are defined on `CellStatistics`. They include identity and cell type, puncta line/distance, nuclear/cell-pair/cytoplasmic fields, blue/red/green contour sizes, red/green total-max-average intensity triplets, distance-of-green-from-red triplets, legacy blue/red-blue fields, CEN dot classification, biorientation counts, file paths, deletion flag, and JSON `properties`. (`cytocv/core/models.py:287-397`)

Key `properties` fields stored per cell include cell type, cell inclusion mode, puncta line mode, nuclear mode, scale values and units, line width, CEN thresholds, biorientation thresholds, dot split modes, signal mode, contour intensity flag, alternate nucleus detection status/channel, neck split metadata, stat visibility, parentage payload, contour count metadata, contour centers, and unavailable field lists. (`cytocv/core/services/segmentation_pipeline.py:1209-1295`; `cytocv/core/services/segmentation_pipeline.py:1296-1351`; `cytocv/core/views/segment_image.py:675-676`; `cytocv/core/cell_analysis/puncta_distance.py:160-169`)

Exported CSV/XLSX columns are the `CellTable.Meta.fields` set in table order: `Cell ID`, `Cell Type`, puncta distance/line intensity, blue contour fields, red/green contour sizes/centers, total-max-average intensity triplets, measurement/contour ratios, green-red distances, nuclear/cell-pair fields, parentage, CEN dot, and biorientation fields. (`cytocv/core/tables.py:140-249`; `cytocv/core/tables.py:250-324`; `cytocv/core/tables.py:898-925`)

Unavailable/null behavior:

- Numeric display cells render `N/A` when the value cannot be formatted or the field is not applicable. (`cytocv/core/tables.py:54-78`)
- Choice labels such as CEN dot render `N/A` when the field is not applicable; old schema rows can return rerun-required labels for non-NA old CEN values. (`cytocv/core/tables.py:81-110`; `cytocv/core/models.py:255-284`)
- Field applicability comes from selected-plugin visibility and row-level `unavailable_stat_fields`; disabled plugin groups and explicitly unavailable fields render/export as `N/A`. (`cytocv/core/services/stat_applicability.py:186-205`; `cytocv/core/services/stat_applicability.py:222-278`)
- Exported decimals are quantized to three decimal places; invalid, missing, or non-finite values export as `N/A`. (`cytocv/core/tables.py:441-507`)
- Single-cell rows clear pair-specific outputs: CEN dot is `N/A`, biorientation counts are zero in storage, nuclear/cell/cytoplasm sums are zero, ratio is null, and the nuclear/CEN/biorientation visibility groups are false. (`cytocv/core/services/cell_type_statistics.py:8-29`)
- Red-only/green-only puncta modes mark opposite-channel and paired-ratio fields as unavailable through `properties["unavailable_stat_fields"]`; same-channel contour stats can still be computed when contour intensity is enabled. (`cytocv/core/cell_analysis/puncta_distance.py:37-129`; `cytocv/core/cell_analysis/puncta_distance.py:160-245`)
- JSON payload code normalizes disabled/unavailable groups to `None`/`N/A` for frontend cards instead of implying that default zeros were calculated. (`cytocv/core/services/cell_statistics_payload.py:52-113`; `cytocv/core/services/cell_statistics_payload.py:337-374`)

Pixel versus micron behavior:

- Spatial table fields are puncta distance, contour areas/centers, and green-red distances; labels receive `(px)`, `(px^2)`, `(um)`, or `(um^2)` suffixes depending on selected unit. (`cytocv/core/tables.py:118-137`; `cytocv/core/tables.py:386-394`; `cytocv/core/scale.py:464-474`)
- Area conversion multiplies pixel area by `x_um_per_px * y_um_per_px`; distance conversion uses stored delta x/y with anisotropic axes when deltas are available, otherwise scalar effective scale. (`cytocv/core/scale.py:408-461`; `cytocv/core/tables.py:583-615`)
- Contour-center coordinates are stored as full-image bottom-left pixel coordinates and rendered/exported with per-axis micron conversion when requested. (`cytocv/core/services/contour_coordinates.py:88-117`; `cytocv/core/services/contour_coordinates.py:194-217`; `cytocv/core/tables.py:623-639`)

## 8. Validation Status

Automated tests cover the major software contracts, but they are implementation/regression tests rather than independent biological validation.

Examples of automated coverage:

- Supported extensions and TIFF loading behavior: `cytocv/core/tests/test_image_sources.py:23-57`
- TIFF channel labels and TIFF scale metadata: `cytocv/core/tests/test_tiff_channel_parser.py:20-154`; `cytocv/core/tests/test_tiff_scale_parser.py:16-50`
- Required channels, three-layer missing-channel behavior, DV header mapping, TIFF validation, puncta line modes, and legacy intensity raw-value selection: `cytocv/core/tests/test_stats_validation.py:64-89`; `cytocv/core/tests/test_stats_validation.py:229-493`; `cytocv/core/tests/test_stats_validation.py:700-858`
- Canonical contour clipping, ranking, centers, and parentage masks: `cytocv/core/tests/test_canonical_contours.py:36-280`
- Puncta/modern contour statistics, source contour counts, raw measurement images, alternate nuclear detection, and green split/debug behavior: `cytocv/core/tests/test_modern_contour_statistics.py:331-1606`
- CEN dot classification cases: `cytocv/core/tests/test_cen_dot_classification.py:150-464`
- Biorientation collinearity/off-axis behavior: `cytocv/core/tests/test_biorientation.py:105-324`
- Nuclear/cell-pair intensity modes, alternate detection, raw measurement, clipping, legacy scaled path, and ratio null behavior: `cytocv/core/tests/test_nuclear_cell_pair_intensity.py:120-758`
- Dot splitting and green contour filtering: `cytocv/core/tests/test_dot_split.py:425-1260`; `cytocv/core/tests/test_dot_split_config.py:13-91`
- Cell Inclusion Mode and display/export filters: `cytocv/core/tests/test_cell_inclusion_mode.py:81-479`; `cytocv/core/tests/test_puncta_source_contour_count_filter.py:59-275`
- Scale conversion and upload scale initialization: `cytocv/core/tests/test_upload_length_scale.py:37-349`; `cytocv/core/tests/test_scale_request_payloads.py:17-135`
- Tables/export behavior and `N/A` semantics: `cytocv/core/tests/test_tables.py:82-710`; `cytocv/core/tests/test_stat_export_selection.py:49-268`
