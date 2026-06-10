      (function () {
        function clampSidebar() {
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
          requestAnimationFrame(clampSidebar);
          setTimeout(clampSidebar, 0);
        });
        window.addEventListener('resize', clampSidebar);
        document.addEventListener('fullscreenchange', function () {
          requestAnimationFrame(clampSidebar);
          setTimeout(clampSidebar, 0);
        });

        var sidebarEl = document.getElementById('sidebar');
        if (sidebarEl) {
          sidebarEl.addEventListener('transitionend', function (e) {
            if (e.propertyName !== 'width') return;
            sidebarEl.classList.remove('is-expanding');
            clampSidebar();
          });
        }

        if ('ResizeObserver' in window) {
          var main = document.querySelector('.main-content');
          if (main) new ResizeObserver(clampSidebar).observe(main);
          var contentEl = document.querySelector('.sidebar-content');
          if (contentEl) {
            new ResizeObserver(clampSidebar).observe(contentEl);
            var fileListEl = contentEl.querySelector('ul');
            if (fileListEl) new ResizeObserver(clampSidebar).observe(fileListEl);
          }
        }
      })();
