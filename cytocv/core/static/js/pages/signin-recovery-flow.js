    // Recovery-code verification keeps submission server-rendered while adding
    // resend timers, enter-key affordances, and a duplicate-submit guard.
    (() => {
        const form = document.querySelector('.recovery-form');
        if (!form) return;

        const resendButton = document.getElementById('recoveryResendButton');
        const timer = document.getElementById('recoveryResendTimer');
        const codeInput = document.getElementById('recovery_verify_code');
        const verifyButton = document.getElementById('recoveryVerifyButton');

        if (resendButton && timer) {
            let remaining = parseInt(resendButton.dataset.resend || '0', 10);
            if (!Number.isFinite(remaining)) remaining = 0;
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
                    if (remaining <= 0) clearInterval(interval);
                }, 1000);
            }
        }

        if (codeInput && verifyButton) {
            codeInput.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    verifyButton.click();
                }
            });
        }

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

        form.addEventListener('submit', (event) => {
            if (form.dataset.submitting === '1') {
                event.preventDefault();
                return;
            }
            form.dataset.submitting = '1';
            const submitter = event.submitter;
            if (!submitter) return;
            if (submitter.dataset.spinner === '1') {
                submitter.classList.add('loading');
            }
        });
    })();
