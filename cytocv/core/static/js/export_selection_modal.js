(function () {
  'use strict';

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

  function formatLabel(format) {
    return normalizeFormat(format) === 'xlsx' ? 'Excel' : 'CSV';
  }

  function getHeaderLabels(items) {
    const headers = Array.from(document.querySelectorAll('#celltable thead th'));
    const labels = new Map();
    if (headers.length < 2) return labels;
    items.forEach((item, index) => {
      const header = headers[index + 1];
      const text = header ? (header.textContent || '').replace(/\s+/g, ' ').trim() : '';
      if (text) labels.set(item.id, text);
    });
    return labels;
  }

  const MODAL_ENTER_MS = 170;
  const MODAL_EXIT_MS = 120;

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
    const list = document.getElementById(options.listId || 'exportSelectionList');
    const cancelBtn = document.getElementById(options.cancelId || 'cancelExportSelectionBtn');
    const confirmBtn = document.getElementById(options.confirmId || 'confirmExportSelectionBtn');
    const countEl = document.getElementById(options.countId || 'exportSelectionCount');
    const messageEl = document.getElementById(options.messageId || 'exportSelectionMessage');
    const triggerFormats = options.triggerFormats || {};
    const items = metadata && Array.isArray(metadata.items) ? metadata.items : [];
    const groups = metadata && Array.isArray(metadata.groups) ? metadata.groups : [];
    const groupLabels = new Map(groups.map((group) => [group.id, group.label || group.id]));
    const presetButtons = Array.from(
      backdrop ? backdrop.querySelectorAll('[data-export-selection-action]') : []
    );

    if (!metadata || !backdrop || !list || !cancelBtn || !confirmBtn || !items.length) {
      return null;
    }

    const modalVisibility = createModalVisibility(backdrop, modalPanel);
    let activeFormat = 'csv';
    let activeFileContext = null;

    function fileContext() {
      if (typeof options.getCurrentFileContext === 'function') {
        return options.getCurrentFileContext() || {};
      }
      return {};
    }

    function isDefaultSelected(item, visibility) {
      if (item.disabled) return true;
      if (!visibility) return item.defaultSelected !== false;
      if (!item.group) return item.defaultSelected !== false;
      return visibility[item.group] !== false;
    }

    function selectedIds() {
      return Array.from(list.querySelectorAll('input[type="checkbox"]:checked'))
        .map((input) => input.value)
        .filter(Boolean);
    }

    function sameMembers(left, right) {
      if (left.length !== right.length) return false;
      const rightSet = new Set(right);
      return left.every((value) => rightSet.has(value));
    }

    function defaultSelectedIds() {
      const visibility = statVisibilityForFile(activeFileContext ? activeFileContext.fileData : null);
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

    function updateCount() {
      const selected = selectedIds();
      const count = selected.length;
      if (countEl) {
        countEl.textContent = count === 1 ? '1 statistic selected' : `${count} statistics selected`;
      }
      confirmBtn.disabled = count === 0;
      updatePresetState(selected);
    }

    function setSelection(mode) {
      const visibility = statVisibilityForFile(activeFileContext ? activeFileContext.fileData : null);
      list.querySelectorAll('input[type="checkbox"]').forEach((input) => {
        const item = items.find((candidate) => candidate.id === input.value);
        if (!item) return;
        if (mode === 'all') {
          input.checked = true;
        } else if (mode === 'clear') {
          input.checked = false;
        } else {
          input.checked = isDefaultSelected(item, visibility);
        }
      });
      updateCount();
    }

    function buildRows() {
      const visibility = statVisibilityForFile(activeFileContext ? activeFileContext.fileData : null);
      const headerLabels = getHeaderLabels(items);
      list.innerHTML = '';

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
          row.className = 'export-selection-row';

          const text = document.createElement('span');
          text.className = 'export-selection-row-text';
          text.textContent = headerLabels.get(item.id) || item.label || item.id;

          const checkbox = document.createElement('input');
          checkbox.type = 'checkbox';
          checkbox.value = item.id;
          checkbox.checked = isDefaultSelected(item, visibility);
          checkbox.disabled = !!item.disabled;
          checkbox.addEventListener('change', updateCount);

          row.appendChild(text);
          row.appendChild(checkbox);
          section.appendChild(row);
        });

        list.appendChild(section);
      });
      updateCount();
    }

    function open(format) {
      activeFormat = normalizeFormat(format);
      activeFileContext = fileContext();
      buildRows();
      if (messageEl) {
        messageEl.textContent = `Choose the statistics to include in this ${formatLabel(activeFormat)} download.`;
      }
      confirmBtn.textContent = `Download ${formatLabel(activeFormat)}`;
      modalVisibility.show();
      const firstInput = list.querySelector('input[type="checkbox"]');
      if (firstInput) {
        firstInput.focus();
      } else {
        confirmBtn.focus();
      }
    }

    function close() {
      modalVisibility.hide(() => {
        activeFileContext = null;
      });
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
        setSelection(button.dataset.exportSelectionAction || 'calculated');
      });
    });

    cancelBtn.addEventListener('click', close);
    backdrop.addEventListener('click', (event) => {
      if (event.target === backdrop) close();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && backdrop.getAttribute('aria-hidden') === 'false') {
        close();
      }
    });

    confirmBtn.addEventListener('click', () => {
      const selected = selectedIds();
      if (!selected.length || typeof options.buildExportUrl !== 'function') return;
      const context = activeFileContext || fileContext();
      const url = options.buildExportUrl(context.fileUUID, activeFormat, selected);
      if (url) {
        window.location.href = url;
      }
    });

    return {
      open,
      close,
      refresh: buildRows,
    };
  }

  window.CytoCVExportSelection = {
    init: createController,
  };
})();
