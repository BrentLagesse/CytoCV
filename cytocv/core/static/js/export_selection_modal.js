(function () {
  'use strict';

  const MODAL_ENTER_MS = 170;
  const MODAL_EXIT_MS = 120;
  const VIEW_ENTER_MS = 150;
  const VIEW_EXIT_MS = 120;
  const SELECTED_COUNT_COLOR = '#61d394';
  const EMPTY_COUNT_COLOR = '#f0c95a';
  const VIEW_ANIM_CLASSES = [
    'anim-enter-forward',
    'anim-enter-backward',
    'anim-exit-forward',
    'anim-exit-backward',
  ];

  function parseConfig(scriptId) {
    const node = document.getElementById(scriptId || 'exportSelectionConfig');
    if (!node) return null;
    try {
      return JSON.parse(node.textContent || '{}');
    } catch (error) {
      return null;
    }
  }

  function firstStatisticsRow(fileData) {
    const statistics = fileData && fileData.Statistics && typeof fileData.Statistics === 'object'
      ? fileData.Statistics
      : {};
    return Object.values(statistics).find((row) => row && typeof row === 'object') || null;
  }

  function statVisibilityForFile(fileData) {
    const firstRow = firstStatisticsRow(fileData);
    const visibility = firstRow && firstRow.stat_visibility && typeof firstRow.stat_visibility === 'object'
      ? firstRow.stat_visibility
      : null;
    return visibility || null;
  }

  function normalizeFormat(format) {
    return format === 'xlsx' ? 'xlsx' : 'csv';
  }

  function getHeaderLabels(items, useCurrentTable) {
    const labels = new Map();
    if (!useCurrentTable) return labels;
    const headers = Array.from(document.querySelectorAll('#celltable thead th'));
    if (headers.length < 2) return labels;
    items.forEach((item, index) => {
      const header = headers[index + 1];
      const text = header ? (header.textContent || '').replace(/\s+/g, ' ').trim() : '';
      if (text) labels.set(item.id, text);
    });
    return labels;
  }

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

  function filenameFromDisposition(header, fallback) {
    const value = String(header || '');
    const utfMatch = value.match(/filename\*=UTF-8''([^;]+)/i);
    if (utfMatch) return decodeURIComponent(utfMatch[1].replace(/"/g, ''));
    const match = value.match(/filename="?([^";]+)"?/i);
    return match ? match[1] : fallback;
  }

  function triggerBlobDownload(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => window.URL.revokeObjectURL(url), 500);
  }

  function createModalVisibility(backdrop, panel) {
    const prefersReducedMotion = !!(
      window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    );
    let enterTimer = null;
    let exitTimer = null;

    function clearTimers() {
      if (enterTimer) {
        window.clearTimeout(enterTimer);
        enterTimer = null;
      }
      if (exitTimer) {
        window.clearTimeout(exitTimer);
        exitTimer = null;
      }
    }

    function clearAnimationClasses() {
      backdrop.classList.remove('modal-enter', 'modal-exit');
      if (panel) panel.classList.remove('modal-enter', 'modal-exit');
    }

    function show() {
      clearTimers();
      clearAnimationClasses();
      backdrop.style.display = 'flex';
      backdrop.setAttribute('aria-hidden', 'false');
      if (prefersReducedMotion) return;
      void backdrop.offsetWidth;
      backdrop.classList.add('modal-enter');
      if (panel) panel.classList.add('modal-enter');
      enterTimer = window.setTimeout(() => {
        clearAnimationClasses();
        enterTimer = null;
      }, MODAL_ENTER_MS);
    }

    function hide(onAfterClose) {
      clearTimers();
      if (prefersReducedMotion || backdrop.style.display !== 'flex') {
        clearAnimationClasses();
        backdrop.style.display = 'none';
        backdrop.setAttribute('aria-hidden', 'true');
        if (typeof onAfterClose === 'function') onAfterClose();
        return;
      }

      clearAnimationClasses();
      backdrop.classList.add('modal-exit');
      if (panel) panel.classList.add('modal-exit');
      backdrop.setAttribute('aria-hidden', 'true');
      exitTimer = window.setTimeout(() => {
        clearAnimationClasses();
        backdrop.style.display = 'none';
        exitTimer = null;
        if (typeof onAfterClose === 'function') onAfterClose();
      }, MODAL_EXIT_MS);
    }

    return { show, hide };
  }

  function createController(options) {
    const metadata = options.metadata || parseConfig(options.configScriptId);
    const backdrop = document.getElementById(options.modalId || 'exportSelectionBackdrop');
    const modalPanel = backdrop ? backdrop.querySelector('.export-selection-modal') : null;
    const fileView = document.getElementById(options.fileViewId || 'exportFileSelectionView');
    const statsView = document.getElementById(options.statsViewId || 'exportStatSelectionView');
    const fileList = document.getElementById(options.fileListId || 'exportFileSelectionList');
    const statList = document.getElementById(options.listId || 'exportSelectionList');
    const fileCountEl = document.getElementById(options.fileCountId || 'exportFileSelectionCount');
    const statCountEl = document.getElementById(options.countId || 'exportSelectionCount');
    const titleEl = document.getElementById(options.titleId || 'exportSelectionTitle');
    const messageEl = document.getElementById(options.messageId || 'exportSelectionMessage');
    const fileMessageEl = document.getElementById(options.fileMessageId || 'exportFileSelectionMessage');
    const backFileBtn = document.getElementById(options.backFileId || 'backExportFileSelectionBtn');
    const continueFileBtn = document.getElementById(options.continueFileId || 'continueExportFileSelectionBtn');
    const cancelBtn = document.getElementById(options.cancelId || 'cancelExportSelectionBtn');
    const confirmBtn = document.getElementById(options.confirmId || 'confirmExportSelectionBtn');
    const chooseFilesBtn = document.getElementById(options.chooseFilesId || 'chooseExportFilesBtn');
    const formatToggle = document.getElementById(options.formatToggleId || 'exportFormatToggle');
    const triggerFormats = options.triggerFormats || {};
    const items = metadata && Array.isArray(metadata.items) ? metadata.items : [];
    const groups = metadata && Array.isArray(metadata.groups) ? metadata.groups : [];
    const groupLabels = new Map(groups.map((group) => [group.id, group.label || group.id]));
    const presetButtons = Array.from(
      backdrop ? backdrop.querySelectorAll('[data-export-selection-action]') : []
    );
    const fileActionButtons = Array.from(
      backdrop ? backdrop.querySelectorAll('[data-export-file-action]') : []
    );
    const formatButtons = Array.from(
      backdrop ? backdrop.querySelectorAll('[data-export-format]') : []
    );

    if (
      !metadata || !backdrop || !fileView || !statsView || !fileList || !statList
      || !backFileBtn || !continueFileBtn || !cancelBtn || !confirmBtn || !items.length
    ) {
      return null;
    }

    const modalVisibility = createModalVisibility(backdrop, modalPanel);
    let activeFormat = 'csv';
    let activeMode = 'single';
    let activeView = 'stats';
    let activeFileContext = null;
    let activeFileIds = new Set();
    let statsCanBack = false;
    let viewTimer = null;
    let downloading = false;

    function fileContext() {
      if (typeof options.getCurrentFileContext === 'function') {
        return options.getCurrentFileContext() || {};
      }
      return {};
    }

    function selectableFiles() {
      if (typeof options.getSelectableFiles !== 'function') return [];
      return (options.getSelectableFiles() || [])
        .map((file) => {
          const id = String(file.id || file.uuid || file.fileUUID || '');
          return {
            id,
            label: file.label || file.name || id,
            fileData: file.fileData || null,
          };
        })
        .filter((file) => file.id);
    }

    function selectedFileIdsInOrder() {
      const selected = activeFileIds;
      return selectableFiles()
        .filter((file) => selected.has(file.id))
        .map((file) => file.id);
    }

    function selectedSidebarFileIds() {
      if (typeof options.getSelectedFileIds !== 'function') return [];
      const selected = new Set((options.getSelectedFileIds() || []).map((id) => String(id)));
      return selectableFiles()
        .filter((file) => selected.has(file.id))
        .map((file) => file.id);
    }

    function selectedFileDataList() {
      const selected = activeFileIds;
      return selectableFiles()
        .filter((file) => selected.has(file.id))
        .map((file) => file.fileData)
        .filter((fileData) => fileData && typeof fileData === 'object');
    }

    function clearViewTimer() {
      if (viewTimer !== null) {
        window.clearTimeout(viewTimer);
        viewTimer = null;
      }
    }

    function clearViewAnim(view) {
      if (!view) return;
      VIEW_ANIM_CLASSES.forEach((className) => view.classList.remove(className));
    }

    function switchView(target, animate, direction) {
      const toView = target === 'files' ? fileView : statsView;
      const fromView = target === 'files' ? statsView : fileView;
      activeView = target;
      clearViewTimer();
      clearViewAnim(fileView);
      clearViewAnim(statsView);

      if (!animate || fromView.hidden) {
        fromView.hidden = true;
        toView.hidden = false;
        return;
      }

      const suffix = direction === 'backward' ? 'backward' : 'forward';
      fromView.hidden = false;
      toView.hidden = true;
      fromView.classList.add(`anim-exit-${suffix}`);
      viewTimer = window.setTimeout(() => {
        clearViewAnim(fromView);
        fromView.hidden = true;
        toView.hidden = false;
        void toView.offsetWidth;
        toView.classList.add(`anim-enter-${suffix}`);
        viewTimer = window.setTimeout(() => {
          clearViewAnim(toView);
          viewTimer = null;
        }, VIEW_ENTER_MS);
      }, VIEW_EXIT_MS);
    }

    function sameMembers(left, right) {
      if (left.length !== right.length) return false;
      const rightSet = new Set(right);
      return left.every((value) => rightSet.has(value));
    }

    function majorityVisibility() {
      const totals = new Map();
      const enabled = new Map();
      selectedFileDataList().forEach((fileData) => {
        const visibility = statVisibilityForFile(fileData);
        if (!visibility) return;
        groups.forEach((group) => {
          if (!Object.prototype.hasOwnProperty.call(visibility, group.id)) return;
          totals.set(group.id, (totals.get(group.id) || 0) + 1);
          if (visibility[group.id] !== false) {
            enabled.set(group.id, (enabled.get(group.id) || 0) + 1);
          }
        });
      });
      const result = {};
      totals.forEach((total, groupId) => {
        result[groupId] = (enabled.get(groupId) || 0) >= total / 2;
      });
      return result;
    }

    function activeVisibility() {
      if (activeMode === 'multi') return majorityVisibility();
      return statVisibilityForFile(activeFileContext ? activeFileContext.fileData : null);
    }

    function isDefaultSelected(item, visibility) {
      if (item.disabled) return true;
      if (!visibility) return item.defaultSelected !== false;
      if (!item.group) return item.defaultSelected !== false;
      if (!Object.prototype.hasOwnProperty.call(visibility, item.group)) {
        return item.defaultSelected !== false;
      }
      return visibility[item.group] !== false;
    }

    function selectedStatIds() {
      return Array.from(statList.querySelectorAll('input[type="checkbox"]:checked'))
        .map((input) => input.value)
        .filter(Boolean);
    }

    function defaultSelectedIds() {
      const visibility = activeVisibility();
      return items
        .filter((item) => isDefaultSelected(item, visibility))
        .map((item) => item.id);
    }

    function updatePresetState(selected) {
      let activeAction = '';
      if (selected.length === 0) {
        activeAction = 'clear';
      } else if (selected.length === items.length) {
        activeAction = 'all';
      } else if (sameMembers(selected, defaultSelectedIds())) {
        activeAction = 'calculated';
      }

      presetButtons.forEach((button) => {
        const isActive = button.dataset.exportSelectionAction === activeAction;
        button.classList.toggle('active', isActive);
        button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });
    }

    function updateFormatState() {
      if (formatToggle) {
        formatToggle.dataset.activeFormat = activeFormat;
      }
      formatButtons.forEach((button) => {
        const isActive = normalizeFormat(button.dataset.exportFormat) === activeFormat;
        button.classList.toggle('active', isActive);
        button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });
    }

    function setActiveFormat(format) {
      activeFormat = normalizeFormat(format);
      updateFormatState();
    }

    function updateCountState(element, count) {
      if (!element) return;
      const hasSelection = count > 0;
      element.classList.toggle('has-selection', count > 0);
      element.classList.toggle('is-empty', count === 0);
      element.dataset.selectionState = hasSelection ? 'selected' : 'empty';
      element.style.setProperty(
        'color',
        hasSelection ? SELECTED_COUNT_COLOR : EMPTY_COUNT_COLOR,
        'important'
      );
    }

    function updateStatCount() {
      const selected = selectedStatIds();
      const count = selected.length;
      if (statCountEl) {
        statCountEl.textContent = count === 1 ? '1 statistic selected' : `${count} statistics selected`;
        updateCountState(statCountEl, count);
      }
      confirmBtn.disabled = count === 0 || downloading;
      updatePresetState(selected);
    }

    function setStatSelection(mode) {
      const visibility = activeVisibility();
      const selected = selectedStatIds();
      const shouldToggleAllOff = mode === 'all' && selected.length === items.length;
      let checkedCount = 0;
      statList.querySelectorAll('input[type="checkbox"]').forEach((input) => {
        const item = items.find((candidate) => candidate.id === input.value);
        if (!item) return;
        if (mode === 'all') {
          input.checked = !shouldToggleAllOff;
        } else if (mode === 'clear') {
          input.checked = false;
        } else {
          input.checked = isDefaultSelected(item, visibility);
        }
        if (input.checked) checkedCount += 1;
      });
      updateStatCount();
      if (mode === 'calculated' && checkedCount === 0) {
        showNotice(
          'Calculated statistics could not be selected for the current file set. Select statistics manually or choose different files.',
          'warning'
        );
      }
    }

    function updateFileCount() {
      const selected = selectedFileIdsInOrder();
      const count = selected.length;
      if (fileCountEl) {
        fileCountEl.textContent = count === 1 ? '1 file selected' : `${count} files selected`;
        updateCountState(fileCountEl, count);
      }
      continueFileBtn.disabled = count === 0;
      fileActionButtons.forEach((button) => {
        const action = button.dataset.exportFileAction;
        const isActive = (action === 'clear' && count === 0)
          || (action === 'all' && count === selectableFiles().length && count > 0);
        button.classList.toggle('active', isActive);
        button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });
    }

    function setFileSelection(mode) {
      if (mode === 'all') {
        const allFileIds = selectableFiles().map((file) => file.id);
        activeFileIds = selectedFileIdsInOrder().length === allFileIds.length
          ? new Set()
          : new Set(allFileIds);
      } else if (mode === 'clear') {
        activeFileIds = new Set();
      }
      fileList.querySelectorAll('input[type="checkbox"]').forEach((input) => {
        input.checked = activeFileIds.has(input.value);
      });
      updateFileCount();
    }

    function buildFileRows() {
      fileList.innerHTML = '';
      selectableFiles().forEach((file) => {
        const row = document.createElement('label');
        row.className = 'export-selection-row file-export-row';

        const text = document.createElement('span');
        text.className = 'export-selection-row-text';
        text.textContent = file.label;

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = file.id;
        checkbox.checked = activeFileIds.has(file.id);
        checkbox.addEventListener('change', () => {
          if (checkbox.checked) {
            activeFileIds.add(file.id);
          } else {
            activeFileIds.delete(file.id);
          }
          updateFileCount();
        });

        row.appendChild(text);
        row.appendChild(checkbox);
        fileList.appendChild(row);
      });
      updateFileCount();
    }

    function buildStatRows() {
      const visibility = activeVisibility();
      const useCurrentTableLabels = activeMode === 'single';
      const headerLabels = getHeaderLabels(items, useCurrentTableLabels);
      statList.innerHTML = '';

      const grouped = new Map();
      items.forEach((item) => {
        const groupId = item.group || 'other';
        if (!grouped.has(groupId)) grouped.set(groupId, []);
        grouped.get(groupId).push(item);
      });

      grouped.forEach((groupItems, groupId) => {
        const section = document.createElement('section');
        section.className = 'export-selection-group';

        const title = document.createElement('div');
        title.className = 'export-selection-group-title';
        title.textContent = groupLabels.get(groupId) || groupId;
        section.appendChild(title);

        groupItems.forEach((item) => {
          const row = document.createElement('label');
          row.className = 'export-selection-row stat-export-row';

          const text = document.createElement('span');
          text.className = 'export-selection-row-text';
          text.textContent = headerLabels.get(item.id) || item.label || item.id;

          const checkbox = document.createElement('input');
          checkbox.type = 'checkbox';
          checkbox.value = item.id;
          checkbox.checked = isDefaultSelected(item, visibility);
          checkbox.disabled = !!item.disabled;
          checkbox.addEventListener('change', updateStatCount);

          row.appendChild(text);
          row.appendChild(checkbox);
          section.appendChild(row);
        });

        statList.appendChild(section);
      });
      updateStatCount();
    }

    function configureStatsView() {
      const isMulti = activeMode === 'multi';
      const fileCount = selectedFileIdsInOrder().length;
      if (titleEl) titleEl.textContent = 'Download statistics';
      if (messageEl) {
        messageEl.textContent = isMulti
          ? `Choose the statistics to include for ${fileCount} selected ${fileCount === 1 ? 'file' : 'files'}.`
          : 'Choose the statistics to include in this download.';
      }
      cancelBtn.textContent = statsCanBack ? 'Back' : 'Cancel';
      confirmBtn.textContent = 'Download';
      if (chooseFilesBtn) chooseFilesBtn.hidden = !selectableFiles().length;
      updateFormatState();
    }

    function focusFirst(view) {
      const firstInput = view.querySelector('input[type="checkbox"]');
      if (firstInput) {
        firstInput.focus();
        return;
      }
      const button = view.querySelector('button:not(:disabled)');
      if (button) button.focus();
    }

    function open(format) {
      activeMode = 'single';
      activeView = 'stats';
      statsCanBack = false;
      setActiveFormat(format);
      activeFileContext = fileContext();
      activeFileIds = new Set(
        activeFileContext && activeFileContext.fileUUID
          ? [String(activeFileContext.fileUUID)]
          : []
      );
      buildStatRows();
      configureStatsView();
      switchView('stats', false, 'forward');
      modalVisibility.show();
      focusFirst(statsView);
    }

    function openFiles(initialFileIds) {
      const selectedIds = Array.isArray(initialFileIds) && initialFileIds.length
        ? initialFileIds.map((id) => String(id))
        : selectedSidebarFileIds();
      if (!selectedIds.length) return;
      activeMode = 'multi';
      activeView = 'files';
      statsCanBack = false;
      setActiveFormat('csv');
      activeFileContext = null;
      activeFileIds = new Set(selectedIds);
      if (fileMessageEl) {
        fileMessageEl.textContent = 'Choose the files to include in this download.';
      }
      buildFileRows();
      switchView('files', false, 'forward');
      modalVisibility.show();
      focusFirst(fileView);
    }

    function close() {
      clearViewTimer();
      modalVisibility.hide(() => {
        activeFileContext = null;
        activeFileIds = new Set();
        statsCanBack = false;
        downloading = false;
        confirmBtn.disabled = false;
      });
    }

    function continueToStats() {
      if (!selectedFileIdsInOrder().length) return;
      activeMode = 'multi';
      statsCanBack = true;
      buildStatRows();
      configureStatsView();
      switchView('stats', true, 'forward');
      focusFirst(statsView);
    }

    function backToFiles() {
      buildFileRows();
      switchView('files', true, 'backward');
      focusFirst(fileView);
    }

    function editFilesFromStats() {
      let currentIds = selectedFileIdsInOrder();
      if (!currentIds.length && activeFileContext && activeFileContext.fileUUID) {
        currentIds = [String(activeFileContext.fileUUID)];
      }
      if (!currentIds.length) {
        currentIds = selectedSidebarFileIds();
      }
      if (!currentIds.length) return;
      activeMode = 'multi';
      activeFileIds = new Set(currentIds);
      buildFileRows();
      switchView('files', true, 'backward');
      focusFirst(fileView);
    }

    function showNotice(message, tone) {
      if (typeof options.showError === 'function') {
        options.showError(message);
        return;
      }
      if (window.showGlobalMessage) {
        window.showGlobalMessage(message, tone || 'error', {
          scope: 'analysis-warning',
          top: 'calc(var(--nav-height) + 8px)',
          timeoutMs: 7000,
        });
        return;
      }
      window.alert(message);
    }

    function showError(message) {
      showNotice(message, 'error');
    }

    async function bulkDownload() {
      const selectedColumns = selectedStatIds();
      const fileIds = selectedFileIdsInOrder();
      if (!selectedColumns.length || !fileIds.length || downloading) return;
      if (!options.bulkExportUrl || typeof options.buildBulkExportPayload !== 'function') return;

      downloading = true;
      updateStatCount();
      try {
        const response = await fetch(options.bulkExportUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': options.csrfToken || getCookie('csrftoken') || '',
          },
          credentials: 'same-origin',
          body: JSON.stringify(options.buildBulkExportPayload({
            fileIds,
            format: activeFormat,
            columns: selectedColumns,
          })),
        });
        if (!response.ok) {
          let message = 'Unable to download selected files.';
          const errorResponse = response.clone();
          try {
            const payload = await response.json();
            message = payload.error || message;
          } catch (error) {
            const text = await errorResponse.text();
            if (text) message = text;
          }
          throw new Error(message);
        }
        const blob = await response.blob();
        triggerBlobDownload(
          blob,
          filenameFromDisposition(
            response.headers.get('Content-Disposition'),
            `selected-statistics.${activeFormat}`
          )
        );
        close();
      } catch (error) {
        showError(error && error.message ? error.message : 'Unable to download selected files.');
      } finally {
        downloading = false;
        updateStatCount();
      }
    }

    Object.entries(triggerFormats).forEach(([triggerId, format]) => {
      const trigger = document.getElementById(triggerId);
      if (!trigger) return;
      trigger.addEventListener('click', (event) => {
        if (trigger.getAttribute('href') === '#') return;
        event.preventDefault();
        open(format);
      });
    });

    presetButtons.forEach((button) => {
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => {
        setStatSelection(button.dataset.exportSelectionAction || 'calculated');
      });
    });

    fileActionButtons.forEach((button) => {
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => {
        setFileSelection(button.dataset.exportFileAction || 'all');
      });
    });

    formatButtons.forEach((button) => {
      button.addEventListener('click', () => {
        setActiveFormat(button.dataset.exportFormat || 'csv');
      });
    });

    backFileBtn.addEventListener('click', close);
    continueFileBtn.addEventListener('click', continueToStats);
    cancelBtn.addEventListener('click', () => {
      if (statsCanBack && activeView === 'stats') {
        backToFiles();
        return;
      }
      close();
    });
    confirmBtn.addEventListener('click', () => {
      const selected = selectedStatIds();
      if (!selected.length) return;
      if (activeMode === 'multi') {
        void bulkDownload();
        return;
      }
      if (typeof options.buildExportUrl !== 'function') return;
      const context = activeFileContext || fileContext();
      const url = options.buildExportUrl(context.fileUUID, activeFormat, selected);
      if (url) {
        window.location.href = url;
      }
    });
    if (chooseFilesBtn) {
      chooseFilesBtn.addEventListener('click', () => {
        editFilesFromStats();
      });
    }

    backdrop.addEventListener('click', (event) => {
      if (event.target === backdrop) close();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape' || backdrop.getAttribute('aria-hidden') !== 'false') return;
      if (statsCanBack && activeView === 'stats') {
        backToFiles();
        return;
      }
      close();
    });

    return {
      open,
      openFiles,
      close,
      refresh: buildStatRows,
    };
  }

  window.CytoCVExportSelection = {
    init: createController,
  };
})();
