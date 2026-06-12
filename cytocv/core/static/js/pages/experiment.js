    const selectedFiles = new Map();
    const pluginPayloadElement = document.getElementById('statsPluginPayload');
    const restoredQueuePayloadElement = document.getElementById('restoredQueuePayload');
    const serverPreferenceDefaultsElement = document.getElementById('serverPreferenceDefaults');
    const uploadQuotaProjectionElement = document.getElementById('uploadQuotaProjection');
    const uploadAccessPolicyElement = document.getElementById('uploadAccessPolicy');
    const uploadResumePayloadElement = document.getElementById('uploadResumePayload');
    const uploadPreparationConfigElement = document.getElementById('uploadPreparationConfig');
    let restoredQueueItems = [];
    try {
        const restoredRaw = restoredQueuePayloadElement ? restoredQueuePayloadElement.textContent : '[]';
        const restoredParsed = JSON.parse(restoredRaw || '[]');
        if (Array.isArray(restoredParsed)) {
            restoredQueueItems = restoredParsed
                .filter((item) => item && typeof item.uuid === 'string' && typeof item.name === 'string')
                .map((item) => ({ uuid: item.uuid, name: item.name }));
        }
    } catch (err) {
        restoredQueueItems = [];
    }
    let statsPayload = {};
    try {
        const payloadRaw = pluginPayloadElement ? pluginPayloadElement.textContent : '{}';
        statsPayload = JSON.parse(payloadRaw || '{}');
    } catch (err) {
        statsPayload = {};
    }

    const statsPlugins = Array.isArray(statsPayload.plugins) ? statsPayload.plugins : [];
    const channelOrder = Array.isArray(statsPayload.channel_order) && statsPayload.channel_order.length
        ? statsPayload.channel_order
        : ['DIC', 'channel_blue', 'channel_red', 'channel_green'];
    const alwaysRequiredChannels = new Set(
        Array.isArray(statsPayload.always_required_channels) && statsPayload.always_required_channels.length
            ? statsPayload.always_required_channels
            : ['DIC']
    );
    const channelInfo = statsPayload.channel_info || {};
    const channelLabels = statsPayload.channel_labels || {};
    const pluginMap = new Map(statsPlugins.map((plugin) => [plugin.id, plugin]));
    const signalPrimaryPluginIds = new Set(['PunctaDistance', 'GreenRedIntensity', 'NuclearCellPairIntensity']);

    const selectionKey = 'cytocv.selected_analyses.v3';
    const initializedKey = 'cytocv.selected_analyses_initialized.v3';
    const widthKey = 'cytocv.puncta_line_width.v3';
    const distanceKey = 'cytocv.cen_dot_distance.v2';
    const proximityRadiusKey = 'cytocv.cen_dot_proximity_radius.v1';
    const oldThresholdKey = 'cytocv.cen_dot_collinearity_threshold.v2';
    const biorientationRedMinDistanceKey = 'cytocv.biorientation_red_min_distance.v1';
    const biorientationRedMaxDistanceKey = 'cytocv.biorientation_red_max_distance.v1';
    const biorientationThresholdKey = 'cytocv.biorientation_collinearity_threshold.v1';
    const greenDotSplitKey = 'cytocv.green_dot_split_enabled.v1';
    const greenDotSplitModeKey = 'cytocv.green_dot_split_mode.v1';
    const redDotSplitKey = 'cytocv.red_dot_split_enabled.v1';
    const redDotSplitModeKey = 'cytocv.red_dot_split_mode.v1';
    const legacyBiorientationGreenSplitKey = 'cytocv.biorientation_green_split_enabled.v1';
    const advancedKey = 'cytocv.advanced_validation.v3';
    const signalQuantificationKey = 'cytocv.signal_quantification.v1';
    const punctaModeKey = 'cytocv.puncta_line_mode.v1';
    const nuclearModeKey = 'cytocv.nuclear_cell_pair_mode.v3';
    const nuclearContourModeKey = 'cytocv.nuclear_cell_pair_contour_mode.v1';
    const legacyNuclearCellPairModeKey = 'cytocv.use_legacy_nuclear_cell_pair_pipeline.v1';
    const legacyLengthUnitKey = 'cytocv.stats_length_unit.v2';
    const punctaLineWidthUnitKey = 'cytocv.puncta_line_width_unit.v3';
    const cenDotDistanceUnitKey = 'cytocv.cen_dot_distance_unit.v2';
    const cenDotProximityRadiusUnitKey = 'cytocv.cen_dot_proximity_radius_unit.v1';
    const biorientationRedMinDistanceUnitKey = 'cytocv.biorientation_red_min_distance_unit.v1';
    const biorientationRedMaxDistanceUnitKey = 'cytocv.biorientation_red_max_distance_unit.v1';
    const micronsPerPixelKey = 'cytocv.stats_microns_per_pixel.v2';
    const useMetadataScaleKey = 'cytocv.use_metadata_scale.v2';
    const useMetadataChannelOrderKey = 'cytocv.use_metadata_channel_order.v1';
    const fallbackChannelOrderKey = 'cytocv.fallback_channel_order.v1';
    const DEFAULT_FALLBACK_CHANNEL_ORDER = ['DIC', 'channel_blue', 'channel_green', 'channel_red'];
    const DEFAULT_MICRONS_PER_PIXEL = 0.1;
    let uploadPreparationConfig = {};
    try {
        const uploadPreparationRaw = uploadPreparationConfigElement
            ? uploadPreparationConfigElement.textContent
            : '{}';
        uploadPreparationConfig = JSON.parse(uploadPreparationRaw || '{}');
    } catch (err) {
        uploadPreparationConfig = {};
    }
    const uploadBatchTargetBytes = Number(uploadPreparationConfig.batch_target_bytes);
    const UPLOAD_BATCH_TARGET_BYTES = Number.isFinite(uploadBatchTargetBytes) && uploadBatchTargetBytes > 0
        ? uploadBatchTargetBytes
        : 83886080;
    const UPLOAD_PREPARATION_EXECUTION_MODE = typeof uploadPreparationConfig.execution_mode === 'string'
        ? uploadPreparationConfig.execution_mode
        : 'worker';
    const EXPERIMENT_WORKFLOW_DEFAULTS_URL = uploadPreparationConfig.workflow_defaults_url || '/api/experiment/workflow-defaults/';
    const EXPERIMENT_UPLOAD_BATCH_URL = uploadPreparationConfig.upload_batch_url || '/api/experiment/uploads/';
    const EXPERIMENT_UPLOAD_PREPARE_URL = uploadPreparationConfig.upload_prepare_url || '/api/experiment/upload-prep/';
    let serverPreferenceDefaults = {};
    try {
        const defaultsRaw = serverPreferenceDefaultsElement
            ? serverPreferenceDefaultsElement.textContent
            : '{}';
        serverPreferenceDefaults = JSON.parse(defaultsRaw || '{}');
    } catch (err) {
        serverPreferenceDefaults = {};
    }
    const UPLOAD_QUOTA_WARNING_SCOPE = 'upload-quota-warning';
    let uploadQuotaProjection = {};
    try {
        const uploadQuotaRaw = uploadQuotaProjectionElement
            ? uploadQuotaProjectionElement.textContent
            : '{}';
        uploadQuotaProjection = JSON.parse(uploadQuotaRaw || '{}');
    } catch (err) {
        uploadQuotaProjection = {};
    }
    let uploadAccessPolicy = {};
    try {
        const uploadAccessRaw = uploadAccessPolicyElement
            ? uploadAccessPolicyElement.textContent
            : '{}';
        uploadAccessPolicy = JSON.parse(uploadAccessRaw || '{}');
    } catch (err) {
        uploadAccessPolicy = {};
    }
    let uploadResumePayload = {};
    try {
        const uploadResumeRaw = uploadResumePayloadElement
            ? uploadResumePayloadElement.textContent
            : '{}';
        uploadResumePayload = JSON.parse(uploadResumeRaw || '{}');
    } catch (err) {
        uploadResumePayload = {};
    }

    const statsState = {
        selectedPlugins: new Set(),
        moduleEnabled: false,
        enforceLayerCount: false,
        enforceAllWavelengths: false,
        showLegacyPlugins: false,
        manualRequiredChannels: new Set(),
        punctaLineWidth: 1,
        cenDotDistance: 37,
        cenDotProximityRadius: 13,
        biorientationRedMinDistance: 0,
        biorientationRedMaxDistance: 37,
        biorientationCollinearityThreshold: 3,
        signalQuantificationEnabled: true,
        signalQuantificationMode: 'puncta_distance',
        punctaContourIntensityEnabled: true,
        alternateNucleusDetectionEnabled: false,
        useLegacyNuclearCellPairPipeline: false,
        greenDotSplitEnabled: true,
        greenDotSplitMode: 'balanced',
        redDotSplitEnabled: true,
        redDotSplitMode: 'balanced',
        punctaLineMode: 'red_puncta',
        nuclearCellPairMode: 'green_nucleus',
        nuclearCellPairContourMode: 'balanced',
        greenContourFilterEnabled: false,
        punctaLineWidthUnit: 'px',
        cenDotDistanceUnit: 'px',
        cenDotProximityRadiusUnit: 'px',
        biorientationRedMinDistanceUnit: 'px',
        biorientationRedMaxDistanceUnit: 'px',
        micronsPerPixel: DEFAULT_MICRONS_PER_PIXEL,
        useMetadataScale: true,
        useMetadataChannelOrder: true,
        fallbackChannelOrder: [...DEFAULT_FALLBACK_CHANNEL_ORDER],
    };

    const statToggleElements = new Map();
    const channelToggleElements = new Map();
    const channelRowElements = new Map();
    const lengthUnitSelectElements = new Set();
    const modeDropdownControls = new Set();
    let punctaLineWidthInput = null;
    let punctaLineWidthRow = null;
    let cenDotDistanceInput = null;
    let cenDotDistanceRow = null;
    let cenDotProximityRadiusInput = null;
    let biorientationRedMinDistanceInput = null;
    let biorientationRedMaxDistanceInput = null;
    let biorientationCollinearityThresholdInput = null;
    let biorientationRow = null;
    let micronsPerPixelInput = null;
    let useMetadataScaleInput = null;
    let useMetadataChannelOrderInput = null;
    let wavelengthChannelOrderStatus = null;
    let fallbackChannelOrderBar = null;
    let fallbackChannelOrderModeLabel = null;
    let fallbackChannelOrderBackButton = null;
    let fallbackChannelOrderResetButton = null;
    let fallbackChannelOrderResetBaseline = [...DEFAULT_FALLBACK_CHANNEL_ORDER];
    const fallbackChannelOrderActionLockMs = 220;
    const fallbackChannelOrderUndoStack = [];
    let fallbackChannelOrderActionLocked = false;
    let measurementScalePxPerUmValue = null;
    let measurementScaleUmPerPxValue = null;
    let measurementScaleExampleHint = null;
    let measurementScaleFallbackHint = null;
    let punctaLineModeRow = null;
    let punctaLineModeSelect = null;
    let signalQuantificationToggle = null;
    let signalQuantificationModeRow = null;
    let signalQuantificationModeSelect = null;
    let signalQuantificationInfoDot = null;
    let signalModePausedNote = null;
    const SIGNAL_MODE_NOTICE_FADE_MS = 120;
    let signalModeNoticeTimer = null;
    let signalModeNoticeTransition = 0;
    let signalPunctaPanel = null;
    let signalNuclearPanel = null;
    let punctaContourIntensityToggle = null;
    let punctaContourIntensityRow = null;
    let alternateNucleusDetectionToggle = null;
    let alternateNucleusDetectionRow = null;
    let legacyNuclearCellPairToggle = null;
    let legacyNuclearCellPairRow = null;
    let nuclearModeSelect = null;
    let nuclearModeRow = null;
    let nuclearContourModeSelect = null;
    let nuclearContourModeRow = null;
    let dotSplitTargetSelect = null;
    let greenDotSplitModeSelect = null;
    let redDotSplitModeSelect = null;
    let selectionsInitializedBeforeLoad = false;
    let infoTooltipElement = null;
    let activeInfoAnchor = null;

    function normalizeGreenDotSplitMode(value) {
        return value === 'aggressive' ? 'aggressive' : 'balanced';
    }

    function normalizeRedDotSplitMode(value) {
        return value === 'aggressive' ? 'aggressive' : 'balanced';
    }

    function normalizeNuclearContourMode(value) {
        return value === 'aggressive' ? 'aggressive' : 'balanced';
    }

    function normalizeDotSplitTarget(value) {
        if (value === 'red' || value === 'green' || value === 'both') return value;
        return 'both';
    }

    function dotSplitTargetFromFlags(greenEnabled, redEnabled) {
        if (greenEnabled && redEnabled) return 'both';
        if (greenEnabled) return 'green';
        if (redEnabled) return 'red';
        return 'both';
    }

    function dotSplitTargetAllowed(target, greenAllowed, redAllowed) {
        if (target === 'green') return greenAllowed;
        if (target === 'red') return redAllowed;
        return greenAllowed && redAllowed;
    }

    function fallbackDotSplitTarget(preferredTarget, greenAllowed, redAllowed) {
        const target = normalizeDotSplitTarget(preferredTarget);
        if (dotSplitTargetAllowed(target, greenAllowed, redAllowed)) return target;
        if (greenAllowed && redAllowed) return 'both';
        if (greenAllowed) return 'green';
        if (redAllowed) return 'red';
        return '';
    }

    function applyDotSplitTargetToState(preferredTarget, enabled) {
        const greenAllowed = selectedStatsRequireChannel('channel_green');
        const redAllowed = selectedStatsRequireChannel('channel_red');
        const target = fallbackDotSplitTarget(preferredTarget, greenAllowed, redAllowed);
        if (!enabled || !target) {
            statsState.greenDotSplitEnabled = false;
            statsState.redDotSplitEnabled = false;
            return target;
        }
        statsState.greenDotSplitEnabled = target === 'green' || target === 'both';
        statsState.redDotSplitEnabled = target === 'red' || target === 'both';
        return target;
    }

    function joinLabels(labels) {
        const values = Array.isArray(labels) ? labels.filter(Boolean) : [];
        if (values.length === 0) return 'None';
        if (values.length === 1) return values[0];
        if (values.length === 2) return `${values[0]} and ${values[1]}`;
        return `${values.slice(0, -1).join(', ')}, and ${values[values.length - 1]}`;
    }

    function buildInfoSections(sections) {
        return sections
            .filter((section) => typeof section === 'string' && section.trim())
            .join('\n\n');
    }

    const pluginInfoExplanations = {
        PunctaDistance: 'Measures the distance between two puncta in the chosen source channel and sums the opposite-channel intensity along the line connecting them. It uses the first two detected source puncta, draws a line mask between their centers, and records the line intensity from the measurement channel.',
        CENDot: 'Classifies whether Green CEN dots are associated with the mother side, daughter side, both sides, or neither side. It uses automatic DIC mother/daughter parentage, checks for two usable Red puncta, then assigns nearby Green dots to the closest eligible Red punctum.',
        Biorientation: 'Counts Green dots as colinear or off-axis relative to the line between the two Red puncta. Counts are reported only when exactly two Red puncta are present and their separation is inside the configured distance range.',
        GreenRedIntensity: 'Measures raw intensity sums inside detected Red and Green contour masks. For Red contours it records Red and Green signal in the Red mask; for Green contours it records Red and Green signal in the Green mask and the distance to the nearest Red contour.',
        NuclearCellPairIntensity: 'Measures intensity in the selected nucleus contour and the full DIC cell-pair mask. The selected Red or Green nucleus contour defines the nucleus, and the opposite channel is summed inside the nucleus, whole cell pair, and cytoplasm.',
        NucleusIntensity: 'Legacy Blue-channel workflow that uses the Blue nucleus contour as the nuclear mask, then measures Green signal in the nucleus, whole cell, and cytoplasm.',
        BlueNucleusIntensity: 'Legacy Blue-channel workflow that uses the Blue nucleus contour as the nuclear mask, then measures Blue signal in the nucleus, whole cell, and cytoplasm.',
        RedBlueIntensity: 'Legacy workflow that measures Blue signal inside each detected Red-dot contour, up to the first three Red contours.',
    };

    const pluginAdjustmentInfo = {
        PunctaDistance: [
            'Puncta Source: chooses which channel supplies the two dots that define the line. Red Puncta measures Green along the Red-dot line; Green Puncta measures Red along the Green-dot line.',
            'Puncta Line Width: sets the thickness of the line mask used for the intensity sum. Use px or um; um values are converted from the measurement scale.',
        ],
        CENDot: [
            'Minimum Signal Distance: minimum allowed distance between the two Red puncta before CEN dot location is classified.',
            'Signal Proximity Radius: maximum distance a Green dot can be from a Red punctum and still count as associated with it.',
        ],
        Biorientation: [
            'Minimum Red Puncta Distance: smallest allowed spacing between the two Red puncta for biorientation counts to run.',
            'Maximum Red Puncta Distance: largest allowed spacing between the two Red puncta for biorientation counts to run.',
            'Collinearity Threshold: maximum allowed perpendicular offset (pixels) from the Red-puncta line for a Green dot to count as colinear.',
        ],
        NuclearCellPairIntensity: [
            'Nucleus Contour Source: chooses which channel supplies the nucleus contour. Green Nucleus measures Red signal; Red Nucleus measures Green signal.',
            'Nucleus Contour Mode: Balanced keeps the current alternate nucleus contour behavior; Aggressive uses tighter speckle-derived alternate nucleus masks for the selected nucleus source channel.',
            'Legacy Measurement Compatibility: measures the selected channel from YeastAnalysisTool-style 8-bit scaled crops while preserving CytoCV masks, contours, and channel identity.',
        ],
    };

    function buildPluginInfoText(plugin, requiredLabels) {
        const explanation = pluginInfoExplanations[plugin.id] || plugin.description || 'Statistic plugin.';
        const adjustmentLines = pluginAdjustmentInfo[plugin.id] || [];
        return buildInfoSections([
            explanation,
            ...adjustmentLines,
            `Required channels: ${joinLabels(requiredLabels)}`,
        ]);
    }

    const signalQuantificationInfoBase = 'Signal Quantification controls the primary Red/Green signal measurement workflow for this experiment. Choose one primary mode: Puncta Distance or Nuclear, Cell-Pair Intensity. The selected mode determines which statistics are calculated, which child controls are shown, and which results appear in the output.';
    const signalQuantificationPunctaInfo = [
        'Puncta Distance detects the first two usable puncta in the selected source channel, measures the distance between their centers, draws a line mask between them, and sums intensity from the opposite measurement channel along that line. Results include puncta distance, puncta line intensity, and pixel/scale-adjusted distance values.',
        'Puncta Source chooses which channel defines the two puncta and which opposite channel is measured. Red Puncta measures Green signal along the Red-puncta line; Green Puncta measures Red signal along the Green-puncta line.',
        'Puncta Line Width sets the thickness of the line mask used for the line-intensity sum. Values can be entered in pixels or microns; micron values are converted using the active measurement scale.',
        'Red/Green Contour Intensities optionally calculates raw intensity sums inside detected Red and Green contour masks. When enabled, results include Red in Red, Green in Red, Red in Green, Green in Green, Green-from-Red distance fields, and Measurement/Contour ratios for the selected puncta source.',
    ];
    const signalQuantificationNuclearInfo = [
        'Nuclear, Cell-Pair Intensity measures signal from the selected measurement channel inside the selected nucleus contour and inside the full DIC cell-pair mask. Results include nucleus contour channel, measurement channel, nuclear intensity, cell-pair intensity, cytoplasmic intensity, and nuclear status.',
        'Nucleus Contour Source chooses which channel supplies the nucleus contour and which opposite channel is measured. Green Nucleus uses the Green contour as the nucleus and measures Red signal; Red Nucleus uses the Red contour as the nucleus and measures Green signal.',
        'Legacy Measurement Compatibility changes only the measurement pixel source to 8-bit scaled crops for publication comparison. CytoCV channel identity, nucleus clipping, contours, and cell-pair masks are preserved.',
    ];

    function buildSignalQuantificationInfoText(mode = statsState.signalQuantificationMode) {
        const modeSections = normalizeSignalMode(mode) === 'nuclear_cell_pair'
            ? signalQuantificationNuclearInfo
            : signalQuantificationPunctaInfo;
        return buildInfoSections([
            signalQuantificationInfoBase,
            ...modeSections,
            'Required channels: Red and Green.',
        ]);
    }

    function updateSignalQuantificationInfoDot() {
        if (!signalQuantificationInfoDot) return;
        const normalized = normalizeInfoText(buildSignalQuantificationInfoText());
        signalQuantificationInfoDot.dataset.infoText = normalized;
        signalQuantificationInfoDot.setAttribute('aria-label', normalized || 'Information');
        if (activeInfoAnchor === signalQuantificationInfoDot && infoTooltipElement && !infoTooltipElement.hidden) {
            showInfoTooltip(signalQuantificationInfoDot);
        }
    }

    function normalizeSignalMode(value) {
        return value === 'nuclear_cell_pair' ? 'nuclear_cell_pair' : 'puncta_distance';
    }

    function persistSignalQuantificationSettings() {
        localStorage.setItem(signalQuantificationKey, JSON.stringify({
            enabled: !!statsState.signalQuantificationEnabled,
            mode: normalizeSignalMode(statsState.signalQuantificationMode),
            punctaContourIntensityEnabled: !!statsState.punctaContourIntensityEnabled,
            alternateNucleusDetectionEnabled: !!statsState.alternateNucleusDetectionEnabled,
            useLegacyNuclearCellPairPipeline: !!statsState.useLegacyNuclearCellPairPipeline,
        }));
    }

    function syncSignalSelectedPlugins() {
        signalPrimaryPluginIds.forEach((pluginId) => statsState.selectedPlugins.delete(pluginId));
        if (!statsState.signalQuantificationEnabled) {
            return;
        }
        if (normalizeSignalMode(statsState.signalQuantificationMode) === 'nuclear_cell_pair') {
            statsState.selectedPlugins.add('NuclearCellPairIntensity');
            return;
        }
        statsState.selectedPlugins.add('PunctaDistance');
        if (statsState.punctaContourIntensityEnabled) {
            statsState.selectedPlugins.add('GreenRedIntensity');
        }
    }

    function isNuclearSignalModeActive() {
        return !!statsState.signalQuantificationEnabled
            && normalizeSignalMode(statsState.signalQuantificationMode) === 'nuclear_cell_pair';
    }

    function isPluginPausedBySignalMode(pluginId) {
        return isNuclearSignalModeActive() && pluginId !== 'NuclearCellPairIntensity';
    }

    function getEffectiveSelectedPlugins() {
        if (isNuclearSignalModeActive()) {
            return new Set(['NuclearCellPairIntensity']);
        }
        return new Set(statsState.selectedPlugins);
    }

    function buildSignalModeNotice(signalEnabled, signalMode) {
        if (!signalEnabled) return null;
        if (signalMode === 'nuclear_cell_pair') {
            return {
                state: 'paused',
                text: 'Nuclear, Cell-Pair Intensity primary mode on. Other stat modules disabled.',
            };
        }
        return {
            state: 'enabled',
            text: 'All other stat modules enabled in Puncta Distance mode.',
        };
    }

    function syncSignalModeNotice(signalEnabled, signalMode) {
        if (!signalModePausedNote) return;
        const notice = buildSignalModeNotice(signalEnabled, signalMode);
        const state = notice ? notice.state : '';
        const text = notice ? notice.text : '';
        const changed = signalModePausedNote.dataset.state !== state || signalModePausedNote.textContent !== text;
        const isActive = signalModePausedNote.classList.contains('visible');
        signalModeNoticeTransition += 1;
        const transitionId = signalModeNoticeTransition;
        if (signalModeNoticeTimer) {
            window.clearTimeout(signalModeNoticeTimer);
            signalModeNoticeTimer = null;
        }
        const applyNotice = () => {
            if (transitionId !== signalModeNoticeTransition) return;
            signalModePausedNote.classList.remove('is-enabled', 'is-paused');
            signalModePausedNote.textContent = text;
            signalModePausedNote.dataset.state = state;
            signalModePausedNote.classList.add(`is-${state}`);
            signalModePausedNote.setAttribute('aria-hidden', 'false');
            void signalModePausedNote.offsetWidth;
            signalModePausedNote.classList.add('visible');
        };
        if (!notice) {
            signalModePausedNote.classList.remove('visible');
            signalModePausedNote.setAttribute('aria-hidden', 'true');
            signalModeNoticeTimer = window.setTimeout(() => {
                if (transitionId !== signalModeNoticeTransition) return;
                signalModePausedNote.classList.remove('is-enabled', 'is-paused');
                signalModePausedNote.dataset.state = '';
                signalModePausedNote.textContent = '';
            }, SIGNAL_MODE_NOTICE_FADE_MS);
            return;
        }
        if (!changed && isActive) {
            signalModePausedNote.setAttribute('aria-hidden', 'false');
            return;
        }
        if (changed && isActive) {
            signalModePausedNote.classList.remove('visible');
            signalModePausedNote.setAttribute('aria-hidden', 'true');
            signalModeNoticeTimer = window.setTimeout(applyNotice, SIGNAL_MODE_NOTICE_FADE_MS);
            return;
        }
        applyNotice();
    }

    const advancedInfoTextById = {
        legacyPluginInfoDot: buildInfoSections([
            'Shows legacy Blue-channel statistics in the plugin list. Turn this on only when you need older Blue-nucleus or Red-in-Blue outputs; modern Red/Green modules stay available either way.',
            'Required channels: Blue when a legacy plugin is selected.',
        ]),
        greenFilterInfoDot: buildInfoSections([
            'Filters Green contours before statistics run by removing low-confidence Green objects that often come from noisy background. This changes which Green dots or contours downstream plugins see, so validate a sample of overlays before using it for conclusions.',
            'Required channels: Green.',
        ]),
        greenFilterExperimentalDot: 'Experimental setting: behavior can vary across image quality, exposure, and channel mapping. Validate outputs before using results for conclusions.',
        dotSplitInfoDot: buildInfoSections([
            'Splits connected multi-peak Red and/or Green signal into separate dot contours before statistics are calculated. Use it when nearby dots are detected as one merged contour.',
            'Target: choose Red, Green, or Both. Unavailable targets are disabled when selected statistics do not require that channel.',
            'Modes: Balanced uses standard split sensitivity; Aggressive is the highest-recall split mode for tiny, very close, unequal, or tip-connected merged dots.',
            'Required channels: Red or Green.',
        ]),
        alternateRedInfoDot: buildInfoSections([
            'Uses alternate Red detection when standard detection creates one contour around all Red speckles. It tries to recover separate Red-dot contours so Red-dependent statistics can still run.',
            'Required channels: Red.',
        ]),
        optionalChecksInfoDot: buildInfoSections([
            'Controls the optional metadata and file validation checks below. When off, saved optional channel and layer requirements are paused, but channels required by selected statistics are still enforced.',
            'Enforce 4-Layer Files: requires exactly four image layers before preprocessing.',
            'Require All Channels: requires DIC, Blue, Red, and Green for every upload.',
            'Manual channel toggles: require individual channels even when selected statistics do not need them.',
            'Required channels: DIC is always required; optional checks can also require Blue, Red, and Green.',
        ]),
        layerCheckInfoDot: buildInfoSections([
            'Requires each source image file to have exactly four image layers before preprocessing. Use this to catch incomplete acquisitions or files exported with missing layers.',
            'Required channels: not channel-specific.',
        ]),
        wavelengthCheckInfoDot: buildInfoSections([
            'Requires every upload to include DIC, Blue, Red, and Green, even if the selected statistics only need a subset.',
            'Required channels: DIC, Blue, Red, and Green.',
        ]),
    };

    function hydrateAdvancedInfoDots() {
        Object.entries(advancedInfoTextById).forEach(([id, text]) => {
            const el = document.getElementById(id);
            if (!el) return;
            const normalized = normalizeInfoText(text);
            el.dataset.infoText = normalized;
            el.setAttribute('aria-label', normalized || 'Information');
        });
    }

    function buildChannelInfoText(channel) {
        const channelLabel = displayChannelLabel(channel);
        return buildInfoSections([
            `Channel purpose: ${channelInfo[channel] || `${channelLabel} channel.`}`,
            `Required channels: ${channelLabel}.`,
        ]);
    }

    function selectedPluginLabelsRequiringChannel(channel) {
        const labels = [];
        getEffectiveSelectedPlugins().forEach((pluginId) => {
            const plugin = pluginMap.get(pluginId);
            if (!plugin || !Array.isArray(plugin.required_channels)) return;
            if (plugin.required_channels.includes(channel)) {
                labels.push(plugin.label || plugin.id);
            }
        });
        return labels;
    }

    function buildAdvancedChannelInfo(channel, statusText = '') {
        const channelLabel = displayChannelLabel(channel);
        return buildInfoSections([
            `Channel purpose: ${channelInfo[channel] || `${channelLabel} channel.`}`,
            `Manual requirement: when this toggle is on and optional metadata checks are enabled, uploads must include the ${channelLabel} channel even if selected statistics do not need it.`,
            statusText ? `Current requirement status: ${statusText}` : '',
            `Required channels: ${channelLabel}.`,
        ]);
    }

    function normalizeChannelOrder(order) {
        const values = Array.isArray(order) ? order.filter(Boolean) : [];
        const expectedOrder = channelOrder.length ? channelOrder : DEFAULT_FALLBACK_CHANNEL_ORDER;
        if (values.length !== expectedOrder.length) return [...DEFAULT_FALLBACK_CHANNEL_ORDER];
        const expected = new Set(expectedOrder);
        const seen = new Set();
        const normalized = [];
        values.forEach((channel) => {
            if (!expected.has(channel) || seen.has(channel)) return;
            seen.add(channel);
            normalized.push(channel);
        });
        return normalized.length === expectedOrder.length ? normalized : [...DEFAULT_FALLBACK_CHANNEL_ORDER];
    }

    function applyServerPreferenceDefaults() {
        if (!serverPreferenceDefaults || typeof serverPreferenceDefaults !== 'object') {
            return;
        }

        const selectedPlugins = Array.isArray(serverPreferenceDefaults.selected_plugins)
            ? serverPreferenceDefaults.selected_plugins.filter((pluginId) => pluginMap.has(pluginId))
            : [];
        localStorage.setItem(selectionKey, JSON.stringify(selectedPlugins));
        localStorage.setItem(initializedKey, '1');

        const manualChannels = Array.isArray(serverPreferenceDefaults.manual_required_channels)
            ? serverPreferenceDefaults.manual_required_channels.filter((channel) => channelOrder.includes(channel))
            : [];
        const rawGreenDotSplitDefault = Object.prototype.hasOwnProperty.call(serverPreferenceDefaults, 'green_dot_split_enabled')
            ? serverPreferenceDefaults.green_dot_split_enabled
            : serverPreferenceDefaults.biorientation_green_split_enabled;
        const rawRedDotSplitDefault = Object.prototype.hasOwnProperty.call(serverPreferenceDefaults, 'red_dot_split_enabled')
            ? serverPreferenceDefaults.red_dot_split_enabled
            : true;
        const advancedPayload = {
            moduleEnabled: !!serverPreferenceDefaults.module_enabled,
            enforceLayerCount: !!serverPreferenceDefaults.enforce_layer_count,
            enforceAllWavelengths: !!serverPreferenceDefaults.enforce_wavelengths,
            showLegacyPlugins: !!serverPreferenceDefaults.show_legacy_plugins,
            manualRequiredChannels: manualChannels,
            greenContourFilterEnabled: !!serverPreferenceDefaults.green_contour_filter_enabled,
            greenDotSplitEnabled: rawGreenDotSplitDefault !== false,
            greenDotSplitMode: normalizeGreenDotSplitMode(serverPreferenceDefaults.green_dot_split_mode),
            redDotSplitEnabled: rawRedDotSplitDefault !== false,
            redDotSplitMode: normalizeRedDotSplitMode(serverPreferenceDefaults.red_dot_split_mode),
        };
        localStorage.setItem(advancedKey, JSON.stringify(advancedPayload));
        localStorage.setItem(signalQuantificationKey, JSON.stringify({
            enabled: serverPreferenceDefaults.signal_quantification_enabled !== false,
            mode: serverPreferenceDefaults.signal_quantification_mode === 'nuclear_cell_pair'
                ? 'nuclear_cell_pair'
                : 'puncta_distance',
            punctaContourIntensityEnabled: serverPreferenceDefaults.puncta_contour_intensity_enabled !== false,
            alternateNucleusDetectionEnabled: !!(
                serverPreferenceDefaults.alternate_nucleus_detection_enabled ||
                serverPreferenceDefaults.alternate_red_detection
            ),
            useLegacyNuclearCellPairPipeline: !!serverPreferenceDefaults.use_legacy_nuclear_cell_pair_pipeline,
        }));

        const widthUnit = (serverPreferenceDefaults.puncta_line_width_unit === 'um') ? 'um' : 'px';
        const distanceUnit = (serverPreferenceDefaults.cen_dot_distance_unit === 'um') ? 'um' : 'px';
        const proximityRadiusUnit = (serverPreferenceDefaults.cen_dot_proximity_radius_unit === 'um') ? 'um' : 'px';
        const biorientationMinUnit = (serverPreferenceDefaults.biorientation_red_min_distance_unit === 'um') ? 'um' : 'px';
        const biorientationMaxUnit = (serverPreferenceDefaults.biorientation_red_max_distance_unit === 'um') ? 'um' : 'px';
        localStorage.setItem(punctaLineWidthUnitKey, widthUnit);
        localStorage.setItem(cenDotDistanceUnitKey, distanceUnit);
        localStorage.setItem(cenDotProximityRadiusUnitKey, proximityRadiusUnit);
        localStorage.setItem(biorientationRedMinDistanceUnitKey, biorientationMinUnit);
        localStorage.setItem(biorientationRedMaxDistanceUnitKey, biorientationMaxUnit);
        localStorage.setItem(legacyLengthUnitKey, widthUnit === distanceUnit ? widthUnit : 'mixed');

        const width = Number(serverPreferenceDefaults.puncta_line_width);
        const distance = Number(serverPreferenceDefaults.cen_dot_distance);
        const proximityRadius = Number(serverPreferenceDefaults.cen_dot_proximity_radius);
        const biorientationMinDistance = Number(serverPreferenceDefaults.biorientation_red_min_distance);
        const biorientationMaxDistance = Number(serverPreferenceDefaults.biorientation_red_max_distance);
        const threshold = Number(serverPreferenceDefaults.biorientation_collinearity_threshold);
        const micronsPerPixel = Number(serverPreferenceDefaults.microns_per_pixel);
        localStorage.setItem(widthKey, Number.isFinite(width) ? String(width) : '1');
        localStorage.setItem(distanceKey, Number.isFinite(distance) ? String(distance) : '37');
        localStorage.setItem(proximityRadiusKey, Number.isFinite(proximityRadius) ? String(proximityRadius) : '13');
        localStorage.setItem(biorientationRedMinDistanceKey, Number.isFinite(biorientationMinDistance) ? String(biorientationMinDistance) : '0');
        localStorage.setItem(biorientationRedMaxDistanceKey, Number.isFinite(biorientationMaxDistance) ? String(biorientationMaxDistance) : '37');
        localStorage.setItem(biorientationThresholdKey, Number.isFinite(threshold) ? String(Math.max(0, Math.round(threshold))) : '3');
        localStorage.setItem(greenDotSplitKey, String(rawGreenDotSplitDefault !== false));
        localStorage.setItem(greenDotSplitModeKey, normalizeGreenDotSplitMode(serverPreferenceDefaults.green_dot_split_mode));
        localStorage.setItem(redDotSplitKey, String(rawRedDotSplitDefault !== false));
        localStorage.setItem(redDotSplitModeKey, normalizeRedDotSplitMode(serverPreferenceDefaults.red_dot_split_mode));
        localStorage.setItem(
            nuclearContourModeKey,
            normalizeNuclearContourMode(serverPreferenceDefaults.nuclear_cell_pair_contour_mode)
        );
        localStorage.setItem(
            legacyNuclearCellPairModeKey,
            String(!!serverPreferenceDefaults.use_legacy_nuclear_cell_pair_pipeline)
        );
        localStorage.setItem(
            micronsPerPixelKey,
            Number.isFinite(micronsPerPixel) && micronsPerPixel > 0
                ? String(micronsPerPixel)
                : String(DEFAULT_MICRONS_PER_PIXEL)
        );
        localStorage.setItem(
            useMetadataScaleKey,
            String(serverPreferenceDefaults.use_metadata_scale !== false)
        );
        localStorage.setItem(
            useMetadataChannelOrderKey,
            String(serverPreferenceDefaults.use_metadata_channel_order !== false)
        );
        localStorage.setItem(
            fallbackChannelOrderKey,
            JSON.stringify(normalizeChannelOrder(serverPreferenceDefaults.fallback_channel_order))
        );

        const nuclearMode = serverPreferenceDefaults.nuclear_cell_pair_mode === 'red_nucleus'
            ? 'red_nucleus'
            : 'green_nucleus';
        const punctaMode = serverPreferenceDefaults.puncta_line_mode === 'green_puncta'
            ? 'green_puncta'
            : 'red_puncta';
        localStorage.setItem(punctaModeKey, punctaMode);
        localStorage.setItem(nuclearModeKey, nuclearMode);
    }

    function displayChannelLabel(channel) {
        return channelLabels[channel] || channel;
    }

    function getQueuedCount() {
        return selectedFiles.size + restoredQueueItems.length;
    }

    function getQueuedNameSet() {
        const names = new Set(selectedFiles.keys());
        restoredQueueItems.forEach((item) => {
            if (item && typeof item.name === 'string') {
                names.add(item.name);
            }
        });
        return names;
    }

    function formatStorageBytes(rawBytes) {
        const bytes = Number(rawBytes);
        if (!Number.isFinite(bytes) || bytes <= 0) {
            return '0 B';
        }
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let value = bytes;
        let unitIndex = 0;
        while (value >= 1024 && unitIndex < units.length - 1) {
            value /= 1024;
            unitIndex += 1;
        }
        const decimals = value >= 100 || unitIndex === 0 ? 0 : value >= 10 ? 1 : 2;
        return `${value.toFixed(decimals)} ${units[unitIndex]}`;
    }

    function getUploadMaxFiles() {
        const raw = uploadAccessPolicy ? uploadAccessPolicy.upload_max_files : null;
        const parsed = Number(raw);
        if (!Number.isFinite(parsed) || parsed < 1) {
            return null;
        }
        return parsed;
    }

    function buildUploadFileLimitErrors(requestedFiles) {
        const lines = [];
        if (uploadAccessPolicy && typeof uploadAccessPolicy.upload_limit_message === 'string' && uploadAccessPolicy.upload_limit_message) {
            lines.push(uploadAccessPolicy.upload_limit_message);
        }
        const count = Number(requestedFiles) || 0;
        lines.push(`This submission includes ${count} ${count === 1 ? 'file' : 'files'} total.`);
        lines.push('Reduce the selection and try again.');
        return lines;
    }

    function updateUploadQuotaStatus() {
        const statusElement = document.getElementById('uploadQuotaStatus');
        if (!statusElement) {
            return;
        }

        const isAuthenticated = !!uploadQuotaProjection?.is_authenticated;
        const autoSaveExperiments = !!uploadQuotaProjection?.auto_save_experiments;
        if (!isAuthenticated) {
            statusElement.hidden = true;
            statusElement.textContent = '';
            statusElement.classList.remove('is-warning');
            if (window.clearGlobalMessages) {
                window.clearGlobalMessages({ scope: UPLOAD_QUOTA_WARNING_SCOPE });
            }
            return;
        }

        const availableStorage = Math.max(0, Number(uploadQuotaProjection.available_storage) || 0);
        const additionalFilesPossible = Math.max(
            0,
            Number(uploadQuotaProjection.additional_files_possible) || 0
        );
        const projectionReady = !!uploadQuotaProjection.projection_ready;
        const queuedCount = getQueuedCount();
        const queuedLabel = queuedCount === 1 ? 'file' : 'files';
        const separator = ' \u2022 ';
        const autosaveLabel = autoSaveExperiments ? 'Autosave on' : 'Autosave off';
        let statusMessage = `${queuedCount} ${queuedLabel} queued • Autosave on • ${formatStorageBytes(availableStorage)} left`;
        if (projectionReady) {
            statusMessage += ` • Est. ${additionalFilesPossible} ${additionalFilesPossible === 1 ? 'file' : 'files'}`;
        } else {
            statusMessage += ' • Estimate after first saved run';
        }

        statusMessage = `${queuedCount} ${queuedLabel} queued${separator}${autosaveLabel}${separator}${formatStorageBytes(availableStorage)} left`;
        if (projectionReady) {
            statusMessage += `${separator}Est. ${additionalFilesPossible} ${additionalFilesPossible === 1 ? 'file' : 'files'}`;
        } else {
            statusMessage += `${separator}Estimate after first saved run`;
        }

        statusElement.textContent = statusMessage;
        statusElement.hidden = false;
        statusElement.classList.remove('is-warning');

        if (window.clearGlobalMessages) {
            window.clearGlobalMessages({ scope: UPLOAD_QUOTA_WARNING_SCOPE });
        }

        const queueExceedsEstimate = projectionReady && queuedCount > additionalFilesPossible;
        if (queueExceedsEstimate) {
            statusElement.classList.add('is-warning');
        }
        if (queueExceedsEstimate && autoSaveExperiments && window.showGlobalMessage) {
            const warningPlural = additionalFilesPossible === 1 ? '' : 's';
            window.showGlobalMessage(
                `This queued workflow is estimated not to autosave because your storage quota would be exceeded. At your current average saved file size, you can autosave up to ${additionalFilesPossible} queued file${warningPlural} without freeing storage.`,
                'error',
                {
                    scope: UPLOAD_QUOTA_WARNING_SCOPE,
                    timeoutMs: 0,
                    dedupe: true,
                }
            );
        }
    }
    const POPUP_ENTER_MS = 170;
    const POPUP_EXIT_MS = 120;
    const prefersReducedMotionGlobal = !!(
        window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    );
    const QUEUE_ROW_FADE_MS = prefersReducedMotionGlobal ? 0 : 110;
    const QUEUE_PANEL_ANIM_MS = prefersReducedMotionGlobal ? 0 : 150;
    const QUEUE_PANEL_MAX_HEIGHT_PX = 320;

    function clearPopupAnim(backdrop, panel) {
        if (backdrop) {
            backdrop.classList.remove('modal-enter', 'modal-exit');
        }
        if (panel) {
            panel.classList.remove('modal-enter', 'modal-exit');
        }
    }

    function openPopupModal(backdrop, panel) {
        if (!backdrop) return;
        clearPopupAnim(backdrop, panel);
        backdrop.style.display = 'flex';
        backdrop.setAttribute('aria-hidden', 'false');
        if (!prefersReducedMotionGlobal) {
            void backdrop.offsetWidth;
            backdrop.classList.add('modal-enter');
            if (panel) {
                panel.classList.add('modal-enter');
            }
            window.setTimeout(() => clearPopupAnim(backdrop, panel), POPUP_ENTER_MS);
        }
    }

    function closePopupModal(backdrop, panel, onAfterClose = null) {
        if (!backdrop) {
            if (typeof onAfterClose === 'function') onAfterClose();
            return;
        }
        if (prefersReducedMotionGlobal || backdrop.style.display !== 'flex') {
            clearPopupAnim(backdrop, panel);
            backdrop.style.display = 'none';
            backdrop.setAttribute('aria-hidden', 'true');
            if (typeof onAfterClose === 'function') onAfterClose();
            return;
        }
        clearPopupAnim(backdrop, panel);
        backdrop.classList.add('modal-exit');
        if (panel) {
            panel.classList.add('modal-exit');
        }
        backdrop.setAttribute('aria-hidden', 'true');
        window.setTimeout(() => {
            clearPopupAnim(backdrop, panel);
            backdrop.style.display = 'none';
            if (typeof onAfterClose === 'function') onAfterClose();
        }, POPUP_EXIT_MS);
    }

    document.addEventListener('DOMContentLoaded', () => {
        applyServerPreferenceDefaults();
        infoTooltipElement = document.getElementById('statsInfoTooltip');
        hydrateAdvancedInfoDots();
        document.querySelectorAll('.advanced-info-dot').forEach((el) => {
            attachInfoTooltipBehavior(el);
        });
        initializeStatsSettings();
        setupSettingsModal();
        setupNavExitGuard();
        setupResetModal();
        setupFileInputs();
        setupUploadSubmit();
        displayFileQueue({ skipAnimation: true });
        window.addEventListener('scroll', refreshInfoTooltipPosition, true);
        window.addEventListener('resize', refreshInfoTooltipPosition);
        document.addEventListener('click', (event) => {
            const target = event.target;
            let clickedInsideLengthUnit = false;
            let clickedInsideMode = false;
            if (target instanceof Element) {
                lengthUnitSelectElements.forEach((control) => {
                    if (control.root.contains(target)) clickedInsideLengthUnit = true;
                });
                modeDropdownControls.forEach((ctrl) => {
                    if (ctrl.root.contains(target)) clickedInsideMode = true;
                });
            }
            if (!clickedInsideLengthUnit) {
                closeAllLengthUnitDropdowns();
            }
            if (!clickedInsideMode) {
                modeDropdownControls.forEach((ctrl) => ctrl.close());
            }
            if (!(target instanceof Element) || !target.classList.contains('info-dot')) {
                hideInfoTooltip();
            }
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                closeAllLengthUnitDropdowns();
                modeDropdownControls.forEach((ctrl) => ctrl.close());
                hideInfoTooltip();
            }
        });
        resumeUploadPreparationFromServer();
        const raw = sessionStorage.getItem('dvErrors');
        if (!raw) return;
        let lines = [];
        try {
            lines = JSON.parse(raw) || [];
        } catch (err) {
            sessionStorage.removeItem('dvErrors');
            return;
        }
        sessionStorage.removeItem('dvErrors');
        showErrors(lines);
    });


    function showErrors(lines) {
        if (!Array.isArray(lines) || lines.length === 0) return;

        let container = document.querySelector('.message-container.dv-overlay');
        if (!container) {
            container = document.createElement('div');
            container.className = 'message-container dv-overlay';
            document.body.appendChild(container);
        }

        const key = lines.filter((line) => line).join('\n').trim() || 'dv-errors';
        const existing = Array.from(
            container.querySelectorAll('.message.dv-error')
        ).find((msg) => msg.dataset.key === key);
        if (existing) {
            existing.remove();
        }

        const formattedLines = lines.map((line) => {
            if (!line) {
                return '<div class="dv-error-separator"></div>';
            }
            const isHeader = line.startsWith('Could not process');
            const cleanedLine = isHeader
                ? line
                : line
                    .replace(/\s*\(expected\s*\d+\s*layers?\)/i, '')
                    .replace(/\s*\(expected\s*\d+\s*\)/i, '');
            const lineClass = isHeader ? 'dv-error-line is-header' : 'dv-error-line';
            return `<div class="${lineClass}">${cleanedLine}</div>`;
        }).join('');
        const hasSections = lines.some((line) => !line);
        const headerLine = hasSections
            ? '<div class="dv-error-section-title">Input checks to review:</div><div class="dv-error-separator"></div>'
            : '';

        const message = document.createElement('div');
        message.className = 'message dv-error';
        message.dataset.key = key;
        message.innerHTML = `${headerLine}${formattedLines}`;
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'message-close';
        close.setAttribute('aria-label', 'Dismiss');
        close.innerHTML = '&times;';
        close.addEventListener('click', () => message.remove());
        message.appendChild(close);
        container.prepend(message);
        const maxVisibleMessages = 1;
        const activeMessages = Array.from(container.querySelectorAll('.message.dv-error'));
        if (activeMessages.length > maxVisibleMessages) {
            activeMessages.slice(maxVisibleMessages).forEach((oldMessage) => oldMessage.remove());
        }
        setTimeout(() => message.remove(), 60000);
    }

    function formatFileListForError(names, maxItems = 10) {
        if (!Array.isArray(names) || names.length === 0) return '';
        const unique = [...new Set(names)];
        const shown = unique.slice(0, maxItems);
        const remainder = unique.length - shown.length;
        const shownText = shown.join(', ');
        if (remainder > 0) {
            return `${shownText} (+${remainder} more)`;
        }
        return shownText;
    }

    function normalizeInfoText(value) {
        if (typeof value !== 'string') return '';
        const lines = value.split('\n').map((line) => line.trim());

        // Keep intentional blank lines between sections, but trim outer padding.
        while (lines.length && lines[0] === '') {
            lines.shift();
        }
        while (lines.length && lines[lines.length - 1] === '') {
            lines.pop();
        }

        // Collapse large blank runs to a single empty line for consistent spacing.
        const compact = [];
        let previousWasBlank = false;
        lines.forEach((line) => {
            if (line === '') {
                if (!previousWasBlank) {
                    compact.push('');
                }
                previousWasBlank = true;
                return;
            }
            compact.push(line);
            previousWasBlank = false;
        });

        return compact.join('\n');
    }

    function hideInfoTooltip() {
        activeInfoAnchor = null;
        if (!infoTooltipElement) return;
        infoTooltipElement.hidden = true;
        infoTooltipElement.textContent = '';
        infoTooltipElement.classList.remove('wide');
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

        const placement = anchor.dataset.tooltipPlacement || 'above';
        let left = rect.left + (rect.width / 2) - (width / 2);
        let top = rect.top - height - gap;

        if (placement === 'right') {
            left = rect.right + gap;
            if (left + width > window.innerWidth - margin) {
                left = rect.left - width - gap;
            }
            left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));
            top = rect.top + (rect.height / 2) - (height / 2);
            top = Math.max(margin, Math.min(top, window.innerHeight - height - margin));
        } else {
            left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));
        }

        const preferAbove = placement === 'above';
        if (placement !== 'right' && top < margin && preferAbove) {
            top = margin;
        } else if (placement !== 'right' && top < margin) {
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
        infoTooltipElement.classList.toggle('wide', anchor.dataset.tooltipWidth === 'wide');
        infoTooltipElement.hidden = false;
        positionInfoTooltip(anchor);
    }

    function attachInfoTooltipBehavior(info, text = '') {
        if (!info) return;
        const normalized = normalizeInfoText(text || info.dataset.infoText || '');
        if (normalized) {
            info.dataset.infoText = normalized;
            info.setAttribute('aria-label', normalized);
        } else if (!info.getAttribute('aria-label')) {
            info.setAttribute('aria-label', 'Information');
        }

        info.addEventListener('mouseenter', () => showInfoTooltip(info));
        info.addEventListener('focus', () => showInfoTooltip(info));
        info.addEventListener('mouseleave', hideInfoTooltip);
        info.addEventListener('blur', hideInfoTooltip);
        info.addEventListener('click', (event) => {
            event.preventDefault();
            if (activeInfoAnchor === info && infoTooltipElement && !infoTooltipElement.hidden) {
                hideInfoTooltip();
                return;
            }
            showInfoTooltip(info);
        });
    }

    function buildInfoDot(text) {
        const info = document.createElement('button');
        info.type = 'button';
        info.className = 'info-dot';
        info.textContent = 'i';
        attachInfoTooltipBehavior(info, text);
        return info;
    }

    function normalizeLengthUnit(value) {
        return value === 'um' ? 'um' : 'px';
    }

    function formatLengthUnitLabel(value) {
        return normalizeLengthUnit(value) === 'um' ? '\u00b5m' : 'px';
    }

    function sanitizeMicronsPerPixel(value, fallback = DEFAULT_MICRONS_PER_PIXEL) {
        const parsed = Number.parseFloat(String(value ?? '').trim());
        if (!Number.isFinite(parsed) || parsed <= 0) {
            return fallback;
        }
        return parsed;
    }

    function formatNumericInputValue(value, decimals = 3) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return '';
        if (Number.isInteger(numeric)) return String(numeric);
        return numeric.toFixed(decimals).replace(/\.?0+$/, '');
    }

    function defaultWidthForUnit(unit) {
        return unit === 'um' ? sanitizeMicronsPerPixel(statsState.micronsPerPixel) : 1;
    }

    function defaultDistanceForUnit(unit) {
        return unit === 'um'
            ? 37 * sanitizeMicronsPerPixel(statsState.micronsPerPixel)
            : 37;
    }

    function defaultBiorientationMinDistanceForUnit() {
        return 0;
    }

    function defaultBiorientationMaxDistanceForUnit(unit) {
        return unit === 'um'
            ? 37 * sanitizeMicronsPerPixel(statsState.micronsPerPixel)
            : 37;
    }

    function defaultProximityRadiusForUnit(unit) {
        return unit === 'um'
            ? 13 * sanitizeMicronsPerPixel(statsState.micronsPerPixel)
            : 13;
    }

    function getLengthUnitForField(field) {
        if (field === 'punctaLineWidth') return statsState.punctaLineWidthUnit;
        if (field === 'cenDotDistance') return statsState.cenDotDistanceUnit;
        if (field === 'cenDotProximityRadius') return statsState.cenDotProximityRadiusUnit;
        if (field === 'biorientationRedMinDistance') return statsState.biorientationRedMinDistanceUnit;
        if (field === 'biorientationRedMaxDistance') return statsState.biorientationRedMaxDistanceUnit;
        return 'px';
    }

    function setLengthUnitForField(field, unit) {
        const normalized = normalizeLengthUnit(unit);
        if (field === 'punctaLineWidth') {
            statsState.punctaLineWidthUnit = normalized;
            return;
        }
        if (field === 'cenDotDistance') {
            statsState.cenDotDistanceUnit = normalized;
            return;
        }
        if (field === 'cenDotProximityRadius') {
            statsState.cenDotProximityRadiusUnit = normalized;
            return;
        }
        if (field === 'biorientationRedMinDistance') {
            statsState.biorientationRedMinDistanceUnit = normalized;
            return;
        }
        if (field === 'biorientationRedMaxDistance') {
            statsState.biorientationRedMaxDistanceUnit = normalized;
        }
    }

    function getLengthValueForField(field) {
        if (field === 'punctaLineWidth') return statsState.punctaLineWidth;
        if (field === 'cenDotDistance') return statsState.cenDotDistance;
        if (field === 'cenDotProximityRadius') return statsState.cenDotProximityRadius;
        if (field === 'biorientationRedMinDistance') return statsState.biorientationRedMinDistance;
        if (field === 'biorientationRedMaxDistance') return statsState.biorientationRedMaxDistance;
        return 0;
    }

    function setLengthValueForField(field, value) {
        if (field === 'punctaLineWidth') {
            statsState.punctaLineWidth = value;
            return;
        }
        if (field === 'cenDotDistance') {
            statsState.cenDotDistance = value;
            return;
        }
        if (field === 'cenDotProximityRadius') {
            statsState.cenDotProximityRadius = value;
            return;
        }
        if (field === 'biorientationRedMinDistance') {
            statsState.biorientationRedMinDistance = value;
            return;
        }
        if (field === 'biorientationRedMaxDistance') {
            statsState.biorientationRedMaxDistance = value;
        }
    }

    function parseLengthValue(raw, unit, fallback, minimum = 0) {
        const parser = unit === 'um' ? Number.parseFloat : (value) => Number.parseInt(value, 10);
        const parsed = parser(String(raw ?? '').trim());
        if (!Number.isFinite(parsed) || parsed < minimum) {
            return fallback;
        }
        if (unit === 'um') {
            return parsed;
        }
        return Math.round(parsed);
    }

    function persistLengthUnitSettings() {
        localStorage.setItem(punctaLineWidthUnitKey, statsState.punctaLineWidthUnit);
        localStorage.setItem(cenDotDistanceUnitKey, statsState.cenDotDistanceUnit);
        localStorage.setItem(cenDotProximityRadiusUnitKey, statsState.cenDotProximityRadiusUnit);
        localStorage.setItem(biorientationRedMinDistanceUnitKey, statsState.biorientationRedMinDistanceUnit);
        localStorage.setItem(biorientationRedMaxDistanceUnitKey, statsState.biorientationRedMaxDistanceUnit);
        localStorage.setItem(micronsPerPixelKey, String(statsState.micronsPerPixel));
        localStorage.setItem(useMetadataScaleKey, String(!!statsState.useMetadataScale));
    }

    function persistChannelOrderSettings() {
        localStorage.setItem(useMetadataChannelOrderKey, String(!!statsState.useMetadataChannelOrder));
        localStorage.setItem(fallbackChannelOrderKey, JSON.stringify(normalizeChannelOrder(statsState.fallbackChannelOrder)));
    }

    function convertLengthValueToUnit(value, fromUnit, toUnit) {
        const normalizedFrom = normalizeLengthUnit(fromUnit);
        const normalizedTo = normalizeLengthUnit(toUnit);
        if (normalizedFrom === normalizedTo) {
            return Number(value);
        }
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
            return Number.NaN;
        }
        const umPerPx = sanitizeMicronsPerPixel(statsState.micronsPerPixel);
        if (normalizedFrom === 'px' && normalizedTo === 'um') {
            return numeric * umPerPx;
        }
        if (normalizedFrom === 'um' && normalizedTo === 'px') {
            return numeric / umPerPx;
        }
        return numeric;
    }

    function convertLengthToPixels(value, unit, minimumPx, fallbackPx) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
            return fallbackPx;
        }
        if (normalizeLengthUnit(unit) === 'um') {
            const umPerPx = sanitizeMicronsPerPixel(statsState.micronsPerPixel);
            const asPx = numeric / umPerPx;
            if (!Number.isFinite(asPx)) {
                return fallbackPx;
            }
            return Math.max(minimumPx, Math.round(asPx));
        }
        return Math.max(minimumPx, Math.round(numeric));
    }

    function applyLengthUnitSelection(field, nextUnit) {
        const currentUnit = getLengthUnitForField(field);
        const normalizedNext = normalizeLengthUnit(nextUnit);
        if (currentUnit === normalizedNext) return;

        const currentValue = getLengthValueForField(field);
        let converted = convertLengthValueToUnit(currentValue, currentUnit, normalizedNext);
        if (!Number.isFinite(converted)) {
            if (field === 'punctaLineWidth') converted = defaultWidthForUnit(normalizedNext);
            else if (field === 'cenDotProximityRadius') converted = defaultProximityRadiusForUnit(normalizedNext);
            else if (field === 'biorientationRedMinDistance') converted = defaultBiorientationMinDistanceForUnit();
            else if (field === 'biorientationRedMaxDistance') converted = defaultBiorientationMaxDistanceForUnit(normalizedNext);
            else converted = defaultDistanceForUnit(normalizedNext);
        }

        if (field === 'punctaLineWidth') {
            const minValue = normalizedNext === 'um' ? 0.01 : 1;
            if (converted < minValue) {
                converted = defaultWidthForUnit(normalizedNext);
            }
            if (normalizedNext === 'px') {
                converted = Math.round(converted);
            }
        } else if (
            field === 'cenDotDistance' ||
            field === 'cenDotProximityRadius' ||
            field === 'biorientationRedMinDistance' ||
            field === 'biorientationRedMaxDistance'
        ) {
            let fallback = defaultDistanceForUnit(normalizedNext);
            if (field === 'cenDotProximityRadius') fallback = defaultProximityRadiusForUnit(normalizedNext);
            if (field === 'biorientationRedMinDistance') fallback = defaultBiorientationMinDistanceForUnit();
            if (field === 'biorientationRedMaxDistance') fallback = defaultBiorientationMaxDistanceForUnit(normalizedNext);
            if (converted < 0) {
                converted = fallback;
            }
            if (normalizedNext === 'px') {
                converted = Math.round(converted);
            }
        }

        setLengthValueForField(field, converted);
        setLengthUnitForField(field, normalizedNext);
        persistLengthUnitSettings();
        if (field === 'punctaLineWidth') {
            localStorage.setItem(widthKey, String(statsState.punctaLineWidth));
        } else if (field === 'cenDotDistance') {
            localStorage.setItem(distanceKey, String(statsState.cenDotDistance));
        } else if (field === 'cenDotProximityRadius') {
            localStorage.setItem(proximityRadiusKey, String(statsState.cenDotProximityRadius));
        } else if (field === 'biorientationRedMinDistance') {
            localStorage.setItem(biorientationRedMinDistanceKey, String(statsState.biorientationRedMinDistance));
        } else if (field === 'biorientationRedMaxDistance') {
            localStorage.setItem(biorientationRedMaxDistanceKey, String(statsState.biorientationRedMaxDistance));
        }
        syncStatsUI();
    }

    function closeAllLengthUnitDropdowns(exceptControl = null) {
        lengthUnitSelectElements.forEach((control) => {
            if (control !== exceptControl) {
                control.close();
            }
        });
    }

    function buildLengthUnitSelect(field) {
        const root = document.createElement('div');
        root.className = 'length-unit-dropdown';

        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'length-unit-trigger';
        trigger.setAttribute('aria-haspopup', 'menu');
        trigger.setAttribute('aria-expanded', 'false');

        const label = document.createElement('span');
        label.className = 'length-unit-label';
        label.textContent = formatLengthUnitLabel(getLengthUnitForField(field));

        const caret = document.createElement('span');
        caret.className = 'length-unit-caret';
        caret.setAttribute('aria-hidden', 'true');

        trigger.appendChild(label);
        trigger.appendChild(caret);
        root.appendChild(trigger);

        const menu = document.createElement('div');
        menu.className = 'length-unit-menu';
        menu.hidden = true;
        root.appendChild(menu);

        const optionButtons = new Map();
        ['px', 'um'].forEach((unit) => {
            const option = document.createElement('button');
            option.type = 'button';
            option.className = 'length-unit-option';
            option.textContent = formatLengthUnitLabel(unit);
            option.dataset.unit = unit;
            option.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                applyLengthUnitSelection(field, unit);
                control.close();
            });
            menu.appendChild(option);
            optionButtons.set(unit, option);
        });

        const control = {
            field,
            root,
            close() {
                root.classList.remove('open');
                menu.hidden = true;
                trigger.setAttribute('aria-expanded', 'false');
                const row = root.closest('.stats-toggle-row');
                if (row) {
                    row.classList.remove('unit-menu-open');
                }
            },
            open() {
                closeAllLengthUnitDropdowns(control);
                root.classList.add('open');
                menu.hidden = false;
                trigger.setAttribute('aria-expanded', 'true');
                const row = root.closest('.stats-toggle-row');
                if (row) {
                    row.classList.add('unit-menu-open');
                }
            },
            setUnit(unit) {
                const normalized = normalizeLengthUnit(unit);
                label.textContent = formatLengthUnitLabel(normalized);
                root.dataset.unit = normalized;
                optionButtons.forEach((button, candidate) => {
                    button.classList.toggle('is-selected', candidate === normalized);
                });
            },
        };

        trigger.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            if (root.classList.contains('open')) {
                control.close();
            } else {
                control.open();
            }
        });
        trigger.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                control.close();
            }
        });

        lengthUnitSelectElements.add(control);
        control.setUnit(getLengthUnitForField(field));
        return root;
    }

    function buildCustomModeSelect(optionsList, initialValue, onChange) {
        let currentValue = initialValue;
        let disabledValues = new Set(optionsList.filter((o) => o.disabled).map((o) => o.value));
        let controlDisabled = false;

        const root = document.createElement('div');
        root.className = 'length-unit-dropdown mode-dropdown';

        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'length-unit-trigger mode-trigger';
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');

        const labelSpan = document.createElement('span');
        const getLabel = (val) => (optionsList.find((o) => o.value === val) || {}).text || val;
        labelSpan.textContent = getLabel(currentValue);

        const caret = document.createElement('span');
        caret.className = 'length-unit-caret';
        caret.setAttribute('aria-hidden', 'true');
        trigger.appendChild(labelSpan);
        trigger.appendChild(caret);
        root.appendChild(trigger);

        const menu = document.createElement('div');
        menu.className = 'length-unit-menu';
        menu.setAttribute('role', 'listbox');
        menu.hidden = true;
        root.appendChild(menu);

        const optionButtons = new Map();
        const syncDisabledState = () => {
            trigger.disabled = controlDisabled;
            root.classList.toggle('is-disabled', controlDisabled);
            optionButtons.forEach((btn, value) => {
                const disabled = controlDisabled || disabledValues.has(value);
                btn.disabled = disabled;
                btn.classList.toggle('is-disabled', disabled);
                btn.setAttribute('aria-disabled', disabled ? 'true' : 'false');
            });
        };

        optionsList.forEach(({ value, text }) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'length-unit-option';
            btn.setAttribute('role', 'option');
            btn.textContent = text;
            btn.dataset.value = value;
            if (value === currentValue) btn.classList.add('is-selected');
            btn.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                if (controlDisabled || disabledValues.has(value)) return;
                currentValue = value;
                optionButtons.forEach((b, v) => b.classList.toggle('is-selected', v === value));
                labelSpan.textContent = getLabel(value);
                ctrl.close();
                onChange(value);
            });
            menu.appendChild(btn);
            optionButtons.set(value, btn);
        });

        const ctrl = {
            root,
            menu,
            close() {
                root.classList.remove('open');
                menu.hidden = true;
                trigger.setAttribute('aria-expanded', 'false');
                modeDropdownControls.delete(ctrl);
                const modeInline = root.closest('.nuclear-mode-inline');
                if (modeInline) modeInline.classList.remove('mode-menu-open');
                const comboRow = root.closest('.toggle-row.combo');
                if (comboRow) comboRow.classList.remove('mode-menu-open');
                const statsInline = root.closest('.stats-distance-inline');
                if (statsInline) statsInline.classList.remove('mode-menu-open');
            },
            open() {
                modeDropdownControls.forEach((c) => { if (c !== ctrl) c.close(); });
                closeAllLengthUnitDropdowns();
                root.classList.add('open');
                menu.hidden = false;
                trigger.setAttribute('aria-expanded', 'true');
                modeDropdownControls.add(ctrl);
                const modeInline = root.closest('.nuclear-mode-inline');
                if (modeInline) modeInline.classList.add('mode-menu-open');
                const comboRow = root.closest('.toggle-row.combo');
                if (comboRow) comboRow.classList.add('mode-menu-open');
                const statsInline = root.closest('.stats-distance-inline');
                if (statsInline) statsInline.classList.add('mode-menu-open');
            },
        };

        trigger.addEventListener('click', (event) => {
            event.stopPropagation();
            if (root.classList.contains('open')) ctrl.close();
            else ctrl.open();
        });

        const handle = Object.create(null);
        Object.defineProperty(handle, 'value', {
            get() { return currentValue; },
            set(val) {
                currentValue = val;
                optionButtons.forEach((b, v) => b.classList.toggle('is-selected', v === val));
                labelSpan.textContent = getLabel(val);
            },
            enumerable: true,
            configurable: true,
        });
        handle.setDisabledValues = (values) => {
            disabledValues = new Set(Array.isArray(values) ? values : []);
            syncDisabledState();
        };
        handle.setDisabled = (disabled) => {
            controlDisabled = !!disabled;
            if (controlDisabled) ctrl.close();
            syncDisabledState();
        };
        handle.root = root;
        handle.ctrl = ctrl;
        syncDisabledState();
        return handle;
    }

    function buildLengthInputGroup({ field, inputId, minValue, defaultValue, onChange }) {
        const controls = document.createElement('div');
        controls.className = 'length-input-group';

        const input = document.createElement('input');
        input.type = 'number';
        input.id = inputId;
        input.min = String(minValue);
        input.value = String(defaultValue);
        input.addEventListener('change', onChange);

        controls.appendChild(input);
        controls.appendChild(buildLengthUnitSelect(field));
        return { controls, input };
    }

    function syncLengthControls() {
        if (statsState.punctaLineWidthUnit === 'px') {
            statsState.punctaLineWidth = Math.max(1, Math.round(Number(statsState.punctaLineWidth) || 1));
        }
        if (statsState.cenDotDistanceUnit === 'px') {
            statsState.cenDotDistance = Math.max(0, Math.round(Number(statsState.cenDotDistance) || 0));
        }
        if (statsState.cenDotProximityRadiusUnit === 'px') {
            statsState.cenDotProximityRadius = Math.max(0, Math.round(Number(statsState.cenDotProximityRadius) || 0));
        }
        if (statsState.biorientationRedMinDistanceUnit === 'px') {
            statsState.biorientationRedMinDistance = Math.max(0, Math.round(Number(statsState.biorientationRedMinDistance) || 0));
        }
        if (statsState.biorientationRedMaxDistanceUnit === 'px') {
            statsState.biorientationRedMaxDistance = Math.max(0, Math.round(Number(statsState.biorientationRedMaxDistance) || 0));
        }
        lengthUnitSelectElements.forEach((control) => {
            control.setUnit(getLengthUnitForField(control.field));
        });

        if (punctaLineWidthInput) {
            if (statsState.punctaLineWidthUnit === 'um') {
                punctaLineWidthInput.step = '0.01';
                punctaLineWidthInput.min = '0.01';
            } else {
                punctaLineWidthInput.step = '1';
                punctaLineWidthInput.min = '1';
            }
            punctaLineWidthInput.value = formatNumericInputValue(statsState.punctaLineWidth);
        }

        if (cenDotDistanceInput) {
            if (statsState.cenDotDistanceUnit === 'um') {
                cenDotDistanceInput.step = '0.01';
                cenDotDistanceInput.min = '0';
            } else {
                cenDotDistanceInput.step = '1';
                cenDotDistanceInput.min = '0';
            }
            cenDotDistanceInput.value = formatNumericInputValue(statsState.cenDotDistance);
        }

        if (cenDotProximityRadiusInput) {
            if (statsState.cenDotProximityRadiusUnit === 'um') {
                cenDotProximityRadiusInput.step = '0.01';
                cenDotProximityRadiusInput.min = '0';
            } else {
                cenDotProximityRadiusInput.step = '1';
                cenDotProximityRadiusInput.min = '0';
            }
            cenDotProximityRadiusInput.value = formatNumericInputValue(statsState.cenDotProximityRadius);
        }
        if (biorientationRedMinDistanceInput) {
            biorientationRedMinDistanceInput.step = statsState.biorientationRedMinDistanceUnit === 'um' ? '0.01' : '1';
            biorientationRedMinDistanceInput.min = '0';
            biorientationRedMinDistanceInput.value = formatNumericInputValue(statsState.biorientationRedMinDistance);
        }
        if (biorientationRedMaxDistanceInput) {
            biorientationRedMaxDistanceInput.step = statsState.biorientationRedMaxDistanceUnit === 'um' ? '0.01' : '1';
            biorientationRedMaxDistanceInput.min = '0';
            biorientationRedMaxDistanceInput.value = formatNumericInputValue(statsState.biorientationRedMaxDistance);
        }
    }

    function initializeStatsSettings() {
        renderRequiredChannels();
        loadStoredSelections();
        loadStoredAdvancedSettings();
        loadStoredSignalQuantificationSettings();
        loadStoredLengthUnits();
        loadStoredMicronsPerPixel();
        loadStoredUseMetadataScale();
        loadStoredChannelOrderSettings();
        loadStoredWidth();
        loadStoredDistance();
        loadStoredProximityRadius();
        loadStoredBiorientationSettings();
        loadStoredPunctaMode();
        loadStoredNuclearMode();
        loadStoredNuclearContourMode();
        if (!statsState.showLegacyPlugins) {
            statsPlugins.forEach((plugin) => {
                if (plugin.is_legacy) {
                    statsState.selectedPlugins.delete(plugin.id);
                }
            });
        }
        renderStatsToggles();
        renderAdvancedChannelToggles();
        syncStatsUI();
    }

    function renderRequiredChannels() {
        const grid = document.getElementById('requiredChannelGrid');
        if (!grid) return;
        grid.innerHTML = '';
        channelOrder.forEach((channel) => {
            const row = document.createElement('div');
            row.className = 'required-channel-row';
            row.dataset.channel = channel;
            const channelLabel = displayChannelLabel(channel);

            const name = document.createElement('span');
            name.className = 'required-channel-name';
            name.textContent = channelLabel;
            row.appendChild(name);

            const info = buildInfoDot(buildChannelInfoText(channel));
            row.appendChild(info);

            const state = document.createElement('span');
            state.className = 'required-channel-state';
            state.dataset.stateFor = channel;
            state.textContent = 'Optional';
            row.appendChild(state);

            grid.appendChild(row);
        });
    }

    function renderSignalQuantificationModule(list) {
        const row = document.createElement('div');
        row.className = 'stats-toggle-row signal-quantification-row';

        const left = document.createElement('div');
        left.className = 'stats-toggle-left';
        const titleWrap = document.createElement('span');
        titleWrap.className = 'stats-toggle-title-wrap';
        const title = document.createElement('span');
        title.className = 'stats-toggle-title';
        title.textContent = 'Signal Quantification';
        titleWrap.appendChild(title);
        left.appendChild(titleWrap);
        signalQuantificationInfoDot = buildInfoDot(buildSignalQuantificationInfoText());
        signalQuantificationInfoDot.dataset.tooltipWidth = 'wide';
        signalQuantificationInfoDot.dataset.tooltipPlacement = 'right';
        left.appendChild(signalQuantificationInfoDot);
        row.appendChild(left);

        const right = document.createElement('div');
        right.className = 'stats-toggle-right';
        const switchLabel = document.createElement('label');
        switchLabel.className = 'switch';
        signalQuantificationToggle = document.createElement('input');
        signalQuantificationToggle.type = 'checkbox';
        signalQuantificationToggle.checked = !!statsState.signalQuantificationEnabled;
        signalQuantificationToggle.addEventListener('change', () => {
            statsState.signalQuantificationEnabled = signalQuantificationToggle.checked;
            syncSignalSelectedPlugins();
            persistSignalQuantificationSettings();
            persistSelectedPlugins();
            syncStatsUI();
        });
        const slider = document.createElement('span');
        slider.className = 'slider';
        switchLabel.appendChild(signalQuantificationToggle);
        switchLabel.appendChild(slider);
        right.appendChild(switchLabel);
        row.appendChild(right);

        signalQuantificationModeRow = document.createElement('div');
        signalQuantificationModeRow.className = 'nuclear-mode-inline';
        const modeTop = document.createElement('div');
        modeTop.className = 'nuclear-mode-row';
        const modeLabel = document.createElement('label');
        modeLabel.textContent = 'Primary Mode:';
        modeTop.appendChild(modeLabel);
        signalQuantificationModeSelect = buildCustomModeSelect(
            [
                { value: 'puncta_distance', text: 'Puncta Distance' },
                { value: 'nuclear_cell_pair', text: 'Nuclear, Cell-Pair Intensity' },
            ],
            normalizeSignalMode(statsState.signalQuantificationMode),
            (nextMode) => {
                statsState.signalQuantificationMode = normalizeSignalMode(nextMode);
                syncSignalSelectedPlugins();
                persistSignalQuantificationSettings();
                persistSelectedPlugins();
                syncStatsUI();
            },
        );
        modeTop.appendChild(signalQuantificationModeSelect.root);
        signalQuantificationModeRow.appendChild(modeTop);
        signalModePausedNote = document.createElement('p');
        signalModePausedNote.className = 'signal-mode-paused-note';
        signalModePausedNote.setAttribute('aria-hidden', 'true');
        signalQuantificationModeRow.appendChild(signalModePausedNote);
        row.appendChild(signalQuantificationModeRow);

        const signalPanelStack = document.createElement('div');
        signalPanelStack.className = 'signal-mode-stack';

        signalPunctaPanel = document.createElement('div');
        signalPunctaPanel.className = 'signal-mode-panel';

        const punctaModeRow = document.createElement('div');
        punctaModeRow.className = 'nuclear-mode-inline';
        const punctaModeTop = document.createElement('div');
        punctaModeTop.className = 'nuclear-mode-row';
        const punctaModeLabel = document.createElement('label');
        punctaModeLabel.textContent = 'Puncta Source:';
        punctaModeTop.appendChild(punctaModeLabel);
        punctaLineModeSelect = buildCustomModeSelect(
            [
                { value: 'red_puncta', text: 'Red Puncta (Measure Green)' },
                { value: 'green_puncta', text: 'Green Puncta (Measure Red)' },
            ],
            statsState.punctaLineMode === 'green_puncta' ? 'green_puncta' : 'red_puncta',
            (nextMode) => {
                statsState.punctaLineMode = nextMode;
                localStorage.setItem(punctaModeKey, nextMode);
            },
        );
        punctaModeTop.appendChild(punctaLineModeSelect.root);
        punctaModeRow.appendChild(punctaModeTop);
        signalPunctaPanel.appendChild(punctaModeRow);
        punctaLineModeRow = punctaModeRow;

        const widthRow = document.createElement('div');
        widthRow.className = 'stats-distance-inline';
        const widthLine = document.createElement('div');
        widthLine.className = 'stats-distance-line';
        const widthLabel = document.createElement('label');
        widthLabel.textContent = 'Puncta Line Width:';
        widthLine.appendChild(widthLabel);
        const widthGroup = buildLengthInputGroup({
            field: 'punctaLineWidth',
            inputId: 'punctaLineWidthInput',
            minValue: 1,
            defaultValue: 1,
            onChange: () => {
                const fallback = defaultWidthForUnit(statsState.punctaLineWidthUnit);
                const minimum = statsState.punctaLineWidthUnit === 'um' ? 0.01 : 1;
                statsState.punctaLineWidth = parseLengthValue(widthGroup.input.value, statsState.punctaLineWidthUnit, fallback, minimum);
                widthGroup.input.value = formatNumericInputValue(statsState.punctaLineWidth);
                localStorage.setItem(widthKey, String(statsState.punctaLineWidth));
                updateMeasurementScaleHints();
            },
        });
        widthLine.appendChild(widthGroup.controls);
        widthRow.appendChild(widthLine);
        signalPunctaPanel.appendChild(widthRow);
        punctaLineWidthRow = widthRow;
        punctaLineWidthInput = widthGroup.input;

        punctaContourIntensityRow = document.createElement('div');
        punctaContourIntensityRow.className = 'toggle-row stats-inline-toggle';
        const contourText = document.createElement('div');
        contourText.className = 'toggle-text';
        const contourLabel = document.createElement('span');
        contourLabel.className = 'toggle-label';
        contourLabel.textContent = 'Red/Green Contour Intensities';
        contourText.appendChild(contourLabel);
        punctaContourIntensityRow.appendChild(contourText);
        const contourSwitch = document.createElement('label');
        contourSwitch.className = 'switch';
        punctaContourIntensityToggle = document.createElement('input');
        punctaContourIntensityToggle.type = 'checkbox';
        punctaContourIntensityToggle.checked = !!statsState.punctaContourIntensityEnabled;
        punctaContourIntensityToggle.addEventListener('change', () => {
            statsState.punctaContourIntensityEnabled = punctaContourIntensityToggle.checked;
            syncSignalSelectedPlugins();
            persistSignalQuantificationSettings();
            persistSelectedPlugins();
            syncStatsUI();
        });
        const contourSlider = document.createElement('span');
        contourSlider.className = 'slider';
        contourSwitch.appendChild(punctaContourIntensityToggle);
        contourSwitch.appendChild(contourSlider);
        punctaContourIntensityRow.appendChild(contourSwitch);
        signalPunctaPanel.appendChild(punctaContourIntensityRow);
        signalPanelStack.appendChild(signalPunctaPanel);

        signalNuclearPanel = document.createElement('div');
        signalNuclearPanel.className = 'signal-mode-panel';
        const nuclearRow = document.createElement('div');
        nuclearRow.className = 'nuclear-mode-inline';
        const nuclearTop = document.createElement('div');
        nuclearTop.className = 'nuclear-mode-row';
        const nuclearLabel = document.createElement('label');
        nuclearLabel.textContent = 'Nucleus Contour Source:';
        nuclearTop.appendChild(nuclearLabel);
        nuclearModeSelect = buildCustomModeSelect(
            [
                { value: 'green_nucleus', text: 'Green Nucleus (Measure Red)' },
                { value: 'red_nucleus', text: 'Red Nucleus (Measure Green)' },
            ],
            statsState.nuclearCellPairMode === 'red_nucleus' ? 'red_nucleus' : 'green_nucleus',
            (nextMode) => {
                statsState.nuclearCellPairMode = nextMode;
                localStorage.setItem(nuclearModeKey, nextMode);
            },
        );
        nuclearTop.appendChild(nuclearModeSelect.root);
        nuclearRow.appendChild(nuclearTop);
        signalNuclearPanel.appendChild(nuclearRow);
        nuclearModeRow = nuclearRow;

        alternateNucleusDetectionRow = document.createElement('div');
        alternateNucleusDetectionRow.className = 'toggle-row stats-inline-toggle';
        const alternateText = document.createElement('div');
        alternateText.className = 'toggle-text';
        const alternateLabel = document.createElement('span');
        alternateLabel.className = 'toggle-label';
        alternateLabel.textContent = 'Alternate Nucleus Detection';
        alternateText.appendChild(alternateLabel);
        alternateNucleusDetectionRow.appendChild(alternateText);
        const alternateSwitch = document.createElement('label');
        alternateSwitch.className = 'switch';
        alternateNucleusDetectionToggle = document.createElement('input');
        alternateNucleusDetectionToggle.type = 'checkbox';
        alternateNucleusDetectionToggle.checked = !!statsState.alternateNucleusDetectionEnabled;
        alternateNucleusDetectionToggle.addEventListener('change', () => {
            statsState.alternateNucleusDetectionEnabled = alternateNucleusDetectionToggle.checked;
            persistSignalQuantificationSettings();
            syncStatsUI();
        });
        const alternateSlider = document.createElement('span');
        alternateSlider.className = 'slider';
        alternateSwitch.appendChild(alternateNucleusDetectionToggle);
        alternateSwitch.appendChild(alternateSlider);
        alternateNucleusDetectionRow.appendChild(alternateSwitch);
        signalNuclearPanel.appendChild(alternateNucleusDetectionRow);

        const contourModeRow = document.createElement('div');
        contourModeRow.className = 'nuclear-mode-inline nuclear-contour-mode-child';
        const contourModeTop = document.createElement('div');
        contourModeTop.className = 'nuclear-mode-row';
        const contourModeLabel = document.createElement('label');
        contourModeLabel.textContent = 'Nucleus Contour Mode:';
        contourModeTop.appendChild(contourModeLabel);
        nuclearContourModeSelect = buildCustomModeSelect(
            [
                { value: 'balanced', text: 'Balanced' },
                { value: 'aggressive', text: 'Aggressive' },
            ],
            normalizeNuclearContourMode(statsState.nuclearCellPairContourMode),
            (nextMode) => {
                statsState.nuclearCellPairContourMode = normalizeNuclearContourMode(nextMode);
                localStorage.setItem(nuclearContourModeKey, statsState.nuclearCellPairContourMode);
            },
        );
        contourModeTop.appendChild(nuclearContourModeSelect.root);
        contourModeRow.appendChild(contourModeTop);
        signalNuclearPanel.appendChild(contourModeRow);
        nuclearContourModeRow = contourModeRow;

        legacyNuclearCellPairRow = document.createElement('div');
        legacyNuclearCellPairRow.className = 'toggle-row stats-inline-toggle';
        const legacyText = document.createElement('div');
        legacyText.className = 'toggle-text';
        const legacyLabel = document.createElement('span');
        legacyLabel.className = 'toggle-label';
        legacyLabel.textContent = 'Legacy Measurement Compatibility';
        legacyText.appendChild(legacyLabel);
        legacyNuclearCellPairRow.appendChild(legacyText);
        const legacySwitch = document.createElement('label');
        legacySwitch.className = 'switch';
        legacyNuclearCellPairToggle = document.createElement('input');
        legacyNuclearCellPairToggle.type = 'checkbox';
        legacyNuclearCellPairToggle.checked = !!statsState.useLegacyNuclearCellPairPipeline;
        legacyNuclearCellPairToggle.addEventListener('change', () => {
            statsState.useLegacyNuclearCellPairPipeline = legacyNuclearCellPairToggle.checked;
            localStorage.setItem(legacyNuclearCellPairModeKey, String(statsState.useLegacyNuclearCellPairPipeline));
            persistSignalQuantificationSettings();
            syncStatsUI();
        });
        const legacySlider = document.createElement('span');
        legacySlider.className = 'slider';
        legacySwitch.appendChild(legacyNuclearCellPairToggle);
        legacySwitch.appendChild(legacySlider);
        legacyNuclearCellPairRow.appendChild(legacySwitch);
        signalNuclearPanel.appendChild(legacyNuclearCellPairRow);
        signalPanelStack.appendChild(signalNuclearPanel);
        row.appendChild(signalPanelStack);

        list.appendChild(row);
    }

    function renderStatsToggles() {
        const list = document.getElementById('statsList');
        if (!list) return;
        if (signalModeNoticeTimer) {
            window.clearTimeout(signalModeNoticeTimer);
            signalModeNoticeTimer = null;
        }
        signalModeNoticeTransition += 1;
        list.innerHTML = '';
        statToggleElements.clear();
        lengthUnitSelectElements.clear();
        punctaLineWidthInput = null;
        punctaLineWidthRow = null;
        cenDotDistanceInput = null;
        cenDotDistanceRow = null;
        cenDotProximityRadiusInput = null;
        biorientationRedMinDistanceInput = null;
        biorientationRedMaxDistanceInput = null;
        biorientationCollinearityThresholdInput = null;
        biorientationRow = null;
        micronsPerPixelInput = null;
        punctaLineModeRow = null;
        punctaLineModeSelect = null;
        signalQuantificationToggle = null;
        signalQuantificationModeRow = null;
        signalQuantificationModeSelect = null;
        signalQuantificationInfoDot = null;
        signalModePausedNote = null;
        signalPunctaPanel = null;
        signalNuclearPanel = null;
        punctaContourIntensityToggle = null;
        punctaContourIntensityRow = null;
        alternateNucleusDetectionToggle = null;
        alternateNucleusDetectionRow = null;
        legacyNuclearCellPairToggle = null;
        legacyNuclearCellPairRow = null;
        nuclearModeSelect = null;
        nuclearModeRow = null;
        nuclearContourModeSelect = null;
        nuclearContourModeRow = null;
        syncSignalSelectedPlugins();
        renderSignalQuantificationModule(list);

        const visiblePlugins = statsPlugins.filter(
            (plugin) => !signalPrimaryPluginIds.has(plugin.id) && (statsState.showLegacyPlugins || !plugin.is_legacy)
        );

        visiblePlugins.forEach((plugin) => {
            const row = document.createElement('div');
            row.className = 'stats-toggle-row';

            const left = document.createElement('div');
            left.className = 'stats-toggle-left';
            const titleWrap = document.createElement('span');
            titleWrap.className = 'stats-toggle-title-wrap';
            const title = document.createElement('span');
            title.className = 'stats-toggle-title';
            title.textContent = plugin.label || plugin.id;
            titleWrap.appendChild(title);
            left.appendChild(titleWrap);

            const reqLabels = Array.isArray(plugin.required_channel_labels) && plugin.required_channel_labels.length
                ? plugin.required_channel_labels
                : (Array.isArray(plugin.required_channels) ? plugin.required_channels.map(displayChannelLabel) : []);
            const info = buildInfoDot(buildPluginInfoText(plugin, reqLabels));
            left.appendChild(info);
            if (plugin.is_legacy) {
                const legacyBadge = document.createElement('span');
                legacyBadge.className = 'legacy-pill';
                legacyBadge.textContent = 'Legacy';
                left.appendChild(legacyBadge);
            }
            row.appendChild(left);

            const right = document.createElement('div');
            right.className = 'stats-toggle-right';

            const switchLabel = document.createElement('label');
            switchLabel.className = 'switch';
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.dataset.pluginId = plugin.id;
            const slider = document.createElement('span');
            slider.className = 'slider';
            switchLabel.appendChild(input);
            switchLabel.appendChild(slider);
            right.appendChild(switchLabel);
            row.appendChild(right);
            list.appendChild(row);
            statToggleElements.set(plugin.id, input);

            input.addEventListener('change', () => {
                const pluginId = input.dataset.pluginId;
                if (!pluginId) return;
                if (input.checked) {
                    statsState.selectedPlugins.add(pluginId);
                    enforceExclusiveGroup(pluginId);
                    applyPluginDependencies(pluginId);
                } else if (isPluginRequiredBySelection(pluginId)) {
                    input.checked = true;
                    return;
                } else {
                    statsState.selectedPlugins.delete(pluginId);
                }
                persistSelectedPlugins();
                syncStatsUI();
            });

            if (plugin.id === 'PunctaDistance') {
                const modeRow = document.createElement('div');
                modeRow.className = 'nuclear-mode-inline';

                const modeTop = document.createElement('div');
                modeTop.className = 'nuclear-mode-row';

                const modeLabel = document.createElement('label');
                modeLabel.setAttribute('for', 'punctaLineMode');
                modeLabel.textContent = 'Puncta Source:';
                modeTop.appendChild(modeLabel);

                const select = buildCustomModeSelect(
                    [
                        { value: 'red_puncta', text: 'Red Puncta (Measure Green)' },
                        { value: 'green_puncta', text: 'Green Puncta (Measure Red)' },
                    ],
                    statsState.punctaLineMode === 'green_puncta' ? 'green_puncta' : 'red_puncta',
                    (nextMode) => {
                        statsState.punctaLineMode = nextMode;
                        localStorage.setItem(punctaModeKey, nextMode);
                    },
                );
                modeTop.appendChild(select.root);
                modeRow.appendChild(modeTop);

                row.appendChild(modeRow);
                punctaLineModeRow = modeRow;
                punctaLineModeSelect = select;

                const widthRow = document.createElement('div');
                widthRow.className = 'stats-distance-inline';
                const widthLine = document.createElement('div');
                widthLine.className = 'stats-distance-line';

                const widthLabel = document.createElement('label');
                widthLabel.setAttribute('for', 'punctaLineWidthInput');
                widthLabel.textContent = 'Puncta Line Width:';
                widthLine.appendChild(widthLabel);

                const widthGroup = buildLengthInputGroup({
                    field: 'punctaLineWidth',
                    inputId: 'punctaLineWidthInput',
                    minValue: 1,
                    defaultValue: 1,
                    onChange: () => {
                        const fallback = defaultWidthForUnit(statsState.punctaLineWidthUnit);
                        const minimum = statsState.punctaLineWidthUnit === 'um' ? 0.01 : 1;
                        statsState.punctaLineWidth = parseLengthValue(widthGroup.input.value, statsState.punctaLineWidthUnit, fallback, minimum);
                        widthGroup.input.value = formatNumericInputValue(statsState.punctaLineWidth);
                        localStorage.setItem(widthKey, String(statsState.punctaLineWidth));
                        updateMeasurementScaleHints();
                    },
                });
                widthLine.appendChild(widthGroup.controls);
                widthRow.appendChild(widthLine);
                row.appendChild(widthRow);
                punctaLineWidthRow = widthRow;
                punctaLineWidthInput = widthGroup.input;
            }

            if (plugin.id === 'CENDot') {
                const distanceRow = document.createElement('div');
                distanceRow.className = 'stats-distance-inline';
                const distanceLine = document.createElement('div');
                distanceLine.className = 'stats-distance-line';

                const distanceLabel = document.createElement('label');
                distanceLabel.setAttribute('for', 'cenDotDistanceInput');
                distanceLabel.textContent = 'Minimum Signal Distance:';
                distanceLine.appendChild(distanceLabel);

                const distanceGroup = buildLengthInputGroup({
                    field: 'cenDotDistance',
                    inputId: 'cenDotDistanceInput',
                    minValue: 0,
                    defaultValue: 37,
                    onChange: () => {
                        const fallback = defaultDistanceForUnit(statsState.cenDotDistanceUnit);
                        statsState.cenDotDistance = parseLengthValue(distanceGroup.input.value, statsState.cenDotDistanceUnit, fallback, 0);
                        distanceGroup.input.value = formatNumericInputValue(statsState.cenDotDistance);
                        localStorage.setItem(distanceKey, String(statsState.cenDotDistance));
                        updateMeasurementScaleHints();
                    },
                });
                distanceLine.appendChild(distanceGroup.controls);
                distanceRow.appendChild(distanceLine);

                const proximityRadiusLine = document.createElement('div');
                proximityRadiusLine.className = 'stats-distance-line';
                const proximityRadiusLabel = document.createElement('label');
                proximityRadiusLabel.setAttribute('for', 'cenDotProximityRadiusInput');
                proximityRadiusLabel.textContent = 'Signal Proximity Radius:';
                proximityRadiusLine.appendChild(proximityRadiusLabel);

                const proximityRadiusGroup = buildLengthInputGroup({
                    field: 'cenDotProximityRadius',
                    inputId: 'cenDotProximityRadiusInput',
                    minValue: 0,
                    defaultValue: 13,
                    onChange: () => {
                        const fallback = defaultProximityRadiusForUnit(statsState.cenDotProximityRadiusUnit);
                        statsState.cenDotProximityRadius = parseLengthValue(proximityRadiusGroup.input.value, statsState.cenDotProximityRadiusUnit, fallback, 0);
                        proximityRadiusGroup.input.value = formatNumericInputValue(statsState.cenDotProximityRadius);
                        localStorage.setItem(proximityRadiusKey, String(statsState.cenDotProximityRadius));
                        updateMeasurementScaleHints();
                    },
                });
                proximityRadiusLine.appendChild(proximityRadiusGroup.controls);
                distanceRow.appendChild(proximityRadiusLine);
                cenDotProximityRadiusInput = proximityRadiusGroup.input;

                row.appendChild(distanceRow);
                cenDotDistanceRow = distanceRow;
                cenDotDistanceInput = distanceGroup.input;
            }

            if (plugin.id === 'Biorientation') {
                const orientationRow = document.createElement('div');
                orientationRow.className = 'stats-distance-inline';

                const minLine = document.createElement('div');
                minLine.className = 'stats-distance-line';
                const minLabel = document.createElement('label');
                minLabel.setAttribute('for', 'biorientationRedMinDistanceInput');
                minLabel.textContent = 'Minimum Red Puncta Distance:';
                minLine.appendChild(minLabel);
                const minGroup = buildLengthInputGroup({
                    field: 'biorientationRedMinDistance',
                    inputId: 'biorientationRedMinDistanceInput',
                    minValue: 0,
                    defaultValue: 0,
                    onChange: () => {
                        statsState.biorientationRedMinDistance = parseLengthValue(
                            minGroup.input.value,
                            statsState.biorientationRedMinDistanceUnit,
                            defaultBiorientationMinDistanceForUnit(),
                            0
                        );
                        minGroup.input.value = formatNumericInputValue(statsState.biorientationRedMinDistance);
                        localStorage.setItem(biorientationRedMinDistanceKey, String(statsState.biorientationRedMinDistance));
                        updateMeasurementScaleHints();
                    },
                });
                minLine.appendChild(minGroup.controls);
                orientationRow.appendChild(minLine);

                const maxLine = document.createElement('div');
                maxLine.className = 'stats-distance-line';
                const maxLabel = document.createElement('label');
                maxLabel.setAttribute('for', 'biorientationRedMaxDistanceInput');
                maxLabel.textContent = 'Maximum Red Puncta Distance:';
                maxLine.appendChild(maxLabel);
                const maxGroup = buildLengthInputGroup({
                    field: 'biorientationRedMaxDistance',
                    inputId: 'biorientationRedMaxDistanceInput',
                    minValue: 0,
                    defaultValue: 37,
                    onChange: () => {
                        const fallback = defaultBiorientationMaxDistanceForUnit(statsState.biorientationRedMaxDistanceUnit);
                        statsState.biorientationRedMaxDistance = parseLengthValue(
                            maxGroup.input.value,
                            statsState.biorientationRedMaxDistanceUnit,
                            fallback,
                            0
                        );
                        maxGroup.input.value = formatNumericInputValue(statsState.biorientationRedMaxDistance);
                        localStorage.setItem(biorientationRedMaxDistanceKey, String(statsState.biorientationRedMaxDistance));
                        updateMeasurementScaleHints();
                    },
                });
                maxLine.appendChild(maxGroup.controls);
                orientationRow.appendChild(maxLine);

                const thresholdLine = document.createElement('div');
                thresholdLine.className = 'stats-distance-line stats-threshold-line';
                const thresholdLabel = document.createElement('label');
                thresholdLabel.setAttribute('for', 'biorientationCollinearityThresholdInput');
                thresholdLabel.textContent = 'Collinearity Threshold:';
                thresholdLine.appendChild(thresholdLabel);
                const thresholdInput = document.createElement('input');
                thresholdInput.type = 'number';
                thresholdInput.id = 'biorientationCollinearityThresholdInput';
                thresholdInput.min = '0';
                thresholdInput.value = '3';
                thresholdInput.addEventListener('change', () => {
                    const parsed = parseInt(thresholdInput.value, 10);
                    statsState.biorientationCollinearityThreshold = Number.isFinite(parsed) && parsed >= 0 ? parsed : 3;
                    thresholdInput.value = String(statsState.biorientationCollinearityThreshold);
                    localStorage.setItem(biorientationThresholdKey, String(statsState.biorientationCollinearityThreshold));
                });
                const thresholdInputGroup = document.createElement('div');
                thresholdInputGroup.className = 'boxed-number-group compact-control';
                thresholdInputGroup.appendChild(thresholdInput);
                thresholdLine.appendChild(thresholdInputGroup);
                orientationRow.appendChild(thresholdLine);

                row.appendChild(orientationRow);
                biorientationRow = orientationRow;
                biorientationRedMinDistanceInput = minGroup.input;
                biorientationRedMaxDistanceInput = maxGroup.input;
                biorientationCollinearityThresholdInput = thresholdInput;
            }

            if (plugin.id === 'NuclearCellPairIntensity') {
                const modeRow = document.createElement('div');
                modeRow.className = 'nuclear-mode-inline';

                const modeTop = document.createElement('div');
                modeTop.className = 'nuclear-mode-row';

                const modeLabel = document.createElement('label');
                modeLabel.setAttribute('for', 'nuclearCellPairMode');
                modeLabel.textContent = 'Nucleus Contour Source (Nuclear/Cell-Pair Mode):';
                modeTop.appendChild(modeLabel);

                const select = buildCustomModeSelect(
                    [
                        { value: 'green_nucleus', text: 'Green Nucleus (Measure Red)' },
                        { value: 'red_nucleus', text: 'Red Nucleus (Measure Green)' },
                    ],
                    statsState.nuclearCellPairMode === 'red_nucleus' ? 'red_nucleus' : 'green_nucleus',
                    (nextMode) => {
                        statsState.nuclearCellPairMode = nextMode;
                        localStorage.setItem(nuclearModeKey, nextMode);
                    },
                );
                modeTop.appendChild(select.root);
                modeRow.appendChild(modeTop);

                row.appendChild(modeRow);
                nuclearModeSelect = select;
                nuclearModeRow = modeRow;
            }
        });
        renderMeasurementScaleSettings();
    }

    function renderMeasurementScaleSettings() {
        const container = document.getElementById('measurementScaleGroup');
        if (!container) return;
        container.innerHTML = '';
        measurementScalePxPerUmValue = null;
        measurementScaleUmPerPxValue = null;
        measurementScaleExampleHint = null;
        measurementScaleFallbackHint = null;

        const metadataRow = document.createElement('div');
        metadataRow.className = 'measurement-scale-row measurement-scale-toggle-row';

        const metadataText = document.createElement('div');
        metadataText.className = 'measurement-scale-text';
        const metadataTitleRow = document.createElement('div');
        metadataTitleRow.className = 'measurement-scale-title-row';
        const metadataTitle = document.createElement('span');
        metadataTitle.className = 'measurement-scale-title';
        metadataTitle.textContent = 'Auto-Detect Scale From File';
        metadataTitleRow.appendChild(metadataTitle);
        const metadataInfo = buildInfoDot(
            'When enabled, each file uses DV header dx/dy scale when valid. If metadata is missing or invalid, the manual scale fallback below is used.\n\nTurn this off to apply the manual scale fallback to every file in this run.'
        );
        metadataInfo.classList.add('compact');
        metadataTitleRow.appendChild(metadataInfo);
        metadataText.appendChild(metadataTitleRow);

        const fallback = document.createElement('p');
        fallback.className = 'measurement-scale-fallback';
        metadataRow.appendChild(metadataText);
        metadataText.appendChild(fallback);

        const metadataSwitch = document.createElement('label');
        metadataSwitch.className = 'switch';
        const metadataInput = document.createElement('input');
        metadataInput.type = 'checkbox';
        metadataInput.id = 'statsUseMetadataScale';
        metadataInput.checked = !!statsState.useMetadataScale;
        const syncMetadataVisualState = () => {
            metadataRow.classList.toggle('is-off', !metadataInput.checked);
        };
        metadataInput.addEventListener('change', () => {
            statsState.useMetadataScale = metadataInput.checked;
            persistLengthUnitSettings();
            syncMetadataVisualState();
            updateMeasurementScaleHints();
        });
        const metadataSlider = document.createElement('span');
        metadataSlider.className = 'slider';
        metadataSwitch.appendChild(metadataInput);
        metadataSwitch.appendChild(metadataSlider);
        metadataRow.appendChild(metadataSwitch);
        syncMetadataVisualState();

        const scaleRow = document.createElement('div');
        scaleRow.className = 'measurement-scale-row measurement-scale-manual-row';

        const scaleText = document.createElement('div');
        scaleText.className = 'measurement-scale-text';

        const scaleTitleRow = document.createElement('div');
        scaleTitleRow.className = 'measurement-scale-title-row';

        const scaleTitle = document.createElement('span');
        scaleTitle.className = 'measurement-scale-title';
        scaleTitle.textContent = 'Manual Scale Fallback';
        scaleTitleRow.appendChild(scaleTitle);

        const scaleInfo = buildInfoDot(
            'Enter the manual scale fallback as \u00b5m/px (how many micrometers one pixel represents).\n\nEnter \u00b5m/px, not px/\u00b5m. Example: if 1 pixel = 0.1 \u00b5m, enter 0.1.\nFormula: pixels = micrometers / (\u00b5m/px).\n\nWhen auto-detect scale is enabled and dx/dy are anisotropic, distance checks use:\ndistance in \u00b5m = sqrt((DeltaX_px * dx)^2 + (DeltaY_px * dy)^2).\n\nFor single-width operations (like line thickness), conversion uses a geometric proxy:\nproxy \u00b5m/px = sqrt(dx * dy).\n\nUsed for all plugin length settings when unit is \u00b5m.'
        );
        scaleInfo.classList.add('compact');
        scaleTitleRow.appendChild(scaleInfo);

        scaleText.appendChild(scaleTitleRow);

        const live = document.createElement('p');
        live.className = 'measurement-scale-live';
        live.appendChild(document.createTextNode('Current Scale: 1 \u00b5m = '));
        const livePxValue = document.createElement('span');
        livePxValue.className = 'measurement-scale-value';
        live.appendChild(livePxValue);
        live.appendChild(document.createTextNode(' px ('));
        const liveUmValue = document.createElement('span');
        liveUmValue.className = 'measurement-scale-value';
        live.appendChild(liveUmValue);
        live.appendChild(document.createTextNode(' \u00b5m/px).'));
        scaleText.appendChild(live);

        const example = document.createElement('p');
        example.className = 'measurement-scale-example';
        scaleText.appendChild(example);

        scaleRow.appendChild(scaleText);

        const inputGroup = document.createElement('div');
        inputGroup.className = 'boxed-number-group measurement-scale-input-group compact-control';
        const input = document.createElement('input');
        input.type = 'number';
        input.id = 'statsMicronsPerPixelInput';
        input.className = 'measurement-scale-input';
        input.min = '0.0001';
        input.step = '0.0001';
        input.placeholder = '0.1';
        input.value = formatNumericInputValue(statsState.micronsPerPixel, 4);
        input.addEventListener('change', () => {
            statsState.micronsPerPixel = sanitizeMicronsPerPixel(input.value);
            input.value = formatNumericInputValue(statsState.micronsPerPixel, 4);
            persistLengthUnitSettings();
            syncLengthControls();
            updateMeasurementScaleHints();
        });
        inputGroup.appendChild(input);
        scaleRow.appendChild(inputGroup);

        container.appendChild(metadataRow);
        container.appendChild(scaleRow);
        micronsPerPixelInput = input;
        useMetadataScaleInput = metadataInput;
        measurementScalePxPerUmValue = livePxValue;
        measurementScaleUmPerPxValue = liveUmValue;
        measurementScaleExampleHint = example;
        measurementScaleFallbackHint = fallback;
        updateMeasurementScaleHints();
        renderWavelengthChannelOrderSettings();
    }

    function channelSlugClass(channel) {
        if (channel === 'DIC') return 'dic';
        if (channel === 'channel_blue') return 'blue';
        if (channel === 'channel_red') return 'red';
        if (channel === 'channel_green') return 'green';
        return '';
    }

    function channelOrderFromBar(bar) {
        if (!bar) return normalizeChannelOrder(statsState.fallbackChannelOrder);
        return normalizeChannelOrder(
            [...bar.querySelectorAll('[data-channel-role]')].map((chip) => chip.dataset.channelRole)
        );
    }

    function sameChannelOrder(first, second) {
        return JSON.stringify(normalizeChannelOrder(first)) === JSON.stringify(normalizeChannelOrder(second));
    }

    function orderFallbackChannelBar(order, options = {}) {
        if (!fallbackChannelOrderBar) return;
        const normalized = normalizeChannelOrder(order);
        const chipsByChannel = new Map(
            [...fallbackChannelOrderBar.querySelectorAll('[data-channel-role]')]
                .map((chip) => [chip.dataset.channelRole, chip])
        );
        const shouldAnimate = options.animate
            && !window.matchMedia('(prefers-reduced-motion: reduce)').matches
            && typeof Element !== 'undefined'
            && typeof Element.prototype.animate === 'function';
        const firstRects = shouldAnimate
            ? new Map([...chipsByChannel].map(([channel, chip]) => [channel, chip.getBoundingClientRect()]))
            : null;
        normalized.forEach((channel) => {
            const chip = fallbackChannelOrderBar.querySelector(`[data-channel-role="${channel}"]`);
            if (chip) fallbackChannelOrderBar.appendChild(chip);
        });
        if (!shouldAnimate) return;
        normalized.forEach((channel) => {
            const chip = chipsByChannel.get(channel);
            const firstRect = firstRects.get(channel);
            if (!chip || !firstRect) return;
            const lastRect = chip.getBoundingClientRect();
            const deltaX = firstRect.left - lastRect.left;
            const deltaY = firstRect.top - lastRect.top;
            if (Math.abs(deltaX) < 0.5 && Math.abs(deltaY) < 0.5) return;
            chip.animate(
                [
                    { transform: `translate(${deltaX}px, ${deltaY}px)`, opacity: 0.72 },
                    { transform: 'translate(0, 0)', opacity: 1 },
                ],
                { duration: 180, easing: 'cubic-bezier(0.2, 0, 0.2, 1)' }
            );
        });
    }

    function syncFallbackChannelOrderActions() {
        const currentOrder = channelOrderFromBar(fallbackChannelOrderBar);
        if (fallbackChannelOrderBackButton) {
            fallbackChannelOrderBackButton.disabled = fallbackChannelOrderActionLocked || fallbackChannelOrderUndoStack.length === 0;
        }
        if (fallbackChannelOrderResetButton) {
            fallbackChannelOrderResetButton.disabled = fallbackChannelOrderActionLocked || sameChannelOrder(currentOrder, fallbackChannelOrderResetBaseline);
        }
    }

    function lockFallbackChannelOrderActions() {
        fallbackChannelOrderActionLocked = true;
        syncFallbackChannelOrderActions();
        window.setTimeout(() => {
            fallbackChannelOrderActionLocked = false;
            syncFallbackChannelOrderActions();
        }, fallbackChannelOrderActionLockMs);
    }

    function setFallbackChannelOrder(order, options = {}) {
        const normalized = normalizeChannelOrder(order);
        statsState.fallbackChannelOrder = normalized;
        orderFallbackChannelBar(normalized, { animate: options.animate });
        if (options.clearHistory) {
            fallbackChannelOrderUndoStack.length = 0;
        }
        if (options.persist !== false) {
            persistChannelOrderSettings();
        }
        syncFallbackChannelOrderActions();
    }

    function pushFallbackChannelOrderUndo(order) {
        const normalized = normalizeChannelOrder(order);
        fallbackChannelOrderUndoStack.push(normalized);
        if (fallbackChannelOrderUndoStack.length > 20) {
            fallbackChannelOrderUndoStack.shift();
        }
    }

    function setFallbackChannelOrderResetBaseline(order) {
        fallbackChannelOrderResetBaseline = normalizeChannelOrder(order);
        fallbackChannelOrderUndoStack.length = 0;
        syncFallbackChannelOrderActions();
    }

    function syncWavelengthChannelOrderStatus(animate = false) {
        if (!useMetadataChannelOrderInput) return;
        const metadataEnabled = useMetadataChannelOrderInput.checked;
        const nextText = useMetadataChannelOrderInput.checked
            ? 'Metadata mode enabled'
            : 'Fallback-only mode enabled';
        const nextModeText = metadataEnabled ? 'Backup order' : 'Primary order';
        let changed = false;
        if (wavelengthChannelOrderStatus) {
            wavelengthChannelOrderStatus.classList.toggle('is-metadata-enabled', metadataEnabled);
            wavelengthChannelOrderStatus.classList.toggle('is-metadata-off', !metadataEnabled);
            if (wavelengthChannelOrderStatus.textContent !== nextText) {
                wavelengthChannelOrderStatus.textContent = nextText;
                changed = true;
            }
        }
        if (fallbackChannelOrderModeLabel) {
            fallbackChannelOrderModeLabel.classList.toggle('is-backup', metadataEnabled);
            fallbackChannelOrderModeLabel.classList.toggle('is-primary', !metadataEnabled);
            if (fallbackChannelOrderModeLabel.textContent !== nextModeText) {
                fallbackChannelOrderModeLabel.textContent = nextModeText;
                changed = true;
            }
        }
        if (!animate || !changed) return;
        [wavelengthChannelOrderStatus, fallbackChannelOrderModeLabel].forEach((element) => {
            if (!element) return;
            element.classList.remove('is-fading-down');
            void element.offsetWidth;
            element.classList.add('is-fading-down');
        });
    }

    function setupChannelOrderDrag(bar) {
        if (!bar) return;
        if (!window.Sortable || typeof window.Sortable.create !== 'function') return;
        window.Sortable.create(bar, {
            animation: 150,
            onStart() {
                bar.dataset.previousChannelOrder = JSON.stringify(channelOrderFromBar(bar));
            },
            onEnd() {
                const previousOrder = normalizeChannelOrder(JSON.parse(bar.dataset.previousChannelOrder || '[]'));
                const nextOrder = channelOrderFromBar(bar);
                delete bar.dataset.previousChannelOrder;
                if (!sameChannelOrder(previousOrder, nextOrder)) {
                    pushFallbackChannelOrderUndo(previousOrder);
                }
                setFallbackChannelOrder(nextOrder);
            },
        });
    }

    function renderWavelengthChannelOrderSettings() {
        const container = document.getElementById('wavelengthChannelOrderGroup');
        if (!container) return;
        container.innerHTML = '';

        const metadataRow = document.createElement('div');
        metadataRow.className = 'measurement-scale-row measurement-scale-toggle-row';
        const metadataText = document.createElement('div');
        metadataText.className = 'measurement-scale-text';
        const metadataTitleRow = document.createElement('div');
        metadataTitleRow.className = 'measurement-scale-title-row';
        const metadataTitle = document.createElement('span');
        metadataTitle.className = 'measurement-scale-title';
        metadataTitle.textContent = 'Auto-Detect Channels From File';
        metadataTitleRow.appendChild(metadataTitle);
        const metadataInfo = buildInfoDot(
            'When enabled, each DV or TIFF file uses metadata-derived wavelength ordering when the file stores usable channel metadata.\n\nIf metadata is unavailable or invalid, the selected manual channel fallback order is used. Turn this off to apply the manual channel fallback order to every new file.'
        );
        metadataInfo.classList.add('compact');
        metadataTitleRow.appendChild(metadataInfo);
        metadataText.appendChild(metadataTitleRow);
        wavelengthChannelOrderStatus = document.createElement('p');
        wavelengthChannelOrderStatus.className = 'measurement-scale-fallback channel-order-status';
        metadataText.appendChild(wavelengthChannelOrderStatus);
        metadataRow.appendChild(metadataText);

        const metadataSwitch = document.createElement('label');
        metadataSwitch.className = 'switch';
        useMetadataChannelOrderInput = document.createElement('input');
        useMetadataChannelOrderInput.type = 'checkbox';
        useMetadataChannelOrderInput.id = 'statsUseMetadataChannelOrder';
        useMetadataChannelOrderInput.checked = !!statsState.useMetadataChannelOrder;
        useMetadataChannelOrderInput.addEventListener('change', () => {
            statsState.useMetadataChannelOrder = useMetadataChannelOrderInput.checked;
            persistChannelOrderSettings();
            metadataRow.classList.toggle('is-off', !useMetadataChannelOrderInput.checked);
            syncWavelengthChannelOrderStatus(true);
        });
        const metadataSlider = document.createElement('span');
        metadataSlider.className = 'slider';
        metadataSwitch.appendChild(useMetadataChannelOrderInput);
        metadataSwitch.appendChild(metadataSlider);
        metadataRow.appendChild(metadataSwitch);
        metadataRow.classList.toggle('is-off', !useMetadataChannelOrderInput.checked);
        wavelengthChannelOrderStatus.addEventListener('animationend', () => {
            wavelengthChannelOrderStatus.classList.remove('is-fading-down');
        });

        const fallbackRow = document.createElement('div');
        fallbackRow.className = 'measurement-scale-row channel-order-fallback-row';
        const fallbackText = document.createElement('div');
        fallbackText.className = 'measurement-scale-text';
        const fallbackTitleRow = document.createElement('div');
        fallbackTitleRow.className = 'measurement-scale-title-row';
        const fallbackTitle = document.createElement('span');
        fallbackTitle.className = 'measurement-scale-title';
        fallbackTitle.textContent = 'Manual Channel Fallback Order';
        fallbackTitleRow.appendChild(fallbackTitle);
        const fallbackInfo = buildInfoDot(
            'Sets the manual channel fallback order CytoCV should use when a file does not include usable wavelength information, or when channel auto-detection is turned off.\n\nTo change the order, select a channel box and drag it to the image plane where it belongs. For example, if image 1 is Blue and image 2 is Green, drag Blue into the first position and Green into the second.\n\nThis gives new uploads a starting channel order. You can still adjust a single file later on the preprocess page if one image is different.'
        );
        fallbackInfo.classList.add('compact');
        fallbackTitleRow.appendChild(fallbackInfo);
        fallbackText.appendChild(fallbackTitleRow);
        const orderLabel = document.createElement('span');
        orderLabel.className = 'channel-order-label';
        orderLabel.textContent = 'Select wavelength order:';
        fallbackText.appendChild(orderLabel);
        const orderHelp = document.createElement('p');
        orderHelp.className = 'channel-order-drag-help';
        orderHelp.textContent = 'Drag and drop boxes to edit order.';
        fallbackText.appendChild(orderHelp);
        fallbackRow.appendChild(fallbackText);

        const orderControl = document.createElement('div');
        orderControl.className = 'channel-order-control';
        const planeRow = document.createElement('div');
        planeRow.className = 'channel-plane-row';
        ['Image 1', 'Image 2', 'Image 3', 'Image 4'].forEach((label) => {
            const span = document.createElement('span');
            span.textContent = label;
            planeRow.appendChild(span);
        });
        fallbackChannelOrderBar = document.createElement('div');
        fallbackChannelOrderBar.className = 'channel-bar';
        normalizeChannelOrder(statsState.fallbackChannelOrder).forEach((channel) => {
            const chip = document.createElement('span');
            chip.className = `channel-chip ${channelSlugClass(channel)}`.trim();
            chip.dataset.channelRole = channel;
            const grip = document.createElement('span');
            grip.className = 'channel-chip-grip';
            grip.setAttribute('aria-hidden', 'true');
            const label = document.createElement('span');
            label.className = 'channel-chip-label';
            label.textContent = displayChannelLabel(channel);
            chip.appendChild(grip);
            chip.appendChild(label);
            fallbackChannelOrderBar.appendChild(chip);
        });
        orderControl.appendChild(planeRow);
        orderControl.appendChild(fallbackChannelOrderBar);
        const actionRow = document.createElement('div');
        actionRow.className = 'channel-order-actions';
        actionRow.setAttribute('aria-label', 'Fallback channel order actions');
        const actionCopy = document.createElement('span');
        actionCopy.className = 'channel-order-action-copy';
        fallbackChannelOrderModeLabel = actionCopy;
        const actionGroup = document.createElement('div');
        actionGroup.className = 'channel-order-action-group';
        fallbackChannelOrderBackButton = document.createElement('button');
        fallbackChannelOrderBackButton.type = 'button';
        fallbackChannelOrderBackButton.className = 'channel-order-action-btn';
        fallbackChannelOrderBackButton.setAttribute('aria-label', 'Back');
        fallbackChannelOrderBackButton.title = 'Back';
        fallbackChannelOrderBackButton.innerHTML = '<svg class="channel-order-action-icon is-back" aria-hidden="true" focusable="false" viewBox="0 0 12 12"><path d="M4.8 3.1 2.2 5.7l2.6 2.6"></path><path d="M2.6 5.7h4a3 3 0 1 1-1.8 5.4"></path></svg><span class="channel-order-action-label">Back</span>';
        fallbackChannelOrderBackButton.addEventListener('click', () => {
            if (fallbackChannelOrderActionLocked) return;
            const previousOrder = fallbackChannelOrderUndoStack.pop();
            if (!previousOrder) return;
            lockFallbackChannelOrderActions();
            setFallbackChannelOrder(previousOrder, { animate: true });
        });
        fallbackChannelOrderResetButton = document.createElement('button');
        fallbackChannelOrderResetButton.type = 'button';
        fallbackChannelOrderResetButton.className = 'channel-order-action-btn';
        fallbackChannelOrderResetButton.setAttribute('aria-label', 'Reset');
        fallbackChannelOrderResetButton.title = 'Reset';
        fallbackChannelOrderResetButton.innerHTML = '<svg class="channel-order-action-icon is-reset" aria-hidden="true" focusable="false" viewBox="0 0 12 12"><path d="M9.4 5.4A3.5 3.5 0 1 0 8.3 8.5"></path><path d="M9.4 2.6v2.8H6.6"></path></svg><span class="channel-order-action-label">Reset</span>';
        fallbackChannelOrderResetButton.addEventListener('click', () => {
            if (fallbackChannelOrderActionLocked) return;
            if (sameChannelOrder(channelOrderFromBar(fallbackChannelOrderBar), fallbackChannelOrderResetBaseline)) return;
            lockFallbackChannelOrderActions();
            setFallbackChannelOrder(fallbackChannelOrderResetBaseline, { clearHistory: true, animate: true });
        });
        actionGroup.appendChild(fallbackChannelOrderBackButton);
        actionGroup.appendChild(fallbackChannelOrderResetButton);
        actionRow.appendChild(actionCopy);
        actionRow.appendChild(actionGroup);
        orderControl.appendChild(actionRow);
        const actionDivider = document.createElement('span');
        actionDivider.className = 'channel-order-action-divider';
        actionDivider.setAttribute('aria-hidden', 'true');
        orderControl.appendChild(actionDivider);
        fallbackRow.appendChild(orderControl);

        container.appendChild(metadataRow);
        container.appendChild(fallbackRow);
        setupChannelOrderDrag(fallbackChannelOrderBar);
        syncFallbackChannelOrderActions();
        syncWavelengthChannelOrderStatus();
    }

    function setSmoothText(element, nextText) {
        if (!element) return;
        const normalized = typeof nextText === 'string' ? nextText : String(nextText ?? '');
        if ((element.textContent || '') === normalized) return;

        if (element._smoothTextTimer) {
            clearTimeout(element._smoothTextTimer);
            element._smoothTextTimer = null;
        }

        element.classList.add('smooth-text-fading');
        element._smoothTextTimer = window.setTimeout(() => {
            element.textContent = normalized;
            element.classList.remove('smooth-text-fading');
            element._smoothTextTimer = null;
        }, 105);
    }

    function setSlideInText(element, nextText) {
        if (!element) return;
        const normalized = typeof nextText === 'string' ? nextText : String(nextText ?? '');
        if ((element.textContent || '') === normalized) return;
        element.textContent = normalized;
        if (element._slideInTimer) {
            clearTimeout(element._slideInTimer);
            element._slideInTimer = null;
        }
        element.classList.remove('smooth-text-slide-in');
        void element.offsetWidth;
        element.classList.add('smooth-text-slide-in');
        element._slideInTimer = window.setTimeout(() => {
            element.classList.remove('smooth-text-slide-in');
            element._slideInTimer = null;
        }, 260);
    }

    function updateMeasurementScaleHints() {
        if (!measurementScalePxPerUmValue || !measurementScaleUmPerPxValue || !measurementScaleExampleHint) return;

        if (useMetadataScaleInput) {
            const metadataRow = useMetadataScaleInput.closest('.measurement-scale-row');
            if (metadataRow) metadataRow.classList.toggle('is-off', !useMetadataScaleInput.checked);
        }

        const umPerPx = sanitizeMicronsPerPixel(statsState.micronsPerPixel);
        const pxPerUm = umPerPx > 0 ? (1 / umPerPx) : 0;
        setSlideInText(measurementScalePxPerUmValue, formatNumericInputValue(pxPerUm, 3));
        setSlideInText(measurementScaleUmPerPxValue, formatNumericInputValue(umPerPx, 4));

        const examples = [];
        if (statsState.punctaLineWidthUnit === 'um') {
            const pxValue = convertLengthToPixels(statsState.punctaLineWidth, statsState.punctaLineWidthUnit, 1, 1);
            examples.push(
                `Puncta Line Width ${formatNumericInputValue(statsState.punctaLineWidth, 3)} µm -> ${pxValue} px`
            );
        }
        if (statsState.cenDotDistanceUnit === 'um') {
            const pxValue = convertLengthToPixels(statsState.cenDotDistance, statsState.cenDotDistanceUnit, 0, 37);
            examples.push(
                `Minimum Signal Distance ${formatNumericInputValue(statsState.cenDotDistance, 3)} µm -> ${pxValue} px`
            );
        }
        if (statsState.cenDotProximityRadiusUnit === 'um') {
            const pxValue = convertLengthToPixels(statsState.cenDotProximityRadius, statsState.cenDotProximityRadiusUnit, 0, 13);
            examples.push(
                `Signal Proximity Radius ${formatNumericInputValue(statsState.cenDotProximityRadius, 3)} µm -> ${pxValue} px`
            );
        }

        if (statsState.biorientationRedMinDistanceUnit === 'um') {
            const pxValue = convertLengthToPixels(statsState.biorientationRedMinDistance, statsState.biorientationRedMinDistanceUnit, 0, 0);
            examples.push(
                `Biorientation Minimum Red Distance ${formatNumericInputValue(statsState.biorientationRedMinDistance, 3)} µm -> ${pxValue} px`
            );
        }
        if (statsState.biorientationRedMaxDistanceUnit === 'um') {
            const pxValue = convertLengthToPixels(statsState.biorientationRedMaxDistance, statsState.biorientationRedMaxDistanceUnit, 0, 37);
            examples.push(
                `Biorientation Maximum Red Distance ${formatNumericInputValue(statsState.biorientationRedMaxDistance, 3)} µm -> ${pxValue} px`
            );
        }

        setSmoothText(
            measurementScaleExampleHint,
            examples.length
                ? `Live Conversion: ${examples.join(' | ')}`
                : 'Set a plugin length unit to µm to preview its pixel conversion here.'
        );

        if (measurementScaleFallbackHint) {
            measurementScaleFallbackHint.classList.toggle('is-metadata-enabled', !!statsState.useMetadataScale);
            measurementScaleFallbackHint.classList.toggle('is-metadata-off', !statsState.useMetadataScale);
            setSlideInText(
                measurementScaleFallbackHint,
                statsState.useMetadataScale
                    ? 'Metadata mode enabled'
                    : 'Metadata mode disabled'
            );
        }
    }

    function renderAdvancedChannelToggles() {
        const container = document.getElementById('advancedChannelGroup');
        if (!container) return;
        container.innerHTML = '';
        channelToggleElements.clear();
        channelRowElements.clear();

        channelOrder.forEach((channel) => {
            const row = document.createElement('div');
            row.className = 'toggle-row subtoggle';
            row.id = `channelCheckRow_${channel}`;
            const channelLabel = displayChannelLabel(channel);

            const text = document.createElement('div');
            text.className = 'toggle-text';
            const labelRow = document.createElement('span');
            labelRow.className = 'toggle-label-row';
            const label = document.createElement('span');
            label.className = 'toggle-label';
            label.textContent = `Require ${channelLabel} channel`;
            labelRow.appendChild(label);
            const info = buildInfoDot(buildAdvancedChannelInfo(channel));
            info.classList.add('compact');
            labelRow.appendChild(info);
            text.appendChild(labelRow);
            row.appendChild(text);

            const switchLabel = document.createElement('label');
            switchLabel.className = 'switch';
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.id = `enforceChannel_${channel}`;
            const slider = document.createElement('span');
            slider.className = 'slider';
            switchLabel.appendChild(input);
            switchLabel.appendChild(slider);
            row.appendChild(switchLabel);
            container.appendChild(row);

            input.addEventListener('change', () => {
                if (input.checked) {
                    statsState.manualRequiredChannels.add(channel);
                } else {
                    statsState.manualRequiredChannels.delete(channel);
                }
                persistAdvancedSettings();
                syncStatsUI();
            });

            channelToggleElements.set(channel, input);
            channelRowElements.set(channel, row);
        });

        const greenContourFilterEnabled = document.getElementById('greenContourFilterEnabled');
        const dotSplitEnabled = document.getElementById('dotSplitEnabled');
        const dotSplitTargetMount = document.getElementById('dotSplitTargetMount');
        const greenDotSplitModeMount = document.getElementById('greenDotSplitModeMount');
        const redDotSplitModeMount = document.getElementById('redDotSplitModeMount');
        const moduleToggle = document.getElementById('cytocvAnalysisEnabled');
        const layerToggle = document.getElementById('enforceLayerCount');
        const wavelengthToggle = document.getElementById('enforceWavelengths');
        const legacyToggle = document.getElementById('showLegacyPlugins');
        if (greenContourFilterEnabled) {
            greenContourFilterEnabled.addEventListener('change', () => {
                statsState.greenContourFilterEnabled = greenContourFilterEnabled.checked;
                persistAdvancedSettings();
                syncStatsUI();
            });
        }
        if (dotSplitEnabled) {
            dotSplitEnabled.addEventListener('change', () => {
                applyDotSplitTargetToState(
                    dotSplitTargetSelect
                        ? dotSplitTargetSelect.value
                        : dotSplitTargetFromFlags(statsState.greenDotSplitEnabled, statsState.redDotSplitEnabled),
                    dotSplitEnabled.checked
                );
                persistAdvancedSettings();
                syncStatsUI();
            });
        }
        if (dotSplitTargetMount && !dotSplitTargetSelect) {
            dotSplitTargetSelect = buildCustomModeSelect(
                [
                    { value: 'both', text: 'Both' },
                    { value: 'green', text: 'Green' },
                    { value: 'red', text: 'Red' },
                ],
                dotSplitTargetFromFlags(statsState.greenDotSplitEnabled, statsState.redDotSplitEnabled),
                (nextTarget) => {
                    applyDotSplitTargetToState(nextTarget, true);
                    persistAdvancedSettings();
                    syncStatsUI();
                },
            );
            dotSplitTargetMount.appendChild(dotSplitTargetSelect.root);
        }
        if (greenDotSplitModeMount && !greenDotSplitModeSelect) {
            greenDotSplitModeSelect = buildCustomModeSelect(
                [
                    { value: 'balanced', text: 'Balanced' },
                    { value: 'aggressive', text: 'Aggressive' },
                ],
                normalizeGreenDotSplitMode(statsState.greenDotSplitMode),
                (nextMode) => {
                    statsState.greenDotSplitMode = normalizeGreenDotSplitMode(nextMode);
                    persistAdvancedSettings();
                    syncStatsUI();
                },
            );
            greenDotSplitModeMount.appendChild(greenDotSplitModeSelect.root);
        }
        if (redDotSplitModeMount && !redDotSplitModeSelect) {
            redDotSplitModeSelect = buildCustomModeSelect(
                [
                    { value: 'balanced', text: 'Balanced' },
                    { value: 'aggressive', text: 'Aggressive' },
                ],
                normalizeRedDotSplitMode(statsState.redDotSplitMode),
                (nextMode) => {
                    statsState.redDotSplitMode = normalizeRedDotSplitMode(nextMode);
                    persistAdvancedSettings();
                    syncStatsUI();
                },
            );
            redDotSplitModeMount.appendChild(redDotSplitModeSelect.root);
        }
        if (moduleToggle) {
            moduleToggle.addEventListener('change', () => {
                statsState.moduleEnabled = moduleToggle.checked;
                persistAdvancedSettings();
                syncStatsUI();
            });
        }
        if (layerToggle) {
            layerToggle.addEventListener('change', () => {
                statsState.enforceLayerCount = layerToggle.checked;
                persistAdvancedSettings();
                syncStatsUI();
            });
        }
        if (wavelengthToggle) {
            wavelengthToggle.addEventListener('change', () => {
                statsState.enforceAllWavelengths = wavelengthToggle.checked;
                persistAdvancedSettings();
                syncStatsUI();
            });
        }
        if (legacyToggle) {
            legacyToggle.addEventListener('change', () => {
                statsState.showLegacyPlugins = !!legacyToggle.checked;
                if (!statsState.showLegacyPlugins) {
                    statsPlugins.forEach((plugin) => {
                        if (plugin.is_legacy) {
                            statsState.selectedPlugins.delete(plugin.id);
                        }
                    });
                }
                renderStatsToggles();
                persistSelectedPlugins();
                persistAdvancedSettings();
                syncStatsUI();
            });
        }
    }

    function loadStoredSelections() {
        const initialized = localStorage.getItem(initializedKey) === '1';
        selectionsInitializedBeforeLoad = initialized;
        let stored = [];
        try {
            stored = JSON.parse(localStorage.getItem(selectionKey) || '[]');
        } catch (err) {
            stored = [];
        }
        if (!Array.isArray(stored)) {
            stored = [];
        }

        if (!initialized) {
            // First-run plugin defaults are applied by the Signal Quantification state.
            persistSelectedPlugins();
        } else {
            stored.forEach((pluginId) => {
                if (pluginMap.has(pluginId)) {
                    statsState.selectedPlugins.add(pluginId);
                    enforceExclusiveGroup(pluginId);
                }
            });
            normalizeExclusiveSelections();
        }

        [...statsState.selectedPlugins].forEach((pluginId) => applyPluginDependencies(pluginId));
    }

    function loadStoredAdvancedSettings() {
        let stored = {};
        try {
            stored = JSON.parse(localStorage.getItem(advancedKey) || '{}');
        } catch (err) {
            stored = {};
        }

        statsState.greenContourFilterEnabled = typeof stored.greenContourFilterEnabled === 'boolean' ? stored.greenContourFilterEnabled : false;
        if (typeof stored.greenDotSplitEnabled === 'boolean') {
            statsState.greenDotSplitEnabled = stored.greenDotSplitEnabled;
        } else {
            const splitRaw = localStorage.getItem(greenDotSplitKey) ?? localStorage.getItem(legacyBiorientationGreenSplitKey);
            statsState.greenDotSplitEnabled = splitRaw === null
                ? true
                : !['0', 'false', 'off', 'no'].includes(String(splitRaw).trim().toLowerCase());
        }
        statsState.greenDotSplitMode = normalizeGreenDotSplitMode(
            stored.greenDotSplitMode || localStorage.getItem(greenDotSplitModeKey)
        );
        if (typeof stored.redDotSplitEnabled === 'boolean') {
            statsState.redDotSplitEnabled = stored.redDotSplitEnabled;
        } else {
            const redSplitRaw = localStorage.getItem(redDotSplitKey);
            statsState.redDotSplitEnabled = redSplitRaw === null
                ? true
                : !['0', 'false', 'off', 'no'].includes(String(redSplitRaw).trim().toLowerCase());
        }
        statsState.redDotSplitMode = normalizeRedDotSplitMode(
            stored.redDotSplitMode || localStorage.getItem(redDotSplitModeKey)
        );
        statsState.moduleEnabled = typeof stored.moduleEnabled === 'boolean' ? stored.moduleEnabled : false;
        statsState.enforceLayerCount = typeof stored.enforceLayerCount === 'boolean' ? stored.enforceLayerCount : false;
        statsState.enforceAllWavelengths = typeof stored.enforceAllWavelengths === 'boolean' ? stored.enforceAllWavelengths : false;
        statsState.showLegacyPlugins = typeof stored.showLegacyPlugins === 'boolean' ? stored.showLegacyPlugins : false;
        statsState.manualRequiredChannels = new Set(
            Array.isArray(stored.manualRequiredChannels)
                ? stored.manualRequiredChannels.filter((channel) => channelOrder.includes(channel))
                : []
        );
    }

    function loadStoredSignalQuantificationSettings() {
        let stored = {};
        try {
            stored = JSON.parse(localStorage.getItem(signalQuantificationKey) || '{}');
        } catch (err) {
            stored = {};
        }
        const hasPrimary = [...statsState.selectedPlugins].some((pluginId) => signalPrimaryPluginIds.has(pluginId));
        statsState.signalQuantificationEnabled = typeof stored.enabled === 'boolean'
            ? stored.enabled
            : (selectionsInitializedBeforeLoad ? hasPrimary : true);
        if (typeof stored.mode === 'string') {
            statsState.signalQuantificationMode = normalizeSignalMode(stored.mode);
        } else if (statsState.selectedPlugins.has('NuclearCellPairIntensity') && !statsState.selectedPlugins.has('PunctaDistance')) {
            statsState.signalQuantificationMode = 'nuclear_cell_pair';
        } else {
            statsState.signalQuantificationMode = 'puncta_distance';
        }
        statsState.punctaContourIntensityEnabled = typeof stored.punctaContourIntensityEnabled === 'boolean'
            ? stored.punctaContourIntensityEnabled
            : statsState.selectedPlugins.has('GreenRedIntensity');
        const legacyAlternateRedDetection = typeof stored.alternateRedDetection === 'boolean'
            ? stored.alternateRedDetection
            : null;
        statsState.alternateNucleusDetectionEnabled = typeof stored.alternateNucleusDetectionEnabled === 'boolean'
            ? stored.alternateNucleusDetectionEnabled
            : !!legacyAlternateRedDetection;
        statsState.useLegacyNuclearCellPairPipeline = typeof stored.useLegacyNuclearCellPairPipeline === 'boolean'
            ? stored.useLegacyNuclearCellPairPipeline
            : localStorage.getItem(legacyNuclearCellPairModeKey) === 'true';
        if (!selectionsInitializedBeforeLoad) {
            statsState.selectedPlugins.add('CENDot');
            statsState.selectedPlugins.add('Biorientation');
        }
        syncSignalSelectedPlugins();
        persistSignalQuantificationSettings();
        persistSelectedPlugins();
    }

    function loadStoredLengthUnits() {
        const legacyUnit = normalizeLengthUnit(localStorage.getItem(legacyLengthUnitKey));
        const storedWidthUnit = localStorage.getItem(punctaLineWidthUnitKey);
        const storedDistanceUnit = localStorage.getItem(cenDotDistanceUnitKey);
        const storedProximityRadiusUnit = localStorage.getItem(cenDotProximityRadiusUnitKey);
        const storedBiorientationMinUnit = localStorage.getItem(biorientationRedMinDistanceUnitKey);
        const storedBiorientationMaxUnit = localStorage.getItem(biorientationRedMaxDistanceUnitKey);
        statsState.punctaLineWidthUnit = normalizeLengthUnit(storedWidthUnit || legacyUnit);
        statsState.cenDotDistanceUnit = normalizeLengthUnit(storedDistanceUnit || legacyUnit);
        statsState.cenDotProximityRadiusUnit = normalizeLengthUnit(storedProximityRadiusUnit || legacyUnit);
        statsState.biorientationRedMinDistanceUnit = normalizeLengthUnit(storedBiorientationMinUnit || legacyUnit);
        statsState.biorientationRedMaxDistanceUnit = normalizeLengthUnit(storedBiorientationMaxUnit || legacyUnit);
    }

    function loadStoredMicronsPerPixel() {
        statsState.micronsPerPixel = sanitizeMicronsPerPixel(localStorage.getItem(micronsPerPixelKey));
    }

    function loadStoredUseMetadataScale() {
        const raw = localStorage.getItem(useMetadataScaleKey);
        if (raw === null) {
            statsState.useMetadataScale = true;
            return;
        }
        const normalized = String(raw).trim().toLowerCase();
        statsState.useMetadataScale = !['0', 'false', 'off', 'no'].includes(normalized);
    }

    function loadStoredChannelOrderSettings() {
        const rawMetadataMode = localStorage.getItem(useMetadataChannelOrderKey);
        if (rawMetadataMode === null) {
            statsState.useMetadataChannelOrder = true;
        } else {
            const normalized = String(rawMetadataMode).trim().toLowerCase();
            statsState.useMetadataChannelOrder = !['0', 'false', 'off', 'no'].includes(normalized);
        }
        try {
            statsState.fallbackChannelOrder = normalizeChannelOrder(
                JSON.parse(localStorage.getItem(fallbackChannelOrderKey) || '[]')
            );
        } catch (err) {
            statsState.fallbackChannelOrder = [...DEFAULT_FALLBACK_CHANNEL_ORDER];
        }
    }

    function loadStoredWidth() {
        const raw = localStorage.getItem(widthKey);
        const fallback = defaultWidthForUnit(statsState.punctaLineWidthUnit);
        const minimum = statsState.punctaLineWidthUnit === 'um' ? 0.01 : 1;
        statsState.punctaLineWidth = parseLengthValue(raw, statsState.punctaLineWidthUnit, fallback, minimum);
    }

    function loadStoredDistance() {
        const raw = localStorage.getItem(distanceKey);
        const fallback = defaultDistanceForUnit(statsState.cenDotDistanceUnit);
        statsState.cenDotDistance = parseLengthValue(raw, statsState.cenDotDistanceUnit, fallback, 0);
    }

    function loadStoredProximityRadius() {
        const raw = localStorage.getItem(proximityRadiusKey);
        const fallback = defaultProximityRadiusForUnit(statsState.cenDotProximityRadiusUnit);
        statsState.cenDotProximityRadius = parseLengthValue(raw, statsState.cenDotProximityRadiusUnit, fallback, 0);
    }

    function loadStoredBiorientationSettings() {
        const minRaw = localStorage.getItem(biorientationRedMinDistanceKey);
        const maxRaw = localStorage.getItem(biorientationRedMaxDistanceKey);
        statsState.biorientationRedMinDistance = parseLengthValue(
            minRaw,
            statsState.biorientationRedMinDistanceUnit,
            defaultBiorientationMinDistanceForUnit(),
            0
        );
        statsState.biorientationRedMaxDistance = parseLengthValue(
            maxRaw,
            statsState.biorientationRedMaxDistanceUnit,
            defaultBiorientationMaxDistanceForUnit(statsState.biorientationRedMaxDistanceUnit),
            0
        );
        const raw = localStorage.getItem(biorientationThresholdKey) || localStorage.getItem(oldThresholdKey);
        const parsed = parseInt(raw || '3', 10);
        statsState.biorientationCollinearityThreshold = Number.isFinite(parsed) && parsed >= 0 ? parsed : 3;
    }

    function loadStoredPunctaMode() {
        const raw = localStorage.getItem(punctaModeKey);
        statsState.punctaLineMode = raw === 'green_puncta' ? 'green_puncta' : 'red_puncta';
    }

    function loadStoredNuclearMode() {
        const raw = localStorage.getItem(nuclearModeKey);
        statsState.nuclearCellPairMode = raw === 'red_nucleus' ? 'red_nucleus' : 'green_nucleus';
    }

    function loadStoredNuclearContourMode() {
        statsState.nuclearCellPairContourMode = normalizeNuclearContourMode(
            localStorage.getItem(nuclearContourModeKey)
        );
    }

    function persistSelectedPlugins() {
        localStorage.setItem(selectionKey, JSON.stringify([...statsState.selectedPlugins]));
        localStorage.setItem(initializedKey, '1');
    }

    function persistAdvancedSettings() {
        localStorage.setItem(advancedKey, JSON.stringify({
            moduleEnabled: !!statsState.moduleEnabled,
            enforceLayerCount: !!statsState.enforceLayerCount,
            enforceAllWavelengths: !!statsState.enforceAllWavelengths,
            showLegacyPlugins: !!statsState.showLegacyPlugins,
            manualRequiredChannels: [...statsState.manualRequiredChannels],
            greenContourFilterEnabled: !!statsState.greenContourFilterEnabled,
            greenDotSplitEnabled: !!statsState.greenDotSplitEnabled,
            greenDotSplitMode: normalizeGreenDotSplitMode(statsState.greenDotSplitMode),
            redDotSplitEnabled: !!statsState.redDotSplitEnabled,
            redDotSplitMode: normalizeRedDotSplitMode(statsState.redDotSplitMode),
        }));
        localStorage.setItem(greenDotSplitKey, String(statsState.greenDotSplitEnabled));
        localStorage.setItem(greenDotSplitModeKey, normalizeGreenDotSplitMode(statsState.greenDotSplitMode));
        localStorage.setItem(redDotSplitKey, String(statsState.redDotSplitEnabled));
        localStorage.setItem(redDotSplitModeKey, normalizeRedDotSplitMode(statsState.redDotSplitMode));
    }

    function enforceExclusiveGroup(pluginId) {
        const plugin = pluginMap.get(pluginId);
        if (!plugin || !plugin.exclusive_group) return;
        statsPlugins.forEach((candidate) => {
            if (
                candidate.id !== pluginId &&
                candidate.exclusive_group &&
                candidate.exclusive_group === plugin.exclusive_group
            ) {
                statsState.selectedPlugins.delete(candidate.id);
            }
        });
    }

    function normalizeExclusiveSelections() {
        const normalized = new Set();
        const seenGroups = new Set();
        statsPlugins.forEach((plugin) => {
            if (!statsState.selectedPlugins.has(plugin.id)) return;
            if (plugin.exclusive_group && seenGroups.has(plugin.exclusive_group)) return;
            if (plugin.exclusive_group) {
                seenGroups.add(plugin.exclusive_group);
            }
            normalized.add(plugin.id);
        });
        statsState.selectedPlugins = normalized;
    }

    function isPluginRequiredBySelection(pluginId) {
        for (const selectedId of statsState.selectedPlugins) {
            if (selectedId === pluginId) continue;
            const selectedPlugin = pluginMap.get(selectedId);
            if (!selectedPlugin || !Array.isArray(selectedPlugin.required_plugins)) continue;
            if (selectedPlugin.required_plugins.includes(pluginId)) return true;
        }
        return false;
    }

    function applyPluginDependencies(pluginId) {
        const plugin = pluginMap.get(pluginId);
        if (!plugin || !Array.isArray(plugin.required_plugins)) return;
        plugin.required_plugins.forEach((dependencyId) => {
            if (!pluginMap.has(dependencyId)) return;
            statsState.selectedPlugins.add(dependencyId);
            applyPluginDependencies(dependencyId);
        });
    }

    function getStatsRequiredChannels() {
        const required = new Set(alwaysRequiredChannels);
        getEffectiveSelectedPlugins().forEach((pluginId) => {
            const plugin = pluginMap.get(pluginId);
            if (!plugin || !Array.isArray(plugin.required_channels)) return;
            plugin.required_channels.forEach((channel) => required.add(channel));
        });
        return required;
    }

    function isChannelUsed(channel) {
        var used = statsState.manualRequiredChannels.has(channel);
        getEffectiveSelectedPlugins().forEach((pluginId) => {
            const plugin = pluginMap.get(pluginId);
            if (!plugin || !Array.isArray(plugin.required_channels)) return false;
            plugin.required_channels.forEach((required_channel) => {
                if (required_channel === channel) used = true;
            });
        });
        return used;
    }

    function selectedStatsRequireChannel(channel) {
        for (const pluginId of getEffectiveSelectedPlugins()) {
            const plugin = pluginMap.get(pluginId);
            if (plugin && Array.isArray(plugin.required_channels) && plugin.required_channels.includes(channel)) {
                return true;
            }
        }
        return false;
    }

    function setOffVisualState(row, isOff) {
        if (!row) return;
        row.classList.toggle('is-off', !!isOff);
    }

    function syncStatsUI() {
        syncSignalSelectedPlugins();
        const statsRequired = getStatsRequiredChannels();
        const moduleToggle = document.getElementById('cytocvAnalysisEnabled');
        const layerToggle = document.getElementById('enforceLayerCount');
        const wavelengthToggle = document.getElementById('enforceWavelengths');
        const legacyToggle = document.getElementById('showLegacyPlugins');
        const legacyRow = document.getElementById('legacyPluginRow');
        const layerRow = document.getElementById('layerCheckRow');
        const wavelengthRow = document.getElementById('wavelengthCheckRow');
        const optionalChecksNote = document.getElementById('optionalChecksNote');
        const greenContourFilterEnabled = document.getElementById('greenContourFilterEnabled');
        const dotSplitEnabled = document.getElementById('dotSplitEnabled');
        const dotSplitTargetRow = document.getElementById('dotSplitTargetRow');
        const greenDotSplitModeRow = document.getElementById('greenDotSplitModeRow');
        const redDotSplitModeRow = document.getElementById('redDotSplitModeRow');
        const greenFilterRow = document.getElementById('greenFilterRow');
        const dotSplitRow = document.getElementById('dotSplitRow');
        const moduleRow = document.getElementById('moduleToggleRow');

        statToggleElements.forEach((toggle, pluginId) => {
            const row = toggle.closest('.stats-toggle-row');
            const paused = isPluginPausedBySignalMode(pluginId);
            toggle.checked = statsState.selectedPlugins.has(pluginId) && !paused;
            toggle.disabled = isPluginRequiredBySelection(pluginId) || paused;
            if (row) {
                row.classList.toggle('is-paused', paused);
                row.setAttribute('aria-disabled', paused ? 'true' : 'false');
            }
            setOffVisualState(row, !toggle.checked);
        });

        const signalEnabled = !!statsState.signalQuantificationEnabled;
        const signalMode = normalizeSignalMode(statsState.signalQuantificationMode);
        updateSignalQuantificationInfoDot();
        if (signalQuantificationToggle) {
            signalQuantificationToggle.checked = signalEnabled;
            setOffVisualState(signalQuantificationToggle.closest('.stats-toggle-row'), !signalEnabled);
        }
        if (signalQuantificationModeSelect) {
            signalQuantificationModeSelect.value = signalMode;
        }
        if (signalQuantificationModeRow) {
            signalQuantificationModeRow.classList.toggle('visible', signalEnabled);
        }
        syncSignalModeNotice(signalEnabled, signalMode);
        if (signalPunctaPanel) {
            signalPunctaPanel.classList.toggle('visible', signalEnabled && signalMode === 'puncta_distance');
        }
        if (signalNuclearPanel) {
            signalNuclearPanel.classList.toggle('visible', signalEnabled && signalMode === 'nuclear_cell_pair');
        }
        if (punctaContourIntensityToggle) {
            punctaContourIntensityToggle.checked = !!statsState.punctaContourIntensityEnabled;
        }
        if (alternateNucleusDetectionToggle) {
            alternateNucleusDetectionToggle.checked = !!statsState.alternateNucleusDetectionEnabled;
        }

        syncLengthControls();

        if (punctaLineWidthInput) {
            punctaLineWidthInput.value = formatNumericInputValue(statsState.punctaLineWidth);
        }
        if (punctaLineWidthRow) {
            punctaLineWidthRow.classList.toggle('visible', statsState.selectedPlugins.has('PunctaDistance'));
        }
        if (punctaLineModeSelect) {
            punctaLineModeSelect.value = statsState.punctaLineMode === 'green_puncta' ? 'green_puncta' : 'red_puncta';
        }
        if (punctaLineModeRow) {
            punctaLineModeRow.classList.toggle('visible', statsState.selectedPlugins.has('PunctaDistance'));
        }
        if (cenDotDistanceInput) {
            cenDotDistanceInput.value = formatNumericInputValue(statsState.cenDotDistance);
        }
        if (cenDotProximityRadiusInput) {
            cenDotProximityRadiusInput.value = formatNumericInputValue(statsState.cenDotProximityRadius);
        }
        if (cenDotDistanceRow) {
            cenDotDistanceRow.classList.toggle(
                'visible',
                statsState.selectedPlugins.has('CENDot') && !isPluginPausedBySignalMode('CENDot')
            );
        }
        if (biorientationRow) {
            biorientationRow.classList.toggle(
                'visible',
                statsState.selectedPlugins.has('Biorientation') && !isPluginPausedBySignalMode('Biorientation')
            );
        }
        if (biorientationRedMinDistanceInput) {
            biorientationRedMinDistanceInput.value = formatNumericInputValue(statsState.biorientationRedMinDistance);
        }
        if (biorientationRedMaxDistanceInput) {
            biorientationRedMaxDistanceInput.value = formatNumericInputValue(statsState.biorientationRedMaxDistance);
        }
        if (biorientationCollinearityThresholdInput) {
            biorientationCollinearityThresholdInput.value = String(statsState.biorientationCollinearityThreshold);
        }
        if (micronsPerPixelInput) {
            micronsPerPixelInput.value = formatNumericInputValue(statsState.micronsPerPixel, 4);
        }
        if (useMetadataScaleInput) {
            useMetadataScaleInput.checked = !!statsState.useMetadataScale;
        }
        if (useMetadataChannelOrderInput) {
            useMetadataChannelOrderInput.checked = !!statsState.useMetadataChannelOrder;
            useMetadataChannelOrderInput.closest('.measurement-scale-row')?.classList.toggle(
                'is-off',
                !useMetadataChannelOrderInput.checked
            );
        }
        if (fallbackChannelOrderBar) {
            orderFallbackChannelBar(statsState.fallbackChannelOrder);
            syncFallbackChannelOrderActions();
        }
        syncWavelengthChannelOrderStatus();
        updateMeasurementScaleHints();
        if (nuclearModeSelect) {
            nuclearModeSelect.value = statsState.nuclearCellPairMode === 'red_nucleus' ? 'red_nucleus' : 'green_nucleus';
        }
        if (nuclearModeRow) {
            nuclearModeRow.classList.toggle('visible', statsState.selectedPlugins.has('NuclearCellPairIntensity'));
        }
        if (nuclearContourModeSelect) {
            nuclearContourModeSelect.value = normalizeNuclearContourMode(statsState.nuclearCellPairContourMode);
            nuclearContourModeSelect.setDisabled(!statsState.alternateNucleusDetectionEnabled);
        }
        if (nuclearContourModeRow) {
            nuclearContourModeRow.classList.toggle('visible', statsState.selectedPlugins.has('NuclearCellPairIntensity'));
            nuclearContourModeRow.classList.toggle('disabled', !statsState.alternateNucleusDetectionEnabled);
        }
        if (legacyNuclearCellPairToggle) {
            legacyNuclearCellPairToggle.checked = !!statsState.useLegacyNuclearCellPairPipeline;
        }
        if (legacyNuclearCellPairRow) {
            legacyNuclearCellPairRow.classList.toggle('visible', statsState.selectedPlugins.has('NuclearCellPairIntensity'));
        }
        if (greenContourFilterEnabled) {
            greenContourFilterEnabled.checked = !!statsState.greenContourFilterEnabled;
            const greenUsed = isChannelUsed('channel_green');
            greenContourFilterEnabled.disabled = !greenUsed;
            if (greenUsed) {
                greenFilterRow.classList.remove('disabled');
            } else {
                greenFilterRow.classList.add('disabled');
                greenContourFilterEnabled.checked = false;
                statsState.greenContourFilterEnabled = greenContourFilterEnabled.checked;
            }
            setOffVisualState(greenFilterRow, !greenContourFilterEnabled.checked);
        }
        const greenDotSplitAllowed = selectedStatsRequireChannel('channel_green');
        const redDotSplitAllowed = selectedStatsRequireChannel('channel_red');
        let dotSplitTarget = fallbackDotSplitTarget(
            dotSplitTargetSelect
                ? dotSplitTargetSelect.value
                : dotSplitTargetFromFlags(statsState.greenDotSplitEnabled, statsState.redDotSplitEnabled),
            greenDotSplitAllowed,
            redDotSplitAllowed
        );
        let dotSplitActive = !!(statsState.greenDotSplitEnabled || statsState.redDotSplitEnabled);
        if (!dotSplitTarget) dotSplitActive = false;
        dotSplitTarget = applyDotSplitTargetToState(dotSplitTarget, dotSplitActive);
        dotSplitActive = !!(statsState.greenDotSplitEnabled || statsState.redDotSplitEnabled);
        if (dotSplitEnabled) {
            dotSplitEnabled.disabled = !dotSplitTarget;
            dotSplitEnabled.checked = dotSplitActive;
        }
        if (dotSplitTargetSelect) {
            const disabledTargets = [];
            if (!dotSplitTargetAllowed('both', greenDotSplitAllowed, redDotSplitAllowed)) disabledTargets.push('both');
            if (!dotSplitTargetAllowed('green', greenDotSplitAllowed, redDotSplitAllowed)) disabledTargets.push('green');
            if (!dotSplitTargetAllowed('red', greenDotSplitAllowed, redDotSplitAllowed)) disabledTargets.push('red');
            dotSplitTargetSelect.setDisabledValues(disabledTargets);
            dotSplitTargetSelect.setDisabled(!dotSplitActive || !dotSplitTarget);
            if (dotSplitTarget) dotSplitTargetSelect.value = dotSplitTarget;
        }
        if (dotSplitRow) {
            dotSplitRow.classList.toggle('disabled', !dotSplitTarget);
            setOffVisualState(dotSplitRow, !dotSplitActive);
        }
        if (dotSplitTargetRow) {
            dotSplitTargetRow.classList.toggle('visible', dotSplitActive && !!dotSplitTarget);
        }
        if (greenDotSplitModeSelect) {
            greenDotSplitModeSelect.value = normalizeGreenDotSplitMode(statsState.greenDotSplitMode);
            greenDotSplitModeSelect.setDisabled(!statsState.greenDotSplitEnabled);
        }
        if (greenDotSplitModeRow) {
            greenDotSplitModeRow.classList.toggle('visible', dotSplitActive && !!dotSplitTarget);
            greenDotSplitModeRow.classList.toggle('disabled', !statsState.greenDotSplitEnabled);
        }
        if (redDotSplitModeSelect) {
            redDotSplitModeSelect.value = normalizeRedDotSplitMode(statsState.redDotSplitMode);
            redDotSplitModeSelect.setDisabled(!statsState.redDotSplitEnabled);
        }
        if (redDotSplitModeRow) {
            redDotSplitModeRow.classList.toggle('visible', dotSplitActive && !!dotSplitTarget);
            redDotSplitModeRow.classList.toggle('disabled', !statsState.redDotSplitEnabled);
        }
        if (moduleToggle) moduleToggle.checked = !!statsState.moduleEnabled;
        if (layerToggle) layerToggle.checked = !!statsState.enforceLayerCount;
        if (wavelengthToggle) wavelengthToggle.checked = !!statsState.enforceAllWavelengths;
        if (legacyToggle) legacyToggle.checked = !!statsState.showLegacyPlugins;
        if (legacyRow) legacyRow.classList.remove('disabled');
        if (legacyToggle) legacyToggle.disabled = false;
        setOffVisualState(moduleRow, moduleToggle ? !moduleToggle.checked : false);
        setOffVisualState(legacyRow, legacyToggle ? !legacyToggle.checked : false);
        if (optionalChecksNote) {
            const nextState = statsState.moduleEnabled ? 'on' : 'off';
            const nextText = statsState.moduleEnabled
                ? 'Optional checks below are ON. Required checks from selected statistics are still enforced.'
                : 'Optional checks below are OFF. Saved optional selections are paused; required checks from selected statistics are still enforced.';
            if (statsState.moduleEnabled) {
                optionalChecksNote.classList.remove('off');
                optionalChecksNote.classList.add('on');
            } else {
                optionalChecksNote.classList.remove('on');
                optionalChecksNote.classList.add('off');
            }
            optionalChecksNote.dataset.state = nextState;
            setSlideInText(optionalChecksNote, nextText);
        }

        if (layerToggle && layerRow) {
            layerToggle.disabled = !statsState.moduleEnabled;
            layerRow.classList.toggle('disabled', !statsState.moduleEnabled);
            layerRow.classList.remove('locked');
            setOffVisualState(layerRow, !layerToggle.checked);
        }

        const allChannelsRequiredByStats = channelOrder.every((channel) => statsRequired.has(channel));
        if (wavelengthToggle && wavelengthRow) {
            if (allChannelsRequiredByStats) {
                statsState.enforceAllWavelengths = true;
                wavelengthToggle.checked = true;
            }
            wavelengthToggle.disabled = allChannelsRequiredByStats || !statsState.moduleEnabled;
            wavelengthRow.classList.toggle('disabled', !statsState.moduleEnabled && !allChannelsRequiredByStats);
            wavelengthRow.classList.toggle('locked', allChannelsRequiredByStats);
            setOffVisualState(wavelengthRow, !wavelengthToggle.checked);
        }

        channelOrder.forEach((channel) => {
            const toggle = channelToggleElements.get(channel);
            const row = channelRowElements.get(channel);
            const info = row ? row.querySelector('.info-dot') : null;
            if (!toggle || !row) return;

            const requiredByStats = statsRequired.has(channel);
            const requiredByAllToggle = statsState.moduleEnabled && statsState.enforceAllWavelengths;
            let statusText = statsState.moduleEnabled
                ? 'optional; enable this toggle to require it manually.'
                : 'optional checks are off, so manual channel requirements are paused.';

            if (requiredByStats) {
                toggle.checked = true;
                toggle.disabled = true;
                statsState.manualRequiredChannels.delete(channel);
                row.classList.add('locked');
                row.classList.remove('disabled');
                const requiringStats = selectedPluginLabelsRequiringChannel(channel);
                statusText = alwaysRequiredChannels.has(channel)
                    ? 'always required for segmentation/CNN.'
                    : `required by selected statistic(s)${requiringStats.length ? `: ${joinLabels(requiringStats)}.` : '.'}`;
            } else if (requiredByAllToggle) {
                toggle.checked = true;
                toggle.disabled = true;
                row.classList.remove('locked');
                row.classList.add('disabled');
                statusText = 'required because "Require All Channels" is enabled.';
            } else {
                toggle.checked = statsState.manualRequiredChannels.has(channel);
                toggle.disabled = !statsState.moduleEnabled;
                row.classList.toggle('disabled', !statsState.moduleEnabled);
                row.classList.remove('locked');
                if (toggle.checked) {
                    statusText = 'manual requirement is enabled.';
                }
            }
            setOffVisualState(row, !toggle.checked);

            if (info) {
                const infoText = buildAdvancedChannelInfo(channel, statusText);
                const normalizedInfoText = normalizeInfoText(infoText);
                info.dataset.infoText = normalizedInfoText;
                info.setAttribute('aria-label', normalizedInfoText || 'Information');
                if (activeInfoAnchor === info && infoTooltipElement && !infoTooltipElement.hidden) {
                    showInfoTooltip(info);
                }
            }

            const requiredCell = document.querySelector(`.required-channel-row[data-channel="${channel}"]`);
            const stateEl = document.querySelector(`.required-channel-state[data-state-for="${channel}"]`);
            const requiredForValidation = requiredByStats || (statsState.moduleEnabled && (requiredByAllToggle || statsState.manualRequiredChannels.has(channel)));
            if (requiredCell) {
                requiredCell.classList.toggle('required', requiredForValidation);
            }
            if (stateEl) {
                if (alwaysRequiredChannels.has(channel)) {
                    stateEl.textContent = 'Always required';
                } else if (requiredByStats) {
                    stateEl.textContent = 'Required by stats';
                } else if (statsState.moduleEnabled && requiredByAllToggle) {
                    stateEl.textContent = 'Required by all-channels';
                } else if (statsState.moduleEnabled && statsState.manualRequiredChannels.has(channel)) {
                    stateEl.textContent = 'Required (advanced)';
                } else {
                    stateEl.textContent = 'Optional';
                }
            }
        });
    }

    function commitStatsStateFromInputs() {
        persistSelectedPlugins();
        persistAdvancedSettings();
        persistLengthUnitSettings();

        if (micronsPerPixelInput) {
            statsState.micronsPerPixel = sanitizeMicronsPerPixel(micronsPerPixelInput.value);
            micronsPerPixelInput.value = formatNumericInputValue(statsState.micronsPerPixel);
            localStorage.setItem(micronsPerPixelKey, String(statsState.micronsPerPixel));
        }
        if (useMetadataScaleInput) {
            statsState.useMetadataScale = !!useMetadataScaleInput.checked;
            localStorage.setItem(useMetadataScaleKey, String(statsState.useMetadataScale));
        }
        if (useMetadataChannelOrderInput) {
            statsState.useMetadataChannelOrder = !!useMetadataChannelOrderInput.checked;
        }
        statsState.fallbackChannelOrder = channelOrderFromBar(fallbackChannelOrderBar);
        persistChannelOrderSettings();
        if (punctaLineWidthInput) {
            const fallback = defaultWidthForUnit(statsState.punctaLineWidthUnit);
            const minimum = statsState.punctaLineWidthUnit === 'um' ? 0.01 : 1;
            statsState.punctaLineWidth = parseLengthValue(
                punctaLineWidthInput.value,
                statsState.punctaLineWidthUnit,
                fallback,
                minimum
            );
            punctaLineWidthInput.value = formatNumericInputValue(statsState.punctaLineWidth);
            localStorage.setItem(widthKey, String(statsState.punctaLineWidth));
        }
        if (cenDotDistanceInput) {
            const fallback = defaultDistanceForUnit(statsState.cenDotDistanceUnit);
            statsState.cenDotDistance = parseLengthValue(
                cenDotDistanceInput.value,
                statsState.cenDotDistanceUnit,
                fallback,
                0
            );
            cenDotDistanceInput.value = formatNumericInputValue(statsState.cenDotDistance);
            localStorage.setItem(distanceKey, String(statsState.cenDotDistance));
        }
        if (cenDotProximityRadiusInput) {
            const fallback = defaultProximityRadiusForUnit(statsState.cenDotProximityRadiusUnit);
            statsState.cenDotProximityRadius = parseLengthValue(
                cenDotProximityRadiusInput.value,
                statsState.cenDotProximityRadiusUnit,
                fallback,
                0
            );
            cenDotProximityRadiusInput.value = formatNumericInputValue(statsState.cenDotProximityRadius);
            localStorage.setItem(proximityRadiusKey, String(statsState.cenDotProximityRadius));
        }
        if (biorientationRedMinDistanceInput) {
            statsState.biorientationRedMinDistance = parseLengthValue(
                biorientationRedMinDistanceInput.value,
                statsState.biorientationRedMinDistanceUnit,
                defaultBiorientationMinDistanceForUnit(),
                0
            );
            biorientationRedMinDistanceInput.value = formatNumericInputValue(statsState.biorientationRedMinDistance);
            localStorage.setItem(biorientationRedMinDistanceKey, String(statsState.biorientationRedMinDistance));
        }
        if (biorientationRedMaxDistanceInput) {
            statsState.biorientationRedMaxDistance = parseLengthValue(
                biorientationRedMaxDistanceInput.value,
                statsState.biorientationRedMaxDistanceUnit,
                defaultBiorientationMaxDistanceForUnit(statsState.biorientationRedMaxDistanceUnit),
                0
            );
            biorientationRedMaxDistanceInput.value = formatNumericInputValue(statsState.biorientationRedMaxDistance);
            localStorage.setItem(biorientationRedMaxDistanceKey, String(statsState.biorientationRedMaxDistance));
        }
        if (biorientationCollinearityThresholdInput) {
            const parsed = parseInt(biorientationCollinearityThresholdInput.value, 10);
            statsState.biorientationCollinearityThreshold = Number.isFinite(parsed) && parsed >= 0 ? parsed : 3;
            biorientationCollinearityThresholdInput.value = String(statsState.biorientationCollinearityThreshold);
            localStorage.setItem(
                biorientationThresholdKey,
                String(statsState.biorientationCollinearityThreshold)
            );
        }
        if (punctaLineModeSelect) {
            statsState.punctaLineMode = punctaLineModeSelect.value === 'green_puncta'
                ? 'green_puncta'
                : 'red_puncta';
            localStorage.setItem(punctaModeKey, statsState.punctaLineMode);
        }
        if (signalQuantificationToggle) {
            statsState.signalQuantificationEnabled = !!signalQuantificationToggle.checked;
        }
        if (signalQuantificationModeSelect) {
            statsState.signalQuantificationMode = normalizeSignalMode(signalQuantificationModeSelect.value);
        }
        if (punctaContourIntensityToggle) {
            statsState.punctaContourIntensityEnabled = !!punctaContourIntensityToggle.checked;
        }
        if (alternateNucleusDetectionToggle) {
            statsState.alternateNucleusDetectionEnabled = !!alternateNucleusDetectionToggle.checked;
        }
        syncSignalSelectedPlugins();
        persistSignalQuantificationSettings();
        if (nuclearModeSelect) {
            statsState.nuclearCellPairMode = nuclearModeSelect.value === 'red_nucleus'
                ? 'red_nucleus'
                : 'green_nucleus';
            localStorage.setItem(nuclearModeKey, statsState.nuclearCellPairMode);
        }
        if (nuclearContourModeSelect) {
            statsState.nuclearCellPairContourMode = normalizeNuclearContourMode(nuclearContourModeSelect.value);
            localStorage.setItem(nuclearContourModeKey, statsState.nuclearCellPairContourMode);
        }
        if (legacyNuclearCellPairToggle) {
            statsState.useLegacyNuclearCellPairPipeline = !!legacyNuclearCellPairToggle.checked;
            localStorage.setItem(legacyNuclearCellPairModeKey, String(statsState.useLegacyNuclearCellPairPipeline));
        }

        const usingMicrometers = statsState.punctaLineWidthUnit === 'um'
            || statsState.cenDotDistanceUnit === 'um'
            || statsState.cenDotProximityRadiusUnit === 'um'
            || statsState.biorientationRedMinDistanceUnit === 'um'
            || statsState.biorientationRedMaxDistanceUnit === 'um';
        if (usingMicrometers && !(Number.isFinite(statsState.micronsPerPixel) && statsState.micronsPerPixel > 0)) {
            return {
                ok: false,
                errors: ['Micrometers-per-pixel must be greater than 0 when using micrometer input.'],
            };
        }

        return { ok: true };
    }

    function setupSettingsModal() {
        const settingsButton = document.getElementById('settingsButton');
        const backdrop = document.getElementById('settingsBackdrop');
        const closeButton = document.getElementById('settingsClose');
        const openAdvanced = document.getElementById('openAdvancedSettings');
        const backButton = document.getElementById('advancedBackButton');
        const saveDefaultButtons = Array.from(document.querySelectorAll('[data-save-workflow-default]'));
        const primaryView = document.getElementById('statsPrimaryView');
        const advancedView = document.getElementById('statsAdvancedView');
        const modalPanel = backdrop ? backdrop.querySelector('.settings-modal') : null;
        const unsavedBackdrop = document.getElementById('statsUnsavedBackdrop');
        const keepOldButton = document.getElementById('statsUnsavedKeepOld');
        const keepNewButton = document.getElementById('statsUnsavedKeepNew');
        const unsavedPanel = unsavedBackdrop ? unsavedBackdrop.querySelector('.nav-exit-modal') : null;
        const saveDefaultsBackdrop = document.getElementById('saveWorkflowDefaultsBackdrop');
        const saveDefaultsCancelButton = document.getElementById('saveWorkflowDefaultsCancel');
        const saveDefaultsConfirmButton = document.getElementById('saveWorkflowDefaultsConfirm');
        const saveDefaultsPanel = saveDefaultsBackdrop ? saveDefaultsBackdrop.querySelector('.nav-exit-modal') : null;

        if (!settingsButton || !backdrop || !closeButton || !primaryView || !advancedView) {
            return;
        }

        const ENTER_MS = 150;
        const EXIT_MS = 120;
        const MODAL_ENTER_MS = 170;
        const MODAL_EXIT_MS = 120;
        const prefersReducedMotion = !!(
            window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
        );
        const viewAnimClasses = [
            'anim-enter-forward',
            'anim-enter-backward',
            'anim-exit-forward',
            'anim-exit-backward',
        ];
        let viewSwitchTimer = null;
        let modalEnterTimer = null;
        let modalCloseTimer = null;
        let modalOpenSnapshot = null;

        const captureStatsSnapshot = () => ({
            selectedPlugins: [...statsState.selectedPlugins].sort(),
            signalQuantificationEnabled: !!statsState.signalQuantificationEnabled,
            signalQuantificationMode: normalizeSignalMode(statsState.signalQuantificationMode),
            punctaContourIntensityEnabled: !!statsState.punctaContourIntensityEnabled,
            alternateNucleusDetectionEnabled: !!statsState.alternateNucleusDetectionEnabled,
            moduleEnabled: !!statsState.moduleEnabled,
            enforceLayerCount: !!statsState.enforceLayerCount,
            enforceAllWavelengths: !!statsState.enforceAllWavelengths,
            showLegacyPlugins: !!statsState.showLegacyPlugins,
            manualRequiredChannels: [...statsState.manualRequiredChannels].sort(),
            punctaLineWidth: Number.isFinite(Number(statsState.punctaLineWidth)) ? Number(statsState.punctaLineWidth) : 1,
            cenDotDistance: Number.isFinite(Number(statsState.cenDotDistance)) ? Number(statsState.cenDotDistance) : 37,
            cenDotProximityRadius: Number.isFinite(Number(statsState.cenDotProximityRadius)) ? Number(statsState.cenDotProximityRadius) : 13,
            biorientationRedMinDistance: Number.isFinite(Number(statsState.biorientationRedMinDistance)) ? Number(statsState.biorientationRedMinDistance) : 0,
            biorientationRedMaxDistance: Number.isFinite(Number(statsState.biorientationRedMaxDistance)) ? Number(statsState.biorientationRedMaxDistance) : 37,
            biorientationCollinearityThreshold: Number.isFinite(Number(statsState.biorientationCollinearityThreshold)) ? Number(statsState.biorientationCollinearityThreshold) : 3,
            punctaLineMode: statsState.punctaLineMode === 'green_puncta' ? 'green_puncta' : 'red_puncta',
            nuclearCellPairMode: statsState.nuclearCellPairMode === 'red_nucleus' ? 'red_nucleus' : 'green_nucleus',
            nuclearCellPairContourMode: normalizeNuclearContourMode(statsState.nuclearCellPairContourMode),
            useLegacyNuclearCellPairPipeline: !!statsState.useLegacyNuclearCellPairPipeline,
            greenContourFilterEnabled: !!statsState.greenContourFilterEnabled,
            greenDotSplitEnabled: !!statsState.greenDotSplitEnabled,
            greenDotSplitMode: normalizeGreenDotSplitMode(statsState.greenDotSplitMode),
            redDotSplitEnabled: !!statsState.redDotSplitEnabled,
            redDotSplitMode: normalizeRedDotSplitMode(statsState.redDotSplitMode),
            punctaLineWidthUnit: normalizeLengthUnit(statsState.punctaLineWidthUnit),
            cenDotDistanceUnit: normalizeLengthUnit(statsState.cenDotDistanceUnit),
            cenDotProximityRadiusUnit: normalizeLengthUnit(statsState.cenDotProximityRadiusUnit),
            biorientationRedMinDistanceUnit: normalizeLengthUnit(statsState.biorientationRedMinDistanceUnit),
            biorientationRedMaxDistanceUnit: normalizeLengthUnit(statsState.biorientationRedMaxDistanceUnit),
            micronsPerPixel: sanitizeMicronsPerPixel(statsState.micronsPerPixel),
            useMetadataScale: !!statsState.useMetadataScale,
            useMetadataChannelOrder: !!statsState.useMetadataChannelOrder,
            fallbackChannelOrder: normalizeChannelOrder(statsState.fallbackChannelOrder),
        });
        const snapshotToKey = (snapshot) => JSON.stringify(snapshot || {});
        const hasModalChanges = () => {
            if (!modalOpenSnapshot) return false;
            return snapshotToKey(captureStatsSnapshot()) !== snapshotToKey(modalOpenSnapshot);
        };
        const restoreStatsSnapshot = (snapshot) => {
            if (!snapshot) return;
            statsState.selectedPlugins = new Set(
                Array.isArray(snapshot.selectedPlugins)
                    ? snapshot.selectedPlugins.filter((pluginId) => pluginMap.has(pluginId))
                    : []
            );
            [...statsState.selectedPlugins].forEach((pluginId) => applyPluginDependencies(pluginId));
            normalizeExclusiveSelections();
            statsState.moduleEnabled = !!snapshot.moduleEnabled;
            statsState.enforceLayerCount = !!snapshot.enforceLayerCount;
            statsState.enforceAllWavelengths = !!snapshot.enforceAllWavelengths;
            statsState.showLegacyPlugins = !!snapshot.showLegacyPlugins;
            statsState.manualRequiredChannels = new Set(
                Array.isArray(snapshot.manualRequiredChannels)
                    ? snapshot.manualRequiredChannels.filter((channel) => channelOrder.includes(channel))
                    : []
            );
            statsState.punctaLineWidthUnit = normalizeLengthUnit(snapshot.punctaLineWidthUnit);
            statsState.cenDotDistanceUnit = normalizeLengthUnit(snapshot.cenDotDistanceUnit);
            statsState.cenDotProximityRadiusUnit = normalizeLengthUnit(snapshot.cenDotProximityRadiusUnit);
            statsState.biorientationRedMinDistanceUnit = normalizeLengthUnit(snapshot.biorientationRedMinDistanceUnit);
            statsState.biorientationRedMaxDistanceUnit = normalizeLengthUnit(snapshot.biorientationRedMaxDistanceUnit);
            statsState.micronsPerPixel = sanitizeMicronsPerPixel(snapshot.micronsPerPixel);
            statsState.useMetadataScale = !!snapshot.useMetadataScale;
            statsState.useMetadataChannelOrder = snapshot.useMetadataChannelOrder !== false;
            statsState.fallbackChannelOrder = normalizeChannelOrder(snapshot.fallbackChannelOrder);
            const widthMinimum = statsState.punctaLineWidthUnit === 'um' ? 0.01 : 1;
            const widthFallback = defaultWidthForUnit(statsState.punctaLineWidthUnit);
            statsState.punctaLineWidth = parseLengthValue(snapshot.punctaLineWidth, statsState.punctaLineWidthUnit, widthFallback, widthMinimum);
            const distanceFallback = defaultDistanceForUnit(statsState.cenDotDistanceUnit);
            statsState.cenDotDistance = parseLengthValue(snapshot.cenDotDistance, statsState.cenDotDistanceUnit, distanceFallback, 0);
            const proximityRadiusFallback = defaultProximityRadiusForUnit(statsState.cenDotProximityRadiusUnit);
            statsState.cenDotProximityRadius = parseLengthValue(snapshot.cenDotProximityRadius, statsState.cenDotProximityRadiusUnit, proximityRadiusFallback, 0);
            statsState.biorientationRedMinDistance = parseLengthValue(
                snapshot.biorientationRedMinDistance,
                statsState.biorientationRedMinDistanceUnit,
                defaultBiorientationMinDistanceForUnit(),
                0
            );
            statsState.biorientationRedMaxDistance = parseLengthValue(
                snapshot.biorientationRedMaxDistance,
                statsState.biorientationRedMaxDistanceUnit,
                defaultBiorientationMaxDistanceForUnit(statsState.biorientationRedMaxDistanceUnit),
                0
            );
            const parsedThreshold = parseInt(String(snapshot.biorientationCollinearityThreshold ?? 3), 10);
            statsState.biorientationCollinearityThreshold = Number.isFinite(parsedThreshold) && parsedThreshold >= 0 ? parsedThreshold : 3;
            statsState.punctaLineMode = snapshot.punctaLineMode === 'green_puncta' ? 'green_puncta' : 'red_puncta';
            statsState.nuclearCellPairMode = snapshot.nuclearCellPairMode === 'red_nucleus' ? 'red_nucleus' : 'green_nucleus';
            statsState.nuclearCellPairContourMode = normalizeNuclearContourMode(snapshot.nuclearCellPairContourMode);
            statsState.useLegacyNuclearCellPairPipeline = !!snapshot.useLegacyNuclearCellPairPipeline;
            statsState.signalQuantificationEnabled = snapshot.signalQuantificationEnabled !== false;
            statsState.signalQuantificationMode = normalizeSignalMode(snapshot.signalQuantificationMode);
            statsState.punctaContourIntensityEnabled = snapshot.punctaContourIntensityEnabled !== false;
        statsState.alternateNucleusDetectionEnabled = !!(
            snapshot.alternateNucleusDetectionEnabled || snapshot.alternateRedDetection
        );
        statsState.greenContourFilterEnabled = !!snapshot.greenContourFilterEnabled;
        statsState.greenDotSplitEnabled = snapshot.greenDotSplitEnabled !== false;
        statsState.greenDotSplitMode = normalizeGreenDotSplitMode(snapshot.greenDotSplitMode);
        statsState.redDotSplitEnabled = snapshot.redDotSplitEnabled !== false;
        statsState.redDotSplitMode = normalizeRedDotSplitMode(snapshot.redDotSplitMode);
        syncSignalSelectedPlugins();
            if (!statsState.showLegacyPlugins) {
                statsPlugins.forEach((plugin) => {
                    if (plugin.is_legacy) {
                        statsState.selectedPlugins.delete(plugin.id);
                    }
                });
            }
            renderStatsToggles();
            persistSelectedPlugins();
            persistAdvancedSettings();
            localStorage.setItem(widthKey, String(statsState.punctaLineWidth));
            localStorage.setItem(distanceKey, String(statsState.cenDotDistance));
            localStorage.setItem(proximityRadiusKey, String(statsState.cenDotProximityRadius));
            localStorage.setItem(biorientationRedMinDistanceKey, String(statsState.biorientationRedMinDistance));
            localStorage.setItem(biorientationRedMaxDistanceKey, String(statsState.biorientationRedMaxDistance));
            localStorage.setItem(biorientationThresholdKey, String(statsState.biorientationCollinearityThreshold));
            localStorage.setItem(greenDotSplitKey, String(statsState.greenDotSplitEnabled));
            localStorage.setItem(greenDotSplitModeKey, normalizeGreenDotSplitMode(statsState.greenDotSplitMode));
            localStorage.setItem(redDotSplitKey, String(statsState.redDotSplitEnabled));
            localStorage.setItem(redDotSplitModeKey, normalizeRedDotSplitMode(statsState.redDotSplitMode));
            localStorage.setItem(punctaModeKey, statsState.punctaLineMode);
            localStorage.setItem(nuclearModeKey, statsState.nuclearCellPairMode);
            localStorage.setItem(nuclearContourModeKey, statsState.nuclearCellPairContourMode);
            localStorage.setItem(legacyNuclearCellPairModeKey, String(statsState.useLegacyNuclearCellPairPipeline));
            persistSignalQuantificationSettings();
            persistLengthUnitSettings();
            persistChannelOrderSettings();
            syncStatsUI();
        };

        const clearViewAnim = (view) => {
            if (!view) return;
            viewAnimClasses.forEach((cls) => view.classList.remove(cls));
        };
        const clearAllViewAnim = () => {
            clearViewAnim(primaryView);
            clearViewAnim(advancedView);
        };
        const clearSwitchTimer = () => {
            if (viewSwitchTimer !== null) {
                window.clearTimeout(viewSwitchTimer);
                viewSwitchTimer = null;
            }
        };
        const clearModalTimer = () => {
            if (modalEnterTimer !== null) {
                window.clearTimeout(modalEnterTimer);
                modalEnterTimer = null;
            }
            if (modalCloseTimer !== null) {
                window.clearTimeout(modalCloseTimer);
                modalCloseTimer = null;
            }
        };
        const clearModalAnim = () => {
            backdrop.classList.remove('modal-enter', 'modal-exit');
            if (modalPanel) {
                modalPanel.classList.remove('modal-enter', 'modal-exit');
            }
        };
        const promptUnsavedStatsDecision = () => {
            if (!unsavedBackdrop || !keepOldButton || !keepNewButton) {
                return Promise.resolve(true);
            }
            openPopupModal(unsavedBackdrop, unsavedPanel);

            return new Promise((resolve) => {
                let settled = false;
                const closePrompt = (decision) => {
                    if (settled) return;
                    settled = true;
                    cleanup();
                    closePopupModal(unsavedBackdrop, unsavedPanel, () => resolve(decision));
                };
                const onKeepOld = () => closePrompt(false);
                const onKeepNew = () => closePrompt(true);
                const onBackdrop = (event) => {
                    if (event.target === unsavedBackdrop) {
                        closePrompt(null);
                    }
                };
                const onKeydown = (event) => {
                    if (event.key === 'Escape') {
                        closePrompt(null);
                    }
                };
                const cleanup = () => {
                    keepOldButton.removeEventListener('click', onKeepOld);
                    keepNewButton.removeEventListener('click', onKeepNew);
                    unsavedBackdrop.removeEventListener('click', onBackdrop);
                    document.removeEventListener('keydown', onKeydown);
                };

                keepOldButton.addEventListener('click', onKeepOld);
                keepNewButton.addEventListener('click', onKeepNew);
                unsavedBackdrop.addEventListener('click', onBackdrop);
                document.addEventListener('keydown', onKeydown);
            });
        };
        saveDefaultButtons.forEach((button) => {
            if (!button.dataset.defaultLabel) {
                button.dataset.defaultLabel = button.textContent.trim() || 'Save as Workflow Default';
            }
        });

        const setWorkflowDefaultButtonsPending = (pending) => {
            saveDefaultButtons.forEach((button) => {
                button.disabled = pending;
                button.textContent = pending
                    ? 'Saving...'
                    : (button.dataset.defaultLabel || 'Save as Workflow Default');
            });
        };

        const showWorkflowDefaultError = (message) => {
            if (window.showGlobalMessage) {
                window.showGlobalMessage(
                    message || "We couldn't save that workflow setting. Try again.",
                    'error'
                );
                return;
            }
            showErrors([message || "We couldn't save that workflow setting. Try again."]);
        };

        const promptWorkflowDefaultConfirmation = () => {
            if (
                !saveDefaultsBackdrop
                || !saveDefaultsCancelButton
                || !saveDefaultsConfirmButton
            ) {
                return Promise.resolve(true);
            }
            openPopupModal(saveDefaultsBackdrop, saveDefaultsPanel);

            return new Promise((resolve) => {
                let settled = false;
                const closePrompt = (decision) => {
                    if (settled) return;
                    settled = true;
                    cleanup();
                    closePopupModal(saveDefaultsBackdrop, saveDefaultsPanel, () => resolve(decision));
                };
                const onCancel = () => closePrompt(false);
                const onConfirm = () => closePrompt(true);
                const onBackdrop = (event) => {
                    if (event.target === saveDefaultsBackdrop) {
                        closePrompt(false);
                    }
                };
                const onKeydown = (event) => {
                    if (event.key === 'Escape') {
                        closePrompt(false);
                    }
                };
                const cleanup = () => {
                    saveDefaultsCancelButton.removeEventListener('click', onCancel);
                    saveDefaultsConfirmButton.removeEventListener('click', onConfirm);
                    saveDefaultsBackdrop.removeEventListener('click', onBackdrop);
                    document.removeEventListener('keydown', onKeydown);
                };

                saveDefaultsCancelButton.addEventListener('click', onCancel);
                saveDefaultsConfirmButton.addEventListener('click', onConfirm);
                saveDefaultsBackdrop.addEventListener('click', onBackdrop);
                document.addEventListener('keydown', onKeydown);
            });
        };

        const buildWorkflowDefaultPayload = () => {
            const snapshot = captureStatsSnapshot();
            return {
                selected_plugins: snapshot.selectedPlugins,
                signal_quantification_enabled: snapshot.signalQuantificationEnabled,
                signal_quantification_mode: snapshot.signalQuantificationMode,
                puncta_contour_intensity_enabled: snapshot.punctaContourIntensityEnabled,
                alternate_nucleus_detection_enabled: snapshot.alternateNucleusDetectionEnabled,
                module_enabled: snapshot.moduleEnabled,
                enforce_layer_count: snapshot.enforceLayerCount,
                enforce_wavelengths: snapshot.enforceAllWavelengths,
                show_legacy_plugins: snapshot.showLegacyPlugins,
                manual_required_channels: snapshot.manualRequiredChannels,
                green_contour_filter_enabled: snapshot.greenContourFilterEnabled,
                green_dot_split_enabled: snapshot.greenDotSplitEnabled,
                green_dot_split_mode: snapshot.greenDotSplitMode,
                red_dot_split_enabled: snapshot.redDotSplitEnabled,
                red_dot_split_mode: snapshot.redDotSplitMode,
                alternate_red_detection: snapshot.alternateNucleusDetectionEnabled,
                puncta_line_width: snapshot.punctaLineWidth,
                puncta_line_width_unit: snapshot.punctaLineWidthUnit,
                cen_dot_distance: snapshot.cenDotDistance,
                cen_dot_distance_unit: snapshot.cenDotDistanceUnit,
                cen_dot_proximity_radius: snapshot.cenDotProximityRadius,
                cen_dot_proximity_radius_unit: snapshot.cenDotProximityRadiusUnit,
                biorientation_red_min_distance: snapshot.biorientationRedMinDistance,
                biorientation_red_min_distance_unit: snapshot.biorientationRedMinDistanceUnit,
                biorientation_red_max_distance: snapshot.biorientationRedMaxDistance,
                biorientation_red_max_distance_unit: snapshot.biorientationRedMaxDistanceUnit,
                biorientation_collinearity_threshold: snapshot.biorientationCollinearityThreshold,
                puncta_line_mode: snapshot.punctaLineMode,
                nuclear_cell_pair_mode: snapshot.nuclearCellPairMode,
                nuclear_cell_pair_contour_mode: snapshot.nuclearCellPairContourMode,
                use_legacy_nuclear_cell_pair_pipeline: snapshot.useLegacyNuclearCellPairPipeline,
                microns_per_pixel: snapshot.micronsPerPixel,
                use_metadata_scale: snapshot.useMetadataScale,
                use_metadata_channel_order: snapshot.useMetadataChannelOrder,
                fallback_channel_order: snapshot.fallbackChannelOrder,
            };
        };

        const saveCurrentWorkflowDefaults = async () => {
            const syncResult = commitStatsStateFromInputs();
            if (!syncResult.ok) {
                showErrors(syncResult.errors || ["We couldn't save that workflow setting. Try again."]);
                return;
            }

            const confirmed = await promptWorkflowDefaultConfirmation();
            if (!confirmed) {
                return;
            }

            setWorkflowDefaultButtonsPending(true);
            try {
                const csrfTokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
                const response = await fetch(EXPERIMENT_WORKFLOW_DEFAULTS_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfTokenInput ? csrfTokenInput.value : '',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify(buildWorkflowDefaultPayload()),
                });
                const contentType = response.headers.get('content-type') || '';
                const responsePayload = contentType.includes('application/json')
                    ? await response.json()
                    : {};
                if (!response.ok) {
                    const errorMessage = Array.isArray(responsePayload.errors) && responsePayload.errors.length
                        ? responsePayload.errors.join('\n')
                        : (responsePayload.error || "We couldn't save that workflow setting. Try again.");
                    throw new Error(errorMessage);
                }

                if (responsePayload.defaults && typeof responsePayload.defaults === 'object') {
                    serverPreferenceDefaults = responsePayload.defaults;
                    if (serverPreferenceDefaultsElement) {
                        serverPreferenceDefaultsElement.textContent = JSON.stringify(responsePayload.defaults);
                    }
                }
                modalOpenSnapshot = captureStatsSnapshot();
                setFallbackChannelOrderResetBaseline(modalOpenSnapshot.fallbackChannelOrder);
                if (window.showGlobalMessage) {
                    window.showGlobalMessage(
                        responsePayload.message
                            || 'Workflow default updated. Future experiments will start with this configuration.',
                        'success'
                    );
                }
            } catch (error) {
                showWorkflowDefaultError(
                    error && error.message
                        ? error.message
                        : "We couldn't save that workflow setting. Try again."
                );
            } finally {
                setWorkflowDefaultButtonsPending(false);
            }
        };

        const switchToView = (target, animate = false) => {
            hideInfoTooltip();
            const toView = target === 'primary' ? primaryView : advancedView;
            const fromView = target === 'primary' ? advancedView : primaryView;

            if (!toView.hidden && fromView.hidden) return;

            clearSwitchTimer();
            clearAllViewAnim();

            if (!animate || prefersReducedMotion || fromView.hidden) {
                fromView.hidden = true;
                toView.hidden = false;
                return;
            }

            fromView.hidden = false;
            toView.hidden = true;
            fromView.classList.add(target === 'primary' ? 'anim-exit-backward' : 'anim-exit-forward');

            viewSwitchTimer = window.setTimeout(() => {
                clearViewAnim(fromView);
                fromView.hidden = true;
                toView.hidden = false;
                void toView.offsetWidth;
                toView.classList.add(target === 'primary' ? 'anim-enter-backward' : 'anim-enter-forward');

                viewSwitchTimer = window.setTimeout(() => {
                    clearViewAnim(toView);
                    viewSwitchTimer = null;
                }, ENTER_MS);
            }, EXIT_MS);
        };

        const showPrimary = (animate = false) => switchToView('primary', animate);
        const showAdvanced = (animate = false) => switchToView('advanced', animate);

        const openModal = () => {
            clearModalTimer();
            clearModalAnim();
            showPrimary(false);
            syncStatsUI();
            modalOpenSnapshot = captureStatsSnapshot();
            setFallbackChannelOrderResetBaseline(modalOpenSnapshot.fallbackChannelOrder);
            backdrop.style.display = 'flex';
            backdrop.setAttribute('aria-hidden', 'false');
            settingsButton.setAttribute('aria-expanded', 'true');
            if (!prefersReducedMotion) {
                void backdrop.offsetWidth;
                backdrop.classList.add('modal-enter');
                if (modalPanel) {
                    modalPanel.classList.add('modal-enter');
                }
                modalEnterTimer = window.setTimeout(() => {
                    clearModalAnim();
                    modalEnterTimer = null;
                }, MODAL_ENTER_MS);
            }
        };
        const closeModal = () => {
            hideInfoTooltip();
            clearSwitchTimer();
            clearAllViewAnim();
            backdrop.setAttribute('aria-hidden', 'true');
            settingsButton.setAttribute('aria-expanded', 'false');

            clearModalTimer();
            if (prefersReducedMotion || backdrop.style.display !== 'flex') {
                clearModalAnim();
                backdrop.style.display = 'none';
                return;
            }

            clearModalAnim();
            backdrop.classList.add('modal-exit');
            if (modalPanel) {
                modalPanel.classList.add('modal-exit');
            }
            modalCloseTimer = window.setTimeout(() => {
                clearModalAnim();
                backdrop.style.display = 'none';
                modalCloseTimer = null;
            }, MODAL_EXIT_MS);
        };
        const attemptCloseModal = async () => {
            if (backdrop.style.display !== 'flex') {
                return;
            }
            if (!hasModalChanges()) {
                closeModal();
                return;
            }
            const keepChanges = await promptUnsavedStatsDecision();
            if (keepChanges === null) {
                return;
            }
            if (!keepChanges) {
                restoreStatsSnapshot(modalOpenSnapshot);
            }
            closeModal();
        };

        settingsButton.addEventListener('click', (event) => {
            event.stopPropagation();
            openModal();
        });
        closeButton.addEventListener('click', (event) => {
            event.stopPropagation();
            attemptCloseModal();
        });
        if (openAdvanced) {
            openAdvanced.addEventListener('click', (event) => {
                event.preventDefault();
                showAdvanced(true);
            });
        }
        if (backButton) {
            backButton.addEventListener('click', (event) => {
                event.preventDefault();
                showPrimary(true);
            });
        }
        saveDefaultButtons.forEach((button) => {
            button.addEventListener('click', (event) => {
                event.preventDefault();
                saveCurrentWorkflowDefaults();
            });
        });
        backdrop.addEventListener('click', (event) => {
            if (event.target === backdrop) {
                attemptCloseModal();
            }
        });
        document.addEventListener('keydown', (event) => {
            const saveConfirmOpen = saveDefaultsBackdrop && saveDefaultsBackdrop.style.display === 'flex';
            const unsavedPromptOpen = unsavedBackdrop && unsavedBackdrop.style.display === 'flex';
            if (event.key === 'Escape' && backdrop.style.display === 'flex' && !saveConfirmOpen && !unsavedPromptOpen) {
                attemptCloseModal();
            }
        });

        const url = new URL(window.location.href);
        if (url.searchParams.get('open_settings') === 'advanced') {
            openModal();
            showAdvanced(false);
            url.searchParams.delete('open_settings');
            window.history.replaceState({}, '', url.toString());
        }
    }

    function setupNavExitGuard() {
        const navLinks = document.querySelectorAll(
            '.navbar a[href="/"], .navbar a[href="/signin/"], .navbar a[href="/signup/"], .navbar a[href="/signup/?fresh=1"], .navbar a[href="/account-settings/"], .navbar a[href="/dashboard/"], .navbar a[href="/workflow-defaults/"]'
        );
        const pageBackButton = document.getElementById('pageBackButton');
        const backdrop = document.getElementById('navExitBackdrop');
        const cancel = document.getElementById('navExitCancel');
        const confirm = document.getElementById('navExitConfirm');
        const panel = backdrop ? backdrop.querySelector('.nav-exit-modal') : null;

        if (!backdrop || !cancel || !confirm) {
            return;
        }

        let pendingHref = null;
        const openModal = (href) => {
            pendingHref = href;
            openPopupModal(backdrop, panel);
        };
        const closeModal = () => {
            closePopupModal(backdrop, panel, () => {
                pendingHref = null;
            });
        };
        const handleNavClick = (event) => {
            if (getQueuedCount() === 0) {
                return;
            }
            event.preventDefault();
            openModal(event.currentTarget.getAttribute('href'));
        };

        navLinks.forEach((link) => link.addEventListener('click', handleNavClick));
        if (pageBackButton) {
            pageBackButton.addEventListener('click', (event) => {
                if (getQueuedCount() === 0) {
                    window.location.href = '/';
                    return;
                }
                event.preventDefault();
                openModal('/');
            });
        }

        cancel.addEventListener('click', closeModal);
        confirm.addEventListener('click', () => {
            if (pendingHref) {
                window.location.href = pendingHref;
            }
        });
        backdrop.addEventListener('click', (event) => {
            if (event.target === backdrop) {
                closeModal();
            }
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                closeModal();
            }
        });
    }

    function getQueuePanelHeightLimit() {
        return Math.min(window.innerHeight * 0.4, QUEUE_PANEL_MAX_HEIGHT_PX);
    }

    function getQueueEntries() {
        const entries = [];

        restoredQueueItems.forEach((item) => {
            entries.push({
                key: `restored:${item.uuid}`,
                label: item.name,
                remove: () => {
                    restoredQueueItems = restoredQueueItems.filter((queued) => queued.uuid !== item.uuid);
                },
            });
        });

        selectedFiles.forEach((file, fileName) => {
            entries.push({
                key: `selected:${fileName}`,
                label: file.webkitRelativePath || file.name,
                remove: () => {
                    selectedFiles.delete(fileName);
                },
            });
        });

        return entries;
    }

    function finalizeQueuePanelState(fileList, hasItems) {
        fileList.classList.remove('is-resizing');
        fileList.classList.toggle('is-active', hasItems);
        fileList.style.height = hasItems ? '' : '0px';
        fileList.style.overflowY = '';
        fileList.style.opacity = '';
        fileList.setAttribute('aria-hidden', hasItems ? 'false' : 'true');
        fileList._queuePanelCleanupTimer = 0;
        fileList._queuePanelFrame = 0;
    }

    function clearQueuePanelAnimation(fileList) {
        if (fileList._queuePanelFrame) {
            window.cancelAnimationFrame(fileList._queuePanelFrame);
            fileList._queuePanelFrame = 0;
        }
        if (fileList._queuePanelCleanupTimer) {
            window.clearTimeout(fileList._queuePanelCleanupTimer);
            fileList._queuePanelCleanupTimer = 0;
        }
    }

    function queueNeedsScrollbar(fileList, renderedHeight) {
        if (!fileList || renderedHeight <= 0) {
            return false;
        }
        return fileList.scrollHeight > renderedHeight + 1;
    }

    function animateQueuePanelUpdate(fileList, mutateDom) {
        if (!fileList) {
            mutateDom();
            updateUploadQuotaStatus();
            return;
        }

        clearQueuePanelAnimation(fileList);

        const startHeight = Math.round(fileList.getBoundingClientRect().height);
        const startHasItems = fileList.children.length > 0;
        const startHasScrollbar = queueNeedsScrollbar(fileList, startHeight);

        mutateDom();

        const hasItems = fileList.children.length > 0;
        fileList.classList.toggle('is-active', hasItems);
        const targetScrollHeight = fileList.scrollHeight;
        const targetHeight = hasItems
            ? Math.min(targetScrollHeight, getQueuePanelHeightLimit())
            : 0;
        const targetHasScrollbar = hasItems && targetScrollHeight > targetHeight + 1;
        const shouldAnimatePanel =
            QUEUE_PANEL_ANIM_MS > 0 &&
            (startHeight !== targetHeight || startHasItems !== hasItems || startHasScrollbar !== targetHasScrollbar);

        if (!shouldAnimatePanel) {
            fileList.style.height = hasItems ? '' : '0px';
            fileList.style.overflowY = '';
            fileList.style.opacity = '';
            finalizeQueuePanelState(fileList, hasItems);
            updateUploadQuotaStatus();
            return;
        }

        fileList.style.height = `${startHeight}px`;
        fileList.style.overflowY = startHasScrollbar && targetHasScrollbar ? 'auto' : 'hidden';
        fileList.style.opacity = startHeight > 0 ? '0.94' : '0';
        fileList.classList.add('is-resizing');

        fileList.offsetHeight;
        fileList._queuePanelFrame = window.requestAnimationFrame(() => {
            fileList.classList.toggle('is-active', hasItems);
            fileList.style.height = `${targetHeight}px`;
            fileList.style.opacity = hasItems ? '1' : '0';
        });
        fileList._queuePanelCleanupTimer = window.setTimeout(() => {
            finalizeQueuePanelState(fileList, hasItems);
        }, QUEUE_PANEL_ANIM_MS + 40);

        updateUploadQuotaStatus();
    }

    function animateQueueRowRemoval(listItem, removeItem) {
        if (typeof removeItem !== 'function') return;
        if (!listItem || QUEUE_ROW_FADE_MS === 0) {
            removeItem();
            displayFileQueue();
            return;
        }
        if (listItem.dataset.removing === 'true') {
            return;
        }
        listItem.dataset.removing = 'true';
        listItem.classList.add('is-exiting');
        window.setTimeout(() => {
            removeItem();
            displayFileQueue();
        }, QUEUE_ROW_FADE_MS);
    }

    function animateQueueClear(clearQueue) {
        const fileList = document.getElementById('fileList');
        if (typeof clearQueue !== 'function') return;
        if (!fileList || QUEUE_ROW_FADE_MS === 0) {
            clearQueue();
            displayFileQueue();
            return;
        }
        const rows = Array.from(fileList.querySelectorAll('.file-item'));
        if (!rows.length) {
            clearQueue();
            displayFileQueue();
            return;
        }
        rows.forEach((row) => row.classList.add('is-exiting'));
        window.setTimeout(() => {
            clearQueue();
            displayFileQueue();
        }, QUEUE_ROW_FADE_MS);
    }

    function createQueueRow(entry, enteringKeys) {
        const listItem = document.createElement('div');
        listItem.className = 'file-item';
        listItem.dataset.queueKey = entry.key;
        if (enteringKeys && enteringKeys.has(entry.key) && !prefersReducedMotionGlobal) {
            listItem.classList.add('is-entering');
        }

        const fileNameSpan = document.createElement('span');
        fileNameSpan.textContent = entry.label;

        const removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.textContent = 'X';
        removeButton.className = 'remove-btn';
        removeButton.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            animateQueueRowRemoval(listItem, entry.remove);
        });

        listItem.appendChild(fileNameSpan);
        listItem.appendChild(removeButton);
        return listItem;
    }

    function displayFileQueue(options = {}) {
        const { enteringKeys = new Set(), skipAnimation = false } = options;
        const fileList = document.getElementById('fileList');
        if (!fileList) {
            updateUploadQuotaStatus();
            return;
        }

        const renderQueueRows = () => {
            fileList.innerHTML = '';
            getQueueEntries().forEach((entry) => {
                fileList.appendChild(createQueueRow(entry, enteringKeys));
            });
        };

        if (skipAnimation) {
            clearQueuePanelAnimation(fileList);
            renderQueueRows();
            finalizeQueuePanelState(fileList, fileList.children.length > 0);
            updateUploadQuotaStatus();
            return;
        }

        animateQueuePanelUpdate(fileList, renderQueueRows);
    }

    function setupResetModal() {
        const clearQueueButton = document.getElementById('clearQueueButton');
        const resetBackdrop = document.getElementById('resetBackdrop');
        const resetConfirm = document.getElementById('resetConfirm');
        const resetCancel = document.getElementById('resetCancel');
        const resetPanel = resetBackdrop ? resetBackdrop.querySelector('.reset-modal') : null;

        const openResetModal = () => {
            if (!resetBackdrop) return;
            openPopupModal(resetBackdrop, resetPanel);
        };
        const closeResetModal = () => {
            if (!resetBackdrop) return;
            closePopupModal(resetBackdrop, resetPanel);
        };

        if (clearQueueButton) {
            clearQueueButton.addEventListener('click', () => {
                if (getQueuedCount() === 0) return;
                openResetModal();
            });
        }
        if (resetConfirm) {
            resetConfirm.addEventListener('click', () => {
                animateQueueClear(() => {
                    selectedFiles.clear();
                    restoredQueueItems = [];
                });
                closeResetModal();
            });
        }
        if (resetCancel) {
            resetCancel.addEventListener('click', closeResetModal);
        }
        if (resetBackdrop) {
            resetBackdrop.addEventListener('click', (event) => {
                if (event.target === resetBackdrop) {
                    closeResetModal();
                }
            });
        }
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                closeResetModal();
            }
        });
    }

    const SUPPORTED_UPLOAD_EXTENSIONS = ['.dv', '.tif', '.tiff'];
    const SUPPORTED_UPLOAD_EXTENSIONS_LABEL = '.dv, .tif, .tiff';

    function isSupportedUploadFileName(fileName) {
        const normalizedName = String(fileName || '').toLowerCase();
        return SUPPORTED_UPLOAD_EXTENSIONS.some(extension => normalizedName.endsWith(extension));
    }

    function openFolderIssueModal({ validCount, duplicateFiles, invalidFiles }) {
        const backdrop = document.getElementById('folderIssueBackdrop');
        const panel = backdrop ? backdrop.querySelector('.folder-issue-modal') : null;
        const body = document.getElementById('folderIssueBody');
        const list = document.getElementById('folderIssueList');
        const noBtn = document.getElementById('folderIssueNo');
        const yesBtn = document.getElementById('folderIssueYes');

        if (!backdrop || !body || !list || !noBtn || !yesBtn) {
            return Promise.resolve(true);
        }

        const duplicateCount = Array.isArray(duplicateFiles) ? duplicateFiles.length : 0;
        const invalidCount = Array.isArray(invalidFiles) ? invalidFiles.length : 0;

        if (validCount > 0) {
            const plural = validCount === 1 ? '' : 's';
            body.textContent = `Some files in this folder cannot be added. Add ${validCount} supported image file${plural} to the queue?`;
        } else {
            body.textContent = 'No new supported image files are available to add from this folder.';
        }

        list.innerHTML = '';
        if (duplicateCount > 0) {
            const plural = duplicateCount === 1 ? '' : 's';
            const item = document.createElement('li');
            item.textContent = `${duplicateCount} duplicate supported image file${plural} already in queue`;
            list.appendChild(item);
        }
        if (invalidCount > 0) {
            const item = document.createElement('li');
            item.textContent = invalidCount === 1
                ? `1 file is not a supported image file (${SUPPORTED_UPLOAD_EXTENSIONS_LABEL})`
                : `${invalidCount} files are not supported image files (${SUPPORTED_UPLOAD_EXTENSIONS_LABEL})`;
            list.appendChild(item);
        }

        yesBtn.disabled = validCount <= 0;
        openPopupModal(backdrop, panel);

        return new Promise((resolve) => {
            let settled = false;

            const close = (accepted) => {
                if (settled) return;
                settled = true;
                cleanup();
                closePopupModal(backdrop, panel, () => resolve(accepted));
            };

            const onNo = () => close(false);
            const onYes = () => {
                if (yesBtn.disabled) return;
                close(true);
            };
            const onBackdrop = (evt) => {
                if (evt.target === backdrop) {
                    close(false);
                }
            };
            const onKeydown = (evt) => {
                if (evt.key === 'Escape') {
                    close(false);
                }
            };

            const cleanup = () => {
                noBtn.removeEventListener('click', onNo);
                yesBtn.removeEventListener('click', onYes);
                backdrop.removeEventListener('click', onBackdrop);
                document.removeEventListener('keydown', onKeydown);
            };

            noBtn.addEventListener('click', onNo);
            yesBtn.addEventListener('click', onYes);
            backdrop.addEventListener('click', onBackdrop);
            document.addEventListener('keydown', onKeydown);
        });
    }

    async function handleFileSelection(event) {
        const files = Array.from(event.target.files);
        const isFolderSelection = event.target && event.target.id === 'folderInput';
        const duplicateFiles = [];
        const invalidFiles = [];
        const filesToAdd = [];
        const queuedNames = getQueuedNameSet();

        files.forEach(file => {
            const fileName = file.name;

            if (!isSupportedUploadFileName(file.name)) {
                invalidFiles.push(file.name);
                return;
            }

            if (queuedNames.has(fileName)) {
                duplicateFiles.push(fileName);
            } else {
                filesToAdd.push([fileName, file]);
                queuedNames.add(fileName);
            }
        });

        if (isFolderSelection && (invalidFiles.length > 0 || duplicateFiles.length > 0)) {
            const shouldAdd = await openFolderIssueModal({
                validCount: filesToAdd.length,
                duplicateFiles,
                invalidFiles,
            });
            if (!shouldAdd) {
                event.target.value = '';
                return;
            }
        }

        const enteringKeys = new Set();
        filesToAdd.forEach(([fileName, file]) => {
            selectedFiles.set(fileName, file);
            enteringKeys.add(`selected:${fileName}`);
        });

        if (!isFolderSelection) {
            const queueIssues = [];
            if (invalidFiles.length > 0) {
                queueIssues.push(
                    `Unsupported files detected (only supported image files (${SUPPORTED_UPLOAD_EXTENSIONS_LABEL}) are allowed): ${formatFileListForError(invalidFiles)}`
                );
            }
            if (duplicateFiles.length > 0) {
                const uniqueDuplicates = [...new Set(duplicateFiles)];
                const duplicatePreviewLimit = 10;
                const duplicatePreview = uniqueDuplicates.slice(0, duplicatePreviewLimit);
                const remainingDuplicates = uniqueDuplicates.length - duplicatePreview.length;

                if (queueIssues.length > 0) {
                    queueIssues.push('');
                }
                queueIssues.push('Duplicate files detected and skipped:');
                duplicatePreview.forEach((name) => {
                    queueIssues.push(`- ${name}`);
                });
                if (remainingDuplicates > 0) {
                    queueIssues.push(`- (+${remainingDuplicates} more)`);
                }
            }
            if (queueIssues.length > 0) {
                showErrors(queueIssues);
            }
        }

        if (enteringKeys.size > 0) {
            displayFileQueue({ enteringKeys });
        }

        // Clear the input value to allow re-adding the same file
        event.target.value = '';
    }

    function setupFileInputs() {
        const fileInput = document.getElementById('fileInput');
        const folderInput = document.getElementById('folderInput');
        if (fileInput) fileInput.addEventListener('change', handleFileSelection);
        if (folderInput) folderInput.addEventListener('change', handleFileSelection);
    }

    const UPLOAD_PREPARATION_TIMEOUT_MS = 1800000;
    const UPLOAD_PREPARATION_POLL_INITIAL_DELAY_MS = 50;
    const UPLOAD_PREPARATION_POLL_MAX_DELAY_MS = 500;
    const UPLOAD_CONTROL_SELECTOR = '.upload-btn, .submit-btn, .settings-btn, .settings-close, .advanced-btn, .back-btn, .workflow-default-btn, .upload-page-back-btn, .folder-issue-btn, input[type="file"], input[type="checkbox"], input[type="number"], .remove-btn';

    function getUploadSubmitParts() {
        const submitBtn = document.getElementById('uploadSubmit');
        const btnText = submitBtn ? submitBtn.querySelector('.btn-text') : null;
        return { submitBtn, btnText };
    }

    function setUploadControlsDisabled(disabled) {
        const controls = document.querySelectorAll(UPLOAD_CONTROL_SELECTOR);
        controls.forEach((el) => {
            el.disabled = disabled;
            el.style.pointerEvents = disabled ? 'none' : '';
            el.style.cursor = disabled ? 'not-allowed' : '';
        });
    }

    function setUploadProgressForButton(submitBtn, payload) {
        if (submitBtn && window.CytoCVAsyncProgress) {
            window.CytoCVAsyncProgress.set(submitBtn, payload);
        }
    }

    function clearUploadProgressForButton(submitBtn) {
        if (submitBtn && window.CytoCVAsyncProgress) {
            window.CytoCVAsyncProgress.clear(submitBtn);
        }
    }

    function applyUploadPhaseText(btnText, phase) {
        if (!btnText || !phase) return;
        if (phase === 'Validating Files') {
            btnText.textContent = 'Validating Files';
        } else if (phase === 'Extracting Image Metadata') {
            btnText.textContent = 'Extracting Image Metadata';
        } else if (phase === 'Preparing Previews') {
            btnText.textContent = 'Preparing Previews';
        } else {
            btnText.textContent = phase;
        }
    }

    function lockUploadUi(payload) {
        const { submitBtn, btnText } = getUploadSubmitParts();
        if (!submitBtn) return { submitBtn, btnText };
        setUploadControlsDisabled(true);
        submitBtn.classList.add('loading');
        submitBtn.style.backgroundColor = '#0056b3';
        if (payload && payload.phase) {
            applyUploadPhaseText(btnText, payload.phase);
            setUploadProgressForButton(submitBtn, payload);
        } else {
            if (btnText) btnText.textContent = 'Preprocess Files';
            setUploadProgressForButton(submitBtn, {
                phase: 'Preprocess Files',
                message: 'Preparing upload request.',
            });
        }
        return { submitBtn, btnText };
    }

    function unlockUploadUi() {
        const { submitBtn, btnText } = getUploadSubmitParts();
        if (submitBtn) {
            submitBtn.classList.remove('loading');
            submitBtn.style.backgroundColor = '';
            clearUploadProgressForButton(submitBtn);
        }
        if (btnText) btnText.textContent = 'Preprocess Files';
        setUploadControlsDisabled(false);
    }

    function createUploadUserError(errors) {
        const err = new Error('user-facing-upload-error');
        err.userErrors = Array.isArray(errors) ? errors : [String(errors || 'Upload failed.')];
        return err;
    }

    function failWithUploadErrors(errors) {
        throw createUploadUserError(errors);
    }

    async function parseUploadJsonResponse(response) {
        const contentType = response.headers.get('content-type') || '';
        const payload = contentType.includes('application/json') ? await response.json() : {};
        if (!response.ok) {
            const lines = Array.isArray(payload.errors) && payload.errors.length > 0
                ? payload.errors
                : [payload.error || 'Upload failed. Please try again.'];
            failWithUploadErrors(lines);
        }
        return payload;
    }

    function persistUploadPreparationErrors(payload) {
        if (Array.isArray(payload?.errors) && payload.errors.length > 0) {
            sessionStorage.setItem('dvErrors', JSON.stringify(payload.errors));
        }
    }

    function redirectToUploadPreparationResult(payload, message) {
        persistUploadPreparationErrors(payload);
        if (message && window.showGlobalMessage) {
            window.showGlobalMessage(message, 'info', {
                scope: 'upload-preparation',
                top: 'calc(var(--nav-height) + 8px)',
                timeoutMs: 2500,
            });
        }
        window.setTimeout(() => {
            window.location.href = payload.redirect;
        }, message ? 250 : 0);
    }

    function handleTerminalUploadPreparationPayload(payload, { submitBtn } = {}) {
        if (!payload || typeof payload.status !== 'string') return false;
        if (payload.status === 'succeeded') {
            clearUploadProgressForButton(submitBtn);
            if (payload.redirect) {
                redirectToUploadPreparationResult(payload);
                return true;
            }
            failWithUploadErrors([
                'Upload preparation completed, but the preprocess page could not be resolved. Please refresh.',
            ]);
        }
        if (payload.status === 'failed') {
            const failureLines = Array.isArray(payload.errors) && payload.errors.length > 0
                ? payload.errors
                : [payload.failure_summary || 'Upload preparation failed. Please try again.'];
            failWithUploadErrors(failureLines);
        }
        if (payload.status === 'cancelled') {
            failWithUploadErrors(['Upload preparation was cancelled.']);
        }
        return false;
    }

    async function pollUploadPreparationJob(jobUuid, { signal, deadline, submitBtn, btnText }) {
        const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
        let delay = UPLOAD_PREPARATION_POLL_INITIAL_DELAY_MS;
        while (Date.now() < deadline) {
            const statusResponse = await fetch(`/api/experiment/upload-prep/${encodeURIComponent(jobUuid)}/`, {
                cache: 'no-store',
                signal,
            });
            const statusPayload = await parseUploadJsonResponse(statusResponse);
            if (statusPayload.phase) {
                applyUploadPhaseText(btnText, statusPayload.phase);
                setUploadProgressForButton(submitBtn, {
                    ...(statusPayload.detail || {}),
                    phase: statusPayload.phase,
                    status: statusPayload.status,
                });
            }
            if (handleTerminalUploadPreparationPayload(statusPayload, { submitBtn })) {
                return;
            }
            await wait(delay);
            delay = Math.min(UPLOAD_PREPARATION_POLL_MAX_DELAY_MS, Math.round(delay * 1.15));
        }
        throw new DOMException('Upload timed out.', 'AbortError');
    }

    function resumeUploadPreparationFromServer() {
        if (!uploadResumePayload || typeof uploadResumePayload !== 'object') return;
        if (!uploadResumePayload.job_uuid || typeof uploadResumePayload.status !== 'string') return;

        const status = uploadResumePayload.status;
        if (status === 'succeeded' && uploadResumePayload.redirect) {
            redirectToUploadPreparationResult(
                uploadResumePayload,
                'Upload preparation finished. Continuing to preprocess.',
            );
            return;
        }
        if (status === 'failed') {
            const failureLines = Array.isArray(uploadResumePayload.errors) && uploadResumePayload.errors.length > 0
                ? uploadResumePayload.errors
                : [uploadResumePayload.failure_summary || 'Upload preparation failed. Please try again.'];
            showErrors(failureLines);
            return;
        }
        if (status === 'cancelled') {
            showErrors(['Upload preparation was cancelled.']);
            return;
        }
        if (!['queued', 'running', 'cancelling'].includes(status)) {
            return;
        }

        const { submitBtn, btnText } = lockUploadUi({
            ...(uploadResumePayload.detail || {}),
            phase: uploadResumePayload.phase || 'Queued',
            status: uploadResumePayload.status,
            message: uploadResumePayload.detail?.message || 'Reconnecting to upload-preparation worker.',
        });
        if (!submitBtn) return;

        const uploadController = new AbortController();
        const uploadTimeout = setTimeout(() => uploadController.abort(), UPLOAD_PREPARATION_TIMEOUT_MS);
        pollUploadPreparationJob(uploadResumePayload.job_uuid, {
            signal: uploadController.signal,
            deadline: Date.now() + UPLOAD_PREPARATION_TIMEOUT_MS,
            submitBtn,
            btnText,
        }).catch((err) => {
            console.error(err);
            if (err && Array.isArray(err.userErrors)) {
                showErrors(err.userErrors);
            } else if (err && err.name === 'AbortError') {
                showErrors([
                    'Lost connection to upload preparation. Refresh to reconnect to the active job.',
                ]);
            } else {
                showErrors([
                    'Upload status could not be refreshed. Refresh to reconnect to the active job.',
                ]);
            }
            unlockUploadUi();
        }).finally(() => {
            clearTimeout(uploadTimeout);
        });
    }

    function setupUploadSubmit() {
        const uploadForm = document.getElementById('uploadForm');
        if (!uploadForm) return;

        uploadForm.addEventListener('submit', async function (event) {
            event.preventDefault();

            const queuedCount = getQueuedCount();
            if (queuedCount === 0) {
                showErrors([
                    'No files selected. Upload at least one supported image file before preprocessing.',
                ]);
                return;
            }
            const uploadMaxFiles = getUploadMaxFiles();
            if (uploadMaxFiles !== null && queuedCount > uploadMaxFiles) {
                showErrors(buildUploadFileLimitErrors(queuedCount));
                return;
            }

            const syncResult = commitStatsStateFromInputs();
            if (!syncResult.ok) {
                showErrors(syncResult.errors || [
                    'Micrometers-per-pixel must be greater than 0 when using micrometer input.',
                ]);
                return;
            }

            const punctaLineWidthPixels = convertLengthToPixels(statsState.punctaLineWidth, statsState.punctaLineWidthUnit, 1, 1);
            const cenDotDistancePixels = convertLengthToPixels(statsState.cenDotDistance, statsState.cenDotDistanceUnit, 0, 37);
            const cenDotProximityRadiusPixels = convertLengthToPixels(statsState.cenDotProximityRadius, statsState.cenDotProximityRadiusUnit, 0, 13);

            const { submitBtn, btnText } = lockUploadUi();
            if (!submitBtn) return;

            const settingsBackdrop = document.getElementById('settingsBackdrop');
            if (settingsBackdrop) {
                hideInfoTooltip();
                settingsBackdrop.classList.remove('modal-enter', 'modal-exit');
                const settingsPanel = settingsBackdrop.querySelector('.settings-modal');
                if (settingsPanel) {
                    settingsPanel.classList.remove('modal-enter', 'modal-exit');
                }
                settingsBackdrop.style.display = 'none';
                settingsBackdrop.setAttribute('aria-hidden', 'true');
            }

            const moduleEnabled = !!statsState.moduleEnabled;
            const layerEnabled = moduleEnabled && !!statsState.enforceLayerCount;
            const wavelengthEnabled = moduleEnabled && !!statsState.enforceAllWavelengths;
            const statsRequired = getStatsRequiredChannels();
            const extraRequiredChannels = moduleEnabled
                ? [...statsState.manualRequiredChannels].filter((channel) => !statsRequired.has(channel))
                : [];

            const prepData = new FormData();
            restoredQueueItems.forEach((item) => prepData.append('existing_uuids', item.uuid));
            prepData.append('cytocv_analysis_enabled', moduleEnabled ? '1' : '0');
            prepData.append('enforce_layer_count', layerEnabled ? '1' : '0');
            prepData.append('enforce_wavelengths', wavelengthEnabled ? '1' : '0');
            extraRequiredChannels.forEach((channel) => prepData.append('extra_required_channels', channel));
            [...getEffectiveSelectedPlugins()].forEach((pluginId) => prepData.append('selected_analysis', pluginId));
            prepData.append('signalQuantificationEnabled', String(statsState.signalQuantificationEnabled));
            prepData.append('signalQuantificationMode', normalizeSignalMode(statsState.signalQuantificationMode));
            prepData.append('punctaContourIntensityEnabled', String(statsState.punctaContourIntensityEnabled));
            prepData.append('alternateNucleusDetectionEnabled', String(statsState.alternateNucleusDetectionEnabled));
            prepData.append('stats_puncta_line_width_value', String(statsState.punctaLineWidth));
            prepData.append('stats_cen_dot_distance_value', String(statsState.cenDotDistance));
            prepData.append('stats_cen_dot_proximity_radius_value', String(statsState.cenDotProximityRadius));
            prepData.append('biorientationRedMinDistance', String(statsState.biorientationRedMinDistance));
            prepData.append('biorientationRedMaxDistance', String(statsState.biorientationRedMaxDistance));
            prepData.append('biorientationCollinearityThreshold', String(statsState.biorientationCollinearityThreshold));
            prepData.append('greenDotSplitEnabled', String(
                selectedStatsRequireChannel('channel_green') && statsState.greenDotSplitEnabled
            ));
            prepData.append('greenDotSplitMode', normalizeGreenDotSplitMode(statsState.greenDotSplitMode));
            prepData.append('redDotSplitEnabled', String(
                selectedStatsRequireChannel('channel_red') && statsState.redDotSplitEnabled
            ));
            prepData.append('redDotSplitMode', normalizeRedDotSplitMode(statsState.redDotSplitMode));
            prepData.append('punctaLineWidth', String(punctaLineWidthPixels));
            prepData.append('cenDotDistance', String(cenDotDistancePixels));
            prepData.append('cenDotProximityRadius', String(cenDotProximityRadiusPixels));
            prepData.append('puncta_line_mode', statsState.punctaLineMode);
            prepData.append('nuclear_cell_pair_mode', statsState.nuclearCellPairMode);
            prepData.append('nuclear_cell_pair_contour_mode', normalizeNuclearContourMode(statsState.nuclearCellPairContourMode));
            prepData.append('use_legacy_nuclear_cell_pair_pipeline', String(statsState.useLegacyNuclearCellPairPipeline));
            prepData.append('greenContourFilterEnabled', String(statsState.greenContourFilterEnabled));
            prepData.append('alternateRedDetection', String(statsState.alternateNucleusDetectionEnabled));
            const allUnitsMatch = statsState.punctaLineWidthUnit === statsState.cenDotDistanceUnit
                && statsState.cenDotDistanceUnit === statsState.cenDotProximityRadiusUnit;
            const sharedLengthUnit = allUnitsMatch
                ? statsState.punctaLineWidthUnit
                : 'mixed';
            prepData.append('stats_length_unit', sharedLengthUnit);
            prepData.append('stats_puncta_line_width_unit', statsState.punctaLineWidthUnit);
            prepData.append('stats_cen_dot_distance_unit', statsState.cenDotDistanceUnit);
            prepData.append('stats_cen_dot_proximity_radius_unit', statsState.cenDotProximityRadiusUnit);
            prepData.append('biorientationRedMinDistanceUnit', statsState.biorientationRedMinDistanceUnit);
            prepData.append('biorientationRedMaxDistanceUnit', statsState.biorientationRedMaxDistanceUnit);
            prepData.append('stats_biorientation_red_min_distance_value', String(statsState.biorientationRedMinDistance));
            prepData.append('stats_biorientation_red_max_distance_value', String(statsState.biorientationRedMaxDistance));
            prepData.append('stats_biorientation_red_min_distance_unit', statsState.biorientationRedMinDistanceUnit);
            prepData.append('stats_biorientation_red_max_distance_unit', statsState.biorientationRedMaxDistanceUnit);
            prepData.append('stats_microns_per_pixel', String(statsState.micronsPerPixel));
            prepData.append('stats_use_metadata_scale', statsState.useMetadataScale ? '1' : '0');
            prepData.append('stats_use_metadata_channel_order', statsState.useMetadataChannelOrder ? '1' : '0');
            normalizeChannelOrder(statsState.fallbackChannelOrder).forEach((channel) => {
                prepData.append('stats_fallback_channel_order', channel);
            });

            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            const uploadController = new AbortController();
            const uploadTimeout = setTimeout(() => uploadController.abort(), UPLOAD_PREPARATION_TIMEOUT_MS);

            const selectedFileList = [...selectedFiles.values()];
            const oversizedFiles = selectedFileList.filter((file) => file.size > UPLOAD_BATCH_TARGET_BYTES);
            const buildFileBatches = (files, targetBytes) => {
                const batches = [];
                let current = [];
                let currentBytes = 0;
                files.forEach((file) => {
                    const size = Number(file.size) || 0;
                    if (current.length > 0 && currentBytes + size > targetBytes) {
                        batches.push(current);
                        current = [];
                        currentBytes = 0;
                    }
                    current.push(file);
                    currentBytes += size;
                });
                if (current.length > 0) batches.push(current);
                return batches;
            };

            try {
                if (oversizedFiles.length > 0) {
                    const fileList = oversizedFiles.slice(0, 5).map((file) => `${file.name} (${formatStorageBytes(file.size)})`);
                    const remaining = oversizedFiles.length - fileList.length;
                    if (remaining > 0) fileList.push(`(+${remaining} more)`);
                    failWithUploadErrors([
                        `Each individual file must be ${formatStorageBytes(UPLOAD_BATCH_TARGET_BYTES)} or smaller.`,
                        ...fileList,
                    ]);
                }

                const uploadedRunUuids = [];
                const batches = buildFileBatches(selectedFileList, UPLOAD_BATCH_TARGET_BYTES);
                for (let index = 0; index < batches.length; index += 1) {
                    if (btnText) {
                        btnText.textContent = batches.length > 1
                            ? `Uploading ${index + 1}/${batches.length}`
                            : 'Uploading Files';
                    }
                    setUploadProgressForButton(submitBtn, {
                        phase: 'Uploading Files',
                        batchIndex: index + 1,
                        batchTotal: batches.length,
                        fileName: batches[index][0] ? batches[index][0].name : '',
                    });
                    const batchData = new FormData();
                    batches[index].forEach((file) => batchData.append('files', file));
                    const uploadResponse = await fetch(EXPERIMENT_UPLOAD_BATCH_URL, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                        body: batchData,
                        signal: uploadController.signal,
                    });
                    const uploadPayload = await parseUploadJsonResponse(uploadResponse);
                    (uploadPayload.uploads || []).forEach((item) => {
                        if (item && item.uuid) uploadedRunUuids.push(item.uuid);
                    });
                }

                uploadedRunUuids.forEach((uuid) => prepData.append('new_run_uuids', uuid));
                const uploadPrepUsesWorker = UPLOAD_PREPARATION_EXECUTION_MODE === 'worker';
                applyUploadPhaseText(btnText, uploadPrepUsesWorker ? 'Queued' : 'Preparing Upload');
                setUploadProgressForButton(submitBtn, {
                    phase: uploadPrepUsesWorker ? 'Queued' : 'Preparing Upload',
                    message: uploadPrepUsesWorker
                        ? 'Waiting for upload-preparation worker.'
                        : 'Validating files, extracting metadata, and preparing previews in this request.',
                });
                const prepResponse = await fetch(EXPERIMENT_UPLOAD_PREPARE_URL, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: prepData,
                    signal: uploadController.signal,
                });
                const prepPayload = await parseUploadJsonResponse(prepResponse);
                if (!prepPayload.job_uuid) {
                    failWithUploadErrors(['Upload preparation could not be started. Please try again.']);
                }
                if (handleTerminalUploadPreparationPayload(prepPayload, { submitBtn })) {
                    return;
                }

                await pollUploadPreparationJob(prepPayload.job_uuid, {
                    signal: uploadController.signal,
                    deadline: Date.now() + UPLOAD_PREPARATION_TIMEOUT_MS,
                    submitBtn,
                    btnText,
                });
            } catch (err) {
                console.error(err);
                if (err && Array.isArray(err.userErrors)) {
                    showErrors(err.userErrors);
                } else if (err && err.name === 'AbortError') {
                    showErrors([
                        'Upload timed out. Please check file validity or try again.',
                    ]);
                } else {
                    showErrors([
                        'Upload failed. Please try again.',
                    ]);
                }
                unlockUploadUi();
            } finally {
                clearTimeout(uploadTimeout);
            }
        });
    }
