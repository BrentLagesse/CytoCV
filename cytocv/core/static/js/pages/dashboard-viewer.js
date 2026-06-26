        const resultsViewerShared = window.CytoCVResultsViewerShared;
        const { readJsonConfig } = resultsViewerShared;
        const { bindContourIntensityDisplayControls } = resultsViewerShared;

        const dashboardPageConfig = readJsonConfig('dashboardPageConfig');
        window.CytoCVDashboardPageConfig = dashboardPageConfig;

        function applyQuotaFillWidths() {
            document.querySelectorAll('.quota-fill[data-quota-fill-width]').forEach((element) => {
                const quotaFillWidth = element.dataset.quotaFillWidth;
                element.style.setProperty('--quota-fill-width', `${quotaFillWidth}%`);
            });
        }
        applyQuotaFillWidths();

        function getCsrfToken() {
            const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
            return match ? decodeURIComponent(match[1]) : '';
        }
        const csrfToken = getCsrfToken();
        const confirmCellDeletion = dashboardPageConfig.confirmCellDeletion === true;
        const confirmMultiCellDeletion = dashboardPageConfig.confirmMultiCellDeletion === true;

        // Parse JSON file data
        let filesData = {};
        let filesDataParseError = false;
        try {
            filesData = JSON.parse(document.getElementById('dashboardFilesData').textContent || '{}');
        } catch (err) {
            filesData = {};
            filesDataParseError = true;
        }
        let fileUUIDs = Object.keys(filesData);
        const dashboardHasFiles = dashboardPageConfig.hasFiles === true;
        let currentFileIndex = 0;
        let currentCellNumber = 1;
        let maxCells;
        const channels = ["dic", "blue", "red", "green"];
        const normalizeMainImageChannel = (channel) => resultsViewerShared.normalizeMainImageChannel(channel, channels);
        const getSortedCellIds = resultsViewerShared.getSortedCellIds;
        let activeChannelRequest = 0;
        const defaultChannelIndexMap = { 0: 'dic', 1: 'blue', 2: 'green', 3: 'red' };
        const noCellPlaceholder =
            "data:image/svg+xml;utf8," + encodeURIComponent(
                '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="220" viewBox="0 0 320 220">' +
                '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#1d2530"/><stop offset="100%" stop-color="#10151c"/></linearGradient></defs>' +
                '<rect width="320" height="220" fill="url(#g)"/>' +
                '<text x="50%" y="46%" fill="#8fa6bf" font-size="15" font-family="Segoe UI, Arial, sans-serif" text-anchor="middle">No segmented cell image</text>' +
                '<text x="50%" y="58%" fill="#6f859d" font-size="12" font-family="Segoe UI, Arial, sans-serif" text-anchor="middle">Check channel mapping and rerun segmentation</text>' +
                '</svg>'
            );
        const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const getContourToggleState = resultsViewerShared.getContourToggleState;
        const getVisibleCellImageUrls = (imageUrls, showContours = getContourToggleState()) =>
            resultsViewerShared.getVisibleCellImageUrls(imageUrls, showContours, noCellPlaceholder);
        const {
            defaultStatVisibility,
            getStatVisibility,
            showChannelError,
            preloadImage,
            preloadImageSet,
            setCellPairImagesLoading,
            setCellDataRegionLoading,
            createCellDataRegionLoadingController,
            bindFilterMenuPointerAwayClose,
        } = resultsViewerShared;
        const FILE_BLEND_TEXT_MS = 170;
        const FILE_BLEND_IMAGE_MS = 190;
        const BLEND_METRIC_IDS = [
            'distance',
            'punctaLineIntensity',
            'measurementContourRatioFormula',
            'measurementContourRatio1',
            'measurementContourRatio2',
            'measurementContourRatio3',
            'redInRedIntensity1',
            'redInRedIntensity2',
            'redInRedIntensity3',
            'greenInRedIntensity1',
            'greenInRedIntensity2',
            'greenInRedIntensity3',
            'redInGreenIntensity1',
            'redInGreenIntensity2',
            'redInGreenIntensity3',
            'greenInGreenIntensity1',
            'greenInGreenIntensity2',
            'greenInGreenIntensity3',
            'nucleusIntensitySum',
            'cellPairIntensitySum',
            'cytoplasmicIntensity',
            'nuclearCytoplasmicRatio',
            'cellParentage',
            'cenDot',
            'colinearDots',
            'offAxisDots',
            'nucleusContourChannel',
            'measurementChannel',
            'nuclearStatus',
        ];
        const defaultSpatialStatsUnit = dashboardPageConfig.defaultSpatialStatsUnit || 'px';
        const initialSidebarSpatialStatsUnit = dashboardPageConfig.initialSidebarSpatialStatsUnit || defaultSpatialStatsUnit;
        const initialPreferredMainImageChannel = dashboardPageConfig.initialPreferredMainImageChannel || '';
        const spatialFieldKinds = {
            puncta_distance: 'distance',
            blue_contour_size: 'area',
            blue_contour_center_xy: 'coordinate',
            red_contour_1_size: 'area',
            red_contour_2_size: 'area',
            red_contour_3_size: 'area',
            red_contour_1_center_xy: 'coordinate',
            red_contour_2_center_xy: 'coordinate',
            red_contour_3_center_xy: 'coordinate',
            green_contour_1_size: 'area',
            green_contour_2_size: 'area',
            green_contour_3_size: 'area',
            green_contour_1_center_xy: 'coordinate',
            green_contour_2_center_xy: 'coordinate',
            green_contour_3_center_xy: 'coordinate',
            distance_of_green_from_red_1: 'distance',
            distance_of_green_from_red_2: 'distance',
            distance_of_green_from_red_3: 'distance',
        };
        const tableFieldOrder = [
            'cell_id',
            'cell_type',
            'puncta_distance',
            'puncta_line_intensity',
            'blue_contour_size',
            'blue_contour_center_xy',
            'red_contour_1_size',
            'red_contour_2_size',
            'red_contour_3_size',
            'red_contour_1_center_xy',
            'red_contour_2_center_xy',
            'red_contour_3_center_xy',
            'green_contour_1_size',
            'green_contour_2_size',
            'green_contour_3_size',
            'green_contour_1_center_xy',
            'green_contour_2_center_xy',
            'green_contour_3_center_xy',
            'red_in_red_total_intensity_1',
            'red_in_red_max_intensity_1',
            'red_in_red_average_intensity_1',
            'red_in_red_total_intensity_2',
            'red_in_red_max_intensity_2',
            'red_in_red_average_intensity_2',
            'red_in_red_total_intensity_3',
            'red_in_red_max_intensity_3',
            'red_in_red_average_intensity_3',
            'green_in_red_total_intensity_1',
            'green_in_red_max_intensity_1',
            'green_in_red_average_intensity_1',
            'green_in_red_total_intensity_2',
            'green_in_red_max_intensity_2',
            'green_in_red_average_intensity_2',
            'green_in_red_total_intensity_3',
            'green_in_red_max_intensity_3',
            'green_in_red_average_intensity_3',
            'red_in_green_total_intensity_1',
            'red_in_green_max_intensity_1',
            'red_in_green_average_intensity_1',
            'red_in_green_total_intensity_2',
            'red_in_green_max_intensity_2',
            'red_in_green_average_intensity_2',
            'red_in_green_total_intensity_3',
            'red_in_green_max_intensity_3',
            'red_in_green_average_intensity_3',
            'green_in_green_total_intensity_1',
            'green_in_green_max_intensity_1',
            'green_in_green_average_intensity_1',
            'green_in_green_total_intensity_2',
            'green_in_green_max_intensity_2',
            'green_in_green_average_intensity_2',
            'green_in_green_total_intensity_3',
            'green_in_green_max_intensity_3',
            'green_in_green_average_intensity_3',
            'measurement_contour_ratio_1',
            'measurement_contour_ratio_2',
            'measurement_contour_ratio_3',
            'distance_of_green_from_red_1',
            'distance_of_green_from_red_2',
            'distance_of_green_from_red_3',
            'nuclear_cell_pair_contour_source',
            'cell_pair_intensity_sum',
            'nucleus_intensity_sum',
            'cytoplasmic_intensity',
            'nuclear_cytoplasmic_ratio',
            'cell_parentage',
            'category_cen_dot',
            'colinear_dots',
            'off_axis_dots',
        ];
        const statFieldGroups = {
            puncta_distance: ['puncta_distance', 'puncta_line_intensity'],
            legacy_blue_intensity: ['blue_contour_size', 'blue_contour_center_xy'],
            red_green_intensity: [
                'red_contour_1_size',
                'red_contour_2_size',
                'red_contour_3_size',
                'red_contour_1_center_xy',
                'red_contour_2_center_xy',
                'red_contour_3_center_xy',
                'green_contour_1_size',
                'green_contour_2_size',
                'green_contour_3_size',
                'green_contour_1_center_xy',
                'green_contour_2_center_xy',
                'green_contour_3_center_xy',
                'red_in_red_total_intensity_1',
                'red_in_red_max_intensity_1',
                'red_in_red_average_intensity_1',
                'red_in_red_total_intensity_2',
                'red_in_red_max_intensity_2',
                'red_in_red_average_intensity_2',
                'red_in_red_total_intensity_3',
                'red_in_red_max_intensity_3',
                'red_in_red_average_intensity_3',
                'green_in_red_total_intensity_1',
                'green_in_red_max_intensity_1',
                'green_in_red_average_intensity_1',
                'green_in_red_total_intensity_2',
                'green_in_red_max_intensity_2',
                'green_in_red_average_intensity_2',
                'green_in_red_total_intensity_3',
                'green_in_red_max_intensity_3',
                'green_in_red_average_intensity_3',
                'red_in_green_total_intensity_1',
                'red_in_green_max_intensity_1',
                'red_in_green_average_intensity_1',
                'red_in_green_total_intensity_2',
                'red_in_green_max_intensity_2',
                'red_in_green_average_intensity_2',
                'red_in_green_total_intensity_3',
                'red_in_green_max_intensity_3',
                'red_in_green_average_intensity_3',
                'green_in_green_total_intensity_1',
                'green_in_green_max_intensity_1',
                'green_in_green_average_intensity_1',
                'green_in_green_total_intensity_2',
                'green_in_green_max_intensity_2',
                'green_in_green_average_intensity_2',
                'green_in_green_total_intensity_3',
                'green_in_green_max_intensity_3',
                'green_in_green_average_intensity_3',
                'measurement_contour_ratio_1',
                'measurement_contour_ratio_2',
                'measurement_contour_ratio_3',
                'distance_of_green_from_red_1',
                'distance_of_green_from_red_2',
                'distance_of_green_from_red_3',
            ],
            nuclear_cell_pair_intensity: [
                'nuclear_cell_pair_contour_source',
                'cell_pair_intensity_sum',
                'nucleus_intensity_sum',
                'cytoplasmic_intensity',
                'nuclear_cytoplasmic_ratio',
            ],
            cen_dot: ['cell_parentage', 'category_cen_dot'],
            biorientation: ['colinear_dots', 'off_axis_dots'],
        };
        const spatialHeaderBaseLabels = {
            blue_contour_size: 'Blue Contour Size',
            blue_contour_center_xy: 'Blue Contour Center (x,y)',
            red_contour_1_size: 'Red Contour 1 Size',
            red_contour_1_center_xy: 'Red Contour 1 Center (x,y)',
            red_contour_2_size: 'Red Contour 2 Size',
            red_contour_2_center_xy: 'Red Contour 2 Center (x,y)',
            red_contour_3_size: 'Red Contour 3 Size',
            red_contour_3_center_xy: 'Red Contour 3 Center (x,y)',
            green_contour_1_size: 'Green Contour 1 Size',
            green_contour_1_center_xy: 'Green Contour 1 Center (x,y)',
            green_contour_2_size: 'Green Contour 2 Size',
            green_contour_2_center_xy: 'Green Contour 2 Center (x,y)',
            green_contour_3_size: 'Green Contour 3 Size',
            green_contour_3_center_xy: 'Green Contour 3 Center (x,y)',
            distance_of_green_from_red_1: 'Distance Of Green From Red 1',
            distance_of_green_from_red_2: 'Distance Of Green From Red 2',
            distance_of_green_from_red_3: 'Distance Of Green From Red 3',
        };
        let currentSpatialStatsUnit = initialSidebarSpatialStatsUnit;
        let currentContourIntensityDisplayType = 'total';
        const {
            applyMetricVisibility,
            normalizeSpatialUnit,
            getCurrentSpatialUnit,
            getScaleContext,
            formatSpatialLabel,
            formatFieldValue,
            formatStatValue,
            hasNoNucleusContour,
            getNuclearLabelPair,
            buildCellCardMetricValues,
            getDynamicSpatialHeaderLabel,
            renderStatisticsTable,
            hasStatisticsTableRows,
            normalizePunctaSourceContourCountFilter,
            getPunctaSourceContourCountFilterLabel,
            normalizeCellTypeFilter,
            getCellTypeFilterLabel,
            matchesCellTypeFilter,
            getCellTypeFilterUiState,
            getPunctaSourceContourContext,
            matchesPunctaSourceContourCountFilter,
            getPunctaSourceContourCountFilterCounts,
            getPunctaSourceContourFilterUiState,
            getRowFilterEmptyMessage,
            getPunctaSourceContourFilteredCellIds,
            findNearestMatchingCellByOriginalOrder,
            getAdjacentFilteredCellId,
            updateSpatialUnitControls,
            bindSpatialUnitControls,
        } = resultsViewerShared.createStatisticsHelpers({
            tableFieldOrder,
            statFieldGroups,
            spatialFieldKinds,
            spatialHeaderBaseLabels,
            defaultSpatialStatsUnit,
            getCurrentSpatialStatsUnit: () => currentSpatialStatsUnit,
            setCurrentSpatialStatsUnit: (unit) => {
                currentSpatialStatsUnit = unit;
            },
        });
        let currentCellTypeFilter = normalizeCellTypeFilter(
            dashboardPageConfig.initialCellTypeFilter
        );
        let currentPunctaSourceContourCountFilter = normalizePunctaSourceContourCountFilter(
            dashboardPageConfig.initialPunctaSourceContourCountFilter
        );
        const PUNCTA_SOURCE_FILTER_APPLY_FEEDBACK_MS = 120;
        const CELL_DATA_REGION_LOADING_MIN_MS = 160;
        let punctaSourceContourApplySkeletonTimer = null;
        const cellDataRegionLoadingController = createCellDataRegionLoadingController({
            minimumDurationMs: CELL_DATA_REGION_LOADING_MIN_MS,
        });
        const punctaSourceContourFilterControl = document.getElementById('punctaSourceContourFilterControl');
        const punctaSourceContourFilterButton = document.getElementById('punctaSourceContourFilterButton');
        const punctaSourceContourFilterValue = document.getElementById('punctaSourceContourFilterValue');
        const punctaSourceContourFilterMenu = document.getElementById('punctaSourceContourFilterMenu');
        const punctaSourceContourFilterLabel = document.getElementById('punctaSourceContourFilterLabel');
        const cellTypeFilterControl = document.getElementById('cellTypeFilterControl');
        const cellTypeFilterButton = document.getElementById('cellTypeFilterButton');
        const cellTypeFilterValue = document.getElementById('cellTypeFilterValue');
        const cellTypeFilterMenu = document.getElementById('cellTypeFilterMenu');
        let preferredMainImageChannel = normalizeMainImageChannel(initialPreferredMainImageChannel);
        let activeFileLoadToken = 0;
        let activeCellRenderToken = 0;
        let hasInitializedDashboardFile = false;
        let fileSwapLoading = false;
        const fileSwapRoot = document.querySelector('.dashboard-page');
        const mainImageWarmStateByFile = new Map();
        const {
            setTextWithBlend,
            setImageWithBlend,
        } = resultsViewerShared.createBlendHelpers({
            reducedMotion: REDUCED_MOTION,
            isInitialized: () => hasInitializedDashboardFile,
            noCellPlaceholder,
            defaultTextDuration: FILE_BLEND_TEXT_MS,
            defaultImageDuration: FILE_BLEND_IMAGE_MS,
        });
        const {
            getMainImagePaths,
            markMainImageChannelWarm,
            warmMainImageChannel,
            primeMainImageWarmState,
            scheduleMainImageWarmup,
        } = resultsViewerShared.createMainImageHelpers({
            channels,
            defaultChannelIndexMap,
            mainImageWarmStateByFile,
            getCurrentFileData: () => {
                const currentFileUUID = fileUUIDs[currentFileIndex];
                return currentFileUUID ? filesData[currentFileUUID] : null;
            },
        });
        const overlayWarmCoordinator = window.CytoCVOverlayPrefetch
            ? window.CytoCVOverlayPrefetch.createWarmCoordinator({
                resolveUrl: ({ fileKey, cellNumber }) => {
                    const fileData = filesData[fileKey];
                    if (!fileData) {
                        return '';
                    }
                    const pairImages = fileData.CellPairImages || {};
                    const imageUrls = pairImages[cellNumber] || pairImages[String(cellNumber)] || null;
                    if (!Array.isArray(imageUrls)) {
                        return '';
                    }
                    return [2, 4, 6]
                        .map((index) => imageUrls[index] || '')
                        .find((url) => typeof url === 'string' && url.includes('/overlay/')) || '';
                },
                warmUrl: (url) => preloadImage(url),
            })
            : {
                markCellWarm() {},
                scheduleCells() {},
            };

        function setFileSwapLoading(isLoading, requestToken = null) {
            if (requestToken !== null && requestToken !== activeFileLoadToken) {
                return;
            }
            fileSwapLoading = !!isLoading;
            if (fileSwapRoot) {
                fileSwapRoot.classList.toggle('is-file-swap-loading', fileSwapLoading);
            }
            syncFileNavigationState();
        }







        function getCellDisplayState(cellPairImages, statistics, { showContours = getContourToggleState(), cellNumber = currentCellNumber } = {}) {
            const safeCellPairImages = cellPairImages || {};
            const safeStatistics = statistics || {};
            const imageUrls = safeCellPairImages[cellNumber] || safeCellPairImages[String(cellNumber)] || null;
            const visibleImageUrls = getVisibleCellImageUrls(imageUrls, showContours);
            const cellStats = safeStatistics[cellNumber] || safeStatistics[String(cellNumber)] || null;
            const fileUUID = fileUUIDs[currentFileIndex];
            const scaleContext = getScaleContext(filesData[fileUUID]);
            const cellCard = buildCellCardMetricValues(cellStats, {
                scaleContext,
                contourIntensityType: currentContourIntensityDisplayType,
            });

            return {
                visibleImageUrls,
                cellId: (imageUrls || cellStats) ? cellNumber : 0,
                mode: cellCard.mode,
                sections: cellCard.sections,
                visibleContourIntensityCombinations: cellCard.visibleContourIntensityCombinations,
                metricValues: cellCard.metricValues,
                labels: cellCard.labels,
            };
        }

        function renderCellDisplayState(state, { blendImages = false, blendText = false } = {}) {
            if (!state) {
                return Promise.resolve();
            }

            document.getElementById('distanceLabel').textContent = state.labels.distanceLabel;
            document.getElementById('lineIntensityLabel').textContent = state.labels.lineIntensityLabel;
            document.getElementById('nucleusIntensityLabel').textContent = state.labels.nucleusIntensityLabel;
            document.getElementById('cellularIntensityLabel').textContent = state.labels.cellularIntensityLabel;
            const contourIntensityTypeLabel = state.labels.contourIntensityTypeLabel || 'Total';
            const contourIntensityTypeLabelUpdates = Array.from(
                document.querySelectorAll('[data-contour-intensity-type-label]')
            ).map((element) => setTextWithBlend(element, contourIntensityTypeLabel, { blend: blendText }));
            document.querySelectorAll('[data-contour-intensity-label-for]').forEach((element) => {
                const metricId = element.dataset.contourIntensityLabelFor;
                const label = state.labels.contourIntensityLabels?.[metricId];
                if (!label) return;
                element.setAttribute('aria-label', label);
                element.setAttribute('title', label);
                element.textContent = element.dataset.contourSlotLabel || label;
            });
            applyMetricVisibility(state.sections || { reference: true }, {
                mode: state.mode,
                contourIntensityCombinations: state.visibleContourIntensityCombinations,
            });

            const imageIds = ['cellImage1', 'cellImage2', 'cellImage3', 'cellImage4'];
            const imageUpdates = imageIds.map((id, index) =>
                setImageWithBlend(document.getElementById(id), state.visibleImageUrls[index], {
                    duration: FILE_BLEND_IMAGE_MS,
                    blend: blendImages,
                })
            );

            const textUpdates = [
                setTextWithBlend(document.getElementById('cellID'), state.cellId, { blend: blendText }),
                ...contourIntensityTypeLabelUpdates,
                ...BLEND_METRIC_IDS.map((metricId) =>
                    setTextWithBlend(document.getElementById(metricId), state.metricValues[metricId] ?? 'N/A', { blend: blendText })
                ),
            ];

            return Promise.all([...imageUpdates, ...textUpdates]);
        }





        function setActiveChannel(channel) {
            resultsViewerShared.setActiveChannel(channel, mainChannelButtons);
        }


        function getPreferredMainImageChannel() {
            return normalizeMainImageChannel(preferredMainImageChannel);
        }

        function setPreferredMainImageChannel(channel) {
            preferredMainImageChannel = normalizeMainImageChannel(channel);
            return preferredMainImageChannel;
        }

        async function persistPreferredMainImageChannel(channel) {
            const response = await fetch('/dashboard/preferences/channels/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || '',
                },
                credentials: 'same-origin',
                body: JSON.stringify({ main_image_channel: normalizeMainImageChannel(channel) }),
            });
            if (!response.ok) {
                throw new Error('Unable to save main image channel preference.');
            }
            const payload = await response.json();
            return setPreferredMainImageChannel(payload.main_image_channel || channel);
        }

        function showChannelPreferenceWarning() {
            showChannelError('Main channel changed, but the preference could not be saved right now.');
        }

        function syncContourStateLabel(showContours) {
            const contourStateValue = document.getElementById('contourStateValue');
            if (contourStateValue) {
                contourStateValue.textContent = showContours ? 'On' : 'Off';
            }
        }












        updateSpatialUnitControls(filesData[fileUUIDs[currentFileIndex]] || null);








        function buildDashboardExportUrl(fileUUID, format, selectedColumns = null) {
            const params = new URLSearchParams({
                file_uuid: fileUUID,
                _export: format,
                _unit: getCurrentSpatialUnit(),
                _cell_type: getCurrentCellTypeFilter(),
                _puncta_source_contour_count: getCurrentPunctaSourceContourCountFilter(),
            });
            if (Array.isArray(selectedColumns) && selectedColumns.length > 0) {
                params.set('_columns', selectedColumns.join(','));
            }
            return `/dashboard/?${params.toString()}`;
        }

        function getExportSelectionStatLabel(item, context = {}) {
            if (context.currentTableLabel) {
                return context.currentTableLabel;
            }
            const fieldName = item ? (item.tableField || item.id) : '';
            if (fieldName && Object.prototype.hasOwnProperty.call(spatialFieldKinds, fieldName)) {
                const fileUUID = fileUUIDs[currentFileIndex];
                return getDynamicSpatialHeaderLabel(fieldName, filesData[fileUUID] || null);
            }
            return item ? (item.label || item.id) : '';
        }

        function syncDashboardExportButtons(fileUUID, fileData, renderedRowCount = 0) {
            const exportButtons = document.getElementById('exportButtons');
            if (!exportButtons) {
                return;
            }

            const canExport = Boolean(fileUUID) && hasStatisticsTableRows(fileData, renderedRowCount);
            exportButtons.style.display = canExport ? 'flex' : 'none';
            if (!canExport) {
                return;
            }

            const statsBtn = document.getElementById('downloadStatsBtn');
            if (statsBtn) {
                statsBtn.href = buildDashboardExportUrl(fileUUID, 'csv');
            }
        }

        let dashboardExportSelectionController = null;
        if (window.CytoCVExportSelection) {
            dashboardExportSelectionController = window.CytoCVExportSelection.init({
                configScriptId: 'exportSelectionConfig',
                modalId: 'exportSelectionBackdrop',
                triggerFormats: {
                    downloadStatsBtn: 'csv',
                },
                getCurrentFileContext: () => {
                    const fileUUID = fileUUIDs[currentFileIndex];
                    return {
                        fileUUID,
                        fileData: fileUUID ? filesData[fileUUID] : null,
                    };
                },
                buildExportUrl: buildDashboardExportUrl,
                getStatLabel: getExportSelectionStatLabel,
                bulkExportUrl: '/dashboard/files/export/',
                getSelectableFiles: () => fileUUIDs.map((fileUUID) => ({
                    id: fileUUID,
                    label: filesData[fileUUID] && filesData[fileUUID].Image_Name
                        ? filesData[fileUUID].Image_Name
                        : fileUUID,
                    fileData: filesData[fileUUID] || null,
                })),
                buildBulkExportPayload: ({ fileIds, format, columns }) => ({
                    uuids: fileIds,
                    _export: format,
                    _columns: columns,
                    _unit: getCurrentSpatialUnit(),
                    _cell_type: getCurrentCellTypeFilter(),
                    _puncta_source_contour_count: getCurrentPunctaSourceContourCountFilter(),
                }),
            });
            window.dashboardExportSelectionController = dashboardExportSelectionController;
        }

        function getCurrentFileData() {
            const fileUUID = fileUUIDs[currentFileIndex];
            return fileUUID ? filesData[fileUUID] : null;
        }

        function getCurrentCellTypeFilter(fileData = getCurrentFileData()) {
            return getCellTypeFilterUiState(
                fileData?.Statistics || {},
                currentCellTypeFilter,
            ).effectiveFilter;
        }

        function setCurrentCellTypeFilter(value) {
            currentCellTypeFilter = normalizeCellTypeFilter(value);
            const fileData = getCurrentFileData();
            syncCellTypeFilterControl(fileData);
            syncPunctaSourceContourFilterControl(fileData);
            return getCurrentCellTypeFilter(fileData);
        }

        function syncCellTypeFilterControl(fileData = getCurrentFileData()) {
            const state = getCellTypeFilterUiState(
                fileData?.Statistics || {},
                currentCellTypeFilter,
            );
            const effectiveFilter = state.effectiveFilter;
            if (cellTypeFilterValue) {
                cellTypeFilterValue.textContent = state.displayLabel;
            }
            if (cellTypeFilterControl) {
                cellTypeFilterControl.classList.toggle('is-disabled', !state.enabled);
                cellTypeFilterControl.dataset.availableCellTypes = state.availableCellTypes.join(',');
            }
            if (cellTypeFilterButton) {
                cellTypeFilterButton.disabled = !state.enabled;
                cellTypeFilterButton.setAttribute('aria-disabled', state.enabled ? 'false' : 'true');
                cellTypeFilterButton.title = state.helpText;
                if (!state.enabled) {
                    closeCellTypeFilterMenu();
                }
            }
            if (cellTypeFilterMenu) {
                cellTypeFilterMenu.querySelectorAll('[data-value]').forEach((option) => {
                    const selected = option.dataset.value === effectiveFilter;
                    option.classList.toggle('is-selected', selected);
                    option.setAttribute('aria-selected', selected ? 'true' : 'false');
                });
            }
        }

        function closeCellTypeFilterMenu() {
            if (!cellTypeFilterMenu || !cellTypeFilterButton) return;
            cellTypeFilterMenu.hidden = true;
            cellTypeFilterButton.setAttribute('aria-expanded', 'false');
        }

        function getCurrentPunctaSourceContourCountFilter() {
            return getPunctaSourceContourFilterUiState(
                getCurrentFileData()?.Statistics || {},
                currentPunctaSourceContourCountFilter,
            ).effectiveFilter;
        }

        function setCurrentPunctaSourceContourCountFilter(value) {
            currentPunctaSourceContourCountFilter = normalizePunctaSourceContourCountFilter(value);
            const fileData = getCurrentFileData();
            syncPunctaSourceContourFilterControl(fileData);
            return getCurrentPunctaSourceContourCountFilter();
        }

        function getEffectivePunctaSourceContourCountFilter(fileData) {
            return getPunctaSourceContourFilterUiState(
                fileData?.Statistics || {},
                currentPunctaSourceContourCountFilter,
            ).effectiveFilter;
        }

        function syncPunctaSourceContourFilterControl(fileData) {
            const state = getPunctaSourceContourFilterUiState(
                fileData?.Statistics || {},
                currentPunctaSourceContourCountFilter,
            );
            const effectiveFilter = state.effectiveFilter;
            if (punctaSourceContourFilterLabel) {
                punctaSourceContourFilterLabel.textContent = `${state.controlLabel}:`;
            }
            if (punctaSourceContourFilterValue) {
                punctaSourceContourFilterValue.textContent = getPunctaSourceContourCountFilterLabel(effectiveFilter);
            }
            if (punctaSourceContourFilterControl) {
                punctaSourceContourFilterControl.classList.toggle('is-disabled', !state.enabled);
                punctaSourceContourFilterControl.dataset.sourceChannel = state.channel || '';
            }
            if (punctaSourceContourFilterButton) {
                punctaSourceContourFilterButton.disabled = !state.enabled;
                punctaSourceContourFilterButton.setAttribute('aria-disabled', state.enabled ? 'false' : 'true');
                if (!state.enabled) {
                    closePunctaSourceContourFilterMenu();
                }
            }
            if (punctaSourceContourFilterMenu) {
                punctaSourceContourFilterMenu.querySelectorAll('[data-value]').forEach((option) => {
                    const selected = option.dataset.value === effectiveFilter;
                    option.classList.toggle('is-selected', selected);
                    option.setAttribute('aria-selected', selected ? 'true' : 'false');
                });
            }
        }

        function closePunctaSourceContourFilterMenu() {
            if (!punctaSourceContourFilterMenu || !punctaSourceContourFilterButton) return;
            punctaSourceContourFilterMenu.hidden = true;
            punctaSourceContourFilterButton.setAttribute('aria-expanded', 'false');
        }

        if (typeof bindFilterMenuPointerAwayClose === 'function') {
            bindFilterMenuPointerAwayClose({
                control: cellTypeFilterControl,
                button: cellTypeFilterButton,
                menu: cellTypeFilterMenu,
                closeMenu: closeCellTypeFilterMenu,
            });
            bindFilterMenuPointerAwayClose({
                control: punctaSourceContourFilterControl,
                button: punctaSourceContourFilterButton,
                menu: punctaSourceContourFilterMenu,
                closeMenu: closePunctaSourceContourFilterMenu,
            });
        }

        function waitForPunctaSourceContourFilterApplyFeedback() {
            return new Promise((resolve) => {
                window.setTimeout(resolve, PUNCTA_SOURCE_FILTER_APPLY_FEEDBACK_MS);
            });
        }

        function setPunctaSourceContourFilterApplying(isApplying) {
            const status = document.getElementById('punctaSourceContourFilterStatus');
            if (!status) return;
            status.classList.toggle('is-applying-filter', !!isApplying);
            if (isApplying) {
                status.textContent = 'Applying filter...';
                status.dataset.activeFilter = 'Applying filter';
            }
        }

        function setPunctaSourceContourFilterSkeleton(isApplying) {
            setCellDataRegionLoading(isApplying);
        }

        function startPunctaSourceContourFilterApplyVisualState() {
            setPunctaSourceContourFilterApplying(true);
            if (punctaSourceContourApplySkeletonTimer) {
                window.clearTimeout(punctaSourceContourApplySkeletonTimer);
            }
            setPunctaSourceContourFilterSkeleton(false);
            punctaSourceContourApplySkeletonTimer = window.setTimeout(() => {
                punctaSourceContourApplySkeletonTimer = null;
                setPunctaSourceContourFilterSkeleton(true);
            }, PUNCTA_SOURCE_FILTER_APPLY_FEEDBACK_MS);
        }

        function clearPunctaSourceContourFilterApplyVisualState() {
            if (punctaSourceContourApplySkeletonTimer) {
                window.clearTimeout(punctaSourceContourApplySkeletonTimer);
                punctaSourceContourApplySkeletonTimer = null;
            }
            setPunctaSourceContourFilterSkeleton(false);
        }

        function syncPunctaSourceContourFilterStatus(fileData, renderedRowCount = 0) {
            const status = document.getElementById('punctaSourceContourFilterStatus');
            if (status) {
                status.classList.remove('is-applying-filter');
                const sourceState = getPunctaSourceContourFilterUiState(
                    fileData?.Statistics || {},
                    currentPunctaSourceContourCountFilter,
                );
                const counts = getPunctaSourceContourCountFilterCounts(
                    fileData?.Statistics || {},
                    sourceState.effectiveFilter,
                    getCurrentCellTypeFilter(fileData),
                );
                const shown = Number.isFinite(Number(renderedRowCount))
                    ? Number(renderedRowCount)
                    : counts.shown;
                status.textContent = `Showing ${shown} of ${counts.total} cells`;
                status.dataset.activeFilter = [
                    getCellTypeFilterLabel(getCurrentCellTypeFilter(fileData)),
                    getPunctaSourceContourCountFilterLabel(sourceState.effectiveFilter),
                ].join(' / ');
            }
            syncPunctaSourceContourCellCardState(fileData);
        }

        function getActiveCellNavigationIds(fileData) {
            const filterValue = getEffectivePunctaSourceContourCountFilter(fileData);
            const allIds = new Set(getSortedCellIds(fileData));
            return getPunctaSourceContourFilteredCellIds(
                fileData,
                filterValue,
                getCurrentCellTypeFilter(),
            )
                .filter((cellId) => allIds.has(cellId));
        }

        function getPunctaSourceContourCardFilterLabel(fileData) {
            const filterValue = getEffectivePunctaSourceContourCountFilter(fileData);
            const parts = [];
            const cellTypeFilter = getCurrentCellTypeFilter();
            if (cellTypeFilter !== 'all') {
                parts.push(getCellTypeFilterLabel(cellTypeFilter));
            }
            if (filterValue !== 'all') {
                const context = getPunctaSourceContourContext(fileData?.Statistics || {});
                const countLabel = filterValue === 'exactly_1'
                    ? 'Exactly 1'
                    : 'Exactly 2';
                const sourceLabel = context.channelLabel
                    ? `${context.channelLabel.toLowerCase()} source contour${filterValue === 'exactly_1' ? '' : 's'}`
                    : `source contour${filterValue === 'exactly_1' ? '' : 's'}`;
                parts.push(`${countLabel} ${sourceLabel}`);
            }
            return parts.join(' / ');
        }

        function syncPunctaSourceContourCellCardState(fileData) {
            const badge = document.getElementById('punctaSourceContourCellFilterBadge');
            const filterValue = getEffectivePunctaSourceContourCountFilter(fileData);
            if (badge) {
                const label = getPunctaSourceContourCardFilterLabel(fileData);
                badge.replaceChildren();
                const prefix = document.createElement('span');
                prefix.className = 'cell-card-filter-label';
                prefix.textContent = 'Filtered view';
                const separator = document.createElement('span');
                separator.className = 'cell-card-filter-separator';
                separator.setAttribute('aria-hidden', 'true');
                separator.textContent = '\u00b7';
                const value = document.createElement('span');
                value.className = 'cell-card-filter-value';
                value.textContent = label || getCellTypeFilterLabel('all');
                badge.append(prefix, separator, value);
                badge.hidden = false;
            }

            const message = document.getElementById('punctaSourceContourActiveCellMessage');
            if (!message) return;
            const cellTypeFilter = getCurrentCellTypeFilter();
            if (filterValue === 'all' && cellTypeFilter === 'all') {
                message.hidden = true;
                message.textContent = '';
                return;
            }
            const activeIds = getActiveCellNavigationIds(fileData);
            if (activeIds.length === 0) {
                message.hidden = true;
                message.textContent = '';
                return;
            }
            const row = fileData?.Statistics?.[String(currentCellNumber)] || null;
            if (
                row
                && (
                    !matchesCellTypeFilter(row, cellTypeFilter)
                    || !matchesPunctaSourceContourCountFilter(row, filterValue)
                )
            ) {
                message.textContent = 'Current cell is outside the active row filters.';
                message.hidden = false;
            } else {
                message.hidden = true;
                message.textContent = '';
            }
        }

        function syncCellNavigationState(fileData = filesData[fileUUIDs[currentFileIndex]] || null) {
            const activeIds = getActiveCellNavigationIds(fileData);
            const disableNavigation = fileSwapLoading || activeIds.length === 0;
            [
                document.getElementById('previousCellBtn'),
                document.getElementById('nextCellBtn'),
            ].forEach((button) => {
                if (!button) return;
                button.disabled = disableNavigation;
                button.setAttribute('aria-disabled', disableNavigation ? 'true' : 'false');
                button.title = disableNavigation
                    ? 'No cells match the current table filters.'
                    : '';
            });
        }

        function alignCurrentCellNumberToActiveFilter(fileData, { anchorCellId = currentCellNumber } = {}) {
            const allIds = getSortedCellIds(fileData);
            const activeIds = getActiveCellNavigationIds(fileData);
            if (allIds.length === 0) {
                currentCellNumber = 0;
                return { changed: true, activeIds };
            }
            if (activeIds.length === 0) {
                return { changed: false, activeIds };
            }
            if (activeIds.includes(Number(currentCellNumber))) {
                return { changed: false, activeIds };
            }
            const nearestCellId = findNearestMatchingCellByOriginalOrder(
                anchorCellId,
                allIds,
                activeIds,
            );
            if (!nearestCellId) {
                return { changed: false, activeIds };
            }
            const changed = Number(currentCellNumber) !== nearestCellId;
            currentCellNumber = nearestCellId;
            return { changed, activeIds };
        }

        async function syncCurrentCellToActiveContourFilter(fileData, options = {}) {
            if (!fileData) return null;
            const previousCellNumber = Number(currentCellNumber);
            const { changed, activeIds } = alignCurrentCellNumberToActiveFilter(fileData, {
                anchorCellId: options.anchorCellId ?? previousCellNumber,
            });
            syncCellNavigationState(fileData);
            if (activeIds.length === 0) {
                const allIds = getSortedCellIds(fileData);
                if (!allIds.includes(Number(currentCellNumber))) {
                    const fallbackCellId = findNearestMatchingCellByOriginalOrder(
                        options.anchorCellId ?? previousCellNumber,
                        allIds,
                        allIds,
                    );
                    currentCellNumber = fallbackCellId || 0;
                    await updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                        blendImages: options.blendImages !== false,
                        blendText: options.blendText !== false,
                        forceShowContours: getContourToggleState(),
                        imageLoading: options.imageLoading === true,
                    });
                }
                syncPunctaSourceContourCellCardState(fileData);
                return null;
            }
            if (changed || options.forceRender) {
                const showContours = getContourToggleState();
                await updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                    blendImages: options.blendImages !== false,
                    blendText: options.blendText !== false,
                    forceShowContours: showContours,
                    imageLoading: options.imageLoading === true,
                });
                if (showContours) {
                    const fileUUID = fileUUIDs[currentFileIndex];
                    markCurrentCellWarm(fileUUID, true);
                    scheduleCircularOverlayWarmup(options.warmDirection || 'initial');
                }
            } else {
                syncPunctaSourceContourCellCardState(fileData);
            }
            return currentCellNumber;
        }

        function reconcileRowFilterState(fileData) {
            let cellTypeState = getCellTypeFilterUiState(
                fileData?.Statistics || {},
                currentCellTypeFilter,
            );
            if (cellTypeState.resetRequestedFilter) {
                currentCellTypeFilter = cellTypeState.effectiveFilter;
                cellTypeState = getCellTypeFilterUiState(
                    fileData?.Statistics || {},
                    currentCellTypeFilter,
                );
            }
            const punctaSourceContourState = getPunctaSourceContourFilterUiState(
                fileData?.Statistics || {},
                currentPunctaSourceContourCountFilter,
            );
            return { cellTypeState, punctaSourceContourState };
        }

        function updateTableState(fileUUID, fileData) {
            const exportButtons = document.getElementById('exportButtons');
            let note = document.getElementById('table-empty-note');
            if (!note) {
                note = document.createElement('div');
                note.id = 'table-empty-note';
                note.className = 'message info';
                note.style.marginTop = '10px';
                const tableSection = document.querySelector('.table-section');
                if (tableSection) {
                    tableSection.insertBefore(note, exportButtons || null);
                }
            }

            const { cellTypeState, punctaSourceContourState } = reconcileRowFilterState(fileData);
            const filterValue = punctaSourceContourState.effectiveFilter;
            const renderedRowCount = renderStatisticsTable(
                fileData.Statistics || {},
                fileData,
                {
                    cellTypeFilter: cellTypeState.effectiveFilter,
                    punctaSourceContourCountFilter: filterValue,
                    activeCellId: currentCellNumber,
                },
            );
            syncCellTypeFilterControl(fileData);
            syncPunctaSourceContourFilterControl(fileData);
            const emptyMessage = getRowFilterEmptyMessage(
                fileData.Statistics || {},
                renderedRowCount,
                { cellTypeState, punctaSourceContourState },
            );

            if (emptyMessage) {
                note.textContent = emptyMessage;
                note.style.display = 'block';
            } else if (fileData.NoCellsWarning) {
                note.textContent = fileData.NoCellsWarning;
                note.style.display = 'block';
            } else {
                note.style.display = 'none';
            }

            syncPunctaSourceContourFilterStatus(fileData, renderedRowCount);
            syncCellNavigationState(fileData);
            syncDashboardExportButtons(fileUUID, fileData, renderedRowCount);
        }

        if (cellTypeFilterButton && cellTypeFilterMenu) {
            cellTypeFilterButton.addEventListener('click', () => {
                if (cellTypeFilterButton.disabled) return;
                const isOpen = cellTypeFilterButton.getAttribute('aria-expanded') === 'true';
                cellTypeFilterMenu.hidden = isOpen;
                cellTypeFilterButton.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
            });
            cellTypeFilterMenu.querySelectorAll('[data-value]').forEach((option) => {
                option.addEventListener('click', async () => {
                    const nextFilter = normalizeCellTypeFilter(option.dataset.value);
                    if (nextFilter === getCurrentCellTypeFilter()) {
                        closeCellTypeFilterMenu();
                        return;
                    }
                    const previousCellNumber = Number(currentCellNumber);
                    setCurrentCellTypeFilter(nextFilter);
                    startPunctaSourceContourFilterApplyVisualState();
                    closeCellTypeFilterMenu();
                    try {
                        await waitForPunctaSourceContourFilterApplyFeedback();
                        const fileUUID = fileUUIDs[currentFileIndex];
                        const fileData = fileUUID ? filesData[fileUUID] : null;
                        if (fileUUID && fileData) {
                            await cellDataRegionLoadingController.run(async () => {
                                await syncCurrentCellToActiveContourFilter(fileData, {
                                    anchorCellId: previousCellNumber,
                                    blendImages: true,
                                    blendText: true,
                                    imageLoading: true,
                                });
                                updateTableState(fileUUID, fileData);
                            });
                        } else {
                            syncPunctaSourceContourFilterStatus({ Statistics: {} }, 0);
                        }
                    } catch (error) {
                        setPunctaSourceContourFilterApplying(false);
                        throw error;
                    } finally {
                        clearPunctaSourceContourFilterApplyVisualState();
                    }
                });
            });
        }

        if (punctaSourceContourFilterButton && punctaSourceContourFilterMenu) {
            punctaSourceContourFilterButton.addEventListener('click', () => {
                if (punctaSourceContourFilterButton.disabled) return;
                const isOpen = punctaSourceContourFilterButton.getAttribute('aria-expanded') === 'true';
                punctaSourceContourFilterMenu.hidden = isOpen;
                punctaSourceContourFilterButton.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
            });
            punctaSourceContourFilterMenu.querySelectorAll('[data-value]').forEach((option) => {
                option.addEventListener('click', async () => {
                    const initialFileUUID = fileUUIDs[currentFileIndex];
                    const initialFileData = initialFileUUID ? filesData[initialFileUUID] : null;
                    const nextFilter = normalizePunctaSourceContourCountFilter(option.dataset.value);
                    if (nextFilter === getEffectivePunctaSourceContourCountFilter(initialFileData)) {
                        closePunctaSourceContourFilterMenu();
                        return;
                    }
                    const previousCellNumber = Number(currentCellNumber);
                    setCurrentPunctaSourceContourCountFilter(nextFilter);
                    startPunctaSourceContourFilterApplyVisualState();
                    closePunctaSourceContourFilterMenu();
                    try {
                        await waitForPunctaSourceContourFilterApplyFeedback();
                        const fileUUID = fileUUIDs[currentFileIndex];
                        const fileData = fileUUID ? filesData[fileUUID] : null;
                        if (fileUUID && fileData) {
                            await cellDataRegionLoadingController.run(async () => {
                                await syncCurrentCellToActiveContourFilter(fileData, {
                                    anchorCellId: previousCellNumber,
                                    blendImages: true,
                                    blendText: true,
                                    imageLoading: true,
                                });
                                updateTableState(fileUUID, fileData);
                            });
                        } else {
                            syncPunctaSourceContourFilterStatus({ Statistics: {} }, 0);
                        }
                    } catch (error) {
                        setPunctaSourceContourFilterApplying(false);
                        throw error;
                    } finally {
                        clearPunctaSourceContourFilterApplyVisualState();
                    }
                });
            });
            document.addEventListener('click', (event) => {
                if (
                    (punctaSourceContourFilterControl && punctaSourceContourFilterControl.contains(event.target))
                    || (cellTypeFilterControl && cellTypeFilterControl.contains(event.target))
                ) {
                    return;
                }
                closePunctaSourceContourFilterMenu();
                closeCellTypeFilterMenu();
            });
        }

        const statisticsTable = document.getElementById('celltable');
        if (statisticsTable) {
            statisticsTable.addEventListener('click', async (event) => {
                if (event.target.closest('button, a, input, label, [role="button"]')) {
                    return;
                }
                const row = event.target.closest('tbody tr[data-cell-id]');
                if (!row || !statisticsTable.contains(row)) {
                    return;
                }
                const cellId = Number(row.dataset.cellId);
                if (!Number.isFinite(cellId) || cellId <= 0) {
                    return;
                }
                const fileUUID = fileUUIDs[currentFileIndex];
                const fileData = fileUUID ? filesData[fileUUID] : null;
                if (!fileData || !getActiveCellNavigationIds(fileData).includes(cellId)) {
                    return;
                }
                currentCellNumber = cellId;
                await updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                    blendImages: true,
                    blendText: true,
                    forceShowContours: getContourToggleState(),
                });
                updateTableState(fileUUID, fileData);
            });
        }

        function rerenderSpatialUnitsForCurrentFile() {
            const fileUUID = fileUUIDs[currentFileIndex];
            const fileData = filesData[fileUUID];
            if (!fileUUID || !fileData) {
                return;
            }
            updateSpatialUnitControls(fileData);
            const nextState = getCellDisplayState(fileData.CellPairImages, fileData.Statistics, {
                showContours: getContourToggleState(),
                cellNumber: currentCellNumber,
            });
            renderCellDisplayState(nextState, { blendImages: false, blendText: false });
            updateTableState(fileUUID, fileData);
            if (dashboardExportSelectionController && dashboardExportSelectionController.refreshStatLabels) {
                dashboardExportSelectionController.refreshStatLabels();
            }
        }

        async function persistSidebarSpatialUnit(unit) {
            const response = await fetch('/dashboard/preferences/channels/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || '',
                },
                credentials: 'same-origin',
                body: JSON.stringify({ sidebar_spatial_stats_unit: normalizeSpatialUnit(unit) }),
            });
            if (!response.ok) {
                throw new Error('Unable to save spatial unit preference.');
            }
            const payload = await response.json();
            return normalizeSpatialUnit(payload.sidebar_spatial_stats_unit || unit);
        }

        bindSpatialUnitControls({
            getCurrentFileData: () => filesData[fileUUIDs[currentFileIndex]] || null,
            rerender: rerenderSpatialUnitsForCurrentFile,
            persistSpatialUnit: persistSidebarSpatialUnit,
            onError: () => {
                showMessage('Unable to save spatial unit preference right now.');
            },
        });

        function getCurrentCellImageUrls() {
            const fileData = filesData[fileUUIDs[currentFileIndex]];
            if (!fileData) {
                return null;
            }
            const pairImages = fileData.CellPairImages || {};
            return pairImages[currentCellNumber] || pairImages[String(currentCellNumber)] || null;
        }

        function hasMultipleFiles() {
            return fileUUIDs.length > 1;
        }

        function syncFileNavigationState() {
            const disableNavigation = !hasMultipleFiles() || fileSwapLoading;
            const buttons = [
                document.getElementById('previousFileBtn'),
                document.getElementById('nextFileBtn'),
            ];
            buttons.forEach((button) => {
                if (!button) {
                    return;
                }
                button.disabled = disableNavigation;
                button.setAttribute('aria-disabled', disableNavigation ? 'true' : 'false');
            });
            syncCellNavigationState();
        }

        function applyContourToggleState(forceShowContours = null) {
            const toggleElement = document.getElementById('toggleContours');
            const showContours = forceShowContours === null
                ? !!(toggleElement && toggleElement.checked)
                : !!forceShowContours;
            syncContourStateLabel(showContours);
            const imageUrls = getCurrentCellImageUrls();
            if (!imageUrls) {
                return;
            }
            if (showContours) {
                document.getElementById("cellImage1").src = imageUrls[0] || noCellPlaceholder;
                document.getElementById("cellImage2").src = imageUrls[2] || noCellPlaceholder;
                document.getElementById("cellImage3").src = imageUrls[4] || noCellPlaceholder;
                document.getElementById("cellImage4").src = imageUrls[6] || noCellPlaceholder;
            } else {
                document.getElementById("cellImage1").src = imageUrls[1] || noCellPlaceholder;
                document.getElementById("cellImage2").src = imageUrls[3] || noCellPlaceholder;
                document.getElementById("cellImage3").src = imageUrls[5] || noCellPlaceholder;
                document.getElementById("cellImage4").src = imageUrls[7] || noCellPlaceholder;
            }
        }

        function rerenderCurrentCellCard() {
            const fileData = filesData[fileUUIDs[currentFileIndex]];
            if (!fileData) {
                return Promise.resolve(false);
            }
            const state = getCellDisplayState(fileData.CellPairImages, fileData.Statistics, {
                showContours: getContourToggleState(),
                cellNumber: currentCellNumber,
            });
            return renderCellDisplayState(state, {
                blendImages: false,
                blendText: hasInitializedDashboardFile,
            });
        }

        window.onload = async function () {
            bindContourIntensityDisplayControls({
                getCurrentType: () => currentContourIntensityDisplayType,
                setCurrentType: (type) => {
                    currentContourIntensityDisplayType = type;
                },
                rerender: () => {
                    void rerenderCurrentCellCard();
                },
            });
            if (filesDataParseError) {
                showChannelError('Saved file preview data could not be loaded. Refresh and try again.');
                return;
            }
            if (dashboardHasFiles && fileUUIDs.length === 0) {
                showChannelError('Saved files were found, but preview payload is unavailable.');
                return;
            }
            if (fileUUIDs.length > 0) {
                syncFileNavigationState();
                toggleContourOverlays();
                await loadFile(currentFileIndex);
            }
        };

        async function loadFile(fileIndex) {
            const normalizedIndex = Number(fileIndex);
            if (Number.isNaN(normalizedIndex) || normalizedIndex < 0 || normalizedIndex >= fileUUIDs.length) {
                return false;
            }

            const fileUUID = fileUUIDs[normalizedIndex];
            const fileData = filesData[fileUUID];
            if (!fileData) {
                return false;
            }

            const requestToken = ++activeFileLoadToken;
            ++activeChannelRequest;
            currentFileIndex = normalizedIndex;
            maxCells = Number(fileData.NumberOfCells || 0);
            if (!Number.isFinite(maxCells) || maxCells < 0) {
                maxCells = 0;
            }
            const initialSortedIds = getSortedCellIds(fileData);
            currentCellNumber = initialSortedIds.length > 0 ? initialSortedIds[0] : 1;
            alignCurrentCellNumberToActiveFilter(fileData, {
                anchorCellId: currentCellNumber,
            });

            const defaultMainImagePath = fileData.MainImagePath || noCellPlaceholder;
            const inferredDefaultChannel = primeMainImageWarmState(fileUUID, fileData, defaultMainImagePath);
            const preferredChannel = getPreferredMainImageChannel();
            const preferredMainImagePath = preferredChannel
                ? (getMainImagePaths(fileData)[preferredChannel] || '')
                : '';
            const mainImagePath = preferredMainImagePath || defaultMainImagePath;
            const activeMainChannel = preferredMainImagePath
                ? preferredChannel
                : inferredDefaultChannel;
            if (activeMainChannel && activeMainChannel !== inferredDefaultChannel) {
                markMainImageChannelWarm(fileUUID, fileData, activeMainChannel, mainImagePath);
            }
            const showContours = getContourToggleState();
            syncContourStateLabel(showContours);
            const initialCellState = getCellDisplayState(fileData.CellPairImages, fileData.Statistics, {
                showContours,
                cellNumber: currentCellNumber,
            });
            const shouldShowSkeleton = hasInitializedDashboardFile;

            if (shouldShowSkeleton) {
                setFileSwapLoading(true, requestToken);
            }

            try {
                if (hasInitializedDashboardFile) {
                    await Promise.all([
                        preloadImage(mainImagePath),
                        preloadImageSet(initialCellState.visibleImageUrls),
                    ]);
                    if (requestToken !== activeFileLoadToken) {
                        return false;
                    }
                }

                await Promise.all([
                    setImageWithBlend(document.getElementById('mainImage'), mainImagePath, {
                        duration: FILE_BLEND_IMAGE_MS,
                        blend: hasInitializedDashboardFile,
                    }),
                    setTextWithBlend(document.getElementById('imageTitle'), fileData.Image_Name || '', {
                        duration: FILE_BLEND_TEXT_MS,
                        blend: hasInitializedDashboardFile,
                    }),
                    updateFileContextSummary(fileUUID, fileData, { blend: hasInitializedDashboardFile }),
                    updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                        blendImages: hasInitializedDashboardFile,
                        blendText: hasInitializedDashboardFile,
                        forceShowContours: showContours,
                        preload: false,
                        fileToken: requestToken,
                    }),
                ]);

                if (requestToken !== activeFileLoadToken) {
                    return false;
                }

                fileData.MainImagePath = mainImagePath;
                if (fileData.NoCellsWarning) {
                    showChannelError(fileData.NoCellsWarning);
                }
                updateTableState(fileUUID, fileData);
                updateSidebarActive();
                syncFileNavigationState();

                if (activeMainChannel) {
                    setActiveChannel(activeMainChannel);
                } else if (inferredDefaultChannel) {
                    setActiveChannel(inferredDefaultChannel);
                }
                scheduleMainImageWarmup(fileUUID, fileData, activeMainChannel || inferredDefaultChannel);
                if (showContours) {
                    markCurrentCellWarm(fileUUID, true);
                    scheduleCircularOverlayWarmup('initial');
                }

                hasInitializedDashboardFile = true;
                return true;
            } finally {
                if (shouldShowSkeleton) {
                    setFileSwapLoading(false, requestToken);
                }
            }
        }

        function updateFileContextSummary(fileUUID, fileData, { blend = false } = {}) {
            const metaLine = document.getElementById('fileContextMetaLine');
            const scaleLine = document.getElementById('fileContextScaleLine');
            if (!metaLine || !scaleLine) {
                return Promise.resolve();
            }

            const fileItem = Array.from(document.querySelectorAll('.file-item')).find(
                (item) => item.dataset.uuid === fileUUID
            );
            const metaText = fileItem?.querySelector('.file-meta')?.textContent?.trim() || '';
            const scaleValue = fileItem?.querySelector('.file-scale-line span:first-child')?.textContent?.trim() || '';
            const scaleSource = fileItem?.querySelector('.file-scale-source')?.textContent?.trim() || '';
            const cellsFallback = Number(fileData?.NumberOfCells || 0);
            const nextMetaText = metaText || `${cellsFallback} cells`;
            const nextScaleText = (scaleValue || scaleSource)
                ? (scaleSource ? `${scaleValue} · ${scaleSource}` : scaleValue)
                : 'Scale metadata unavailable.';

            return Promise.all([
                setTextWithBlend(metaLine, nextMetaText, { blend }),
                setTextWithBlend(scaleLine, nextScaleText, { blend }),
            ]);
        }











        async function switchMainChannel(channel, { persistPreference = true } = {}) {
            const mainImage = document.getElementById('mainImage');
            if (!mainImage) return;
            const normalizedChannel = normalizeMainImageChannel(channel);
            if (!normalizedChannel) return;
            const fileUUID = fileUUIDs[currentFileIndex];
            const fileData = fileUUID ? filesData[fileUUID] : null;
            if (!fileUUID || !fileData) return;
            const requestId = ++activeChannelRequest;
            const fileLoadTokenAtRequest = activeFileLoadToken;
            try {
                const imageUrl = await warmMainImageChannel(fileUUID, fileData, normalizedChannel);
                if (!imageUrl) {
                    throw new Error('Missing image URL');
                }
                if (
                    requestId !== activeChannelRequest
                    || fileLoadTokenAtRequest !== activeFileLoadToken
                    || fileUUID !== fileUUIDs[currentFileIndex]
                ) {
                    return;
                }
                await setImageWithBlend(mainImage, imageUrl, {
                    duration: FILE_BLEND_IMAGE_MS,
                    blend: hasInitializedDashboardFile,
                });
                if (
                    requestId !== activeChannelRequest
                    || fileLoadTokenAtRequest !== activeFileLoadToken
                    || fileUUID !== fileUUIDs[currentFileIndex]
                ) {
                    return;
                }
                fileData.MainImagePath = imageUrl;
                markMainImageChannelWarm(fileUUID, fileData, normalizedChannel, imageUrl);
                setActiveChannel(normalizedChannel);
                setPreferredMainImageChannel(normalizedChannel);
                if (persistPreference) {
                    void persistPreferredMainImageChannel(normalizedChannel).catch(() => {
                        showChannelPreferenceWarning();
                    });
                }
            } catch (error) {
                if (error && error.name === 'AbortError') return;
                showChannelError('Unable to load that channel image. Please try again.');
            }
        }



        function getCircularWarmQueue(direction = 'initial') {
            const fileData = filesData[fileUUIDs[currentFileIndex]];
            return resultsViewerShared.getCircularWarmQueue({
                sortedIds: getActiveCellNavigationIds(fileData),
                currentCellNumber,
                maxCells,
                direction,
            });
        }

        function markCurrentCellWarm(fileUUID, showContours) {
            if (!showContours || !fileUUID || maxCells < 1) {
                return;
            }
            overlayWarmCoordinator.markCellWarm(fileUUID, currentCellNumber);
        }

        function scheduleCircularOverlayWarmup(direction = 'initial') {
            const fileUUID = fileUUIDs[currentFileIndex];
            if (!fileUUID || !getContourToggleState() || maxCells < 1) {
                return;
            }
            overlayWarmCoordinator.scheduleCells(fileUUID, getCircularWarmQueue(direction));
        }

        async function updateCellImages(cellPairImages, statistics, options = {}) {
            const renderToken = ++activeCellRenderToken;
            const blendImages = !!options.blendImages;
            const blendText = !!options.blendText;
            const showImageLoading = options.imageLoading === true;
            const showContours = getContourToggleState(options.forceShowContours ?? null);
            const state = getCellDisplayState(cellPairImages, statistics, {
                showContours,
                cellNumber: options.cellNumber ?? currentCellNumber,
            });

            if (showImageLoading) {
                setCellPairImagesLoading(true);
            }

            try {
                if (blendImages && options.preload !== false) {
                    await preloadImageSet(state.visibleImageUrls);
                    if (renderToken !== activeCellRenderToken) {
                        return false;
                    }
                    if (options.fileToken && options.fileToken !== activeFileLoadToken) {
                        return false;
                    }
                }

                if (renderToken !== activeCellRenderToken) {
                    return false;
                }
                if (options.fileToken && options.fileToken !== activeFileLoadToken) {
                    return false;
                }

                await renderCellDisplayState(state, { blendImages, blendText });
                syncPunctaSourceContourCellCardState(
                    filesData[fileUUIDs[currentFileIndex]] || { Statistics: statistics || {} }
                );

                if (renderToken !== activeCellRenderToken) {
                    return false;
                }
                if (options.fileToken && options.fileToken !== activeFileLoadToken) {
                    return false;
                }

                return true;
            } finally {
                const shouldClearLoading = (
                    renderToken === activeCellRenderToken
                    && (!options.fileToken || options.fileToken === activeFileLoadToken)
                );
                if (shouldClearLoading) {
                    if (showImageLoading) {
                        setCellPairImagesLoading(false);
                    }
                }
            }
        }

        async function handleContourToggleChange(forceShowContours = null) {
            const showContours = getContourToggleState(forceShowContours);
            syncContourStateLabel(showContours);

            const fileUUID = fileUUIDs[currentFileIndex];
            const fileData = filesData[fileUUID];
            if (!fileData) {
                return;
            }

            await updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                blendImages: hasInitializedDashboardFile,
                blendText: false,
                forceShowContours: showContours,
            });

            if (showContours) {
                markCurrentCellWarm(fileUUID, true);
                scheduleCircularOverlayWarmup('initial');
            }
        }

        async function nextFile() {
            if (!hasMultipleFiles()) {
                syncFileNavigationState();
                return;
            }
            const nextIndex = (currentFileIndex + 1) % fileUUIDs.length;
            await loadFile(nextIndex);
        }

        async function previousFile() {
            if (!hasMultipleFiles()) {
                syncFileNavigationState();
                return;
            }
            const nextIndex = (currentFileIndex - 1 + fileUUIDs.length) % fileUUIDs.length;
            await loadFile(nextIndex);
        }


        async function nextCell() {
            if (maxCells < 1) {
                return;
            }
            const fileUUID = fileUUIDs[currentFileIndex];
            const fileData = filesData[fileUUID];
            if (!fileData) {
                return;
            }
            const activeIds = getActiveCellNavigationIds(fileData);
            if (activeIds.length === 0) {
                syncCellNavigationState(fileData);
                return;
            }
            currentCellNumber = getAdjacentFilteredCellId(currentCellNumber, activeIds, 'next');
            const showContours = getContourToggleState();
            await cellDataRegionLoadingController.run(async () => {
                await updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                    blendImages: true,
                    blendText: true,
                    forceShowContours: showContours,
                    imageLoading: true,
                });
                updateTableState(fileUUID, fileData);
            });
            if (showContours) {
                markCurrentCellWarm(fileUUID, true);
                scheduleCircularOverlayWarmup('next');
            }
        }

        async function previousCell() {
            if (maxCells < 1) {
                return;
            }
            const fileUUID = fileUUIDs[currentFileIndex];
            const fileData = filesData[fileUUID];
            if (!fileData) {
                return;
            }
            const activeIds = getActiveCellNavigationIds(fileData);
            if (activeIds.length === 0) {
                syncCellNavigationState(fileData);
                return;
            }
            currentCellNumber = getAdjacentFilteredCellId(currentCellNumber, activeIds, 'previous');
            const showContours = getContourToggleState();
            await cellDataRegionLoadingController.run(async () => {
                await updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                    blendImages: true,
                    blendText: true,
                    forceShowContours: showContours,
                    imageLoading: true,
                });
                updateTableState(fileUUID, fileData);
            });
            if (showContours) {
                markCurrentCellWarm(fileUUID, true);
                scheduleCircularOverlayWarmup('previous');
            }
        }

        let contourToggleBound = false;
        function toggleContourOverlays() {
            const toggleElement = document.getElementById('toggleContours');
            if (!toggleElement) {
                return;
            }
            syncContourStateLabel(toggleElement.checked);
            if (contourToggleBound) {
                return;
            }
            contourToggleBound = true;
            toggleElement.addEventListener('change', function () {
                void handleContourToggleChange(this.checked);
            });
        }

        // Sidebar elements
        const sidebar = document.getElementById('sidebar');
        const toggleBtn = document.getElementById('toggleSidebarBtn');
        const fileItems = document.querySelectorAll('.file-item[data-index]');
        const mainChannelButtons = document.querySelectorAll('.main-channel-btn[data-main-channel]');

        // Highlight active
        function updateSidebarActive() {
            fileItems.forEach(i => i.classList.remove('active'));
            const active = document.querySelector(`.file-item[data-index="${currentFileIndex}"]`);
            if (active) active.classList.add('active');
        }
        updateSidebarActive();

        // Click file
        fileItems.forEach(item => {
            item.addEventListener('click', (event) => {
                if (sidebar.classList.contains('select-mode')) {
                    return;
                }
                const idx = parseInt(item.dataset.index, 10);
                loadFile(idx);
            });
        });

        const previousFileBtn = document.getElementById('previousFileBtn');
        const nextFileBtn = document.getElementById('nextFileBtn');
        const previousCellBtn = document.getElementById('previousCellBtn');
        const nextCellBtn = document.getElementById('nextCellBtn');
        if (previousFileBtn) previousFileBtn.addEventListener('click', previousFile);
        if (nextFileBtn) nextFileBtn.addEventListener('click', nextFile);
        if (previousCellBtn) previousCellBtn.addEventListener('click', previousCell);
        if (nextCellBtn) nextCellBtn.addEventListener('click', nextCell);

        // Toggle sidebar
        const setSidebarCollapsed = (collapsed) => {
            const isCollapsed = sidebar.classList.contains('collapsed');
            if (collapsed === isCollapsed) {
                return;
            }
            if (collapsed) {
                sidebar.classList.remove('is-expanding');
                sidebar.classList.add('collapsed');
                return;
            }
            sidebar.classList.add('is-expanding');
            sidebar.classList.remove('collapsed');
        };
        toggleBtn.addEventListener('click', e => {
            e.stopPropagation();
            setSidebarCollapsed(!sidebar.classList.contains('collapsed'));
        });

        // ALSO expand when collapsed sidebar area is clicked
        sidebar.addEventListener('click', e => {
            if (sidebar.classList.contains('collapsed')) {
                setSidebarCollapsed(false);
            }
        });

        // Main channel switching (async, no page reload)
        mainChannelButtons.forEach((btn) => {
            btn.addEventListener('click', (event) => {
                event.preventDefault();
                const channel = btn.dataset.mainChannel;
                if (!channel) return;
                switchMainChannel(channel);
            });
        });

        const statsTablePanel = document.getElementById('statsTablePanel');
        const tableFullscreenBtn = document.getElementById('tableFullscreenBtn');
        let wasTableFullscreen = false;

        function playTableExitFade() {
            if (!statsTablePanel) return;
            statsTablePanel.classList.remove('fullscreen-exit-anim');
            // force reflow so rapid re-entry replays animation
            void statsTablePanel.offsetWidth;
            statsTablePanel.classList.add('fullscreen-exit-anim');
            window.setTimeout(() => {
                if (statsTablePanel) {
                    statsTablePanel.classList.remove('fullscreen-exit-anim');
                }
            }, 320);
        }

        function syncTableFullscreenState() {
            if (!tableFullscreenBtn || !statsTablePanel) return;
            const active = document.fullscreenElement === statsTablePanel;
            if (!active && wasTableFullscreen) {
                playTableExitFade();
            }
            const fullscreenLabel = tableFullscreenBtn.querySelector('.fullscreen-label');
            if (fullscreenLabel) {
                fullscreenLabel.textContent = active ? 'Exit Fullscreen' : 'Fullscreen';
            } else {
                tableFullscreenBtn.textContent = active ? 'Exit Fullscreen' : 'Fullscreen';
            }
            tableFullscreenBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
            wasTableFullscreen = active;
        }

        async function toggleTableFullscreen() {
            if (!statsTablePanel) return;
            if (document.fullscreenElement === statsTablePanel) {
                await document.exitFullscreen();
            } else {
                await statsTablePanel.requestFullscreen();
            }
        }

        if (tableFullscreenBtn && statsTablePanel) {
            tableFullscreenBtn.addEventListener('click', async () => {
                try {
                    await toggleTableFullscreen();
                } catch (err) {
                    showChannelError('Fullscreen is not available in this browser context.');
                }
            });
            document.addEventListener('fullscreenchange', syncTableFullscreenState);
            syncTableFullscreenState();
        }
