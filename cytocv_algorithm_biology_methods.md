# CytoCV Algorithm and Biology-Methods Compendium

Repository audited at commit `a3ed23ed3b861729d2caa960524e55e17c4d9977`. This compendium describes software measurements and processing logic only. It does not claim that any measurement is a validated biological conclusion unless a cited test or documented biology-side validation supports that claim.

## Emily's Questions Answered Directly

- How red and green contours are determined for puncta:
  Red puncta contours are detected from the preprocessed red image family. `find_contours()` reads `gray_red_3`/`gray_red`, thresholds the red signal using an Otsu-derived low value plus an offset, finds external contours, optionally applies red dot splitting, and keeps small dot contours under an area cap for the `dot_contours` family. Green contours are detected from `gray_green`, thresholded using an Otsu-derived low value plus an offset, morphologically closed, optionally split, optionally filtered, and returned as `contours_green`. Canonical contour slots then fill each raw contour into a mask, clip it to the DIC-derived cell mask, split any remaining pieces into external contours, compute area and centroid, sort by descending area and position, and limit the number of slots used by downstream plugins. Citations: `cytocv/core/contour_processing/contour_operations.py::find_contours()` lines 2528-2829; `cytocv/core/services/canonical_contours.py::build_canonical_contour_slots()` lines 149-186; `cytocv/core/services/canonical_contours.py::get_canonical_red_slots()` lines 331-347; `cytocv/core/services/canonical_contours.py::get_canonical_green_slots()` lines 350-366.

- How total, max, and mean/average red/green intensities are calculated:
  The software selects a grayscale measurement image, applies a binary contour mask, and computes `total=sum(values)`, `max=max(values)`, and `mean=mean(values)` over pixels where `mask > 0`. Empty masks return zeros. Citations: `cytocv/core/image_processing/image_helper.py::calculate_masked_intensity_stats()` lines 27-40; `cytocv/core/cell_analysis/green_red_intensity.py::GreenRedIntensity._store_intensity_stats()` lines 58-64.

- How distance between puncta of the same color is calculated:
  In red-only or green-only puncta modes, `PunctaDistance` takes the first two canonical source contour centers and stores Euclidean pixel distance with `math.dist(center1, center2)`. Citations: `cytocv/core/cell_analysis/puncta_distance.py::PunctaDistance.calculate_statistics()` lines 293-318.

- How distance from green to red or red to green is calculated for each contour:
  `GreenRedIntensity` computes, for each green slot, the nearest red contour center by Euclidean `math.dist()`, stores `distance_of_green_from_red`, and stores the center-to-center `delta_x` and `delta_y` in `properties`. The code records green-to-nearest-red distance; it does not store a symmetric per-red nearest-green table. Citations: `cytocv/core/cell_analysis/green_red_intensity.py::GreenRedIntensity.calculate_statistics()` lines 148-173.

- How x,y coordinates of puncta are computed and stored:
  Canonical contour centers are mask centroids computed from moments, with a nonzero-pixel mean fallback. The local crop center is converted to full-image coordinates as `x = crop_left + local_x` and `y = main_height - 1 - (crop_top + local_y)`, so stored y coordinates use a bottom-left image coordinate convention. Plugin properties store center values such as `red_contour_center_x_px`, `red_contour_center_y_px`, `green_contour_center_x_px`, and `green_contour_center_y_px`. Citations: `cytocv/core/services/canonical_contours.py::_mask_center()` lines 136-146; `cytocv/core/services/canonical_contours.py::build_canonical_contour_slots()` lines 149-186; `cytocv/core/cell_analysis/green_red_intensity.py::GreenRedIntensity.calculate_statistics()` lines 122-133 and 166-173.

- How intensity over the line between puncta is calculated:
  `PunctaDistance` rounds the two source contour centers, draws a `cv2.line()` into a binary mask at the user-defined thickness, takes all coordinates where the line mask is positive, and sums the measurement image values at those coordinates. Citations: `cytocv/core/cell_analysis/puncta_distance.py::PunctaDistance.calculate_statistics()` lines 320-348.

- How the user-defined line-width setting is used:
  User line width is normalized during preprocessing to a pixel integer, with micron inputs converted using the active scale context. `PunctaDistance` passes that pixel width directly as the `thickness` argument to `cv2.line()`. Citations: `cytocv/core/services/segmentation_pipeline.py::segment_images()` lines 842-879; `cytocv/core/scale.py::convert_length_to_pixels()` lines 477-503; `cytocv/core/cell_analysis/puncta_distance.py::PunctaDistance.calculate_statistics()` lines 320-341.

- How contour determination differs for nuclear intensity vs puncta analysis:
  Puncta analysis uses red dot contours or green fluorescence contours as small puncta sources and can use two source contours for distance/line measurements. Nuclear-cell-pair analysis chooses one nucleus contour from the configured nuclear channel, optionally using alternate detection, clips the filled nuclear mask to the DIC cell mask, and measures whole-cell, nuclear, and cytoplasmic intensity sums rather than puncta-to-puncta line intensity. Citations: `cytocv/core/cell_analysis/puncta_distance.py::PunctaDistance.calculate_statistics()` lines 258-348; `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py::NuclearCellPairIntensity.calculate_statistics()` lines 177-276.

- How cytoplasmic intensity is determined, if still implemented:
  Cytoplasmic intensity is still implemented in nuclear-cell-pair analysis as `cell_pair_intensity_sum - nucleus_intensity_sum`, with a nuclear-to-cytoplasmic ratio returned only when the cytoplasmic denominator is positive and finite. Legacy nucleus modules also populate cytoplasmic-style fields. Citations: `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py::NuclearCellPairIntensity._nuclear_cytoplasmic_ratio()` lines 88-103; `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py::NuclearCellPairIntensity.calculate_statistics()` lines 258-276; `cytocv/core/cell_analysis/nucleus_intensity.py::NucleusIntensity.calculate_statistics()` lines 65-85.

- How CEN dots are identified and quantified:
  `CENDot` requires exactly two deduplicated red canonical slots, checks that their center distance meets the configured minimum, assigns each red dot to mother or daughter side using overlap with DIC-derived side masks, requires the two red dots to occupy opposite sides, associates nearby green slots to the mother and daughter red dots within a configured proximity radius, and classifies the result as mother-and-daughter, mother-only, daughter-only, or none/N/A. Citations: `cytocv/core/cell_analysis/cen_dot.py::CENDot.calculate_statistics()` lines 237-467.

- How mother and daughter distinctions are made:
  The neck-split service attempts to find a neck chord from DIC cell shape geometry, splits the DIC mask into two side masks, and treats the larger side as mother and the smaller side as daughter. If a valid neck split is unavailable, parentage can fall back to a principal-axis/area threshold method. Citations: `cytocv/core/services/neck_split.py::detect_neck_split()` lines 112-174; `cytocv/core/services/neck_split.py::compute_side_areas()` lines 177-219; `cytocv/core/services/cell_parentage.py::_derive_from_neck_split()` lines 135-170; `cytocv/core/services/cell_parentage.py::derive_cell_parentage()` lines 310-336.

- How CEN dot user-defined settings are used:
  The minimum red-red distance threshold and green proximity radius are read from settings, interpreted in pixels or microns according to the selected unit, and used to reject close red pairs and to associate green dots with mother/daughter red anchors. Citations: `cytocv/core/cell_analysis/cen_dot.py::CENDot._distance_between_centers()` lines 50-69; `cytocv/core/cell_analysis/cen_dot.py::CENDot._distance_meets_threshold()` lines 71-84; `cytocv/core/cell_analysis/cen_dot.py::CENDot._proximity_radius_pixels()` lines 86-109; `cytocv/core/cell_analysis/cen_dot.py::CENDot.calculate_statistics()` lines 249-404.

- How on-axis vs off-axis dots are determined from the collinearity threshold:
  `Biorientation` defines the axis between the two red dots. Each green dot must lie inside the DIC pair mask and project onto the red-red segment with anchor padding. The perpendicular distance from the green center to the red-red line is calculated by the cross-product line-distance formula; if it is less than or equal to the collinearity threshold, the dot is counted on-axis/collinear, otherwise it is counted off-axis. Citations: `cytocv/core/cell_analysis/biorientation.py::Biorientation.calculate_statistics()` lines 158-183; `cytocv/core/cell_analysis/biorientation.py::Biorientation._projects_within_segment()` lines 194-217; `cytocv/core/cell_analysis/biorientation.py::Biorientation._is_collinear()` lines 219-247.

- How on-axis/off-axis dots are counted:
  Green slots passing the DIC mask and projection tests increment either `colinear_dot_count` or `off_axis_dot_count`; both counts are capped at 2. Citations: `cytocv/core/cell_analysis/biorientation.py::Biorientation.calculate_statistics()` lines 158-186.

- How dot splitting works under each split setting:
  Dot splitting is controlled by a split mode configuration. The current parameter table defines `balanced` and `aggressive` modes with the same thresholds, while `disabled` leaves contours unsplit. When enabled, the contour processor tries deterministic split candidates based on watershed/chord/peak/shape evidence and accepts child contours only when validation checks pass for area, circularity, solidity, aspect ratio, peak ratios, combined area, area fractions, center separation, peak labels, and neck alignment. Citations: `cytocv/core/contour_processing/contour_operations.py::DOT_SPLIT_PARAMS` lines 45-130; `cytocv/core/contour_processing/contour_operations.py::validate_split_contours()` lines 999-1098; `cytocv/core/contour_processing/contour_operations.py::_split_merged_green_contours()` lines 2375-2396.

- What “filter green contours” does when selected:
  Green contour filtering removes green contours that are too small, preserves contours passing legacy shape evidence, and otherwise compares filled-contour signal to a dilated local ring. It accepts contours with strong internal peak contrast and rejects weak or likely background contours. When splitting and filtering are both enabled, accepted split pairs are preserved atomically through the filter. Citations: `cytocv/core/contour_processing/contour_operations.py::_postprocess_and_filter_aggressive_green_contours()` lines 2345-2372; `cytocv/core/contour_processing/contour_operations.py::_filter_green_contours_with_image()` lines 2866-2983.

- What red-only and green-only puncta modes hide, show, compute, and export:
  Red-only mode uses red contours as the puncta source and has no measurement channel; green-only mode uses green contours as the puncta source and has no measurement channel. Both modes compute same-color contour size, same-channel total/max/average intensities if contour-intensity stats are enabled, same-color centers, and same-color distance/line geometry when two source contours exist. They mark paired/opposite-channel fields unavailable so tables and exports can show `N/A` or omit inapplicable values. Citations: `cytocv/core/services/puncta_line_mode.py::LINE_MODE_CONFIGS` lines 38-59; `cytocv/core/cell_analysis/puncta_distance.py::_RED_ONLY_UNAVAILABLE_FIELDS` lines 37-82; `cytocv/core/cell_analysis/puncta_distance.py::_GREEN_ONLY_UNAVAILABLE_FIELDS` lines 84-129; `cytocv/core/cell_analysis/puncta_distance.py::PunctaDistance._store_same_channel_contour_stats()` lines 187-245; `cytocv/core/services/stat_applicability.py::unavailable_stat_fields()` lines 198-205.

- What fields are set to unavailable/null/ND when a channel is missing:
  The upload and analysis setup block selected plugins when their required channels are absent, except single-channel puncta modes intentionally reduce channel requirements. For single-channel modes, `PunctaDistance` records unavailable paired fields in `properties["unavailable_stat_fields"]`, and display/export logic uses applicability rules to render `N/A`. If `GreenRedIntensity` runs without a red or green image, it stores zeros for red/green contour size, intensity, centers, and distance fields. If `NuclearCellPairIntensity` lacks its source or measurement image, it clears nuclear/cell/cytoplasmic fields and records status `missing_channel`. CEN dot categories can be `N/A`, and legacy/old-schema CEN rows can be labeled as needing rerun. Citations: `cytocv/core/stats_plugins.py::get_required_channels_for_selection()` lines 240-253; `cytocv/core/services/signal_quantification.py::resolve_signal_quantification_selection()` lines 242-386; `cytocv/core/cell_analysis/puncta_distance.py::PunctaDistance._merge_unavailable_fields()` lines 160-169; `cytocv/core/cell_analysis/green_red_intensity.py::GreenRedIntensity.calculate_statistics()` lines 102-115; `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py::NuclearCellPairIntensity.calculate_statistics()` lines 143-156; `cytocv/core/models.py::get_cen_dot_category_label()` lines 255-284; `cytocv/core/tables.py::CellStatisticsTable._export_value()` lines 509-565.

## PunctaDistance

- File(s):
  `cytocv/core/cell_analysis/puncta_distance.py`; `cytocv/core/services/puncta_line_mode.py`; `cytocv/core/services/canonical_contours.py`; `cytocv/core/image_processing/image_helper.py`.

- Main class/function(s):
  `PunctaDistance`; `PunctaDistance.calculate_statistics()`; `PunctaDistance._source_image()`; `PunctaDistance._measurement_image()`; `get_canonical_red_slots()`; `get_canonical_green_slots()`.

- User-facing name:
  `PunctaDistance` / puncta distance and puncta line intensity.

- Biological purpose:
  Measures spatial separation between two fluorescence puncta within a segmented cell or cell pair, and optionally measures intensity along the line connecting those puncta. The measurement is intended to quantify puncta geometry and intervening signal, not to infer a biological mechanism by itself.

- Required channels:
  DIC is universally required for segmentation. In paired red-green mode, Red and Green are required. In red-only mode, Red is required. In green-only mode, Green is required.

- Optional channels:
  Blue is optional. The opposite fluorescence channel is optional only in single-channel red-only or green-only modes.

- Input images used:
  Source contour image depends on line mode: Red source modes use red contour slots derived from red preprocessing; Green source modes use green contour slots. Measurement image is Green for red-puncta mode and Red for green-puncta mode. Single-channel modes have no opposite-channel measurement image.

- Input masks/contours used:
  DIC-derived cell mask; canonical red slots from `dot_contours`; canonical green slots from `contours_green`; source contour centers and source masks.

- User parameters and defaults:
  Selected plugin defaults include `PunctaDistance`. Default puncta line mode is `red_puncta`. Default line width is `1` in the user's active length unit. Contour-intensity statistics are enabled by default. Defaults are stored in user preferences.

- Step-by-step algorithm:
  1. Resolve the puncta line mode and identify source color and measurement color.
  2. Load the source image and, for paired modes, the opposite-channel measurement image.
  3. Retrieve canonical source contour slots, clipped to the DIC cell mask.
  4. In red-only or green-only modes, store same-channel contour intensity and unavailable-field metadata.
  5. If fewer than two source slots are present, return without distance/line measurements.
  6. Take the centers of the first two source slots and compute Euclidean center distance.
  7. Draw a line between the rounded centers using the normalized pixel line width.
  8. Sum measurement-image pixels under the line mask for paired modes.
  9. Store distance, line intensity, center coordinates, line geometry, visibility, and unavailable-field metadata in `CellStatistics`.

- Exact formulas:
  `puncta_distance = sqrt((x2 - x1)^2 + (y2 - y1)^2)` via `math.dist()`. Line intensity is `sum(I[y, x] for (x, y) where line_mask[y, x] > 0)`. Same-channel contour intensity uses `total=sum(masked pixels)`, `max=max(masked pixels)`, and `average=mean(masked pixels)`.

- Output fields:
  `puncta_distance`; `puncta_line_intensity`; `properties["puncta_line"]`; contour center fields such as `red_contour_center_x_px`, `red_contour_center_y_px`, `green_contour_center_x_px`, `green_contour_center_y_px`; same-channel intensity fields in red-only or green-only modes; `properties["unavailable_stat_fields"]`.

- Display/export behavior:
  Distance and line intensity are table/export fields when applicable. Single-channel modes mark opposite-channel fields unavailable so display and export can show `N/A` or suppress inapplicable values depending on filter settings.

- Biological interpretation:
  A larger distance indicates wider separation of the selected puncta centers. Line intensity is a raw summed signal along the center-to-center line and should be interpreted as a software-derived fluorescence measurement sensitive to image preprocessing, line width, and contour selection.

- Assumptions:
  The first two canonical source slots represent the biologically relevant puncta. The DIC segmentation and fluorescence contour detection are adequate for the cell. Pixel intensity values are not background-normalized beyond the selected image preprocessing path unless the measurement image itself is background-subtracted.

- Failure/NA cases:
  Missing required channel should block the selected mode during validation. If fewer than two source contours are available, distance and line intensity are not produced. Single-channel modes mark paired/opposite-channel fields unavailable. Exceptions are caught and return empty statistics.

- Validation status or tests:
  Software behavior is covered by contour/statistics tests, including modern contour statistics and single-channel validation cases. These are regression tests, not biological validation of puncta identity.

- Plain-English explanation for biologists:
  CytoCV finds the two strongest usable puncta contours of the chosen color inside each DIC-segmented cell, records how far apart their centers are, and can add up fluorescence along the line connecting them.

- Manuscript-ready methods paragraph:
  Puncta distance was computed from fluorescence contours clipped to the DIC-derived cell mask. For each cell, canonical puncta contours were generated by filling detected red or green fluorescence contours, intersecting them with the cell mask, extracting external components, and sorting retained components by area and position. The centers of the first two retained source contours were used to compute Euclidean center-to-center distance. For paired red-green modes, a line mask was drawn between these centers using the user-specified line width converted to pixels, and fluorescence intensity in the opposite channel was summed over pixels intersecting the line mask. Single-channel red-only and green-only modes report same-color contour metrics and mark opposite-channel measurements as unavailable.

- File/path/line citations:
  `cytocv/core/cell_analysis/puncta_distance.py::PunctaDistance` lines 30-354; `cytocv/core/services/puncta_line_mode.py::LINE_MODE_CONFIGS` lines 38-59; `cytocv/core/services/canonical_contours.py::build_canonical_contour_slots()` lines 149-186; `cytocv/core/image_processing/image_helper.py::calculate_masked_intensity_stats()` lines 27-40; `cytocv/core/tests/test_stats_validation.py` lines 734-778; `cytocv/core/tests/test_modern_contour_statistics.py` lines 331-1606.

## Red-only puncta mode

- File(s):
  `cytocv/core/services/puncta_line_mode.py`; `cytocv/core/cell_analysis/puncta_distance.py`; `cytocv/core/services/signal_quantification.py`; `cytocv/core/services/stat_applicability.py`.

- Main class/function(s):
  `LINE_MODE_CONFIGS`; `is_single_channel_mode()`; `PunctaDistance._store_same_channel_contour_stats()`; `PunctaDistance._merge_unavailable_fields()`; `resolve_signal_quantification_selection()`.

- User-facing name:
  Red-only puncta mode.

- Biological purpose:
  Supports datasets where only red puncta are present or should be analyzed, allowing red puncta geometry and red-in-red contour intensity measurements without requiring a green channel.

- Required channels:
  DIC and Red.

- Optional channels:
  Blue and Green are optional and not required for this mode.

- Input images used:
  Red source image and red measurement image for same-channel contour intensity.

- Input masks/contours used:
  DIC-derived cell mask; canonical red slots from red `dot_contours`.

- User parameters and defaults:
  The user selects puncta line mode `red_puncta_only`. Line width remains available for line geometry if two red puncta are present. Contour-intensity statistics follow the global contour-intensity toggle.

- Step-by-step algorithm:
  1. Resolve line mode to `source_channel=Red` and `measurement_channel=None`.
  2. Reduce required fluorescence channels to Red for selected puncta analysis.
  3. Build canonical red source slots clipped to the DIC mask.
  4. Store red contour centers and red-in-red total/max/average intensity when contour-intensity stats are enabled.
  5. If two red slots are present, compute same-color puncta distance and line geometry.
  6. Record unavailable green/opposite-channel fields in `properties`.

- Exact formulas:
  Same-color distance is Euclidean center distance. Red-in-red intensity is computed as total/max/mean of red measurement pixels under each red contour mask.

- Output fields:
  `puncta_distance`; red contour center fields; `red_contour_size`; `red_in_red_total_intensity`; `red_in_red_max_intensity`; `red_in_red_average_intensity`; unavailable-field metadata for green/opposite-channel fields.

- Display/export behavior:
  Red-only applicable fields can appear in Display/Dashboard and export. Green and paired red-green fields are marked unavailable and rendered/exported as not applicable where the table/export layer honors field applicability.

- Biological interpretation:
  Reports the separation and same-channel signal of red puncta only. It should not be interpreted as red-green colocalization or cross-channel signal.

- Assumptions:
  Red puncta are adequately segmented by the red contour pipeline and the two selected canonical red slots are the intended dots.

- Failure/NA cases:
  Missing Red should block the mode. Fewer than two red slots prevents same-color distance. Green-derived fields are intentionally unavailable.

- Validation status or tests:
  Single-channel validation and table/applicability behavior are covered by tests, but biology-side validation of red puncta identity is not established in code.

- Plain-English explanation for biologists:
  This mode analyzes red dots by themselves and removes green-dependent measurements from the output.

- Manuscript-ready methods paragraph:
  For red-only puncta analysis, CytoCV used red fluorescence contours clipped to the DIC cell mask as the puncta source. Red contour centers and red-channel intensity statistics within red contour masks were recorded when contour intensity reporting was enabled. Measurements that require a green channel or red-green pairing were flagged as unavailable for display and export.

- File/path/line citations:
  `cytocv/core/services/puncta_line_mode.py::LINE_MODE_CONFIGS` lines 38-59; `cytocv/core/services/puncta_line_mode.py::required_channels_for_line_mode()` lines 87-95; `cytocv/core/cell_analysis/puncta_distance.py::_RED_ONLY_UNAVAILABLE_FIELDS` lines 37-82; `cytocv/core/cell_analysis/puncta_distance.py::PunctaDistance._store_same_channel_contour_stats()` lines 187-245; `cytocv/core/services/signal_quantification.py::resolve_signal_quantification_selection()` lines 242-386; `cytocv/core/tests/test_stats_validation.py` lines 734-778.

## Green-only puncta mode

- File(s):
  `cytocv/core/services/puncta_line_mode.py`; `cytocv/core/cell_analysis/puncta_distance.py`; `cytocv/core/services/signal_quantification.py`; `cytocv/core/services/stat_applicability.py`.

- Main class/function(s):
  `LINE_MODE_CONFIGS`; `is_single_channel_mode()`; `PunctaDistance._store_same_channel_contour_stats()`; `PunctaDistance._merge_unavailable_fields()`; `resolve_signal_quantification_selection()`.

- User-facing name:
  Green-only puncta mode.

- Biological purpose:
  Supports datasets where only green puncta are present or should be analyzed, allowing green puncta geometry and green-in-green contour intensity measurements without requiring a red channel.

- Required channels:
  DIC and Green.

- Optional channels:
  Blue and Red are optional and not required for this mode.

- Input images used:
  Green source image and green measurement image for same-channel contour intensity.

- Input masks/contours used:
  DIC-derived cell mask; canonical green slots from `contours_green`.

- User parameters and defaults:
  The user selects puncta line mode `green_puncta_only`. Line width remains available for line geometry if two green puncta are present. Contour-intensity statistics follow the global contour-intensity toggle.

- Step-by-step algorithm:
  1. Resolve line mode to `source_channel=Green` and `measurement_channel=None`.
  2. Reduce required fluorescence channels to Green for selected puncta analysis.
  3. Build canonical green source slots clipped to the DIC mask.
  4. Store green contour centers and green-in-green total/max/average intensity when contour-intensity stats are enabled.
  5. If two green slots are present, compute same-color puncta distance and line geometry.
  6. Record unavailable red/opposite-channel fields in `properties`.

- Exact formulas:
  Same-color distance is Euclidean center distance. Green-in-green intensity is computed as total/max/mean of green measurement pixels under each green contour mask.

- Output fields:
  `puncta_distance`; green contour center fields; `green_contour_size`; `green_in_green_total_intensity`; `green_in_green_max_intensity`; `green_in_green_average_intensity`; unavailable-field metadata for red/opposite-channel fields.

- Display/export behavior:
  Green-only applicable fields can appear in Display/Dashboard and export. Red and paired red-green fields are marked unavailable and rendered/exported as not applicable where the table/export layer honors field applicability.

- Biological interpretation:
  Reports the separation and same-channel signal of green puncta only. It should not be interpreted as red-green colocalization or cross-channel signal.

- Assumptions:
  Green puncta are adequately segmented by the green contour pipeline and the two selected canonical green slots are the intended dots.

- Failure/NA cases:
  Missing Green should block the mode. Fewer than two green slots prevents same-color distance. Red-derived fields are intentionally unavailable.

- Validation status or tests:
  Single-channel validation and table/applicability behavior are covered by tests, but biology-side validation of green puncta identity is not established in code.

- Plain-English explanation for biologists:
  This mode analyzes green dots by themselves and removes red-dependent measurements from the output.

- Manuscript-ready methods paragraph:
  For green-only puncta analysis, CytoCV used green fluorescence contours clipped to the DIC cell mask as the puncta source. Green contour centers and green-channel intensity statistics within green contour masks were recorded when contour intensity reporting was enabled. Measurements that require a red channel or red-green pairing were flagged as unavailable for display and export.

- File/path/line citations:
  `cytocv/core/services/puncta_line_mode.py::LINE_MODE_CONFIGS` lines 38-59; `cytocv/core/services/puncta_line_mode.py::required_channels_for_line_mode()` lines 87-95; `cytocv/core/cell_analysis/puncta_distance.py::_GREEN_ONLY_UNAVAILABLE_FIELDS` lines 84-129; `cytocv/core/cell_analysis/puncta_distance.py::PunctaDistance._store_same_channel_contour_stats()` lines 187-245; `cytocv/core/services/signal_quantification.py::resolve_signal_quantification_selection()` lines 242-386; `cytocv/core/tests/test_stats_validation.py` lines 734-778.

## GreenRedIntensity

- File(s):
  `cytocv/core/cell_analysis/green_red_intensity.py`; `cytocv/core/services/canonical_contours.py`; `cytocv/core/services/measurement_contour_ratio.py`; `cytocv/core/image_processing/image_helper.py`.

- Main class/function(s):
  `GreenRedIntensity`; `GreenRedIntensity.calculate_statistics()`; `GreenRedIntensity._store_intensity_stats()`; `store_measurement_contour_ratios()`.

- User-facing name:
  GreenRedIntensity / red and green contour intensity.

- Biological purpose:
  Quantifies red and green signal within red and green puncta contours and measures the spatial relationship of green contours to the nearest red contour.

- Required channels:
  DIC, Red, and Green.

- Optional channels:
  Blue is optional.

- Input images used:
  Raw red and raw green images are preferred. If raw images are unavailable, the code falls back to red/green background-subtracted or grayscale preprocessing outputs.

- Input masks/contours used:
  DIC-clipped canonical red slots and green slots.

- User parameters and defaults:
  Enabled by default in selected plugins. Measurement/contour ratio mode is derived from the signal quantification mode. Contour-intensity stats can be enabled/disabled through analysis settings.

- Step-by-step algorithm:
  1. Select red and green measurement images, preferring raw channel arrays.
  2. If either measurement image is missing, store zero/default contour metrics and return.
  3. Retrieve up to three canonical red slots and green slots.
  4. Store contour centers in `properties`.
  5. For each red slot, compute red-in-red and green-in-red total/max/average intensities and red contour size.
  6. For each green slot, identify the nearest red center, compute red-in-green and green-in-green total/max/average intensities, compute green contour size, and store green-to-red distance.
  7. Store center delta properties and measurement/contour ratio values.

- Exact formulas:
  Intensity triplets are `sum`, `max`, and `mean` over masked pixels. `distance_of_green_from_red = min(math.dist(green_center, red_center) for red_center in red_centers)`. Ratio helper formulas include `green_in_red / red_in_red` for red-contour mode and `red_in_green / green_in_green` for green-contour mode, with zero returned for zero denominators.

- Output fields:
  `red_contour_size`; `green_contour_size`; `red_in_red_total_intensity`; `red_in_red_max_intensity`; `red_in_red_average_intensity`; `green_in_red_total_intensity`; `green_in_red_max_intensity`; `green_in_red_average_intensity`; `red_in_green_total_intensity`; `red_in_green_max_intensity`; `red_in_green_average_intensity`; `green_in_green_total_intensity`; `green_in_green_max_intensity`; `green_in_green_average_intensity`; `distance_of_green_from_red`; `green_red_intensity`; ratio fields in `properties`.

- Display/export behavior:
  Fields are available in tables and CSV/XLSX exports when the plugin is active and field applicability permits them. Spatial distances can be displayed/exported in pixels or microns depending on the active scale setting.

- Biological interpretation:
  Reports fluorescence signal overlap and proximity between red and green detected contours. It provides quantitative features for interpretation but does not by itself establish colocalization, interaction, or biological state.

- Assumptions:
  Red and green contour masks are biologically meaningful. The nearest red contour is the relevant red reference for each green contour. Raw intensity values are comparable across cells only under appropriate imaging controls.

- Failure/NA cases:
  Missing Red or Green should generally block the plugin. If run with missing images, the code stores zeros/defaults. Empty masks return zero intensity statistics.

- Validation status or tests:
  Software behavior is covered by tests for modern contour statistics, raw intensity selection, ratio behavior, and missing-channel validation. These tests validate implementation behavior, not biological ground truth.

- Plain-English explanation for biologists:
  CytoCV measures how much red and green signal sits inside red and green dot outlines and how far each green dot is from the closest red dot.

- Manuscript-ready methods paragraph:
  Red-green intensity analysis used canonical red and green fluorescence contour masks clipped to each DIC-segmented cell. Raw red and green images were used for measurement when available, with preprocessed fallbacks otherwise. For red contours, CytoCV computed red and green total, maximum, and mean intensity within the red mask. For green contours, it computed red and green total, maximum, and mean intensity within the green mask and recorded the distance from each green contour center to the nearest red contour center. Ratio fields were computed from selected measurement/contour intensity pairs with zero-denominator protection.

- File/path/line citations:
  `cytocv/core/cell_analysis/green_red_intensity.py::GreenRedIntensity` lines 26-178; `cytocv/core/image_processing/image_helper.py::calculate_masked_intensity_stats()` lines 27-40; `cytocv/core/services/measurement_contour_ratio.py` lines 9-46 and 100-157; `cytocv/core/tests/test_stats_validation.py` lines 521-633; `cytocv/core/tests/test_modern_contour_statistics.py` lines 331-1606.

## NuclearCellPairIntensity

- File(s):
  `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py`; `cytocv/core/cell_analysis/nuclear_cell_pair_legacy_scaled.py`; `cytocv/core/services/canonical_contours.py`.

- Main class/function(s):
  `NuclearCellPairIntensity`; `NuclearCellPairIntensity.calculate_statistics()`; `NuclearCellPairIntensity._nuclear_cytoplasmic_ratio()`; `nuclear_cell_pair_legacy_scaled` helpers.

- User-facing name:
  Nuclear-cell-pair intensity.

- Biological purpose:
  Measures signal in a whole DIC-segmented cell pair, a detected nuclear contour, and the inferred cytoplasmic region outside the nucleus.

- Required channels:
  DIC plus the configured nuclear contour channel and the configured measurement channel. Default mode uses Green as the nuclear contour channel and Red as the measurement channel.

- Optional channels:
  Blue is optional unless a legacy or alternate setting uses it.

- Input images used:
  In default `green_nucleus` mode, green images are used to determine the nuclear contour and red images are used for measurement. In `red_nucleus` mode, red images determine the contour and green images are measured.

- Input masks/contours used:
  DIC-derived cell mask; one canonical or alternate nuclear contour slot; filled nuclear mask clipped to the cell mask.

- User parameters and defaults:
  User can select nuclear/cell-pair mode, alternate nucleus detection, and legacy scaled behavior. Defaults are stored in preferences; the default nuclear mode is `green_nucleus`.

- Step-by-step algorithm:
  1. Resolve nuclear mode to a contour channel and measurement channel.
  2. Select contour and measurement images.
  3. If an image is missing, clear nuclear/cell/cytoplasmic fields and record `missing_channel`.
  4. Load the DIC cell mask for the cell.
  5. Choose a single nuclear contour slot from the configured channel, optionally using alternate detection.
  6. Fill and normalize the nuclear mask and clip it to the DIC cell mask.
  7. Sum measurement-channel pixels over the full cell mask and over the nuclear mask.
  8. Compute cytoplasmic signal as cell sum minus nuclear sum.
  9. Compute nuclear/cytoplasmic ratio if the cytoplasmic denominator is valid.
  10. Store status, contour metadata, sums, ratio, and optional drawing artifacts.

- Exact formulas:
  `cell_pair_intensity_sum = sum(I[p] for p in cell_mask)`. `nucleus_intensity_sum = sum(I[p] for p in nucleus_mask)`. `cytoplasmic_intensity_sum = cell_pair_intensity_sum - nucleus_intensity_sum`. `nuclear_cytoplasmic_ratio = nucleus_intensity_sum / cytoplasmic_intensity_sum` when cytoplasmic sum is positive and finite; otherwise null.

- Output fields:
  `cell_pair_intensity_sum`; `nucleus_intensity_sum`; `cytoplasmic_intensity_sum`; `nuclear_cytoplasmic_ratio`; nuclear contour status/metadata in `properties`; optional drawing path.

- Display/export behavior:
  Nuclear/cell-pair fields are displayed/exported when applicable. Missing contour or missing channel statuses drive unavailable/`N/A` rendering in table logic.

- Biological interpretation:
  Quantifies a measurement-channel signal partitioned into whole-cell-pair, nuclear-contour, and non-nuclear/cytoplasmic compartments. The cytoplasmic region is computationally inferred as the DIC cell mask minus the nuclear mask.

- Assumptions:
  The chosen fluorescence contour corresponds to the nucleus or nuclear proxy. The DIC mask represents the full cell pair. The selected measurement channel is appropriate for the biological signal being quantified.

- Failure/NA cases:
  Missing contour or measurement image, missing cell mask, no nuclear slot, empty clipped nuclear mask, or contour extraction failure produce cleared fields and status metadata rather than a biological conclusion.

- Validation status or tests:
  Implementation behavior is covered by nuclear cell-pair tests and modern contour statistics tests. These tests check computation and failure handling, not the biological correctness of nuclear identity.

- Plain-English explanation for biologists:
  CytoCV finds one nucleus-like contour, clips it inside the DIC cell outline, adds up the chosen fluorescence signal inside the whole cell and inside that nucleus-like contour, and reports the remaining signal as cytoplasmic.

- Manuscript-ready methods paragraph:
  Nuclear-cell-pair intensity analysis selected a nuclear contour from the configured fluorescence channel and clipped the filled contour to the DIC-derived cell-pair mask. Fluorescence intensity in the configured measurement channel was summed across the full cell mask and across the clipped nuclear mask. Cytoplasmic intensity was computed as the difference between whole-cell-pair and nuclear sums, and a nuclear-to-cytoplasmic ratio was reported only when the cytoplasmic denominator was positive and finite.

- File/path/line citations:
  `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py::NuclearCellPairIntensity` lines 28-294; `cytocv/core/cell_analysis/nuclear_cell_pair_legacy_scaled.py` lines 1-97; `cytocv/core/tests/test_nuclear_cell_pair_intensity.py` lines 120-758; `cytocv/core/tests/test_modern_contour_statistics.py` lines 480-545.

## CENDot

- File(s):
  `cytocv/core/cell_analysis/cen_dot.py`; `cytocv/core/models.py`; `cytocv/core/services/canonical_contours.py`; `cytocv/core/services/cell_parentage.py`; `cytocv/core/services/neck_split.py`.

- Main class/function(s):
  `CENDot`; `CENDot.calculate_statistics()`; `CENDot._distance_between_centers()`; `CENDot._proximity_radius_pixels()`; `CENDot._associate_green_slots()`.

- User-facing name:
  CEN dot / CEN-dot classification.

- Biological purpose:
  Classifies whether green CEN-associated dots are present near red anchor dots on mother and daughter sides of a segmented cell pair.

- Required channels:
  DIC, Red, and Green.

- Optional channels:
  Blue is optional.

- Input images used:
  Red and green preprocessed/canonical contour sources. DIC is used for segmentation and mother/daughter side masks.

- Input masks/contours used:
  DIC pair mask; mother and daughter side masks; canonical red slots; canonical green slots.

- User parameters and defaults:
  CEN red-red minimum distance threshold default is 37 pixels. Green proximity radius default is 13 pixels. The unit can be pixels or microns, with micron conversion using the active scale context.

- Step-by-step algorithm:
  1. Load CEN distance threshold and green proximity settings.
  2. Build cell, mother, and daughter masks from DIC-derived geometry.
  3. Retrieve and deduplicate red and green canonical slots.
  4. Require exactly two red slots.
  5. Compute red-red center distance and require it to meet the configured threshold.
  6. Assign each red slot to mother or daughter side based on overlap with side masks.
  7. Require one red on mother and one red on daughter.
  8. For each green slot inside the pair mask, associate it to the nearest red anchor if within the proximity radius.
  9. Classify as mother-and-daughter, mother-only, daughter-only, none, or N/A.
  10. Store category and diagnostic payload in `properties`.

- Exact formulas:
  Red-red distance is Euclidean in pixels or `sqrt((dx*x_scale)^2 + (dy*y_scale)^2)` in microns. Green association uses squared pixel distance to mother and daughter red centers and accepts only distances within the configured proximity radius.

- Output fields:
  `category_cen_dot`; CEN payload in `properties`; mother/daughter red and green location metadata; failure/status labels.

- Display/export behavior:
  Category labels are rendered from `CategoryCENDot`, including `N/A` for no valid classification and a rerun-required label for old schema rows. CSV/XLSX export uses the table layer's choice-label rendering.

- Biological interpretation:
  Provides a computational classification of green dot presence near red mother/daughter anchors. It should be interpreted as an image-analysis classification requiring biological review, especially for borderline segmentation or ambiguous dot cases.

- Assumptions:
  Exactly two red anchor dots are expected. Mother/daughter side masks reflect the true cell pair geometry. Green dots near red anchors represent the intended CEN signal.

- Failure/NA cases:
  Not exactly two red slots, red dots below the distance threshold, missing mother/daughter masks, both red dots assigned to the same side, ambiguous assignment, no valid green association, or exceptions can produce `N/A` or a none category.

- Validation status or tests:
  CEN classification logic is covered by targeted software tests. These verify classification paths, not biological validation of CEN dot calls.

- Plain-English explanation for biologists:
  CytoCV looks for two red anchor dots, verifies that one is on the mother side and one on the daughter side, and then checks whether green dots are close enough to either anchor to classify the cell pair.

- Manuscript-ready methods paragraph:
  CEN-dot analysis used canonical red and green fluorescence contours clipped to the DIC-derived cell-pair mask. The algorithm required two red anchor contours separated by at least the user-specified distance threshold and assigned them to mother and daughter sides using DIC-derived side masks. Green contours within the cell-pair mask were associated with the nearest red anchor when located within the user-specified proximity radius. The resulting classification reported whether valid green dots were associated with both mother and daughter anchors, only the mother anchor, only the daughter anchor, or neither anchor.

- File/path/line citations:
  `cytocv/core/cell_analysis/cen_dot.py::CENDot` lines 39-467; `cytocv/core/models.py::CategoryCENDot` lines 246-252; `cytocv/core/models.py::get_cen_dot_category_label()` lines 255-284; `cytocv/core/tests/test_cen_dot_classification.py` lines 150-464.

## Biorientation

- File(s):
  `cytocv/core/cell_analysis/biorientation.py`; `cytocv/core/services/biorientation_config.py`; `cytocv/core/services/canonical_contours.py`.

- Main class/function(s):
  `Biorientation`; `Biorientation.calculate_statistics()`; `Biorientation._projects_within_segment()`; `Biorientation._is_collinear()`.

- User-facing name:
  Biorientation.

- Biological purpose:
  Counts green dots that lie on or off the red-red axis in a segmented cell pair, supporting software measurement of dot alignment relative to red anchors.

- Required channels:
  DIC, Red, and Green.

- Optional channels:
  Blue is optional.

- Input images used:
  Red and green contour sources; DIC-derived mask for cell-pair containment.

- Input masks/contours used:
  Canonical red slots; canonical green slots; DIC pair mask.

- User parameters and defaults:
  Red-red distance minimum default is 0, maximum default is 37 pixels, and collinearity threshold default is 3 pixels. Thresholds can be interpreted in pixels or microns depending on settings.

- Step-by-step algorithm:
  1. Read configured red-red distance bounds and collinearity threshold.
  2. Retrieve and deduplicate red and green slots.
  3. Require exactly two red slots.
  4. Check red-red distance against configured minimum and maximum.
  5. Treat the two red centers as the axis.
  6. For each green center, require it to fall inside the DIC pair mask.
  7. Require projection onto the red-red segment with anchor padding.
  8. Compute perpendicular distance to the red-red line.
  9. Count the green dot as collinear/on-axis if perpendicular distance is within threshold; otherwise count off-axis.
  10. Cap both counts at 2.

- Exact formulas:
  Red-red distance uses Euclidean pixel distance or calibrated micron distance. Perpendicular line distance is the cross-product distance from point to line, divided by red-red line length. On-axis condition is `perpendicular_distance <= collinearity_threshold` and projection within the padded segment.

- Output fields:
  `colinear_dot_count`; `off_axis_dot_count`; diagnostic properties for biorientation decisions.

- Display/export behavior:
  Counts are table/export fields when the plugin is active. Values are reset to zero on invalid prerequisites or exceptions.

- Biological interpretation:
  Counts how many green dots are geometrically aligned with a red-red axis versus away from that axis. The output is an alignment measurement, not a validated biological state assignment by itself.

- Assumptions:
  Exactly two red dots define a meaningful axis. Green dot centers are the relevant objects to classify. The selected collinearity threshold matches the microscopy scale and biological question.

- Failure/NA cases:
  Missing required channels should block plugin selection. Not exactly two red dots, red-red distance outside bounds, green dots outside the DIC pair mask, or projection outside the segment result in no or reduced counts. Exceptions reset counts.

- Validation status or tests:
  Biorientation logic is covered by targeted software tests.

- Plain-English explanation for biologists:
  CytoCV draws an imaginary line between two red dots and counts green dots that fall close to that line versus away from it.

- Manuscript-ready methods paragraph:
  Biorientation analysis used two canonical red contour centers to define an axis within a DIC-segmented cell pair. After verifying that the red-red distance fell within user-specified bounds, each canonical green contour center was tested for containment in the cell-pair mask, projection onto the red-red segment with anchor padding, and perpendicular distance to the red-red axis. Green dots with perpendicular distance less than or equal to the configured collinearity threshold were counted as on-axis; remaining projected dots were counted as off-axis.

- File/path/line citations:
  `cytocv/core/cell_analysis/biorientation.py::Biorientation` lines 70-247; `cytocv/core/services/biorientation_config.py` line 5; `cytocv/core/tests/test_biorientation.py` lines 105-324.

## Legacy blue nucleus intensity

- File(s):
  `cytocv/core/cell_analysis/blue_nucleus_intensity.py`; `cytocv/core/stats_plugins.py`; `cytocv/core/services/canonical_contours.py`.

- Main class/function(s):
  `BlueNucleusIntensity`; `BlueNucleusIntensity.calculate_statistics()`.

- User-facing name:
  BlueNucleusIntensity / legacy blue nucleus intensity.

- Biological purpose:
  Legacy measurement of blue-channel signal in a blue nuclear contour and whole cell.

- Required channels:
  DIC and Blue.

- Optional channels:
  Red and Green are optional for this legacy module.

- Input images used:
  Raw blue image if available; otherwise grayscale blue image with rolling-ball background subtraction fallback.

- Input masks/contours used:
  One canonical blue slot; DIC-derived cell mask.

- User parameters and defaults:
  This is a legacy plugin and is not in the default selected plugin list.

- Step-by-step algorithm:
  1. Select raw blue or preprocessed blue measurement image.
  2. Retrieve one canonical blue slot.
  3. Load the DIC cell mask.
  4. Sum blue intensity under the nuclear contour mask.
  5. Sum blue intensity under the full cell mask.
  6. Store nucleus and cell intensity fields or defaults.

- Exact formulas:
  `nucleus_intensity = sum(blue pixels where nucleus_mask > 0)`. `cell_intensity = sum(blue pixels where cell_mask > 0)`.

- Output fields:
  `nucleus_intensity`; `cell_intensity`; `cell_pair_intensity_sum`; related legacy point-count properties.

- Display/export behavior:
  Available only when the legacy plugin is selected and applicable. It uses shared table/export infrastructure.

- Biological interpretation:
  Reports blue-channel intensity under a detected nuclear contour and cell mask. It is a legacy measurement and should be described separately from current nuclear-cell-pair intensity.

- Assumptions:
  The blue contour represents the nucleus and the blue channel is the desired measured signal.

- Failure/NA cases:
  Missing blue image, missing blue contour, or missing cell mask returns default zero/empty fields.

- Validation status or tests:
  Legacy plugin registration is present; broad statistics tests cover plugin validation behavior. Current biological validation is not documented.

- Plain-English explanation for biologists:
  This older module measures blue signal inside a blue nucleus-like outline and inside the whole cell outline.

- Manuscript-ready methods paragraph:
  The legacy blue nucleus module used a blue-channel contour as a nuclear mask and summed blue-channel fluorescence within that mask and within the DIC-derived cell mask. Raw blue images were preferred when present, with preprocessed blue images used as fallbacks.

- File/path/line citations:
  `cytocv/core/cell_analysis/blue_nucleus_intensity.py::BlueNucleusIntensity` lines 19-97; `cytocv/core/stats_plugins.py::PLUGIN_DEFINITIONS` lines 175-184; `cytocv/core/tests/test_stats_validation.py` lines 64-493.

## Legacy red/blue intensity

- File(s):
  `cytocv/core/cell_analysis/red_blue_intensity.py`; `cytocv/core/stats_plugins.py`; `cytocv/core/services/canonical_contours.py`.

- Main class/function(s):
  `RedBlueIntensity`; `RedBlueIntensity.calculate_statistics()`.

- User-facing name:
  RedBlueIntensity / legacy red-blue intensity.

- Biological purpose:
  Legacy measurement of blue-channel signal under red contour masks.

- Required channels:
  DIC, Red, and Blue.

- Optional channels:
  Green is optional.

- Input images used:
  Raw blue image if available; otherwise preprocessed blue fallback.

- Input masks/contours used:
  Canonical red slots clipped to the DIC mask.

- User parameters and defaults:
  This is a legacy plugin and is not in the default selected plugin list.

- Step-by-step algorithm:
  1. Select blue measurement image.
  2. Retrieve up to three canonical red slots.
  3. Sum blue image intensity under each red mask.
  4. Store blue-in-red intensity fields.

- Exact formulas:
  For each red slot, `blue_in_red_total_intensity = sum(blue pixels where red_mask > 0)`. Other triplet fields default to zero in this legacy implementation.

- Output fields:
  `blue_in_red_total_intensity`; `blue_in_red_max_intensity`; `blue_in_red_average_intensity`.

- Display/export behavior:
  Available only when the legacy plugin is selected and applicable.

- Biological interpretation:
  Reports blue signal under red contours. This is a software measurement of channel overlap, not a validated interaction call.

- Assumptions:
  Red contours identify the regions where blue signal should be sampled.

- Failure/NA cases:
  Missing blue image or missing red contours leads to default zero values.

- Validation status or tests:
  Plugin registration and validation paths are covered in statistics tests; detailed biology validation is not documented.

- Plain-English explanation for biologists:
  This older module measures how much blue signal lies inside red dot outlines.

- Manuscript-ready methods paragraph:
  The legacy red-blue intensity module used canonical red fluorescence contours as masks and summed blue-channel fluorescence within those masks, preferring raw blue data when available.

- File/path/line citations:
  `cytocv/core/cell_analysis/red_blue_intensity.py::RedBlueIntensity` lines 8-44; `cytocv/core/stats_plugins.py::PLUGIN_DEFINITIONS` lines 185-194; `cytocv/core/tests/test_stats_validation.py` lines 64-493.

## NucleusIntensity if still active

- File(s):
  `cytocv/core/cell_analysis/nucleus_intensity.py`; `cytocv/core/stats_plugins.py`; `cytocv/core/services/canonical_contours.py`.

- Main class/function(s):
  `NucleusIntensity`; `NucleusIntensity.calculate_statistics()`.

- User-facing name:
  NucleusIntensity / legacy nucleus intensity.

- Biological purpose:
  Legacy module measuring green-channel signal in a blue nuclear contour and whole cell/cytoplasm.

- Required channels:
  DIC, Blue, and Green.

- Optional channels:
  Red is optional.

- Input images used:
  Raw green image if available; otherwise green background-subtracted/preprocessed fallback.

- Input masks/contours used:
  One canonical blue nuclear slot; DIC-derived cell mask.

- User parameters and defaults:
  Registered as a legacy plugin and not in the default selected plugin list.

- Step-by-step algorithm:
  1. Select green measurement image.
  2. Retrieve one blue canonical slot as the nuclear contour.
  3. Load the DIC cell mask.
  4. Sum green intensity under the blue nuclear mask.
  5. Sum green intensity under the whole cell mask.
  6. Store cytoplasmic intensity as whole-cell minus nuclear intensity.

- Exact formulas:
  `nucleus_intensity = sum(green pixels where blue_nuclear_mask > 0)`. `cell_intensity = sum(green pixels where cell_mask > 0)`. `cytoplasmic_intensity_sum = cell_intensity - nucleus_intensity`.

- Output fields:
  `nucleus_intensity`; `cell_intensity`; `cell_pair_intensity_sum`; `cytoplasmic_intensity_sum`; legacy point-count fields.

- Display/export behavior:
  Available when selected and applicable through shared table/export infrastructure.

- Biological interpretation:
  Measures green signal in a blue-defined nucleus-like region and outside it. This is legacy behavior and should not be conflated with the current configurable nuclear-cell-pair module.

- Assumptions:
  The blue contour is a nucleus proxy and green is the signal to quantify.

- Failure/NA cases:
  Missing green image, missing blue slot, or missing cell mask returns default zero/empty values.

- Validation status or tests:
  Registered plugin and validation behavior are covered by statistics tests. Specific biological validation is not documented.

- Plain-English explanation for biologists:
  This older module uses a blue outline to define the nucleus and measures green signal inside the nucleus and cell.

- Manuscript-ready methods paragraph:
  The legacy nucleus intensity module used a canonical blue-channel contour as a nuclear mask and summed green-channel fluorescence within that mask and within the DIC-derived cell mask. Cytoplasmic signal was computed by subtracting the nuclear sum from the whole-cell sum.

- File/path/line citations:
  `cytocv/core/cell_analysis/nucleus_intensity.py::NucleusIntensity` lines 15-85; `cytocv/core/stats_plugins.py::PLUGIN_DEFINITIONS` lines 165-174; `cytocv/core/tests/test_stats_validation.py` lines 64-493.

## Dot splitting / green split modes

- File(s):
  `cytocv/core/contour_processing/contour_operations.py`; `cytocv/core/services/upload_preparation.py`; `cytocv/accounts/preferences.py`.

- Main class/function(s):
  `DOT_SPLIT_PARAMS`; `validate_split_contours()`; `_split_merged_green_contours()`; `_postprocess_and_filter_aggressive_green_contours()`; `find_contours()`.

- User-facing name:
  Green splitting and split mode.

- Biological purpose:
  Attempts to separate merged fluorescence puncta into multiple dot contours so downstream dot counts, distances, and intensity measurements better reflect individual objects.

- Required channels:
  DIC and the fluorescence channel being split. Green split modes are specifically tied to green contour processing; red splitting also appears in red dot contour processing.

- Optional channels:
  Other fluorescence channels are optional unless required by selected downstream plugins.

- Input images used:
  Green preprocessed grayscale image for green splitting; red preprocessed image for red dot splitting.

- Input masks/contours used:
  Candidate fluorescence contours and their local masks.

- User parameters and defaults:
  Green split is enabled by default in preferences, with default split mode `balanced`. The current parameter table defines `balanced` and `aggressive` with the same numeric values. Disabled mode leaves contours unsplit.

- Step-by-step algorithm:
  1. Detect initial fluorescence contours.
  2. If splitting is disabled, pass contours through.
  3. If splitting is enabled, evaluate contour shape, intensity peaks, neck/chord geometry, watershed-style candidates, and asymmetric split candidates.
  4. Validate child contours against area, circularity, solidity, aspect ratio, peak-ratio, combined-area, area-fraction, center-distance, peak-label, and neck-alignment checks.
  5. Accept split children only if validation passes; otherwise retain or reject according to the contour-processing branch.
  6. For green contours, optionally run filtering after splitting, preserving accepted split pairs atomically.

- Exact formulas:
  Shape metrics include contour area, perimeter-derived circularity, convex-hull solidity, and bounding-box aspect ratio. Child validation compares these metrics and peak/intensity ratios against `DOT_SPLIT_PARAMS`.

- Output fields:
  No direct database field is solely "dot splitting." It changes downstream contour counts, contour centers, distances, intensity masks, and `properties` metadata that depend on canonical contour slots.

- Display/export behavior:
  Effects appear indirectly through contour overlays, contour counts, contour center fields, intensity fields, puncta distances, and plugin outputs.

- Biological interpretation:
  Splitting is an image-processing heuristic for resolving merged puncta. It should be reviewed visually, especially for dense or low-contrast signals.

- Assumptions:
  Merged contours contain separable local peaks and geometry consistent with multiple dots. Current `balanced` and `aggressive` settings should not be described as biologically distinct unless their parameters diverge.

- Failure/NA cases:
  Ambiguous or invalid split candidates are rejected. Disabled mode does not split. Poor contrast, weak peak separation, or irregular shapes can leave merged contours intact.

- Validation status or tests:
  Dot splitting and configuration behavior are covered by software tests.

- Plain-English explanation for biologists:
  When a green dot outline looks like two dots stuck together, CytoCV can try to split it, but only keeps the split when shape and brightness checks pass.

- Manuscript-ready methods paragraph:
  Optional dot splitting was applied during fluorescence contour processing to resolve candidate merged puncta. Candidate splits were generated from contour geometry and local intensity structure, then accepted only when child contours satisfied configured shape, area, intensity, and separation criteria. Split contours were subsequently processed as independent canonical contour slots for downstream measurements.

- File/path/line citations:
  `cytocv/core/contour_processing/contour_operations.py::DOT_SPLIT_PARAMS` lines 45-130; `cytocv/core/contour_processing/contour_operations.py::validate_split_contours()` lines 999-1098; `cytocv/core/contour_processing/contour_operations.py::_split_merged_green_contours()` lines 2375-2396; `cytocv/core/contour_processing/contour_operations.py::find_contours()` lines 2741-2791; `cytocv/core/tests/test_dot_split.py` lines 425-1260; `cytocv/core/tests/test_dot_split_config.py` lines 13-91.

## Green contour filtering

- File(s):
  `cytocv/core/contour_processing/contour_operations.py`; `cytocv/accounts/preferences.py`.

- Main class/function(s):
  `_filter_green_contours_with_image()`; `_postprocess_and_filter_aggressive_green_contours()`; `find_contours()`.

- User-facing name:
  Filter green contours.

- Biological purpose:
  Removes weak or likely-background green contour candidates before downstream puncta and intensity measurements.

- Required channels:
  DIC and Green for downstream cell-based green contour analysis.

- Optional channels:
  Red and Blue are optional unless selected plugins require them.

- Input images used:
  Green preprocessed grayscale image.

- Input masks/contours used:
  Candidate green contours and local ring masks around them.

- User parameters and defaults:
  Green contour filtering is false by default in preferences.

- Step-by-step algorithm:
  1. Evaluate each green contour.
  2. Reject contours below a minimum area threshold.
  3. Accept contours passing legacy closed/open shape-ratio evidence.
  4. For remaining contours, fill the contour mask and build a dilated ring region around it.
  5. Compare internal signal to local ring signal using max and percentile-based peak ratios.
  6. Accept contours with strong internal peak contrast; reject weak candidates.
  7. If split pairs were accepted before filtering, preserve those pairs together through the filter branch.

- Exact formulas:
  The filter computes inside maximum, inside 90th percentile, ring 90th percentile, and ratios comparing inside signal to local ring signal. Specific thresholds are defined in the contour-processing function.

- Output fields:
  No direct field. Filtering affects downstream green contour count, green contour centers, green intensities, puncta distance, CEN/Biorientation inputs, and table/export values.

- Display/export behavior:
  Effects appear through fewer or different green contours and downstream measurements. The control state is part of the analysis configuration snapshot.

- Biological interpretation:
  Filtering can reduce false positive green dots but may also remove dim true signal. It is a preprocessing/analysis choice that should be reported.

- Assumptions:
  True green puncta have stronger signal inside the contour than in the surrounding local ring or pass accepted shape evidence.

- Failure/NA cases:
  Weak true dots may be filtered out; high local background can prevent acceptance; disabled filtering leaves initial green contours unfiltered.

- Validation status or tests:
  Green filtering behavior is covered in dot split/filter tests.

- Plain-English explanation for biologists:
  This option keeps green dot outlines only when they look strong enough compared with nearby background or pass shape checks.

- Manuscript-ready methods paragraph:
  Optional green contour filtering rejected small candidate contours and used local signal contrast to distinguish candidate puncta from background. For each remaining green contour, CytoCV compared signal inside the filled contour to signal in a dilated surrounding ring and retained contours with sufficient internal peak contrast or accepted legacy shape evidence.

- File/path/line citations:
  `cytocv/core/contour_processing/contour_operations.py::_postprocess_and_filter_aggressive_green_contours()` lines 2345-2372; `cytocv/core/contour_processing/contour_operations.py::_filter_green_contours_with_image()` lines 2866-2983; `cytocv/accounts/preferences.py::DEFAULTS` lines 65-114; `cytocv/core/tests/test_dot_split.py` lines 425-1260.

## Cell Inclusion Mode and single-cell vs pair logic

- File(s):
  `cytocv/core/cell_types.py`; `cytocv/core/services/cell_candidate_retention.py`; `cytocv/core/services/segmentation_pipeline.py`; `cytocv/core/services/cell_type_statistics.py`; `cytocv/core/models.py`.

- Main class/function(s):
  `normalize_cell_inclusion_mode()`; `filter_stats_for_cell_type()`; `build_retained_candidate_label_image()`; `mark_single_cell_pair_specific_stats_na()`.

- User-facing name:
  Cell Inclusion Mode.

- Biological purpose:
  Controls whether CytoCV retains single cells, paired cells, or both after DIC segmentation and candidate classification.

- Required channels:
  DIC.

- Optional channels:
  Fluorescence channels depend on selected statistics plugins.

- Input images used:
  DIC segmentation label image and downstream fluorescence images for retained cells.

- Input masks/contours used:
  Mask R-CNN candidate labels; neighbor relationships among segmented candidates; retained label image; refined pair masks.

- User parameters and defaults:
  Default mode is pairs only. Other modes include singles only and singles plus pairs.

- Step-by-step algorithm:
  1. Normalize the requested inclusion mode.
  2. Analyze labeled DIC candidates and nearby neighbors.
  3. Candidates with no neighbors are classified as single cells.
  4. Mutual closest-neighbor candidates are classified as cell pairs.
  5. Ambiguous candidates are excluded.
  6. Retain or remove candidates according to the selected inclusion mode.
  7. Relabel retained candidates and run downstream statistics according to cell type.
  8. For single cells, mark pair-specific statistics as unavailable/NA.

- Exact formulas:
  Pair classification is based on local neighbor counts and mutual closest-neighbor relationships within the candidate-retention radius. Pair-specific fields are cleared or hidden for single-cell rows.

- Output fields:
  `CellStatistics.cell_type`; `SegmentedImage.cell_inclusion_mode`; row-level statistic availability metadata; retained masks and cell-pair artifacts.

- Display/export behavior:
  Display filters can show all, single, or paired rows. Export honors table/filter settings and field applicability. Pair-specific fields are not applicable for single-cell rows.

- Biological interpretation:
  The mode controls which DIC-segmented objects enter analysis. It does not prove cell-cycle stage or mother/daughter identity by itself.

- Assumptions:
  Neighbor geometry in the DIC segmentation is sufficient to distinguish singles from pairs. Ambiguous candidates are better excluded than forced into a category.

- Failure/NA cases:
  Ambiguous candidates are excluded. Pair-specific plugins may be skipped or marked NA for single cells. Incorrect DIC segmentation can misclassify cell type.

- Validation status or tests:
  Cell inclusion behavior is covered by dedicated tests.

- Plain-English explanation for biologists:
  CytoCV can keep only single cells, only touching cell pairs, or both, based on how DIC segmentation candidates sit next to each other.

- Manuscript-ready methods paragraph:
  Cell inclusion mode was applied after DIC segmentation to determine which candidate masks were retained for downstream analysis. Candidates without neighbors were classified as single cells, while mutual closest-neighbor candidates were classified as pairs; ambiguous candidates were excluded. The selected inclusion mode determined whether single cells, paired cells, or both were retained, and pair-specific measurements were marked unavailable for single-cell rows.

- File/path/line citations:
  `cytocv/core/cell_types.py` lines 8-144; `cytocv/core/services/cell_candidate_retention.py::build_retained_candidate_label_image()` lines 42-139; `cytocv/core/services/segmentation_pipeline.py` lines 607-620, 806-813, and 1318-1351; `cytocv/core/services/cell_type_statistics.py` lines 8-29; `cytocv/core/models.py::SegmentedImage` lines 88-108; `cytocv/core/tests/test_cell_inclusion_mode.py` lines 81-479.

## Mother/daughter parentage logic

- File(s):
  `cytocv/core/services/neck_split.py`; `cytocv/core/services/cell_parentage.py`; `cytocv/core/services/canonical_contours.py`.

- Main class/function(s):
  `detect_neck_split()`; `compute_side_areas()`; `derive_cell_parentage()`; `_derive_from_neck_split()`.

- User-facing name:
  Mother/daughter side assignment.

- Biological purpose:
  Assigns DIC-derived cell-pair sides as mother or daughter for CEN-dot and related pair-aware measurements.

- Required channels:
  DIC.

- Optional channels:
  Fluorescence channels are used by downstream modules after parentage is assigned.

- Input images used:
  DIC-derived cell mask.

- Input masks/contours used:
  Pair mask, neck chord, side masks, optional canonical contour payload.

- User parameters and defaults:
  Parentage logic is part of pair processing. User-exposed controls primarily affect downstream modules rather than the side-assignment algorithm itself.

- Step-by-step algorithm:
  1. Attempt to detect a neck split from DIC pair-mask geometry.
  2. Use convexity/neck geometry to choose a chord that separates the touching cells.
  3. Compute side masks by cutting the pair mask along that chord.
  4. If the split is valid, assign the larger side as mother and the smaller side as daughter.
  5. If the neck split is unavailable, derive parentage with a fallback principal-axis/area threshold method.
  6. Attach mother/daughter masks and parentage payload to canonical contour processing for downstream modules.

- Exact formulas:
  Side assignment is area-based after a valid split: larger connected side = mother, smaller connected side = daughter. The fallback uses principal-axis geometry and an area threshold.

- Output fields:
  Parentage payload in `properties`; mother/daughter masks in canonical contour payload; statuses describing valid split, fallback, or unavailable parentage.

- Display/export behavior:
  Parentage itself is primarily diagnostic/supporting metadata. It affects CEN-dot classification and any module requiring mother/daughter sides.

- Biological interpretation:
  Mother/daughter identity is inferred from DIC cell geometry. It should be reviewed and confirmed in biological analyses, especially for unusual morphologies.

- Assumptions:
  In budding yeast-like pairs, the larger side is the mother and the smaller side is the daughter. The neck split accurately separates the two cells.

- Failure/NA cases:
  No valid neck split, ambiguous side areas, or poor DIC segmentation can produce unavailable or fallback parentage, which can cause CEN-dot classification to become N/A.

- Validation status or tests:
  Neck split, parentage, and canonical-contour parentage integration are covered by software tests.

- Plain-English explanation for biologists:
  CytoCV tries to cut a touching cell pair at the neck and calls the larger side mother and the smaller side daughter.

- Manuscript-ready methods paragraph:
  Mother/daughter assignment was inferred from DIC pair geometry. CytoCV attempted to identify a neck chord separating the paired mask into two side masks and assigned the larger side as mother and the smaller side as daughter. If a valid neck split was unavailable, a principal-axis/area-based fallback could provide a best-effort parentage assignment. These assignments were used as computational metadata for downstream pair-aware analyses.

- File/path/line citations:
  `cytocv/core/services/neck_split.py::detect_neck_split()` lines 112-174; `cytocv/core/services/neck_split.py::compute_side_areas()` lines 177-219; `cytocv/core/services/neck_split.py` lines 222-360; `cytocv/core/services/cell_parentage.py::_derive_from_neck_split()` lines 135-170; `cytocv/core/services/cell_parentage.py::derive_cell_parentage()` lines 310-336; `cytocv/core/services/canonical_contours.py::build_canonical_contour_payload()` lines 245-318; `cytocv/core/tests/test_cell_parentage.py` lines 19-68; `cytocv/core/tests/test_neck_split.py` lines 46-200.

## Channel validation and missing-channel behavior

- File(s):
  `cytocv/core/metadata_processing/error_handling/source_image_validation.py`; `cytocv/core/stats_plugins.py`; `cytocv/core/services/signal_quantification.py`; `cytocv/core/services/puncta_line_mode.py`; `cytocv/core/channel_roles.py`; `cytocv/core/services/channel_presence.py`.

- Main class/function(s):
  `validate_source_image_file()`; `get_effective_required_channels()`; `get_required_channels_for_selection()`; `resolve_signal_quantification_selection()`; `required_channels_for_line_mode()`.

- User-facing name:
  Channel validation and channel mapping.

- Biological purpose:
  Ensures that selected analysis modules have the microscopy channels needed to compute their measurements.

- Required channels:
  DIC is universally required. Fluorescence requirements depend on selected plugins and puncta mode.

- Optional channels:
  Blue, Red, and Green are optional unless a selected plugin requires them. TIFF metadata can identify three-channel datasets with one fluorescence channel absent.

- Input images used:
  Source `.dv`, `.tif`, or `.tiff` stacks; metadata-derived channel labels; user channel mapping.

- Input masks/contours used:
  None at validation time; later DIC masks and fluorescence contours depend on validated channels.

- User parameters and defaults:
  Defaults select `PunctaDistance`, `CENDot`, `Biorientation`, and `GreenRedIntensity`. Default puncta line mode is red puncta. Channel aliases normalize labels such as DAPI/Hoechst to Blue, mCherry/cherry to Red, and GFP to Green.

- Step-by-step algorithm:
  1. Detect supported file extension and image layer count.
  2. Extract channel metadata from DV or TIFF metadata when available.
  3. Build logical channel configuration for DIC, Blue, Red, and Green.
  4. Determine required channels from selected plugins and signal quantification mode.
  5. Always require DIC.
  6. For three-layer images, require metadata/channel mapping sufficient to identify the missing fluorescence role.
  7. Reject missing required channels and provide messages/suggestions.
  8. Persist channel configuration and presence sidecars for downstream analysis.

- Exact formulas:
  Channel normalization uses role alias and substring matching rather than numeric formulas. Required channel set is the union of plugin requirements plus DIC, adjusted for single-channel puncta modes.

- Output fields:
  Validation result messages; channel configuration sidecars; `channel_config` snapshots; unavailable field metadata for modes that intentionally reduce channel requirements.

- Display/export behavior:
  Channel labels drive display names, preview mapping, plugin availability, and output interpretation. Missing-channel fields are blocked, unavailable, or rendered as `N/A` according to plugin and table logic.

- Biological interpretation:
  Correct channel mapping is essential because CytoCV measures logical roles rather than hard-coded fluorophore names. Users should confirm that metadata mapping matches the acquisition setup.

- Assumptions:
  Channel metadata is accurate or user mapping corrects it. DIC is needed for segmentation. Fluorescence channel absence can be inferred only when metadata/mapping is sufficient.

- Failure/NA cases:
  Unsupported extension, unsupported stack shape, missing DIC, missing required fluorescence channel, or insufficient three-layer metadata blocks analysis or disables selected measurements. Some modules have runtime fallback behavior but validation is intended to prevent invalid combinations.

- Validation status or tests:
  Channel validation, TIFF parsing, image source handling, and stats-plugin validation are covered by tests.

- Plain-English explanation for biologists:
  CytoCV does not assume fixed physical channel order; it maps images to DIC, Blue, Red, and Green roles and checks that the chosen analysis has the roles it needs.

- Manuscript-ready methods paragraph:
  Input channels were normalized to logical DIC, Blue, Red, and Green roles using metadata and alias matching. DIC was required for all analyses because it drives segmentation. Fluorescence channel requirements were determined from the selected statistics plugins and puncta mode, allowing single-channel red-only or green-only puncta analysis while blocking plugins that require absent channels.

- File/path/line citations:
  `cytocv/core/channel_roles.py` lines 5-89; `cytocv/core/metadata_processing/error_handling/source_image_validation.py` lines 22-420; `cytocv/core/stats_plugins.py` lines 31-39, 104-194, and 240-253; `cytocv/core/services/signal_quantification.py` lines 52-76 and 242-386; `cytocv/core/services/puncta_line_mode.py` lines 38-95; `cytocv/core/services/channel_presence.py` lines 1-390; `cytocv/core/tests/test_stats_validation.py` lines 64-493; `cytocv/core/tests/test_tiff_channel_parser.py` lines 20-154; `cytocv/core/tests/test_image_sources.py` lines 23-57.

## Pixel/micron scale conversion

- File(s):
  `cytocv/core/scale.py`; `cytocv/core/metadata_processing/dv_scale_parser.py`; `cytocv/core/metadata_processing/tiff_scale_parser.py`; `cytocv/core/services/segmentation_pipeline.py`.

- Main class/function(s):
  `build_scale_info()`; `normalize_scale_info()`; `resolve_scale_context()`; `convert_pixel_delta_to_microns()`; `convert_length_to_pixels()`; `convert_distance_for_display()`.

- User-facing name:
  Pixel/micron scale settings.

- Biological purpose:
  Allows distances and length thresholds to be reported or configured in physical units when reliable pixel-size metadata or manual scale is available.

- Required channels:
  Not channel-dependent.

- Optional channels:
  Not channel-dependent.

- Input images used:
  DV/TIFF metadata may provide physical pixel sizes. Manual settings can override metadata.

- Input masks/contours used:
  Coordinate pairs, distances, line widths, and thresholds from downstream analyses.

- User parameters and defaults:
  Default microns per pixel is 0.1. Spatial unit defaults to pixels. Metadata scale use is enabled by default. Users can override or revert scale settings.

- Step-by-step algorithm:
  1. Attempt to extract physical pixel size from DV/TIFF metadata.
  2. Normalize scale information and status.
  3. Apply manual override if provided.
  4. Resolve active spatial unit, x/y microns-per-pixel, and anisotropy status.
  5. Convert display distances from pixels to microns when requested.
  6. Convert user length inputs such as line width or CEN thresholds to pixels when algorithms require pixel values.

- Exact formulas:
  Pixel delta to microns: `sqrt((dx * x_microns_per_pixel)^2 + (dy * y_microns_per_pixel)^2)`. Area conversion multiplies pixel area by `x_mpp * y_mpp`. Length-to-pixel conversion uses the active scale context and geometric proxy where appropriate.

- Output fields:
  Scale metadata in image/job configuration; display/export headers with spatial unit suffixes; converted distance/area values in table/export output; pixel thresholds passed to algorithms.

- Display/export behavior:
  Distance columns can be labeled and rendered in pixels or microns. Raw coordinate fields are stored as pixel coordinates, while display/export conversion is applied by table logic.

- Biological interpretation:
  Micron outputs are only as reliable as the extracted or manually supplied scale. Users should report whether metadata or manual scale was used.

- Assumptions:
  Pixel scale metadata is correct, or manual override is correct. For anisotropic pixels, x/y scales can differ and Euclidean physical distance uses both axes.

- Failure/NA cases:
  Missing/invalid metadata falls back to defaults/manual settings. Invalid user scale values are rejected or normalized. If users choose pixel units, no physical conversion is applied.

- Validation status or tests:
  Scale extraction, request payloads, and display conversion behavior are covered by tests.

- Plain-English explanation for biologists:
  CytoCV stores measurements in pixels but can convert distances and thresholds to microns when it knows the pixel size.

- Manuscript-ready methods paragraph:
  Spatial scale was obtained from microscopy metadata when available or from a user-supplied manual microns-per-pixel value. Distances stored in pixel coordinates could be displayed or exported in pixels or microns. Physical distance conversion used x and y pixel scales, computing Euclidean distance as the square root of the squared scaled x and y deltas.

- File/path/line citations:
  `cytocv/core/scale.py` lines 8-503; `cytocv/core/metadata_processing/dv_scale_parser.py` lines 50-106; `cytocv/core/metadata_processing/tiff_scale_parser.py` lines 12-176; `cytocv/core/services/segmentation_pipeline.py` lines 842-942; `cytocv/core/tests/test_upload_length_scale.py` lines 37-349; `cytocv/core/tests/test_scale_request_payloads.py` lines 17-135.

## CSV/XLSX export and table filtering

- File(s):
  `cytocv/core/tables.py`; `cytocv/core/services/stat_export_selection.py`; `cytocv/core/services/combined_stat_export.py`; `cytocv/core/views/display.py`; `cytocv/core/services/puncta_source_contour_count_filter.py`; `cytocv/core/services/stat_applicability.py`.

- Main class/function(s):
  `CellStatisticsTable`; `CellStatisticsTable.as_values()`; `CellStatisticsTable.as_export_rows()`; `normalize_export_selection()`; `build_combined_stats_response()`; display export views.

- User-facing name:
  Display/Dashboard table filters and CSV/XLSX export.

- Biological purpose:
  Provides reviewable per-cell measurement tables and downloadable datasets for downstream analysis.

- Required channels:
  Depends on selected plugins; export itself is not channel-specific.

- Optional channels:
  Depends on selected plugins.

- Input images used:
  None directly at export time; export reads stored `CellStatistics` rows and properties.

- Input masks/contours used:
  None directly at export time; contour-derived fields are already stored.

- User parameters and defaults:
  Users can filter by cell type, selected statistics/output groups, puncta source contour count, save status, and table/download settings. CSV and XLSX formats are supported.

- Step-by-step algorithm:
  1. Query stored/transient `CellStatistics` rows for a displayed analysis.
  2. Apply cell-type and contour-count filters.
  3. Resolve export selection, field applicability, spatial unit, and display labels.
  4. Convert row values using field-specific render/export logic.
  5. Include unavailable or inapplicable values as `N/A`, blanks, null-like values, or excluded fields according to table/export configuration.
  6. Return CSV or XLSX response.

- Exact formulas:
  Numeric rendering applies decimal formatting and spatial conversion through table helpers. Puncta source contour-count filtering derives the source channel from puncta mode and compares the relevant source contour count to the selected filter.

- Output fields:
  Export columns include identity fields, contour sizes, intensity triplets, distances, ratios, CEN category, biorientation counts, nuclear/cell-pair fields, coordinates, and plugin-dependent properties as configured.

- Display/export behavior:
  Display tables render values with labels and applicability rules. CSV/XLSX export can include selected groups and combined analysis rows. Spatial headers include unit suffixes where applicable.

- Biological interpretation:
  Exports are row-level software measurements. Downstream statistical and biological conclusions should be performed and documented separately.

- Assumptions:
  Stored rows correspond to the intended analysis configuration. Users choose filters that match their biological question. Inapplicable fields are not treated as measured zeros.

- Failure/NA cases:
  Missing/inapplicable fields render as `N/A` or configured unavailable values. Deleted rows can be filtered out. Export requests with no matching rows produce empty or limited outputs according to response logic.

- Validation status or tests:
  Table rendering, export selection, frontend export contracts, account preferences, and combined export behavior are covered by tests.

- Plain-English explanation for biologists:
  CytoCV saves one row per analyzed cell or cell pair and lets users filter the rows and download the measurements as CSV or Excel.

- Manuscript-ready methods paragraph:
  Per-cell measurement rows were stored in the database and reviewed through Display/Dashboard tables. Users could filter rows by cell type, save status, selected statistic groups, and puncta source contour count before export. CSV and XLSX downloads used the same field-applicability logic as the display tables, including spatial unit conversion and `N/A` handling for unavailable measurements.

- File/path/line citations:
  `cytocv/core/tables.py` lines 54-925; `cytocv/core/services/stat_export_selection.py` lines 19-253; `cytocv/core/services/combined_stat_export.py` lines 37-210; `cytocv/core/views/display.py` lines 163-913; `cytocv/core/services/puncta_source_contour_count_filter.py` lines 12-218; `cytocv/core/services/stat_applicability.py` lines 16-278; `cytocv/core/tests/test_tables.py` lines 82-710; `cytocv/core/tests/test_stat_export_selection.py` lines 49-268; `cytocv/core/tests/test_frontend_export_contracts.py` lines 141-561.
