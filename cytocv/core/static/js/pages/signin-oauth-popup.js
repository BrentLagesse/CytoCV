    // OAuth error toasts are rendered by the login template and self-dismiss on
    // the client so the backend response stays a plain page render.
    (() => {
        const toast = document.getElementById('oauthErrorToast');
        const close = document.getElementById('oauthErrorClose');
        if (!toast || !close) return;
        close.addEventListener('click', () => toast.remove());
        setTimeout(() => toast.remove(), 7000);
    })();
