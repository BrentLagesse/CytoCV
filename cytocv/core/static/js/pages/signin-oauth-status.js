    (() => {
        const btn = document.getElementById('loginSubmit');
        if (!btn) return;
        btn.classList.remove('shake');
        void btn.offsetWidth;
        btn.classList.add('shake');
    })();
