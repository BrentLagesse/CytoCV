    // License back navigation prefers a same-origin referrer and falls back to
    // Home so the page does not send users outside CytoCV.
    (function () {
        const backLink = document.getElementById('licenseBackLink');
        if (!backLink) return;

        const homeUrl = backLink.dataset.homeUrl || '/';
        const licensePath = backLink.dataset.licensePath || '/license/';
        const referrer = document.referrer;

        if (!referrer) {
            backLink.href = homeUrl;
            return;
        }

        try {
            const referrerUrl = new URL(referrer);
            if (referrerUrl.origin !== window.location.origin) {
                backLink.href = homeUrl;
                return;
            }

            if (referrerUrl.pathname === licensePath) {
                backLink.href = homeUrl;
                return;
            }

            backLink.href = `${referrerUrl.pathname}${referrerUrl.search}${referrerUrl.hash}`;
        } catch (error) {
            backLink.href = homeUrl;
        }
    }());
