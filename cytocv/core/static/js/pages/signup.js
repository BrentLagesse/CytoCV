        // Signup flow keeps server-rendered validation as the source of truth while
        // updating the card with AJAX to preserve form context and resend timers.
        (() => {
            const initResendTimer = (root) => {
                const resendButton = root.querySelector('#resendButton');
                const timer = root.querySelector('#resendTimer');
                const codeInput = root.querySelector('#verify_code');
                const verifyButton = root.querySelector('#verifyButton');
                if (!resendButton || !timer) return;
                let remaining = parseInt(resendButton.dataset.resend || '0', 10);
                if (!Number.isFinite(remaining)) {
                    remaining = 0;
                }
                const update = () => {
                    if (remaining > 0) {
                        resendButton.disabled = true;
                        timer.textContent = `(${remaining}s)`;
                    } else {
                        resendButton.disabled = false;
                        timer.textContent = '';
                    }
                };
                update();
                if (remaining > 0) {
                    const interval = setInterval(() => {
                        remaining = Math.max(0, remaining - 1);
                        update();
                        if (remaining <= 0) {
                            clearInterval(interval);
                        }
                    }, 1000);
                }
                if (codeInput && verifyButton) {
                    codeInput.addEventListener('keydown', (event) => {
                        if (event.key === 'Enter') {
                            event.preventDefault();
                            verifyButton.click();
                        }
                    });
                }
            };

            const syncNoticeToast = (doc) => {
                const newToast = doc.querySelector('.notice-toast');
                const currentToast = document.querySelector('.notice-toast');
                if (newToast) {
                    if (currentToast) {
                        currentToast.replaceWith(newToast);
                    } else {
                        document.body.appendChild(newToast);
                    }
                } else if (currentToast) {
                    currentToast.remove();
                }
            };
            const syncTopMessages = (doc) => {
                const newContainer = doc.querySelector('.auth-message-container');
                const currentContainer = document.querySelector('.auth-message-container');
                if (newContainer) {
                    if (currentContainer) {
                        currentContainer.replaceWith(newContainer);
                    } else {
                        document.body.appendChild(newContainer);
                    }
                    if (typeof window.initializeMessages === 'function') {
                        window.initializeMessages();
                    }
                } else if (currentContainer) {
                    currentContainer.remove();
                }
            };

            const restorePasswords = (card, preserved) => {
                // The server marks which password fields should be cleared after a
                // validation step; the browser only restores fields still allowed.
                const form = card.querySelector('.signup-form');
                if (!form) return;
                const clearPassword = form.dataset.clearPassword === '1';
                const clearConfirm = form.dataset.clearConfirm === '1';
                const passwordInput = form.querySelector('#password');
                const confirmInput = form.querySelector('#verify_password');
                if (passwordInput && !clearPassword) {
                    passwordInput.value = preserved.password || '';
                }
                if (confirmInput) {
                    confirmInput.value = clearConfirm ? '' : (preserved.confirm || '');
                }
            };

            const setCaptchaToken = (form, token) => {
                if (!form || !token) return;
                let tokenInput = form.querySelector('textarea[name="g-recaptcha-response"], input[name="g-recaptcha-response"]');
                if (!tokenInput) {
                    tokenInput = document.createElement('input');
                    tokenInput.type = 'hidden';
                    tokenInput.name = 'g-recaptcha-response';
                    form.appendChild(tokenInput);
                }
                tokenInput.value = token;
            };

            const syncCaptchaResponse = (form) => {
                if (!form || !window.grecaptcha || typeof window.grecaptcha.getResponse !== 'function') {
                    return;
                }
                const token = window.grecaptcha.getResponse();
                if (token) {
                    setCaptchaToken(form, token);
                }
            };

            const autoSubmitCaptchaGate = (token) => {
                // CAPTCHA success resumes the same form submission path so backend
                // rate-limit and verification checks remain centralized.
                const gateMarker = document.querySelector('.signup-form input[name="pass_captcha_gate"]');
                const gateForm = gateMarker ? gateMarker.form : null;
                if (!gateForm) return;
                if (gateForm.dataset.submitting === '1' || gateForm.dataset.recaptchaAutoSubmitted === '1') return;
                setCaptchaToken(gateForm, token);
                gateForm.dataset.recaptchaAutoSubmitted = '1';
                const submitButton =
                    gateForm.querySelector('button.primary-action[type="submit"]') ||
                    gateForm.querySelector('button[type="submit"]');
                if (typeof gateForm.requestSubmit === 'function' && submitButton) {
                    gateForm.requestSubmit(submitButton);
                    return;
                }
                gateForm.submit();
            };

            window.onSignupRecaptchaGateSuccess = (token) => {
                window.setTimeout(() => autoSubmitCaptchaGate(token), 0);
            };

            const initAjaxForm = (root) => {
                // Form replacement expects the response to contain a fresh .signup-card
                // with the same IDs and names used by the Django view.
                const form = root.querySelector('.signup-form');
                if (!form || form.dataset.bound === '1') return;
                form.dataset.bound = '1';
                form.addEventListener('keydown', (event) => {
                    if (event.key !== 'Enter' || event.isComposing) return;
                    const target = event.target;
                    if (!(target instanceof HTMLElement)) return;
                    if (target.tagName === 'TEXTAREA') return;
                    const primary = form.querySelector('.primary-action:not([disabled])');
                    if (!primary || target === primary) return;
                    event.preventDefault();
                    primary.click();
                });
                form.addEventListener('submit', async (event) => {
                    event.preventDefault();
                    if (form.dataset.submitting === '1') {
                        return;
                    }
                    form.dataset.submitting = '1';
                    const currentCard = document.querySelector('.signup-card');
                    if (!currentCard) {
                        form.submit();
                        return;
                    }
                    const preserved = {
                        password: document.getElementById('password')?.value || '',
                        confirm: document.getElementById('verify_password')?.value || '',
                    };
                    const submitter = event.submitter || document.activeElement;
                    if (form.querySelector('input[name="pass_captcha_gate"]')) {
                        syncCaptchaResponse(form);
                    }
                    const formData = new FormData(form);
                    if (submitter && submitter.name) {
                        formData.set(submitter.name, submitter.value || '1');
                    }
                    if (submitter && typeof submitter.disabled === 'boolean') {
                        submitter.disabled = true;
                    }
                    if (submitter && submitter.classList && submitter.classList.contains('btn')) {
                        submitter.classList.add('loading');
                        submitter.setAttribute('aria-busy', 'true');
                    }
                    try {
                        const response = await fetch(form.action || window.location.href, {
                            method: 'POST',
                            body: formData,
                            credentials: 'same-origin',
                            headers: { 'X-Requested-With': 'XMLHttpRequest' },
                        });
                        if (response.redirected) {
                            window.location.href = response.url;
                            return;
                        }
                        const html = await response.text();
                        const doc = new DOMParser().parseFromString(html, 'text/html');
                        const newCard = doc.querySelector('.signup-card');
                        if (!newCard) {
                            window.location.reload();
                            return;
                        }
                        currentCard.replaceWith(newCard);
                        syncNoticeToast(doc);
                        syncTopMessages(doc);
                        initSignupFlow(document);
                        restorePasswords(newCard, preserved);
                    } catch (error) {
                        form.submit();
                    } finally {
                        form.dataset.submitting = '0';
                        if (submitter && typeof submitter.disabled === 'boolean') {
                            submitter.disabled = false;
                        }
                        if (submitter && submitter.classList && submitter.classList.contains('btn')) {
                            submitter.classList.remove('loading');
                            submitter.removeAttribute('aria-busy');
                        }
                    }
                });
            };

            const initSignupFlow = (root) => {
                if (window.grecaptcha && typeof window.grecaptcha.render === 'function') {
                    root.querySelectorAll('.g-recaptcha').forEach((el) => {
                        if (!(el instanceof HTMLElement)) return;
                        if (el.dataset.rendered === '1') return;
                        if (!el.dataset.sitekey) return;
                        if (el.childElementCount > 0) {
                            el.dataset.rendered = '1';
                            return;
                        }
                        const renderOptions = { sitekey: el.dataset.sitekey };
                        const callbackName = el.dataset.callback;
                        if (callbackName && typeof window[callbackName] === 'function') {
                            renderOptions.callback = window[callbackName];
                        }
                        window.grecaptcha.render(el, renderOptions);
                        el.dataset.rendered = '1';
                    });
                }
                initResendTimer(root);
                initAjaxForm(root);
            };

            window.initSignupFlow = initSignupFlow;
            document.addEventListener('DOMContentLoaded', () => initSignupFlow(document));
        })();
