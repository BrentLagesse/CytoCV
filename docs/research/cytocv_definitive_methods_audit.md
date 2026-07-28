# CytoCV Definitive Methods and Implementation Audit

Audit target: commit `a3ed23ed3b861729d2caa960524e55e17c4d9977` on branch `nicolasmgioanni`, audited 2026-07-20. The comparison commit is the same commit, so the committed implementation delta is empty. “Biological” labels below describe software classifications, not independently established biological truth.

## A. Version, identity, and defaults (answers 1–9)

**Evidence outcome:** CONFIRMED IMPLEMENTATION

**Plain-language answer:**
1. The product name is CytoCV. The only version string in the root product documentation is `1.0`; HEAD is untagged and identifies itself more precisely as `v1.8.1-44-ga3ed23ed`. These identifiers are inconsistent, so the exact commit is the definitive identity.
2. HEAD is `a3ed23ed3b861729d2caa960524e55e17c4d9977`; the latest tag by creation date is `v1.8.1` at `921f2d6f8d2078cec486fcc3e3a9020ae4094ae3` (2026-06-11 19:52:22 -0700).
3. New-account defaults select `PunctaDistance`, `CENDot`, `Biorientation`, and `GreenRedIntensity`.
4. `NuclearCellPairIntensity` is available but is not selected by default.
5. Signal Quantification defaults to `puncta_distance`.
6. Puncta source/line mode defaults to `red_puncta`: Red contours define the endpoints and Green is measured over the line.
7. Line width defaults to `1 px`; the active length unit is `px`. Micron lengths are divided by the geometric scale proxy `sqrt(x_um_per_px*y_um_per_px)`, rounded with Python `round()` (ties-to-even), converted to `int`, and clamped to at least 1 pixel.
8. Defaults are: Cell pairs only; Red split on/balanced; Green split on/balanced; Green contour filter off; contour-intensity statistics on; spatial output `px`; metadata scale on; manual/fallback `0.1 µm/px`; CEN Red–Red threshold `37 px`; CEN Green proximity `13 px`; biorientation Red–Red minimum `0 px`, maximum `37 px`; collinearity `3 px`. Nuclear mode is `green_nucleus`, alternate contour mode is balanced, legacy-scaled measurement is off, and alternate nucleus detection is configured on but becomes operational only when the nuclear mode/plugin is active.
9. Balanced and aggressive dot-split parameter dictionaries are numerically identical. Aggressive is behaviorally different: after the shared baseline routes, it continues through extra geometry-first, deterministic peak/bridge, chord, watershed, single-defect/asymmetric, and recall-oriented fallback branches; balanced returns after the shared routes.

**Exact technical behavior:**
Account preference normalization is the public default source. `analysis_context` independently carries compatible runtime defaults, except an invalid biorientation collinearity value falls back to 66 there even though an empty/valid default snapshot resolves to 3. This is an inconsistency, not the normal default.

**Inputs and prerequisites:**
Defaults apply to a new or normalized user configuration. Existing stored preferences are normalized and may retain non-default values.

**Algorithm steps:**
1. Load `DEFAULT_USER_PREFERENCES`.
2. Normalize plugin aliases and mutually exclusive Signal Quantification selections.
3. Copy the normalized session state into synchronous execution or a worker snapshot.
4. Convert physical-length controls to integer pixel controls per run.

**Exact formulas:**
`pixel_length = max(minimum_px, int(round(length_um / sqrt(x_scale*y_scale))))`; for native pixels, `pixel_length = max(minimum_px, int(round(length_px)))`.

**Defaults and units:**
All numerical defaults and units are listed in `cytocv_current_defaults.csv`.

**Outputs and stored fields:**
Defaults are stored in `CustomUser.config`; effective run values are copied into `CellStatistics.properties`, `UploadedImage.scale_info`, sidecars, and (worker mode) `AnalysisJob.config_snapshot` as described in section N.

**Display/export behavior:**
Spatial display/export starts in pixels. Changing the display unit does not alter stored pixel measurements.

**Failure, null, zero, and N/A behavior:**
Invalid preference values normalize to allowed defaults/minima. The noted runtime invalid-collinearity fallback is 66.

**Computational interpretation:**
These are software defaults, not biologically optimized parameters.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE supports biological optimality of any default.

**Tests executed:**
The 911-test `core accounts` suite passed; preference/default coverage also passed in the 155-test `test_accounts_preferences` module.

**Exact implementation evidence:**
- `README.md` lines 1–8 and 31–39
- `cytocv/accounts/preferences.py::DEFAULT_USER_PREFERENCES` lines 55–114
- `cytocv/core/services/signal_quantification.py::DEFAULT_SIGNAL_SELECTED_PLUGINS` lines 52–66
- `cytocv/core/services/puncta_line_mode.py` lines 15–58
- `cytocv/core/contour_processing/contour_operations.py::DOT_SPLIT_PARAMS` lines 45–130 and `split_necked_dot_contour_if_needed()` lines 1952–2301
- `cytocv/core/tests/test_accounts_preferences.py`

**Manuscript-safe wording:**
“CytoCV at commit `a3ed23ed3b861729d2caa960524e55e17c4d9977` defaults to the PunctaDistance, CENDot, Biorientation, and GreenRedIntensity software modules; configurable thresholds are reported as implementation defaults rather than biologically optimized values.”

## B. Input formats and channel model (answers 10–19)

**Evidence outcome:** CONFIRMED IMPLEMENTATION; separate-file channel assembly is NOT IMPLEMENTED.

**Plain-language answer:**
10. Extensions are case-insensitive `.dv`, `.tif`, and `.tiff`. The loader accepts a two-dimensional plane (expanded to one layer) or a normalizable three-dimensional stack. TIFF axes metadata may contain singleton non-spatial axes, which are squeezed; more than one non-spatial stack axis, missing Y/X, or unsupported dimensionality is rejected. Normal analysis validation requires a 3- or 4-layer stack because DIC is required.
11. DV arrays pass through shape normalization. TIFF uses the first series, honors axes metadata when available, moves the single non-Y/X/non-S stack axis to the front, or without axes retains a first axis of at most 16, moves a last axis of at most 16, otherwise moves the smallest axis to the front. Values/dtype are not rescaled by the source loader.
12. TIFFs with a non-singleton sample/RGB `S` axis and no independent stack axis are rejected as RGB/sample images.
13. DV mapping first uses structured header channel records, then XML records. Names/aliases are normalized; wavelengths within 12 nm of 625/525/435 map to Red/Green/Blue, while a negative or `1 <= wavelength < 200` maps to DIC. TIFF metadata uses ImageJ `Labels`; wavelength tokens near 625/525/435 and DIC/brightfield/transmission/R3D-reference patterns are recognized. TIFF metadata does not apply the broader GFP/mCherry aliases. Four-layer ambiguous metadata may use manual/stored mapping or fallback order `DIC, Blue, Green, Red`. User reordering persists `channel_config.json`.
14. DIC is universally required by the statistics/segmentation plan.
15. Beyond DIC: Puncta paired modes require Red+Green; Red-only requires Red; Green-only requires Green; `CENDot`, `Biorientation`, `GreenRedIntensity`, and `NuclearCellPairIntensity` require Red+Green; `NucleusIntensity` requires Blue+Green; `BlueNucleusIntensity` requires Blue; `RedBlueIntensity` requires Red+Blue.
16–17. A three-layer stack is accepted only when metadata preference is enabled and reliable metadata identifies exactly three distinct in-range roles consisting of DIC plus exactly two fluorescence roles, and that set satisfies every required channel. It is rejected for incomplete/duplicate/ambiguous labels, missing DIC, a missing required role, or disabled metadata preference.
18. CytoCV does not guess which role is absent from an ambiguous three-layer stack. A four-layer stack is treated as all four roles and may use fallback order because no logical role is missing.
19. Combining separate single-channel TIFF files into one run is NOT IMPLEMENTED; every upload is an independent run/UUID.

**Exact technical behavior:**
Presence is persisted in `channel_presence.json`, and mapping in `channel_config.json`. Three-layer resolution bypasses general fallback parsing and returns an empty config when metadata is ambiguous.

**Inputs and prerequisites:**
The file must open through `mrc.DVFile` or `tifffile.TiffFile`; the upload workflow then applies the required-channel and 3/4-layer rules.

**Algorithm steps:**
1. Validate extension/openability.
2. Normalize the array to channel-first.
3. Derive plugin requirements plus DIC and optional validation requirements.
4. Resolve reliable metadata for three layers, or metadata/fallback/manual mapping for four.
5. Reject missing requirements and write mapping/presence sidecars for accepted files.

**Exact formulas:**
Wavelength role matching uses absolute distance `< 12 nm` from 625, 525, or 435 nm.

**Defaults and units:**
Metadata channel order is preferred; fallback order is DIC, Blue, Green, Red. Exact-four-layer and all-role enforcement default off.

**Outputs and stored fields:**
`UploadedImage`, `scale_info`, `channel_config.json`, `channel_presence.json`, and up to four preview rows/files.

**Display/export behavior:**
The stored channel mapping controls previews, crops, overlays, and channel labels; statistics CSV/XLSX does not embed the complete mapping.

**Failure, null, zero, and N/A behavior:**
Parser/open/shape failures produce a generic unsupported-image validation failure. Ambiguous three-layer metadata produces a specific metadata-insufficient failure rather than a guessed mapping.

**Computational interpretation:**
Logical channel roles are metadata/configuration assignments, not proof of fluorophore identity.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE independently establishes that inferred roles match sample biology.

**Tests executed:**
`test_image_sources`, `test_tiff_channel_parser`, `test_stats_validation`, `test_upload_preparation`, and the full suite passed.

**Exact implementation evidence:**
- `cytocv/core/image_sources.py` lines 21–180
- `cytocv/core/metadata_processing/dv_channel_parser.py` lines 25–214
- `cytocv/core/metadata_processing/tiff_channel_parser.py` lines 27–132
- `cytocv/core/metadata_processing/error_handling/source_image_validation.py::validate_source_image_file()` lines 92–233
- `cytocv/core/services/channel_presence.py` lines 243–390
- `cytocv/core/stats_plugins.py` lines 31–194 and 240–253

**Manuscript-safe wording:**
“CytoCV accepts DV and stack-TIFF inputs, maps stack planes to logical DIC/Blue/Red/Green roles, requires DIC, and rejects ambiguous three-layer mappings rather than imputing the missing fluorescence role.”

## C. Red and green puncta contour determination (answers 20–31)

**Evidence outcome:** CONFIRMED IMPLEMENTATION

**Plain-language answer:**
20. Red puncta are detected from `gray_red_3`, a display-scaled Red crop converted to grayscale and Gaussian-blurred with a 3×3 kernel and sigma 1. Raw Red pixels are not the detection source.
21. Green contours are detected from `green`, the corresponding display-scaled grayscale crop after 3×3 Gaussian blur. `green_no_bg` is used only as split-child tightening evidence/fallback, not the initial threshold image.
22. Each color calls Otsu thresholding (the supplied `0.65` is ignored by Otsu as a threshold value), then applies a fixed additive offset: Otsu+11 for Red dots and Otsu+13 for Green. Broader legacy Red contour families use Canny(50,150), with an Otsu/adaptive-flag threshold fallback when the edge image is empty.
23. Initial Red puncta receive no morphology before contour extraction. Green binary signal receives one `MORPH_CLOSE` using a 3×3 cross kernel. Split/filter operations add the operations specified in section J.
24. Red and Green use `cv2.RETR_LIST` and `cv2.CHAIN_APPROX_SIMPLE`.
25. Initial Red dots are retained only when `contourArea < 100 px²`; there is no additional initial Red minimum. Initial Green extraction has no area/shape gate unless filtering is enabled. Split-child and Green-filter thresholds are all listed in section J. Canonical empty intersections are discarded. Blue legacy canonical selection requires area at least `max(10, 0.002*crop_area)`, less than `0.95*crop_area`, and retains one slot.
26. Red split processing operates on Red `dot_contours` with `gray_red_3` evidence and `red_no_bg` tightening fallback; failure keeps the original contour.
27. Green split processing operates on `contours_green` with `green` evidence and `green_no_bg` tightening fallback. Filtering is a separate optional stage; accepted pairs are atomic as described in section J.
28–29. For each raw contour, CytoCV fills a binary mask, intersects it with the DIC-derived cell mask, discards an empty intersection, extracts external connected contours using `RETR_EXTERNAL/CHAIN_APPROX_SIMPLE`, calculates area as the sum of component contour areas, and calculates centroid with binary-mask moments (`m10/m00`, `m01/m00`) or the mean of nonzero pixel coordinates. Slots sort deterministically by `(-area, center_x, center_y)` and are truncated to three. Canonical construction itself does not deduplicate; CEN/Biorientation later remove centers within 8 px of an already-kept slot.
30. Contours beyond the first three canonical slots are discarded. PunctaDistance consumes only slots 1–2; CEN/Biorientation deduplicate and require exactly two among at most three; GreenRedIntensity consumes at most three; nuclear measurement consumes slot 1.
31. No biological identity is assigned beyond image-derived labels such as Red contour, Green contour, nucleus-contour candidate, or software classification.

**Exact technical behavior:**
Detection geometry is produced from 8-bit display-scaled preprocessing; modern intensity plugins then prefer raw source arrays for pixel measurement. Detection and measurement sources therefore differ by design.

**Inputs and prerequisites:**
Mapped fluorescence crops and a DIC cell outline/mask; missing color arrays produce empty contour families.

**Algorithm steps:**
1. Preprocess display crops.
2. Otsu+offset threshold.
3. Apply Green closing.
4. Extract `RETR_LIST` contours.
5. Optionally split/filter.
6. Clip filled masks to the DIC cell and rank canonical slots.

**Exact formulas:**
`centroid=(m10/m00,m01/m00)` when `m00 != 0`; fallback is `(mean(column_indices), mean(row_indices))`. Slot key is `(-area,x,y)`.

**Defaults and units:**
Both Red and Green split default on/balanced; Green filter defaults off. Areas are pixel-area units.

**Outputs and stored fields:**
Canonical masks/components/centers feed contour-size fields and center keys, count keys, debug overlays, and all modern plugins.

**Display/export behavior:**
Sizes and full-image centers are visible/exportable in pixel or converted micron units. Extra discarded contours are not exposed as additional table slots.

**Failure, null, zero, and N/A behavior:**
Absent/empty contours produce zero-valued size/intensity slots when calculated; fields are N/A when their plugin/mode marks them unavailable.

**Computational interpretation:**
These are threshold-derived, DIC-clipped image components, not established biological puncta.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE provides curated contour truth or biological accuracy estimates.

**Tests executed:**
Canonical-contour, modern-contour-statistics, dot-split, cell-mask, and full suites passed.

**Exact implementation evidence:**
- `cytocv/core/image_processing/image_operations.py::preprocess_image_to_gray()` lines 108–187
- `cytocv/core/contour_processing/contour_operations.py::find_contours()` lines 2528–2829
- `cytocv/core/services/canonical_contours.py` lines 118–186 and 245–410
- `cytocv/core/tests/test_canonical_contours.py`
- `cytocv/core/tests/test_modern_contour_statistics.py`

**Manuscript-safe wording:**
“Red and Green contour candidates are Otsu-offset threshold components detected from preprocessed channel crops, optionally split/filtered, clipped to each DIC-derived cell mask, and ranked into deterministic software slots.”

## D. Intensity measurements (answers 32–37)

**Evidence outcome:** CONFIRMED IMPLEMENTATION

**Plain-language answer:**
32. `GreenRedIntensity` and same-channel puncta metrics prefer `raw_red`/`raw_green`, then `red_no_bg`/`green_no_bg`, then `gray_red`/`green`. Paired line intensity uses the same fallback order for the measurement color. The current nuclear path uses raw opposite-channel pixels first, then no-background, then preprocessed grayscale. `NucleusIntensity` prefers raw Green then no-background/Green; `BlueNucleusIntensity` prefers raw Blue and otherwise a rolling-ball-subtracted Blue image; `RedBlueIntensity` prefers raw Blue then preprocessed Blue. Legacy-scaled nuclear mode uses only `red_no_bg` or `green_no_bg`.
33. For pixels `V={image[p] | mask[p]>0}`, total is `ΣV`, maximum is `max(V)`, and average is `mean(V)`.
34. An empty mask returns `(0.0,0.0,0.0)`.
35. Modern plugin methods perform no exposure, flat-field, cross-image, or additional background normalization. Background subtraction may occur only through the documented fallback/preprocessing source. No exposure metadata is used.
36. Direct Red/Green fields are the 36 nullable fields formed by `red_in_red`, `green_in_red`, `red_in_green`, and `green_in_green` × `total|max|average` × slots 1–3. Legacy Blue fields are `red_blue_intensity_1..3`, `cell_pair_intensity_sum_blue`, `nucleus_intensity_sum_blue`, and `cytoplasmic_intensity_blue`. Nuclear fields are `cell_pair_intensity_sum`, `nucleus_intensity_sum`, `cytoplasmic_intensity`, and `nuclear_cytoplasmic_ratio`.
37. Measurement/contour ratios use slot totals: in Red-contour mode, `green_in_red_total/red_in_red_total`; in Green-contour mode, `red_in_green_total/green_in_green_total`. Invalid/missing terms coerce to zero and a zero denominator returns `0.0`. Nuclear/cytoplasmic ratio is `nucleus_intensity_sum/cytoplasmic_intensity` only when the denominator is nonzero and the result is finite; otherwise it is `None`.

**Exact technical behavior:**
Raw arrays retain source dtype/dynamic range. Contour geometry is still generated from display-scaled images.

**Inputs and prerequisites:**
A measurement array and nonempty canonical/DIC mask for a nonzero result.

**Algorithm steps:**
1. Select the first available measurement source.
2. Fill/obtain the applicable mask.
3. Select values at `mask>0`.
4. calculate sum/max/mean and derived ratios.

**Exact formulas:**
The formulas are stated above; cytoplasm is additionally defined in section G as whole-cell sum minus nuclear sum.

**Defaults and units:**
Intensity values are source pixel-value units; ratios are dimensionless. Contour statistics default on in puncta mode.

**Outputs and stored fields:**
All direct fields are enumerated in section M and model lines 297–397.

**Display/export behavior:**
Finite numerics render/export to three decimals (integer biorientation counts remain integers); unavailable fields become `N/A`.

**Failure, null, zero, and N/A behavior:**
Empty calculated masks return numeric zero; invalid nuclear ratio is null; unselected or explicitly unavailable fields are N/A at display/export.

**Computational interpretation:**
Values are mask-restricted software measurements in source/fallback pixel units, not calibrated molecule counts.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE validates these values against an independent quantitative assay.

**Tests executed:**
Intensity-helper, modern-contour, puncta, nuclear, table/export, and full suites passed.

**Exact implementation evidence:**
- `cytocv/core/image_processing/image_helper.py::calculate_masked_intensity_stats()` lines 27–40
- `cytocv/core/cell_analysis/green_red_intensity.py` lines 37–178
- `cytocv/core/cell_analysis/puncta_distance.py` lines 132–245
- `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py` lines 50–294
- `cytocv/core/services/measurement_contour_ratio.py` lines 99–190
- `cytocv/core/tests/test_intensity_helpers.py`

**Manuscript-safe wording:**
“CytoCV reports mask-restricted source-pixel sums, maxima, and means, with explicit fallback image sources and zero/null semantics.”

## E. Puncta distance and line intensity (answers 38–49)

**Evidence outcome:** CONFIRMED IMPLEMENTATION

**Plain-language answer:**
38–40. `red_puncta`: Red source, Green measurement. `green_puncta`: Green source, Red measurement. `red_puncta_only` and `green_puncta_only`: named source color and no measurement channel.
41. The first two canonical source slots are selected; those are the two largest DIC-clipped masks with x/y tie breaking.
42–43. `puncta_distance = math.dist(center1,center2) = sqrt((x2-x1)^2+(y2-y1)^2)`. It is centroid-to-centroid, not edge/mask distance.
44. Each centroid coordinate is converted with `int(round(value))`; points are `(x,y)`. `cv2.line` draws into a uint8 mask with the configured integer thickness and default `LINE_8`. Selected indices come from `np.nonzero(mask)` in `(row=y,column=x)` order.
45. Line intensity is the sum of all measurement-image pixels whose rasterized line mask is positive. It is not a mean, maximum, interpolated profile, or length-normalized integral.
46. Fewer than two source slots leaves `puncta_distance=0.0`, `puncta_line_intensity=0.0`, and returns no line pixels.
47. `properties` stores mode, source/measurement channel, contour centers/counts, and `puncta_distance_delta_x_px/delta_y_px`; it does not store line endpoints, the raster mask, pixel profile, or line coordinates.
48. Red-only provides distance, Red slot sizes/centers, and (when contour intensity is enabled) Red-in-Red total/max/average. Line intensity, all Green slots, all cross-color fields/ratios, Green-in-Green, and Green-to-Red distances are unavailable.
49. Green-only is the mirror: distance plus Green sizes/centers and Green-in-Green statistics; line, Red, cross-color/ratio, and Green-to-Red distance fields are unavailable.

**Exact technical behavior:**
Single-channel execution forces the corresponding same-channel contour-stat visibility even when the independent GreenRedIntensity plugin is not selected.

**Inputs and prerequisites:**
At least two canonical source slots; paired modes additionally need the opposite measurement array.

**Algorithm steps:**
1. Resolve mode metadata.
2. Load canonical source slots and measurement fallback.
3. Select slots 1–2 and compute distance/deltas.
4. Rasterize line and sum measurement pixels for paired modes.
5. Record unavailable fields for single-channel modes.

**Exact formulas:**
`d_px=sqrt(dx²+dy²)`; `I_line=Σ image[y,x]` for all `(y,x)` with `line_mask[y,x]>0`.

**Defaults and units:**
Default mode `red_puncta`, width 1 px. Stored distance/deltas are pixels; line intensity is pixel-value sum.

**Outputs and stored fields:**
`puncta_distance`, `puncta_line_intensity`, mode/channel/count/center/delta properties, plus optional same-channel slot statistics.

**Display/export behavior:**
Headers change with mode. Single-channel line header is “Opposite-Channel Line Intensity (N/A)” and values are N/A through applicability metadata.

**Failure, null, zero, and N/A behavior:**
Missing geometry produces calculated zeros; mode-inapplicable fields are marked unavailable and displayed/exported as N/A.

**Computational interpretation:**
Distance is between software contour centroids; line intensity is a thickness-dependent raster sum.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE establishes that selected contours are the intended biological pair.

**Tests executed:**
Modern-contour, single-channel, applicability, table, export, and full suites passed.

**Exact implementation evidence:**
- `cytocv/core/services/puncta_line_mode.py` lines 15–122
- `cytocv/core/cell_analysis/puncta_distance.py::calculate_statistics()` lines 246–354
- `cytocv/core/services/canonical_contours.py` lines 149–186 and 331–366
- `cytocv/core/tests/test_modern_contour_statistics.py`
- `cytocv/core/tests/test_tables.py` lines 439–471

**Manuscript-safe wording:**
“Puncta Distance is the Euclidean separation of the first two canonical source-contour centroids; paired modes additionally sum opposite-channel pixel values over an integer-width OpenCV line.”

## F. Cross-color distance and coordinates (answers 50–56)

**Evidence outcome:** CONFIRMED IMPLEMENTATION

**Plain-language answer:**
50. Cross-color distance is Green-to-nearest-Red for each of up to three Green slots; it is not symmetric or all-pairs output.
51. For each Green centroid, Python `min(red_slots,key=math.dist)` selects the nearest Red. Exact ties select the first Red in canonical order.
52. Direct fields are `distance_of_green_from_red_1..3`; properties store matching `_delta_x_px` and `_delta_y_px`, where each delta is `red_center - green_center`.
53. A local canonical centroid uses filled binary-mask moments; if `m00==0`, it uses the mean of nonzero pixel coordinates; an empty mask is discarded (the helper’s final empty fallback is `(0,0)`).
54. `x_full=crop_left+x_local`; `y_full=main_height-1-(crop_top+y_local)`.
55. Stored coordinates use the full main image with bottom-left origin: x increases rightward and y upward.
56. Micron display/export computes `x_um=x_px*x_um_per_px` and `y_um=y_px*y_um_per_px`, formatted to three decimals.

**Exact technical behavior:**
Coordinates are property-backed and share canonical slot identities with sizes/intensities.

**Inputs and prerequisites:**
Valid crop origin, main-image height, and canonical masks. Invalid/out-of-bounds transforms omit coordinate keys.

**Algorithm steps:**
1. Compute local centroids.
2. Add left/top crop offsets and invert row-origin y.
3. Store pixel coordinates.
4. For each Green, choose nearest Red and store distance/deltas.

**Exact formulas:**
As listed above; anisotropic micron distance is `sqrt((dx*x_scale)^2+(dy*y_scale)^2)`.

**Defaults and units:**
Pixel storage; display/export default px and optionally µm.

**Outputs and stored fields:**
Blue, Red 1–3, and Green 1–3 center x/y keys; three Green-to-Red distances and six delta keys.

**Display/export behavior:**
Coordinates render as `x.xxx, y.yyy`; missing/non-applicable coordinates are `N/A`.

**Failure, null, zero, and N/A behavior:**
No Red slot leaves the corresponding distance at zero and stores no delta; no Green slot leaves its slot zero/missing. Applicability can convert stored zero to N/A.

**Computational interpretation:**
Coordinates and nearest-neighbor relationships are software geometry in the segmented image coordinate frame.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE validates coordinate-derived associations biologically.

**Tests executed:**
Contour-coordinate, modern-statistics, anisotropic-scale, table/export, and full suites passed.

**Exact implementation evidence:**
- `cytocv/core/services/canonical_contours.py::_mask_center()` lines 136–146
- `cytocv/core/services/contour_coordinates.py` lines 1–230
- `cytocv/core/cell_analysis/green_red_intensity.py::calculate_statistics()` lines 66–178
- `cytocv/core/tables.py` lines 583–639
- `cytocv/core/tests/test_contour_coordinates.py`

**Manuscript-safe wording:**
“For each Green canonical slot, CytoCV stores centroid distance to the nearest Red slot and reports full-image bottom-left-origin coordinates in pixels or scale-converted micrometers.”

## G. Nuclear and cytoplasmic workflows (answers 57–66)

**Evidence outcome:** CONFIRMED IMPLEMENTATION

**Plain-language answer:**
57. Current/legacy plugins are `NuclearCellPairIntensity`, `NucleusIntensity`, `BlueNucleusIntensity`, and `RedBlueIntensity`; the optional legacy-scaled path is a mode within `NuclearCellPairIntensity`.
58. `green_nucleus` uses Green contour slot 1 and measures Red; `red_nucleus` uses Red slot 1 and measures Green.
59. Standard nucleus selection is the first/largest canonical slot for the contour channel.
60. When alternate detection is effectively enabled for the active nuclear channel, slot 1 from the alternate contour/mask family replaces the standard slot and the source property records `alternate_red_nucleus_slot_1` or `alternate_green_nucleus_slot_1`.
61. The nucleus contour is filled to a uint8 binary mask, a 3-channel mask is converted to grayscale if necessary, nonzero values become 255, it is intersected with the filled DIC cell mask, and an external/simple contour check rejects an empty clipped result.
62. `cell=sum(measurement[cell_mask>0])`; `nucleus=sum(measurement[nucleus_mask>0])`; `cytoplasm=cell-nucleus`; `N/C=nucleus/cytoplasm` when finite and denominator nonzero.
63. Missing contour or measurement channel: all sums zero, ratio null, status `missing_channel`. Missing/empty cell: zeros/null, `no_cell_points`. Missing/empty/clipped-away nucleus: zeros/null, `no_nucleus_contour`. A valid empty pixel set sums to zero. There is no broad exception handler inside this plugin; unexpected exceptions propagate to row/batch error handling.
64. Legacy-scaled mode uses background-subtracted 8-bit `red_no_bg`/`green_no_bg` only and may use exact label-pair support before falling back to the current DIC pair mask. The sum/subtraction/ratio formulas do not change; pixel source and cell support do.
65. No nuclear plugin is selected by default.
66. README lines 31–37, `docs/user/workflow-guide.md` line 46, `docs/user/getting-started.md` line 71, `docs/research/methods-and-system-description.md` table line 43, and `docs/research/reproducibility-and-validation.md` lines 13/24 incorrectly describe `NuclearCellPairIntensity` as default.

**Exact technical behavior:**
Alternate detection preference alone is insufficient; Signal Quantification must resolve to nuclear mode, which also suppresses puncta-mode execution through the exclusive selection contract.

**Inputs and prerequisites:**
DIC cell mask, both Red and Green arrays for the modern two-color plugin, and at least one usable contour in the selected nucleus color.

**Algorithm steps:**
1. Resolve mode and raw/legacy source.
2. Select standard or alternate slot 1.
3. Fill, normalize, and DIC-clip the nucleus mask.
4. Sum whole-cell/nucleus pixels, subtract cytoplasm, calculate ratio.
5. Store provenance/status.

**Exact formulas:**
The formulas are stated in answer 62.

**Defaults and units:**
Mode `green_nucleus`; alternate contour mode balanced; legacy-scaled off; no nuclear workflow selected by default.

**Outputs and stored fields:**
Four direct fields plus contour/measurement channel, mode, contour mode, contour source, measurement mode/pixel provenance, and status properties.

**Display/export behavior:**
Headers are mode-specific. `no_nucleus_contour`, unselected nuclear group, and single-cell rows render/export all nuclear outputs as N/A. The source string is exportable.

**Failure, null, zero, and N/A behavior:**
Plugin failures are stored as zeros plus null ratio/status for expected prerequisites; UI/export converts no-contour/inapplicable values to N/A.

**Computational interpretation:**
“Nucleus” means the configured color-derived canonical/alternate mask clipped to the DIC cell mask.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE compares these masks or intensity partitions with independent nuclear/cytoplasmic ground truth.

**Tests executed:**
Nuclear-cell-pair, red-speckle, modern-contour, applicability, export, and full suites passed.

**Exact implementation evidence:**
- `cytocv/core/cell_analysis/nuclear_cell_pair_intensity.py` lines 28–294
- `cytocv/core/cell_analysis/nuclear_cell_pair_legacy_scaled.py` lines 1–126
- `cytocv/core/stats_plugins.py` lines 144–194
- `cytocv/core/services/signal_quantification.py` lines 228–386
- `cytocv/core/tests/test_nuclear_cell_pair_intensity.py`

**Manuscript-safe wording:**
“The optional NuclearCellPairIntensity module uses the largest configured color-derived contour as a nucleus mask, clips it to the DIC cell mask, and reports whole-cell, nuclear, cytoplasmic, and nuclear/cytoplasmic software measurements.”

## H. CEN-dot classification (answers 67–79)

**Evidence outcome:** CONFIRMED IMPLEMENTATION for answers 67–78; NO REPOSITORY EVIDENCE for biological correctness (answer 79).

**Plain-language answer:**
67–68. `CENDot` requires DIC parentage/masks, Red and Green arrays/contours, and exactly two usable Red anchors after canonical top-three selection and deduplication.
69. Red and Green slots are separately deduplicated in canonical order: a candidate is dropped when its squared centroid distance to any kept slot is `<=64` (8 px).
70. Pixel Red distance is Euclidean centroid distance. Micron distance is `sqrt((dx*x_scale)^2+(dy*y_scale)^2)`.
71. The Red pair passes when distance is `>= threshold`; equality passes.
72–73. A detected neck chord is drawn black with `LINE_8`, thickness 2 through the filled DIC mask; 8-connected components are sorted by area and the larger (including deterministic tie order) is mother.
74. If neck splitting fails, PCA/principal-axis projection divides the DIC pixels at a smoothed central histogram valley or midpoint; an empty-side case falls back to a stable sorted half split. Larger area is mother. Empty/degenerate masks remain unavailable.
75. Each Red mask is assigned to the side with larger overlap; an overlap tie assigns mother. The two anchors must land on opposite sides.
76. Each eligible Green slot is assigned to its nearest of the mother/daughter Red anchors when distance is `<= proximity radius`; equality passes. Exact squared-distance ties within `1e-9` are ambiguous and count for neither anchor.
77. Enum/schema 3: `1 Mother and daughter`, `2 Mother only`, `3 Daughter only`, `4 N/A`. Missing/bad values display N/A. Schema missing or `<3` with stored 1–3 displays “Rerun analysis for CEN location.” Failure statuses include no source shape/default N/A, `too_few_reds`, `too_many_reds`, `reds_below_threshold`, `missing_cell_parentage`, `red_side_unassigned`, `reds_same_side`, `no_valid_green`, and caught `error`; successful statuses are `mother_and_daughter`, `mother_only`, `daughter_only`.
78. `cen_dot_location` stores schema/category/status; parentage status/mode/method/reason; threshold/radius values, units and pixel equivalents; neck flag; Red count/centers/distance/threshold; Red side assignments; Green count/centers; assignment rule; mother/daughter association booleans and center lists; ambiguous centers; and error text on exception.
79. NO REPOSITORY EVIDENCE: there is no curated CEN dataset, benchmark, comparison table, sensitivity/specificity result, or independent biological truth for CEN calls.

**Exact technical behavior:**
Only the first three canonical slots can enter deduplication; raw contours beyond that limit cannot produce `too_many_reds`.

**Inputs and prerequisites:**
A cell-pair row, parentage masks, exactly two separated Red anchors, and at least one valid Green for a non-N/A category.

**Algorithm steps:**
1. Canonicalize/deduplicate Red and require exactly two.
2. Apply inclusive Red distance minimum.
3. obtain mother/daughter masks.
4. Assign Red anchors to opposite sides.
5. Canonicalize/deduplicate/validate Green slots.
6. Associate each Green to nearest anchor inside the inclusive radius.
7. Map association booleans to enum.

**Exact formulas:**
Distance and comparisons are stated above. Current µm proximity is converted to a scalar pixel radius through the geometric scale proxy; the actual Red-distance threshold uses anisotropic distance.

**Defaults and units:**
Red threshold 37 px; Green proximity 13 px; category schema 3.

**Outputs and stored fields:**
`category_cen_dot`, `properties.cen_dot_schema_version`, `properties.cen_dot_location`, and shared `cell_parentage`.

**Display/export behavior:**
Table/export uses schema-aware labels; disabled/single-cell groups are N/A.

**Failure, null, zero, and N/A behavior:**
All invalid prerequisite/failure paths produce enum 4/N/A; unexpected exceptions are caught and recorded as `status=error`.

**Computational interpretation:**
The category is a thresholded software classification of image-derived contours and inferred DIC sides.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE. Safe wording: “software-derived CEN-dot location category.”

**Tests executed:**
CEN classification, parentage, neck split, canonical contours, tables, and full suites passed.

**Exact implementation evidence:**
- `cytocv/core/cell_analysis/cen_dot.py` lines 39–467
- `cytocv/core/models.py` lines 242–284 and 374–382
- `cytocv/core/services/neck_split.py` lines 87–219
- `cytocv/core/services/cell_parentage.py` lines 135–336
- `cytocv/core/tests/test_cen_dot_classification.py`

**Manuscript-safe wording:**
“CytoCV computes a CEN-dot location category by assigning two Red contour anchors to inferred mother/daughter DIC masks and associating Green contours to the nearest anchor within a configurable radius; the repository does not establish biological classification accuracy.”

## I. Biorientation (answers 80–91)

**Evidence outcome:** CONFIRMED IMPLEMENTATION for answers 80–90; NO REPOSITORY EVIDENCE for biological correctness (answer 91).

**Plain-language answer:**
80–81. `Biorientation` requires a DIC cell mask, Red and Green canonical slots, and exactly two Red anchors after top-three selection and 8-px deduplication.
82. Default Red–Red range is inclusive 0–37 px. A pair is invalid only when `distance < minimum` or `distance > maximum`. Pixel or anisotropic micron units are supported independently for min/max.
83. The axis is the infinite line through the two Red centroids, constrained to a padded anchor-to-anchor segment for candidate counting.
84. A Green slot is eligible only when its filled mask has nonzero overlap with the DIC cell mask.
85. With `a` and `b` as Red centers, `v=b-a`, `L=|v|`, and `p` a Green center, projection numerator is `(p-a)·v`. It must lie in `[-r1*L, L²+r2*L]`, inclusive, where `r=sqrt(red_area/pi)` for each anchor.
86. Perpendicular distance is `abs((py-y1)*dx-(px-x1)*dy)/L`.
87. A candidate is on-axis when perpendicular distance is `<= collinearity threshold`; equality is on-axis.
88. A candidate is off-axis when it passes DIC overlap and padded projection bounds but has perpendicular distance `> threshold`. A projection-outside candidate is ignored, not counted off-axis.
89. At most the first three canonical/deduplicated Green candidates are evaluated. On-axis and off-axis results are each capped with `min(count,2)`.
90. Missing images/masks, a Red count other than two, degenerate axis, out-of-range Red distance, or unexpected exception leaves both counts at zero. No biorientation diagnostic status is persisted.
91. NO REPOSITORY EVIDENCE: no curated biorientation dataset, benchmark, or independent biological comparison exists.

**Exact technical behavior:**
Biorientation shares Red/Green canonical slots and deduplication with CENDot but does not use mother/daughter masks.

**Inputs and prerequisites:**
DIC mask, exactly two valid Red anchors, and Green candidates.

**Algorithm steps:**
1. Canonicalize and deduplicate slots.
2. Validate Red count/range and nonzero axis.
3. DIC-overlap each Green mask.
4. Apply padded projection bound.
5. Apply perpendicular threshold and cap counts.

**Exact formulas:**
All formulas and inclusive rules are given above.

**Defaults and units:**
Minimum 0 px, maximum 37 px, collinearity 3 px.

**Outputs and stored fields:**
`colinear_dots` and `off_axis_dots`; no status/geometry payload.

**Display/export behavior:**
Selected zeros display/export as integer `0`; unselected/single-cell values are N/A.

**Failure, null, zero, and N/A behavior:**
Computationally invalid prerequisites return zeros; applicability metadata distinguishes those zeros from N/A only at the plugin/row level, not by a biorientation-specific status.

**Computational interpretation:**
Counts classify image-derived Green centroids relative to a padded Red-centroid axis.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE. Safe wording: “software-derived on-axis/off-axis contour counts.”

**Tests executed:**
All biorientation, canonical, scale, applicability, and full-suite tests passed.

**Exact implementation evidence:**
- `cytocv/core/cell_analysis/biorientation.py` lines 25–247
- `cytocv/core/services/biorientation_config.py` lines 1–5
- `cytocv/core/tests/test_biorientation.py`

**Manuscript-safe wording:**
“Biorientation reports software-derived counts of Green contour centroids on or off the padded segment joining two Red contour centroids; biological classification accuracy is not established in the repository.”

## J. Dot splitting and Green filtering (answers 92–99)

**Evidence outcome:** CONFIRMED IMPLEMENTATION for answers 92–98; NO REPOSITORY EVIDENCE for biological accuracy (answer 99).

**Plain-language answer:**
92. Modes are `balanced` and `aggressive`. Both use the identical parameter set: original area ≥8; peak distance ≥1; distance peak ratio ≥0.18; intensity/second peak ratios ≥0.20; intensity valley ≤0.96; distance valley ≤0.97; defect depth ≥0.25 px and relative depth ≥0.04; neck/lobe width ≤1; chord mask fraction ≥0.45; round-dot gates circularity ≥0.92, solidity ≥0.99, aspect ≤1.12; suspicious gates aspect ≥1.04 or circularity ≤0.88 or solidity ≤0.99; child circularity ≥0.10, solidity ≥0.45, pixel area ≥4, small/large area fraction ≥0.06, combined/original area ≥0.58, center distance ≥1, aspect ≤5.5, child peak ≥0.15 of original, center-axis/neck cosine ≤0.94; cut thickness 1. Asymmetric gates are enabled with peak distance ≥2, second peak ≥0.20, intensity valley ≤0.94, intensity drop ≥0.04, distance saddle ≤0.94, peak-line support ≥0.60, defect depth ≥0.35 px, saddle/defect distance ≤10 px, child fraction ≥0.08, child mean/original-max ≥0.08, low-signal boundary fraction ≥0.40, and saddle distance ≤8 px. Candidate/peak caps are 8; profiles sample 48 points.
93. Candidate routes include distance/intensity peak pairs, paired convexity-defect neck chords, direct chord separation, marker watershed over `0.65*normalized_distance + 0.35*normalized_intensity`, geometry-first watershed, peak bisector/principal-axis bridge labels, deterministic aggressive separation, single-defect/asymmetric peak-saddle watershed, and aggressive fallbacks.
94. A standard accepted split has exactly two children, every child passes area/contour length/circularity/solidity/aspect/peak gates, the pair passes combined area, area balance, center separation, marker separation, and neck alignment. Asymmetric routes add their gates. Final tightening thresholds each child at `max(0.55*child_peak, child_70th_percentile)`, keeps the connected component containing the maximum, dilates once with 3×3, clips to original, and requires at least `max(4,0.25*original_area)` mask and contour area; if tightening fails, the already accepted untightened pair is retained.
95. Any failed candidate leaves the original unsplit contour.
96. During combined Green split+filter, a split pair is retained only if both children pass; otherwise the original merged contour is restored atomically.
97. Green filter: area ≥8; shape accepts closed/open arc-length ratio `<=0.9` or `>=1.06`. Otherwise an 11×11 elliptical one-dilation outer ring is required; inside maximum and 90th percentile are divided by `max(ring_p90,1)`, and both ratios must be at least 3.0 and 2.5 respectively. There is no maximum-area or separate solidity/circularity/aspect threshold in this filter.
98. It removes area specks, shapes inside the neutral ratio band without a ring, and insufficient-contrast neutral shapes. It retains shape outliers without intensity evidence and neutral shapes with both strong-peak ratios.
99. NO REPOSITORY EVIDENCE: no ground-truth split/filter benchmark or manually labeled comparison exists.

**Exact technical behavior:**
Balanced exits after common baseline routes. Aggressive invokes additional recall routes even though numerical dictionaries match.

**Inputs and prerequisites:**
A contour, binary mask, and preprocessed evidence array; tightening may use the no-background array.

**Algorithm steps:**
1. Calculate shape/peak/defect metrics.
2. Reject round single-dot evidence.
3. Generate ordered split candidates.
4. Validate two-child geometry/intensity.
5. Tighten accepted children.
6. Optionally filter Green, preserving accepted pairs atomically.

**Exact formulas:**
Circularity `4*pi*A/P²`; solidity `A/hull_area`; aspect `max(w,h)/min(w,h)`; lobe width `2*max(distance_transform)`.

**Defaults and units:**
Red/Green splitting on, balanced; Green filtering off. Thresholds are pixel/intensity ratios as listed.

**Outputs and stored fields:**
Final contours only; split decisions are debug-logged, while effective split enabled/mode is stored per row. Green-filter enabled state is not stored per row.

**Display/export behavior:**
Only final canonical children affect size/count/intensity/distance exports; split-route diagnostics are not exported.

**Failure, null, zero, and N/A behavior:**
Invalid/failed split inputs retain the original; empty input returns an empty list.

**Computational interpretation:**
Splits/filters are deterministic image-shape and intensity heuristics.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE. Safe wording: “heuristic separation/filtering of merged contour candidates.”

**Tests executed:**
`test_dot_split`, `test_dot_split_config`, modern-contour, and full suites passed.

**Exact implementation evidence:**
- `cytocv/core/contour_processing/contour_operations.py` lines 45–142, 260–2301, and 2832–2983
- `cytocv/core/services/dot_split.py` lines 1–56
- `cytocv/core/tests/test_dot_split.py`
- `cytocv/core/tests/test_dot_split_config.py`

**Manuscript-safe wording:**
“Optional dot splitting applies validated two-child geometric/intensity heuristics, while optional Green filtering applies area, contour-shape, and local-ring contrast gates; no biological split/filter accuracy benchmark is included.”

## K. Cell inclusion and parentage (answers 100–109)

**Evidence outcome:** CONFIRMED IMPLEMENTATION for answers 100–108; NO REPOSITORY EVIDENCE for biological accuracy (answer 109).

**Plain-language answer:**
100. Values are `cell_pairs_only` (default), `single_cells_only`, and `single_cells_and_cell_pairs`.
101. For every pixel of a candidate label, CytoCV examines the clipped square radius-3 neighborhood (Chebyshev distance ≤3) and counts occurrences of other positive labels.
102. A computational single is a candidate with no neighboring positive label in those neighborhoods.
103. A computational pair is two candidates that select each other as closest/dominant neighbors; the second label is relabeled into the first.
104. A single neighbor is selected directly. With multiple neighbors, counts sort descending; the largest is closest only when the second-largest count is not greater than half the largest. A mutual mapping is required for a pair.
105. If the second count is `>0.5*top`, the candidate and its observed neighbors are marked unknown/excluded. Non-mutual closest relationships are also unknown.
106. The July 2026 code at HEAD clips edge neighborhoods instead of allowing negative-slice wrapping, selects the dominant neighbor in descending order, and merges a mutual pair into one retained label. Consequently, neither member remains as an independent single row. This fix is already in the comparison commit and is not a post-comparison change.
107. On a retained single row, pair-specific CEN, biorientation, nuclear, and parentage values are reset to enum/zero/null sentinels, those visibility groups are false, and table/export shows N/A.
108. Neck detection uses DIC convexity defects with depth ≥1 px, considers the six deepest, tests pair chords using 20 rounded interior samples, draws the first qualifying chord at thickness 2, and requires two 8-connected sides. Larger side is mother. If unavailable, principal-axis/histogram/midpoint and stable half-split fallbacks derive sides; empty/too-small/degenerate masks remain not identified.
109. NO REPOSITORY EVIDENCE: no curated single/pair or mother/daughter truth set is present.

**Exact technical behavior:**
After inclusion, a 3×3 ellipse closing and unambiguous-background refinement can add only pixels claimed by exactly one label; existing ownership is never removed.

**Inputs and prerequisites:**
Labeled Mask R-CNN output for inclusion; filled DIC pair mask for parentage.

**Algorithm steps:**
1. Build contact counts at radius 3.
2. identify singles, dominant closest candidates, and ambiguities.
3. merge mutual pairs and apply inclusion mode.
4. Refine retained masks.
5. detect neck or derive fallback parentage.

**Exact formulas:**
Ambiguity condition is `second_contact_count > 0.5*top_contact_count`; mother is the side with greater or deterministic-tie area.

**Defaults and units:**
Cell pairs only; neighbor radius 3 px; neck cut thickness 2 px.

**Outputs and stored fields:**
`SegmentedImage.cell_inclusion_mode`, `CellStatistics.cell_type`, property copies, pair geometry/neck sidecars, and `properties.cell_parentage`.

**Display/export behavior:**
Cell Type is always shown/exported. Row filters select stored rows only; pair-specific single-row fields display/export N/A.

**Failure, null, zero, and N/A behavior:**
Ambiguous/unknown candidates are excluded during analysis. Unidentified parentage stores a status/reason and displays a non-identified label or N/A when inapplicable.

**Computational interpretation:**
Single/pair and mother/daughter are DIC-mask/contact/area-derived software labels.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE. Safe wording: “computational cell-candidate type and inferred parentage.”

**Tests executed:**
Cell inclusion, parentage, neck split, pair-label refinement, table/applicability, and full suites passed.

**Exact implementation evidence:**
- `cytocv/core/services/cell_candidate_retention.py` lines 21–139
- `cytocv/core/services/segmentation_pipeline.py` lines 607–913
- `cytocv/core/services/neck_split.py` lines 87–219
- `cytocv/core/services/cell_parentage.py` lines 59–384
- `cytocv/core/services/cell_type_statistics.py` lines 8–29
- `cytocv/core/tests/test_cell_inclusion_mode.py`
- `cytocv/core/tests/test_cell_parentage.py`

**Manuscript-safe wording:**
“CytoCV retains computational single-cell and/or mutual-neighbor cell-pair candidates according to Cell Inclusion Mode and infers mother/daughter sides from DIC neck geometry or a deterministic principal-axis fallback.”

## L. Scale and units (answers 110–116)

**Evidence outcome:** CONFIRMED IMPLEMENTATION

**Plain-language answer:**
110. DV scale sources are header `dx`, `dy`, and `dz`. TIFF uses XResolution/YResolution with ResolutionUnit (inch→25400 µm, centimeter→10000 µm); absent standard unit, ImageJ unit strings µm/nm/mm supply factors 1/0.001/1000 with resolution tags.
111. A persisted per-file manual override has highest active priority. Otherwise, when metadata preference is on and valid metadata exists, metadata wins; when unavailable, manual fallback is used. With metadata preference off, manual global scale is used. Invalid sources normalize to the default.
112. Default/fallback is `0.1 µm/px`.
113. Metadata may retain separate x/y scales. Directional distances and areas use both axes; a scalar effective value is their arithmetic mean, while length-to-pixel thresholds use the geometric proxy `sqrt(x*y)`.
114. Distance: `sqrt((dx_px*x_scale)^2+(dy_px*y_scale)^2)`; area: `area_px*x_scale*y_scale`; coordinates: `(x_px*x_scale,y_px*y_scale)`; physical length threshold: `length_um/sqrt(x_scale*y_scale)`.
115. Converted thresholds use Python ties-to-even `round`, `int`, then the caller minimum. Puncta width minimum is 1 px; CEN/proximity thresholds use minimum 0. UI line-width entry minimum is 1 px or 0.01 µm.
116. Direct spatial database fields and property deltas/coordinates remain pixels. Scale context and original control unit/value/pixel equivalent are stored; µm values are produced only for display/export or threshold execution.

**Exact technical behavior:**
When directional deltas are missing on a legacy row, micron distance falls back to stored pixel distance times scalar effective scale.

**Inputs and prerequisites:**
Valid scale range is 0.0001–10000 µm/px; extraction must produce positive finite values.

**Algorithm steps:**
1. Extract metadata scale.
2. apply metadata/manual preference or per-file override.
3. persist scale context.
4. convert thresholds into execution pixels.
5. retain pixel results and convert at presentation.

**Exact formulas:**
All conversion formulas are stated above.

**Defaults and units:**
0.1 µm/px fallback; pixel display and pixel control units by default.

**Outputs and stored fields:**
`UploadedImage.scale_info`; per-row `scale_*` and `stats_*unit/value/px` properties.

**Display/export behavior:**
Headers use `(px)`, `(px²)`, `(µm)`, or `(µm²)`; coordinate pairs use the selected length unit and three decimals.

**Failure, null, zero, and N/A behavior:**
Invalid metadata/manual values fall back to a valid normalized context. Missing spatial fields become N/A through table formatting/applicability.

**Computational interpretation:**
Micron outputs are deterministic conversions using recorded metadata/manual scales.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE independently calibrates the sample-file scales.

**Tests executed:**
DV/TIFF scale, upload initialization, request payload, length conversion, table/export, and full suites passed.

**Exact implementation evidence:**
- `cytocv/core/metadata_processing/dv_scale_parser.py` lines 1–118
- `cytocv/core/metadata_processing/tiff_scale_parser.py` lines 1–176
- `cytocv/core/scale.py` lines 70–503
- `cytocv/core/tests/test_tiff_scale_parser.py`
- `cytocv/core/tests/test_scale_upload_initialization.py`

**Manuscript-safe wording:**
“Spatial results are stored in pixels and converted at execution/presentation using per-file metadata or manual µm/px context, including anisotropic x/y conversion where directional geometry is available.”

## M. Storage, applicability, tables, and export (answers 117–129)

**Evidence outcome:** CONFIRMED IMPLEMENTATION

**Plain-language answer:**
117. `CellStatistics` fields are: `segmented_image`, `cell_id`, `cell_type`, `puncta_distance`, `puncta_line_intensity`, `nucleus_intensity_sum`, `cell_pair_intensity_sum`, `cytoplasmic_intensity`, nullable `nuclear_cytoplasmic_ratio`, `blue_contour_size`, Red sizes 1–3, 36 nullable Red/Green total/max/average intensity fields, Green sizes 1–3, Green-to-Red distances 1–3, compatibility ratios `green_red_intensity_1..3`, legacy `red_blue_intensity_1..3`, Blue cell/nucleus/cytoplasm sums, `category_cen_dot`, `colinear_dots`, `off_axis_dots`, `dv_file_path`, `image_name`, `is_correct`, `nuclei_count`, `cen_dot_count`, `cyan_dot_count`, `ground_truth`, `nucleus_intensity`, `nucleus_total_points`, `cell_intensity`, `cell_total_points`, `ignored`, and `properties`. Important properties include selected analysis/visibility/unavailable fields; cell type/inclusion/parentage; signal/nuclear/puncta modes and sources/status; contour counts/centers/deltas; CEN diagnostics; scale/provenance; effective thresholds; split settings; and intensity source flags.
118. Per run: `UploadedImage.scale_info`, `SegmentedImage.cell_inclusion_mode`, mapping/presence/overlay config sidecars, and worker `config_snapshot`. Per row: selected plugins, stat visibility, effective signal/mode/contour settings, cell type/inclusion, scale/threshold values, split enabled/modes, contour counts/coordinates, parentage and plugin diagnostics. Green-filter enabled is not copied to row properties.
119. `unavailable_stat_fields` is a row-level list overriding otherwise visible fields. Visibility groups are `puncta_distance`, `red_green_intensity`, `nuclear_cell_pair_intensity`, `cen_dot`, `biorientation`, and `legacy_blue_intensity`. Multi-row tables union explicit visibility; legacy rows without metadata treat all groups as visible.
120. Numeric zero is a calculated value and renders `0.000` (or integer 0). Database null is absence; number exports convert it to N/A, while ordinary django-table HTML may use the empty-value glyph before a renderer is called. Blank applies to string/form/model empty values and usually renders empty/glyph or N/A in explicit formatters. A missing property/attribute resolves through field-specific fallback or N/A/Unknown. “Unavailable” means visibility false or field named in `unavailable_stat_fields`; N/A is the public string emitted for that semantic state. JSON serialization uses `null` for unavailable numeric/stat keys and explicit `N/A` labels/status text where defined.
121. Applicable finite floats render to three decimals; counts render integers; CEN renders schema-aware label; parentage renders its label; coordinates render `x.xxx, y.yyy`; unavailable/invalid explicit formatters return N/A.
122. Both CSV and XLSX use `CellTable.as_values`: finite numeric cells are Decimal quantized to 0.001, integers remain integers, labels/coordinates are strings, and unavailable/invalid/non-finite cells are literal `N/A`. CSV serialization renders Decimal text; XLSX retains numeric cells.
123. Decimal precision is 0.001. `NaN`, `Infinity`, invalid numbers, and conversion failures become N/A.
124. Cell filter values are all/single_cell/cell_pair. A specific filter is applied only if both known types exist and the requested type exists; otherwise it normalizes effectively to all.
125. Source-count filters are all/exactly_1/exactly_2. Count priority is stored source count, stored source-channel count, direct count, then positive canonical size slots. Rows outside puncta mode pass the filter. If no usable count data exists, the effective filter is all.
126. Filters select displayed/exported rows only; they do not recalculate or mutate stored results.
127. `Cell ID` and `Cell Type` are always included. Combined exports additionally always prepend `File Name`.
128. Requested metric IDs accept ratio aliases, discard unknown IDs, require at least one valid statistic, deduplicate through a set, and emit canonical `CellTable.Meta.fields` order. No `_columns` parameter means legacy full export.
129. Spatial headers are generated from field kind and requested unit; values use recorded scale/deltas, as described in section L.

**Exact technical behavior:**
The current `CellTable` does not include legacy `red_blue_intensity_*` or Blue nuclear/cell/cytoplasm sum fields, although they exist in the model/JSON payload. They therefore are not current CSV/XLSX columns.

**Inputs and prerequisites:**
Stored `CellStatistics` rows and optional column/row-filter/unit request parameters.

**Algorithm steps:**
1. Resolve effective row filters.
2. resolve visibility/applicability per row.
3. normalize selected columns into canonical order.
4. convert units and values through `CellTable`.
5. serialize with tablib/django-tables2 to CSV/XLSX.

**Exact formulas:**
Export quantization is `Decimal(str(value)).quantize(Decimal("0.001"))` after a finite check.

**Defaults and units:**
All rows, all source counts, all selectable metrics, pixels, CSV modal default.

**Outputs and stored fields:**
Single-file table or combined table. Combined `File Name` appears only on the first row of each file group.

**Display/export behavior:**
Table and export share formatting/applicability. JSON uses null for disabled values while HTML/CSV/XLSX uses N/A.

**Failure, null, zero, and N/A behavior:**
An empty/invalid selected-metric set raises “Select at least one statistic to export.” Combined exports with no rows fail with a defined message. Non-finite values never reach numeric output.

**Computational interpretation:**
Applicability separates a measured zero from a statistic that was not run or cannot apply.

**Biological-evidence status:**
Exports preserve software outputs; they add no biological validation.

**Tests executed:**
Tables, stat selection, frontend export, account export, filters, payload, and full suites passed.

**Exact implementation evidence:**
- `cytocv/core/models.py::CellStatistics` lines 287–397
- `cytocv/core/services/stat_applicability.py` lines 16–278
- `cytocv/core/tables.py` lines 44–925
- `cytocv/core/services/stat_export_selection.py` lines 19–253
- `cytocv/core/services/combined_stat_export.py` lines 37–210
- `cytocv/core/services/puncta_source_contour_count_filter.py` lines 12–218
- `cytocv/core/tests/test_tables.py`
- `cytocv/core/tests/test_frontend_export_contracts.py`

**Manuscript-safe wording:**
“CytoCV exports applicability-aware per-cell CSV/XLSX tables with fixed three-decimal numeric precision, explicit N/A values, canonical column ordering, and non-mutating row filters.”

## N. Workflow, architecture, and reproducibility (answers 130–137)

**Evidence outcome:** CONFIRMED IMPLEMENTATION; complete persisted configuration is NOT IMPLEMENTED.

**Plain-language answer:**
130. End to end: upload each file into an `UploadedImage`; validate/normalize source, requirements, scale and channel mapping; generate previews; preprocess DIC; run cached Mask R-CNN inference; postprocess/write `mask.tif`; classify/retain/refine candidate masks; write frames/crops/outlines/neck/pair geometry; preprocess fluorescence per cell; build canonical contours; execute selected plugins; persist `SegmentedImage`/`CellStatistics`; render overlays/tables; filter and export CSV/XLSX.
131. `CYTOCV_ANALYSIS_EXECUTION_MODE` supports `sync` and `worker`, default `sync`. Sync performs preparation/analysis inline through shared services; worker mode queues `UploadPreparationJob` and `AnalysisJob`. Production docs recommend worker mode but code default remains sync.
132. Progress is stored in job rows and mirrored filesystem state for legacy sync paths. Cancellation is cooperative between files/stages; cancelled analysis deletes source uploads and all artifacts. Failed analysis preserves source/previews but removes partial results/transients. Authenticated completed results start guest-owned and are atomically transferred on autosave if quota permits; otherwise remain session-listed transient. Default autosave is on. Saved quota defaults are 100 MB general and 1024 MB `.edu`; job caps default 1/2. Maintenance every 300 s in the combined worker (or timer) removes regenerable artifacts and unsaved runs older than 24 h while protecting active-job UUIDs. Queue/running stale defaults are 300/7200 s (upload 300/1800). Same active batch enqueue is idempotently reused; terminal/failure resubmission creates a new job. There is no automatic retry loop.
133. Major models: `CustomUser`, `UploadedImage`, `UploadPreparationJob`, `AnalysisJob`, `DVLayerTifPreview`, `SegmentedImage`, `CellStatistics`, plus django-allauth identity models. Files include source uploads; preview PNGs; `scale_info`; channel config/presence; preprocessed images/lists; `compressed_masks.csv`; `output/mask.tif`, `cellpairs.tif`, frames, `.outline`, `.neck_split`, pair geometry; segmented crops/no-outline/debug images; overlay render config/cache; progress/cancel/log artifacts.
134. Reproduction requires the exact source, commit, Python/dependencies, untracked model-weight bytes/checksum, channel config/presence, DIC mask/segmentation result or deterministic inference environment, scale_info, cell inclusion, selected plugins, signal/puncta/nuclear modes, effective thresholds/units, split/filter/alternate settings, and output unit/filter choices. The repository does not persist the commit or weight checksum with a result.
135. Complete persistence is NOT IMPLEMENTED. Worker snapshots omit CEN proximity radius/value unit, so worker execution falls back to 13 px even when sync session state differs. Row properties omit whether Green contour filtering was enabled. Sync runs have no durable run-level analysis snapshot. Software commit, dependency lock resolution, hardware, warm/cold runtime state, and model-weight checksum are not stored with results.
136. UI/JSON exposes selected plugins, visibility, contour counts, signal/nuclear status/channel data, ratio formula text, scale/filter context, and CEN diagnostics that are not CSV/XLSX columns. Model/JSON legacy Blue intensity values are absent from the current table/export field list. Conversely, table/export reconstructs property-backed center columns and exports `Nucleus Contour Source`/parentage labels; these also appear in UI cards/payload, so no exclusive export-only calculated metric was found.
137. Stale/contradictory material: root version `1.0` conflicts with tag/describe identity; five documents name NCP as a default; README’s “DIC-only structural run” conflicts with 3/4-layer upload validation; TIFF docs say only complete four-role metadata and ambiguous fallback, omitting accepted metadata-proven three-layer stacks and their fail-closed behavior; analysis-options lists only the two paired puncta modes; research docs claim each run retains selected analyses/settings strongly enough for traceability, but section 135 identifies missing persistence; qualitative manual-time reduction has no study; “raw only/not normalized fallback” wording overstates fallback behavior.

**Exact technical behavior:**
Worker and sync share `run_analysis_batch`/segmentation services, but configuration acquisition differs as stated.

**Inputs and prerequisites:**
Django environment, database, writable media, dependencies, and `cytocv/core/weights/deepretina_final.h5` (ignored by Git and not part of HEAD).

**Algorithm steps:**
1. Prepare upload.
2. preprocess/infer.
3. segment/retain/analyze.
4. persist ownership/results.
5. render/filter/export.
6. clean transient/failure/cancel artifacts by policy.

**Exact formulas:**
Retention cutoff is `now - max(TRANSIENT_RUN_RETENTION_HOURS,1)`; default 24 h. Quota projection sums retained run bytes before ownership transfer.

**Defaults and units:**
Sync, autosave on, 24-h transient retention, 300-s maintenance interval, quotas/caps as stated.

**Outputs and stored fields:**
Models/artifacts are listed in answer 133.

**Display/export behavior:**
Display/Dashboard share serialized statistics and `CellTable`; filters affect row selection only.

**Failure, null, zero, and N/A behavior:**
Cancellation deletes batch uploads; failure keeps upload/preview for a manual resubmission and removes partial calculations; storage-full autosave leaves completed results transient and returns a warning.

**Computational interpretation:**
Reproducibility is strongest for stored derived outputs; exact rerun reproducibility additionally depends on non-persisted revision/weights/environment/config gaps.

**Biological-evidence status:**
Workflow regression tests establish software behavior only.

**Tests executed:**
Async job, artifact storage, inference, upload preparation, security/accounts, and full suites passed.

**Exact implementation evidence:**
- `cytocv/core/services/analysis_pipeline.py` lines 40–227
- `cytocv/core/services/segmentation_pipeline.py` lines 482–1398
- `cytocv/core/services/analysis_context.py` lines 38–76 and 164–555
- `cytocv/core/models.py` lines 57–397
- `cytocv/core/services/analysis_jobs.py` lines 23–327
- `cytocv/core/services/artifact_storage.py` lines 40–802
- `cytocv/cytocv/settings.py` lines 138–161 and 523–570
- `cytocv/core/tests/test_analysis_async.py`
- `cytocv/core/tests/test_artifact_storage.py`

**Manuscript-safe wording:**
“CytoCV provides a synchronous or database-worker workflow from validated stack upload through DIC-guided Mask R-CNN segmentation, plugin measurement, persisted results, and filtered CSV/XLSX export. Exact reruns require archiving the commit, weight checksum, and effective configuration outside the current result schema.”

## O. Evidence and manuscript claim matrix (answers 138–141)

**Evidence outcome:** CONFIRMED IMPLEMENTATION for the evidence inventory; NO REPOSITORY EVIDENCE for the requested quantitative/biological performance claims.

**Plain-language answer:**
138. Input loading/channel validation, contour canonicalization, intensity formulas, PunctaDistance, GreenRedIntensity, nuclear intensity, CENDot, Biorientation, splitting/filtering, inclusion/parentage, scale, tables/export, preferences, jobs, quota, and cleanup have coded behavior plus regression tests. Mask R-CNN execution has coded behavior plus synthetic/runtime regression tests. No audited capability has a repository benchmark, manually curated comparison, or independent biological ground-truth evidence.
139. Manual-analysis time reduction: NO REPOSITORY EVIDENCE. Per-file inference improvement: NO REPOSITORY EVIDENCE. Batch inference improvement: NO REPOSITORY EVIDENCE. Storage reduction: NO REPOSITORY EVIDENCE. Accuracy/agreement with manual labels: NO REPOSITORY EVIDENCE. Sensitivity/specificity/error rate: NO REPOSITORY EVIDENCE.
140. No qualifying quantitative result was found, so there is no exact value, unit, dataset, sample size, hardware, warm/cold state, commit/version, producing script/table, or reproducibility record to report. Operational defaults (timeouts, quotas, compression levels) and algorithm thresholds are configuration values, not measured performance outcomes. The 17 committed DV files are unlabeled examples; no benchmark script/result links them to a performance claim.
141. Safe replacements: “CytoCV automates a configurable image-processing and per-cell measurement workflow” instead of a time-reduction number; “the process-local inference runtime reuses a loaded model” instead of an inference-speed percentage; “transient artifacts are cleaned under retention policy” instead of a storage-reduction percentage; and “outputs are software-derived classifications/measurements with regression-tested formulas” instead of accuracy, agreement, sensitivity, specificity, or error-rate claims.

**Exact technical behavior:**
The repository contains unit/integration/regression evidence and sample DV inputs, but no experiment design joining predictions to curated truth or timing/storage baselines.

**Inputs and prerequisites:**
Evidence search covered tracked source, tests, docs/research, release notes, Git history, 17 DV samples, figures/PDFs, and all tracked CSV/XLSX/notebook-like files; none of the latter result/label formats are tracked.

**Algorithm steps:**
1. Search claims/keywords and data/result formats.
2. inspect research/manuscript/release material.
3. distinguish test assertions from biological labels/benchmarks.
4. classify each claim in `cytocv_claim_evidence_matrix.csv`.

**Exact formulas:**
Not applicable to absent performance claims; algorithm formulas are documented in sections C–L.

**Defaults and units:**
Not applicable to absent performance measurements.

**Outputs and stored fields:**
The claim matrix contains 141 rows: 132 CONFIRMED IMPLEMENTATION, 2 NOT IMPLEMENTED, and 7 NO REPOSITORY EVIDENCE.

**Display/export behavior:**
No benchmark-result export exists.

**Failure, null, zero, and N/A behavior:**
Evidence absence is reported as the final outcome NO REPOSITORY EVIDENCE, not as a pending task.

**Computational interpretation:**
Passing tests prove coded behavior and failure contracts, not biological correctness or real-world performance magnitude.

**Biological-evidence status:**
NO REPOSITORY EVIDENCE for independent biological ground truth across all major scientific classifications.

**Tests executed:**
- `CYTOCV_DB_BACKEND=sqlite python manage.py test core accounts --verbosity 1`: 911 tests, all passed in 402.738 s, no skips/xfails reported.
- Targeted scientific/export suite: 312 tests, all passed in 20.711 s, no skips/xfails reported.
- `test_accounts_preferences`: 155 tests, all passed in 121.325 s, no skips/xfails reported.
- `manage.py check`, migration dry run, static dry run, compileall, every JavaScript `node --check`, and `git diff --check`: passed.

**Exact implementation evidence:**
- `cytocv/core/tests/` and `cytocv/accounts/tests*.py`
- `Test_Files/` (17 tracked DV files; no labels/results)
- `docs/research/` (descriptive material; no performance result tables)
- `cytocv/templates/about.html` line 87 (qualitative time-reduction claim without quantitative support)

**Manuscript-safe wording:**
“Repository evidence establishes implementation behavior through 911 passing software tests. The repository contains no quantitative timing, storage, agreement, sensitivity, specificity, error-rate, curated-label, or independent biological-ground-truth study; scientific outputs are therefore described as software-derived measurements and classifications.”

## Implementation inconsistencies and correction recommendations

1. Version identity: replace README `Version: 1.0` with an explicit release/tag policy and cite the exact commit in manuscripts.
2. Default plugin lists: remove `NuclearCellPairIntensity` from every default list named in section G; corrected wording is “Defaults: PunctaDistance, CENDot, Biorientation, GreenRedIntensity; NuclearCellPairIntensity is optional.”
3. Worker CEN proximity persistence: add value/unit keys to `DEFAULT_ANALYSIS_CONFIG_SNAPSHOT`, normalization, and `build_analysis_config_snapshot`; until changed, state that worker mode uses 13 px.
4. Per-row reproducibility: persist Green-filter enabled state, commit, weight checksum, and a complete normalized run snapshot.
5. Three-layer TIFF docs: replace “incomplete metadata falls back” with “a three-layer stack is accepted only when reliable metadata identifies DIC plus exactly two fluorescence roles and all required roles; ambiguous three-layer stacks are rejected.”
6. Puncta-mode docs: list all four modes, including Red-only and Green-only.
7. Intensity-source docs: replace unconditional “raw” language with the exact raw → background-subtracted → preprocessed fallback chain.
8. Performance language: replace “reduce manual analysis time” with “automates image processing and per-cell measurement”; no percentage or time saving is supported.
9. Invalid biorientation config: change the `analysis_context` invalid-value fallback from 66 to the shared 3-px constant to eliminate divergent normalization.
