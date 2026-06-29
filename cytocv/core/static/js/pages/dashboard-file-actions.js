        // Dashboard saved-file controls coordinate sidebar selection, bulk export, and
        // persisted visibility preferences for server-rendered file rows.
        (() => {
            // These IDs and data attributes are rendered by dashboard.html and are also
            // covered by frontend contract tests.
            const sidebar = document.getElementById('sidebar');
            const fileItems = Array.from(document.querySelectorAll('.file-item[data-uuid]'));
            const fileUUIDs = fileItems.map((item) => item.dataset.uuid).filter(Boolean);
            const selectModeBtn = document.getElementById('selectModeBtn');
            const selectAllBtn = document.getElementById('selectAllBtn');
            const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
            const downloadSelectedBtn = document.getElementById('downloadSelectedBtn');
            const channelVisibilityBtn = document.getElementById('toggleChannelVisibilityBtn');
            const scaleVisibilityBtn = document.getElementById('toggleScaleVisibilityBtn');
            const deleteBackdrop = document.getElementById('deleteFilesBackdrop');
            const deleteMessage = document.getElementById('deleteFilesMessage');
            const deleteList = document.getElementById('deleteFilesList');
            const deleteStatus = document.getElementById('deleteFilesStatus');
            const cancelDeleteFilesBtn = document.getElementById('cancelDeleteFilesBtn');
            const confirmDeleteFilesBtn = document.getElementById('confirmDeleteFilesBtn');

            if (
                !sidebar || !selectModeBtn || !selectAllBtn || !deleteSelectedBtn
                || !downloadSelectedBtn || !channelVisibilityBtn || !scaleVisibilityBtn
            ) {
                return;
            }

            const selectedFileUUIDs = new Set();
            let selectModeActive = false;
            const csrfToken = getCookie('csrftoken');
            let channelLabelFadeTimer = null;
            let scaleLabelFadeTimer = null;
            let isDeletingFiles = false;

            // Dashboard actions use fetch POSTs, so CSRF remains cookie-backed instead
            // of embedding a token in each control.
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

            // Keep sidebar-specific errors visually near the controls while reusing the
            // same message markup expected by the shared CSS.
            function showMessage(message) {
                let container = document.querySelector('.message-container.channel-switch');
                if (!container) {
                    container = document.createElement('div');
                    container.className = 'message-container channel-switch';
                    container.style.top = 'calc(var(--nav-height) + 8px)';
                    document.body.appendChild(container);
                }
                const msg = document.createElement('div');
                msg.className = 'message';
                msg.textContent = message;
                const close = document.createElement('button');
                close.type = 'button';
                close.className = 'message-close';
                close.innerHTML = '&times;';
                close.addEventListener('click', () => msg.remove());
                msg.appendChild(close);
                container.appendChild(msg);
                setTimeout(() => msg.remove(), 7000);
            }

            // Selection state is local to the dashboard page; export/delete endpoints
            // still perform ownership checks server-side.
            function syncSelectionUI() {
                fileItems.forEach((item) => item.classList.toggle('selected', selectedFileUUIDs.has(item.dataset.uuid)));
                deleteSelectedBtn.disabled = selectedFileUUIDs.size === 0;
                downloadSelectedBtn.disabled = selectedFileUUIDs.size === 0;
                downloadSelectedBtn.title = downloadSelectedBtn.disabled
                    ? 'Select files first.'
                    : 'Download selected files.';
            }

            function setSelectMode(enabled) {
                selectModeActive = enabled;
                sidebar.classList.toggle('select-mode', enabled);
                selectModeBtn.classList.toggle('active', enabled);
                selectModeBtn.textContent = enabled ? 'Done' : 'Select';
                if (!enabled) {
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

            // Channel and scale visibility are immediate UI preferences. Persistence is
            // best-effort so a failed preference save does not block browsing saved files.
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

            // The modal lists selected display names, but deletion is keyed only by UUIDs
            // submitted to the dashboard delete endpoint.
            function setDeleteLoading(isLoading) {
                isDeletingFiles = isLoading;
                if (confirmDeleteFilesBtn) {
                    const label = confirmDeleteFilesBtn.querySelector('.btn-label');
                    confirmDeleteFilesBtn.disabled = isLoading;
                    confirmDeleteFilesBtn.classList.toggle('loading', isLoading);
                    if (isLoading) {
                        confirmDeleteFilesBtn.setAttribute('aria-busy', 'true');
                    } else {
                        confirmDeleteFilesBtn.removeAttribute('aria-busy');
                    }
                    if (label) {
                        label.textContent = isLoading ? 'Deleting' : 'Confirm Delete';
                    }
                }
                if (cancelDeleteFilesBtn) {
                    cancelDeleteFilesBtn.disabled = isLoading;
                }
                if (deleteStatus) {
                    deleteStatus.textContent = isLoading ? 'Deleting selected files...' : '';
                    deleteStatus.classList.toggle('is-visible', isLoading);
                }
            }

            function closeDeleteModal() {
                if (isDeletingFiles) return;
                if (!deleteBackdrop) return;
                deleteBackdrop.style.display = 'none';
                deleteBackdrop.setAttribute('aria-hidden', 'true');
            }

            function openDeleteModal() {
                if (!deleteBackdrop || !deleteMessage || !deleteList) return;
                setDeleteLoading(false);
                const selected = fileUUIDs.filter((uuid) => selectedFileUUIDs.has(uuid)).map((uuid) => {
                    const row = fileItems.find((item) => item.dataset.uuid === uuid);
                    const title = row ? row.querySelector('.file-title') : null;
                    return title ? title.textContent.trim() : uuid;
                });
                if (!selected.length) return;
                deleteMessage.textContent = selected.length === fileUUIDs.length
                    ? 'Are you sure you want to delete all your saved files?'
                    : 'Are you sure you want to delete the selected files?';
                deleteList.innerHTML = '';
                selected.forEach((name) => {
                    const li = document.createElement('li');
                    li.textContent = name;
                    deleteList.appendChild(li);
                });
                deleteBackdrop.style.display = 'flex';
                deleteBackdrop.setAttribute('aria-hidden', 'false');
            }

            async function deleteSelectedFiles() {
                if (isDeletingFiles) return;
                const uuids = Array.from(selectedFileUUIDs);
                if (!uuids.length) return;
                setDeleteLoading(true);
                try {
                    // The server revalidates ownership and returns stale-selection
                    // errors; the client never removes rows optimistically.
                    const response = await fetch('/dashboard/files/delete/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken || '',
                        },
                        credentials: 'same-origin',
                        body: JSON.stringify({ uuids }),
                    });
                    const payload = await response.json();
                    if (!response.ok) {
                        throw new Error(payload.error || 'Delete failed');
                    }
                    // Reload after deletion so quota cards, sidebar counts, viewer
                    // selection, and export state all come from one fresh payload.
                    window.location.reload();
                } catch (err) {
                    setDeleteLoading(false);
                    showMessage(err.message || 'Unable to delete selected files.');
                }
            }

            // Event handlers preserve the sidebar's normal navigation until explicit
            // select mode is active.
            selectModeBtn.addEventListener('click', () => setSelectMode(!selectModeActive));
            selectAllBtn.addEventListener('click', toggleSelectAll);
            deleteSelectedBtn.addEventListener('click', openDeleteModal);
            downloadSelectedBtn.addEventListener('click', () => {
                if (!window.dashboardExportSelectionController || selectedFileUUIDs.size === 0) {
                    return;
                }
                window.dashboardExportSelectionController.openFiles(
                    fileUUIDs.filter((uuid) => selectedFileUUIDs.has(uuid))
                );
            });
            channelVisibilityBtn.addEventListener('click', () => {
                applyChannelVisibility(sidebar.classList.contains('channels-hidden'), true);
            });
            scaleVisibilityBtn.addEventListener('click', () => {
                applyScaleVisibility(sidebar.classList.contains('scales-hidden'), true);
            });

            fileItems.forEach((item) => {
                const uuid = item.dataset.uuid;
                const checkbox = item.querySelector('.file-select-check');
                if (checkbox && uuid) {
                    // Checkbox clicks only mutate local selection. Navigation and
                    // destructive effects stay behind explicit toolbar actions.
                    checkbox.addEventListener('click', (event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        if (!selectModeActive) return;
                        if (selectedFileUUIDs.has(uuid)) {
                            selectedFileUUIDs.delete(uuid);
                        } else {
                            selectedFileUUIDs.add(uuid);
                        }
                        syncSelectionUI();
                    });
                }
                item.addEventListener('click', () => {
                    if (!selectModeActive || !uuid) return;
                    if (selectedFileUUIDs.has(uuid)) {
                        selectedFileUUIDs.delete(uuid);
                    } else {
                        selectedFileUUIDs.add(uuid);
                    }
                    syncSelectionUI();
                });
            });

            if (cancelDeleteFilesBtn) cancelDeleteFilesBtn.addEventListener('click', closeDeleteModal);
            if (confirmDeleteFilesBtn) confirmDeleteFilesBtn.addEventListener('click', deleteSelectedFiles);
            if (deleteBackdrop) {
                deleteBackdrop.addEventListener('click', (event) => {
                    if (isDeletingFiles) return;
                    if (event.target === deleteBackdrop) closeDeleteModal();
                });
            }
            document.addEventListener('keydown', (event) => {
                if (isDeletingFiles) return;
                if (event.key === 'Escape' && deleteBackdrop && deleteBackdrop.style.display === 'flex') {
                    closeDeleteModal();
                }
            });

            applyChannelVisibility(!sidebar.classList.contains('channels-hidden'), false);
            applyScaleVisibility(!sidebar.classList.contains('scales-hidden'), false);
            syncSelectionUI();
        })();
