        const resultsViewerShared = window.CytoCVResultsViewerShared;
        const { readJsonConfig } = resultsViewerShared;

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
            'red_intensity_1',
            'red_intensity_2',
            'red_intensity_3',
            'green_intensity_1',
            'green_intensity_2',
            'green_intensity_3',
            'red_in_green_intensity_1',
            'red_in_green_intensity_2',
            'red_in_green_intensity_3',
            'green_in_green_intensity_1',
            'green_in_green_intensity_2',
            'green_in_green_intensity_3',
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
                'red_intensity_1',
                'red_intensity_2',
                'red_intensity_3',
                'green_intensity_1',
                'green_intensity_2',
                'green_intensity_3',
                'red_in_green_intensity_1',
                'red_in_green_intensity_2',
                'red_in_green_intensity_3',
                'green_in_green_intensity_1',
                'green_in_green_intensity_2',
                'green_in_green_intensity_3',
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
        const {
            applyMetricVisibility,
            normalizeSpatialUnit,
            getCurrentSpatialUnit,
            setCurrentSpatialUnit,
            getScaleContext,
            formatSpatialLabel,
            formatFieldValue,
            formatStatValue,
            hasNoNucleusContour,
            getNuclearLabelPair,
            renderStatisticsTable,
            hasStatisticsTableRows,
            updateSpatialUnitControls,
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
            const spatialUnit = getCurrentSpatialUnit();
            const category = cellStats ? (cellStats.category_cen_dot_label || 'N/A') : 'N/A';
            const cellParentage = cellStats ? (cellStats.cell_parentage_label || 'Not identified') : 'N/A';
            const nuclearUnavailable = hasNoNucleusContour(cellStats);
            const mode = cellStats ? cellStats.nuclear_cell_pair_mode : null;
            const labels = getNuclearLabelPair(mode);
            const distanceLabel = cellStats ? (cellStats.puncta_distance_label || 'Distance Between Red Puncta') : 'Distance Between Red Puncta';
            const lineIntensityLabel = cellStats ? (cellStats.puncta_line_intensity_label || 'Green Intensity Over Red Line') : 'Green Intensity Over Red Line';
            const statVisibility = getStatVisibility(cellStats);

            return {
                visibleImageUrls,
                cellId: (imageUrls || cellStats) ? cellNumber : 0,
                statVisibility,
                metricValues: {
                    distance: formatFieldValue('puncta_distance', cellStats ? cellStats.puncta_distance : null, cellStats, scaleContext),
                    punctaLineIntensity: formatStatValue(cellStats ? cellStats.puncta_line_intensity : null),
                    measurementContourRatioFormula: cellStats ? (cellStats.measurement_contour_ratio_display_text || 'N/A') : 'N/A',
                    measurementContourRatio1: formatStatValue(cellStats ? cellStats.measurement_contour_ratio_1 : null),
                    measurementContourRatio2: formatStatValue(cellStats ? cellStats.measurement_contour_ratio_2 : null),
                    measurementContourRatio3: formatStatValue(cellStats ? cellStats.measurement_contour_ratio_3 : null),
                    redInRedIntensity1: formatStatValue(cellStats ? cellStats.red_intensity_1 : null),
                    redInRedIntensity2: formatStatValue(cellStats ? cellStats.red_intensity_2 : null),
                    redInRedIntensity3: formatStatValue(cellStats ? cellStats.red_intensity_3 : null),
                    greenInRedIntensity1: formatStatValue(cellStats ? cellStats.green_intensity_1 : null),
                    greenInRedIntensity2: formatStatValue(cellStats ? cellStats.green_intensity_2 : null),
                    greenInRedIntensity3: formatStatValue(cellStats ? cellStats.green_intensity_3 : null),
                    redInGreenIntensity1: formatStatValue(cellStats ? cellStats.red_in_green_intensity_1 : null),
                    redInGreenIntensity2: formatStatValue(cellStats ? cellStats.red_in_green_intensity_2 : null),
                    redInGreenIntensity3: formatStatValue(cellStats ? cellStats.red_in_green_intensity_3 : null),
                    greenInGreenIntensity1: formatStatValue(cellStats ? cellStats.green_in_green_intensity_1 : null),
                    greenInGreenIntensity2: formatStatValue(cellStats ? cellStats.green_in_green_intensity_2 : null),
                    greenInGreenIntensity3: formatStatValue(cellStats ? cellStats.green_in_green_intensity_3 : null),
                    nucleusIntensitySum: (!cellStats || nuclearUnavailable) ? 'N/A' : formatStatValue(cellStats.nucleus_intensity_sum),
                    cellPairIntensitySum: (!cellStats || nuclearUnavailable) ? 'N/A' : formatStatValue(cellStats.cell_pair_intensity_sum),
                    cytoplasmicIntensity: (!cellStats || nuclearUnavailable) ? 'N/A' : formatStatValue(cellStats.cytoplasmic_intensity),
                    nuclearCytoplasmicRatio: (!cellStats || nuclearUnavailable) ? 'N/A' : formatStatValue(cellStats.nuclear_cytoplasmic_ratio),
                    cellParentage,
                    cenDot: category,
                    colinearDots: formatStatValue(cellStats ? cellStats.colinear_dots : null),
                    offAxisDots: formatStatValue(cellStats ? cellStats.off_axis_dots : null),
                    nucleusContourChannel: cellStats ? (cellStats.nuclear_cell_pair_contour_channel || labels.contour) : labels.contour,
                    measurementChannel: cellStats ? (cellStats.nuclear_cell_pair_measurement_channel || labels.measurement) : labels.measurement,
                    nuclearStatus: cellStats ? (cellStats.nuclear_cell_pair_status || 'unknown') : 'N/A',
                },
                labels: {
                    distanceLabel: formatSpatialLabel(distanceLabel, 'puncta_distance', spatialUnit),
                    lineIntensityLabel,
                    nucleusIntensityLabel: labels.nuclear,
                    cellularIntensityLabel: labels.cellular,
                },
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
            applyMetricVisibility(state.statVisibility || defaultStatVisibility());

            const imageIds = ['cellImage1', 'cellImage2', 'cellImage3', 'cellImage4'];
            const imageUpdates = imageIds.map((id, index) =>
                setImageWithBlend(document.getElementById(id), state.visibleImageUrls[index], {
                    duration: FILE_BLEND_IMAGE_MS,
                    blend: blendImages,
                })
            );

            const textUpdates = [
                setTextWithBlend(document.getElementById('cellID'), state.cellId, { blend: blendText }),
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
            });
            if (Array.isArray(selectedColumns) && selectedColumns.length > 0) {
                params.set('_columns', selectedColumns.join(','));
            }
            return `/dashboard/?${params.toString()}`;
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
                }),
            });
            window.dashboardExportSelectionController = dashboardExportSelectionController;
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

            const renderedRowCount = renderStatisticsTable(fileData.Statistics || {}, fileData);

            if (fileData.NoCellsWarning) {
                note.textContent = fileData.NoCellsWarning;
                note.style.display = 'block';
            } else {
                note.style.display = 'none';
            }

            syncDashboardExportButtons(fileUUID, fileData, renderedRowCount);
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

        const sidebarSpatialUnitToggle = document.getElementById('sidebarSpatialUnitToggle');
        if (sidebarSpatialUnitToggle) {
            sidebarSpatialUnitToggle.querySelectorAll('[data-spatial-unit]').forEach((button) => {
                button.addEventListener('click', async () => {
                    const nextUnit = normalizeSpatialUnit(button.dataset.spatialUnit || 'px');
                    if (nextUnit === getCurrentSpatialUnit()) {
                        return;
                    }
                    const previousUnit = getCurrentSpatialUnit();
                    setCurrentSpatialUnit(nextUnit);
                    updateSpatialUnitControls(filesData[fileUUIDs[currentFileIndex]] || null);
                    rerenderSpatialUnitsForCurrentFile();
                    try {
                        const persistedUnit = await persistSidebarSpatialUnit(nextUnit);
                        setCurrentSpatialUnit(persistedUnit);
                        updateSpatialUnitControls(filesData[fileUUIDs[currentFileIndex]] || null);
                        rerenderSpatialUnitsForCurrentFile();
                    } catch (error) {
                        setCurrentSpatialUnit(previousUnit);
                        updateSpatialUnitControls(filesData[fileUUIDs[currentFileIndex]] || null);
                        rerenderSpatialUnitsForCurrentFile();
                        showMessage('Unable to save spatial unit preference right now.');
                    }
                });
            });
        }

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

        window.onload = async function () {
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
            return resultsViewerShared.getCircularWarmQueue({
                sortedIds: getSortedCellIds(filesData[fileUUIDs[currentFileIndex]]),
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
            const showContours = getContourToggleState(options.forceShowContours ?? null);
            const state = getCellDisplayState(cellPairImages, statistics, {
                showContours,
                cellNumber: options.cellNumber ?? currentCellNumber,
            });

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

            if (renderToken !== activeCellRenderToken) {
                return false;
            }
            if (options.fileToken && options.fileToken !== activeFileLoadToken) {
                return false;
            }

            return true;
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
            const sortedIds = getSortedCellIds(fileData);
            if (sortedIds.length === 0) {
                return;
            }
            const currentIdx = sortedIds.indexOf(Number(currentCellNumber));
            const nextIdx = currentIdx === -1 ? 0 : (currentIdx + 1) % sortedIds.length;
            currentCellNumber = sortedIds[nextIdx];
            const showContours = getContourToggleState();
            await updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                blendImages: true,
                blendText: true,
                forceShowContours: showContours,
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
            const sortedIds = getSortedCellIds(fileData);
            if (sortedIds.length === 0) {
                return;
            }
            const currentIdx = sortedIds.indexOf(Number(currentCellNumber));
            const prevIdx = currentIdx === -1
                ? sortedIds.length - 1
                : (currentIdx - 1 + sortedIds.length) % sortedIds.length;
            currentCellNumber = sortedIds[prevIdx];
            const showContours = getContourToggleState();
            await updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                blendImages: true,
                blendText: true,
                forceShowContours: showContours,
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
