(() => {
  const navButtons = [...document.querySelectorAll('.nav button')];
  const sections = {
    plugins: document.getElementById('sec-plugins'),
    advanced: document.getElementById('sec-advanced'),
    saving: document.getElementById('sec-saving'),
  };
  const sectionLabelByKey = {
    plugins: 'Plugin Settings',
    advanced: 'Advanced Settings',
    saving: 'Preferences',
  };
  const validSections = new Set(Object.keys(sections));
  let activeSection = 'plugins';
  const updateSectionQueryParam = (id) => {
    if (!window.history || !window.history.replaceState) return;
    const url = new URL(window.location.href);
    if (id === 'plugins') {
      url.searchParams.delete('section');
    } else {
      url.searchParams.set('section', id);
    }
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
  };
  const sectionRedirectPath = (id) => {
    const url = new URL(window.location.href);
    if (id === 'plugins') {
      url.searchParams.delete('section');
    } else {
      url.searchParams.set('section', id);
    }
    return `${url.pathname}${url.search}${url.hash}`;
  };
  const showSection = (id, options = {}) => {
    if (!validSections.has(id)) return;
    activeSection = id;
    navButtons.forEach((button) => button.classList.toggle('active', button.dataset.sec === id));
    Object.entries(sections).forEach(([name, panel]) => {
      if (!panel) return;
      const isActive = name === id;
      panel.hidden = !isActive;
      if (isActive) {
        panel.classList.remove('fade-enter');
        requestAnimationFrame(() => panel.classList.add('fade-enter'));
      } else {
        panel.classList.remove('fade-enter');
      }
    });
    if (options.syncUrl !== false) {
      updateSectionQueryParam(id);
    }
  };
  const sectionFromUrl = new URLSearchParams(window.location.search).get('section');
  showSection(validSections.has(sectionFromUrl) ? sectionFromUrl : 'plugins', { syncUrl: false });

  let payload = {};
  try {
    payload = JSON.parse(document.getElementById('pluginDependencyPayload').textContent || '{}');
  } catch (err) {
    payload = {};
  }
  const pluginCatalog = Array.isArray(payload.plugins) ? payload.plugins : [];
  const pluginMap = new Map(pluginCatalog.map((plugin) => [plugin.id, plugin]));
  const channelLabels = payload.channel_labels || {};
  const alwaysRequired = new Set(payload.always_required_channels || []);
  const pluginToggles = [...document.querySelectorAll('.plugin-toggle')];
  const channelToggles = [...document.querySelectorAll('.channel-toggle')];
  const manualRequiredBox = document.getElementById('manualRequiredChannels');
  const manualRequiredChannels = new Set(
    [...(manualRequiredBox ? manualRequiredBox.querySelectorAll('input[name="manual_required_channels"]') : [])]
      .map((input) => input.value)
      .filter((value) => value && !alwaysRequired.has(value))
  );
  const selectedPlugins = new Set(
    pluginToggles.filter((toggle) => toggle.checked).map((toggle) => toggle.value)
  );
  const signalPrimaryPlugins = new Set(['PunctaDistance', 'GreenRedIntensity', 'NuclearCellPairIntensity']);
  const overrideBox = document.getElementById('overrideChannels');
  const overrides = new Set(
    [...(overrideBox ? overrideBox.querySelectorAll('input[name=\"override_required_channels\"]') : [])]
      .map((input) => input.value)
      .filter((value) => value)
  );
  const pluginForm = document.getElementById('pluginForm');
  const signalSelectedPluginsBox = document.getElementById('signalSelectedPlugins');
  const signalQuantificationEnabledInput = document.getElementById('signal_quantification_enabled');
  const signalQuantificationModeInput = document.getElementById('signal_quantification_mode');
  const signalQuantificationInline = document.getElementById('signalQuantificationInline');
  const signalQuantificationModule = document.getElementById('signalQuantificationModule');
  const signalModePausedNote = document.getElementById('signalModePausedNote');
  const SIGNAL_MODE_NOTICE_FADE_MS = 120;
  let signalModeNoticeTimer = null;
  let signalModeNoticeTransition = 0;
  const punctaContourIntensityEnabledInput = document.getElementById('puncta_contour_intensity_enabled');
  const alternateNucleusDetectionInput = document.getElementById('alternate_nucleus_detection_enabled');
  const advancedForm = document.getElementById('advancedForm');
  const savingForm = document.getElementById('savingForm');
  const sectionFormMap = {
    plugins: pluginForm,
    advanced: advancedForm,
    saving: savingForm,
  };

  const confirmBack = document.getElementById('confirmBack');
  const confirmMsg = document.getElementById('confirmMsg');
  const confirmPlugins = document.getElementById('confirmPlugins');
  const confirmCancel = document.getElementById('confirmCancel');
  const confirmOk = document.getElementById('confirmOk');
  const reviewChangesBackdrop = document.getElementById('reviewChangesBackdrop');
  const reviewChangesPanel = reviewChangesBackdrop ? reviewChangesBackdrop.querySelector('.review-modal') : null;
  const reviewChangesList = document.getElementById('reviewChangesList');
  const reviewKeepOld = document.getElementById('reviewKeepOld');
  const reviewConfirmChanges = document.getElementById('reviewConfirmChanges');
  const leaveUnsavedBackdrop = document.getElementById('leaveUnsavedBackdrop');
  const leaveUnsavedPanel = leaveUnsavedBackdrop ? leaveUnsavedBackdrop.querySelector('.review-modal') : null;
  const leaveUnsavedKeepOld = document.getElementById('leaveUnsavedKeepOld');
  const leaveUnsavedConfirmNew = document.getElementById('leaveUnsavedConfirmNew');
  const leaveUnsavedListWrap = document.getElementById('leaveUnsavedListWrap');
  const leaveUnsavedList = document.getElementById('leaveUnsavedList');
  const POPUP_ENTER_MS = 170;
  const POPUP_EXIT_MS = 120;
  const prefersReducedMotionGlobal = !!(
    window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
  let pending = null;

  const displayChannelLabel = (channel) => channelLabels[channel] || channel;
  const joinLabels = (labels) => {
    const values = Array.isArray(labels) ? labels.filter(Boolean) : [];
    if (values.length === 0) return 'None';
    if (values.length === 1) return values[0];
    if (values.length === 2) return `${values[0]} and ${values[1]}`;
    return `${values.slice(0, -1).join(', ')}, and ${values[values.length - 1]}`;
  };
  const channelPurposeInfo = {
    channel_dic: 'DIC is the transmitted-light channel used for segmentation/CNN preprocessing and cell-pair geometry.',
    channel_blue: 'Blue is the fluorescence channel used for nucleus-related contours and legacy Blue-channel statistics.',
    channel_red: 'Red is the fluorescence channel used for Red dot contour detection and Red intensity measurements.',
    channel_green: 'Green is the fluorescence channel used for Green intensity, contour, Cen Dot, and merged-dot measurements.',
  };
  let pendingReview = null;
  let pendingLeaveTarget = null;
  let allowWindowUnloadWithoutPrompt = false;
  const bypassReviewForSubmit = new WeakSet();
  const baselineSnapshots = {
    plugins: null,
    advanced: null,
    saving: null,
  };

  const clearPopupAnim = (backdrop, panel) => {
    if (backdrop) backdrop.classList.remove('modal-enter', 'modal-exit');
    if (panel) panel.classList.remove('modal-enter', 'modal-exit');
  };

  const openPopupModal = (backdrop, panel) => {
    if (!backdrop) return;
    clearPopupAnim(backdrop, panel);
    backdrop.style.display = 'flex';
    backdrop.setAttribute('aria-hidden', 'false');
    if (prefersReducedMotionGlobal) return;
    void backdrop.offsetWidth;
    backdrop.classList.add('modal-enter');
    if (panel) panel.classList.add('modal-enter');
    window.setTimeout(() => clearPopupAnim(backdrop, panel), POPUP_ENTER_MS);
  };

  const closePopupModal = (backdrop, panel, onAfterClose = null) => {
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
    if (panel) panel.classList.add('modal-exit');
    backdrop.setAttribute('aria-hidden', 'true');
    window.setTimeout(() => {
      clearPopupAnim(backdrop, panel);
      backdrop.style.display = 'none';
      if (typeof onAfterClose === 'function') onAfterClose();
    }, POPUP_EXIT_MS);
  };

  const setFormNext = (form, nextValue) => {
    if (!form || !nextValue) return;
    let nextInput = form.querySelector('input[name="next"]');
    if (!nextInput) {
      nextInput = document.createElement('input');
      nextInput.type = 'hidden';
      nextInput.name = 'next';
      form.appendChild(nextInput);
    }
    nextInput.value = nextValue;
  };

  const submitFormBypassingReview = (form) => {
    if (!form) return;
    allowWindowUnloadWithoutPrompt = true;
    bypassReviewForSubmit.add(form);
    if (typeof form.requestSubmit === 'function') {
      form.requestSubmit();
    } else {
      form.submit();
    }
  };

  const pluginDependents = (channel) => {
    return [...selectedPlugins].filter((pluginId) => {
      const plugin = pluginMap.get(pluginId);
      return plugin && Array.isArray(plugin.required_channels) && plugin.required_channels.includes(channel);
    });
  };

  const requiredByStatsChannels = () => {
    const required = new Set(alwaysRequired);
    effectiveSelectedPluginIds().forEach((pluginId) => {
      const plugin = pluginMap.get(pluginId);
      if (!plugin || !Array.isArray(plugin.required_channels)) return;
      plugin.required_channels.forEach((channel) => required.add(channel));
    });
    overrides.forEach((channel) => required.delete(channel));
    alwaysRequired.forEach((channel) => required.add(channel));
    return required;
  };

  const selectedPluginLabelsRequiringChannel = (channel) => {
    const labels = [];
    effectiveSelectedPluginIds().forEach((pluginId) => {
      const plugin = pluginMap.get(pluginId);
      if (!plugin || !Array.isArray(plugin.required_channels)) return;
      if (plugin.required_channels.includes(channel)) {
        labels.push(plugin.label || plugin.id);
      }
    });
    return labels;
  };

  const buildChannelRequirementHelpText = (channel, state) => {
    const channelLabel = displayChannelLabel(channel);
    const basePurpose = channelPurposeInfo[channel] || `${channelLabel} channel requirement.`;
    const requiringStats = selectedPluginLabelsRequiringChannel(channel);
    const status = state ? state.helpText : '';
    const selectedStats = requiringStats.length
      ? ` Selected statistics requiring this channel: ${joinLabels(requiringStats)}.`
      : '';
    return `${basePurpose} ${status}${selectedStats}`.trim();
  };

  const enforceExclusiveGroup = (pluginId) => {
    const plugin = pluginMap.get(pluginId);
    if (!plugin || !plugin.exclusive_group) return;
    pluginCatalog.forEach((candidate) => {
      if (
        candidate.id !== pluginId &&
        candidate.exclusive_group &&
        candidate.exclusive_group === plugin.exclusive_group
      ) {
        selectedPlugins.delete(candidate.id);
      }
    });
  };

  const normalizeExclusiveSelections = () => {
    const normalized = new Set();
    const seenGroups = new Set();
    pluginCatalog.forEach((plugin) => {
      if (!selectedPlugins.has(plugin.id)) return;
      if (plugin.exclusive_group && seenGroups.has(plugin.exclusive_group)) return;
      if (plugin.exclusive_group) {
        seenGroups.add(plugin.exclusive_group);
      }
      normalized.add(plugin.id);
    });
    selectedPlugins.clear();
    normalized.forEach((pluginId) => selectedPlugins.add(pluginId));
  };

  const isPluginRequiredBySelection = (pluginId) => {
    for (const selectedId of selectedPlugins) {
      if (selectedId === pluginId) continue;
      const selectedPlugin = pluginMap.get(selectedId);
      if (!selectedPlugin || !Array.isArray(selectedPlugin.required_plugins)) continue;
      if (selectedPlugin.required_plugins.includes(pluginId)) return true;
    }
    return false;
  };

  const applyPluginDependencies = (pluginId) => {
    const plugin = pluginMap.get(pluginId);
    if (!plugin || !Array.isArray(plugin.required_plugins)) return;
    plugin.required_plugins.forEach((dependencyId) => {
      if (!pluginMap.has(dependencyId)) return;
      selectedPlugins.add(dependencyId);
      applyPluginDependencies(dependencyId);
    });
  };

  const normalizeSignalMode = (value) =>
    value === 'nuclear_cell_pair' ? 'nuclear_cell_pair' : 'puncta_distance';

  const isSignalQuantificationEnabled = () =>
    !!(signalQuantificationEnabledInput && signalQuantificationEnabledInput.checked);

  const isNuclearSignalModeActive = () =>
    isSignalQuantificationEnabled() &&
    normalizeSignalMode(signalQuantificationModeInput?.value) === 'nuclear_cell_pair';

  const deriveSignalPluginIds = () => {
    if (!isSignalQuantificationEnabled()) return [];
    if (normalizeSignalMode(signalQuantificationModeInput?.value) === 'nuclear_cell_pair') {
      return ['NuclearCellPairIntensity'];
    }
    const plugins = ['PunctaDistance'];
    if (!punctaContourIntensityEnabledInput || punctaContourIntensityEnabledInput.checked) {
      plugins.push('GreenRedIntensity');
    }
    return plugins;
  };

  const isPluginPausedBySignalMode = (pluginId) =>
    isNuclearSignalModeActive() && pluginId !== 'NuclearCellPairIntensity';

  const effectiveSelectedPluginIds = () => {
    if (isNuclearSignalModeActive()) {
      return new Set(['NuclearCellPairIntensity']);
    }
    return new Set(selectedPlugins);
  };

  const buildSignalModeNotice = (enabled, mode) => {
    if (!enabled) return null;
    if (mode === 'nuclear_cell_pair') {
      return {
        state: 'paused',
        text: 'Nuclear, Cell-Pair Intensity primary mode on. Other stat modules disabled.',
      };
    }
    return {
      state: 'enabled',
      text: 'All other stat modules enabled in Puncta Distance mode.',
    };
  };

  const syncSignalModeNotice = (enabled, mode) => {
    if (!signalModePausedNote) return;
    const notice = buildSignalModeNotice(enabled, mode);
    const state = notice ? notice.state : '';
    const text = notice ? notice.text : '';
    const changed = signalModePausedNote.dataset.state !== state || signalModePausedNote.textContent !== text;
    const isActive = signalModePausedNote.classList.contains('is-active');
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
      signalModePausedNote.classList.add('is-active');
    };
    if (!notice) {
      signalModePausedNote.classList.remove('is-active');
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
      signalModePausedNote.classList.remove('is-active');
      signalModePausedNote.setAttribute('aria-hidden', 'true');
      signalModeNoticeTimer = window.setTimeout(applyNotice, SIGNAL_MODE_NOTICE_FADE_MS);
      return;
    }
    applyNotice();
  };

  const syncSignalSelectedPlugins = () => {
    signalPrimaryPlugins.forEach((pluginId) => selectedPlugins.delete(pluginId));
    deriveSignalPluginIds().forEach((pluginId) => selectedPlugins.add(pluginId));
    if (!signalSelectedPluginsBox) return;
    signalSelectedPluginsBox.innerHTML = '';
    sortByOrder([...selectedPlugins], pluginOrder).forEach((pluginId) => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'selected_plugins';
      input.value = pluginId;
      signalSelectedPluginsBox.appendChild(input);
    });
  };

  const syncSignalQuantificationPanels = () => {
    const enabled = isSignalQuantificationEnabled();
    const mode = normalizeSignalMode(signalQuantificationModeInput?.value);
    if (signalQuantificationInline) {
      signalQuantificationInline.classList.toggle('is-active', enabled);
      signalQuantificationInline.setAttribute('aria-hidden', enabled ? 'false' : 'true');
    }
    if (signalQuantificationModule) {
      signalQuantificationModule.classList.toggle('is-off', !enabled);
    }
    document.querySelectorAll('[data-signal-mode-panel]').forEach((panel) => {
      const active = enabled && panel.dataset.signalModePanel === mode;
      panel.classList.toggle('is-active', active);
      panel.setAttribute('aria-hidden', active ? 'false' : 'true');
    });
    const contourModeInput = document.getElementById('nuclear_cell_pair_contour_mode');
    const contourModeHiddenInput = document.getElementById('nuclear_cell_pair_contour_mode_value');
    const contourModeRow = document.getElementById('nuclearContourModeRow');
    const alternateNucleusActive = !!(alternateNucleusDetectionInput && alternateNucleusDetectionInput.checked);
    if (contourModeHiddenInput && contourModeInput) {
      contourModeHiddenInput.value = contourModeInput.value;
    }
    if (contourModeInput) {
      contourModeInput.disabled = !alternateNucleusActive;
      refreshCustomSelect(contourModeInput);
    }
    if (contourModeRow) {
      contourModeRow.classList.toggle('disabled', !alternateNucleusActive);
    }
    syncSignalModeNotice(enabled, mode);
  };

  const clearOverridesRequiredBySelectedPlugins = () => {
    effectiveSelectedPluginIds().forEach((pluginId) => {
      const plugin = pluginMap.get(pluginId);
      if (!plugin || !Array.isArray(plugin.required_channels)) return;
      plugin.required_channels.forEach((channel) => overrides.delete(channel));
    });
  };

  const syncPluginToggles = () => {
    pluginToggles.forEach((toggle) => {
      const paused = isPluginPausedBySignalMode(toggle.value);
      toggle.checked = selectedPlugins.has(toggle.value) && !paused;
      toggle.disabled = isPluginRequiredBySelection(toggle.value) || paused;
    });
  };

  const syncOverrideInputs = () => {
    if (!overrideBox) return;
    overrideBox.innerHTML = '';
    overrides.forEach((channel) => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'override_required_channels';
      input.value = channel;
      overrideBox.appendChild(input);
    });
  };

  const syncManualRequiredInputs = () => {
    if (!manualRequiredBox) return;
    manualRequiredBox.innerHTML = '';
    sortByOrder([...manualRequiredChannels], channelOrder)
      .filter((channel) => channel && !alwaysRequired.has(channel))
      .forEach((channel) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'manual_required_channels';
        input.value = channel;
        input.dataset.manualRequiredInput = 'true';
        manualRequiredBox.appendChild(input);
      });
  };

  const syncPluginInlineSettings = () => {
    [...document.querySelectorAll('[data-plugin-inline]')].forEach((panel) => {
      const pluginId = panel.dataset.pluginInline;
      const toggle = pluginToggles.find((item) => item.value === pluginId);
      const isActive = !!(toggle && toggle.checked && !isPluginPausedBySignalMode(pluginId));
      panel.classList.toggle('is-active', isActive);
      panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
    });
  };

  const syncWorkflowModuleVisualStates = () => {
    document.querySelectorAll('.plugin').forEach((row) => {
      const toggle = row.querySelector('.plugin-toggle');
      const paused = !!(toggle && isPluginPausedBySignalMode(toggle.value));
      row.classList.toggle('is-paused', paused);
      row.setAttribute('aria-disabled', paused ? 'true' : 'false');
      row.classList.toggle('is-off', !!toggle && !toggle.checked);
    });

    document.querySelectorAll('.row').forEach((row) => {
      const directToggle = row.querySelector(':scope > .sw input[type="checkbox"]');
      const comboToggle = row.querySelector(':scope > .row-line .sw input[type="checkbox"]');
      const toggle = directToggle || comboToggle;
      row.classList.toggle('is-off', !!toggle && !toggle.checked && !row.classList.contains('locked'));
    });
  };

  const resolveChannelState = (channel, statsRequired) => {
    const moduleEnabled = !!(moduleEnabledInput && moduleEnabledInput.checked);
    const enforceAllWavelengths = !!(enforceWavelengthsInput && enforceWavelengthsInput.checked);
    const manualRequired = manualRequiredChannels.has(channel);

    if (alwaysRequired.has(channel)) {
      return {
        summaryLabel: 'Always required',
        summaryRequired: true,
        summaryPaused: false,
        rowChecked: true,
        toggleDisabled: true,
        rowDisabled: true,
        rowLocked: true,
        helpText: 'Always required for segmentation.',
      };
    }

    if (statsRequired.has(channel)) {
      return {
        summaryLabel: 'Required by stats',
        summaryRequired: true,
        summaryPaused: false,
        rowChecked: true,
        toggleDisabled: false,
        rowDisabled: false,
        rowLocked: true,
        helpText: 'Required because selected statistics need this channel.',
      };
    }

    if (moduleEnabled && enforceAllWavelengths) {
      return {
        summaryLabel: 'Required by all-channels',
        summaryRequired: true,
        summaryPaused: false,
        rowChecked: true,
        toggleDisabled: true,
        rowDisabled: true,
        rowLocked: false,
        helpText: 'Required because "Require All Channels" is enabled.',
      };
    }

    if (moduleEnabled && manualRequired) {
      return {
        summaryLabel: 'Required manually',
        summaryRequired: true,
        summaryPaused: false,
        rowChecked: true,
        toggleDisabled: false,
        rowDisabled: false,
        rowLocked: false,
        helpText: 'Manual channel requirement is enabled.',
      };
    }

    if (enforceAllWavelengths) {
      return {
        summaryLabel: 'Paused by all-channels',
        summaryRequired: false,
        summaryPaused: true,
        rowChecked: true,
        toggleDisabled: true,
        rowDisabled: true,
        rowLocked: false,
        helpText: 'Paused because "Require All Channels" is saved while optional metadata checks are OFF.',
      };
    }

    if (manualRequired) {
      return {
        summaryLabel: 'Paused manually',
        summaryRequired: false,
        summaryPaused: true,
        rowChecked: true,
        toggleDisabled: true,
        rowDisabled: true,
        rowLocked: false,
        helpText: 'Paused until optional metadata checks are turned back on.',
      };
    }

    return {
      summaryLabel: 'Optional',
      summaryRequired: false,
      summaryPaused: false,
      rowChecked: false,
      toggleDisabled: !moduleEnabled,
      rowDisabled: !moduleEnabled,
      rowLocked: false,
      helpText: 'Optional.',
    };
  };

  const syncAdvancedValidationUI = () => {
    const moduleEnabled = !!(moduleEnabledInput && moduleEnabledInput.checked);
    const requiredChannels = requiredByStatsChannels();
    const greenDotSplitAllowed = requiredChannels.has('channel_green');
    const redDotSplitAllowed = requiredChannels.has('channel_red');
    let dotSplitEnabled = !!(dotSplitEnabledInput && dotSplitEnabledInput.checked);
    let dotSplitTarget = normalizeDotSplitTarget(
      dotSplitTargetInput && dotSplitTargetInput.value
        ? dotSplitTargetInput.value
        : dotSplitTargetFromFlags(
          truthyHiddenValue(greenDotSplitEnabledInput),
          truthyHiddenValue(redDotSplitEnabledInput)
        )
    );
    dotSplitTarget = fallbackDotSplitTarget(dotSplitTarget, greenDotSplitAllowed, redDotSplitAllowed);
    if (!dotSplitTarget) {
      dotSplitEnabled = false;
    }
    if (dotSplitEnabledInput) {
      dotSplitEnabledInput.disabled = !dotSplitTarget;
      dotSplitEnabledInput.checked = dotSplitEnabled;
    }
    if (dotSplitTargetInput) {
      Array.from(dotSplitTargetInput.options).forEach((option) => {
        option.disabled = !dotSplitTargetAllowed(option.value, greenDotSplitAllowed, redDotSplitAllowed);
      });
      dotSplitTargetInput.disabled = !dotSplitEnabled || !dotSplitTarget;
      if (dotSplitTarget) dotSplitTargetInput.value = dotSplitTarget;
      refreshCustomSelect(dotSplitTargetInput);
    }
    const greenDotSplitActive = dotSplitEnabled && (dotSplitTarget === 'green' || dotSplitTarget === 'both');
    const redDotSplitActive = dotSplitEnabled && (dotSplitTarget === 'red' || dotSplitTarget === 'both');
    setHiddenBoolValue(greenDotSplitEnabledInput, greenDotSplitActive);
    setHiddenBoolValue(redDotSplitEnabledInput, redDotSplitActive);
    if (dotSplitRow) {
      dotSplitRow.classList.toggle('disabled', !dotSplitTarget);
      dotSplitRow.classList.toggle('is-off', !dotSplitEnabled);
    }
    if (dotSplitTargetRow) {
      dotSplitTargetRow.classList.toggle('is-active', dotSplitEnabled && !!dotSplitTarget);
      dotSplitTargetRow.setAttribute('aria-hidden', dotSplitEnabled && dotSplitTarget ? 'false' : 'true');
    }
    [
      [enforceLayerCountInput, advancedLayerCheckRow],
      [enforceWavelengthsInput, advancedWavelengthCheckRow],
    ].forEach(([input, row]) => {
      if (input) input.disabled = !moduleEnabled;
      if (row) row.classList.toggle('disabled', !moduleEnabled);
    });

    if (greenDotSplitModeRow) {
      greenDotSplitModeRow.classList.toggle('is-active', dotSplitEnabled && !!dotSplitTarget);
      greenDotSplitModeRow.classList.toggle('disabled', !greenDotSplitActive);
      greenDotSplitModeRow.setAttribute('aria-hidden', dotSplitEnabled && dotSplitTarget ? 'false' : 'true');
    }
    if (greenDotSplitModeInput) {
      greenDotSplitModeInput.disabled = !greenDotSplitActive;
      refreshCustomSelect(greenDotSplitModeInput);
    }
    if (redDotSplitModeRow) {
      redDotSplitModeRow.classList.toggle('is-active', dotSplitEnabled && !!dotSplitTarget);
      redDotSplitModeRow.classList.toggle('disabled', !redDotSplitActive);
      redDotSplitModeRow.setAttribute('aria-hidden', dotSplitEnabled && dotSplitTarget ? 'false' : 'true');
    }
    if (redDotSplitModeInput) {
      redDotSplitModeInput.disabled = !redDotSplitActive;
      refreshCustomSelect(redDotSplitModeInput);
    }

    if (enforceLayerCountStateInput && enforceLayerCountInput) {
      enforceLayerCountStateInput.value = enforceLayerCountInput.checked ? '1' : '0';
    }
    if (enforceWavelengthsStateInput && enforceWavelengthsInput) {
      enforceWavelengthsStateInput.value = enforceWavelengthsInput.checked ? '1' : '0';
    }

    if (advancedOptionalChecksGroup) {
      advancedOptionalChecksGroup.classList.toggle('is-disabled', !moduleEnabled);
    }

    if (!advancedOptionalChecksNote) return;
    const prevState = advancedOptionalChecksNote.dataset.state || '';
    const prevText = advancedOptionalChecksNote.textContent || '';
    const nextState = moduleEnabled ? 'on' : 'off';
    const nextText = moduleEnabled
      ? 'Optional checks below are ON. Saved optional selections are active; required checks from selected statistics are still enforced.'
      : 'Optional checks below are OFF. Saved optional selections are paused; required checks from selected statistics are still enforced.';
    const shouldAnimate = prevState !== nextState || prevText !== nextText;

    advancedOptionalChecksNote.classList.remove('on', 'off');
    advancedOptionalChecksNote.classList.add(nextState);
    advancedOptionalChecksNote.dataset.state = nextState;
    if (shouldAnimate) {
      advancedOptionalChecksNote.classList.remove('reveal');
      void advancedOptionalChecksNote.offsetWidth;
      advancedOptionalChecksNote.classList.add('reveal');
    }
    advancedOptionalChecksNote.textContent = nextText;
  };

  const syncChannelSummary = (statsRequired) => {
    [...document.querySelectorAll('[data-req-row][data-summary-scope]')].forEach((row) => {
      const channel = row.dataset.reqRow;
      const statusEl = row.querySelector('.channel-pill-state');
      const wasRequired = row.classList.contains('required');
      const wasPaused = row.classList.contains('paused');
      const previousLabel = statusEl ? statusEl.textContent.trim() : '';
      const state = resolveChannelState(channel, statsRequired);
      const label = state.summaryLabel;
      const required = state.summaryRequired;
      const paused = state.summaryPaused;
      const changed = wasRequired !== required || wasPaused !== paused || previousLabel !== label;
      if (changed) row.classList.add('status-changing');
      row.classList.toggle('required', required);
      row.classList.toggle('paused', paused);
      if (statusEl) {
        if (changed) {
          statusEl.classList.add('state-enter');
          void statusEl.offsetWidth;
          statusEl.textContent = label;
          requestAnimationFrame(() => {
            requestAnimationFrame(() => statusEl.classList.remove('state-enter'));
          });
        } else {
          statusEl.textContent = label;
        }
      }
      if (changed) {
        window.setTimeout(() => row.classList.remove('status-changing'), 190);
      }
    });
  };

  const syncRows = () => {
    syncSignalSelectedPlugins();
    syncSignalQuantificationPanels();
    const statsRequired = requiredByStatsChannels();
    channelToggles.forEach((toggle) => {
      const channel = toggle.dataset.channel;
      if (!channel) return;
      const row = document.querySelector(`[data-ch-row=\"${channel}\"]`);
      const help = document.querySelector(`[data-ch-help=\"${channel}\"]`);
      const state = resolveChannelState(channel, statsRequired);

      toggle.checked = state.rowChecked;
      toggle.disabled = state.toggleDisabled;
      if (row) {
        row.classList.toggle('locked', state.rowLocked);
        row.classList.toggle('disabled', state.rowDisabled && !state.rowLocked);
      }
      if (help) help.textContent = buildChannelRequirementHelpText(channel, state);
    });
    syncOverrideInputs();
    syncManualRequiredInputs();
    syncChannelSummary(statsRequired);
    syncPluginInlineSettings();
    syncAdvancedValidationUI();
    syncWorkflowModuleVisualStates();
  };

  const closeConfirm = () => {
    pending = null;
    if (!confirmBack) return;
    confirmBack.style.display = 'none';
    confirmBack.setAttribute('aria-hidden', 'true');
  };

  const openConfirm = (channel, deps) => {
    pending = { channel, deps };
    if (!confirmBack || !confirmMsg || !confirmPlugins) return;
    confirmMsg.textContent = `Are you sure you want to untoggle ${channel}? These selected statistics require it.`;
    confirmPlugins.innerHTML = '';
    deps.map((id) => pluginMap.get(id)?.label || id).forEach((label) => {
      const li = document.createElement('li');
      li.textContent = label;
      confirmPlugins.appendChild(li);
    });
    confirmBack.style.display = 'flex';
    confirmBack.setAttribute('aria-hidden', 'false');
  };

  pluginToggles.forEach((toggle) => {
    toggle.addEventListener('change', () => {
      if (toggle.checked) {
        selectedPlugins.add(toggle.value);
        enforceExclusiveGroup(toggle.value);
        applyPluginDependencies(toggle.value);
        clearOverridesRequiredBySelectedPlugins();
      } else if (isPluginRequiredBySelection(toggle.value)) {
        toggle.checked = true;
        return;
      } else {
        selectedPlugins.delete(toggle.value);
      }
      syncPluginToggles();
      syncRows();
    });
  });

  [
    signalQuantificationEnabledInput,
    signalQuantificationModeInput,
    punctaContourIntensityEnabledInput,
    alternateNucleusDetectionInput,
    document.getElementById('puncta_line_mode'),
    document.getElementById('nuclear_cell_pair_mode'),
    document.getElementById('nuclear_cell_pair_contour_mode'),
  ].forEach((input) => {
    if (!input) return;
    input.addEventListener('change', () => {
      syncSignalSelectedPlugins();
      clearOverridesRequiredBySelectedPlugins();
      syncPluginToggles();
      syncRows();
    });
  });

  channelToggles.forEach((toggle) => {
    toggle.addEventListener('change', () => {
      const channel = toggle.dataset.channel;
      if (!channel || alwaysRequired.has(channel)) {
        toggle.checked = true;
        return;
      }
      const statsRequired = requiredByStatsChannels();
      const state = resolveChannelState(channel, statsRequired);
      if (state.rowDisabled) {
        syncRows();
        return;
      }
      if (!toggle.checked) {
        const deps = pluginDependents(channel);
        if (deps.length) {
          toggle.checked = true;
          openConfirm(channel, deps);
          return;
        }
        manualRequiredChannels.delete(channel);
      } else {
        manualRequiredChannels.add(channel);
      }
      overrides.delete(channel);
      syncRows();
    });
  });

  document.querySelectorAll('.row > .sw input[type="checkbox"], .row-line > .sw input[type="checkbox"]').forEach((toggle) => {
    toggle.addEventListener('change', syncWorkflowModuleVisualStates);
  });

  if (confirmCancel) {
    confirmCancel.addEventListener('click', () => {
      closeConfirm();
      syncRows();
    });
  }
  if (confirmOk) {
    confirmOk.addEventListener('click', () => {
      if (!pending) return;
      pending.deps.forEach((pluginId) => selectedPlugins.delete(pluginId));
      overrides.add(pending.channel);
      manualRequiredChannels.delete(pending.channel);
      syncPluginToggles();
      const toggle = document.querySelector(`.channel-toggle[data-channel=\"${pending.channel}\"]`);
      if (toggle) toggle.checked = false;
      closeConfirm();
      syncRows();
    });
  }

  if (confirmBack) {
    confirmBack.addEventListener('click', (event) => {
      if (event.target === confirmBack) {
        closeConfirm();
        syncRows();
      }
    });
  }
  if (reviewKeepOld) {
    reviewKeepOld.addEventListener('click', () => {
      if (!pendingReview || typeof pendingReview.restore !== 'function') {
        closeReviewModal();
        return;
      }
      const restore = pendingReview.restore;
      closeReviewModal(() => restore());
    });
  }
  if (reviewConfirmChanges) {
    reviewConfirmChanges.addEventListener('click', () => {
      if (!pendingReview || !pendingReview.form) {
        closeReviewModal();
        return;
      }
      const form = pendingReview.form;
      closeReviewModal(() => {
        submitFormBypassingReview(form);
      });
    });
  }
  if (reviewChangesBackdrop) {
    reviewChangesBackdrop.addEventListener('click', (event) => {
      if (event.target === reviewChangesBackdrop) {
        closeReviewModal();
      }
    });
  }
  if (leaveUnsavedConfirmNew) {
    leaveUnsavedConfirmNew.addEventListener('click', () => {
      const intent = pendingLeaveTarget;
      closeLeaveUnsavedModal(() => {
        if (!intent) return;
        if (intent.mode === 'section') {
          const sourceSection = intent.sourceSection;
          const targetSection = intent.targetSection;
          const form = sectionFormMap[sourceSection];
          if (form && targetSection) {
            setFormNext(form, sectionRedirectPath(targetSection));
            submitFormBypassingReview(form);
          } else if (targetSection) {
            showSection(targetSection);
          }
          return;
        }
        if (intent.mode !== 'link' || !intent.href) return;
        const sectionToSave = intent.sectionToSave;
        if (!sectionToSave) {
          allowWindowUnloadWithoutPrompt = true;
          window.location.assign(intent.href);
          return;
        }
        const form = sectionFormMap[sectionToSave];
        if (!form) {
          allowWindowUnloadWithoutPrompt = true;
          window.location.assign(intent.href);
          return;
        }
        setFormNext(form, intent.href);
        submitFormBypassingReview(form);
      });
    });
  }
  if (leaveUnsavedKeepOld) {
    leaveUnsavedKeepOld.addEventListener('click', () => {
      const intent = pendingLeaveTarget;
      closeLeaveUnsavedModal(() => {
        if (!intent) return;
        if (intent.mode === 'section') {
          const sourceSection = intent.sourceSection;
          const targetSection = intent.targetSection;
          if (sourceSection === 'plugins' && baselineSnapshots.plugins) {
            restorePluginSnapshot(baselineSnapshots.plugins);
          } else if (sourceSection === 'advanced' && baselineSnapshots.advanced) {
            restoreAdvancedSnapshot(baselineSnapshots.advanced);
          } else if (sourceSection === 'saving' && baselineSnapshots.saving) {
            restoreSavingSnapshot(baselineSnapshots.saving);
          }
          if (targetSection) showSection(targetSection);
          return;
        }
        if (intent.mode === 'link' && intent.href) {
          allowWindowUnloadWithoutPrompt = true;
          window.location.assign(intent.href);
        }
      });
    });
  }
  if (leaveUnsavedBackdrop) {
    leaveUnsavedBackdrop.addEventListener('click', (event) => {
      if (event.target === leaveUnsavedBackdrop) {
        closeLeaveUnsavedModal();
      }
    });
  }
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (leaveUnsavedBackdrop && leaveUnsavedBackdrop.style.display === 'flex') {
      closeLeaveUnsavedModal();
      return;
    }
    if (reviewChangesBackdrop && reviewChangesBackdrop.style.display === 'flex') {
      closeReviewModal();
      return;
    }
    if (confirmBack && confirmBack.style.display === 'flex') {
      closeConfirm();
      syncRows();
    }
  });

  const prefsScaleInput = document.getElementById('microns_per_pixel');
  const prefsScaleLive = document.getElementById('prefsScaleLive');
  const prefsScaleExample = document.getElementById('prefsScaleExample');
  const prefsScaleModeStatus = document.getElementById('prefsScaleModeStatus');
  const redWidthInput = document.getElementById('puncta_line_width');
  const redWidthUnit = document.getElementById('puncta_line_width_unit');
  const cenDotDistanceInput = document.getElementById('cen_dot_distance');
  const cenDotDistanceUnit = document.getElementById('cen_dot_distance_unit');
  const cenDotProximityRadiusInput = document.getElementById('cen_dot_proximity_radius');
  const cenDotProximityRadiusUnit = document.getElementById('cen_dot_proximity_radius_unit');
  const biorientationRedMinDistanceInput = document.getElementById('biorientation_red_min_distance');
  const biorientationRedMinDistanceUnit = document.getElementById('biorientation_red_min_distance_unit');
  const biorientationRedMaxDistanceInput = document.getElementById('biorientation_red_max_distance');
  const biorientationRedMaxDistanceUnit = document.getElementById('biorientation_red_max_distance_unit');
  const biorientationCollinearityThresholdInput = document.getElementById('biorientation_collinearity_threshold');
  const punctaLineModeInput = document.getElementById('puncta_line_mode');
  const nuclearCellPairModeInput = document.getElementById('nuclear_cell_pair_mode');
  const nuclearCellPairContourModeInput = document.getElementById('nuclear_cell_pair_contour_mode');
  const legacyNuclearCellPairInput = document.getElementById('use_legacy_nuclear_cell_pair_pipeline');
  const useMetadataScaleInput = document.getElementById('use_metadata_scale');
  const useMetadataChannelOrderInput = document.getElementById('use_metadata_channel_order');
  const prefsChannelOrderModeStatus = document.getElementById('prefsChannelOrderModeStatus');
  const prefsFallbackChannelOrderBar = document.getElementById('prefsFallbackChannelOrder');
  const prefsFallbackChannelOrderModeLabel = document.getElementById('prefsFallbackChannelOrderModeLabel');
  const prefsFallbackChannelOrderBack = document.getElementById('prefsFallbackChannelOrderBack');
  const prefsFallbackChannelOrderReset = document.getElementById('prefsFallbackChannelOrderReset');
  const moduleEnabledInput = document.getElementById('module_enabled');
  const enforceLayerCountInput = document.getElementById('enforce_layer_count');
  const enforceWavelengthsInput = document.getElementById('enforce_wavelengths');
  const enforceLayerCountStateInput = document.getElementById('enforce_layer_count_state');
  const enforceWavelengthsStateInput = document.getElementById('enforce_wavelengths_state');
  const advancedOptionalChecksNote = document.getElementById('advancedOptionalChecksNote');
  const advancedOptionalChecksGroup = document.getElementById('advancedOptionalChecksGroup');
  const advancedLayerCheckRow = document.getElementById('advancedLayerCheckRow');
  const advancedWavelengthCheckRow = document.getElementById('advancedWavelengthCheckRow');
  const showLegacyPluginsInput = document.getElementById('show_legacy_plugins');
  const greenContourFilterEnabledInput = document.getElementById('green_contour_filter_enabled');
  const dotSplitEnabledInput = document.getElementById('dot_split_enabled');
  const dotSplitTargetInput = document.getElementById('dot_split_target');
  const dotSplitRow = document.getElementById('dotSplitRow');
  const dotSplitTargetRow = document.getElementById('dotSplitTargetRow');
  const greenDotSplitEnabledInput = document.getElementById('green_dot_split_enabled');
  const greenDotSplitModeInput = document.getElementById('green_dot_split_mode');
  const greenDotSplitModeRow = document.getElementById('greenDotSplitModeRow');
  const redDotSplitEnabledInput = document.getElementById('red_dot_split_enabled');
  const redDotSplitModeInput = document.getElementById('red_dot_split_mode');
  const redDotSplitModeRow = document.getElementById('redDotSplitModeRow');
  const alternateRedDetectionInput = alternateNucleusDetectionInput;
  const autoSaveExperimentsInput = document.getElementById('auto_save_experiments');
  const showSavedFileChannelsInput = document.getElementById('show_saved_file_channels');
  const showSavedFileScalesInput = document.getElementById('show_saved_file_scales');
  const sidebarStartsOpenInput = document.getElementById('sidebar_starts_open');
  const defaultPunctaSourceContourCountFilterInput = document.getElementById('default_puncta_source_contour_count_filter');
  [moduleEnabledInput, enforceLayerCountInput, enforceWavelengthsInput].forEach((input) => {
    if (!input) return;
    input.addEventListener('change', syncRows);
  });
  if (dotSplitEnabledInput) {
    dotSplitEnabledInput.addEventListener('change', syncRows);
  }
  if (dotSplitTargetInput) {
    dotSplitTargetInput.addEventListener('change', syncRows);
  }
  const pluginOrder = pluginCatalog.map((plugin) => plugin.id);
  const channelOrder = payload.channel_order || [];
  const defaultFallbackChannelOrder = ['DIC', 'channel_blue', 'channel_green', 'channel_red'];

  const sanitizePositive = (value, fallback) => {
    const parsed = Number(value);
    if (Number.isFinite(parsed) && parsed > 0) return parsed;
    return fallback;
  };

  const normalizeLengthUnit = (value) => (value === 'um' ? 'um' : 'px');
  const normalizeGreenDotSplitMode = (value) => (value === 'aggressive' ? 'aggressive' : 'balanced');
  const normalizeRedDotSplitMode = (value) => (value === 'aggressive' ? 'aggressive' : 'balanced');
  const normalizeNuclearContourMode = (value) => (value === 'aggressive' ? 'aggressive' : 'balanced');
  const normalizePunctaSourceContourCountFilter = (value) => {
    const raw = String(value ?? '').trim().toLowerCase();
    if (raw === 'exactly_1' || raw === '1') return 'exactly_1';
    if (raw === 'exactly_2' || raw === '2') return 'exactly_2';
    return 'all';
  };
  const punctaSourceContourCountFilterLabel = (value) => {
    const normalized = normalizePunctaSourceContourCountFilter(value);
    if (normalized === 'exactly_1') return 'Exactly 1 source contour';
    if (normalized === 'exactly_2') return 'Exactly 2 source contours';
    return 'All cells';
  };
  const normalizeDotSplitTarget = (value) => {
    if (value === 'red' || value === 'green' || value === 'both') return value;
    return 'both';
  };
  const formatLengthUnitLabel = (value) => (normalizeLengthUnit(value) === 'um' ? '\u00b5m' : 'px');
  const truthyHiddenValue = (inputEl) => {
    const raw = String(inputEl ? inputEl.value : '').trim().toLowerCase();
    return raw === '1' || raw === 'true' || raw === 'on' || raw === 'yes';
  };
  const setHiddenBoolValue = (inputEl, enabled) => {
    if (inputEl) inputEl.value = enabled ? '1' : '0';
  };
  const dotSplitTargetFromFlags = (greenEnabled, redEnabled) => {
    if (greenEnabled && redEnabled) return 'both';
    if (greenEnabled) return 'green';
    if (redEnabled) return 'red';
    return 'both';
  };
  const dotSplitTargetLabel = (target) => {
    if (target === 'red') return 'Red';
    if (target === 'green') return 'Green';
    return 'Both';
  };

  const normalizeChannelOrder = (order) => {
    const values = Array.isArray(order) ? order.filter(Boolean) : [];
    const expectedOrder = channelOrder.length ? channelOrder : defaultFallbackChannelOrder;
    if (values.length !== expectedOrder.length) return [...defaultFallbackChannelOrder];
    const expected = new Set(expectedOrder);
    const seen = new Set();
    const normalized = [];
    values.forEach((value) => {
      if (!expected.has(value) || seen.has(value)) return;
      seen.add(value);
      normalized.push(value);
    });
    return normalized.length === expectedOrder.length ? normalized : [...defaultFallbackChannelOrder];
  };

  const channelOrderFromBar = (bar) =>
    normalizeChannelOrder([...((bar || {}).querySelectorAll?.('[data-channel-role]') || [])].map((chip) => chip.dataset.channelRole));

  const channelOrderLabelList = (order) =>
    normalizeChannelOrder(order).map((channel) => displayChannelLabel(channel)).join(', ');

  const sameChannelOrder = (first, second) =>
    JSON.stringify(normalizeChannelOrder(first)) === JSON.stringify(normalizeChannelOrder(second));

  const channelOrderAnimationMs = 220;
  const channelOrderActionLockMs = 260;
  const fallbackChannelOrderUndoStack = [];
  let fallbackChannelOrderActionLocked = false;

  const syncScaleMetadataStatus = (animate = false) => {
    if (!prefsScaleModeStatus || !useMetadataScaleInput) return;
    const metadataEnabled = useMetadataScaleInput.checked;
    const nextText = metadataEnabled ? 'Metadata mode enabled' : 'Fallback-only mode enabled';
    let changed = false;
    prefsScaleModeStatus.classList.toggle('is-metadata-enabled', metadataEnabled);
    prefsScaleModeStatus.classList.toggle('is-metadata-off', !metadataEnabled);
    if (prefsScaleModeStatus.textContent.trim() !== nextText) {
      prefsScaleModeStatus.textContent = nextText;
      changed = true;
    }
    if (!animate || !changed) return;
    prefsScaleModeStatus.classList.remove('is-fading-down');
    void prefsScaleModeStatus.offsetWidth;
    prefsScaleModeStatus.classList.add('is-fading-down');
  };

  const syncChannelOrderStatus = (animate = false) => {
    if (!useMetadataChannelOrderInput) return;
    const metadataEnabled = useMetadataChannelOrderInput.checked;
    const nextStatusText = metadataEnabled ? 'Metadata mode enabled' : 'Fallback-only mode enabled';
    const nextModeText = metadataEnabled ? 'Backup order' : 'Primary order';
    let changed = false;
    if (prefsChannelOrderModeStatus) {
      prefsChannelOrderModeStatus.classList.toggle('is-metadata-enabled', metadataEnabled);
      prefsChannelOrderModeStatus.classList.toggle('is-metadata-off', !metadataEnabled);
      if (prefsChannelOrderModeStatus.textContent.trim() !== nextStatusText) {
        prefsChannelOrderModeStatus.textContent = nextStatusText;
        changed = true;
      }
    }
    if (prefsFallbackChannelOrderModeLabel) {
      prefsFallbackChannelOrderModeLabel.classList.toggle('is-backup', metadataEnabled);
      prefsFallbackChannelOrderModeLabel.classList.toggle('is-primary', !metadataEnabled);
      if (prefsFallbackChannelOrderModeLabel.textContent !== nextModeText) {
        prefsFallbackChannelOrderModeLabel.textContent = nextModeText;
        changed = true;
      }
    }
    if (!animate || !changed) return;
    [prefsChannelOrderModeStatus, prefsFallbackChannelOrderModeLabel].forEach((element) => {
      if (!element) return;
      element.classList.remove('is-fading-down');
      void element.offsetWidth;
      element.classList.add('is-fading-down');
    });
  };

  const orderChannelBar = (bar, order, options = {}) => {
    if (!bar) return;
    const normalized = normalizeChannelOrder(order);
    const chipsByChannel = new Map(
      [...bar.querySelectorAll('[data-channel-role]')].map((chip) => [chip.dataset.channelRole, chip])
    );
    const shouldAnimate = options.animate
      && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const firstRects = shouldAnimate
      ? new Map([...chipsByChannel].map(([channel, chip]) => [channel, chip.getBoundingClientRect()]))
      : null;
    normalized.forEach((channel) => {
      const chip = chipsByChannel.get(channel);
      if (chip) bar.appendChild(chip);
    });
    if (!shouldAnimate) return;
    normalized.forEach((channel) => {
      const chip = chipsByChannel.get(channel);
      const firstRect = firstRects.get(channel);
      if (!chip || !firstRect) return;
      const lastRect = chip.getBoundingClientRect();
      const deltaX = firstRect.left - lastRect.left;
      const deltaY = firstRect.top - lastRect.top;
      const moved = Math.abs(deltaX) >= 0.5 || Math.abs(deltaY) >= 0.5;
      const startTransform = moved ? `translate(${deltaX}px, ${deltaY}px)` : 'translate(0, 0)';
      if (typeof Element !== 'undefined' && typeof Element.prototype.animate === 'function') {
        chip.animate(
          [
            { transform: startTransform, opacity: moved ? 0.64 : 0.82 },
            { transform: 'translate(0, 0)', opacity: 1 },
          ],
          { duration: channelOrderAnimationMs, easing: 'cubic-bezier(0.2, 0, 0.2, 1)' }
        );
        return;
      }
      chip.style.transition = 'none';
      chip.style.transform = startTransform;
      chip.style.opacity = moved ? '0.64' : '0.82';
      chip.style.willChange = 'transform, opacity';
      chip.getBoundingClientRect();
      window.requestAnimationFrame(() => {
        chip.style.transition = `transform ${channelOrderAnimationMs}ms cubic-bezier(0.2, 0, 0.2, 1), opacity ${channelOrderAnimationMs}ms ease`;
        chip.style.transform = 'translate(0, 0)';
        chip.style.opacity = '1';
      });
      window.setTimeout(() => {
        chip.style.transition = '';
        chip.style.transform = '';
        chip.style.opacity = '';
        chip.style.willChange = '';
      }, channelOrderAnimationMs + 60);
    });
  };

  const syncFallbackChannelOrderActions = () => {
    const currentOrder = channelOrderFromBar(prefsFallbackChannelOrderBar);
    if (prefsFallbackChannelOrderBack) {
      prefsFallbackChannelOrderBack.disabled = fallbackChannelOrderActionLocked || fallbackChannelOrderUndoStack.length === 0;
    }
    if (prefsFallbackChannelOrderReset) {
      const baselineOrder = baselineSnapshots.plugins?.fallbackChannelOrder || defaultFallbackChannelOrder;
      prefsFallbackChannelOrderReset.disabled = fallbackChannelOrderActionLocked || sameChannelOrder(currentOrder, baselineOrder);
    }
  };

  const lockFallbackChannelOrderActions = () => {
    fallbackChannelOrderActionLocked = true;
    syncFallbackChannelOrderActions();
    window.setTimeout(() => {
      fallbackChannelOrderActionLocked = false;
      syncFallbackChannelOrderActions();
    }, channelOrderActionLockMs);
  };

  const applyFallbackChannelOrder = (order, options = {}) => {
    orderChannelBar(prefsFallbackChannelOrderBar, order, { animate: options.animate });
    if (options.clearHistory) {
      fallbackChannelOrderUndoStack.length = 0;
    }
    syncFallbackChannelOrderActions();
  };

  const pushFallbackChannelOrderUndo = (order) => {
    fallbackChannelOrderUndoStack.push(normalizeChannelOrder(order));
    if (fallbackChannelOrderUndoStack.length > 20) {
      fallbackChannelOrderUndoStack.shift();
    }
  };

  const setupChannelOrderDrag = (bar) => {
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
        syncFallbackChannelOrderActions();
      },
    });
  };
  const dotSplitTargetAllowed = (target, greenAllowed, redAllowed) => {
    if (target === 'green') return greenAllowed;
    if (target === 'red') return redAllowed;
    return greenAllowed && redAllowed;
  };
  const fallbackDotSplitTarget = (preferredTarget, greenAllowed, redAllowed) => {
    const target = normalizeDotSplitTarget(preferredTarget);
    if (dotSplitTargetAllowed(target, greenAllowed, redAllowed)) return target;
    if (greenAllowed && redAllowed) return 'both';
    if (greenAllowed) return 'green';
    if (redAllowed) return 'red';
    return '';
  };
  function refreshCustomSelect(nativeSelect) {
    if (nativeSelect) {
      nativeSelect.dispatchEvent(new Event('cytocv:custom-select-refresh'));
    }
  }

  // Custom styled dropdowns to replace native <select> elements
  const openCustomDropdowns = new Set();

  function closeAllCustomDropdowns(except = null) {
    openCustomDropdowns.forEach((ctrl) => {
      if (ctrl !== except) ctrl.close();
    });
  }

  document.addEventListener('click', (event) => {
    if (!event.target.closest('.length-unit-dropdown')) {
      closeAllCustomDropdowns();
    }
  });

  function buildCustomSelect(nativeSelect) {
    nativeSelect.style.display = 'none';

    const root = document.createElement('div');
    root.className = 'length-unit-dropdown';

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'length-unit-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');

    const labelSpan = document.createElement('span');
    labelSpan.textContent = nativeSelect.options[nativeSelect.selectedIndex]?.text ?? '';

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

    const optionButtons = [];
    const syncFromNative = () => {
      const selectedOption = nativeSelect.options[nativeSelect.selectedIndex];
      labelSpan.textContent = selectedOption ? selectedOption.text : '';
      trigger.disabled = !!nativeSelect.disabled;
      root.classList.toggle('is-disabled', !!nativeSelect.disabled);
      optionButtons.forEach((btn, idx) => {
        const opt = nativeSelect.options[idx];
        const disabled = !!nativeSelect.disabled || !!(opt && opt.disabled);
        btn.disabled = disabled;
        btn.classList.toggle('is-disabled', disabled);
        btn.setAttribute('aria-disabled', disabled ? 'true' : 'false');
        btn.classList.toggle('is-selected', !!opt && opt.value === nativeSelect.value);
      });
    };
    Array.from(nativeSelect.options).forEach((opt) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'length-unit-option';
      btn.setAttribute('role', 'option');
      btn.textContent = opt.text;
      btn.dataset.value = opt.value;
      if (opt.selected) btn.classList.add('is-selected');
      btn.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (nativeSelect.disabled || opt.disabled) return;
        nativeSelect.value = opt.value;
        nativeSelect.dispatchEvent(new Event('change', { bubbles: true }));
        ctrl.close();
      });
      menu.appendChild(btn);
      optionButtons.push(btn);
    });

    const ctrl = {
      close() {
        root.classList.remove('open');
        menu.hidden = true;
        trigger.setAttribute('aria-expanded', 'false');
        [root.closest('.row-sub'), root.closest('.row'), root.closest('.plugin')].forEach((el) => {
          if (el) el.classList.remove('mode-menu-open');
        });
        openCustomDropdowns.delete(ctrl);
      },
      open() {
        closeAllCustomDropdowns(ctrl);
        root.classList.add('open');
        menu.hidden = false;
        trigger.setAttribute('aria-expanded', 'true');
        [root.closest('.row-sub'), root.closest('.row'), root.closest('.plugin')].forEach((el) => {
          if (el) el.classList.add('mode-menu-open');
        });
        openCustomDropdowns.add(ctrl);
      },
    };

    trigger.addEventListener('click', (event) => {
      event.stopPropagation();
      if (root.classList.contains('open')) ctrl.close();
      else ctrl.open();
    });

    nativeSelect.parentNode.insertBefore(root, nativeSelect.nextSibling);
    nativeSelect.addEventListener('change', syncFromNative);
    nativeSelect.addEventListener('cytocv:custom-select-refresh', syncFromNative);
    syncFromNative();
    return ctrl;
  }

  document.querySelectorAll('.length-input-group select, .mode-select-group select').forEach(buildCustomSelect);

  const formatNumeric = (value, precision) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return '0';
    return parsed.toFixed(precision).replace(/\.?0+$/, '');
  };

  const valueOrEmpty = (inputEl) => (inputEl ? String(inputEl.value ?? '').trim() : '');

  const normalizeNumericString = (rawValue) => {
    const raw = String(rawValue ?? '').trim();
    if (!raw) return '';
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return raw;
    return formatNumeric(parsed, 8);
  };

  const sortByOrder = (items, order) => {
    const rank = new Map(order.map((value, idx) => [value, idx]));
    return [...items].sort((a, b) => {
      const aRank = rank.has(a) ? rank.get(a) : Number.MAX_SAFE_INTEGER;
      const bRank = rank.has(b) ? rank.get(b) : Number.MAX_SAFE_INTEGER;
      if (aRank !== bRank) return aRank - bRank;
      return String(a).localeCompare(String(b));
    });
  };

  const asOnOff = (value) => (value ? 'On' : 'Off');
  const pluginLabel = (pluginId) => pluginMap.get(pluginId)?.label || pluginId;
  const nucleusModeLabel = (value) =>
    value === 'red_nucleus'
      ? 'Red Nucleus (Measure Green)'
      : 'Green Nucleus (Measure Red)';
  const nuclearContourModeLabel = (value) =>
    normalizeNuclearContourMode(value) === 'aggressive' ? 'Aggressive' : 'Balanced';
  const signalModeLabel = (value) =>
    normalizeSignalMode(value) === 'nuclear_cell_pair'
      ? 'Nuclear, Cell-Pair Intensity'
      : 'Puncta Distance';

  const convertLengthValueToUnit = (value, fromUnit, toUnit, umPerPx) => {
    const sourceUnit = normalizeLengthUnit(fromUnit);
    const targetUnit = normalizeLengthUnit(toUnit);
    if (sourceUnit === targetUnit) return Number(value);
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || umPerPx <= 0) return Number.NaN;
    if (sourceUnit === 'px' && targetUnit === 'um') return numeric * umPerPx;
    if (sourceUnit === 'um' && targetUnit === 'px') return numeric / umPerPx;
    return numeric;
  };

  const syncLengthInputConstraints = (inputEl, unit, minimumPx, minimumUm) => {
    if (!inputEl) return;
    const normalized = normalizeLengthUnit(unit);
    if (normalized === 'um') {
      inputEl.step = '0.01';
      inputEl.min = String(minimumUm);
      return;
    }
    inputEl.step = '1';
    inputEl.min = String(minimumPx);
  };

  const parseLengthValue = (inputEl, unit, fallback, minimum) => {
    if (!inputEl) return fallback;
    const normalized = normalizeLengthUnit(unit);
    const raw = String(inputEl.value ?? '').trim();
    const parsed = normalized === 'um' ? Number.parseFloat(raw) : Number.parseInt(raw, 10);
    if (!Number.isFinite(parsed) || parsed < minimum) return fallback;
    if (normalized === 'px') return Math.round(parsed);
    return parsed;
  };

  const convertUmToPixels = (valueUm, umPerPx, minimumPx = 1) => {
    const umValue = Number(valueUm);
    if (!Number.isFinite(umValue) || umValue <= 0 || umPerPx <= 0) return 0;
    return Math.max(minimumPx, Math.round(umValue / umPerPx));
  };

  const applyUnitConversion = (inputEl, unitEl, options) => {
    if (!inputEl || !unitEl) return;
    const previousUnit = normalizeLengthUnit(unitEl.dataset.prevUnit || unitEl.value);
    const nextUnit = normalizeLengthUnit(unitEl.value);
    syncLengthInputConstraints(inputEl, nextUnit, options.minimumPx, options.minimumUm);
    if (previousUnit === nextUnit) {
      unitEl.dataset.prevUnit = nextUnit;
      return;
    }
    const umPerPx = sanitizePositive(prefsScaleInput ? prefsScaleInput.value : 0.1, 0.1);
    const currentValue = parseLengthValue(
      inputEl,
      previousUnit,
      options.defaultForUnit(previousUnit, umPerPx),
      options.minimumForUnit(previousUnit)
    );
    let converted = convertLengthValueToUnit(currentValue, previousUnit, nextUnit, umPerPx);
    if (!Number.isFinite(converted)) {
      converted = options.defaultForUnit(nextUnit, umPerPx);
    }
    if (converted < options.minimumForUnit(nextUnit)) {
      converted = options.defaultForUnit(nextUnit, umPerPx);
    }
    if (nextUnit === 'px') {
      converted = Math.round(converted);
    }
    inputEl.value = formatNumeric(converted, nextUnit === 'um' ? 3 : 0);
    unitEl.dataset.prevUnit = nextUnit;
  };

  const updateMeasurementScaleHelp = () => {
    if (!prefsScaleInput || !prefsScaleLive || !prefsScaleExample) return;
    const umPerPx = sanitizePositive(prefsScaleInput.value, 0.1);
    const pxPerUm = umPerPx > 0 ? (1 / umPerPx) : 0;
    prefsScaleLive.textContent =
      `Current Scale: 1 \u00b5m = ${formatNumeric(pxPerUm, 3)} px (${formatNumeric(umPerPx, 4)} \u00b5m/px).`;

    const examples = [];
    if (redWidthUnit && redWidthInput && redWidthUnit.value === 'um') {
      const px = convertUmToPixels(redWidthInput.value, umPerPx);
      if (px > 0) {
        examples.push(`Puncta Line Width ${formatNumeric(redWidthInput.value, 3)} \u00b5m -> ${px} px`);
      }
    }
    if (cenDotDistanceUnit && cenDotDistanceInput && cenDotDistanceUnit.value === 'um') {
      const px = convertUmToPixels(cenDotDistanceInput.value, umPerPx);
      if (px > 0) {
        examples.push(`Minimum Signal Distance ${formatNumeric(cenDotDistanceInput.value, 3)} \u00b5m -> ${px} px`);
      }
    }
    if (cenDotProximityRadiusUnit && cenDotProximityRadiusInput && cenDotProximityRadiusUnit.value === 'um') {
      const px = convertUmToPixels(cenDotProximityRadiusInput.value, umPerPx);
      if (px > 0) {
        examples.push(`Signal Proximity Radius ${formatNumeric(cenDotProximityRadiusInput.value, 3)} \u00b5m -> ${px} px`);
      }
    }
    if (biorientationRedMinDistanceUnit && biorientationRedMinDistanceInput && biorientationRedMinDistanceUnit.value === 'um') {
      const px = convertUmToPixels(biorientationRedMinDistanceInput.value, umPerPx, 0);
      examples.push(`Biorientation Minimum Red Distance ${formatNumeric(biorientationRedMinDistanceInput.value, 3)} \u00b5m -> ${px} px`);
    }
    if (biorientationRedMaxDistanceUnit && biorientationRedMaxDistanceInput && biorientationRedMaxDistanceUnit.value === 'um') {
      const px = convertUmToPixels(biorientationRedMaxDistanceInput.value, umPerPx, 0);
      examples.push(`Biorientation Maximum Red Distance ${formatNumeric(biorientationRedMaxDistanceInput.value, 3)} \u00b5m -> ${px} px`);
    }
    prefsScaleExample.textContent = examples.length
      ? `Live Conversion: ${examples.join(' | ')}`
      : 'Set a plugin length unit to \u00b5m to preview its pixel conversion here.';
  };

  const captureNumericField = (inputEl) => {
    const raw = valueOrEmpty(inputEl);
    return {
      raw,
      normalized: normalizeNumericString(raw),
    };
  };

  const capturePluginSnapshot = () => ({
    selectedPlugins: sortByOrder([...selectedPlugins], pluginOrder),
    signalQuantificationEnabled: isSignalQuantificationEnabled(),
    signalQuantificationMode: normalizeSignalMode(signalQuantificationModeInput?.value),
    punctaContourIntensityEnabled: !!(
      punctaContourIntensityEnabledInput && punctaContourIntensityEnabledInput.checked
    ),
    alternateNucleusDetectionEnabled: !!(
      alternateRedDetectionInput && alternateRedDetectionInput.checked
    ),
    redWidth: captureNumericField(redWidthInput),
    redWidthUnit: normalizeLengthUnit(valueOrEmpty(redWidthUnit)),
    cenDotDistance: captureNumericField(cenDotDistanceInput),
    cenDotDistanceUnit: normalizeLengthUnit(valueOrEmpty(cenDotDistanceUnit)),
    cenDotProximityRadius: captureNumericField(cenDotProximityRadiusInput),
    cenDotProximityRadiusUnit: normalizeLengthUnit(valueOrEmpty(cenDotProximityRadiusUnit)),
    biorientationRedMinDistance: captureNumericField(biorientationRedMinDistanceInput),
    biorientationRedMinDistanceUnit: normalizeLengthUnit(valueOrEmpty(biorientationRedMinDistanceUnit)),
    biorientationRedMaxDistance: captureNumericField(biorientationRedMaxDistanceInput),
    biorientationRedMaxDistanceUnit: normalizeLengthUnit(valueOrEmpty(biorientationRedMaxDistanceUnit)),
    biorientationCollinearityThreshold: captureNumericField(biorientationCollinearityThresholdInput),
    punctaLineMode: valueOrEmpty(punctaLineModeInput) || 'red_puncta',
    nuclearCellPairMode: valueOrEmpty(nuclearCellPairModeInput) || 'green_nucleus',
    nuclearCellPairContourMode: normalizeNuclearContourMode(valueOrEmpty(nuclearCellPairContourModeInput)),
    useLegacyNuclearCellPairPipeline: !!(
      legacyNuclearCellPairInput && legacyNuclearCellPairInput.checked
    ),
    greenContourFilterEnabled: !!(greenContourFilterEnabledInput && greenContourFilterEnabledInput.checked),
    greenDotSplitEnabled: truthyHiddenValue(greenDotSplitEnabledInput),
    greenDotSplitMode: normalizeGreenDotSplitMode(valueOrEmpty(greenDotSplitModeInput)),
    redDotSplitEnabled: truthyHiddenValue(redDotSplitEnabledInput),
    redDotSplitMode: normalizeRedDotSplitMode(valueOrEmpty(redDotSplitModeInput)),
    micronsPerPixel: captureNumericField(prefsScaleInput),
    useMetadataScale: !!(useMetadataScaleInput && useMetadataScaleInput.checked),
    useMetadataChannelOrder: !!(useMetadataChannelOrderInput && useMetadataChannelOrderInput.checked),
    fallbackChannelOrder: channelOrderFromBar(prefsFallbackChannelOrderBar),
  });

  const captureAdvancedSnapshot = () => ({
    moduleEnabled: !!(moduleEnabledInput && moduleEnabledInput.checked),
    enforceLayerCount: !!(enforceLayerCountInput && enforceLayerCountInput.checked),
    enforceWavelengths: !!(enforceWavelengthsInput && enforceWavelengthsInput.checked),
    showLegacyPlugins: !!(showLegacyPluginsInput && showLegacyPluginsInput.checked),
    requiredChannels: sortByOrder([...manualRequiredChannels], channelOrder),
    overrideChannels: sortByOrder([...overrides], channelOrder),
  });

  const captureSavingSnapshot = () => ({
    autoSaveExperiments: !!(autoSaveExperimentsInput && autoSaveExperimentsInput.checked),
    showSavedFileChannels: !!(showSavedFileChannelsInput && showSavedFileChannelsInput.checked),
    showSavedFileScales: !!(showSavedFileScalesInput && showSavedFileScalesInput.checked),
    sidebarStartsOpen: !!(sidebarStartsOpenInput && sidebarStartsOpenInput.checked),
    defaultPunctaSourceContourCountFilter: normalizePunctaSourceContourCountFilter(
      defaultPunctaSourceContourCountFilterInput ? defaultPunctaSourceContourCountFilterInput.value : ''
    ),
  });

  const pushToggleChange = (changes, label, fromValue, toValue) => {
    if (fromValue === toValue) return;
    changes.push(`${label}: ${asOnOff(fromValue)} -> ${asOnOff(toValue)}`);
  };

  const numericDisplay = (field) => (field.normalized || '0');

  const buildPluginChangeList = (fromSnapshot, toSnapshot) => {
    const changes = [];
    pushToggleChange(
      changes,
      'Signal Quantification',
      fromSnapshot.signalQuantificationEnabled,
      toSnapshot.signalQuantificationEnabled
    );
    if (fromSnapshot.signalQuantificationMode !== toSnapshot.signalQuantificationMode) {
      changes.push(
        `Signal Quantification Mode: ${signalModeLabel(fromSnapshot.signalQuantificationMode)} -> ${signalModeLabel(toSnapshot.signalQuantificationMode)}`
      );
    }
    pushToggleChange(
      changes,
      'Red/Green Contour Intensities',
      fromSnapshot.punctaContourIntensityEnabled,
      toSnapshot.punctaContourIntensityEnabled
    );
    const before = new Set(fromSnapshot.selectedPlugins || []);
    const after = new Set(toSnapshot.selectedPlugins || []);

    sortByOrder([...after], pluginOrder).forEach((pluginId) => {
      if (!before.has(pluginId)) {
        changes.push(`Enabled plugin: ${pluginLabel(pluginId)}`);
      }
    });
    sortByOrder([...before], pluginOrder).forEach((pluginId) => {
      if (!after.has(pluginId)) {
        changes.push(`Disabled plugin: ${pluginLabel(pluginId)}`);
      }
    });

    if (
      fromSnapshot.redWidth.normalized !== toSnapshot.redWidth.normalized ||
      fromSnapshot.redWidthUnit !== toSnapshot.redWidthUnit
    ) {
      changes.push(
        `Puncta Line Width: ${numericDisplay(fromSnapshot.redWidth)} ${formatLengthUnitLabel(fromSnapshot.redWidthUnit)} -> ${numericDisplay(toSnapshot.redWidth)} ${formatLengthUnitLabel(toSnapshot.redWidthUnit)}`
      );
    }
    if (
      fromSnapshot.cenDotDistance.normalized !== toSnapshot.cenDotDistance.normalized ||
      fromSnapshot.cenDotDistanceUnit !== toSnapshot.cenDotDistanceUnit
    ) {
      changes.push(
        `Minimum Signal Distance: ${numericDisplay(fromSnapshot.cenDotDistance)} ${formatLengthUnitLabel(fromSnapshot.cenDotDistanceUnit)} -> ${numericDisplay(toSnapshot.cenDotDistance)} ${formatLengthUnitLabel(toSnapshot.cenDotDistanceUnit)}`
      );
    }
    if (
      fromSnapshot.cenDotProximityRadius.normalized !== toSnapshot.cenDotProximityRadius.normalized ||
      fromSnapshot.cenDotProximityRadiusUnit !== toSnapshot.cenDotProximityRadiusUnit
    ) {
      changes.push(
        `Signal Proximity Radius: ${numericDisplay(fromSnapshot.cenDotProximityRadius)} ${formatLengthUnitLabel(fromSnapshot.cenDotProximityRadiusUnit)} -> ${numericDisplay(toSnapshot.cenDotProximityRadius)} ${formatLengthUnitLabel(toSnapshot.cenDotProximityRadiusUnit)}`
      );
    }
    if (
      fromSnapshot.biorientationRedMinDistance.normalized !== toSnapshot.biorientationRedMinDistance.normalized ||
      fromSnapshot.biorientationRedMinDistanceUnit !== toSnapshot.biorientationRedMinDistanceUnit
    ) {
      changes.push(
        `Biorientation Minimum Red Distance: ${numericDisplay(fromSnapshot.biorientationRedMinDistance)} ${formatLengthUnitLabel(fromSnapshot.biorientationRedMinDistanceUnit)} -> ${numericDisplay(toSnapshot.biorientationRedMinDistance)} ${formatLengthUnitLabel(toSnapshot.biorientationRedMinDistanceUnit)}`
      );
    }
    if (
      fromSnapshot.biorientationRedMaxDistance.normalized !== toSnapshot.biorientationRedMaxDistance.normalized ||
      fromSnapshot.biorientationRedMaxDistanceUnit !== toSnapshot.biorientationRedMaxDistanceUnit
    ) {
      changes.push(
        `Biorientation Maximum Red Distance: ${numericDisplay(fromSnapshot.biorientationRedMaxDistance)} ${formatLengthUnitLabel(fromSnapshot.biorientationRedMaxDistanceUnit)} -> ${numericDisplay(toSnapshot.biorientationRedMaxDistance)} ${formatLengthUnitLabel(toSnapshot.biorientationRedMaxDistanceUnit)}`
      );
    }
    if (fromSnapshot.biorientationCollinearityThreshold.normalized !== toSnapshot.biorientationCollinearityThreshold.normalized) {
      changes.push(
        `Biorientation Collinearity Threshold: ${numericDisplay(fromSnapshot.biorientationCollinearityThreshold)} -> ${numericDisplay(toSnapshot.biorientationCollinearityThreshold)}`
      );
    }
    if (fromSnapshot.nuclearCellPairMode !== toSnapshot.nuclearCellPairMode) {
      changes.push(
        `Nucleus Contour Source: ${nucleusModeLabel(fromSnapshot.nuclearCellPairMode)} -> ${nucleusModeLabel(toSnapshot.nuclearCellPairMode)}`
      );
    }
    if (normalizeNuclearContourMode(fromSnapshot.nuclearCellPairContourMode) !== normalizeNuclearContourMode(toSnapshot.nuclearCellPairContourMode)) {
      changes.push(
        `Nucleus Contour Mode: ${nuclearContourModeLabel(fromSnapshot.nuclearCellPairContourMode)} -> ${nuclearContourModeLabel(toSnapshot.nuclearCellPairContourMode)}`
      );
    }
    pushToggleChange(
      changes,
      'Legacy-Scaled Measurement Compatibility',
      fromSnapshot.useLegacyNuclearCellPairPipeline,
      toSnapshot.useLegacyNuclearCellPairPipeline
    );
    pushToggleChange(
      changes,
      'Alternate Nucleus Detection',
      fromSnapshot.alternateNucleusDetectionEnabled,
      toSnapshot.alternateNucleusDetectionEnabled
    );
    const fromDotSplitEnabled = !!(fromSnapshot.greenDotSplitEnabled || fromSnapshot.redDotSplitEnabled);
    const toDotSplitEnabled = !!(toSnapshot.greenDotSplitEnabled || toSnapshot.redDotSplitEnabled);
    pushToggleChange(changes, 'Split Merged Dots', fromDotSplitEnabled, toDotSplitEnabled);
    const fromDotSplitTarget = dotSplitTargetFromFlags(
      fromSnapshot.greenDotSplitEnabled,
      fromSnapshot.redDotSplitEnabled
    );
    const toDotSplitTarget = dotSplitTargetFromFlags(
      toSnapshot.greenDotSplitEnabled,
      toSnapshot.redDotSplitEnabled
    );
    if (fromDotSplitEnabled && toDotSplitEnabled && fromDotSplitTarget !== toDotSplitTarget) {
      changes.push(
        `Split Merged Dots Target: ${dotSplitTargetLabel(fromDotSplitTarget)} -> ${dotSplitTargetLabel(toDotSplitTarget)}`
      );
    }
    if (normalizeGreenDotSplitMode(fromSnapshot.greenDotSplitMode) !== normalizeGreenDotSplitMode(toSnapshot.greenDotSplitMode)) {
      changes.push(`Green Split Mode: ${normalizeGreenDotSplitMode(fromSnapshot.greenDotSplitMode)} -> ${normalizeGreenDotSplitMode(toSnapshot.greenDotSplitMode)}`);
    }
    if (normalizeRedDotSplitMode(fromSnapshot.redDotSplitMode) !== normalizeRedDotSplitMode(toSnapshot.redDotSplitMode)) {
      changes.push(`Red Split Mode: ${normalizeRedDotSplitMode(fromSnapshot.redDotSplitMode)} -> ${normalizeRedDotSplitMode(toSnapshot.redDotSplitMode)}`);
    }
    pushToggleChange(
      changes,
      'Filter Green Contours',
      fromSnapshot.greenContourFilterEnabled,
      toSnapshot.greenContourFilterEnabled
    );
    if (fromSnapshot.micronsPerPixel.normalized !== toSnapshot.micronsPerPixel.normalized) {
      changes.push(
        `Manual Scale Fallback: ${numericDisplay(fromSnapshot.micronsPerPixel)} -> ${numericDisplay(toSnapshot.micronsPerPixel)}`
      );
    }
    pushToggleChange(
      changes,
      'Auto-Detect Scale From File',
      fromSnapshot.useMetadataScale,
      toSnapshot.useMetadataScale
    );
    pushToggleChange(
      changes,
      'Auto-Detect Channels From File',
      fromSnapshot.useMetadataChannelOrder,
      toSnapshot.useMetadataChannelOrder
    );
    if (JSON.stringify(fromSnapshot.fallbackChannelOrder || []) !== JSON.stringify(toSnapshot.fallbackChannelOrder || [])) {
      changes.push(
        `Manual Channel Fallback Order: ${channelOrderLabelList(fromSnapshot.fallbackChannelOrder)} -> ${channelOrderLabelList(toSnapshot.fallbackChannelOrder)}`
      );
    }
    return changes;
  };

  const predictRemovedPluginsForOverrides = (overrideChannels) => {
    if (!baselineSnapshots.plugins || !Array.isArray(overrideChannels) || !overrideChannels.length) {
      return [];
    }
    const overrideSet = new Set(overrideChannels);
    return sortByOrder(baselineSnapshots.plugins.selectedPlugins || [], pluginOrder)
      .filter((pluginId) => {
        const requiredChannels = pluginMap.get(pluginId)?.required_channels;
        return Array.isArray(requiredChannels) && requiredChannels.some((channel) => overrideSet.has(channel));
      })
      .map((pluginId) => pluginLabel(pluginId));
  };

  const buildAdvancedChangeList = (fromSnapshot, toSnapshot) => {
    const changes = [];
    pushToggleChange(
      changes,
      'Show Legacy Blue-Channel Plugins',
      fromSnapshot.showLegacyPlugins,
      toSnapshot.showLegacyPlugins
    );
    pushToggleChange(
      changes,
      'Enable Optional Metadata Checks Below',
      fromSnapshot.moduleEnabled,
      toSnapshot.moduleEnabled
    );
    pushToggleChange(
      changes,
      'Enforce 4-Layer Files',
      fromSnapshot.enforceLayerCount,
      toSnapshot.enforceLayerCount
    );
    pushToggleChange(
      changes,
      'Require All Channels',
      fromSnapshot.enforceWavelengths,
      toSnapshot.enforceWavelengths
    );

    const beforeRequired = new Set(fromSnapshot.requiredChannels || []);
    const afterRequired = new Set(toSnapshot.requiredChannels || []);
    sortByOrder(channelOrder, channelOrder).forEach((channel) => {
      if (alwaysRequired.has(channel)) return;
      const wasRequired = beforeRequired.has(channel);
      const isRequired = afterRequired.has(channel);
      if (wasRequired === isRequired) return;
      changes.push(`Require ${displayChannelLabel(channel)} channel: ${asOnOff(wasRequired)} -> ${asOnOff(isRequired)}`);
    });

    const beforeOverrides = JSON.stringify(fromSnapshot.overrideChannels || []);
    const afterOverrides = JSON.stringify(toSnapshot.overrideChannels || []);
    if (beforeOverrides !== afterOverrides) {
      const removedPluginLabels = predictRemovedPluginsForOverrides(toSnapshot.overrideChannels || []);
      if (removedPluginLabels.length) {
        changes.push(`Dependent plugins that will be removed: ${removedPluginLabels.join(', ')}`);
      }
    }
    return changes;
  };

  const buildSavingChangeList = (fromSnapshot, toSnapshot) => {
    const changes = [];
    pushToggleChange(
      changes,
      'Auto-Save Experiment Files To Account',
      fromSnapshot.autoSaveExperiments,
      toSnapshot.autoSaveExperiments
    );
    pushToggleChange(
      changes,
      'Show Channel Tags In Dashboard Sidebar',
      fromSnapshot.showSavedFileChannels,
      toSnapshot.showSavedFileChannels
    );
    pushToggleChange(
      changes,
      'Show Scale Details In File Sidebars',
      fromSnapshot.showSavedFileScales,
      toSnapshot.showSavedFileScales
    );
    pushToggleChange(
      changes,
      'Start Sidebars Open On Dashboard, Display, And Preprocess',
      fromSnapshot.sidebarStartsOpen,
      toSnapshot.sidebarStartsOpen
    );
    if (
      fromSnapshot.defaultPunctaSourceContourCountFilter
      !== toSnapshot.defaultPunctaSourceContourCountFilter
    ) {
      changes.push(
        `Default Source Contour Count Filter: ${punctaSourceContourCountFilterLabel(fromSnapshot.defaultPunctaSourceContourCountFilter)} -> ${punctaSourceContourCountFilterLabel(toSnapshot.defaultPunctaSourceContourCountFilter)}`
      );
    }
    return changes;
  };

  const getSectionChanges = (section) => {
    if (section === 'plugins' && baselineSnapshots.plugins) {
      return buildPluginChangeList(baselineSnapshots.plugins, capturePluginSnapshot());
    }
    if (section === 'advanced' && baselineSnapshots.advanced) {
      return buildAdvancedChangeList(baselineSnapshots.advanced, captureAdvancedSnapshot());
    }
    if (section === 'saving' && baselineSnapshots.saving) {
      return buildSavingChangeList(baselineSnapshots.saving, captureSavingSnapshot());
    }
    return [];
  };

  const hasUnsavedChangesForSection = (section) => getSectionChanges(section).length > 0;
  const collectUnsavedChanges = () =>
    ['plugins', 'advanced', 'saving'].flatMap((section) => getSectionChanges(section));
  const collectChangedSections = () =>
    ['plugins', 'advanced', 'saving'].filter((section) => hasUnsavedChangesForSection(section));
  const resolveSectionToSaveForNavigation = () => {
    if (hasUnsavedChangesForSection(activeSection)) return activeSection;
    const changed = collectChangedSections();
    return changed.length ? changed[0] : null;
  };
  const hasUnsavedChanges = () => collectUnsavedChanges().length > 0;
  const buildLeaveUnsavedPreviewItems = (intent) => {
    if (!intent) return [];
    if (intent.mode === 'section') {
      return getSectionChanges(intent.sourceSection);
    }
    if (intent.mode !== 'link') return [];
    const sectionToSave = intent.sectionToSave;
    if (!sectionToSave) return collectUnsavedChanges();
    const currentSectionChanges = getSectionChanges(sectionToSave);
    const sectionLabel = sectionLabelByKey[sectionToSave] || sectionToSave;
    const preview = currentSectionChanges.map((item) => `${sectionLabel}: ${item}`);
    const otherChangedSections = collectChangedSections().filter((section) => section !== sectionToSave);
    if (otherChangedSections.length) {
      const labels = otherChangedSections.map((section) => sectionLabelByKey[section] || section).join(', ');
      preview.push(`Other unsaved sections that will be discarded: ${labels}.`);
    }
    return preview;
  };

  const restorePluginSnapshot = (snapshot) => {
    if (!snapshot) return;
    selectedPlugins.clear();
    (snapshot.selectedPlugins || []).forEach((pluginId) => selectedPlugins.add(pluginId));
    if (signalQuantificationEnabledInput) signalQuantificationEnabledInput.checked = snapshot.signalQuantificationEnabled;
    if (signalQuantificationModeInput) signalQuantificationModeInput.value = normalizeSignalMode(snapshot.signalQuantificationMode);
    if (punctaContourIntensityEnabledInput) punctaContourIntensityEnabledInput.checked = snapshot.punctaContourIntensityEnabled;
    syncPluginToggles();
    if (redWidthInput) redWidthInput.value = snapshot.redWidth.raw;
    if (redWidthUnit) {
      redWidthUnit.value = snapshot.redWidthUnit;
      redWidthUnit.dataset.prevUnit = snapshot.redWidthUnit;
      syncLengthInputConstraints(redWidthInput, snapshot.redWidthUnit, 1, 0.01);
    }
    if (cenDotDistanceInput) cenDotDistanceInput.value = snapshot.cenDotDistance.raw;
    if (cenDotDistanceUnit) {
      cenDotDistanceUnit.value = snapshot.cenDotDistanceUnit;
      cenDotDistanceUnit.dataset.prevUnit = snapshot.cenDotDistanceUnit;
      syncLengthInputConstraints(cenDotDistanceInput, snapshot.cenDotDistanceUnit, 0, 0);
    }
    if (cenDotProximityRadiusInput) cenDotProximityRadiusInput.value = snapshot.cenDotProximityRadius.raw;
    if (cenDotProximityRadiusUnit) {
      cenDotProximityRadiusUnit.value = snapshot.cenDotProximityRadiusUnit;
      cenDotProximityRadiusUnit.dataset.prevUnit = snapshot.cenDotProximityRadiusUnit;
      syncLengthInputConstraints(cenDotProximityRadiusInput, snapshot.cenDotProximityRadiusUnit, 0, 0);
    }
    if (biorientationRedMinDistanceInput) biorientationRedMinDistanceInput.value = snapshot.biorientationRedMinDistance.raw;
    if (biorientationRedMinDistanceUnit) {
      biorientationRedMinDistanceUnit.value = snapshot.biorientationRedMinDistanceUnit;
      biorientationRedMinDistanceUnit.dataset.prevUnit = snapshot.biorientationRedMinDistanceUnit;
      syncLengthInputConstraints(biorientationRedMinDistanceInput, snapshot.biorientationRedMinDistanceUnit, 0, 0);
    }
    if (biorientationRedMaxDistanceInput) biorientationRedMaxDistanceInput.value = snapshot.biorientationRedMaxDistance.raw;
    if (biorientationRedMaxDistanceUnit) {
      biorientationRedMaxDistanceUnit.value = snapshot.biorientationRedMaxDistanceUnit;
      biorientationRedMaxDistanceUnit.dataset.prevUnit = snapshot.biorientationRedMaxDistanceUnit;
      syncLengthInputConstraints(biorientationRedMaxDistanceInput, snapshot.biorientationRedMaxDistanceUnit, 0, 0);
    }
    if (biorientationCollinearityThresholdInput) biorientationCollinearityThresholdInput.value = snapshot.biorientationCollinearityThreshold.raw;
    if (punctaLineModeInput) punctaLineModeInput.value = snapshot.punctaLineMode === 'green_puncta' ? 'green_puncta' : 'red_puncta';
    if (nuclearCellPairModeInput) nuclearCellPairModeInput.value = snapshot.nuclearCellPairMode;
    if (nuclearCellPairContourModeInput) {
      nuclearCellPairContourModeInput.value = normalizeNuclearContourMode(snapshot.nuclearCellPairContourMode);
    }
    if (legacyNuclearCellPairInput) {
      legacyNuclearCellPairInput.checked = !!snapshot.useLegacyNuclearCellPairPipeline;
    }
    if (greenContourFilterEnabledInput) greenContourFilterEnabledInput.checked = snapshot.greenContourFilterEnabled;
    setHiddenBoolValue(greenDotSplitEnabledInput, snapshot.greenDotSplitEnabled);
    setHiddenBoolValue(redDotSplitEnabledInput, snapshot.redDotSplitEnabled);
    if (dotSplitEnabledInput) {
      dotSplitEnabledInput.checked = !!(snapshot.greenDotSplitEnabled || snapshot.redDotSplitEnabled);
    }
    if (dotSplitTargetInput) {
      dotSplitTargetInput.value = dotSplitTargetFromFlags(
        snapshot.greenDotSplitEnabled,
        snapshot.redDotSplitEnabled
      );
      refreshCustomSelect(dotSplitTargetInput);
    }
    if (greenDotSplitModeInput) greenDotSplitModeInput.value = normalizeGreenDotSplitMode(snapshot.greenDotSplitMode);
    if (redDotSplitModeInput) redDotSplitModeInput.value = normalizeRedDotSplitMode(snapshot.redDotSplitMode);
    if (alternateRedDetectionInput) {
      alternateRedDetectionInput.checked = snapshot.alternateNucleusDetectionEnabled;
    }
    if (prefsScaleInput) prefsScaleInput.value = snapshot.micronsPerPixel.raw;
    if (useMetadataScaleInput) useMetadataScaleInput.checked = snapshot.useMetadataScale;
    if (useMetadataChannelOrderInput) useMetadataChannelOrderInput.checked = snapshot.useMetadataChannelOrder;
    applyFallbackChannelOrder(snapshot.fallbackChannelOrder, { clearHistory: true });
    syncRows();
    syncScaleMetadataStatus();
    updateMeasurementScaleHelp();
    syncChannelOrderStatus();
  };

  const restoreAdvancedSnapshot = (snapshot) => {
    if (!snapshot) return;
    if (moduleEnabledInput) moduleEnabledInput.checked = snapshot.moduleEnabled;
    if (enforceLayerCountInput) enforceLayerCountInput.checked = snapshot.enforceLayerCount;
    if (enforceWavelengthsInput) enforceWavelengthsInput.checked = snapshot.enforceWavelengths;
    if (showLegacyPluginsInput) showLegacyPluginsInput.checked = snapshot.showLegacyPlugins;
    manualRequiredChannels.clear();
    (snapshot.requiredChannels || []).forEach((channel) => {
      if (channel && !alwaysRequired.has(channel)) {
        manualRequiredChannels.add(channel);
      }
    });
    overrides.clear();
    (snapshot.overrideChannels || []).forEach((channel) => overrides.add(channel));
    syncRows();
  };

  const restoreSavingSnapshot = (snapshot) => {
    if (!snapshot) return;
    if (autoSaveExperimentsInput) autoSaveExperimentsInput.checked = snapshot.autoSaveExperiments;
    if (showSavedFileChannelsInput) showSavedFileChannelsInput.checked = snapshot.showSavedFileChannels;
    if (showSavedFileScalesInput) showSavedFileScalesInput.checked = snapshot.showSavedFileScales;
    if (sidebarStartsOpenInput) sidebarStartsOpenInput.checked = snapshot.sidebarStartsOpen;
    if (defaultPunctaSourceContourCountFilterInput) {
      defaultPunctaSourceContourCountFilterInput.value = normalizePunctaSourceContourCountFilter(
        snapshot.defaultPunctaSourceContourCountFilter
      );
      refreshCustomSelect(defaultPunctaSourceContourCountFilterInput);
    }
  };

  const captureBaselineSnapshots = () => {
    baselineSnapshots.plugins = capturePluginSnapshot();
    baselineSnapshots.advanced = captureAdvancedSnapshot();
    baselineSnapshots.saving = captureSavingSnapshot();
    fallbackChannelOrderUndoStack.length = 0;
    syncFallbackChannelOrderActions();
  };

  const closeReviewModal = (onAfterClose = null) => {
    closePopupModal(reviewChangesBackdrop, reviewChangesPanel, () => {
      pendingReview = null;
      if (reviewChangesList) reviewChangesList.innerHTML = '';
      if (typeof onAfterClose === 'function') onAfterClose();
    });
  };

  const closeLeaveUnsavedModal = (onAfterClose = null) => {
    closePopupModal(leaveUnsavedBackdrop, leaveUnsavedPanel, () => {
      pendingLeaveTarget = null;
      if (leaveUnsavedList) leaveUnsavedList.innerHTML = '';
      if (leaveUnsavedListWrap) leaveUnsavedListWrap.hidden = true;
      if (typeof onAfterClose === 'function') onAfterClose();
    });
  };

  const openLeaveUnsavedModal = (intent) => {
    if (!leaveUnsavedBackdrop) return;
    pendingLeaveTarget = intent;
    const messageEl = document.getElementById('leaveUnsavedMessage');
    if (messageEl) {
      if (intent && intent.mode === 'section') {
        const fromLabel = sectionLabelByKey[intent.sourceSection] || 'this section';
        const toLabel = sectionLabelByKey[intent.targetSection] || 'another section';
        messageEl.textContent = `You have unsaved changes in ${fromLabel}. Keep Old will discard those edits and switch to ${toLabel}. Confirm New will save those edits and switch to ${toLabel}.`;
      } else {
        const saveSectionLabel = sectionLabelByKey[intent?.sectionToSave] || 'current section';
        messageEl.textContent = `Are you sure you want to leave without saving changes? Keep Old will leave and discard edits. Confirm New will save ${saveSectionLabel} and continue to the selected page.`;
      }
    }
    const previewItems = buildLeaveUnsavedPreviewItems(intent);
    if (leaveUnsavedList && leaveUnsavedListWrap) {
      leaveUnsavedList.innerHTML = '';
      if (previewItems.length) {
        previewItems.forEach((item) => {
          const li = document.createElement('li');
          li.textContent = item;
          leaveUnsavedList.appendChild(li);
        });
        leaveUnsavedListWrap.hidden = false;
      } else {
        leaveUnsavedListWrap.hidden = true;
      }
    }
    openPopupModal(leaveUnsavedBackdrop, leaveUnsavedPanel);
  };

  const openReviewModal = ({ section, changes, form, restore }) => {
    if (!reviewChangesBackdrop || !reviewChangesList) return;
    pendingReview = { form, restore };
    const msgEl = document.getElementById('reviewChangesMessage');
    if (msgEl) {
      msgEl.textContent = `Are you sure you want to change ${sectionLabelByKey[section] || 'this section'}?`;
    }
    reviewChangesList.innerHTML = '';
    changes.forEach((item) => {
      const li = document.createElement('li');
      li.textContent = item;
      reviewChangesList.appendChild(li);
    });
    openPopupModal(reviewChangesBackdrop, reviewChangesPanel);
  };

  const attachReviewSubmit = (form, section, captureCurrent, buildDiff, restoreFromBaseline) => {
    if (!form) return;
    form.addEventListener('submit', (event) => {
      if (bypassReviewForSubmit.has(form)) {
        bypassReviewForSubmit.delete(form);
        return;
      }
      const baseline = baselineSnapshots[section];
      if (!baseline) return;
      const current = captureCurrent();
      const changes = buildDiff(baseline, current);
      if (!changes.length) return;
      event.preventDefault();
      openReviewModal({
        section,
        changes,
        form,
        restore: () => restoreFromBaseline(baseline),
      });
    });
  };

  [
    prefsScaleInput,
    redWidthInput,
    redWidthUnit,
    cenDotDistanceInput,
    cenDotDistanceUnit,
    biorientationRedMinDistanceInput,
    biorientationRedMinDistanceUnit,
    biorientationRedMaxDistanceInput,
    biorientationRedMaxDistanceUnit,
  ].forEach((el) => {
    if (!el) return;
    el.addEventListener('input', updateMeasurementScaleHelp);
    el.addEventListener('change', updateMeasurementScaleHelp);
  });
  if (useMetadataScaleInput) {
    useMetadataScaleInput.addEventListener('change', () => syncScaleMetadataStatus(true));
  }
  if (useMetadataChannelOrderInput) {
    useMetadataChannelOrderInput.addEventListener('change', () => syncChannelOrderStatus(true));
  }
  if (prefsFallbackChannelOrderBack) {
    prefsFallbackChannelOrderBack.addEventListener('click', () => {
      if (fallbackChannelOrderActionLocked) return;
      const previousOrder = fallbackChannelOrderUndoStack.pop();
      if (!previousOrder) return;
      lockFallbackChannelOrderActions();
      applyFallbackChannelOrder(previousOrder, { animate: true });
    });
  }
  if (prefsFallbackChannelOrderReset) {
    prefsFallbackChannelOrderReset.addEventListener('click', () => {
      if (fallbackChannelOrderActionLocked) return;
      const baselineOrder = baselineSnapshots.plugins?.fallbackChannelOrder || defaultFallbackChannelOrder;
      if (sameChannelOrder(channelOrderFromBar(prefsFallbackChannelOrderBar), baselineOrder)) return;
      lockFallbackChannelOrderActions();
      applyFallbackChannelOrder(baselineOrder, { clearHistory: true, animate: true });
    });
  }
  setupChannelOrderDrag(prefsFallbackChannelOrderBar);
  syncFallbackChannelOrderActions();
  const disclosureButtons = [...document.querySelectorAll('.measurement-disclosure-toggle[data-disclosure-target]')];
  disclosureButtons.forEach((button) => {
    const panelId = button.dataset.disclosureTarget;
    const panel = panelId ? document.getElementById(panelId) : null;
    const state = button.querySelector('[data-disclosure-state]');
    if (!panel || !state) return;
    panel.hidden = true;
    panel.classList.remove('is-open');
    button.classList.remove('is-open');
    button.setAttribute('aria-expanded', 'false');
    state.textContent = 'Show';
    button.addEventListener('click', () => {
      const opening = !panel.classList.contains('is-open');
      button.classList.toggle('is-open', opening);
      button.setAttribute('aria-expanded', opening ? 'true' : 'false');
      state.textContent = opening ? 'Hide' : 'Show';
      if (opening) {
        panel.hidden = false;
        requestAnimationFrame(() => panel.classList.add('is-open'));
      } else {
        panel.classList.remove('is-open');
        window.setTimeout(() => {
          if (!panel.classList.contains('is-open')) {
            panel.hidden = true;
          }
        }, 210);
      }
    });
  });

  if (redWidthInput && redWidthUnit) {
    redWidthUnit.dataset.prevUnit = normalizeLengthUnit(redWidthUnit.value);
    syncLengthInputConstraints(redWidthInput, redWidthUnit.value, 1, 0.01);
    redWidthUnit.addEventListener('change', () => {
      applyUnitConversion(redWidthInput, redWidthUnit, {
        minimumPx: 1,
        minimumUm: 0.01,
        defaultForUnit: (unit, umPerPx) => (normalizeLengthUnit(unit) === 'um' ? umPerPx : 1),
        minimumForUnit: (unit) => (normalizeLengthUnit(unit) === 'um' ? 0.01 : 1),
      });
      updateMeasurementScaleHelp();
    });
  }

  if (cenDotDistanceInput && cenDotDistanceUnit) {
    cenDotDistanceUnit.dataset.prevUnit = normalizeLengthUnit(cenDotDistanceUnit.value);
    syncLengthInputConstraints(cenDotDistanceInput, cenDotDistanceUnit.value, 0, 0);
    cenDotDistanceUnit.addEventListener('change', () => {
      applyUnitConversion(cenDotDistanceInput, cenDotDistanceUnit, {
        minimumPx: 0,
        minimumUm: 0,
        defaultForUnit: (unit, umPerPx) => (normalizeLengthUnit(unit) === 'um' ? 37 * umPerPx : 37),
        minimumForUnit: () => 0,
      });
      updateMeasurementScaleHelp();
    });
  }

  if (cenDotProximityRadiusInput && cenDotProximityRadiusUnit) {
    cenDotProximityRadiusUnit.dataset.prevUnit = normalizeLengthUnit(cenDotProximityRadiusUnit.value);
    syncLengthInputConstraints(cenDotProximityRadiusInput, cenDotProximityRadiusUnit.value, 0, 0);
    cenDotProximityRadiusUnit.addEventListener('change', () => {
      applyUnitConversion(cenDotProximityRadiusInput, cenDotProximityRadiusUnit, {
        minimumPx: 0,
        minimumUm: 0,
        defaultForUnit: (unit, umPerPx) => (normalizeLengthUnit(unit) === 'um' ? 13 * umPerPx : 13),
        minimumForUnit: () => 0,
      });
      updateMeasurementScaleHelp();
    });
  }

  if (biorientationRedMinDistanceInput && biorientationRedMinDistanceUnit) {
    biorientationRedMinDistanceUnit.dataset.prevUnit = normalizeLengthUnit(biorientationRedMinDistanceUnit.value);
    syncLengthInputConstraints(biorientationRedMinDistanceInput, biorientationRedMinDistanceUnit.value, 0, 0);
    biorientationRedMinDistanceUnit.addEventListener('change', () => {
      applyUnitConversion(biorientationRedMinDistanceInput, biorientationRedMinDistanceUnit, {
        minimumPx: 0,
        minimumUm: 0,
        defaultForUnit: () => 0,
        minimumForUnit: () => 0,
      });
      updateMeasurementScaleHelp();
    });
  }

  if (biorientationRedMaxDistanceInput && biorientationRedMaxDistanceUnit) {
    biorientationRedMaxDistanceUnit.dataset.prevUnit = normalizeLengthUnit(biorientationRedMaxDistanceUnit.value);
    syncLengthInputConstraints(biorientationRedMaxDistanceInput, biorientationRedMaxDistanceUnit.value, 0, 0);
    biorientationRedMaxDistanceUnit.addEventListener('change', () => {
      applyUnitConversion(biorientationRedMaxDistanceInput, biorientationRedMaxDistanceUnit, {
        minimumPx: 0,
        minimumUm: 0,
        defaultForUnit: (unit, umPerPx) => (normalizeLengthUnit(unit) === 'um' ? 37 * umPerPx : 37),
        minimumForUnit: () => 0,
      });
      updateMeasurementScaleHelp();
    });
  }

  attachReviewSubmit(
    pluginForm,
    'plugins',
    capturePluginSnapshot,
    buildPluginChangeList,
    restorePluginSnapshot
  );
  attachReviewSubmit(
    advancedForm,
    'advanced',
    captureAdvancedSnapshot,
    buildAdvancedChangeList,
    restoreAdvancedSnapshot
  );
  attachReviewSubmit(
    savingForm,
    'saving',
    captureSavingSnapshot,
    buildSavingChangeList,
    restoreSavingSnapshot
  );

  navButtons.forEach((button) => {
    button.addEventListener('click', (event) => {
      const targetSection = button.dataset.sec;
      if (!validSections.has(targetSection)) return;
      if (targetSection === activeSection) {
        showSection(targetSection);
        return;
      }
      if (!hasUnsavedChangesForSection(activeSection)) {
        showSection(targetSection);
        return;
      }
      event.preventDefault();
      openLeaveUnsavedModal({
        mode: 'section',
        sourceSection: activeSection,
        targetSection,
      });
    });
  });

  const shouldGuardAnchorNavigation = (event, anchor) => {
    if (!anchor) return false;
    if (event.defaultPrevented) return false;
    if (event.button !== 0) return false;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
    if (anchor.hasAttribute('download')) return false;
    if (anchor.target && anchor.target !== '_self') return false;
    const rawHref = anchor.getAttribute('href');
    if (!rawHref || rawHref.startsWith('#')) return false;
    if (/^javascript:/i.test(rawHref)) return false;
    let url;
    try {
      url = new URL(anchor.href, window.location.href);
    } catch (err) {
      return false;
    }
    if (url.href === window.location.href) return false;
    return true;
  };

  document.addEventListener(
    'click',
    (event) => {
      const anchor = event.target.closest('a[href]');
      if (!shouldGuardAnchorNavigation(event, anchor)) return;
      if (!hasUnsavedChanges()) return;
      event.preventDefault();
      const sectionToSave = resolveSectionToSaveForNavigation();
      openLeaveUnsavedModal({
        mode: 'link',
        href: anchor.href,
        sectionToSave,
      });
    },
    true
  );

  window.addEventListener('beforeunload', (event) => {
    if (allowWindowUnloadWithoutPrompt) return;
    if (!hasUnsavedChanges()) return;
    event.preventDefault();
    event.returnValue = '';
  });

  normalizeExclusiveSelections();
  [...selectedPlugins].forEach((pluginId) => applyPluginDependencies(pluginId));
  clearOverridesRequiredBySelectedPlugins();
  syncPluginToggles();
  syncRows();
  updateMeasurementScaleHelp();
  syncScaleMetadataStatus();
  syncChannelOrderStatus();
  captureBaselineSnapshots();
})();
