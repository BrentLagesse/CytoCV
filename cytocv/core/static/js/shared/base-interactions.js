        // Shared navigation and message interactions used by Django-rendered pages.
        (() => {
            // Runtime-created containers keep AJAX/page-controller errors consistent
            // with server-rendered flash messages.
            const ensureMessageContainer = (scope = 'global', top = 'calc(var(--nav-height) + 12px)') => {
                let container = document.querySelector(`.message-container[data-scope="${scope}"]`);
                if (container) {
                    return container;
                }
                if (scope === 'global') {
                    container = document.querySelector('.message-container');
                    if (container && !container.dataset.scope) {
                        container.dataset.scope = scope;
                    }
                    if (container) {
                        return container;
                    }
                }

                container = document.createElement('div');
                container.className = 'message-container';
                container.dataset.scope = scope;
                container.style.top = top;
                document.body.appendChild(container);
                return container;
            };

            const createMessageElement = (message, tone = 'error') => {
                const msg = document.createElement('div');
                msg.className = tone === 'success' ? 'message success' : 'message';
                msg.style.whiteSpace = 'pre-line';
                msg.textContent = String(message ?? '').trim();
                const close = document.createElement('button');
                close.type = 'button';
                close.className = 'message-close';
                close.setAttribute('aria-label', 'Dismiss');
                close.innerHTML = '&times;';
                close.addEventListener('click', () => msg.remove());
                msg.appendChild(close);
                return msg;
            };

            // Page scripts depend on these globals for scoped, de-duplicated error and
            // success messages without importing a module bundle.
            window.showGlobalMessage = (message, tone = 'error', options = {}) => {
                const normalized = String(message ?? '').trim();
                if (!normalized) {
                    return null;
                }
                const {
                    scope = 'global',
                    top = 'calc(var(--nav-height) + 12px)',
                    timeoutMs = 7000,
                    dedupe = true,
                } = options;
                const container = ensureMessageContainer(scope, top);
                const dedupeKey = `${tone}|${normalized}`;
                if (dedupe) {
                    const existing = Array.from(container.querySelectorAll('.message')).find(
                        (item) => item.dataset.messageKey === dedupeKey
                    );
                    if (existing) {
                        existing.remove();
                    }
                }
                const msg = createMessageElement(normalized, tone);
                msg.dataset.messageKey = dedupeKey;
                container.appendChild(msg);
                if (timeoutMs > 0) {
                    window.setTimeout(() => msg.remove(), timeoutMs);
                }
                return msg;
            };

            window.showGlobalMessages = (messages, tone = 'error', options = {}) => {
                if (!Array.isArray(messages)) {
                    return null;
                }
                const normalized = messages
                    .map((item) => String(item ?? '').trim())
                    .filter((item) => item);
                if (!normalized.length) {
                    return null;
                }
                return window.showGlobalMessage(normalized.join('\n'), tone, options);
            };

            window.clearGlobalMessages = (options = {}) => {
                const { scope = 'global' } = options;
                const container = document.querySelector(`.message-container[data-scope="${scope}"]`)
                    || (scope === 'global' ? document.querySelector('.message-container') : null);
                if (!container) {
                    return 0;
                }
                const messages = Array.from(container.querySelectorAll('.message'));
                messages.forEach((msg) => msg.remove());
                if (scope !== 'global' && !container.querySelector('.message')) {
                    container.remove();
                }
                return messages.length;
            };
        })();

        document.addEventListener('DOMContentLoaded', () => {
            // Normalize server-rendered messages by adding dismiss buttons and enforcing
            // the same duplicate handling used by client-created messages.
            const initializeMessages = () => {
                const messages = Array.from(document.querySelectorAll('.message-container .message'));
                const seen = new Set();
                messages.forEach((msg) => {
                    const key = `${msg.className}|${msg.textContent.trim()}`;
                    if (seen.has(key)) {
                        msg.remove();
                        return;
                    }
                    seen.add(key);
                    if (!msg.querySelector('.message-close')) {
                        const close = document.createElement('button');
                        close.type = 'button';
                        close.className = 'message-close';
                        close.setAttribute('aria-label', 'Dismiss');
                        close.innerHTML = '&times;';
                        close.addEventListener('click', () => msg.remove());
                        msg.appendChild(close);
                    }
                    if (msg.classList.contains('auto-dismiss') && msg.dataset.autoDismissScheduled !== '1') {
                        msg.dataset.autoDismissScheduled = '1';
                        setTimeout(() => {
                            msg.remove();
                        }, 15000);
                    }
                });
            };

            window.initializeMessages = initializeMessages;
            initializeMessages();

            const logoutLink = document.getElementById('logoutLink');
            const logoutBackdrop = document.getElementById('logoutBackdrop');
            const logoutCancel = document.getElementById('logoutCancel');
            const logoutConfirm = document.getElementById('logoutConfirm');
            const logoutPanel = logoutBackdrop ? logoutBackdrop.querySelector('.logout-modal') : null;
            const aboutNavMenu = document.getElementById('aboutNavMenu');
            const aboutNavToggle = document.getElementById('aboutNavToggle');
            const aboutNavPanel = document.getElementById('aboutNavPanel');
            const accountMenu = document.getElementById('accountMenu');
            const accountMenuToggle = document.getElementById('accountMenuToggle');
            const accountMenuPanel = document.getElementById('accountMenuPanel');

            // The about/account dropdowns are optional because many templates share
            // this script without rendering both navigation regions.
            const closeAboutNavMenu = () => {
                if (!aboutNavMenu || !aboutNavToggle) {
                    return;
                }
                aboutNavMenu.classList.remove('is-open');
                aboutNavToggle.setAttribute('aria-expanded', 'false');
            };

            if (aboutNavMenu && aboutNavToggle && aboutNavPanel) {
                aboutNavToggle.addEventListener('click', (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    const isOpen = aboutNavMenu.classList.toggle('is-open');
                    aboutNavToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
                });

                document.addEventListener('click', (event) => {
                    if (!aboutNavMenu.contains(event.target)) {
                        closeAboutNavMenu();
                    }
                });

                aboutNavPanel.addEventListener('click', () => {
                    closeAboutNavMenu();
                });
            }

            const closeAccountMenu = () => {
                if (!accountMenu || !accountMenuToggle) {
                    return;
                }
                accountMenu.classList.remove('is-open');
                accountMenuToggle.setAttribute('aria-expanded', 'false');
            };

            if (accountMenu && accountMenuToggle && accountMenuPanel) {
                accountMenuToggle.addEventListener('click', (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    const isOpen = accountMenu.classList.toggle('is-open');
                    accountMenuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
                });

                document.addEventListener('click', (event) => {
                    if (!accountMenu.contains(event.target)) {
                        closeAccountMenu();
                    }
                });

                accountMenuPanel.addEventListener('click', () => {
                    closeAccountMenu();
                });
            }

            let closeLogoutModal = null;

            if (logoutLink && logoutBackdrop && logoutCancel && logoutConfirm) {
                const MODAL_ENTER_MS = 170;
                const MODAL_EXIT_MS = 120;
                const prefersReducedMotion = !!(
                    window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
                );
                // Logout can become a job-cancel action on analysis pages, so the modal
                // reads the shared analysis-running globals before it submits navigation.
                const clearModalAnim = () => {
                    logoutBackdrop.classList.remove('modal-enter', 'modal-exit');
                    if (logoutPanel) {
                        logoutPanel.classList.remove('modal-enter', 'modal-exit');
                    }
                };

                const openLogoutModal = () => {
                    const titleEl = document.getElementById('logoutTitle');
                    const bodyEl = document.querySelector('.logout-modal-body');
                    if (window.isAnalysisRunning && titleEl && bodyEl) {
                        titleEl.textContent = 'Log out and cancel analysis?';
                        bodyEl.textContent = 'Analysis is currently running. Logging out will cancel the analysis. Are you sure you want to log out?';
                    } else if (titleEl && bodyEl) {
                        titleEl.textContent = 'Confirm Log Out';
                        bodyEl.textContent = 'Are you sure you want to log out?';
                    }
                    clearModalAnim();
                    logoutBackdrop.style.display = 'flex';
                    logoutBackdrop.setAttribute('aria-hidden', 'false');
                    if (!prefersReducedMotion) {
                        void logoutBackdrop.offsetWidth;
                        logoutBackdrop.classList.add('modal-enter');
                        if (logoutPanel) {
                            logoutPanel.classList.add('modal-enter');
                        }
                        window.setTimeout(clearModalAnim, MODAL_ENTER_MS);
                    }
                };
                closeLogoutModal = () => {
                    if (prefersReducedMotion || logoutBackdrop.style.display !== 'flex') {
                        clearModalAnim();
                        logoutBackdrop.style.display = 'none';
                        logoutBackdrop.setAttribute('aria-hidden', 'true');
                        return;
                    }
                    clearModalAnim();
                    logoutBackdrop.classList.add('modal-exit');
                    if (logoutPanel) {
                        logoutPanel.classList.add('modal-exit');
                    }
                    logoutBackdrop.setAttribute('aria-hidden', 'true');
                    window.setTimeout(() => {
                        clearModalAnim();
                        logoutBackdrop.style.display = 'none';
                    }, MODAL_EXIT_MS);
                };

                logoutLink.addEventListener('click', (event) => {
                    event.preventDefault();
                    openLogoutModal();
                });
                logoutConfirm.addEventListener('click', async (event) => {
                    if (window.requestAnalysisCancel && window.isAnalysisRunning) {
                        event.preventDefault();
                        logoutConfirm.classList.add('loading');
                        logoutConfirm.style.pointerEvents = 'none';
                        logoutConfirm.setAttribute('aria-disabled', 'true');
                        const label = logoutConfirm.querySelector('.btn-label');
                        if (label) {
                            label.textContent = 'Logging out';
                        }
                        const logoutHref = logoutConfirm.getAttribute('href');
                        const timeoutMs = 10000;
                        try {
                            const timeoutPromise = new Promise((resolve) => {
                                setTimeout(resolve, timeoutMs);
                            });
                            await Promise.race([window.requestAnalysisCancel(), timeoutPromise]);
                        } catch (error) {
                            if (window.console && typeof window.console.error === 'function') {
                                console.error('Cancel before logout failed.', error);
                            }
                        } finally {
                            if (logoutHref) {
                                window.location.href = logoutHref;
                            }
                        }
                    }
                });
                logoutCancel.addEventListener('click', () => {
                    if (closeLogoutModal) {
                        closeLogoutModal();
                    }
                });
                logoutBackdrop.addEventListener('click', (event) => {
                    if (event.target === logoutBackdrop && closeLogoutModal) {
                        closeLogoutModal();
                    }
                });
            }

            document.addEventListener('keydown', (event) => {
                if (event.key === 'Escape') {
                    closeAboutNavMenu();
                    closeAccountMenu();
                    if (closeLogoutModal) {
                        closeLogoutModal();
                    }
                }
            });
        });
