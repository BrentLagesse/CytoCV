// Shared cell deletion actions for Display and Dashboard viewers. The frontend
// only chooses cell IDs and confirmation scope; the endpoints enforce ownership.
(function (global) {
    'use strict';

    function init({ pageConfig = {} } = {}) {
        // Cell deletion controller: 3-dot menu + table right-click + confirmation modal.
        const table = document.getElementById('celltable');
        const trigger = document.getElementById('cellActionsTrigger');
        const triggerMenu = document.getElementById('cellActionsMenu');
        const contextMenu = document.getElementById('cellRowContextMenu');
        const modalBackdrop = document.getElementById('deleteCellBackdrop');
        const modalPanel = modalBackdrop ? modalBackdrop.querySelector('.save-modal, .delete-modal') : null;
        const modalMessage = document.getElementById('deleteCellMessage');
        const cancelBtn = document.getElementById('cancelDeleteCellBtn');
        const confirmBtn = document.getElementById('confirmDeleteCellBtn');
        const tableFileUuid = (pageConfig && pageConfig.tableFileUuid) || '';
        const selectCellsBackdrop = document.getElementById('selectCellsBackdrop');
        const selectCellsPanel = selectCellsBackdrop ? selectCellsBackdrop.querySelector('.save-modal, .delete-modal') : null;
        const selectCellsView = document.getElementById('selectCellsView');
        const confirmCellsView = document.getElementById('confirmCellsView');
        const selectCellsList = document.getElementById('selectCellsList');
        const confirmCellsList = document.getElementById('confirmCellsList');
        const selectCellsBackBtn = document.getElementById('selectCellsBackBtn');
        const selectCellsDeleteBtn = document.getElementById('selectCellsDeleteBtn');
        const selectCellsToggleAllBtn = document.getElementById('selectCellsToggleAllBtn');
        const selectCellsClearBtn = document.getElementById('selectCellsClearBtn');
        const confirmCellsBackBtn = document.getElementById('confirmCellsBackBtn');
        const confirmCellsDeleteBtn = document.getElementById('confirmCellsDeleteBtn');
        const confirmCellsMessage = document.getElementById('confirmCellsMessage');

        if (!modalBackdrop || !modalMessage || !confirmBtn || !cancelBtn) {
            return;
        }

        function readCsrfToken() {
            let value = null;
            document.cookie.split(';').forEach((cookie) => {
                const item = cookie.trim();
                if (item.startsWith('csrftoken=')) {
                    value = decodeURIComponent(item.slice('csrftoken='.length));
                }
            });
            return value;
        }

        let pendingDelete = null;
        let pendingMultiDelete = null;
        let selectedCellIds = new Set();
        let cellSelectSwitchTimer = null;
        const cellSelectAnimClasses = [
            'anim-enter-forward',
            'anim-enter-backward',
            'anim-exit-forward',
            'anim-exit-backward',
        ];
        const MODAL_ENTER_MS = 170;
        const MODAL_EXIT_MS = 120;
        const prefersReducedMotion = !!(
            window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
        );

        function createModalAnimator(backdrop, panel) {
            let enterTimer = null;
            let exitTimer = null;

            function clearTimers() {
                if (enterTimer !== null) {
                    window.clearTimeout(enterTimer);
                    enterTimer = null;
                }
                if (exitTimer !== null) {
                    window.clearTimeout(exitTimer);
                    exitTimer = null;
                }
            }

            function clearAnimationClasses() {
                if (backdrop) backdrop.classList.remove('modal-enter', 'modal-exit');
                if (panel) panel.classList.remove('modal-enter', 'modal-exit');
            }

            function show() {
                if (!backdrop) return;
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

            function hide(onAfterClose = null) {
                if (!backdrop) {
                    if (typeof onAfterClose === 'function') onAfterClose();
                    return;
                }
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

            function isOpen() {
                return !!backdrop
                    && backdrop.style.display === 'flex'
                    && backdrop.getAttribute('aria-hidden') === 'false';
            }

            return { show, hide, isOpen };
        }

        const deleteCellModal = createModalAnimator(modalBackdrop, modalPanel);
        const selectCellsModal = createModalAnimator(selectCellsBackdrop, selectCellsPanel);

        // Context menus are moved into the fullscreen host when needed so they
        // remain usable with the image/table viewer in fullscreen mode.
        function closeTriggerMenu() {
            if (!triggerMenu || !trigger) return;
            triggerMenu.dataset.open = 'false';
            trigger.setAttribute('aria-expanded', 'false');
        }

        function openTriggerMenu() {
            if (!triggerMenu || !trigger) return;
            triggerMenu.dataset.open = 'true';
            trigger.setAttribute('aria-expanded', 'true');
        }

        function closeContextMenu() {
            if (!contextMenu) return;
            contextMenu.dataset.open = 'false';
            contextMenu.removeAttribute('data-cell-id');
        }

        function openContextMenu(clientX, clientY, cellId) {
            if (!contextMenu) return;
            const host = document.fullscreenElement || document.body;
            if (contextMenu.parentElement !== host) {
                host.appendChild(contextMenu);
            }
            contextMenu.dataset.open = 'true';
            contextMenu.dataset.cellId = String(cellId);
            contextMenu.style.position = 'fixed';
            contextMenu.style.visibility = 'hidden';
            contextMenu.style.left = '0px';
            contextMenu.style.top = '0px';
            const rect = contextMenu.getBoundingClientRect();
            const margin = 8;
            const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
            const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
            let left = clientX;
            if (left + rect.width + margin > viewportWidth) {
                left = viewportWidth - rect.width - margin;
            }
            left = Math.max(margin, left);
            let top = clientY;
            if (top + rect.height + margin > viewportHeight) {
                top = viewportHeight - rect.height - margin;
            }
            top = Math.max(margin, top);
            contextMenu.style.left = left + 'px';
            contextMenu.style.top = top + 'px';
            contextMenu.style.visibility = 'visible';
        }

        function closeAllMenus() {
            closeTriggerMenu();
            closeContextMenu();
        }

        // Multi-cell deletion uses a two-step modal so the selected IDs can be
        // reviewed before the request is sent.
        function clearCellSelectAnim(view) {
            if (!view) return;
            cellSelectAnimClasses.forEach((className) => view.classList.remove(className));
        }

        function clearCellSelectSwitchTimer() {
            if (cellSelectSwitchTimer !== null) {
                window.clearTimeout(cellSelectSwitchTimer);
                cellSelectSwitchTimer = null;
            }
        }

        function switchCellSelectView(target, animate = false) {
            if (!selectCellsView || !confirmCellsView) return;
            const toView = target === 'confirm' ? confirmCellsView : selectCellsView;
            const fromView = target === 'confirm' ? selectCellsView : confirmCellsView;
            clearCellSelectSwitchTimer();
            clearCellSelectAnim(selectCellsView);
            clearCellSelectAnim(confirmCellsView);

            if (!animate || fromView.hidden) {
                fromView.hidden = true;
                toView.hidden = false;
                return;
            }

            fromView.hidden = false;
            toView.hidden = true;
            fromView.classList.add(target === 'confirm' ? 'anim-exit-forward' : 'anim-exit-backward');
            cellSelectSwitchTimer = window.setTimeout(() => {
                clearCellSelectAnim(fromView);
                fromView.hidden = true;
                toView.hidden = false;
                void toView.offsetWidth;
                toView.classList.add(target === 'confirm' ? 'anim-enter-forward' : 'anim-enter-backward');
                cellSelectSwitchTimer = window.setTimeout(() => {
                    clearCellSelectAnim(toView);
                    cellSelectSwitchTimer = null;
                }, 150);
            }, 120);
        }

        function openModal({ cellId, fileUuid, fileName, includeAndItsData }) {
            pendingDelete = { cellId, fileUuid };
            const safeName = fileName || 'this file';
            modalMessage.textContent = includeAndItsData
                ? `Are you sure you want to delete cell ${cellId} and its data from ${safeName}?`
                : `Are you sure you want to delete cell ${cellId} from ${safeName}?`;
            confirmBtn.disabled = false;
            const host = document.fullscreenElement || document.body;
            if (modalBackdrop.parentElement !== host) {
                host.appendChild(modalBackdrop);
            }
            modalBackdrop.style.zIndex = '10000';
            deleteCellModal.show();
        }

        function closeModal() {
            pendingDelete = null;
            deleteCellModal.hide();
            confirmBtn.disabled = false;
        }

        function closeSelectCellsModal() {
            if (!selectCellsBackdrop) return;
            pendingMultiDelete = null;
            selectedCellIds = new Set();
            clearCellSelectSwitchTimer();
            if (selectCellsView) clearCellSelectAnim(selectCellsView);
            if (confirmCellsView) clearCellSelectAnim(confirmCellsView);
            selectCellsModal.hide();
            if (selectCellsDeleteBtn) selectCellsDeleteBtn.disabled = true;
            if (confirmCellsDeleteBtn) confirmCellsDeleteBtn.disabled = false;
        }

        function getCurrentFileData() {
            if (typeof fileUUIDs === 'undefined' || typeof filesData === 'undefined') {
                return { fileUuid: null, fileData: null };
            }
            const fileUuid = fileUUIDs[currentFileIndex];
            return { fileUuid, fileData: fileUuid ? filesData[fileUuid] : null };
        }

        function reportError(message) {
            if (window.showGlobalMessage) {
                window.showGlobalMessage(message, 'error', {
                    scope: 'analysis-warning',
                    top: 'calc(var(--nav-height) + 8px)',
                    timeoutMs: 6000,
                });
            } else {
                window.alert(message);
            }
        }

        function removeTableRow(cellId) {
            if (!table) return;
            const rows = table.querySelectorAll('tbody tr');
            for (const row of rows) {
                const firstCell = row.cells && row.cells[0];
                if (!firstCell) continue;
                if (firstCell.textContent.trim() === String(cellId)) {
                    row.remove();
                    break;
                }
            }
        }

        function removeTableRows(cellIds) {
            (cellIds || []).forEach((cellId) => removeTableRow(cellId));
        }

        function updateLocalStateForDeletedCells(fileUuid, cellIds, payload) {
            const fileData = filesData[fileUuid];
            if (!fileData) return;
            // The server is the source of truth for deletion; local state is pruned
            // only after a successful response so stale selections do not hide cells.
            (cellIds || []).forEach((cellId) => {
                const idStr = String(cellId);
                if (fileData.CellPairImages) {
                    delete fileData.CellPairImages[cellId];
                    delete fileData.CellPairImages[idStr];
                }
                if (fileData.Statistics) {
                    delete fileData.Statistics[cellId];
                    delete fileData.Statistics[idStr];
                }
            });
            fileData.NumberOfCells = Number(payload.num_cells || 0);
            if (typeof fileUUIDs !== 'undefined' && fileUuid === fileUUIDs[currentFileIndex]) {
                maxCells = fileData.NumberOfCells;
            }
        }

        async function refreshDisplayedCellsAfterDelete(fileUuid, deletedCellIds) {
            if (typeof fileUUIDs === 'undefined' || fileUuid !== fileUUIDs[currentFileIndex]) {
                return;
            }
            const fileData = filesData[fileUuid];
            if (!fileData) return;
            const sortedIds = getSortedCellIds(fileData);
            const deletedIdSet = new Set((deletedCellIds || []).map((cellId) => Number(cellId)));
            const previousCellNumber = Number(currentCellNumber);
            // Prefer the shared contour-filter sync path when present so table,
            // image, filter, and cell-number state stay aligned after deletion.
            if (typeof syncCurrentCellToActiveContourFilter === 'function') {
                await syncCurrentCellToActiveContourFilter(fileData, {
                    anchorCellId: previousCellNumber,
                    blendImages: true,
                    blendText: true,
                    forceRender: deletedIdSet.has(previousCellNumber),
                });
                return;
            }
            if (typeof currentCellNumber !== 'undefined' && deletedIdSet.has(previousCellNumber)) {
                if (sortedIds.length === 0) {
                    currentCellNumber = 0;
                } else {
                    const nextLarger = sortedIds.find((id) => id > previousCellNumber);
                    if (typeof nextLarger === 'number') {
                        currentCellNumber = nextLarger;
                    } else {
                        currentCellNumber = sortedIds[sortedIds.length - 1];
                    }
                }
            }
            if (typeof updateCellImages === 'function') {
                const showContours = typeof getContourToggleState === 'function'
                    ? getContourToggleState()
                    : true;
                await updateCellImages(fileData.CellPairImages, fileData.Statistics, {
                    blendImages: true,
                    blendText: true,
                    forceShowContours: showContours,
                });
            }
        }

        async function performDelete(fileUuid, cellId) {
            const csrfToken = readCsrfToken();
            const url = `/experiment/${fileUuid}/cell/${cellId}/delete/`;
            // The endpoint owns authorization, artifact cleanup, and NumCells
            // updates; this request only names the current file/cell.
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken || '',
                    'Accept': 'application/json',
                },
                credentials: 'same-origin',
            });
            if (!response.ok) {
                let errorText = `Failed to delete cell ${cellId}.`;
                try {
                    const data = await response.json();
                    if (data && data.error) {
                        errorText = data.error;
                    }
                } catch (err) {
                    // ignore JSON parse errors; use default message
                }
                throw new Error(errorText);
            }
            return response.json();
        }

        async function performBulkDelete(fileUuid, cellIds) {
            const csrfToken = readCsrfToken();
            const response = await fetch(`/experiment/${fileUuid}/cells/delete/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || '',
                    'Accept': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({ cell_ids: cellIds }),
            });
            if (!response.ok) {
                let errorText = 'Failed to delete selected cells.';
                try {
                    const data = await response.json();
                    if (data && data.error) {
                        errorText = data.error;
                    }
                } catch (err) {
                    // ignore JSON parse errors; use default message
                }
                throw new Error(errorText);
            }
            return response.json();
        }

        async function executeDelete(fileUuid, cellId, { fromModal = false } = {}) {
            if (fromModal) {
                confirmBtn.disabled = true;
            }
            try {
                const payload = await performDelete(fileUuid, cellId);
                updateLocalStateForDeletedCells(fileUuid, [cellId], payload);
                removeTableRow(cellId);
                await refreshDisplayedCellsAfterDelete(fileUuid, [cellId]);
                const fileData = filesData[fileUuid];
                if (typeof updateTableState === 'function' && fileData) {
                    updateTableState(fileUuid, fileData);
                }
            } catch (err) {
                reportError(err && err.message ? err.message : 'Failed to delete cell.');
                if (fromModal) {
                    confirmBtn.disabled = false;
                }
                return false;
            }
            if (fromModal) {
                closeModal();
            }
            return true;
        }

        async function executeBulkDelete(fileUuid, cellIds, { fromSelectModal = false } = {}) {
            const normalizedIds = (cellIds || [])
                .map((cellId) => Number(cellId))
                .filter((cellId) => Number.isFinite(cellId) && cellId > 0);
            if (!normalizedIds.length) return false;
            if (fromSelectModal) {
                if (selectCellsDeleteBtn) selectCellsDeleteBtn.disabled = true;
                if (confirmCellsDeleteBtn) confirmCellsDeleteBtn.disabled = true;
            }
            try {
                const payload = await performBulkDelete(fileUuid, normalizedIds);
                // Use server-returned deleted IDs because stale selections may
                // contain cells already removed by another action.
                const deletedIds = Array.isArray(payload.deleted_cells)
                    ? payload.deleted_cells.map((cellId) => Number(cellId))
                    : normalizedIds;
                updateLocalStateForDeletedCells(fileUuid, deletedIds, payload);
                removeTableRows(deletedIds);
                await refreshDisplayedCellsAfterDelete(fileUuid, deletedIds);
                const fileData = filesData[fileUuid];
                if (typeof updateTableState === 'function' && fileData) {
                    updateTableState(fileUuid, fileData);
                }
            } catch (err) {
                reportError(err && err.message ? err.message : 'Failed to delete selected cells.');
                if (fromSelectModal) {
                    if (selectCellsDeleteBtn) selectCellsDeleteBtn.disabled = selectedCellIds.size === 0;
                    if (confirmCellsDeleteBtn) confirmCellsDeleteBtn.disabled = false;
                }
                return false;
            }
            if (fromSelectModal) {
                closeSelectCellsModal();
            }
            return true;
        }

        async function handleConfirm() {
            if (!pendingDelete) return;
            const { fileUuid, cellId } = pendingDelete;
            await executeDelete(fileUuid, cellId, { fromModal: true });
        }

        function requestCellDelete(options) {
            if (confirmCellDeletion) {
                openModal(options);
                return;
            }
            pendingDelete = null;
            void executeDelete(options.fileUuid, options.cellId);
        }

        function selectedCellIdsArray() {
            return [...selectedCellIds].sort((a, b) => a - b);
        }

        function updateSelectCellsDeleteButton() {
            if (selectCellsDeleteBtn) {
                selectCellsDeleteBtn.disabled = selectedCellIds.size === 0;
            }
        }

        function getSelectCellsCheckboxes() {
            if (!selectCellsList) return [];
            return Array.from(selectCellsList.querySelectorAll('.cell-select-input'));
        }

        function updateSelectCellsToggleAllBtn() {
            if (!selectCellsToggleAllBtn) return;
            const checkboxes = getSelectCellsCheckboxes();
            if (!checkboxes.length) {
                selectCellsToggleAllBtn.disabled = true;
                selectCellsToggleAllBtn.classList.remove('active');
                selectCellsToggleAllBtn.setAttribute('aria-pressed', 'false');
                if (selectCellsClearBtn) {
                    selectCellsClearBtn.disabled = true;
                    selectCellsClearBtn.classList.remove('active');
                    selectCellsClearBtn.setAttribute('aria-pressed', 'false');
                }
                return;
            }
            selectCellsToggleAllBtn.disabled = false;
            if (selectCellsClearBtn) selectCellsClearBtn.disabled = false;
            const allChecked = checkboxes.every((cb) => cb.checked);
            const noneChecked = checkboxes.every((cb) => !cb.checked);
            selectCellsToggleAllBtn.classList.toggle('active', allChecked);
            selectCellsToggleAllBtn.setAttribute('aria-pressed', allChecked ? 'true' : 'false');
            if (selectCellsClearBtn) {
                selectCellsClearBtn.classList.toggle('active', noneChecked);
                selectCellsClearBtn.setAttribute('aria-pressed', noneChecked ? 'true' : 'false');
            }
        }

        function renderCellListItem(list, cellId, { selectable = false } = {}) {
            const item = document.createElement('li');
            if (selectable) {
                const label = document.createElement('label');
                label.className = 'cell-select-card';
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'cell-select-input';
                checkbox.value = String(cellId);
                checkbox.addEventListener('change', () => {
                    if (checkbox.checked) {
                        selectedCellIds.add(cellId);
                        label.classList.add('selected');
                    } else {
                        selectedCellIds.delete(cellId);
                        label.classList.remove('selected');
                    }
                    updateSelectCellsDeleteButton();
                    updateSelectCellsToggleAllBtn();
                });
                const text = document.createElement('span');
                text.className = 'cell-select-title';
                text.textContent = `Cell ${cellId}`;
                const check = document.createElement('span');
                check.className = 'cell-select-check';
                check.setAttribute('aria-hidden', 'true');
                const checkMark = document.createElement('span');
                checkMark.innerHTML = '&#10003;';
                check.appendChild(checkMark);
                label.appendChild(checkbox);
                label.appendChild(text);
                label.appendChild(check);
                item.appendChild(label);
            } else {
                const card = document.createElement('div');
                card.className = 'cell-select-card is-static';
                const text = document.createElement('span');
                text.className = 'cell-select-title';
                text.textContent = `Cell ${cellId}`;
                card.appendChild(text);
                item.appendChild(card);
            }
            list.appendChild(item);
        }

        function renderSelectCellsList(fileData) {
            if (!selectCellsList) return [];
            selectCellsList.innerHTML = '';
            selectedCellIds = new Set();
            const cellIds = getSortedCellIds(fileData);
            if (!cellIds.length) {
                const item = document.createElement('li');
                const empty = document.createElement('p');
                empty.className = 'cell-select-empty';
                empty.textContent = 'No cells are available to delete.';
                item.appendChild(empty);
                selectCellsList.appendChild(item);
            } else {
                cellIds.forEach((cellId) => renderCellListItem(selectCellsList, cellId, {
                    selectable: true,
                }));
            }
            updateSelectCellsDeleteButton();
            updateSelectCellsToggleAllBtn();
            return cellIds;
        }

        function renderConfirmCellsList(cellIds) {
            if (!confirmCellsList) return;
            confirmCellsList.innerHTML = '';
            (cellIds || []).forEach((cellId) => renderCellListItem(confirmCellsList, cellId));
            if (confirmCellsMessage) {
                const count = (cellIds || []).length;
                confirmCellsMessage.textContent = `Delete ${count} selected ${count === 1 ? 'cell' : 'cells'}?`;
            }
        }

        function openSelectCellsModal() {
            if (!selectCellsBackdrop || !selectCellsView || !confirmCellsView || !selectCellsDeleteBtn) {
                return;
            }
            const { fileUuid, fileData } = getCurrentFileData();
            if (!fileUuid || !fileData) return;
            const cellIds = renderSelectCellsList(fileData);
            pendingMultiDelete = { fileUuid, fileName: fileData.Image_Name || '', cellIds };
            switchCellSelectView('select', false);
            const host = document.fullscreenElement || document.body;
            if (selectCellsBackdrop.parentElement !== host) {
                host.appendChild(selectCellsBackdrop);
            }
            selectCellsBackdrop.style.zIndex = '10000';
            selectCellsModal.show();
        }

        if (trigger && triggerMenu) {
            trigger.addEventListener('click', (event) => {
                event.stopPropagation();
                if (triggerMenu.dataset.open === 'true') {
                    closeTriggerMenu();
                } else {
                    closeContextMenu();
                    openTriggerMenu();
                }
            });
            triggerMenu.addEventListener('click', (event) => {
                const selectTarget = event.target.closest('[data-action="select-cells"]');
                if (selectTarget) {
                    closeTriggerMenu();
                    openSelectCellsModal();
                    return;
                }
                const target = event.target.closest('[data-action="delete-current-cell"]');
                if (!target) return;
                closeTriggerMenu();
                const { fileUuid, fileData } = getCurrentFileData();
                if (!fileUuid || !fileData) return;
                const cellId = Number(currentCellNumber);
                if (!cellId || !Number.isFinite(cellId)) return;
                requestCellDelete({
                    cellId,
                    fileUuid,
                    fileName: fileData.Image_Name,
                    includeAndItsData: false,
                });
            });
        }

        if (table && contextMenu) {
            table.addEventListener('contextmenu', (event) => {
                const row = event.target.closest('tr');
                if (!row || row.parentNode.tagName === 'THEAD') return;
                const firstCell = row.cells && row.cells[0];
                if (!firstCell) return;
                const cellIdText = firstCell.textContent.trim();
                const cellId = Number(cellIdText);
                if (!Number.isFinite(cellId) || cellId <= 0) return;
                event.preventDefault();
                closeTriggerMenu();
                openContextMenu(event.clientX, event.clientY, cellId);
            });
            contextMenu.addEventListener('click', (event) => {
                const target = event.target.closest('[data-action="delete-row-cell"]');
                if (!target) return;
                const cellId = Number(contextMenu.dataset.cellId);
                closeContextMenu();
                if (!Number.isFinite(cellId) || cellId <= 0) return;
                // The django table is bound to a single file (table_uuid),
                // not the currently-shown cell-pair card file. Always
                // route table-row deletes to that table's file.
                const fileUuid = tableFileUuid || (getCurrentFileData().fileUuid);
                if (!fileUuid) return;
                const fileData = (typeof filesData !== 'undefined' && filesData[fileUuid]) || null;
                requestCellDelete({
                    cellId,
                    fileUuid,
                    fileName: fileData ? fileData.Image_Name : null,
                    includeAndItsData: true,
                });
            });
        }

        cancelBtn.addEventListener('click', closeModal);
        confirmBtn.addEventListener('click', () => { void handleConfirm(); });
        if (selectCellsBackBtn) {
            selectCellsBackBtn.addEventListener('click', closeSelectCellsModal);
        }
        if (selectCellsToggleAllBtn) {
            selectCellsToggleAllBtn.addEventListener('click', () => {
                const checkboxes = getSelectCellsCheckboxes();
                if (!checkboxes.length) return;
                checkboxes.forEach((cb) => {
                    if (cb.checked) return;
                    cb.checked = true;
                    cb.dispatchEvent(new Event('change'));
                });
            });
        }
        if (selectCellsClearBtn) {
            selectCellsClearBtn.addEventListener('click', () => {
                const checkboxes = getSelectCellsCheckboxes();
                if (!checkboxes.length) return;
                checkboxes.forEach((cb) => {
                    if (!cb.checked) return;
                    cb.checked = false;
                    cb.dispatchEvent(new Event('change'));
                });
            });
        }
        if (selectCellsDeleteBtn) {
            selectCellsDeleteBtn.addEventListener('click', () => {
                if (!pendingMultiDelete) return;
                const cellIds = selectedCellIdsArray();
                if (!cellIds.length) return;
                if (confirmMultiCellDeletion) {
                    renderConfirmCellsList(cellIds);
                    switchCellSelectView('confirm', true);
                    return;
                }
                void executeBulkDelete(pendingMultiDelete.fileUuid, cellIds, {
                    fromSelectModal: true,
                });
            });
        }
        if (confirmCellsBackBtn) {
            confirmCellsBackBtn.addEventListener('click', () => {
                switchCellSelectView('select', true);
            });
        }
        if (confirmCellsDeleteBtn) {
            confirmCellsDeleteBtn.addEventListener('click', () => {
                if (!pendingMultiDelete) return;
                const cellIds = selectedCellIdsArray();
                if (!cellIds.length) return;
                void executeBulkDelete(pendingMultiDelete.fileUuid, cellIds, {
                    fromSelectModal: true,
                });
            });
        }
        modalBackdrop.addEventListener('click', (event) => {
            if (event.target === modalBackdrop) {
                closeModal();
            }
        });
        if (selectCellsBackdrop) {
            selectCellsBackdrop.addEventListener('click', (event) => {
                if (event.target === selectCellsBackdrop) {
                    closeSelectCellsModal();
                }
            });
        }

        document.addEventListener('click', (event) => {
            if (triggerMenu && triggerMenu.dataset.open === 'true'
                && !triggerMenu.contains(event.target)
                && event.target !== trigger
                && (!trigger || !trigger.contains(event.target))) {
                closeTriggerMenu();
            }
            if (contextMenu && contextMenu.dataset.open === 'true' && !contextMenu.contains(event.target)) {
                closeContextMenu();
            }
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                closeAllMenus();
                if (deleteCellModal.isOpen()) {
                    closeModal();
                }
                if (selectCellsModal.isOpen()) {
                    if (confirmCellsView && !confirmCellsView.hidden) {
                        switchCellSelectView('select', true);
                    } else {
                        closeSelectCellsModal();
                    }
                }
            }
        });

        const tableScrollFrame = document.getElementById('tableScrollFrame');
        if (tableScrollFrame) {
            tableScrollFrame.addEventListener('scroll', closeContextMenu);
        }
        window.addEventListener('scroll', closeContextMenu, true);
        window.addEventListener('resize', closeAllMenus);
        document.addEventListener('fullscreenchange', () => {
            closeAllMenus();
            if (deleteCellModal.isOpen()) {
                const host = document.fullscreenElement || document.body;
                if (modalBackdrop.parentElement !== host) {
                    host.appendChild(modalBackdrop);
                }
            }
            if (selectCellsModal.isOpen()) {
                const host = document.fullscreenElement || document.body;
                if (selectCellsBackdrop.parentElement !== host) {
                    host.appendChild(selectCellsBackdrop);
                }
            }
        });
    }

    global.CytoCVResultsCellActions = { init };
})(window);
