    // Home page interactions are intentionally standalone because CytoCV serves
    // Django templates without a frontend build bundle.
    const uploadImageButton = document.getElementById('uploadImageButton');
    if (uploadImageButton) {
        uploadImageButton.addEventListener('click', function () {
            uploadImageButton.classList.add('loading');
            uploadImageButton.style.pointerEvents = 'none';
            uploadImageButton.style.cursor = 'not-allowed';
            uploadImageButton.setAttribute('aria-busy', 'true');
        });
    }

    const homeLayout = document.querySelector('.home-layout');
    const homeDivider = document.getElementById('homeDivider');
    if (homeLayout && homeDivider) {
        // The desktop divider writes a single CSS custom property; mobile layout
        // falls back to stylesheet-defined stacking.
        let dragging = false;
        let pendingClientX = null;
        let resizeFrame = 0;
        let resizeCooldownTimer = 0;
        const minLeft = 280;
        const minRight = 240;
        const minLeftRatio = 0.3;
        const minRightRatio = 0.25;
        const resizeCooldownMs = 180;
        const getGap = () => {
            const styles = getComputedStyle(homeLayout);
            const columnGap = styles.columnGap || styles.gap || '0px';
            const gapValue = parseFloat(columnGap);
            return Number.isNaN(gapValue) ? 0 : gapValue;
        };
        const setResizeState = (isResizing) => {
            homeLayout.classList.toggle('is-resizing', isResizing);
        };
        const clearResizeCooldown = () => {
            if (resizeCooldownTimer) {
                window.clearTimeout(resizeCooldownTimer);
                resizeCooldownTimer = 0;
            }
        };
        const scheduleResizeCooldown = () => {
            clearResizeCooldown();
            resizeCooldownTimer = window.setTimeout(() => {
                setResizeState(false);
                resizeCooldownTimer = 0;
            }, resizeCooldownMs);
        };

        const getColumnBounds = () => {
            // Bounds combine fixed minimums and proportional minimums so the two
            // home columns stay readable across wide desktop sizes.
            const rect = homeLayout.getBoundingClientRect();
            const dividerWidth = homeDivider.offsetWidth;
            const gap = getGap();
            const rawAvailable = rect.width - dividerWidth - gap * 2;
            const baseAvailable = Math.max(rawAvailable, minLeft + minRight);
            const effectiveMinLeft = Math.max(minLeft, baseAvailable * minLeftRatio);
            const effectiveMinRight = Math.max(minRight, baseAvailable * minRightRatio);
            const available = Math.max(baseAvailable, effectiveMinLeft + effectiveMinRight);
            return {
                rect,
                dividerWidth,
                gap,
                minLeft: effectiveMinLeft,
                maxLeft: available - effectiveMinRight,
            };
        };

        const clampColumns = () => {
            if (window.matchMedia('(max-width: 900px)').matches) {
                homeLayout.style.removeProperty('--left-width');
                setResizeState(false);
                return;
            }
            const currentValue = homeLayout.style.getPropertyValue('--left-width').trim();
            if (!currentValue) {
                return;
            }
            const { minLeft, maxLeft } = getColumnBounds();
            const current = parseFloat(currentValue);
            if (Number.isNaN(current)) {
                return;
            }
            const safeLeft = Math.max(minLeft, Math.min(current, maxLeft));
            homeLayout.style.setProperty('--left-width', `${safeLeft}px`);
        };

        const updateColumns = (clientX) => {
            const { rect, dividerWidth, gap, minLeft, maxLeft } = getColumnBounds();
            const nextLeft = Math.max(minLeft, Math.min(clientX - rect.left - gap - dividerWidth / 2, maxLeft));
            homeLayout.style.setProperty('--left-width', `${nextLeft}px`);
        };
        const flushPendingResize = () => {
            resizeFrame = 0;
            if (pendingClientX === null) {
                return;
            }
            updateColumns(pendingClientX);
            pendingClientX = null;
        };
        const scheduleColumnUpdate = (clientX) => {
            pendingClientX = clientX;
            if (resizeFrame) {
                return;
            }
            resizeFrame = window.requestAnimationFrame(flushPendingResize);
        };
        const finishDragging = (event) => {
            if (!dragging) return;
            dragging = false;
            homeDivider.classList.remove('dragging');
            if (resizeFrame) {
                window.cancelAnimationFrame(resizeFrame);
                flushPendingResize();
            }
            clampColumns();
            scheduleResizeCooldown();
            if (homeDivider.releasePointerCapture) {
                homeDivider.releasePointerCapture(event.pointerId);
            }
        };

        homeDivider.addEventListener('pointerdown', (event) => {
            if (window.matchMedia('(max-width: 900px)').matches) return;
            event.preventDefault();
            dragging = true;
            clearResizeCooldown();
            setResizeState(true);
            homeDivider.classList.add('dragging');
            if (homeDivider.setPointerCapture) {
                homeDivider.setPointerCapture(event.pointerId);
            }
            scheduleColumnUpdate(event.clientX);
        });

        homeDivider.addEventListener('pointermove', (event) => {
            if (!dragging) return;
            scheduleColumnUpdate(event.clientX);
        });

        homeDivider.addEventListener('pointerup', (event) => {
            finishDragging(event);
        });

        homeDivider.addEventListener('pointercancel', (event) => {
            finishDragging(event);
        });

        window.addEventListener('resize', clampColumns);
        clampColumns();
    }

    const storyViewport = document.getElementById('storyViewport');
    const storyTrack = document.getElementById('storyTrack');
    const storyMobileMeta = document.getElementById('storyMobileMeta');
    const storyDots = Array.from(document.querySelectorAll('[data-story-dot]'));

    if (storyViewport && storyTrack && storyDots.length) {
        // The story cards become an infinite-feeling carousel only on mobile; on
        // desktop they remain normal content.
        const mobileQuery = window.matchMedia('(max-width: 900px)');
        const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
        const totalStories = storyDots.length;
        let currentIndex = 1;
        let isCarouselReady = false;
        let dragState = null;

        const getOriginalSlides = () => Array.from(storyTrack.querySelectorAll('.story-card:not([data-story-clone="true"])'));
        const getViewportWidth = () => storyViewport.getBoundingClientRect().width || storyViewport.offsetWidth || 1;
        const mod = (value, size) => ((value % size) + size) % size;

        const setTrackTransition = (enabled) => {
            storyTrack.style.transition = enabled && !reducedMotionQuery.matches
                ? 'transform 0.34s cubic-bezier(0.22, 0.8, 0.2, 1)'
                : 'none';
        };

        const updateDots = (logicalIndex) => {
            storyDots.forEach((dot, index) => {
                const isActive = index === logicalIndex;
                dot.classList.toggle('is-active', isActive);
                dot.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            });
        };

        const applyTransform = (extraOffset = 0) => {
            if (!isCarouselReady) {
                storyTrack.style.removeProperty('transform');
                return;
            }
            const offset = (-currentIndex * getViewportWidth()) + extraOffset;
            storyTrack.style.transform = `translate3d(${offset}px, 0, 0)`;
        };

        const syncDotsFromCurrentIndex = () => {
            updateDots(mod(currentIndex - 1, totalStories));
        };

        const removeClones = () => {
            storyTrack.querySelectorAll('[data-story-clone="true"]').forEach((node) => node.remove());
        };

        const destroyCarousel = () => {
            removeClones();
            isCarouselReady = false;
            dragState = null;
            storyViewport.classList.remove('is-carousel-ready');
            storyTrack.classList.remove('is-carousel-ready');
            storyMobileMeta.classList.remove('is-visible');
            storyTrack.style.removeProperty('transform');
            storyTrack.style.removeProperty('transition');
            updateDots(0);
        };

        const buildCarousel = () => {
            // Cloned edge slides let swipes wrap without changing the original
            // server-rendered story-card nodes.
            removeClones();
            const originals = getOriginalSlides();
            if (!mobileQuery.matches || originals.length < 2) {
                destroyCarousel();
                return;
            }

            const firstClone = originals[0].cloneNode(true);
            const lastClone = originals[originals.length - 1].cloneNode(true);
            firstClone.dataset.storyClone = 'true';
            lastClone.dataset.storyClone = 'true';
            firstClone.setAttribute('aria-hidden', 'true');
            lastClone.setAttribute('aria-hidden', 'true');

            storyTrack.insertBefore(lastClone, originals[0]);
            storyTrack.appendChild(firstClone);

            isCarouselReady = true;
            currentIndex = 1;
            storyViewport.classList.add('is-carousel-ready');
            storyTrack.classList.add('is-carousel-ready');
            storyMobileMeta.classList.add('is-visible');

            setTrackTransition(false);
            requestAnimationFrame(() => {
                applyTransform();
                syncDotsFromCurrentIndex();
            });
        };

        const goToIndex = (nextIndex, animate = true) => {
            if (!isCarouselReady) return;
            currentIndex = nextIndex;
            setTrackTransition(animate);
            applyTransform();
            syncDotsFromCurrentIndex();
        };

        const handleBoundaryReset = () => {
            if (!isCarouselReady) return;
            if (currentIndex === 0) {
                currentIndex = totalStories;
            } else if (currentIndex === totalStories + 1) {
                currentIndex = 1;
            } else {
                return;
            }

            setTrackTransition(false);
            applyTransform();
        };

        storyTrack.addEventListener('transitionend', () => {
            handleBoundaryReset();
            syncDotsFromCurrentIndex();
        });

        storyDots.forEach((dot, index) => {
            dot.addEventListener('click', () => {
                if (!isCarouselReady) return;
                goToIndex(index + 1, true);
            });
        });

        storyViewport.addEventListener('pointerdown', (event) => {
            if (!isCarouselReady) return;
            if (event.pointerType === 'mouse' && event.button !== 0) return;

            dragState = {
                pointerId: event.pointerId,
                startX: event.clientX,
                startY: event.clientY,
                deltaX: 0,
                deltaY: 0,
                axisLocked: null,
            };

            setTrackTransition(false);
            if (event.pointerType === 'mouse' && storyViewport.setPointerCapture) {
                storyViewport.setPointerCapture(event.pointerId);
            }
        });

        storyViewport.addEventListener('pointermove', (event) => {
            if (!dragState || !isCarouselReady || event.pointerId !== dragState.pointerId) return;

            dragState.deltaX = event.clientX - dragState.startX;
            dragState.deltaY = event.clientY - dragState.startY;

            if (!dragState.axisLocked) {
                if (Math.abs(dragState.deltaX) < 6 && Math.abs(dragState.deltaY) < 6) {
                    return;
                }
                dragState.axisLocked = Math.abs(dragState.deltaX) > Math.abs(dragState.deltaY) ? 'x' : 'y';
            }

            if (dragState.axisLocked !== 'x') {
                return;
            }

            applyTransform(dragState.deltaX);
        });

        const finishDrag = (event) => {
            if (!dragState || (event && event.pointerId !== dragState.pointerId)) return;

            const activeDrag = dragState;
            dragState = null;

            if (
                event &&
                storyViewport.releasePointerCapture &&
                storyViewport.hasPointerCapture &&
                storyViewport.hasPointerCapture(event.pointerId)
            ) {
                try {
                    storyViewport.releasePointerCapture(event.pointerId);
                } catch (error) {
                    // Ignore pointer release errors caused by browser timing differences.
                }
            }

            if (!isCarouselReady) {
                return;
            }

            if (activeDrag.axisLocked !== 'x') {
                setTrackTransition(true);
                applyTransform();
                return;
            }

            const threshold = Math.max(42, getViewportWidth() * 0.14);
            if (Math.abs(activeDrag.deltaX) > threshold) {
                currentIndex += activeDrag.deltaX < 0 ? 1 : -1;
            }

            setTrackTransition(true);
            applyTransform();
            syncDotsFromCurrentIndex();
        };

        storyViewport.addEventListener('pointerup', finishDrag);
        storyViewport.addEventListener('pointercancel', finishDrag);
        storyViewport.addEventListener('pointerleave', (event) => {
            if (!dragState || event.pointerType !== 'mouse') return;
            finishDrag(event);
        });

        const handleResponsiveCarousel = () => {
            if (mobileQuery.matches) {
                buildCarousel();
            } else {
                destroyCarousel();
            }
        };

        const handleResize = () => {
            if (!isCarouselReady) return;
            setTrackTransition(false);
            applyTransform();
        };

        if (mobileQuery.addEventListener) {
            mobileQuery.addEventListener('change', handleResponsiveCarousel);
            reducedMotionQuery.addEventListener('change', handleResize);
        } else if (mobileQuery.addListener) {
            mobileQuery.addListener(handleResponsiveCarousel);
            reducedMotionQuery.addListener(handleResize);
        }

        window.addEventListener('resize', handleResize);
        handleResponsiveCarousel();
    }
