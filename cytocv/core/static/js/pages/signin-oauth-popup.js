    (() => {
        const toast = document.getElementById('oauthErrorToast');
        const close = document.getElementById('oauthErrorClose');
        if (!toast || !close) return;
        close.addEventListener('click', () => toast.remove());
        setTimeout(() => toast.remove(), 7000);
    })();
