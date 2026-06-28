        // Dashboard sidebar height is recalculated after transitions/fullscreen so
        // bulk-action controls and export messages stay inside the scroll region.
        (function () {
        function setSidebarScrollHeight() {
            var sidebar = document.getElementById('sidebar');
            if (!sidebar) return;
            var content = sidebar.querySelector('.sidebar-content');
            if (!content) return;
            sidebar.style.maxHeight = '';
            content.style.maxHeight = '';
            content.style.overflowY = '';
            content.style.minHeight = '';
            var hasScrollbar = content.scrollHeight > (content.clientHeight + 1);
            content.classList.toggle('has-scrollbar', hasScrollbar);
            sidebar.classList.toggle('has-scrollbar', hasScrollbar);
        }

        window.addEventListener('load', function () {
            requestAnimationFrame(setSidebarScrollHeight);
            setTimeout(setSidebarScrollHeight, 0);
        });
        window.addEventListener('resize', setSidebarScrollHeight);
        document.addEventListener('fullscreenchange', function () {
            requestAnimationFrame(setSidebarScrollHeight);
            setTimeout(setSidebarScrollHeight, 0);
        });

        var sidebarEl = document.getElementById('sidebar');
        if (sidebarEl) {
            sidebarEl.addEventListener('transitionend', function (e) {
            if (e.propertyName !== 'width') return;
            sidebarEl.classList.remove('is-expanding');
            setSidebarScrollHeight();
            });
        }

        if ('ResizeObserver' in window) {
            var main = document.querySelector('.main-content');
            if (main) new ResizeObserver(setSidebarScrollHeight).observe(main);
            var contentEl = document.querySelector('.sidebar-content');
            if (contentEl) {
                new ResizeObserver(setSidebarScrollHeight).observe(contentEl);
                var fileListEl = contentEl.querySelector('ul');
                if (fileListEl) new ResizeObserver(setSidebarScrollHeight).observe(fileListEl);
            }
        }
        })();
