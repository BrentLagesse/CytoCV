        (function () {
            if (window.CytoCVAsyncProgress) return;
            const VIEWPORT_MARGIN = 12;
            const PANEL_GAP = 8;

            function findHost(target) {
                if (!(target instanceof Element)) return null;
                if (target.classList.contains('async-progress-host')) return target;
                return target.closest('.async-progress-host');
            }

            function ensurePanel(host) {
                let panel = host._cytocvAsyncProgressPanel || null;
                if (!panel) {
                    panel = document.createElement('div');
                    panel.className = 'async-progress-panel';
                    panel.setAttribute('role', 'status');
                    panel.setAttribute('aria-live', 'polite');
                    document.body.appendChild(panel);
                    host._cytocvAsyncProgressPanel = panel;
                }
                return panel;
            }

            function wireHost(host) {
                if (host.dataset.progressWired === '1') return;
                host.dataset.progressWired = '1';
                host.addEventListener('mouseenter', () => show(host));
                host.addEventListener('focusin', () => show(host));
                host.addEventListener('mouseleave', () => {
                    if (!host.matches(':focus-within')) hide(host);
                });
                host.addEventListener('focusout', () => {
                    window.setTimeout(() => {
                        if (!host.matches(':hover') && !host.matches(':focus-within')) hide(host);
                    }, 0);
                });
            }

            function clamp(value, minimum, maximum) {
                if (maximum < minimum) return minimum;
                return Math.min(Math.max(value, minimum), maximum);
            }

            function positionPanel(host) {
                const panel = ensurePanel(host);
                const anchor = host.querySelector('button, a') || host;
                const rect = anchor.getBoundingClientRect();
                panel.style.setProperty('--async-progress-panel-min-width', `${Math.ceil(rect.width)}px`);
                panel.style.left = '0px';
                panel.style.top = '0px';

                const panelWidth = panel.offsetWidth;
                const panelHeight = panel.offsetHeight;
                const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
                const anchorCenter = rect.left + (rect.width / 2);
                const left = clamp(
                    anchorCenter - (panelWidth / 2),
                    VIEWPORT_MARGIN,
                    viewportWidth - panelWidth - VIEWPORT_MARGIN,
                );

                let placement = 'top';
                let top = rect.top - panelHeight - PANEL_GAP;
                if (top < VIEWPORT_MARGIN) {
                    placement = 'bottom';
                    top = rect.bottom + PANEL_GAP;
                }
                top = clamp(top, VIEWPORT_MARGIN, viewportHeight - panelHeight - VIEWPORT_MARGIN);
                const arrowLeft = clamp(anchorCenter - left, 16, panelWidth - 16);

                panel.style.left = `${Math.round(left)}px`;
                panel.style.top = `${Math.round(top)}px`;
                panel.style.setProperty('--async-progress-arrow-left', `${Math.round(arrowLeft)}px`);
                panel.dataset.progressPlacement = placement;
            }

            function shouldShow(host) {
                return host.dataset.progressActive === '1' && (
                    host.matches(':hover') ||
                    host.matches(':focus-within') ||
                    host === document.activeElement
                );
            }

            function show(host) {
                if (host.dataset.progressActive !== '1') return;
                const panel = ensurePanel(host);
                positionPanel(host);
                panel.dataset.progressVisible = '1';
            }

            function hide(host) {
                const panel = host._cytocvAsyncProgressPanel;
                if (panel) panel.dataset.progressVisible = '0';
            }

            function repositionVisiblePanels() {
                document.querySelectorAll('.async-progress-host[data-progress-active="1"]').forEach((host) => {
                    if (shouldShow(host)) {
                        show(host);
                    }
                });
            }

            function inferTone(target, host) {
                const button = target instanceof Element && target.matches('button, a')
                    ? target
                    : host.querySelector('button, a');
                if (!button) return 'primary';
                if (
                    button.classList.contains('confirm') ||
                    button.classList.contains('secondary') ||
                    button.classList.contains('back') ||
                    button.classList.contains('cancel')
                ) {
                    return 'neutral';
                }
                return 'primary';
            }

            function cleanText(value) {
                return String(value || '').trim();
            }

            function cleanInt(value) {
                const parsed = Number.parseInt(value, 10);
                return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
            }

            function displayPhase(value) {
                const phase = cleanText(value);
                if (phase.startsWith('Preprocessing Images')) {
                    return phase.replace('Preprocessing Images', 'Processing Images');
                }
                return phase;
            }

            function appendCountLine(lines, label, index, total) {
                if (index === null && total === null) return;
                if (index !== null && total !== null && total > 0) {
                    lines.push(`${label} ${index} of ${total}`);
                } else if (index !== null) {
                    lines.push(`${label} ${index}`);
                } else if (total !== null) {
                    lines.push(`${label} total ${total}`);
                }
            }

            function format(payload) {
                const data = payload && typeof payload === 'object' ? payload : {};
                const phase = displayPhase(data.phase || data.status || '');
                const message = cleanText(data.message);
                const fileName = cleanText(data.fileName);
                const fileIndex = cleanInt(data.fileIndex);
                const fileTotal = cleanInt(data.fileTotal);
                const batchIndex = cleanInt(data.batchIndex);
                const batchTotal = cleanInt(data.batchTotal);
                const cellIndex = cleanInt(data.cellIndex);
                const cellTotal = cleanInt(data.cellTotal);
                const lines = [];

                appendCountLine(lines, 'Batch', batchIndex, batchTotal);
                if (fileIndex !== null || fileTotal !== null || fileName) {
                    let fileLine = '';
                    if (fileIndex !== null && fileTotal !== null && fileTotal > 0) {
                        fileLine = `File ${fileIndex} of ${fileTotal}`;
                    } else if (fileIndex !== null) {
                        fileLine = `File ${fileIndex}`;
                    } else {
                        fileLine = 'File';
                    }
                    if (fileName) fileLine += `: ${fileName}`;
                    lines.push({ text: fileLine, title: fileName });
                }
                appendCountLine(lines, 'Cell', cellIndex, cellTotal);
                if (message && message !== phase) {
                    lines.push(message);
                }

                return {
                    title: phase || message,
                    lines,
                };
            }

            function set(target, payload) {
                const host = findHost(target);
                if (!host) return;
                const panel = ensurePanel(host);
                wireHost(host);
                const tone = inferTone(target, host);
                host.dataset.progressTone = tone;
                panel.dataset.progressTone = tone;
                const formatted = format(payload);
                panel.replaceChildren();
                if (!formatted.title && formatted.lines.length === 0) {
                    clear(target);
                    return;
                }

                const title = document.createElement('span');
                title.className = 'async-progress-title';
                title.textContent = formatted.title || 'Working';
                panel.appendChild(title);

                formatted.lines.forEach((lineValue) => {
                    const line = document.createElement('span');
                    line.className = 'async-progress-line';
                    if (typeof lineValue === 'object' && lineValue !== null) {
                        line.textContent = cleanText(lineValue.text);
                        if (lineValue.title) line.title = cleanText(lineValue.title);
                    } else {
                        line.textContent = cleanText(lineValue);
                    }
                    if (line.textContent) panel.appendChild(line);
                });
                host.dataset.progressActive = '1';
                if (shouldShow(host)) {
                    show(host);
                } else {
                    hide(host);
                }
            }

            function clear(target) {
                const host = findHost(target);
                if (!host) return;
                host.dataset.progressActive = '0';
                delete host.dataset.progressTone;
                const panel = host._cytocvAsyncProgressPanel;
                hide(host);
                if (panel) panel.replaceChildren();
            }

            window.addEventListener('resize', repositionVisiblePanels, { passive: true });
            window.addEventListener('scroll', repositionVisiblePanels, { passive: true, capture: true });

            window.CytoCVAsyncProgress = { set, clear, format };
        })();
