// Shared Display/Dashboard viewer primitives. Both page controllers depend on
// this global namespace, so exported helper names and payload assumptions are
// treated as frontend contracts by the static contract tests.
(function (global) {
    'use strict';

    function readJsonConfig(scriptId) {
        // Templates render page configuration in JSON script tags; missing tags
        // fall back to an empty object so inactive pages can share this bundle.
        const node = document.getElementById(scriptId);
        return JSON.parse(node ? node.textContent || '{}' : '{}');
    }

    // Blend helpers are shared so Display and Dashboard update file/cell content
    // with the same reduced-motion and placeholder behavior.
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

    const OVERLAY_FAMILY_DEFINITIONS = Object.freeze([
        Object.freeze({ key: 'cellBoundary', label: 'Cell boundary', shortLabel: 'Cell' }),
        Object.freeze({ key: 'redContours', label: 'Red contours', shortLabel: 'Red' }),
        Object.freeze({ key: 'greenContours', label: 'Green contours', shortLabel: 'Green' }),
        Object.freeze({ key: 'blueContour', label: 'Blue contour', shortLabel: 'Blue' }),
        Object.freeze({ key: 'analysisAnnotations', label: 'Analysis annotations', shortLabel: 'Analysis' }),
    ]);
    const OVERLAY_FAMILY_KEYS = Object.freeze(
        OVERLAY_FAMILY_DEFINITIONS.map(({ key }) => key)
    );
    const OVERLAY_CHANNELS = Object.freeze(['dic', 'blue', 'red', 'green']);
    const OVERLAY_RENDER_ORDER = Object.freeze([
        'cellBoundary',
        'redContours',
        'blueContour',
        'greenContours',
        'analysisAnnotations',
    ]);
    const RAW_CELL_IMAGE_INDICES = Object.freeze([1, 3, 5, 7]);
    const AGGREGATE_CELL_IMAGE_INDICES = Object.freeze([0, 2, 4, 6]);

    function defaultOverlayVisibility() {
        return Object.fromEntries(OVERLAY_FAMILY_KEYS.map((key) => [key, true]));
    }

    function normalizeOverlayVisibility(value) {
        const source = value && typeof value === 'object' && !Array.isArray(value)
            ? value
            : {};
        return Object.fromEntries(
            OVERLAY_FAMILY_KEYS.map((key) => [
                key,
                typeof source[key] === 'boolean' ? source[key] : true,
            ])
        );
    }

    function getOverlaySelectionSignature(value) {
        const normalized = normalizeOverlayVisibility(value);
        return OVERLAY_FAMILY_KEYS
            .map((key) => `${key}:${normalized[key] ? '1' : '0'}`)
            .join('|');
    }

    function normalizeOverlayLayerContract(value) {
        const source = value && typeof value === 'object' && !Array.isArray(value)
            ? value
            : {};
        const availableSource = (
            source.availableFamilies
            && typeof source.availableFamilies === 'object'
            && !Array.isArray(source.availableFamilies)
        ) ? source.availableFamilies : {};
        const templatesSource = (
            source.layerUrlTemplates
            && typeof source.layerUrlTemplates === 'object'
            && !Array.isArray(source.layerUrlTemplates)
        ) ? source.layerUrlTemplates : {};
        const availableFamilies = Object.fromEntries(
            OVERLAY_FAMILY_KEYS.map((key) => [key, availableSource[key] === true])
        );
        const layerUrlTemplates = {};
        OVERLAY_FAMILY_KEYS.forEach((family) => {
            const channels = templatesSource[family];
            if (!channels || typeof channels !== 'object' || Array.isArray(channels)) {
                return;
            }
            const normalizedChannels = {};
            OVERLAY_CHANNELS.forEach((channel) => {
                if (typeof channels[channel] === 'string' && channels[channel]) {
                    normalizedChannels[channel] = channels[channel];
                }
            });
            if (Object.keys(normalizedChannels).length) {
                layerUrlTemplates[family] = normalizedChannels;
            }
        });
        return {
            schemaVersion: Number(source.schemaVersion) || 0,
            selective: source.selective === true,
            aggregateAvailable: source.aggregateAvailable !== false,
            availableFamilies,
            layerUrlTemplates,
        };
    }

    function intersectOverlayVisibility(selection, availability) {
        const normalizedSelection = normalizeOverlayVisibility(selection);
        const normalizedAvailability = availability
            && typeof availability === 'object'
            && !Array.isArray(availability)
            ? availability
            : {};
        return Object.fromEntries(
            OVERLAY_FAMILY_KEYS.map((key) => [
                key,
                normalizedSelection[key] && normalizedAvailability[key] === true,
            ])
        );
    }

    function getOverlaySelectionSummary(selection, availability = null) {
        const normalized = normalizeOverlayVisibility(selection);
        const state = availability
            ? intersectOverlayVisibility(normalized, availability)
            : normalized;
        const applicableKeys = availability
            ? OVERLAY_FAMILY_KEYS.filter((key) => availability[key] === true)
            : [...OVERLAY_FAMILY_KEYS];
        const selectedDefinitions = OVERLAY_FAMILY_DEFINITIONS.filter(
            ({ key }) => state[key] && applicableKeys.includes(key)
        );
        if (!selectedDefinitions.length) {
            return 'None';
        }
        if (
            applicableKeys.length > 0
            && selectedDefinitions.length === applicableKeys.length
        ) {
            return 'All';
        }
        if (selectedDefinitions.length === 1) {
            return selectedDefinitions[0].shortLabel;
        }
        return `${selectedDefinitions.length} selected`;
    }

    function getOverlayContractSelectionSummary(selection, overlayContract) {
        const normalizedSelection = normalizeOverlayVisibility(selection);
        const contract = normalizeOverlayLayerContract(overlayContract);
        if (!contract.selective) {
            return OVERLAY_FAMILY_KEYS.every((key) => normalizedSelection[key])
                ? 'All'
                : 'None';
        }
        return getOverlaySelectionSummary(
            normalizedSelection,
            contract.availableFamilies,
        );
    }

    function overlayTemplateUrl(template, cellId) {
        if (typeof template !== 'string' || !template) {
            return '';
        }
        return template.replace('{cellId}', encodeURIComponent(String(cellId)));
    }

    function getCellOverlayRenderState(
        imageUrls,
        overlayContract,
        cellId,
        selection,
        noCellPlaceholder,
    ) {
        const images = Array.isArray(imageUrls) ? imageUrls : [];
        const contract = normalizeOverlayLayerContract(overlayContract);
        const selected = normalizeOverlayVisibility(selection);
        const effective = intersectOverlayVisibility(
            selected,
            contract.availableFamilies,
        );
        const availableKeys = OVERLAY_FAMILY_KEYS.filter(
            (key) => contract.availableFamilies[key]
        );
        const allEffectiveSelected = availableKeys.length > 0
            && availableKeys.every((key) => effective[key]);
        const noneEffectiveSelected = !availableKeys.some((key) => effective[key]);
        const everyGlobalFamilySelected = OVERLAY_FAMILY_KEYS.every((key) => selected[key]);
        const renderModeByChannel = Object.fromEntries(
            OVERLAY_CHANNELS.map((channel) => {
                if (!contract.selective) {
                    const mode = contract.aggregateAvailable && everyGlobalFamilySelected
                        ? 'aggregate'
                        : 'raw';
                    return [channel, mode];
                }
                if (noneEffectiveSelected) {
                    return [channel, 'raw'];
                }

                const applicableFamilies = OVERLAY_RENDER_ORDER.filter((family) => (
                    contract.availableFamilies[family]
                    && typeof contract.layerUrlTemplates[family]?.[channel] === 'string'
                ));
                const allChannelFamiliesSelected = applicableFamilies.every(
                    (family) => effective[family]
                );
                if (
                    contract.aggregateAvailable
                    && (allEffectiveSelected || allChannelFamiliesSelected)
                ) {
                    return [channel, 'aggregate'];
                }
                const hasSelectedLayer = applicableFamilies.some(
                    (family) => effective[family]
                );
                return [channel, hasSelectedLayer ? 'layered' : 'raw'];
            })
        );
        const baseUrls = OVERLAY_CHANNELS.map((channel, channelIndex) => {
            const renderMode = renderModeByChannel[channel];
            const index = renderMode === 'aggregate'
                ? AGGREGATE_CELL_IMAGE_INDICES[channelIndex]
                : RAW_CELL_IMAGE_INDICES[channelIndex];
            const candidate = images[index] || '';
            if (
                contract.selective
                && renderMode !== 'aggregate'
                && candidate
                && candidate === images[AGGREGATE_CELL_IMAGE_INDICES[channelIndex]]
            ) {
                // Dashboard legacy recovery can substitute the aggregate when a
                // raw crop is absent. Selective states must use a placeholder
                // instead of silently reintroducing every annotation family.
                return noCellPlaceholder;
            }
            return candidate || noCellPlaceholder;
        });
        // Aggregate failures may safely degrade to the raw crop. Mixed/None
        // states must never fall back to an aggregate that would reintroduce
        // hidden families or lazily generate an overlay.
        const fallbackBaseUrls = OVERLAY_CHANNELS.map((channel, channelIndex) => (
            renderModeByChannel[channel] === 'aggregate'
                ? images[RAW_CELL_IMAGE_INDICES[channelIndex]] || noCellPlaceholder
                : noCellPlaceholder
        ));
        const layersByChannel = Object.fromEntries(
            OVERLAY_CHANNELS.map((channel) => [channel, []])
        );
        if (contract.selective) {
            OVERLAY_RENDER_ORDER.forEach((family) => {
                if (!effective[family]) {
                    return;
                }
                const templates = contract.layerUrlTemplates[family] || {};
                OVERLAY_CHANNELS.forEach((channel) => {
                    if (renderModeByChannel[channel] !== 'layered') {
                        return;
                    }
                    const url = overlayTemplateUrl(templates[channel], cellId);
                    if (url) {
                        layersByChannel[channel].push({ family, url });
                    }
                });
            });
        }
        const layerUrls = OVERLAY_CHANNELS.flatMap(
            (channel) => layersByChannel[channel].map(({ url }) => url)
        );
        const aggregateOverlayUrls = OVERLAY_CHANNELS.flatMap((channel, channelIndex) => {
            const url = baseUrls[channelIndex];
            return (
                renderModeByChannel[channel] === 'aggregate'
                && typeof url === 'string'
                && url.includes('/overlay/')
            ) ? [url] : [];
        });
        return {
            selected,
            effective,
            renderModeByChannel,
            baseUrls,
            fallbackBaseUrls,
            placeholderUrl: noCellPlaceholder,
            layersByChannel,
            layerUrls,
            preloadUrls: [...new Set([...baseUrls, ...layerUrls])],
            usefulOverlayUrls: [...new Set([...aggregateOverlayUrls, ...layerUrls])],
        };
    }

    function setCellImageStack(
        baseImage,
        channel,
        renderState,
        setImageWithBlend,
        options = {},
    ) {
        if (!baseImage) {
            return Promise.resolve();
        }
        const frame = baseImage.closest('[data-cell-image-frame]') || baseImage.parentElement;
        if (frame) {
            frame.querySelectorAll('.cell-overlay-layer').forEach((element) => element.remove());
            (renderState?.layersByChannel?.[channel] || []).forEach(({ family, url }) => {
                const layer = document.createElement('img');
                layer.className = 'cell-overlay-layer';
                layer.alt = '';
                layer.setAttribute('aria-hidden', 'true');
                layer.dataset.overlayFamily = family;
                layer.addEventListener('error', () => layer.remove(), { once: true });
                layer.src = url;
                frame.appendChild(layer);
            });
        }
        const channelIndex = OVERLAY_CHANNELS.indexOf(channel);
        const nextBase = renderState?.baseUrls?.[channelIndex];
        const fallbackBase = renderState?.fallbackBaseUrls?.[channelIndex];
        const placeholder = renderState?.placeholderUrl || '';
        baseImage.onerror = () => {
            const currentSrc = baseImage.getAttribute('src') || '';
            if (fallbackBase && currentSrc !== fallbackBase && currentSrc !== placeholder) {
                baseImage.src = fallbackBase;
                return;
            }
            if (placeholder && currentSrc !== placeholder) {
                baseImage.src = placeholder;
                return;
            }
            baseImage.onerror = null;
        };
        return setImageWithBlend(baseImage, nextBase, options);
    }

    function getMissingCellImageStackUrls(baseImages, renderState) {
        const currentUrls = new Set();
        Array.from(baseImages || []).forEach((baseImage) => {
            if (!baseImage) {
                return;
            }
            const baseUrl = baseImage.getAttribute('src') || '';
            if (baseUrl) {
                currentUrls.add(baseUrl);
            }
            const frame = baseImage.closest('[data-cell-image-frame]') || baseImage.parentElement;
            frame?.querySelectorAll('.cell-overlay-layer').forEach((layer) => {
                const layerUrl = layer.getAttribute('src') || '';
                if (layerUrl) {
                    currentUrls.add(layerUrl);
                }
            });
        });
        return (renderState?.preloadUrls || []).filter((url) => !currentUrls.has(url));
    }

    function createOverlayVisibilityController({
        contractProvider = () => ({}),
        onChange = () => {},
    } = {}) {
        const root = document.querySelector('[data-overlay-visibility-control]');
        const trigger = root?.querySelector('#overlayVisibilityTrigger');
        const menu = root?.querySelector('#overlayVisibilityMenu');
        const summary = root?.querySelector('[data-overlay-visibility-summary]');
        const familyInputs = root
            ? Array.from(root.querySelectorAll('[data-overlay-family]'))
            : [];
        const selectAllButton = root?.querySelector('[data-overlay-select-all]');
        const clearButton = root?.querySelector('[data-overlay-clear]');
        const legacyNote = root?.querySelector('[data-overlay-legacy-note]');
        let selected = defaultOverlayVisibility();
        let contract = normalizeOverlayLayerContract(contractProvider());
        let bound = false;

        function close({ returnFocus = false } = {}) {
            if (!trigger || !menu || menu.hidden) {
                return;
            }
            menu.hidden = true;
            trigger.setAttribute('aria-expanded', 'false');
            if (returnFocus) {
                trigger.focus();
            }
        }

        function open() {
            if (!trigger || !menu) {
                return;
            }
            menu.hidden = false;
            trigger.setAttribute('aria-expanded', 'true');
            const firstEnabled = familyInputs.find((input) => !input.disabled);
            (firstEnabled || selectAllButton)?.focus();
        }

        function sync() {
            familyInputs.forEach((input) => {
                const family = input.dataset.overlayFamily;
                input.checked = selected[family] === true;
                input.disabled = !contract.selective || !contract.availableFamilies[family];
            });
            if (legacyNote) {
                legacyNote.hidden = contract.selective;
            }
            if (summary) {
                const summaryText = getOverlayContractSelectionSummary(
                    selected,
                    contract,
                );
                summary.textContent = summaryText;
                document.querySelectorAll('[data-overlay-state-value]').forEach((element) => {
                    element.textContent = summaryText;
                });
            }
        }

        function notify() {
            sync();
            void onChange(normalizeOverlayVisibility(selected));
        }

        function setSelected(nextSelection, { notifyChange = true } = {}) {
            selected = normalizeOverlayVisibility(nextSelection);
            if (notifyChange) {
                notify();
            } else {
                sync();
            }
            return getSelected();
        }

        function getSelected() {
            return normalizeOverlayVisibility(selected);
        }

        function refreshContract(nextContract = contractProvider()) {
            contract = normalizeOverlayLayerContract(nextContract);
            sync();
            return contract;
        }

        function bind() {
            if (bound || !root || !trigger || !menu) {
                sync();
                return;
            }
            bound = true;
            trigger.addEventListener('click', () => {
                if (menu.hidden) {
                    open();
                } else {
                    close();
                }
            });
            familyInputs.forEach((input) => {
                input.addEventListener('change', () => {
                    selected = {
                        ...selected,
                        [input.dataset.overlayFamily]: input.checked,
                    };
                    notify();
                });
            });
            selectAllButton?.addEventListener('click', () => {
                selected = defaultOverlayVisibility();
                notify();
            });
            clearButton?.addEventListener('click', () => {
                selected = Object.fromEntries(
                    OVERLAY_FAMILY_KEYS.map((key) => [key, false])
                );
                notify();
            });
            document.addEventListener('keydown', (event) => {
                if (event.key === 'Escape' && !menu.hidden) {
                    event.preventDefault();
                    close({ returnFocus: true });
                }
            });
            document.addEventListener('pointerdown', (event) => {
                if (!menu.hidden && !root.contains(event.target)) {
                    close();
                }
            });
            document.addEventListener('focusin', (event) => {
                if (!menu.hidden && !root.contains(event.target)) {
                    close();
                }
            });
            sync();
        }

        return {
            bind,
            close,
            getSelected,
            refreshContract,
            setSelected,
        };
    }

    const CELL_CARD_SIGNAL_MODES = {
        puncta: 'puncta_distance',
        nuclear: 'nuclear_cell_pair',
    };
    const CONTOUR_INTENSITY_COMBINATIONS = [
        ['red_in_red', 'Red In Red', 'redInRedIntensity'],
        ['green_in_red', 'Green In Red', 'greenInRedIntensity'],
        ['red_in_green', 'Red In Green', 'redInGreenIntensity'],
        ['green_in_green', 'Green In Green', 'greenInGreenIntensity'],
    ];
    const CONTOUR_INTENSITY_COMBINATION_KEYS = CONTOUR_INTENSITY_COMBINATIONS.map(
        ([combination]) => combination
    );
    const SINGLE_CHANNEL_CONTOUR_INTENSITY_COMBINATIONS = {
        red_puncta_only: ['red_in_red'],
        green_puncta_only: ['green_in_green'],
    };
    const CONTOUR_INTENSITY_STATISTICS = {
        total: 'Total',
        max: 'Max',
        average: 'Average',
    };
    const CONTOUR_INTENSITY_SLOTS = [1, 2, 3];

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

    function normalizeCellCardSignalMode(value) {
        const raw = String(value ?? '').trim().toLowerCase();
        if (raw === 'nuclear_cell_pair' || raw === 'nuclearcellpairintensity' || raw === 'nuclear') {
            return CELL_CARD_SIGNAL_MODES.nuclear;
        }
        if (raw === 'puncta_distance' || raw === 'punctadistance' || raw === 'puncta') {
            return CELL_CARD_SIGNAL_MODES.puncta;
        }
        return null;
    }

    function selectedAnalysisIncludes(cellStats, pluginId) {
        const selectedAnalysis = Array.isArray(cellStats?.selected_analysis)
            ? cellStats.selected_analysis
            : [];
        return selectedAnalysis.some((value) => String(value || '').trim() === pluginId);
    }

    function getEffectiveCellCardMode(cellStats) {
        const explicitMode = normalizeCellCardSignalMode(cellStats?.signal_quantification_mode);
        if (explicitMode) return explicitMode;

        const visibility = cellStats && typeof cellStats.stat_visibility === 'object'
            ? cellStats.stat_visibility
            : null;
        if (
            visibility
            && visibility.nuclear_cell_pair_intensity !== false
            && visibility.puncta_distance === false
        ) {
            return CELL_CARD_SIGNAL_MODES.nuclear;
        }

        if (
            selectedAnalysisIncludes(cellStats, 'NuclearCellPairIntensity')
            && !selectedAnalysisIncludes(cellStats, 'PunctaDistance')
        ) {
            return CELL_CARD_SIGNAL_MODES.nuclear;
        }

        return CELL_CARD_SIGNAL_MODES.puncta;
    }

    function hasUsableCellCardValue(cellStats, fieldNames) {
        if (!cellStats || typeof cellStats !== 'object') return false;
        return fieldNames.some((fieldName) => {
            const value = cellStats[fieldName];
            return value !== null && value !== undefined && value !== '';
        });
    }

    function normalizeContourIntensityDisplayType(type = 'total') {
        return Object.prototype.hasOwnProperty.call(CONTOUR_INTENSITY_STATISTICS, type)
            ? type
            : 'total';
    }

    function getContourIntensityDisplayFields(type = 'total') {
        const statistic = normalizeContourIntensityDisplayType(type);
        const statisticLabel = CONTOUR_INTENSITY_STATISTICS[statistic];
        const fields = [];
        CONTOUR_INTENSITY_COMBINATIONS.forEach(([combination, label, metricPrefix]) => {
            CONTOUR_INTENSITY_SLOTS.forEach((slot) => {
                fields.push({
                    combination,
                    combinationLabel: label,
                    statistic,
                    statisticLabel,
                    slot,
                    fieldName: `${combination}_${statistic}_intensity_${slot}`,
                    label: `${label} ${statisticLabel} Intensity ${slot}`,
                    metricId: `${metricPrefix}${slot}`,
                });
            });
        });
        return fields;
    }

    function getAllContourIntensityDisplayFields() {
        return Object.keys(CONTOUR_INTENSITY_STATISTICS).flatMap((statistic) => (
            getContourIntensityDisplayFields(statistic)
        ));
    }

    function getContourIntensityFieldNamesForCombinations(combinations) {
        const requestedCombinations = new Set(
            (Array.isArray(combinations) ? combinations : CONTOUR_INTENSITY_COMBINATION_KEYS)
                .map((combination) => String(combination || '').trim())
                .filter((combination) => CONTOUR_INTENSITY_COMBINATION_KEYS.includes(combination))
        );
        if (!requestedCombinations.size) return [];
        return getAllContourIntensityDisplayFields()
            .filter((field) => requestedCombinations.has(field.combination))
            .map((field) => field.fieldName);
    }

    function getForcedContourIntensityCombinations(cellStats) {
        const mode = String(cellStats?.puncta_line_mode || '').trim();
        return SINGLE_CHANNEL_CONTOUR_INTENSITY_COMBINATIONS[mode] || null;
    }

    function getVisibleContourIntensityCombinations(cellStats) {
        if (!cellStats || typeof cellStats !== 'object') return [];
        const forcedCombinations = getForcedContourIntensityCombinations(cellStats);
        if (forcedCombinations) return forcedCombinations.slice();
        return CONTOUR_INTENSITY_COMBINATION_KEYS.filter((combination) => (
            hasUsableCellCardValue(
                cellStats,
                getContourIntensityFieldNamesForCombinations([combination])
            )
        ));
    }

    function setContourIntensityDisplayButtonState(activeType = 'total') {
        const normalizedType = normalizeContourIntensityDisplayType(activeType);
        document.querySelectorAll('.contour-intensity-toggle').forEach((toggle) => {
            toggle.dataset.activeIntensity = normalizedType;
        });
        document.querySelectorAll('[data-contour-intensity-display]').forEach((button) => {
            const buttonType = normalizeContourIntensityDisplayType(button.dataset.contourIntensityDisplay);
            const isActive = buttonType === normalizedType;
            button.classList.toggle('active', isActive);
            button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
    }

    function bindContourIntensityDisplayControls({
        getCurrentType = () => 'total',
        setCurrentType = () => {},
        rerender = () => {},
    } = {}) {
        setContourIntensityDisplayButtonState(getCurrentType());
        document.querySelectorAll('[data-contour-intensity-display]').forEach((button) => {
            if (button.dataset.contourIntensityBound === 'true') return;
            button.dataset.contourIntensityBound = 'true';
            button.addEventListener('click', () => {
                const nextType = normalizeContourIntensityDisplayType(button.dataset.contourIntensityDisplay);
                if (nextType === normalizeContourIntensityDisplayType(getCurrentType())) return;
                setCurrentType(nextType);
                setContourIntensityDisplayButtonState(nextType);
                rerender(nextType);
            });
        });
    }

    function getVisibleCellCardSections(cellStats) {
        const visibility = getStatVisibility(cellStats);
        const mode = getEffectiveCellCardMode(cellStats);
        const hasCellStats = !!(cellStats && typeof cellStats === 'object');
        const visibleContourIntensityCombinations = getVisibleContourIntensityCombinations(cellStats);
        const contourFields = getContourIntensityFieldNamesForCombinations(
            visibleContourIntensityCombinations
        );
        const ratioFields = [
            'measurement_contour_ratio_1',
            'measurement_contour_ratio_2',
            'measurement_contour_ratio_3',
        ];
        const redGreenVisible = hasCellStats
            && mode === CELL_CARD_SIGNAL_MODES.puncta
            && visibility.red_green_intensity !== false;

        return {
            reference: true,
            nuclear_cell_pair_intensity: hasCellStats
                && mode === CELL_CARD_SIGNAL_MODES.nuclear
                && visibility.nuclear_cell_pair_intensity !== false,
            puncta_distance: hasCellStats
                && mode === CELL_CARD_SIGNAL_MODES.puncta
                && visibility.puncta_distance !== false,
            biorientation: hasCellStats
                && mode === CELL_CARD_SIGNAL_MODES.puncta
                && visibility.biorientation !== false,
            cen_dot: hasCellStats
                && mode === CELL_CARD_SIGNAL_MODES.puncta
                && visibility.cen_dot !== false,
            measurement_contour: redGreenVisible && (
                hasUsableCellCardValue(cellStats, ratioFields)
                || (
                    cellStats.measurement_contour_ratio_display_text
                    && cellStats.measurement_contour_ratio_display_text !== 'N/A'
                )
            ),
            contour_intensity: redGreenVisible
                && visibleContourIntensityCombinations.length > 0
                && hasUsableCellCardValue(cellStats, contourFields),
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

    function setCellPairImagesLoading(isLoading, root = null) {
        const loading = !!isLoading;
        const searchRoot = root || (typeof document !== 'undefined' ? document : null);
        const frames = searchRoot && typeof searchRoot.querySelectorAll === 'function'
            ? searchRoot.querySelectorAll('[data-cell-image-frame]')
            : [];
        frames.forEach((frame) => {
            frame.classList.toggle('is-cell-image-loading', loading);
            frame.setAttribute('aria-busy', loading ? 'true' : 'false');
        });
        return frames.length;
    }

    function setCellDataRegionLoading(isLoading, root = null) {
        const loading = !!isLoading;
        const searchRoot = root || (typeof document !== 'undefined' ? document : null);
        const regions = (
            searchRoot
            && typeof searchRoot.querySelector === 'function'
            && typeof searchRoot.querySelectorAll === 'function'
        )
            ? [
                searchRoot.querySelector('#tableScrollFrame'),
                ...searchRoot.querySelectorAll('[data-ui-region="cell-metrics-strip"]'),
            ].filter(Boolean)
            : [];
        regions.forEach((region) => {
            region.classList.toggle('is-contour-filter-applying', loading);
            region.setAttribute('aria-busy', loading ? 'true' : 'false');
        });
        return regions.length;
    }

    function createCellDataRegionLoadingController({
        minimumDurationMs = 160,
        root = null,
        getNow = null,
        wait = null,
    } = {}) {
        let activeToken = 0;
        const readNow = typeof getNow === 'function'
            ? getNow
            : () => (
                typeof performance !== 'undefined' && typeof performance.now === 'function'
                    ? performance.now()
                    : Date.now()
            );
        const sleep = typeof wait === 'function'
            ? wait
            : (delayMs) => new Promise((resolve) => {
                const setTimeoutFn = (
                    typeof window !== 'undefined' && typeof window.setTimeout === 'function'
                )
                    ? window.setTimeout.bind(window)
                    : setTimeout;
                setTimeoutFn(resolve, delayMs);
            });

        return {
            async run(callback) {
                const token = ++activeToken;
                const startedAt = readNow();
                setCellDataRegionLoading(true, root);

                try {
                    if (typeof callback === 'function') {
                        return await callback();
                    }
                    return undefined;
                } finally {
                    const elapsed = Math.max(0, readNow() - startedAt);
                    const remaining = Math.max(0, minimumDurationMs - elapsed);
                    if (remaining > 0) {
                        await sleep(remaining);
                    }
                    if (token === activeToken) {
                        setCellDataRegionLoading(false, root);
                    }
                }
            },
            clear() {
                activeToken += 1;
                setCellDataRegionLoading(false, root);
            },
        };
    }

    function bindFilterMenuPointerAwayClose({
        control,
        button,
        menu,
        closeMenu,
        margin = 36,
        closeDelayMs = 160,
    } = {}) {
        if (
            !control
            || !button
            || !menu
            || typeof closeMenu !== 'function'
            || typeof document === 'undefined'
        ) {
            return () => {};
        }

        let closeTimer = null;
        const clearCloseTimer = () => {
            if (!closeTimer) return;
            window.clearTimeout(closeTimer);
            closeTimer = null;
        };
        const isMenuOpen = () => (
            !menu.hidden
            && button.getAttribute('aria-expanded') === 'true'
        );
        const combinedRect = () => {
            const rects = [control, menu]
                .filter(Boolean)
                .map((element) => element.getBoundingClientRect());
            if (!rects.length) return null;
            return rects.reduce((bounds, rect) => ({
                top: Math.min(bounds.top, rect.top),
                right: Math.max(bounds.right, rect.right),
                bottom: Math.max(bounds.bottom, rect.bottom),
                left: Math.min(bounds.left, rect.left),
            }));
        };
        const isPointerInsideGraceArea = (event) => {
            const rect = combinedRect();
            if (!rect) return false;
            return (
                event.clientX >= rect.left - margin
                && event.clientX <= rect.right + margin
                && event.clientY >= rect.top - margin
                && event.clientY <= rect.bottom + margin
            );
        };
        const scheduleClose = () => {
            if (closeTimer) return;
            closeTimer = window.setTimeout(() => {
                closeTimer = null;
                closeMenu();
            }, closeDelayMs);
        };
        const handlePointerMove = (event) => {
            if (!isMenuOpen()) {
                clearCloseTimer();
                return;
            }
            if (event.pointerType && event.pointerType !== 'mouse' && event.pointerType !== 'pen') {
                return;
            }
            if (isPointerInsideGraceArea(event)) {
                clearCloseTimer();
            } else {
                scheduleClose();
            }
        };

        document.addEventListener('pointermove', handlePointerMove, { passive: true });
        return () => {
            clearCloseTimer();
            document.removeEventListener('pointermove', handlePointerMove);
        };
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

        function applyMetricVisibility(
            visibility,
            {
                mode = CELL_CARD_SIGNAL_MODES.puncta,
                contourIntensityCombinations = CONTOUR_INTENSITY_COMBINATION_KEYS,
            } = {}
        ) {
            const sections = visibility && typeof visibility === 'object'
                ? visibility
                : { reference: true };
            const normalizedMode = normalizeCellCardSignalMode(mode) || CELL_CARD_SIGNAL_MODES.puncta;
            const visibleContourIntensityCombinations = new Set(
                (Array.isArray(contourIntensityCombinations)
                    ? contourIntensityCombinations
                    : CONTOUR_INTENSITY_COMBINATION_KEYS
                )
                    .map((combination) => String(combination || '').trim())
                    .filter((combination) => CONTOUR_INTENSITY_COMBINATION_KEYS.includes(combination))
            );
            document.querySelectorAll('[data-cell-card-root]').forEach((root) => {
                root.dataset.cellCardMode = normalizedMode;
                root.dataset.contourIntensityCombinationCount = String(
                    visibleContourIntensityCombinations.size
                );
            });
            document.querySelectorAll('[data-contour-intensity-combination]').forEach((combinationSection) => {
                const combination = combinationSection.dataset.contourIntensityCombination;
                combinationSection.hidden = !visibleContourIntensityCombinations.has(combination);
            });
            document.querySelectorAll('[data-cell-card-section]').forEach((section) => {
                const sectionName = section.dataset.cellCardSection;
                section.hidden = sectionName && Object.prototype.hasOwnProperty.call(sections, sectionName)
                    ? !sections[sectionName]
                    : false;
            });
            document.querySelectorAll('[data-stat-section]:not([data-cell-card-section])').forEach((section) => {
                const sectionName = section.dataset.statSection;
                section.hidden = sectionName && Object.prototype.hasOwnProperty.call(sections, sectionName)
                    ? !sections[sectionName]
                    : false;
            });
            document.querySelectorAll('[data-stat-row]').forEach((row) => {
                const rowName = row.dataset.statRow;
                row.hidden = rowName && Object.prototype.hasOwnProperty.call(sections, rowName)
                    ? !sections[rowName]
                    : false;
            });
            document.querySelectorAll('[data-cell-card-detail-row]').forEach((row) => {
                const hasVisibleSection = Array.from(row.querySelectorAll('[data-cell-card-section]')).some((section) => (
                    !section.hidden
                ));
                row.hidden = !hasVisibleSection;
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

        function normalizePunctaSourceContourCountFilter(value) {
            const raw = String(value ?? '').trim().toLowerCase();
            if (raw === 'exactly_1' || raw === '1') return 'exactly_1';
            if (raw === 'exactly_2' || raw === '2') return 'exactly_2';
            return 'all';
        }

        function getPunctaSourceContourCountFilterLabel(value) {
            const normalized = normalizePunctaSourceContourCountFilter(value);
            if (normalized === 'exactly_1') return '1 contour';
            if (normalized === 'exactly_2') return '2 contours';
            return 'All cells';
        }

        function normalizeCellTypeFilter(value) {
            const raw = String(value ?? '').trim().toLowerCase();
            if (raw === 'single_cell' || raw === 'cell_pair') return raw;
            return 'all';
        }

        function getCellTypeFilterLabel(value) {
            const normalized = normalizeCellTypeFilter(value);
            if (normalized === 'single_cell') return 'Only single cells';
            if (normalized === 'cell_pair') return 'Only cell pairs';
            return 'Both cells';
        }

        function normalizeCellType(value) {
            const raw = String(value ?? '').trim().toLowerCase();
            if (raw === 'single_cell' || raw === 'cell_pair') return raw;
            return 'unknown';
        }

        function getCellTypeLabel(value) {
            const normalized = normalizeCellType(value);
            if (normalized === 'single_cell') return 'Single Cell';
            if (normalized === 'cell_pair') return 'Cell Pair';
            return 'Unknown';
        }

        function getRowCellType(row) {
            if (!row || typeof row !== 'object') return 'unknown';
            return normalizeCellType(row.cell_type);
        }

        function getAvailableCellTypes(statistics) {
            const seen = new Set();
            getStatisticsEntries(statistics).forEach(([, row]) => {
                seen.add(getRowCellType(row));
            });
            return ['single_cell', 'cell_pair', 'unknown'].filter((cellType) => seen.has(cellType));
        }

        function getDisabledCellTypeFilterLabel(availableCellTypes, baseRowCount) {
            const hasSingle = availableCellTypes.includes('single_cell');
            const hasPair = availableCellTypes.includes('cell_pair');
            if (hasPair && !hasSingle) return getCellTypeFilterLabel('cell_pair');
            if (hasSingle && !hasPair) return getCellTypeFilterLabel('single_cell');
            if (baseRowCount === 0) return 'No cells';
            return 'Cell types unknown';
        }

        function getCellTypeFilterDisabledHelp(availableCellTypes, baseRowCount) {
            if (baseRowCount === 0) {
                return 'No retained cells are available for this result.';
            }
            if (availableCellTypes.includes('cell_pair') && !availableCellTypes.includes('single_cell')) {
                return 'This result only contains cell pairs. To include single cells, rerun analysis with Cell Inclusion Mode set to Single cells and cell pairs.';
            }
            if (availableCellTypes.includes('single_cell') && !availableCellTypes.includes('cell_pair')) {
                return 'This result only contains single cells. To include cell pairs, rerun analysis with Cell Inclusion Mode set to Single cells and cell pairs.';
            }
            return 'Cell type information is not present for this result.';
        }

        function getCellTypeFilterUiState(statistics, requestedFilter) {
            const entries = getStatisticsEntries(statistics);
            const availableCellTypes = getAvailableCellTypes(statistics);
            const hasSingle = availableCellTypes.includes('single_cell');
            const hasPair = availableCellTypes.includes('cell_pair');
            const requested = normalizeCellTypeFilter(requestedFilter);
            const enabled = hasSingle && hasPair;
            const effectiveFilter = enabled && requested !== 'all' && availableCellTypes.includes(requested)
                ? requested
                : 'all';
            const displayLabel = enabled
                ? getCellTypeFilterLabel(effectiveFilter)
                : getDisabledCellTypeFilterLabel(availableCellTypes, entries.length);
            return {
                enabled,
                effectiveFilter,
                requestedFilter: requested,
                displayLabel,
                helpText: enabled
                    ? 'This filter only applies to cells retained during analysis. Rerun analysis with a different Cell Inclusion Mode to include excluded cell types.'
                    : getCellTypeFilterDisabledHelp(availableCellTypes, entries.length),
                availableCellTypes,
                baseRowCount: entries.length,
                resetRequestedFilter: requested !== effectiveFilter,
            };
        }

        function matchesCellTypeFilter(row, filterValue) {
            const normalized = normalizeCellTypeFilter(filterValue);
            if (normalized === 'all') return true;
            return getRowCellType(row) === normalized;
        }

        function primitiveStatValue(value) {
            if (!value || typeof value !== 'object') return value;
            for (const key of ['value', 'raw', 'raw_value', 'display_value']) {
                if (Object.prototype.hasOwnProperty.call(value, key)) {
                    return value[key];
                }
            }
            return value;
        }

        function positiveNumber(value) {
            const primitive = primitiveStatValue(value);
            if (primitive === null || primitive === undefined || primitive === '') return null;
            if (typeof primitive === 'string' && ['n/a', 'na', 'none'].includes(primitive.trim().toLowerCase())) {
                return null;
            }
            const numeric = Number(primitive);
            return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
        }

        function nonnegativeInteger(value) {
            const primitive = primitiveStatValue(value);
            if (primitive === null || primitive === undefined || primitive === '' || typeof primitive === 'boolean') {
                return null;
            }
            const numeric = Number(primitive);
            if (!Number.isInteger(numeric) || numeric < 0) return null;
            return numeric;
        }

        function normalizePunctaSourceChannel(channel) {
            const raw = String(channel ?? '').trim().toLowerCase();
            if (raw === 'red' || raw === 'channel_red' || raw === 'red puncta') return 'red';
            if (raw === 'green' || raw === 'channel_green' || raw === 'green puncta') return 'green';
            if (raw.includes('red')) return 'red';
            if (raw.includes('green')) return 'green';
            return null;
        }

        function getPunctaSourceContourChannel(row) {
            if (!row || typeof row !== 'object') return null;
            const signalMode = String(row.signal_quantification_mode ?? '').trim().toLowerCase();
            if (signalMode && signalMode !== 'puncta_distance') return null;
            const hasPunctaDistanceEvidence = signalMode === 'puncta_distance'
                || row.puncta_distance !== null && row.puncta_distance !== undefined
                || row.puncta_source_contour_count !== null && row.puncta_source_contour_count !== undefined;
            if (!hasPunctaDistanceEvidence) return null;

            const storedChannel = normalizePunctaSourceChannel(row.puncta_source_contour_count_channel);
            if (storedChannel) return storedChannel;
            if (row.puncta_line_mode === 'green_puncta' || row.puncta_line_mode === 'green_puncta_only') return 'green';
            if (row.puncta_line_mode === 'red_puncta' || row.puncta_line_mode === 'red_puncta_only') return 'red';
            const sourceLabel = normalizePunctaSourceChannel(row.puncta_line_source_channel);
            if (sourceLabel) return sourceLabel;
            return 'red';
        }

        function getPunctaSourceContourContext(statistics) {
            const entries = getStatisticsEntries(statistics);
            for (const [, row] of entries) {
                const channel = getPunctaSourceContourChannel(row);
                if (channel) {
                    const channelLabel = channel === 'green' ? 'Green' : 'Red';
                    return {
                        applicable: true,
                        channel,
                        channelLabel,
                        controlLabel: `${channelLabel} Source Contour Count`,
                    };
                }
            }
            return {
                applicable: false,
                channel: null,
                channelLabel: '',
                controlLabel: 'Puncta Source Contour Count',
            };
        }

        function derivePunctaSourceContourCount(row) {
            if (!row || typeof row !== 'object') return null;
            const sourceChannel = getPunctaSourceContourChannel(row);
            if (!sourceChannel) return null;
            const storedCount = nonnegativeInteger(row.puncta_source_contour_count);
            if (storedCount !== null) return storedCount;
            const channelCount = nonnegativeInteger(row[`${sourceChannel}_contour_count`]);
            if (channelCount !== null) return channelCount;

            let count = 0;
            for (let index = 1; index <= 3; index += 1) {
                if (positiveNumber(row[`${sourceChannel}_contour_${index}_size`]) !== null) {
                    count += 1;
                }
            }
            return count > 0 ? count : null;
        }

        function matchesPunctaSourceContourCountFilter(row, filterValue) {
            const normalized = normalizePunctaSourceContourCountFilter(filterValue);
            if (normalized === 'all') return true;
            if (!getPunctaSourceContourChannel(row)) return true;
            const expected = normalized === 'exactly_1' ? 1 : 2;
            return derivePunctaSourceContourCount(row) === expected;
        }

        function getStatisticsEntries(statistics) {
            return Object.keys(statistics || {})
                .map((key) => [Number(key), statistics[String(key)]])
                .filter(([id, row]) => (
                    !Number.isNaN(id)
                    && row
                    && typeof row === 'object'
                ))
                .sort(([leftId], [rightId]) => leftId - rightId);
        }

        function normalizeRowFilterOptions(filterOptions) {
            if (!filterOptions || typeof filterOptions !== 'object') {
                return {
                    cellTypeFilter: 'all',
                    punctaSourceContourCountFilter: normalizePunctaSourceContourCountFilter(filterOptions),
                };
            }
            return {
                cellTypeFilter: normalizeCellTypeFilter(filterOptions.cellTypeFilter),
                punctaSourceContourCountFilter: normalizePunctaSourceContourCountFilter(
                    filterOptions.punctaSourceContourCountFilter,
                ),
            };
        }

        function getFilteredStatisticsEntries(statistics, filterOptions) {
            const filters = normalizeRowFilterOptions(filterOptions);
            const entries = getStatisticsEntries(statistics);
            return entries.filter(([, row]) => (
                matchesCellTypeFilter(row, filters.cellTypeFilter)
                && matchesPunctaSourceContourCountFilter(
                    row,
                    filters.punctaSourceContourCountFilter,
                )
            ));
        }

        function getPunctaSourceContourCountFilterCounts(statistics, filterValue, cellTypeFilter = 'all') {
            const entries = getFilteredStatisticsEntries(statistics, {
                cellTypeFilter,
                punctaSourceContourCountFilter: 'all',
            });
            const filteredStatistics = Object.fromEntries(
                entries.map(([id, row]) => [String(id), row]),
            );
            const context = getPunctaSourceContourContext(filteredStatistics);
            const normalized = context.applicable
                ? normalizePunctaSourceContourCountFilter(filterValue)
                : 'all';
            return {
                filter: normalized,
                total: entries.length,
                applicable: context.applicable,
                channel: context.channel,
                channelLabel: context.channelLabel,
                controlLabel: context.controlLabel,
                shown: normalized === 'all'
                    ? entries.length
                    : entries.filter(([, row]) => matchesPunctaSourceContourCountFilter(row, normalized)).length,
            };
        }

        function getPunctaSourceContourFilterUiState(statistics, requestedFilter) {
            const entries = getStatisticsEntries(statistics);
            const filteredStatistics = Object.fromEntries(
                entries.map(([id, row]) => [String(id), row]),
            );
            const context = getPunctaSourceContourContext(filteredStatistics);
            const normalized = normalizePunctaSourceContourCountFilter(requestedFilter);
            const hasCountData = entries.some(([, row]) => derivePunctaSourceContourCount(row) !== null);
            const enabled = entries.length > 0 && context.applicable && hasCountData;
            return {
                enabled,
                effectiveFilter: enabled ? normalized : 'all',
                requestedFilter: normalized,
                channel: context.channel,
                channelLabel: context.channelLabel,
                controlLabel: context.controlLabel,
                total: entries.length,
            };
        }

        function getPunctaSourceContourCardFilterLabel(statistics, filterValue) {
            const normalized = normalizePunctaSourceContourCountFilter(filterValue);
            if (normalized === 'all') return '';
            const context = getPunctaSourceContourContext(statistics || {});
            const countLabel = normalized === 'exactly_1'
                ? 'Exactly 1'
                : 'Exactly 2';
            const sourceLabel = context.channelLabel
                ? `${context.channelLabel.toLowerCase()} source contour${normalized === 'exactly_1' ? '' : 's'}`
                : `source contour${normalized === 'exactly_1' ? '' : 's'}`;
            return `${countLabel} ${sourceLabel}`;
        }

        function getCellCardFilterBadgeState(statistics, {
            cellTypeFilter = 'all',
            punctaSourceContourCountFilter = 'all',
        } = {}) {
            const rows = statistics || {};
            const cellTypeState = getCellTypeFilterUiState(rows, cellTypeFilter);
            const sourceState = getPunctaSourceContourFilterUiState(
                rows,
                punctaSourceContourCountFilter,
            );
            const parts = [];
            if (cellTypeState.effectiveFilter !== 'all') {
                parts.push(getCellTypeFilterLabel(cellTypeState.effectiveFilter));
            }
            if (sourceState.effectiveFilter !== 'all') {
                const sourceLabel = getPunctaSourceContourCardFilterLabel(
                    rows,
                    sourceState.effectiveFilter,
                );
                if (sourceLabel) {
                    parts.push(sourceLabel);
                }
            }
            const hasActiveFilter = parts.length > 0;
            return {
                hidden: cellTypeState.baseRowCount === 0,
                prefix: hasActiveFilter ? 'Filtered view' : 'Retained cells',
                value: hasActiveFilter
                    ? parts.join(' / ')
                    : cellTypeState.displayLabel,
                cellTypeState,
                punctaSourceContourState: sourceState,
            };
        }

        function getRowFilterEmptyMessage(statistics, renderedRowCount, {
            cellTypeState = null,
            punctaSourceContourState = null,
        } = {}) {
            const baseRowCount = getStatisticsEntries(statistics).length;
            if (baseRowCount === 0) {
                return 'No retained cells are available for this result.';
            }
            if (Number(renderedRowCount) > 0) {
                return '';
            }
            const cellTypeActive = Boolean(
                cellTypeState
                && cellTypeState.enabled
                && cellTypeState.effectiveFilter !== 'all'
            );
            const sourceContourActive = Boolean(
                punctaSourceContourState
                && punctaSourceContourState.enabled
                && punctaSourceContourState.effectiveFilter !== 'all'
            );
            if (cellTypeActive && sourceContourActive) {
                return 'No cells match the current row filters. Switch to Both cells and all source contours to view every retained cell.';
            }
            if (cellTypeActive) {
                return 'No cells match the current Cell Type Filter. Switch to Both cells to view every retained cell.';
            }
            if (sourceContourActive) {
                return 'No cells match the current source contour filter. Show all source contours to view every retained cell.';
            }
            return '';
        }

        function uniquePositiveCellIds(values) {
            const seen = new Set();
            const ids = [];
            (values || []).forEach((value) => {
                const id = Number(value);
                if (!Number.isFinite(id) || id <= 0 || seen.has(id)) return;
                seen.add(id);
                ids.push(id);
            });
            return ids;
        }

        function getPunctaSourceContourFilteredCellIds(fileData, filterValue, cellTypeFilter = 'all') {
            const statistics = fileData?.Statistics || {};
            const cellTypeEntries = getFilteredStatisticsEntries(statistics, {
                cellTypeFilter,
                punctaSourceContourCountFilter: 'all',
            });
            const filteredStatistics = Object.fromEntries(
                cellTypeEntries.map(([id, row]) => [String(id), row]),
            );
            const context = getPunctaSourceContourContext(filteredStatistics);
            const normalized = context.applicable
                ? normalizePunctaSourceContourCountFilter(filterValue)
                : 'all';
            const entries = getStatisticsEntries(filteredStatistics);
            if (normalized === 'all') {
                return entries.map(([id]) => id);
            }
            return entries
                .filter(([, row]) => matchesPunctaSourceContourCountFilter(row, normalized))
                .map(([id]) => id);
        }

        function findNearestMatchingCellByOriginalOrder(currentCellId, allCellIds, filteredCellIds) {
            const filteredIds = uniquePositiveCellIds(filteredCellIds);
            if (filteredIds.length === 0) return null;

            const orderedIds = uniquePositiveCellIds(allCellIds);
            function findInsertionIndex(id) {
                if (orderedIds.length === 0) return 0;
                const numericId = Number(id);
                if (!Number.isFinite(numericId)) return 0;
                for (let index = 0; index < orderedIds.length; index += 1) {
                    if (orderedIds[index] >= numericId) {
                        return index;
                    }
                }
                return orderedIds.length - 1;
            }

            const fullIndexById = new Map();
            orderedIds.forEach((id, index) => {
                fullIndexById.set(id, index);
            });
            const currentId = Number(currentCellId);
            const currentIndex = fullIndexById.has(currentId)
                ? fullIndexById.get(currentId)
                : findInsertionIndex(currentId);

            let bestId = null;
            let bestDistance = Infinity;
            let bestIsForward = false;
            filteredIds.forEach((id) => {
                if (!fullIndexById.has(id)) return;
                const index = fullIndexById.get(id);
                const distance = Math.abs(index - currentIndex);
                const isForward = index >= currentIndex;
                if (
                    distance < bestDistance
                    || (distance === bestDistance && isForward && !bestIsForward)
                ) {
                    bestId = id;
                    bestDistance = distance;
                    bestIsForward = isForward;
                }
            });

            return bestId ?? filteredIds[0];
        }

        function getAdjacentFilteredCellId(currentCellId, filteredCellIds, direction = 'next') {
            const ids = uniquePositiveCellIds(filteredCellIds);
            if (ids.length === 0) return null;
            const currentIdx = ids.indexOf(Number(currentCellId));
            if (direction === 'previous') {
                const prevIdx = currentIdx === -1
                    ? ids.length - 1
                    : (currentIdx - 1 + ids.length) % ids.length;
                return ids[prevIdx];
            }
            const nextIdx = currentIdx === -1
                ? 0
                : (currentIdx + 1) % ids.length;
            return ids[nextIdx];
        }

        function formatFieldValue(fieldName, value, cellStats, scaleContext) {
            if (fieldName === 'cell_type') {
                return getCellTypeLabel(value);
            }
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

        function buildCellCardMetricValues(cellStats, {
            scaleContext = {},
            contourIntensityType = 'total',
        } = {}) {
            const displayType = normalizeContourIntensityDisplayType(contourIntensityType);
            const category = cellStats ? (cellStats.category_cen_dot_label || 'N/A') : 'N/A';
            const cellParentage = cellStats ? (cellStats.cell_parentage_label || 'Not identified') : 'N/A';
            const nuclearUnavailable = hasNoNucleusContour(cellStats);
            const mode = cellStats ? cellStats.nuclear_cell_pair_mode : null;
            const labels = getNuclearLabelPair(mode);
            const spatialUnit = getCurrentSpatialUnit();
            const distanceLabel = cellStats
                ? (cellStats.puncta_distance_label || 'Distance Between Red Puncta')
                : 'Distance Between Red Puncta';
            const lineIntensityLabel = cellStats
                ? (cellStats.puncta_line_intensity_label || 'Green Intensity Over Red Line')
                : 'Green Intensity Over Red Line';
            const metricValues = {
                distance: formatFieldValue(
                    'puncta_distance',
                    cellStats ? cellStats.puncta_distance : null,
                    cellStats,
                    scaleContext,
                ),
                punctaLineIntensity: formatStatValue(cellStats ? cellStats.puncta_line_intensity : null),
                measurementContourRatioFormula: cellStats ? (cellStats.measurement_contour_ratio_display_text || 'N/A') : 'N/A',
                measurementContourRatio1: formatStatValue(cellStats ? cellStats.measurement_contour_ratio_1 : null),
                measurementContourRatio2: formatStatValue(cellStats ? cellStats.measurement_contour_ratio_2 : null),
                measurementContourRatio3: formatStatValue(cellStats ? cellStats.measurement_contour_ratio_3 : null),
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
            };
            const contourIntensityLabels = {};
            const visibleContourIntensityCombinations = getVisibleContourIntensityCombinations(cellStats);
            getContourIntensityDisplayFields(displayType).forEach((field) => {
                metricValues[field.metricId] = formatStatValue(cellStats ? cellStats[field.fieldName] : null);
                contourIntensityLabels[field.metricId] = field.label;
            });

            return {
                mode: getEffectiveCellCardMode(cellStats),
                sections: getVisibleCellCardSections(cellStats),
                contourIntensityType: displayType,
                visibleContourIntensityCombinations,
                metricValues,
                labels: {
                    distanceLabel: formatSpatialLabel(distanceLabel, 'puncta_distance', spatialUnit),
                    lineIntensityLabel,
                    nucleusIntensityLabel: labels.nuclear,
                    cellularIntensityLabel: labels.cellular,
                    contourIntensityTypeLabel: CONTOUR_INTENSITY_STATISTICS[displayType],
                    contourIntensityLabels,
                },
            };
        }

        function renderStatisticsTable(statistics, fileData, {
            cellTypeFilter = 'all',
            punctaSourceContourCountFilter = 'all',
            activeCellId = null,
        } = {}) {
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

            const entries = getFilteredStatisticsEntries(
                statistics,
                { cellTypeFilter, punctaSourceContourCountFilter },
            );

            tbody.innerHTML = '';
            const activeId = Number(activeCellId);
            for (const [id, rowStats] of entries) {
                const tr = document.createElement('tr');
                tr.dataset.cellId = String(id);
                if (Number.isFinite(activeId) && id === activeId) {
                    tr.classList.add('is-active-cell');
                }
                for (const fieldName of visibleFieldOrder) {
                    const td = document.createElement('td');
                    if (fieldName === 'cell_id') {
                        td.textContent = String(id);
                    } else if (fieldName === 'cell_type') {
                        td.textContent = rowStats ? getCellTypeLabel(rowStats.cell_type) : 'Unknown';
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
            return entries.length;
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
            buildCellCardMetricValues,
            getVisibleContourIntensityCombinations,
            normalizePunctaSourceContourCountFilter,
            getPunctaSourceContourCountFilterLabel,
            normalizeCellTypeFilter,
            getCellTypeFilterLabel,
            normalizeCellType,
            getCellTypeLabel,
            matchesCellTypeFilter,
            getAvailableCellTypes,
            getCellTypeFilterUiState,
            getFilteredStatisticsEntries,
            getPunctaSourceContourContext,
            derivePunctaSourceContourCount,
            matchesPunctaSourceContourCountFilter,
            getPunctaSourceContourCountFilterCounts,
            getPunctaSourceContourFilterUiState,
            getCellCardFilterBadgeState,
            getRowFilterEmptyMessage,
            getPunctaSourceContourFilteredCellIds,
            findNearestMatchingCellByOriginalOrder,
            getAdjacentFilteredCellId,
            renderStatisticsTable,
            getStatisticsTableRowCount,
            hasStatisticsTableRows,
        };
    }

    // Public namespace consumed by Display and Dashboard page controllers. Keep
    // these names stable because static contract tests look for shared helpers.
    global.CytoCVResultsViewerShared = {
        readJsonConfig,
        createBlendHelpers,
        OVERLAY_FAMILY_DEFINITIONS,
        OVERLAY_FAMILY_KEYS,
        defaultOverlayVisibility,
        normalizeOverlayVisibility,
        getOverlaySelectionSignature,
        normalizeOverlayLayerContract,
        intersectOverlayVisibility,
        getOverlaySelectionSummary,
        getOverlayContractSelectionSummary,
        getCellOverlayRenderState,
        setCellImageStack,
        getMissingCellImageStackUrls,
        createOverlayVisibilityController,
        defaultStatVisibility,
        getStatVisibility,
        normalizeContourIntensityDisplayType,
        getEffectiveCellCardMode,
        getVisibleCellCardSections,
        getContourIntensityDisplayFields,
        getAllContourIntensityDisplayFields,
        getVisibleContourIntensityCombinations,
        bindContourIntensityDisplayControls,
        setContourIntensityDisplayButtonState,
        ensureChannelMessageContainer,
        showChannelError,
        preloadImage,
        preloadImageSet,
        setCellPairImagesLoading,
        setCellDataRegionLoading,
        createCellDataRegionLoadingController,
        bindFilterMenuPointerAwayClose,
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
