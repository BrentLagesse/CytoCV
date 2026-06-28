        // Dashboard AJAX helpers share this cookie-backed CSRF lookup with the
        // saved-file/sidebar controls.
        function getCookie(name) {
            let val = null;
            document.cookie.split(';').forEach(c => {
                c = c.trim();
                if (c.startsWith(name + '=')) {
                    val = decodeURIComponent(c.slice(name.length + 1));
                }
            });
            return val;
        }
