    (() => {
        const button = document.getElementById('verifiedCheckButton');
        const statusEl = document.getElementById('verificationStatus');
        if (!button || !statusEl) {
            return;
        }

        const statusUrl = button.dataset.statusUrl;
        const setStatus = (message) => {
            statusEl.textContent = message || '';
        };
        const checkStatus = async (manual = false) => {
            if (!statusUrl) {
                return;
            }
            if (manual) {
                button.disabled = true;
                setStatus('Checking verification status...');
            }
            try {
                const response = await fetch(statusUrl, {
                    method: 'GET',
                    credentials: 'same-origin',
                    headers: {
                        'Accept': 'application/json',
                    },
                    cache: 'no-store',
                });
                if (!response.ok) {
                    throw new Error('status check failed');
                }
                const payload = await response.json();
                if (payload.authenticated && payload.redirect_url) {
                    window.location.assign(payload.redirect_url);
                    return;
                }
                if (manual) {
                    setStatus('We are still waiting for verification to complete. Open the newest email link in this same browser session, then try again. If you opened it elsewhere, return to sign in again.');
                }
            } catch (error) {
                if (manual) {
                    setStatus('Unable to check right now. Try again in a moment.');
                }
            } finally {
                if (manual) {
                    button.disabled = false;
                }
            }
        };

        button.addEventListener('click', () => {
            void checkStatus(true);
        });
        setInterval(() => {
            void checkStatus(false);
        }, 4000);
        void checkStatus(false);
    })();
