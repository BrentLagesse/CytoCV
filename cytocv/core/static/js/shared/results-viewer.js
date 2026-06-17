(function (global) {
    'use strict';

    function readJsonConfig(scriptId) {
        const node = document.getElementById(scriptId);
        return JSON.parse(node ? node.textContent || '{}' : '{}');
    }

    function createBlendHelpers({
        reducedMotion = false,
        isInitialized = () => false,
        noCellPlaceholder = '',
        defaultTextDuration = 170,
        defaultImageDuration = 190,
    } = {}) {
        function clearElementBlend(element) {
            if (!element) {
                return;
            }
            if (element._uiBlendTimer) {
                clearTimeout(element._uiBlendTimer);
                element._uiBlendTimer = null;
            }
            if (element._uiBlendOverlay) {
                element._uiBlendOverlay.remove();
                element._uiBlendOverlay = null;
            }
            if (element._uiBlendTextOverlay) {
                element._uiBlendTextOverlay.remove();
                element._uiBlendTextOverlay = null;
            }
            element.classList.remove('is-pre-blend-text', 'is-pre-blend-image', 'is-exiting-old');
            element.removeAttribute('data-blend-old');
        }

        function stripOverlayIds(node) {
            if (!node || node.nodeType !== Node.ELEMENT_NODE) {
                return;
            }
            if (node.id) {
                node.removeAttribute('id');
            }
            node.querySelectorAll('[id]').forEach((child) => child.removeAttribute('id'));
        }

        function createBlendOverlay(element, durationMs) {
            if (!element) {
                return null;
            }
            const rect = element.getBoundingClientRect();
            if (!rect.width || !rect.height) {
                return null;
            }

            const overlay = element.cloneNode(true);
            stripOverlayIds(overlay);
            overlay.classList.add('ui-blend-overlay');
            overlay.setAttribute('aria-hidden', 'true');
            overlay.style.position = 'fixed';
            overlay.style.left = `${rect.left}px`;
            overlay.style.top = `${rect.top}px`;
            overlay.style.width = `${rect.width}px`;
            overlay.style.height = `${rect.height}px`;
            overlay.style.margin = '0';
            overlay.style.setProperty('--ui-blend-duration', `${durationMs}ms`);
            return overlay;
        }

        function createTextBlendOverlay(element, durationMs) {
            if (!element || !element.parentElement) {
                return null;
            }

            const anchor = element.parentElement;
            const rect = element.getBoundingClientRect();
            const anchorRect = anchor.getBoundingClientRect();
            if (!rect.width || !rect.height) {
                return null;
            }

            anchor.classList.add('blend-host-anchor');

            const overlay = element.cloneNode(true);
            const computed = window.getComputedStyle(element);
            stripOverlayIds(overlay);
            overlay.classList.add('ui-blend-overlay');
            overlay.setAttribute('aria-hidden', 'true');
            overlay.style.position = 'absolute';
            overlay.style.left = `${rect.left - anchorRect.left + anchor.scrollLeft}px`;
            overlay.style.top = `${rect.top - anchorRect.top + anchor.scrollTop}px`;
            overlay.style.width = `${rect.width}px`;
            overlay.style.height = `${rect.height}px`;
            overlay.style.display = computed.display === 'inline' ? 'block' : computed.display;
            overlay.style.lineHeight = computed.lineHeight;
            overlay.style.whiteSpace = computed.whiteSpace;
            overlay.style.margin = '0';
            overlay.style.setProperty('--ui-blend-duration', `${durationMs}ms`);

            return {
                overlay,
                mountTarget: anchor,
            };
        }

        function runBlendTransition(element, applyUpdate, { duration = defaultTextDuration, type = 'text', blend = true } = {}) {
            if (!element) {
                applyUpdate();
                return Promise.resolve();
            }

            clearElementBlend(element);

            const shouldBlend = blend && !reducedMotion && isInitialized();
            const overlayConfig = shouldBlend
                ? (type === 'text'
                    ? createTextBlendOverlay(element, duration)
                    : { overlay: createBlendOverlay(element, duration), mountTarget: document.body })
                : null;

            const preBlendClass = type === 'image' ? 'is-pre-blend-image' : 'is-pre-blend-text';
            if (overlayConfig?.overlay) {
                element.classList.add(preBlendClass);
            }
            applyUpdate();

            if (!overlayConfig?.overlay) {
                element.classList.remove(preBlendClass);
                return Promise.resolve();
            }

            const { overlay, mountTarget } = overlayConfig;
            mountTarget.appendChild(overlay);
            element._uiBlendOverlay = overlay;

            return new Promise((resolve) => {
                window.requestAnimationFrame(() => {
                    window.requestAnimationFrame(() => {
                        overlay.classList.add('is-exiting');
                        element.classList.remove(preBlendClass);
                    });
                });

                element._uiBlendTimer = window.setTimeout(() => {
                    if (element._uiBlendOverlay === overlay) {
                        overlay.remove();
                        element._uiBlendOverlay = null;
                    }
                    element._uiBlendTimer = null;
                    element.classList.remove(preBlendClass);
                    resolve();
                }, duration + 55);
            });
        }

        function prepareTextBlendElement(element, duration = defaultTextDuration) {
            if (!element) {
                return null;
            }

            if (element._uiBlendCurrent) {
                element.textContent = element._uiBlendCurrent.textContent || element.textContent || '';
                element._uiBlendCurrent = null;
            }

            const computed = window.getComputedStyle(element);
            element.classList.add('ui-blend-text-target');
            element.style.setProperty('--ui-blend-duration', `${duration}ms`);
            if (!element.dataset.uiBlendPrepared) {
                if (computed.display === 'inline') {
                    element.style.display = 'inline-block';
                    element.style.verticalAlign = computed.verticalAlign || 'baseline';
                } else if (computed.display !== 'none') {
                    element.style.display = computed.display;
                }
                element.dataset.uiBlendPrepared = '1';
            }

            return element;
        }

        function setTextWithBlend(element, nextText, { duration = defaultTextDuration, blend = true } = {}) {
            if (!element) {
                return Promise.resolve();
            }

            const target = prepareTextBlendElement(element, duration);
            const normalized = String(nextText ?? '');
            if ((target.textContent || '') === normalized) {
                return Promise.resolve();
            }

            clearElementBlend(target);

            const shouldBlend = blend && !reducedMotion && isInitialized();
            if (!shouldBlend) {
                target.textContent = normalized;
                return Promise.resolve();
            }

            target.setAttribute('data-blend-old', target.textContent || '');
            target.textContent = normalized;
            target.classList.add('is-pre-blend-text');

            return new Promise((resolve) => {
                window.requestAnimationFrame(() => {
                    window.requestAnimationFrame(() => {
                        target.classList.add('is-exiting-old');
                        target.classList.remove('is-pre-blend-text');
                    });
                });

                target._uiBlendTimer = window.setTimeout(() => {
                    target.removeAttribute('data-blend-old');
                    target._uiBlendTimer = null;
                    target.classList.remove('is-pre-blend-text', 'is-exiting-old');
                    resolve();
                }, duration + 55);
            });
        }

        function setImageWithBlend(element, nextSrc, { duration = defaultImageDuration, blend = true } = {}) {
            if (!element) {
                return Promise.resolve();
            }
            const normalized = nextSrc || noCellPlaceholder;
            if ((element.getAttribute('src') || '') === normalized) {
                return Promise.resolve();
            }
            return runBlendTransition(
                element,
                () => {
                    element.src = normalized;
                },
                { duration, type: 'image', blend },
            );
        }

        return {
            clearElementBlend,
            stripOverlayIds,
            createBlendOverlay,
            createTextBlendOverlay,
            runBlendTransition,
            prepareTextBlendElement,
            setTextWithBlend,
            setImageWithBlend,
        };
    }

    function getContourToggleState(forceShowContours = null) {
        if (forceShowContours !== null) {
            return !!forceShowContours;
        }
        const toggleElement = document.getElementById('toggleContours');
        return !!(toggleElement && toggleElement.checked);
    }

    function getVisibleCellImageUrls(imageUrls, showContours, noCellPlaceholder) {
        if (!Array.isArray(imageUrls) || imageUrls.length === 0) {
            return [noCellPlaceholder, noCellPlaceholder, noCellPlaceholder, noCellPlaceholder];
        }
        const indices = showContours ? [0, 2, 4, 6] : [1, 3, 5, 7];
        return indices.map((index) => imageUrls[index] || noCellPlaceholder);
    }

    function defaultStatVisibility() {
        return {
            puncta_distance: true,
            red_green_intensity: true,
            nuclear_cell_pair_intensity: true,
            cen_dot: true,
            biorientation: true,
            legacy_blue_intensity: true,
        };
    }

    function getStatVisibility(cellStats) {
        const defaults = defaultStatVisibility();
        const visibility = cellStats && typeof cellStats.stat_visibility === 'object'
            ? cellStats.stat_visibility
            : null;
        return {
            puncta_distance: visibility ? visibility.puncta_distance !== false : defaults.puncta_distance,
            red_green_intensity: visibility ? visibility.red_green_intensity !== false : defaults.red_green_intensity,
            nuclear_cell_pair_intensity: visibility ? visibility.nuclear_cell_pair_intensity !== false : defaults.nuclear_cell_pair_intensity,
            cen_dot: visibility ? visibility.cen_dot !== false : defaults.cen_dot,
            biorientation: visibility ? visibility.biorientation !== false : defaults.biorientation,
            legacy_blue_intensity: visibility ? visibility.legacy_blue_intensity !== false : defaults.legacy_blue_intensity,
        };
    }

    function ensureChannelMessageContainer() {
        let container = document.querySelector('.message-container.channel-switch');
        if (container) return container;
        container = document.createElement('div');
        container.className = 'message-container channel-switch';
        container.style.top = 'calc(var(--nav-height) + 8px)';
        container.style.left = '50%';
        container.style.transform = 'translateX(-50%)';
        container.style.width = 'min(720px, calc(100% - 32px))';
        container.style.margin = '0';
        container.style.zIndex = '1500';
        container.style.pointerEvents = 'none';
        document.body.appendChild(container);
        return container;
    }

    function showChannelError(message) {
        const container = ensureChannelMessageContainer();
        const msg = document.createElement('div');
        msg.className = 'message';
        msg.style.pointerEvents = 'auto';
        msg.textContent = message;
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'message-close';
        close.setAttribute('aria-label', 'Dismiss');
        close.innerHTML = '&times;';
        close.addEventListener('click', () => msg.remove());
        msg.appendChild(close);
        container.appendChild(msg);
        setTimeout(() => msg.remove(), 8000);
    }

    function preloadImage(url) {
        return new Promise((resolve) => {
            if (!url) {
                resolve(url);
                return;
            }

            const img = new Image();
            let settled = false;
            const finish = () => {
                if (settled) {
                    return;
                }
                settled = true;
                resolve(url);
            };

            img.onload = finish;
            img.onerror = finish;
            img.src = url;

            if (typeof img.decode === 'function') {
                img.decode().then(finish).catch(finish);
            }

            if (img.complete) {
                finish();
            }
        });
    }

    function preloadImageSet(urls) {
        const uniqueUrls = [...new Set((urls || []).filter(Boolean))];
        if (!uniqueUrls.length) {
            return Promise.resolve();
        }
        return Promise.all(uniqueUrls.map((url) => preloadImage(url)));
    }

    function getSortedCellIds(fileData) {
        const statistics = (fileData && fileData.Statistics) || {};
        const statIds = Object.keys(statistics)
            .map((key) => Number(key))
            .filter((value) => (
                Number.isFinite(value)
                && value > 0
                && statistics[String(value)]
                && typeof statistics[String(value)] === 'object'
            ))
            .sort((a, b) => a - b);
        if (statIds.length > 0) {
            return statIds;
        }
        const pairImages = (fileData && fileData.CellPairImages) || {};
        return Object.keys(pairImages)
            .map((key) => Number(key))
            .filter((value) => Number.isFinite(value) && value > 0)
            .sort((a, b) => a - b);
    }

    function getWarmPriorityOffsets(direction = 'initial') {
        if (direction === 'next') {
            return [1, 2, -1, -2];
        }
        if (direction === 'previous') {
            return [-1, -2, 1, 2];
        }
        return [1, -1, 2, -2];
    }

    function buildFullCircularCellOrder(sortedIds, activeCellNumber, totalCells) {
        if (!Array.isArray(sortedIds) || sortedIds.length < 2 || Number(totalCells || 0) < 1) {
            return [];
        }
        const currentIdx = Math.max(0, sortedIds.indexOf(Number(activeCellNumber)));
        const ordered = [];
        for (let offset = 1; offset < sortedIds.length; offset += 1) {
            ordered.push(sortedIds[(currentIdx + offset) % sortedIds.length]);
        }
        return ordered;
    }

    function getCircularWarmQueue({
        sortedIds,
        currentCellNumber,
        maxCells,
        direction = 'initial',
    } = {}) {
        if (!Array.isArray(sortedIds) || sortedIds.length < 2) {
            return [];
        }
        const currentIdx = Math.max(0, sortedIds.indexOf(Number(currentCellNumber)));
        const offsets = sortedIds.length <= 5
            ? buildFullCircularCellOrder(sortedIds, currentCellNumber, maxCells).map((cellNumber) => (
                (sortedIds.indexOf(cellNumber) - currentIdx + sortedIds.length) % sortedIds.length
            ))
            : getWarmPriorityOffsets(direction);
        const seen = new Set();
        const ordered = [];
        offsets.forEach((offset) => {
            const targetIdx = (currentIdx + offset + sortedIds.length) % sortedIds.length;
            const cellNumber = sortedIds[targetIdx];
            if (!seen.has(cellNumber) && cellNumber !== Number(currentCellNumber)) {
                seen.add(cellNumber);
                ordered.push(cellNumber);
            }
        });
        return ordered;
    }

    function normalizeMainImageChannel(channel, channels) {
        return channels.includes(channel) ? channel : '';
    }

    function setActiveChannel(channel, mainChannelButtons) {
        mainChannelButtons.forEach((btn) => {
            const isActive = btn.dataset.mainChannel === channel;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
    }

    function createMainImageHelpers({
        channels,
        defaultChannelIndexMap,
        mainImageWarmStateByFile,
        getCurrentFileData,
    }) {
        function getMainImageWarmState(fileUUID) {
            const normalizedFileUUID = String(fileUUID || '');
            if (!mainImageWarmStateByFile.has(normalizedFileUUID)) {
                mainImageWarmStateByFile.set(normalizedFileUUID, {
                    warmed: new Set(),
                    inFlight: new Map(),
                });
            }
            return mainImageWarmStateByFile.get(normalizedFileUUID);
        }

        function getMainImagePaths(fileData) {
            if (!fileData || typeof fileData !== 'object') {
                return {};
            }
            if (!fileData.MainImagePaths || typeof fileData.MainImagePaths !== 'object') {
                fileData.MainImagePaths = {};
            }
            return fileData.MainImagePaths;
        }

        function markMainImageChannelWarm(fileUUID, fileData, channel, url = '') {
            if (!fileUUID || !channel) {
                return;
            }
            const mainImagePaths = getMainImagePaths(fileData);
            if (url && !mainImagePaths[channel]) {
                mainImagePaths[channel] = url;
            }
            getMainImageWarmState(fileUUID).warmed.add(channel);
        }

        async function fetchMainImageChannelUrl(fileUUID, channel) {
            const response = await fetch(`/experiment/${fileUUID}/main-channel/?channel=${encodeURIComponent(channel)}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin',
            });
            if (!response.ok) {
                throw new Error(`Channel request failed (${response.status})`);
            }
            const data = await response.json();
            if (!data || !data.image_url) {
                throw new Error('Missing image URL');
            }
            return data.image_url;
        }

        async function resolveMainImageChannelUrl(fileUUID, fileData, channel) {
            const mainImagePaths = getMainImagePaths(fileData);
            const cachedUrl = typeof mainImagePaths[channel] === 'string' ? mainImagePaths[channel] : '';
            if (cachedUrl) {
                return cachedUrl;
            }
            const resolvedUrl = await fetchMainImageChannelUrl(fileUUID, channel);
            mainImagePaths[channel] = resolvedUrl;
            return resolvedUrl;
        }

        function warmMainImageChannel(fileUUID, fileData, channel) {
            if (!fileUUID || !fileData || !channel) {
                return Promise.resolve('');
            }
            const state = getMainImageWarmState(fileUUID);
            if (state.warmed.has(channel)) {
                return Promise.resolve(getMainImagePaths(fileData)[channel] || '');
            }
            if (state.inFlight.has(channel)) {
                return state.inFlight.get(channel);
            }
            const warmPromise = resolveMainImageChannelUrl(fileUUID, fileData, channel)
                .then(async (imageUrl) => {
                    await preloadImage(imageUrl);
                    state.warmed.add(channel);
                    return imageUrl;
                })
                .finally(() => {
                    state.inFlight.delete(channel);
                });
            state.inFlight.set(channel, warmPromise);
            return warmPromise;
        }

        function resolveChannelIndexMap(fileData = null) {
            const resolvedFileData = fileData || getCurrentFileData() || {};
            const configured = resolvedFileData.ChannelConfig || {};
            const indexMap = { ...defaultChannelIndexMap };
            Object.entries(configured).forEach(([channel, index]) => {
                const numericIndex = Number(index);
                if (Number.isFinite(numericIndex)) {
                    indexMap[numericIndex] = channel;
                }
            });
            return indexMap;
        }

        function inferChannelFromMainImage(src, fileData = null) {
            if (!src) return null;
            const match = src.match(/_frame_(\d+)\.png/i);
            if (!match) return null;
            const index = Number(match[1]);
            return resolveChannelIndexMap(fileData)[index] || null;
        }

        function primeMainImageWarmState(fileUUID, fileData, mainImagePath) {
            const inferredChannel = inferChannelFromMainImage(mainImagePath, fileData);
            if (!inferredChannel) {
                return null;
            }
            markMainImageChannelWarm(fileUUID, fileData, inferredChannel, mainImagePath);
            return inferredChannel;
        }

        function scheduleMainImageWarmup(fileUUID, fileData, activeChannel = null) {
            if (!fileUUID || !fileData) {
                return;
            }
            channels
                .filter((channel) => channel !== activeChannel)
                .forEach((channel) => {
                    void warmMainImageChannel(fileUUID, fileData, channel).catch(() => {});
                });
        }

        return {
            getMainImageWarmState,
            getMainImagePaths,
            markMainImageChannelWarm,
            fetchMainImageChannelUrl,
            resolveMainImageChannelUrl,
            warmMainImageChannel,
            resolveChannelIndexMap,
            inferChannelFromMainImage,
            primeMainImageWarmState,
            scheduleMainImageWarmup,
        };
    }

    function createStatisticsHelpers({
        tableFieldOrder,
        statFieldGroups,
        spatialFieldKinds,
        spatialHeaderBaseLabels,
        defaultSpatialStatsUnit,
        getCurrentSpatialStatsUnit,
        setCurrentSpatialStatsUnit,
    }) {
        function getVisibleTableFieldOrder(statistics) {
            return tableFieldOrder.slice();
        }

        function applyMetricVisibility(visibility) {
            document.querySelectorAll('[data-stat-section]').forEach((section) => {
                section.hidden = false;
            });
            document.querySelectorAll('[data-stat-row]').forEach((row) => {
                row.hidden = false;
            });
        }

        function normalizeSpatialUnit(unit) {
            return unit === 'um' ? 'um' : 'px';
        }

        function getCurrentSpatialUnit() {
            return normalizeSpatialUnit(getCurrentSpatialStatsUnit() || defaultSpatialStatsUnit);
        }

        function setCurrentSpatialUnit(unit) {
            setCurrentSpatialStatsUnit(normalizeSpatialUnit(unit));
        }

        function getScaleContext(fileData) {
            return fileData?.ScaleContext || {};
        }

        function getSpatialUnitSuffix(fieldName, unit) {
            const normalizedUnit = normalizeSpatialUnit(unit);
            if (spatialFieldKinds[fieldName] === 'area') {
                return normalizedUnit === 'um' ? 'µm²' : 'px²';
            }
            if (spatialFieldKinds[fieldName] === 'distance') {
                return normalizedUnit === 'um' ? 'µm' : 'px';
            }
            if (spatialFieldKinds[fieldName] === 'coordinate') {
                return normalizedUnit === 'um' ? '\u00B5m' : 'px';
            }
            return '';
        }

        function formatSpatialLabel(label, fieldName, unit) {
            const suffix = getSpatialUnitSuffix(fieldName, unit);
            if (!suffix) {
                return label;
            }
            return `${String(label || '').replace(/\s+\((?:px|µm|px²|µm²)\)$/u, '')} (${suffix})`;
        }

        function formatCoordinateValue(value, scaleContext, unit) {
            if (!value || typeof value !== 'object') {
                return 'N/A';
            }
            let xValue = Number(value.x_px);
            let yValue = Number(value.y_px);
            if (!Number.isFinite(xValue) || !Number.isFinite(yValue)) {
                return 'N/A';
            }
            if (normalizeSpatialUnit(unit) === 'um') {
                const effectiveScale = Number(scaleContext?.effective_um_per_px || 0.1);
                const xScale = Number(scaleContext?.x_um_per_px || effectiveScale || 0.1);
                const yScale = Number(scaleContext?.y_um_per_px || effectiveScale || 0.1);
                xValue *= xScale;
                yValue *= yScale;
            }
            return `${xValue.toFixed(3)}, ${yValue.toFixed(3)}`;
        }

        function convertSpatialValue(fieldName, value, cellStats, scaleContext, unit) {
            if (value === null || value === undefined || value === '') {
                return value;
            }
            const numericValue = Number(value);
            if (!Number.isFinite(numericValue) || normalizeSpatialUnit(unit) === 'px') {
                return numericValue;
            }
            const effectiveScale = Number(scaleContext?.effective_um_per_px || 0.1);
            const xScale = Number(scaleContext?.x_um_per_px || effectiveScale || 0.1);
            const yScale = Number(scaleContext?.y_um_per_px || effectiveScale || 0.1);
            if (spatialFieldKinds[fieldName] === 'area') {
                return numericValue * xScale * yScale;
            }
            if (spatialFieldKinds[fieldName] === 'distance') {
                const dx = Number(cellStats?.[`${fieldName}_delta_x_px`]);
                const dy = Number(cellStats?.[`${fieldName}_delta_y_px`]);
                if (Number.isFinite(dx) && Number.isFinite(dy)) {
                    return Math.hypot(dx * xScale, dy * yScale);
                }
                return numericValue * effectiveScale;
            }
            return numericValue;
        }

        function formatStatValue(value) {
            if (value === null || value === undefined || value === '') {
                return 'N/A';
            }
            if (typeof value === 'number') {
                if (Number.isInteger(value)) {
                    return String(value);
                }
                return value.toFixed(3);
            }
            return String(value);
        }

        function formatFieldValue(fieldName, value, cellStats, scaleContext) {
            if (Object.prototype.hasOwnProperty.call(spatialFieldKinds, fieldName)) {
                if (spatialFieldKinds[fieldName] === 'coordinate') {
                    return formatCoordinateValue(value, scaleContext, getCurrentSpatialUnit());
                }
                return formatStatValue(convertSpatialValue(fieldName, value, cellStats, scaleContext, getCurrentSpatialUnit()));
            }
            return formatStatValue(value);
        }

        function getDynamicSpatialHeaderLabel(fieldName, fileData) {
            if (fieldName === 'puncta_distance') {
                const statistics = fileData?.Statistics || {};
                const firstCellStats = Object.values(statistics).find((row) => row);
                const baseLabel = firstCellStats?.puncta_distance_label || 'Distance Between Red Puncta';
                return formatSpatialLabel(baseLabel, fieldName, getCurrentSpatialUnit());
            }
            return formatSpatialLabel(
                spatialHeaderBaseLabels[fieldName] || fieldName,
                fieldName,
                getCurrentSpatialUnit(),
            );
        }

        function updateSpatialUnitControls(fileData) {
            const activeUnit = getCurrentSpatialUnit();
            document.querySelectorAll('[data-spatial-unit-toggle]').forEach((toggle) => {
                toggle.dataset.activeUnit = activeUnit;
                toggle.querySelectorAll('[data-spatial-unit]').forEach((button) => {
                    const isActive = button.dataset.spatialUnit === activeUnit;
                    button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
                    button.classList.toggle('active', isActive);
                });
            });

            const headers = Array.from(document.querySelectorAll('#celltable thead th'));
            const visibleFieldOrder = getVisibleTableFieldOrder(fileData?.Statistics || {});
            visibleFieldOrder.forEach((fieldName, index) => {
                if (!Object.prototype.hasOwnProperty.call(spatialFieldKinds, fieldName) || !headers[index]) {
                    return;
                }
                headers[index].textContent = getDynamicSpatialHeaderLabel(fieldName, fileData);
            });
        }

        function bindSpatialUnitControls({
            getCurrentFileData = () => null,
            rerender = () => {},
            persistSpatialUnit = null,
            onError = () => {},
        } = {}) {
            document.querySelectorAll('[data-spatial-unit-toggle]').forEach((toggle) => {
                if (toggle.dataset.spatialUnitBound === 'true') {
                    return;
                }
                toggle.dataset.spatialUnitBound = 'true';
                toggle.querySelectorAll('[data-spatial-unit]').forEach((button) => {
                    button.addEventListener('click', async () => {
                        const nextUnit = normalizeSpatialUnit(button.dataset.spatialUnit || 'px');
                        if (nextUnit === getCurrentSpatialUnit()) {
                            return;
                        }
                        const previousUnit = getCurrentSpatialUnit();
                        setCurrentSpatialUnit(nextUnit);
                        updateSpatialUnitControls(getCurrentFileData());
                        rerender();
                        if (!persistSpatialUnit) {
                            return;
                        }
                        try {
                            const persistedUnit = await persistSpatialUnit(nextUnit);
                            setCurrentSpatialUnit(persistedUnit);
                            updateSpatialUnitControls(getCurrentFileData());
                            rerender();
                        } catch (error) {
                            setCurrentSpatialUnit(previousUnit);
                            updateSpatialUnitControls(getCurrentFileData());
                            rerender();
                            onError(error);
                        }
                    });
                });
            });
            updateSpatialUnitControls(getCurrentFileData());
        }

        function hasNoNucleusContour(cellStats) {
            return Boolean(cellStats && cellStats.nuclear_cell_pair_status === 'no_nucleus_contour');
        }

        function getNuclearLabelPair(mode) {
            if (mode === 'red_nucleus') {
                return {
                    cellular: 'Green Cell-Pair Intensity',
                    nuclear: 'Green Nuclear Intensity',
                    contour: 'Red',
                    measurement: 'Green',
                };
            }
            if (mode === 'green_nucleus') {
                return {
                    cellular: 'Red Cell-Pair Intensity',
                    nuclear: 'Red Nuclear Intensity',
                    contour: 'Green',
                    measurement: 'Red',
                };
            }
            return {
                cellular: 'Measured Cell-Pair Intensity',
                nuclear: 'Measured Nuclear Intensity',
                contour: 'N/A',
                measurement: 'N/A',
            };
        }

        function renderStatisticsTable(statistics, fileData) {
            const table = document.getElementById('celltable');
            if (!table) return 0;
            const tbody = table.querySelector('tbody');
            if (!tbody) return 0;
            const nuclearCellularFields = new Set([
                'cell_pair_intensity_sum',
                'nucleus_intensity_sum',
                'cytoplasmic_intensity',
                'nuclear_cytoplasmic_ratio',
            ]);
            const scaleContext = getScaleContext(fileData);
            updateSpatialUnitControls(fileData);
            const visibleFieldOrder = getVisibleTableFieldOrder(statistics);

            const ids = Object.keys(statistics || {})
                .map((k) => Number(k))
                .filter((n) => (
                    !Number.isNaN(n)
                    && statistics[String(n)]
                    && typeof statistics[String(n)] === 'object'
                ))
                .sort((a, b) => a - b);

            tbody.innerHTML = '';
            for (const id of ids) {
                const rowStats = statistics[String(id)] || null;
                const tr = document.createElement('tr');
                for (const fieldName of visibleFieldOrder) {
                    const td = document.createElement('td');
                    if (fieldName === 'cell_id') {
                        td.textContent = String(id);
                    } else if (fieldName === 'category_cen_dot') {
                        td.textContent = rowStats ? (rowStats.category_cen_dot_label || 'N/A') : 'N/A';
                    } else if (fieldName === 'cell_parentage') {
                        td.textContent = rowStats ? (rowStats.cell_parentage_label || 'Not identified') : 'N/A';
                    } else if (nuclearCellularFields.has(fieldName) && hasNoNucleusContour(rowStats)) {
                        td.textContent = 'N/A';
                    } else {
                        td.textContent = formatFieldValue(
                            fieldName,
                            rowStats ? rowStats[fieldName] : null,
                            rowStats,
                            scaleContext,
                        );
                    }
                    tr.appendChild(td);
                }
                tbody.appendChild(tr);
            }
            return ids.length;
        }

        function getStatisticsTableRowCount(fileData, renderedRowCount = 0) {
            const statistics = fileData?.Statistics || {};
            const serializedRows = Object.values(statistics).filter(
                (row) => row && typeof row === 'object',
            ).length;
            return Math.max(
                Number(renderedRowCount) || 0,
                serializedRows,
            );
        }

        function hasStatisticsTableRows(fileData, renderedRowCount = 0) {
            return getStatisticsTableRowCount(fileData, renderedRowCount) > 0;
        }

        return {
            getVisibleTableFieldOrder,
            applyMetricVisibility,
            normalizeSpatialUnit,
            getCurrentSpatialUnit,
            setCurrentSpatialUnit,
            getScaleContext,
            getSpatialUnitSuffix,
            formatSpatialLabel,
            formatCoordinateValue,
            convertSpatialValue,
            formatFieldValue,
            getDynamicSpatialHeaderLabel,
            updateSpatialUnitControls,
            bindSpatialUnitControls,
            formatStatValue,
            hasNoNucleusContour,
            getNuclearLabelPair,
            renderStatisticsTable,
            getStatisticsTableRowCount,
            hasStatisticsTableRows,
        };
    }

    global.CytoCVResultsViewerShared = {
        readJsonConfig,
        createBlendHelpers,
        getContourToggleState,
        getVisibleCellImageUrls,
        defaultStatVisibility,
        getStatVisibility,
        ensureChannelMessageContainer,
        showChannelError,
        preloadImage,
        preloadImageSet,
        getSortedCellIds,
        getWarmPriorityOffsets,
        buildFullCircularCellOrder,
        getCircularWarmQueue,
        normalizeMainImageChannel,
        setActiveChannel,
        createMainImageHelpers,
        createStatisticsHelpers,
    };
})(window);
