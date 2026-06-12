        // Reload from server when restored from the back-forward cache so the
        // table reflects the latest CellStatistics state instead of a stale snapshot.
        window.addEventListener('pageshow', (event) => {
            if (event.persisted) {
                window.location.reload();
            }
        });
