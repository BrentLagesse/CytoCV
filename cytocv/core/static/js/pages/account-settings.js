    (() => {
        const backdrop = document.getElementById('deleteAccountBackdrop');
        const openButton = document.getElementById('openDeleteAccountModal');
        const cancelButton = document.getElementById('cancelDeleteAccount');
        const emailInput = document.getElementById('confirmDeleteEmail');
        if (!backdrop || !openButton || !cancelButton || !emailInput) {
            return;
        }

        const openModal = () => {
            backdrop.style.display = 'flex';
            backdrop.setAttribute('aria-hidden', 'false');
            window.setTimeout(() => {
                emailInput.focus();
            }, 0);
        };
        const closeModal = () => {
            backdrop.style.display = 'none';
            backdrop.setAttribute('aria-hidden', 'true');
            emailInput.value = '';
        };

        openButton.addEventListener('click', openModal);
        cancelButton.addEventListener('click', closeModal);
        backdrop.addEventListener('click', (event) => {
            if (event.target === backdrop) {
                closeModal();
            }
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && backdrop.style.display === 'flex') {
                closeModal();
            }
        });

        let config = {};
        const configElement = document.getElementById('accountSettingsConfig');
        try {
            config = JSON.parse(configElement ? configElement.textContent || '{}' : '{}');
        } catch (err) {
            config = {};
        }

        if (config.openDeleteModal) {
            openModal();
            emailInput.value = '';
        }
    })();
