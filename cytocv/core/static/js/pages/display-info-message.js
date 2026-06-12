        (function () {
            const raw = sessionStorage.getItem('cytocvDisplayInfoMessage');
            if (!raw) return;
            let payload = {};
            try {
                payload = JSON.parse(raw || '{}') || {};
            } catch (err) {
                sessionStorage.removeItem('cytocvDisplayInfoMessage');
                return;
            }
            sessionStorage.removeItem('cytocvDisplayInfoMessage');
            if (!payload.message || !window.showGlobalMessage) return;
            window.showGlobalMessage(payload.message, payload.tone || 'warning', {
                scope: 'analysis-warning',
                top: 'calc(var(--nav-height) + 8px)',
                timeoutMs: 8000,
            });
        })();
