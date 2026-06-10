        (() => {
            const selectionInfoDots = Array.from(document.querySelectorAll('.selection-info-dot[data-info-text]'));
            const infoTooltipElement = document.getElementById('selectionInfoTooltip');
            let activeInfoAnchor = null;

            if (!selectionInfoDots.length || !infoTooltipElement) {
                return;
            }

            function normalizeInfoText(value) {
                if (typeof value !== 'string') return '';
                return value
                    .split('\n')
                    .map((line) => line.trim())
                    .filter((line, index, arr) => !(line === '' && (index === 0 || index === arr.length - 1)))
                    .join('\n');
            }

            function hideInfoTooltip() {
                activeInfoAnchor = null;
                infoTooltipElement.hidden = true;
                infoTooltipElement.textContent = '';
            }

            function positionInfoTooltip(anchor) {
                if (!anchor) return;
                const rect = anchor.getBoundingClientRect();
                const margin = 10;
                const gap = 8;

                infoTooltipElement.style.left = '0px';
                infoTooltipElement.style.top = '0px';
                const width = infoTooltipElement.offsetWidth;
                const height = infoTooltipElement.offsetHeight;

                let left = rect.left + (rect.width / 2) - (width / 2);
                left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));

                let top = rect.top - height - gap;
                if (top < margin) {
                    top = rect.bottom + gap;
                }
                if (top + height > window.innerHeight - margin) {
                    top = Math.max(margin, window.innerHeight - height - margin);
                }

                infoTooltipElement.style.left = `${Math.round(left)}px`;
                infoTooltipElement.style.top = `${Math.round(top)}px`;
            }

            function refreshInfoTooltipPosition() {
                if (!activeInfoAnchor || infoTooltipElement.hidden) return;
                positionInfoTooltip(activeInfoAnchor);
            }

            function showInfoTooltip(anchor) {
                if (!anchor) return;
                const text = normalizeInfoText(anchor.dataset.infoText || '');
                if (!text) {
                    hideInfoTooltip();
                    return;
                }
                activeInfoAnchor = anchor;
                infoTooltipElement.textContent = text;
                infoTooltipElement.hidden = false;
                positionInfoTooltip(anchor);
            }

            function attachInfoTooltipBehavior(infoDot) {
                infoDot.addEventListener('mouseenter', () => showInfoTooltip(infoDot));
                infoDot.addEventListener('mouseleave', hideInfoTooltip);
                infoDot.addEventListener('click', (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (activeInfoAnchor === infoDot && !infoTooltipElement.hidden) {
                        hideInfoTooltip();
                        return;
                    }
                    showInfoTooltip(infoDot);
                });
            }

            selectionInfoDots.forEach(attachInfoTooltipBehavior);
            document.addEventListener('click', (event) => {
                const target = event.target;
                if (!(target instanceof Element) || !target.classList.contains('selection-info-dot')) {
                    hideInfoTooltip();
                }
            });
            window.addEventListener('resize', refreshInfoTooltipPosition);
            window.addEventListener('scroll', refreshInfoTooltipPosition, true);
        })();
