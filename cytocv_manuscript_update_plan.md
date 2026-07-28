# CytoCV Manuscript Update Patch Plan

Scope note: this repository contains `docs/research/methods-and-system-description.md` but no visible SoftwareX manuscript source file named for SoftwareX, YeastWeb, manuscript, article, or paper. This plan is therefore a manuscript patch checklist and replacement-text draft, not an applied edit to a manuscript file.

## 1. Section-by-section manuscript changes

### Title and software identity

Replace all references to "YeastWeb" with "CytoCV" unless discussing historical provenance. The current repository title is CytoCV, and the README describes the project as a Django-based microscopy analysis platform. Citations: `README.md` lines 1-3.

Use a manuscript version value tied to the release/commit chosen for submission, not the current README version line, because `README.md` still reports `Version: 1.0` while local git metadata shows later tags. Citation for README mismatch: `README.md` line 5.

### Abstract

Replace the DeltaVision-only/four-channel abstract language with a current system description: CytoCV supports DeltaVision `.dv` and stack TIFF `.tif/.tiff` inputs, maps images into logical DIC, Blue, Red, and Green roles, and requires DIC universally while fluorescence requirements depend on selected statistics plugins. Citations: `README.md` lines 1-5; `cytocv/core/image_sources.py` lines 11-30; `cytocv/core/channel_roles.py` lines 5-89; `cytocv/core/stats_plugins.py` lines 31-39 and 104-194.

State that segmentation is DIC-guided and uses Mask R-CNN inference followed by mask writing and per-cell analysis. Citations: `docs/user/workflow-guide.md` lines 66-87; `cytocv/core/services/analysis_pipeline.py` lines 92-224; `cytocv/core/services/segmentation_pipeline.py` lines 607-620.

Avoid stating that CytoCV biologically validates cell states or CEN classifications. Existing research documentation limits claims to software-generated measurements and notes that weights are not bundled. Citations: `docs/research/methods-and-system-description.md` lines 62-65; `docs/research/reproducibility-and-validation.md` line 43.

### Metadata table

Update the software name, input formats, programming framework, supported channel roles, segmentation method, output formats, and repository version/commit. Cite the current README, source format code, plugin registry, and export code. Citations: `README.md` lines 1-5; `cytocv/core/image_sources.py` lines 11-30; `cytocv/core/stats_plugins.py` lines 104-194; `cytocv/core/services/combined_stat_export.py` lines 37-210.

### Software description

Replace fixed channel-order descriptions with the logical channel model. The manuscript should say CytoCV maps source layers into DIC, Blue, Red, and Green roles, normalizing aliases such as DAPI/Hoechst to Blue, mCherry/cherry to Red, and GFP to Green. Citations: `cytocv/core/channel_roles.py` lines 5-89; `cytocv/core/channel_ordering.py` lines 17-86; `cytocv/core/metadata_processing/dv_channel_parser.py` lines 34-210; `cytocv/core/metadata_processing/tiff_channel_parser.py` lines 27-132.

Describe the upload and validation workflow: source image validation, metadata extraction, channel preview/configuration, upload preparation jobs, preprocessing, inference, segmentation, statistics, and review. Citations: `cytocv/core/metadata_processing/error_handling/source_image_validation.py` lines 92-233; `cytocv/core/services/upload_preparation.py` lines 57-408; `cytocv/core/views/pre_process.py` lines 305-878; `cytocv/core/services/analysis_pipeline.py` lines 52-224.

### Core functionalities table

Replace the old measurement list with current plugin-based statistics: `PunctaDistance`, `CENDot`, `Biorientation`, `GreenRedIntensity`, `NuclearCellPairIntensity`, and legacy plugins `NucleusIntensity`, `BlueNucleusIntensity`, and `RedBlueIntensity`. Citations: `cytocv/core/stats_plugins.py` lines 104-194; `cytocv/core/services/signal_quantification.py` lines 52-76 and 242-386.

### Methods section

Add separate methods subsections for segmentation, canonical contour construction, puncta distance/line intensity, contour intensity statistics, CEN-dot classification, biorientation, nuclear-cell-pair intensity, cell inclusion mode, parentage assignment, scale conversion, and export. Citations: `cytocv/core/services/canonical_contours.py` lines 149-186 and 245-366; `cytocv/core/cell_analysis/puncta_distance.py` lines 246-354; `cytocv/core/cell_analysis/green_red_intensity.py` lines 66-178; `cytocv/core/cell_analysis/cen_dot.py` lines 237-467; `cytocv/core/cell_analysis/biorientation.py` lines 75-247; `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py` lines 113-294; `cytocv/core/cell_types.py` lines 8-144; `cytocv/core/services/cell_parentage.py` lines 135-336; `cytocv/core/scale.py` lines 8-503; `cytocv/core/tables.py` lines 54-925.

### Results / illustrative examples

Do not report software outputs as biological conclusions unless Emily or another biology-side reviewer supplies validation. Phrase examples as "CytoCV produces per-cell measurements..." and "users can review/export..." Citations for output behavior: `docs/user/output-guide.md` lines 44-55 and 94-127; `cytocv/core/models.py::CellStatistics` lines 287-397; `cytocv/core/views/display.py` lines 163-913.

### Availability and reproducibility

Update reproducibility language to include saved and transient analyses, background jobs, progress/cancellation, generated artifacts, and CSV/XLSX export. Citations: `cytocv/core/models.py::AnalysisJob` lines 119-165; `cytocv/core/services/analysis_progress.py` lines 103-332; `cytocv/core/services/artifact_storage.py` lines 147-183, 214-358, and 615-802; `cytocv/core/views/display.py` lines 487-913; `cytocv/core/services/combined_stat_export.py` lines 37-210.

## 2. Old claim -> replacement claim table

| Old claim | Replacement claim | Rationale and citations |
|---|---|---|
| The software is YeastWeb. | The current software is CytoCV. | Repository title and README identify CytoCV. `README.md` lines 1-3. |
| The system only accepts DeltaVision files. | CytoCV supports DeltaVision `.dv` and stack TIFF `.tif/.tiff` sources. | `README.md` lines 1-3; `cytocv/core/image_sources.py` lines 11-30. |
| The image schema is a fixed four-channel DeltaVision schema. | CytoCV maps source layers to logical DIC, Blue, Red, and Green roles; DIC is always required, while fluorescence channels depend on selected plugins and modes. | `cytocv/core/channel_roles.py` lines 5-89; `cytocv/core/metadata_processing/error_handling/source_image_validation.py` lines 82-233; `cytocv/core/stats_plugins.py` lines 31-39 and 240-253. |
| DAPI, mCherry, and GFP are hard-coded channel positions. | Metadata labels and aliases are normalized to logical roles: DAPI/Hoechst to Blue, mCherry/cherry to Red, and GFP to Green. | `cytocv/core/channel_roles.py` lines 39-89; `cytocv/core/metadata_processing/tiff_channel_parser.py` lines 27-132; `cytocv/core/metadata_processing/dv_channel_parser.py` lines 34-210. |
| The main outputs are mCherry focus distance, GFP line intensity, nucleus intensity, and whole-cell intensity. | The current output model is plugin-based and includes puncta distance/line intensity, red/green contour intensity triplets, green-to-red distance, CEN-dot classification, biorientation counts, nuclear-cell-pair intensity, and legacy intensity plugins. | `cytocv/core/stats_plugins.py` lines 104-194; `cytocv/core/models.py::CellStatistics` lines 287-397. |
| The software only analyzes paired cells. | Cell Inclusion Mode can retain pairs only, singles only, or singles plus pairs; pair-specific fields are marked unavailable for single-cell rows. | `cytocv/core/models.py::SegmentedImage` lines 88-108; `cytocv/core/cell_types.py` lines 8-144; `cytocv/core/services/cell_candidate_retention.py` lines 42-139; `cytocv/core/services/segmentation_pipeline.py` lines 806-813 and 1318-1351. |
| Red and green channels are always both required for puncta analysis. | Paired puncta modes require Red and Green, while red-only mode requires Red and green-only mode requires Green. | `cytocv/core/services/puncta_line_mode.py` lines 38-95; `cytocv/core/services/signal_quantification.py` lines 242-386. |
| Cytoplasmic intensity is absent or only historical. | Cytoplasmic intensity is implemented in NuclearCellPairIntensity as whole-cell-pair measurement minus nuclear measurement; legacy nucleus modules also populate cytoplasmic-style fields. | `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py` lines 88-103 and 258-276; `cytocv/core/cell_analysis/nucleus_intensity.py` lines 65-85. |
| Distances are pixel-only. | Distances and length thresholds can be displayed or configured in pixels or microns using metadata or manual microns-per-pixel scale. | `cytocv/core/scale.py` lines 8-503; `cytocv/core/metadata_processing/dv_scale_parser.py` lines 50-106; `cytocv/core/metadata_processing/tiff_scale_parser.py` lines 12-176. |
| Export is a single static CSV. | Display/Dashboard supports filtering and CSV/XLSX export with field applicability and spatial unit handling. | `cytocv/core/tables.py` lines 54-925; `cytocv/core/services/stat_export_selection.py` lines 19-253; `cytocv/core/services/combined_stat_export.py` lines 37-210; `cytocv/core/views/display.py` lines 163-913. |

## 3. Updated abstract draft

CytoCV is a Django-based microscopy image-analysis platform for yeast cell studies that processes DeltaVision `.dv` and stack TIFF `.tif/.tiff` images mapped to logical DIC, Blue, Red, and Green channel roles. DIC images are required for segmentation, while fluorescence channel requirements are determined by user-selected analysis plugins. The workflow supports upload validation, metadata-assisted channel mapping, preprocessing, DIC-guided Mask R-CNN segmentation, per-cell fluorescence contour analysis, Display/Dashboard review, and CSV/XLSX export. Current analysis modules compute software measurements including puncta distance and line intensity, red/green contour intensity statistics, CEN-dot classification, biorientation dot counts, nuclear-cell-pair intensity, and selected legacy intensity measures. CytoCV also provides controls for cell inclusion mode, single-channel puncta modes, dot splitting/filtering, pixel/micron scale conversion, and export filtering. These outputs are computational measurements intended to support review and downstream biological analysis; the manuscript should avoid presenting them as validated biological conclusions without independent confirmation. Citations: `README.md` lines 1-5; `cytocv/core/image_sources.py` lines 11-30; `cytocv/core/channel_roles.py` lines 5-89; `cytocv/core/stats_plugins.py` lines 104-194; `docs/user/workflow-guide.md` lines 66-101; `cytocv/core/models.py::CellStatistics` lines 287-397; `docs/research/reproducibility-and-validation.md` line 43.

## 4. Updated metadata table values

| Metadata field | Updated value | Citation |
|---|---|---|
| Software name | CytoCV | `README.md` lines 1-3. |
| Current README version line | `Version: 1.0`; treat as stale until release metadata is reconciled | `README.md` line 5. |
| Submission version | Use the selected GitHub release/tag or exact commit for submission; do not infer from README alone | `README.md` line 5 for mismatch context. |
| Input formats | DeltaVision `.dv`; stack TIFF `.tif` and `.tiff` | `cytocv/core/image_sources.py` lines 11-30. |
| Channel roles | DIC, Blue, Red, Green | `cytocv/core/channel_roles.py` lines 5-21. |
| Universal required channel | DIC | `cytocv/core/stats_plugins.py` lines 31-39; `cytocv/core/metadata_processing/error_handling/source_image_validation.py` lines 82-89. |
| Segmentation method | DIC-guided Mask R-CNN inference followed by retained mask/cell analysis | `docs/user/workflow-guide.md` lines 66-87; `cytocv/core/services/analysis_pipeline.py` lines 92-224. |
| Analysis architecture | Plugin-based statistics with configurable selected plugins | `cytocv/core/stats_plugins.py` lines 104-194; `cytocv/core/services/signal_quantification.py` lines 52-76 and 242-386. |
| Spatial units | Pixel storage with pixel/micron display and threshold conversion | `cytocv/core/scale.py` lines 8-503. |
| Export formats | CSV and XLSX | `docs/user/output-guide.md` line 94; `cytocv/core/services/combined_stat_export.py` lines 37-210. |

## 5. Updated Software description section outline

1. System overview:
   CytoCV is a Django microscopy-analysis platform for `.dv` and stack TIFF sources with logical channel mapping. Citations: `README.md` lines 1-5; `cytocv/core/image_sources.py` lines 11-30; `cytocv/core/channel_roles.py` lines 5-89.

2. Input validation and channel mapping:
   Describe extension checks, layer/metadata assumptions, DIC requirement, optional fluorescence roles, and plugin-driven requirements. Citations: `cytocv/core/metadata_processing/error_handling/source_image_validation.py` lines 92-233; `cytocv/core/services/channel_presence.py` lines 1-390; `cytocv/core/stats_plugins.py` lines 240-253.

3. Preprocessing and segmentation:
   Describe fluorescence preprocessing, DIC Mask R-CNN inference, mask conversion/writing, and retained candidate selection. Citations: `cytocv/core/image_processing/image_operations.py` lines 108-187; `cytocv/core/services/analysis_pipeline.py` lines 92-224; `cytocv/core/services/segmentation_pipeline.py` lines 607-620.

4. Canonical contours:
   Describe clipping raw fluorescence contours to DIC cell masks, centroid calculation, sorting, and downstream slot access. Citations: `cytocv/core/services/canonical_contours.py` lines 136-186 and 331-366.

5. Analysis plugins:
   Present each plugin with required channels and outputs. Citations: `cytocv/core/stats_plugins.py` lines 104-194; `cytocv/core/cell_analysis/puncta_distance.py` lines 246-354; `cytocv/core/cell_analysis/green_red_intensity.py` lines 66-178; `cytocv/core/cell_analysis/cen_dot.py` lines 237-467; `cytocv/core/cell_analysis/biorientation.py` lines 75-247; `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py` lines 113-294.

6. Review, persistence, and export:
   Describe Display/Dashboard review, save/unsave, transient storage, filters, and CSV/XLSX export. Citations: `docs/user/workflow-guide.md` lines 89-101; `cytocv/core/views/display.py` lines 163-913; `cytocv/core/tables.py` lines 54-925.

## 6. Updated Core functionalities table

| Functionality | Current description | Citation |
|---|---|---|
| Source upload | Accepts `.dv`, `.tif`, and `.tiff` image sources | `cytocv/core/image_sources.py` lines 11-30. |
| Channel mapping | Maps source layers to DIC, Blue, Red, and Green, including metadata aliases | `cytocv/core/channel_roles.py` lines 5-89; `cytocv/core/metadata_processing/tiff_channel_parser.py` lines 27-132. |
| Validation | Requires DIC and selected-plugin fluorescence channels | `cytocv/core/metadata_processing/error_handling/source_image_validation.py` lines 82-233; `cytocv/core/stats_plugins.py` lines 240-253. |
| Segmentation | Uses DIC-guided Mask R-CNN inference and retained candidate masks | `docs/user/workflow-guide.md` lines 66-87; `cytocv/core/services/analysis_pipeline.py` lines 92-224. |
| Cell inclusion | Retains pairs, singles, or both according to Cell Inclusion Mode | `cytocv/core/cell_types.py` lines 8-144; `cytocv/core/services/cell_candidate_retention.py` lines 42-139. |
| Puncta analysis | Computes puncta distance, line intensity, single-channel modes, and same-channel contour stats | `cytocv/core/cell_analysis/puncta_distance.py` lines 37-354; `cytocv/core/services/puncta_line_mode.py` lines 38-95. |
| Red/green contour intensity | Computes total/max/average red and green intensities under red and green masks and green-to-red distance | `cytocv/core/cell_analysis/green_red_intensity.py` lines 66-178; `cytocv/core/image_processing/image_helper.py` lines 27-40. |
| CEN-dot analysis | Classifies green dots near mother/daughter red anchors with user thresholds | `cytocv/core/cell_analysis/cen_dot.py` lines 237-467. |
| Biorientation | Counts on-axis and off-axis green dots relative to a red-red axis | `cytocv/core/cell_analysis/biorientation.py` lines 75-247. |
| Nuclear-cell-pair intensity | Computes whole-cell-pair, nuclear, cytoplasmic, and ratio fields | `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py` lines 113-294. |
| Scale conversion | Supports pixel and micron units for display and thresholds | `cytocv/core/scale.py` lines 8-503. |
| Export | Provides filtered Display/Dashboard tables and CSV/XLSX export | `cytocv/core/tables.py` lines 54-925; `cytocv/core/services/combined_stat_export.py` lines 37-210. |

## 7. Updated per-cell measurements/plugin table

| Plugin/module | User-facing output | Required channels | Main fields | Citation |
|---|---|---|---|---|
| `PunctaDistance` | Puncta distance and line intensity | DIC plus Red/Green for paired mode; DIC plus Red or Green for single-channel modes | `puncta_distance`, `puncta_line_intensity`, contour centers, same-channel intensity fields in single-channel modes | `cytocv/core/cell_analysis/puncta_distance.py` lines 37-354; `cytocv/core/services/puncta_line_mode.py` lines 38-95. |
| `GreenRedIntensity` | Red/green contour intensity and green-to-red distance | DIC, Red, Green | Red/green contour sizes; red-in-red, green-in-red, red-in-green, green-in-green total/max/average; `distance_of_green_from_red` | `cytocv/core/cell_analysis/green_red_intensity.py` lines 66-178; `cytocv/core/models.py::CellStatistics` lines 310-364. |
| `CENDot` | CEN-dot category | DIC, Red, Green | `category_cen_dot`; mother/daughter CEN payload | `cytocv/core/cell_analysis/cen_dot.py` lines 237-467; `cytocv/core/models.py` lines 242-284. |
| `Biorientation` | On-axis/off-axis dot counts | DIC, Red, Green | `colinear_dot_count`, `off_axis_dot_count` | `cytocv/core/cell_analysis/biorientation.py` lines 75-247; `cytocv/core/models.py` lines 375-382. |
| `NuclearCellPairIntensity` | Whole-cell-pair, nuclear, cytoplasmic, ratio | DIC plus configured contour and measurement channels | `cell_pair_intensity_sum`, `nucleus_intensity_sum`, `cytoplasmic_intensity_sum`, `nuclear_cytoplasmic_ratio` | `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py` lines 113-294; `cytocv/core/models.py` lines 297-306. |
| `NucleusIntensity` | Legacy green-in-blue-nucleus and whole-cell/cytoplasm | DIC, Blue, Green | `nucleus_intensity`, `cell_intensity`, `cytoplasmic_intensity_sum` | `cytocv/core/cell_analysis/nucleus_intensity.py` lines 15-85; `cytocv/core/stats_plugins.py` lines 165-174. |
| `BlueNucleusIntensity` | Legacy blue nucleus and cell intensity | DIC, Blue | `nucleus_intensity`, `cell_intensity` | `cytocv/core/cell_analysis/blue_nucleus_intensity.py` lines 19-97; `cytocv/core/stats_plugins.py` lines 175-184. |
| `RedBlueIntensity` | Legacy blue-in-red intensity | DIC, Red, Blue | `blue_in_red_total_intensity`, `blue_in_red_max_intensity`, `blue_in_red_average_intensity` | `cytocv/core/cell_analysis/red_blue_intensity.py` lines 8-44; `cytocv/core/stats_plugins.py` lines 185-194. |

## 8. Draft Illustrative examples section

Example 1: Puncta distance and contour intensity.
CytoCV can analyze red-green fluorescence puncta in DIC-segmented cells by detecting canonical red and green contour slots, computing red/green intensity triplets inside those contours, and measuring green-to-red or same-color puncta distances. This example should show raw/overlay panels, selected puncta source mode, contour count filters, and the exported row fields. Citations: `cytocv/core/services/canonical_contours.py` lines 149-186 and 331-366; `cytocv/core/cell_analysis/puncta_distance.py` lines 246-354; `cytocv/core/cell_analysis/green_red_intensity.py` lines 66-178; `cytocv/core/services/puncta_source_contour_count_filter.py` lines 12-218.

Example 2: CEN-dot and biorientation review.
CytoCV can classify CEN-dot patterns by requiring two red anchors on mother/daughter sides and associating green contours within a proximity radius, and can count green dots on or off the red-red axis using a collinearity threshold. The figure should present this as computational classification with visual review, not as definitive biological assignment. Citations: `cytocv/core/cell_analysis/cen_dot.py` lines 237-467; `cytocv/core/cell_analysis/biorientation.py` lines 75-247; `cytocv/core/services/cell_parentage.py` lines 135-336.

Example 3: Nuclear-cell-pair intensity.
CytoCV can select a configured nuclear contour channel, measure a configured fluorescence channel in the full DIC cell pair and clipped nuclear mask, and compute cytoplasmic intensity and nuclear/cytoplasmic ratio. This example should explicitly name the selected nuclear mode and measurement channel. Citations: `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py` lines 113-294; `cytocv/core/services/signal_quantification.py` lines 183-225.

Example 4: Pixel/micron scale and export.
CytoCV can display/export spatial measurements in pixels or microns using metadata or manual scale, and can export filtered Display/Dashboard tables as CSV/XLSX. Citations: `cytocv/core/scale.py` lines 8-503; `cytocv/core/tables.py` lines 54-925; `cytocv/core/services/combined_stat_export.py` lines 37-210.

## 9. Draft Impact section

CytoCV's current impact is best framed as a reproducible software workflow for microscopy measurement extraction and review. It reduces manual effort by combining DIC-guided segmentation, metadata-aware channel mapping, configurable plugin measurements, visual review, saved/transient analysis management, and CSV/XLSX export in one Django application. Its strongest manuscript claim is that it produces consistent software-derived per-cell measurements and review artifacts for downstream analysis. Avoid claiming that CytoCV itself validates biological phenotypes or replaces expert review. Citations: `README.md` lines 1-5; `docs/user/workflow-guide.md` lines 66-101; `cytocv/core/services/analysis_pipeline.py` lines 52-224; `cytocv/core/views/display.py` lines 163-913; `docs/research/reproducibility-and-validation.md` line 43.

## 10. Draft Conclusions section

CytoCV has evolved from a fixed, older workflow into a configurable microscopy analysis system supporting `.dv` and stack TIFF inputs, logical channel roles, DIC-guided segmentation, plugin-based fluorescence and geometry measurements, pixel/micron controls, Display/Dashboard review, and CSV/XLSX export. The manuscript should present CytoCV as a software platform for producing auditable image-derived measurements, with biological interpretation and validation handled by domain experts using appropriate experimental controls. Citations: `cytocv/core/image_sources.py` lines 11-30; `cytocv/core/channel_roles.py` lines 5-89; `cytocv/core/stats_plugins.py` lines 104-194; `cytocv/core/scale.py` lines 8-503; `cytocv/core/tables.py` lines 54-925.

## 11. New figures/tables recommended

1. Workflow figure:
   Upload -> validation -> channel mapping -> preprocessing -> Mask R-CNN segmentation -> canonical contours -> plugins -> Display/Dashboard -> CSV/XLSX export. Citations: `docs/user/workflow-guide.md` lines 15-101; `cytocv/core/services/upload_preparation.py` lines 57-408; `cytocv/core/services/analysis_pipeline.py` lines 52-224.

2. Channel model table:
   Logical roles, aliases, universal/optional requirements, and plugin requirements. Citations: `cytocv/core/channel_roles.py` lines 5-89; `cytocv/core/stats_plugins.py` lines 104-194 and 240-253.

3. Plugin methods table:
   Required channels, input masks, formulas, output fields, and failure/NA behavior per plugin. Citations: `cytocv/core/cell_analysis/puncta_distance.py` lines 246-354; `cytocv/core/cell_analysis/green_red_intensity.py` lines 66-178; `cytocv/core/cell_analysis/cen_dot.py` lines 237-467; `cytocv/core/cell_analysis/biorientation.py` lines 75-247; `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py` lines 113-294.

4. Contour and parentage figure:
   DIC cell mask, red/green canonical contour slots, neck split, mother/daughter masks, and downstream CEN-dot classification. Citations: `cytocv/core/services/canonical_contours.py` lines 149-318; `cytocv/core/services/neck_split.py` lines 112-219; `cytocv/core/services/cell_parentage.py` lines 135-336; `cytocv/core/cell_analysis/cen_dot.py` lines 237-467.

5. Export/data schema table:
   Per-cell database fields, JSON properties, applicability rules, and CSV/XLSX column groups. Citations: `cytocv/core/models.py::CellStatistics` lines 287-397; `cytocv/core/services/stat_applicability.py` lines 16-278; `cytocv/core/services/stat_export_selection.py` lines 19-253; `cytocv/core/tables.py` lines 54-925.

## 12. Claims that require biology-side confirmation before submission

- That detected red or green contours correspond to the intended biological puncta across representative datasets. Software contour logic is documented, but biological identity is not validated by code. Citations for software logic: `cytocv/core/contour_processing/contour_operations.py::find_contours()` lines 2528-2829; `cytocv/core/services/canonical_contours.py` lines 149-186.
- That CEN-dot category labels correspond to experimentally validated CEN states. The code computes category labels from contour geometry and thresholds. Citations: `cytocv/core/cell_analysis/cen_dot.py` lines 237-467; `cytocv/core/models.py` lines 246-284.
- That on-axis/off-axis biorientation counts match a specific biological biorientation state. The code measures geometry relative to a red-red axis. Citations: `cytocv/core/cell_analysis/biorientation.py` lines 75-247.
- That mother/daughter assignment is correct for all relevant morphologies. The code infers parentage from DIC geometry and area/fallback logic. Citations: `cytocv/core/services/neck_split.py` lines 112-219; `cytocv/core/services/cell_parentage.py` lines 135-336.
- That default thresholds are biologically optimal. Defaults are software preferences and should be justified or tuned experimentally. Citations: `cytocv/accounts/preferences.py` lines 65-114; `cytocv/core/services/biorientation_config.py` line 5.
- That Mask R-CNN segmentation accuracy is sufficient for the manuscript's biological examples. Documentation notes model weights are not bundled and claims should be limited. Citations: `docs/research/methods-and-system-description.md` lines 62-65.
- That micron-scale metadata is correct for all example datasets. Scale extraction and fallback behavior are implemented, but acquisition metadata/manual values require confirmation. Citations: `cytocv/core/metadata_processing/dv_scale_parser.py` lines 50-106; `cytocv/core/metadata_processing/tiff_scale_parser.py` lines 12-176; `cytocv/core/scale.py` lines 8-503.

## 13. Claims that should be avoided because they overstate validation

- Avoid: "CytoCV automatically determines biological CEN status."
  Use: "CytoCV computes a CEN-dot classification from detected red/green contours, mother/daughter side masks, and user-defined thresholds." Citations: `cytocv/core/cell_analysis/cen_dot.py` lines 237-467.

- Avoid: "Biorientation is validated automatically."
  Use: "CytoCV counts green contours on or off a red-red axis using a configurable collinearity threshold." Citations: `cytocv/core/cell_analysis/biorientation.py` lines 75-247.

- Avoid: "The software identifies mother and daughter cells with complete accuracy."
  Use: "CytoCV infers mother/daughter sides from DIC geometry, assigning the larger side as mother after a valid neck split or using a fallback method." Citations: `cytocv/core/services/neck_split.py` lines 112-219; `cytocv/core/services/cell_parentage.py` lines 135-336.

- Avoid: "All fluorescence puncta are true biological dots."
  Use: "CytoCV detects fluorescence contour candidates using thresholding, optional splitting, filtering, and DIC-mask clipping; users should review results." Citations: `cytocv/core/contour_processing/contour_operations.py` lines 2528-2983; `cytocv/core/services/canonical_contours.py` lines 149-186.

- Avoid: "Every current feature is biologically validated."
  Use: "The repository includes software tests for validation, export, scale conversion, contour handling, and plugin behavior; biological validation should be documented separately." Citations: `cytocv/core/tests/test_stats_validation.py` lines 64-778; `cytocv/core/tests/test_biorientation.py` lines 105-324; `cytocv/core/tests/test_cen_dot_classification.py` lines 150-464; `docs/research/reproducibility-and-validation.md` line 43.

- Avoid: "Micron measurements are always exact."
  Use: "Micron measurements depend on extracted or manually supplied pixel scale and use x/y scale conversion where available." Citations: `cytocv/core/scale.py` lines 8-503.

- Avoid: "Single-channel puncta modes measure cross-channel signal."
  Use: "Red-only and green-only puncta modes compute same-channel puncta and contour metrics and mark opposite-channel fields unavailable." Citations: `cytocv/core/services/puncta_line_mode.py` lines 38-95; `cytocv/core/cell_analysis/puncta_distance.py` lines 37-245.
