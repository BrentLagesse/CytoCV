    (() => {
        const meta = document.getElementById('rateLimitMeta');
        const countdownEl = document.getElementById('rateLimitCountdown');
        const banner = document.getElementById('rateLimitBanner');
        const bannerClose = document.getElementById('rateLimitClose');
        if (!meta) return;
        let remaining = parseInt(meta.dataset.remaining || '0', 10);
        if (!Number.isFinite(remaining) || remaining < 0) remaining = 0;
        const updateText = () => {
            const mins = Math.max(0, Math.floor(remaining / 60));
            const seconds = Math.max(0, remaining % 60);
            if (countdownEl) countdownEl.textContent = mins > 0 ? `${mins}m ${seconds}s` : `${seconds}s`;
        };
        updateText();
        const timer = setInterval(() => {
            remaining = Math.max(0, remaining - 1);
            updateText();
            if (remaining <= 0) {
                clearInterval(timer);
                window.location.reload();
            }
        }, 1000);
        if (banner && bannerClose) {
            bannerClose.addEventListener('click', () => banner.remove());
        }
    })();
