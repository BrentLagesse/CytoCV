        const resultsViewerShared = window.CytoCVResultsViewerShared;
        const { readJsonConfig } = resultsViewerShared;
        const { bindContourIntensityDisplayControls } = resultsViewerShared;

        const displayPageConfig = readJsonConfig('displayPageConfig');
        window.CytoCVDisplayPageConfig = displayPageConfig;

        // Parse JSON file data
        let filesData = JSON.parse(document.getElementById('displayFilesData').textContent || '{}');
        let fileUUIDs = Object.keys(filesData);
        let currentFileIndex = 0;
        let currentCellNumber = 1;
        let maxCells;
        const channels = ["dic", "blue", "red", "green"];
        const normalizeMainImageChannel = (channel) => resultsViewerShared.normalizeMainImageChannel(channel, channels);
        const getSortedCellIds = resultsViewerShared.getSortedCellIds;
        const confirmCellDeletion = displayPageConfig.confirmCellDeletion === true;
        const confirmMultiCellDeletion = displayPageConfig.confirmMultiCellDeletion === true;
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
        const defaultSpatialStatsUnit = displayPageConfig.defaultSpatialStatsUnit || 'px';
        const initialSidebarSpatialStatsUnit = displayPageConfig.initialSidebarSpatialStatsUnit || defaultSpatialStatsUnit;
        const initialPreferredMainImageChannel = displayPageConfig.initialPreferredMainImageChannel || '';
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
            getPunctaSourceContourContext,
            matchesPunctaSourceContourCountFilter,
            getPunctaSourceContourCountFilterCounts,
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
            displayPageConfig.initialCellTypeFilter
        );
        let currentPunctaSourceContourCountFilter = normalizePunctaSourceContourCountFilter(
            displayPageConfig.initialPunctaSourceContourCountFilter
        );
        const PUNCTA_SOURCE_FILTER_APPLY_FEEDBACK_MS = 120;
        let punctaSourceContourApplySkeletonTimer = null;
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
        let hasInitializedDisplayFile = false;
        let fileSwapLoading = false;
        const fileSwapRoot = document.querySelector('.display-page');
        const mainImageWarmStateByFile = new Map();
        const {
            setTextWithBlend,
            setImageWithBlend,
        } = resultsViewerShared.createBlendHelpers({
            reducedMotion: REDUCED_MOTION,
            isInitialized: () => hasInitializedDisplayFile,
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
            document.querySelectorAll('[data-contour-intensity-type-label]').forEach((element) => {
                element.textContent = state.labels.contourIntensityTypeLabel || 'Total';
            });
            document.querySelectorAll('[data-contour-intensity-label-for]').forEach((element) => {
                const metricId = element.dataset.contourIntensityLabelFor;
                const label = state.labels.contourIntensityLabels?.[metricId];
                if (!label) return;
                element.setAttribute('aria-label', label);
                element.setAttribute('title', label);
                element.textContent = element.dataset.contourSlotLabel || label;
            });
            applyMetricVisibility(state.sections || { reference: true }, { mode: state.mode });

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
                blendText: hasInitializedDisplayFile,
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
            syncFileNavigationState();
            toggleContourOverlays();
            await loadFile(currentFileIndex);
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
            const shouldShowSkeleton = hasInitializedDisplayFile;

            if (shouldShowSkeleton) {
                setFileSwapLoading(true, requestToken);
            }

            try {
                if (hasInitializedDisplayFile) {
                    await Promise.all([
                        preloadImage(mainImagePath),
                        preloadImageSet(initialCellState.visibleImageUrls),
                    ]);
                    if (requestToken !== activeFileLoadToken) {
                        return false;
                    }
                }

                for (const channel of channels) {
                    const formElement = document.getElementById(`${channel}_form`);
                    if (formElement) {
                        formElement.action = `/experiment/${fileUUID}/display/`;
                    }
                }

                await Promise.all([
                    setImageWithBlend(document.getElementById('mainImage'), mainImagePath, {
                        duration: FILE_BLEND_IMAGE_MS,
                        blend: hasInitializedDisplayFile,
                    }),
                    setTextWithBlend(document.getElementById('imageTitle'), fileData.Image_Name || '', {
                        duration: FILE_BLEND_TEXT_MS,
                        blend: hasInitializedDisplayFile,
                    }),
                    updateFileContextSummary(fileUUID, fileData, { blend: hasInitializedDisplayFile }),
                    updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                        blendImages: hasInitializedDisplayFile,
                        blendText: hasInitializedDisplayFile,
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

                hasInitializedDisplayFile = true;
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



        function showChannelPreferenceWarning() {
            showChannelError('Main channel changed, but the preference could not be saved right now.');
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
                    blend: hasInitializedDisplayFile,
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

        function syncContourStateLabel(showContours) {
            const contourStateValue = document.getElementById('contourStateValue');
            if (contourStateValue) {
                contourStateValue.textContent = showContours ? 'On' : 'Off';
            }
        }












        updateSpatialUnitControls(filesData[fileUUIDs[currentFileIndex]] || null);








        function buildDisplayExportUrl(fileUUID, format, selectedColumns = null) {
            const params = new URLSearchParams({
                _export: format,
                _unit: getCurrentSpatialUnit(),
                _cell_type: getCurrentCellTypeFilter(),
                _puncta_source_contour_count: getCurrentPunctaSourceContourCountFilter(),
            });
            if (Array.isArray(selectedColumns) && selectedColumns.length > 0) {
                params.set('_columns', selectedColumns.join(','));
            }
            return `/experiment/${encodeURIComponent(fileUUID)}/display/?${params.toString()}`;
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

        function syncDisplayExportButtons(fileUUID, fileData, renderedRowCount = 0) {
            const exportButtons = document.getElementById('displayExportButtons');
            if (!exportButtons) {
                return;
            }

            const canExport = Boolean(fileUUID) && hasStatisticsTableRows(fileData, renderedRowCount);
            exportButtons.style.display = canExport ? 'flex' : 'none';
            if (!canExport) {
                return;
            }

            const statsBtn = document.getElementById('displayDownloadStatsBtn');
            if (statsBtn) {
                statsBtn.href = buildDisplayExportUrl(fileUUID, 'csv');
            }
        }

        let displayExportSelectionController = null;
        if (window.CytoCVExportSelection) {
            displayExportSelectionController = window.CytoCVExportSelection.init({
                configScriptId: 'exportSelectionConfig',
                modalId: 'exportSelectionBackdrop',
                triggerFormats: {
                    displayDownloadStatsBtn: 'csv',
                },
                getCurrentFileContext: () => {
                    const fileUUID = fileUUIDs[currentFileIndex];
                    return {
                        fileUUID,
                        fileData: fileUUID ? filesData[fileUUID] : null,
                    };
                },
                buildExportUrl: buildDisplayExportUrl,
                getStatLabel: getExportSelectionStatLabel,
                bulkExportUrl: '/experiment/display/files/export/',
                getSelectableFiles: () => fileUUIDs.map((fileUUID) => ({
                    id: fileUUID,
                    label: filesData[fileUUID] && filesData[fileUUID].Image_Name
                        ? filesData[fileUUID].Image_Name
                        : fileUUID,
                    fileData: filesData[fileUUID] || null,
                })),
                buildBulkExportPayload: ({ fileIds, format, columns }) => ({
                    visible_uuids: Array.from(fileUUIDs),
                    uuids: fileIds,
                    _export: format,
                    _columns: columns,
                    _unit: getCurrentSpatialUnit(),
                    _cell_type: getCurrentCellTypeFilter(),
                    _puncta_source_contour_count: getCurrentPunctaSourceContourCountFilter(),
                }),
            });
            window.displayExportSelectionController = displayExportSelectionController;
        }

        function getCurrentCellTypeFilter() {
            return normalizeCellTypeFilter(currentCellTypeFilter);
        }

        function setCurrentCellTypeFilter(value) {
            currentCellTypeFilter = normalizeCellTypeFilter(value);
            syncCellTypeFilterControl();
            syncPunctaSourceContourFilterControl(filesData[fileUUIDs[currentFileIndex]] || null);
            return currentCellTypeFilter;
        }

        function syncCellTypeFilterControl() {
            const effectiveFilter = getCurrentCellTypeFilter();
            if (cellTypeFilterValue) {
                cellTypeFilterValue.textContent = getCellTypeFilterLabel(effectiveFilter);
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
            return normalizePunctaSourceContourCountFilter(currentPunctaSourceContourCountFilter);
        }

        function setCurrentPunctaSourceContourCountFilter(value) {
            currentPunctaSourceContourCountFilter = normalizePunctaSourceContourCountFilter(value);
            syncPunctaSourceContourFilterControl(filesData[fileUUIDs[currentFileIndex]] || null);
            return currentPunctaSourceContourCountFilter;
        }

        function getEffectivePunctaSourceContourCountFilter(fileData) {
            const counts = getPunctaSourceContourCountFilterCounts(
                fileData?.Statistics || {},
                getCurrentPunctaSourceContourCountFilter(),
                getCurrentCellTypeFilter(),
            );
            return counts.applicable ? getCurrentPunctaSourceContourCountFilter() : 'all';
        }

        function syncPunctaSourceContourFilterControl(fileData) {
            const counts = getPunctaSourceContourCountFilterCounts(
                fileData?.Statistics || {},
                getCurrentPunctaSourceContourCountFilter(),
                getCurrentCellTypeFilter(),
            );
            const effectiveFilter = counts.applicable
                ? getCurrentPunctaSourceContourCountFilter()
                : 'all';
            if (punctaSourceContourFilterLabel) {
                punctaSourceContourFilterLabel.textContent = `${counts.controlLabel}:`;
            }
            if (punctaSourceContourFilterValue) {
                punctaSourceContourFilterValue.textContent = getPunctaSourceContourCountFilterLabel(effectiveFilter);
            }
            if (punctaSourceContourFilterControl) {
                punctaSourceContourFilterControl.classList.toggle('is-disabled', !counts.applicable);
                punctaSourceContourFilterControl.dataset.sourceChannel = counts.channel || '';
            }
            if (punctaSourceContourFilterButton) {
                punctaSourceContourFilterButton.disabled = !counts.applicable;
                punctaSourceContourFilterButton.setAttribute('aria-disabled', counts.applicable ? 'false' : 'true');
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
            [
                document.getElementById('tableScrollFrame'),
                document.querySelector('[data-ui-region="cell-metrics-strip"]'),
            ].forEach((element) => {
                if (!element) return;
                element.classList.toggle('is-contour-filter-applying', !!isApplying);
                element.setAttribute('aria-busy', isApplying ? 'true' : 'false');
            });
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
                const counts = getPunctaSourceContourCountFilterCounts(
                    fileData?.Statistics || {},
                    getCurrentPunctaSourceContourCountFilter(),
                    getCurrentCellTypeFilter(),
                );
                const shown = Number.isFinite(Number(renderedRowCount))
                    ? Number(renderedRowCount)
                    : counts.shown;
                status.textContent = `Showing ${shown} of ${counts.total} cells`;
                status.dataset.activeFilter = [
                    getCellTypeFilterLabel(getCurrentCellTypeFilter()),
                    getPunctaSourceContourCountFilterLabel(counts.filter),
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
                parts.push(cellTypeFilter === 'single_cell' ? 'Single cells only' : 'Cell pairs only');
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
                value.textContent = label || 'All cells';
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

        function updateTableState(fileUUID, fileData) {
            const exportButtons = document.getElementById('displayExportButtons');
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

            const filterValue = getEffectivePunctaSourceContourCountFilter(fileData);
            const renderedRowCount = renderStatisticsTable(
                fileData.Statistics || {},
                fileData,
                {
                    cellTypeFilter: getCurrentCellTypeFilter(),
                    punctaSourceContourCountFilter: filterValue,
                    activeCellId: currentCellNumber,
                },
            );
            const filterCounts = getPunctaSourceContourCountFilterCounts(
                fileData.Statistics || {},
                getCurrentPunctaSourceContourCountFilter(),
                getCurrentCellTypeFilter(),
            );
            syncCellTypeFilterControl();
            syncPunctaSourceContourFilterControl(fileData);
            const hasActiveRowFilter = (
                getCurrentCellTypeFilter() !== 'all'
                || filterValue !== 'all'
            );
            const analyzedRowCount = Object.values(fileData.Statistics || {}).filter(
                (row) => row && typeof row === 'object',
            ).length;

            if (fileData.NoCellsWarning) {
                note.textContent = fileData.NoCellsWarning;
                note.style.display = 'block';
            } else if (analyzedRowCount > 0 && renderedRowCount === 0 && hasActiveRowFilter) {
                note.textContent = 'No cells match the current row filters. Show all analyzed cell types and all source contours to view every retained cell.';
                note.style.display = 'block';
            } else {
                note.style.display = 'none';
            }

            syncPunctaSourceContourFilterStatus(fileData, renderedRowCount);
            syncCellNavigationState(fileData);
            syncDisplayExportButtons(fileUUID, fileData, renderedRowCount);
        }

        if (cellTypeFilterButton && cellTypeFilterMenu) {
            cellTypeFilterButton.addEventListener('click', () => {
                const isOpen = cellTypeFilterButton.getAttribute('aria-expanded') === 'true';
                cellTypeFilterMenu.hidden = isOpen;
                cellTypeFilterButton.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
            });
            cellTypeFilterMenu.querySelectorAll('[data-value]').forEach((option) => {
                option.addEventListener('click', async () => {
                    const previousCellNumber = Number(currentCellNumber);
                    setCurrentCellTypeFilter(option.dataset.value);
                    startPunctaSourceContourFilterApplyVisualState();
                    closeCellTypeFilterMenu();
                    try {
                        await waitForPunctaSourceContourFilterApplyFeedback();
                        const fileUUID = fileUUIDs[currentFileIndex];
                        const fileData = fileUUID ? filesData[fileUUID] : null;
                        if (fileUUID && fileData) {
                            await syncCurrentCellToActiveContourFilter(fileData, {
                                anchorCellId: previousCellNumber,
                                blendImages: true,
                                blendText: true,
                                imageLoading: true,
                            });
                            updateTableState(fileUUID, fileData);
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
                    const previousCellNumber = Number(currentCellNumber);
                    setCurrentPunctaSourceContourCountFilter(option.dataset.value);
                    startPunctaSourceContourFilterApplyVisualState();
                    closePunctaSourceContourFilterMenu();
                    try {
                        await waitForPunctaSourceContourFilterApplyFeedback();
                        const fileUUID = fileUUIDs[currentFileIndex];
                        const fileData = fileUUID ? filesData[fileUUID] : null;
                        if (fileUUID && fileData) {
                            await syncCurrentCellToActiveContourFilter(fileData, {
                                anchorCellId: previousCellNumber,
                                blendImages: true,
                                blendText: true,
                                imageLoading: true,
                            });
                            updateTableState(fileUUID, fileData);
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
            const nextState = getCellDisplayState(fileData.CellPairImages, fileData.Statistics, {
                showContours: getContourToggleState(),
                cellNumber: currentCellNumber,
            });
            renderCellDisplayState(nextState, { blendImages: false, blendText: false });
            updateTableState(fileUUID, fileData);
            if (displayExportSelectionController && displayExportSelectionController.refreshStatLabels) {
                displayExportSelectionController.refreshStatLabels();
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
                showSidebarMessage('Unable to save spatial unit preference right now.');
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
                if (
                    showImageLoading
                    && renderToken === activeCellRenderToken
                    && (!options.fileToken || options.fileToken === activeFileLoadToken)
                ) {
                    setCellPairImagesLoading(false);
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
                blendImages: hasInitializedDisplayFile,
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
            await updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                blendImages: true,
                blendText: true,
                forceShowContours: showContours,
                imageLoading: true,
            });
            updateTableState(fileUUID, fileData);
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
            await updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                blendImages: true,
                blendText: true,
                forceShowContours: showContours,
                imageLoading: true,
            });
            updateTableState(fileUUID, fileData);
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
        const fileItems = Array.from(document.querySelectorAll('.file-item[data-uuid]'));
        const mainChannelButtons = document.querySelectorAll('.main-channel-btn[data-main-channel]');
        const selectModeBtn = document.getElementById('selectModeBtn');
        const selectAllBtn = document.getElementById('selectAllBtn');
        const saveSelectedBtn = document.getElementById('saveSelectedBtn');
        const downloadSelectedBtn = document.getElementById('downloadSelectedBtn');
        const channelVisibilityBtn = document.getElementById('toggleChannelVisibilityBtn');
        const scaleVisibilityBtn = document.getElementById('toggleScaleVisibilityBtn');
        const saveBackdrop = document.getElementById('saveFilesBackdrop');
        const saveTitle = document.getElementById('saveFilesTitle');
        const saveMessage = document.getElementById('saveFilesMessage');
        const saveAddSection = document.getElementById('saveFilesAddSection');
        const saveRemoveSection = document.getElementById('saveFilesRemoveSection');
        const saveAddList = document.getElementById('saveFilesAddList');
        const saveRemoveList = document.getElementById('saveFilesRemoveList');
        const cancelSaveFilesBtn = document.getElementById('cancelSaveFilesBtn');
        const confirmSaveFilesBtn = document.getElementById('confirmSaveFilesBtn');
        const selectionInfoDots = Array.from(document.querySelectorAll('.selection-info-dot[data-info-text]'));
        const infoTooltipElement = document.getElementById('selectionInfoTooltip');
        const fileItemByUUID = new Map(fileItems.map((item) => [item.dataset.uuid, item]));
        const selectedFileUUIDs = new Set();
        const savedFileUUIDs = new Set(
            fileItems
                .filter((item) => item.dataset.saved === 'true')
                .map((item) => item.dataset.uuid)
                .filter(Boolean)
        );
        let selectModeActive = false;
        let channelLabelFadeTimer = null;
        let scaleLabelFadeTimer = null;
        let pendingSelectionPayload = null;
        let activeInfoAnchor = null;

        function getCookie(name) {
            let value = null;
            document.cookie.split(';').forEach((cookie) => {
                const item = cookie.trim();
                if (item.startsWith(`${name}=`)) {
                    value = decodeURIComponent(item.slice(name.length + 1));
                }
            });
            return value;
        }

        const csrfToken = getCookie('csrftoken');

        function normalizeInfoText(value) {
            if (typeof value !== 'string') return '';
            return value
                .split('\n')
                .map((line) => line.trim())
                .filter((line, index, arr) => !(line === '' && (index === 0 || index === arr.length - 1)))
                .join('\n');
        }

        function hideInfoTooltip() {
            activeInfoAnchor = null;
            if (!infoTooltipElement) return;
            infoTooltipElement.hidden = true;
            infoTooltipElement.textContent = '';
        }

        function positionInfoTooltip(anchor) {
            if (!infoTooltipElement || !anchor) return;
            const rect = anchor.getBoundingClientRect();
            const margin = 10;
            const gap = 8;

            infoTooltipElement.style.left = '0px';
            infoTooltipElement.style.top = '0px';
            const width = infoTooltipElement.offsetWidth;
            const height = infoTooltipElement.offsetHeight;

            let left = rect.left + (rect.width / 2) - (width / 2);
            left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));

            let top = rect.top - height - gap;
            if (top < margin) {
                top = rect.bottom + gap;
            }
            if (top + height > window.innerHeight - margin) {
                top = Math.max(margin, window.innerHeight - height - margin);
            }

            infoTooltipElement.style.left = `${Math.round(left)}px`;
            infoTooltipElement.style.top = `${Math.round(top)}px`;
        }

        function refreshInfoTooltipPosition() {
            if (!activeInfoAnchor || !infoTooltipElement || infoTooltipElement.hidden) return;
            positionInfoTooltip(activeInfoAnchor);
        }

        function showInfoTooltip(anchor) {
            if (!anchor || !infoTooltipElement) return;
            const text = normalizeInfoText(anchor.dataset.infoText || '');
            if (!text) {
                hideInfoTooltip();
                return;
            }
            activeInfoAnchor = anchor;
            infoTooltipElement.textContent = text;
            infoTooltipElement.hidden = false;
            positionInfoTooltip(anchor);
        }

        function attachInfoTooltipBehavior(infoDot) {
            if (!infoDot) return;
            infoDot.addEventListener('mouseenter', () => showInfoTooltip(infoDot));
            infoDot.addEventListener('mouseleave', hideInfoTooltip);
            infoDot.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                if (activeInfoAnchor === infoDot && infoTooltipElement && !infoTooltipElement.hidden) {
                    hideInfoTooltip();
                    return;
                }
                showInfoTooltip(infoDot);
            });
        }

        function showSidebarMessage(message, tone = 'error') {
            if (window.showGlobalMessage) {
                window.showGlobalMessage(message, tone, {
                    scope: 'channel-switch',
                    top: 'calc(var(--nav-height) + 8px)',
                    timeoutMs: 7000,
                });
                return;
            }
        }

        function updateSavedStateClasses() {
            fileItems.forEach((item) => {
                const uuid = item.dataset.uuid;
                const isSaved = savedFileUUIDs.has(uuid);
                item.dataset.saved = isSaved ? 'true' : 'false';
                item.classList.toggle('saved', isSaved);
            });
        }

        function getSelectionChanges() {
            const selectedSet = new Set(selectedFileUUIDs);
            const toSave = [];
            const toUnsave = [];
            fileUUIDs.forEach((uuid) => {
                const isSelected = selectedSet.has(uuid);
                const isSaved = savedFileUUIDs.has(uuid);
                if (isSelected && !isSaved) {
                    toSave.push(uuid);
                }
                if (!isSelected && isSaved) {
                    toUnsave.push(uuid);
                }
            });
            return { toSave, toUnsave };
        }

        function syncSelectionUI() {
            fileItems.forEach((item) => {
                item.classList.toggle('selected', selectedFileUUIDs.has(item.dataset.uuid));
            });

            const hasFiles = fileUUIDs.length > 0;
            const { toSave, toUnsave } = getSelectionChanges();
            const hasChanges = toSave.length > 0 || toUnsave.length > 0;

            selectAllBtn.disabled = !hasFiles;
            saveSelectedBtn.disabled = !selectModeActive || !hasFiles || !hasChanges;
            if (downloadSelectedBtn) {
                downloadSelectedBtn.disabled = !selectModeActive || !hasFiles || selectedFileUUIDs.size === 0;
                downloadSelectedBtn.title = downloadSelectedBtn.disabled
                    ? 'Select files first.'
                    : 'Download selected files.';
            }
            if (!selectModeActive) {
                saveSelectedBtn.title = 'Select files first.';
            } else if (!hasChanges) {
                saveSelectedBtn.title = 'No save-state changes to apply.';
            } else {
                saveSelectedBtn.title = 'Apply selected save state.';
            }
        }

        function renderPreviewList(target, uuids) {
            if (!target) return;
            target.innerHTML = '';
            uuids.forEach((uuid) => {
                const fileItem = fileItemByUUID.get(uuid);
                const title = fileItem ? fileItem.querySelector('.file-title') : null;
                const li = document.createElement('li');
                li.textContent = title ? title.textContent.trim() : uuid;
                target.appendChild(li);
            });
        }

        function updateModalSections(toSave, toUnsave) {
            if (saveAddSection) {
                saveAddSection.hidden = toSave.length === 0;
            }
            if (saveRemoveSection) {
                saveRemoveSection.hidden = toUnsave.length === 0;
            }
            renderPreviewList(saveAddList, toSave);
            renderPreviewList(saveRemoveList, toUnsave);
        }

        function buildSelectionMessage(toSave, toUnsave) {
            if (toSave.length > 0 && toUnsave.length > 0) {
                return 'Selected files will be saved, and unselected files will be removed from saved history.';
            }
            if (toSave.length > 0) {
                return toSave.length === fileUUIDs.length
                    ? 'Are you sure you want to save all files?'
                    : 'Are you sure you want to save the selected files?';
            }
            return toUnsave.length === fileUUIDs.length
                ? 'Are you sure you want to remove all files from saved history?'
                : 'Are you sure you want to remove these files from saved history?';
        }

        function buildSelectionToast(savedCount, unsavedCount) {
            if (savedCount > 0 && unsavedCount > 0) {
                return {
                    message: `Updated selection: saved ${savedCount} file${savedCount === 1 ? '' : 's'} and removed ${unsavedCount} file${unsavedCount === 1 ? '' : 's'}.`,
                    tone: 'success',
                };
            }
            if (savedCount > 0) {
                return {
                    message: `Saved ${savedCount} file${savedCount === 1 ? '' : 's'}.`,
                    tone: 'success',
                };
            }
            if (unsavedCount > 0) {
                return {
                    message: `Removed ${unsavedCount} file${unsavedCount === 1 ? '' : 's'} from saved history.`,
                    tone: 'error',
                };
            }
            return {
                message: 'No save-state changes were needed.',
                tone: 'success',
            };
        }

        function setSelectMode(enabled) {
            selectModeActive = enabled;
            sidebar.classList.toggle('select-mode', enabled);
            selectModeBtn.classList.toggle('active', enabled);
            selectModeBtn.textContent = enabled ? 'Done' : 'Select';

            if (enabled) {
                selectedFileUUIDs.clear();
                savedFileUUIDs.forEach((uuid) => selectedFileUUIDs.add(uuid));
            } else {
                selectedFileUUIDs.clear();
            }

            syncSelectionUI();
        }

        function toggleSelectAll() {
            if (selectedFileUUIDs.size === fileUUIDs.length) {
                selectedFileUUIDs.clear();
            } else {
                fileUUIDs.forEach((uuid) => selectedFileUUIDs.add(uuid));
            }
            syncSelectionUI();
        }

        function applyChannelVisibility(visible, persist) {
            sidebar.classList.toggle('channels-hidden', !visible);
            channelVisibilityBtn.classList.add('label-fade');
            if (channelLabelFadeTimer) {
                window.clearTimeout(channelLabelFadeTimer);
            }
            channelVisibilityBtn.textContent = visible ? 'Hide Channels' : 'Show Channels';
            channelLabelFadeTimer = window.setTimeout(() => {
                channelVisibilityBtn.classList.remove('label-fade');
                channelLabelFadeTimer = null;
            }, 170);
            if (persist) {
                fetch('/dashboard/preferences/channels/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken || '',
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({ show_saved_file_channels: visible }),
                }).catch(() => null);
            }
        }

        function applyScaleVisibility(visible, persist) {
            sidebar.classList.toggle('scales-hidden', !visible);
            if (!scaleVisibilityBtn) return;
            scaleVisibilityBtn.classList.add('label-fade');
            if (scaleLabelFadeTimer) {
                window.clearTimeout(scaleLabelFadeTimer);
            }
            scaleVisibilityBtn.textContent = visible ? 'Hide Scale' : 'Show Scale';
            scaleLabelFadeTimer = window.setTimeout(() => {
                scaleVisibilityBtn.classList.remove('label-fade');
                scaleLabelFadeTimer = null;
            }, 170);
            if (persist) {
                fetch('/dashboard/preferences/channels/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken || '',
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({ show_saved_file_scales: visible }),
                }).catch(() => null);
            }
        }

        function closeSaveModal() {
            if (!saveBackdrop) return;
            saveBackdrop.style.display = 'none';
            saveBackdrop.setAttribute('aria-hidden', 'true');
            pendingSelectionPayload = null;
            if (confirmSaveFilesBtn) {
                confirmSaveFilesBtn.textContent = 'Confirm Save Selection';
            }
            if (saveTitle) {
                saveTitle.textContent = 'Save Selection';
            }
            if (saveMessage) {
                saveMessage.textContent = 'Selected files will be saved and unselected files will be removed from saved history.';
            }
            if (saveAddSection) {
                saveAddSection.hidden = true;
            }
            if (saveRemoveSection) {
                saveRemoveSection.hidden = true;
            }
            if (saveAddList) saveAddList.innerHTML = '';
            if (saveRemoveList) saveRemoveList.innerHTML = '';
        }

        function openSaveModal() {
            if (!saveBackdrop || !saveMessage || !saveTitle || !confirmSaveFilesBtn) return;
            const changes = getSelectionChanges();
            const hasChanges = changes.toSave.length > 0 || changes.toUnsave.length > 0;
            if (!hasChanges) {
                return;
            }

            pendingSelectionPayload = {
                visible_uuids: Array.from(fileUUIDs),
                selected_uuids: Array.from(selectedFileUUIDs),
            };

            saveTitle.textContent = 'Save Selection';
            saveMessage.textContent = buildSelectionMessage(changes.toSave, changes.toUnsave);
            confirmSaveFilesBtn.textContent = 'Confirm Save Selection';
            updateModalSections(changes.toSave, changes.toUnsave);
            saveBackdrop.style.display = 'flex';
            saveBackdrop.setAttribute('aria-hidden', 'false');
        }

        async function saveSelectedFiles() {
            if (!pendingSelectionPayload) return;
            confirmSaveFilesBtn.disabled = true;
            try {
                const response = await fetch('/experiment/display/files/sync-selection/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken || '',
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify(pendingSelectionPayload),
                });
                const payload = await response.json();
                if (!response.ok) {
                    throw new Error(payload.error || 'Unable to update selected files.');
                }

                (payload.saved_uuids || []).forEach((uuid) => savedFileUUIDs.add(uuid));
                (payload.unsaved_uuids || []).forEach((uuid) => savedFileUUIDs.delete(uuid));
                updateSavedStateClasses();
                syncSelectionUI();

                const toast = buildSelectionToast(
                    Number(payload.saved_count || 0),
                    Number(payload.unsaved_count || 0)
                );
                showSidebarMessage(toast.message, toast.tone);
                closeSaveModal();
            } catch (err) {
                showSidebarMessage(err.message || 'Unable to update selected files.');
            } finally {
                confirmSaveFilesBtn.disabled = false;
            }
        }

        // Highlight active
        function updateSidebarActive() {
            fileItems.forEach((item) => item.classList.remove('active'));
            const active = document.querySelector(`.file-item[data-index="${currentFileIndex}"]`);
            if (active) active.classList.add('active');
        }
        updateSidebarActive();

        // Click file/select
        fileItems.forEach((item) => {
            const uuid = item.dataset.uuid;
            const selectCheck = item.querySelector('.file-select-check');
            if (selectCheck) {
                selectCheck.addEventListener('click', (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (!selectModeActive || !uuid) return;
                    if (selectedFileUUIDs.has(uuid)) {
                        selectedFileUUIDs.delete(uuid);
                    } else {
                        selectedFileUUIDs.add(uuid);
                    }
                    syncSelectionUI();
                });
            }

            item.addEventListener('click', () => {
                const idx = parseInt(item.dataset.index, 10);
                if (selectModeActive && uuid) {
                    if (selectedFileUUIDs.has(uuid)) {
                        selectedFileUUIDs.delete(uuid);
                    } else {
                        selectedFileUUIDs.add(uuid);
                    }
                    syncSelectionUI();
                    return;
                }
                loadFile(idx);
            });
        });

        const previousFileBtn = document.getElementById('previousFileBtn');
        const nextFileBtn = document.getElementById('nextFileBtn');
        if (previousFileBtn) previousFileBtn.addEventListener('click', previousFile);
        if (nextFileBtn) nextFileBtn.addEventListener('click', nextFile);

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
        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            setSidebarCollapsed(!sidebar.classList.contains('collapsed'));
        });

        // Also expand when collapsed sidebar area is clicked
        sidebar.addEventListener('click', () => {
            if (sidebar.classList.contains('collapsed')) {
                setSidebarCollapsed(false);
            }
        });

        selectModeBtn.addEventListener('click', () => setSelectMode(!selectModeActive));
        selectAllBtn.addEventListener('click', toggleSelectAll);
        saveSelectedBtn.addEventListener('click', openSaveModal);
        if (downloadSelectedBtn) {
            downloadSelectedBtn.addEventListener('click', () => {
                if (!window.displayExportSelectionController || selectedFileUUIDs.size === 0) {
                    return;
                }
                window.displayExportSelectionController.openFiles(
                    fileUUIDs.filter((uuid) => selectedFileUUIDs.has(uuid))
                );
            });
        }
        channelVisibilityBtn.addEventListener('click', () => {
            applyChannelVisibility(sidebar.classList.contains('channels-hidden'), true);
        });
        if (scaleVisibilityBtn) {
            scaleVisibilityBtn.addEventListener('click', () => {
                applyScaleVisibility(sidebar.classList.contains('scales-hidden'), true);
            });
        }
        if (cancelSaveFilesBtn) cancelSaveFilesBtn.addEventListener('click', closeSaveModal);
        if (confirmSaveFilesBtn) confirmSaveFilesBtn.addEventListener('click', saveSelectedFiles);
        if (saveBackdrop) {
            saveBackdrop.addEventListener('click', (event) => {
                if (event.target === saveBackdrop) closeSaveModal();
            });
        }
        selectionInfoDots.forEach(attachInfoTooltipBehavior);
        document.addEventListener('click', (event) => {
            const target = event.target;
            if (!(target instanceof Element) || !target.classList.contains('selection-info-dot')) {
                hideInfoTooltip();
            }
        });
        window.addEventListener('resize', refreshInfoTooltipPosition);
        window.addEventListener('scroll', refreshInfoTooltipPosition, true);
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                hideInfoTooltip();
            }
            if (event.key === 'Escape' && saveBackdrop && saveBackdrop.style.display === 'flex') {
                closeSaveModal();
            }
        });

        updateSavedStateClasses();
        applyChannelVisibility(!sidebar.classList.contains('channels-hidden'), false);
        applyScaleVisibility(!sidebar.classList.contains('scales-hidden'), false);
        syncSelectionUI();

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
