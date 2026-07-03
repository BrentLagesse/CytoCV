    // Login status feedback replays the button animation after the server marks
    // the attempt as failed.
    (() => {
        const btn = document.getElementById('loginSubmit');
        if (!btn) return;
        btn.classList.remove('shake');
        void btn.offsetWidth;
        btn.classList.add('shake');
    })();
