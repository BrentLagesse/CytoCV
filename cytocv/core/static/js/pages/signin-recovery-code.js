    // Login recovery CAPTCHA mirrors the signup gate: the token is injected into
    // the same form the Django view already validates.
    (() => {
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
            if (!form || !window.grecaptcha || typeof window.grecaptcha.getResponse !== 'function') return;
            const token = window.grecaptcha.getResponse();
            if (token) {
                setCaptchaToken(form, token);
            }
        };

        const submitCaptchaGate = (token) => {
            const gateMarker = document.querySelector('form input[name="pass_captcha_gate"]');
            const gateForm = gateMarker ? gateMarker.form : null;
            if (!gateForm) return;
            if (gateForm.dataset.recaptchaAutoSubmitted === '1') return;
            setCaptchaToken(gateForm, token);
            gateForm.dataset.recaptchaAutoSubmitted = '1';
            const submitButton = document.getElementById('captchaGateContinue') || gateForm.querySelector('button[type="submit"]');
            if (typeof gateForm.requestSubmit === 'function' && submitButton) {
                gateForm.requestSubmit(submitButton);
                return;
            }
            gateForm.submit();
        };

        window.onLoginRecaptchaGateSuccess = (token) => {
            window.setTimeout(() => submitCaptchaGate(token), 0);
        };

        const gateMarker = document.querySelector('form input[name="pass_captcha_gate"]');
        const gateForm = gateMarker ? gateMarker.form : null;
        if (gateForm) {
            gateForm.addEventListener('submit', () => {
                syncCaptchaResponse(gateForm);
            });
        }
    })();
