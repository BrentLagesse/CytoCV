    // Login submit locking is client-side affordance only; the backend still owns
    // credential validation and throttling.
    (() => {
        const form = document.querySelector('.login-form');
        const submit = document.getElementById('loginSubmit');
        if (!form || !submit) return;
        let submitted = false;
        form.addEventListener('submit', (event) => {
            if (submitted) {
                event.preventDefault();
                return;
            }
            submitted = true;
            submit.disabled = true;
            submit.classList.add('loading');
        });
    })();
