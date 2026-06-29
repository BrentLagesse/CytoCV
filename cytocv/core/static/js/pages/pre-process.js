      // Preprocess review controller. Server-rendered JSON supplies the file
      // list, scale metadata, and async execution mode; DOM IDs and progress
      // payload keys are covered by frontend contract tests.
      const preprocessPageConfigElement = document.getElementById("preprocessPageConfig");
      const preprocessPageConfig = JSON.parse(
        preprocessPageConfigElement ? preprocessPageConfigElement.textContent || "{}" : "{}"
      );
      const preprocessUuids = String(preprocessPageConfig.uuids || "");
      const preprocessExperimentUrl = String(preprocessPageConfig.experimentUrl || "/experiment/");
      const preprocessAnalysisExecutionMode = String(preprocessPageConfig.analysisExecutionMode || "");

      // currentFileIndex/totalFiles stay server-originated so browser history
      // restores and back-navigation resume the same review position.
      let currentFileIndex = parseInt(String(preprocessPageConfig.currentFileIndex ?? 0), 10);
      const totalFiles = parseInt(String(preprocessPageConfig.totalFiles ?? 1), 10);
      const setAsyncProgress = (target, payload) => {
        if (target && window.CytoCVAsyncProgress) {
          window.CytoCVAsyncProgress.set(target, payload);
        }
      };
      const clearAsyncProgress = (target) => {
        if (target && window.CytoCVAsyncProgress) {
          window.CytoCVAsyncProgress.clear(target);
        }
      };

      // Sidebar state spans channels, scale overrides, and user preferences; the
      // selectors here are shared with template contract tests.
      const sidebar = document.getElementById("sidebar");
      const toggleBtn = document.getElementById("toggleSidebarBtn");
      const channelVisibilityBtn = document.getElementById("toggleChannelVisibilityBtn");
      const scaleVisibilityBtn = document.getElementById("toggleScaleVisibilityBtn");
      const sidebarSpatialUnitToggle = document.getElementById("sidebarSpatialUnitToggle");
      const fileItems = document.querySelectorAll(".file-item");
      const preprocessMainShell = document.querySelector('[data-ui-region="preprocess-main-shell"]');
      const imageContainerStage = document.getElementById("imageContainerStage");
      const imageContainer = document.getElementById("imageContainer");
      const fileNameElement = document.getElementById("fileName");
      const currentFileIndexElement = document.getElementById("currentFileIndex");
      const fileScaleMapInput = document.getElementById("fileScaleMapInput");
      const fileScaleRevertInput = document.getElementById("fileScaleRevertInput");
      const fileScaleInputs = Array.from(document.querySelectorAll(".file-scale-input"));
      let analysisAbortController = null;
      let analysisPollTimer = null;
      let suppressAnalysisErrors = false;
      window.isAnalysisRunning = false;
      let channelLabelFadeTimer = null;
      let scaleLabelFadeTimer = null;
      const SCALE_TOLERANCE = 1e-6;
      const SCALE_MATCH_TOLERANCE = 5e-5;
      const FILE_SWITCH_TEXT_FADE_MS = 170;
      const FILE_SWITCH_IMAGE_FADE_MS = 190;
      const SCALE_REVERT_BUTTON_HTML = '<svg class="scale-revert-icon" aria-hidden="true" focusable="false" viewBox="0 0 12 12"><path d="M4.8 3.1 2.2 5.7l2.6 2.6"></path><path d="M2.6 5.7h4a3 3 0 1 1-1.8 5.4"></path></svg><span class="scale-revert-label">Revert</span>';
      const REDUCED_MOTION = !!(
        window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
      );
      let latestImageLoadToken = 0;

      function getSidebarCsrfToken() {
        let value = null;
        document.cookie.split(';').forEach((cookie) => {
          const item = cookie.trim();
          if (item.startsWith('csrftoken=')) {
            value = decodeURIComponent(item.slice('csrftoken='.length));
          }
        });
        return value;
      }
      const sidebarCsrfToken = getSidebarCsrfToken();
      const defaultSpatialStatsUnit = preprocessPageConfig.defaultSpatialStatsUnit || "px";
      let currentSpatialStatsUnit = preprocessPageConfig.initialSidebarSpatialStatsUnit || defaultSpatialStatsUnit;

      function normalizeSpatialUnit(unit) {
        return unit === "um" ? "um" : "px";
      }

      function getCurrentSpatialUnit() {
        return normalizeSpatialUnit(currentSpatialStatsUnit || defaultSpatialStatsUnit);
      }

      function setCurrentSpatialUnit(unit) {
        currentSpatialStatsUnit = normalizeSpatialUnit(unit);
      }

      function updateSidebarSpatialUnitControls() {
        if (!sidebarSpatialUnitToggle) return;
        const activeUnit = getCurrentSpatialUnit();
        sidebarSpatialUnitToggle.dataset.activeUnit = activeUnit;
        sidebarSpatialUnitToggle.querySelectorAll("[data-spatial-unit]").forEach((button) => {
          const isActive = button.dataset.spatialUnit === activeUnit;
          button.classList.toggle("active", isActive);
          button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });
      }

      async function persistSidebarSpatialUnit(unit) {
        const response = await fetch("/dashboard/preferences/channels/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": sidebarCsrfToken || "",
          },
          credentials: "same-origin",
          body: JSON.stringify({ sidebar_spatial_stats_unit: normalizeSpatialUnit(unit) }),
        });
        if (!response.ok) {
          throw new Error("Unable to save spatial unit preference.");
        }
        const payload = await response.json();
        return normalizeSpatialUnit(payload.sidebar_spatial_stats_unit || unit);
      }

      updateSidebarSpatialUnitControls();
      if (sidebarSpatialUnitToggle) {
        sidebarSpatialUnitToggle.querySelectorAll("[data-spatial-unit]").forEach((button) => {
          button.addEventListener("click", async () => {
            const nextUnit = normalizeSpatialUnit(button.dataset.spatialUnit || "px");
            if (nextUnit === getCurrentSpatialUnit()) return;
            const previousUnit = getCurrentSpatialUnit();
            setCurrentSpatialUnit(nextUnit);
            updateSidebarSpatialUnitControls();
            try {
              const persistedUnit = await persistSidebarSpatialUnit(nextUnit);
              setCurrentSpatialUnit(persistedUnit);
              updateSidebarSpatialUnitControls();
            } catch (error) {
              setCurrentSpatialUnit(previousUnit);
              updateSidebarSpatialUnitControls();
            }
          });
        });
      }

      function parseScalePayload() {
        // preprocessScalePayload is a per-file scale map, not authorization.
        // The backend revalidates ownership and selected UUIDs on submit.
        const payloadElement = document.getElementById("preprocessScalePayload");
        if (!payloadElement) return {};
        try {
          const parsed = JSON.parse(payloadElement.textContent || "{}");
          return parsed && typeof parsed === "object" ? parsed : {};
        } catch (err) {
          return {};
        }
      }
      function sanitizeScaleValue(value, fallback = 0.1) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed) || parsed <= 0) {
          return fallback;
        }
        return parsed;
      }
      function formatScaleValue(value) {
        const parsed = sanitizeScaleValue(value);
        return parsed.toFixed(4).replace(/\.?0+$/, "");
      }
      function parseOptionalScale(value) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed) || parsed <= 0) return null;
        return parsed;
      }
      function parseScaleBoolean(value, fallback = false) {
        if (typeof value === "boolean") return value;
        const normalized = String(value ?? "").trim().toLowerCase();
        if (["1", "true", "yes", "on"].includes(normalized)) return true;
        if (["0", "false", "no", "off"].includes(normalized)) return false;
        return fallback;
      }
      function buildAutoScaleUi(input, fallbackValue) {
        const preferMetadata = parseScaleBoolean(input.dataset.preferMetadata, true);
        const metadataScale = parseOptionalScale(input.dataset.metadataUmPerPx);
        const manualScale = sanitizeScaleValue(input.dataset.manualUmPerPx, fallbackValue);
        const dx = parseOptionalScale(input.dataset.scaleDx);
        const dy = parseOptionalScale(input.dataset.scaleDy);
        const status = String(input.dataset.scaleStatus || "").trim().toLowerCase();

        const hasMetadataScale = metadataScale !== null;
        const useMetadata = preferMetadata && hasMetadataScale;
        const anisotropic = useMetadata && dx !== null && dy !== null && Math.abs(dx - dy) > SCALE_TOLERANCE;

        const sourceKey = useMetadata ? "metadata" : (preferMetadata ? "manual_fallback" : "manual_global");
        const sourceLabel = useMetadata
          ? (anisotropic ? "Anisotropic auto" : "Metadata")
          : (sourceKey === "manual_fallback" ? "Fallback" : "Manual");
        const effectiveValue = useMetadata ? metadataScale : manualScale;
        const summary = anisotropic
          ? `dx ${formatScaleValue(dx)} / dy ${formatScaleValue(dy)} µm/px`
          : `${formatScaleValue(effectiveValue)} µm/px`;
        const warning = sourceKey === "manual_fallback" || status === "invalid" || anisotropic;

        let note = "";
        if (anisotropic) {
          note = "Anisotropic metadata detected: distance checks use per-axis dx/dy; line width conversion uses geometric proxy.";
        } else if (sourceKey === "manual_fallback") {
          note = status === "invalid"
            ? "Metadata scale values are invalid; using manual scale."
            : "Metadata scale unavailable; using manual global scale.";
        }

        let tooltip = note;
        if (!tooltip) {
          if (sourceKey === "metadata") {
            tooltip = "Using per-file DV metadata scale.";
          } else if (sourceKey === "manual_global") {
            tooltip = "Using manual global scale.";
          }
        }

        return {
          sourceKey,
          sourceLabel,
          sourceWarning: warning,
          summary,
          note,
          tooltip,
          effectiveValue,
        };
      }
      function buildManualOverrideTooltip(autoUi) {
        if (autoUi.sourceKey === "metadata") {
          return "Click Revert to restore auto-detected metadata scale.";
        }
        return "Click Revert to restore this file's automatic scale.";
      }
      function getRevertTitle(autoUi) {
        return autoUi.sourceKey === "metadata"
          ? "Revert this file to metadata scale."
          : "Revert this file to automatic scale.";
      }
      function setRevertButtonState(button, visible, title) {
        if (!button) return;
        button.innerHTML = SCALE_REVERT_BUTTON_HTML;
        button.title = title || "";
        button.classList.toggle("is-visible", !!visible);
      }
      function setScaleText(element, nextText, options = {}) {
        if (!element) return;
        const allowEmpty = !!options.allowEmpty;
        const normalized = typeof nextText === "string" ? nextText : String(nextText ?? "");
        const direction = options.direction === "left" ? "left" : "top";
        if (element._scaleFadeTimer) {
          clearTimeout(element._scaleFadeTimer);
          element._scaleFadeTimer = null;
        }
        element.classList.add("scale-fade-transition");
        element.dataset.fadeDirection = direction;
        element.classList.remove("is-fading");
        element.textContent = normalized;
        if (allowEmpty) {
          element.classList.toggle("is-empty", !normalized);
        }
      }

      function fadeScaleText(element, nextText, options = {}) {
        if (!element) return;
        const normalized = typeof nextText === "string" ? nextText : String(nextText ?? "");
        const allowEmpty = !!options.allowEmpty;
        const direction = options.direction === "left" ? "left" : "top";
        const currentText = element.textContent || "";
        const currentlyEmpty = allowEmpty && element.classList.contains("is-empty");
        if (currentText === normalized && (!allowEmpty || (!!normalized !== currentlyEmpty))) {
          return;
        }
        if (element._scaleFadeTimer) {
          clearTimeout(element._scaleFadeTimer);
          element._scaleFadeTimer = null;
        }
        element.classList.add("scale-fade-transition");
        element.dataset.fadeDirection = direction;

        if (allowEmpty && normalized && (currentlyEmpty || !currentText)) {
          element.textContent = normalized;
          element.classList.remove("is-empty");
          element.classList.add("is-fading");
          window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => {
              element.classList.remove("is-fading");
            });
          });
          return;
        }

        element.classList.add("is-fading");
        element._scaleFadeTimer = window.setTimeout(() => {
          element.textContent = normalized;
          if (allowEmpty) {
            element.classList.toggle("is-empty", !normalized);
          }
          element.classList.remove("is-fading");
          element._scaleFadeTimer = null;
        }, FILE_SWITCH_TEXT_FADE_MS);
      }

      function setFileSwitchState(active) {
        if (!preprocessMainShell) return;
        preprocessMainShell.classList.toggle("is-file-switching", !!active);
      }

      function clearTextBlend(host) {
        if (!host) return;
        if (host._blendTimer) {
          clearTimeout(host._blendTimer);
          host._blendTimer = null;
        }
        if (host._blendOverlay) {
          host._blendOverlay.remove();
          host._blendOverlay = null;
        }
      }

      function blendTextContent(element, nextText) {
        if (!element) return;
        const normalized = typeof nextText === "string" ? nextText : String(nextText ?? "");
        if ((element.textContent || "") === normalized) {
          return;
        }
        if (REDUCED_MOTION) {
          element.textContent = normalized;
          element.classList.remove("is-pre-blend");
          return;
        }

        const host = element.closest(".preprocess-inline-blend-host, .preprocess-blend-host");
        if (!host) {
          element.textContent = normalized;
          return;
        }

        clearTextBlend(host);

        const overlay = document.createElement("span");
        overlay.className = "preprocess-blend-overlay";
        overlay.setAttribute("aria-hidden", "true");
        overlay.textContent = element.textContent || "";
        host.appendChild(overlay);
        host._blendOverlay = overlay;

        element.textContent = normalized;
        element.classList.add("is-pre-blend");

        window.requestAnimationFrame(() => {
          window.requestAnimationFrame(() => {
            overlay.classList.add("is-exiting");
            element.classList.remove("is-pre-blend");
          });
        });

        host._blendTimer = window.setTimeout(() => {
          if (host._blendOverlay === overlay) {
            overlay.remove();
            host._blendOverlay = null;
          }
          host._blendTimer = null;
        }, FILE_SWITCH_TEXT_FADE_MS + 45);
      }

      function preloadPreviewImages(images) {
        const urls = Array.isArray(images)
          ? images.map((img) => img?.file_location?.url).filter(Boolean)
          : [];
        return Promise.all(
          urls.map(
            (url) =>
              new Promise((resolve) => {
                const preloadImage = new Image();
                let settled = false;
                const finish = () => {
                  if (settled) return;
                  settled = true;
                  resolve(url);
                };
                preloadImage.onload = finish;
                preloadImage.onerror = finish;
                preloadImage.src = url;
                if (typeof preloadImage.decode === "function") {
                  preloadImage.decode().then(finish).catch(finish);
                }
                if (preloadImage.complete) {
                  finish();
                }
              }),
          ),
        );
      }

      function buildPreviewImageFragment(images) {
        const fragment = document.createDocumentFragment();
        (images || []).forEach((img) => {
          const image = document.createElement("img");
          image.src = img.file_location.url;
          image.width = 300;
          image.height = 300;
          fragment.appendChild(image);
        });
        return fragment;
      }

      function transitionImageContainer(nextImages, requestToken) {
        if (!imageContainer || !imageContainerStage) return Promise.resolve();

        if (imageContainerStage._blendTimer) {
          clearTimeout(imageContainerStage._blendTimer);
          imageContainerStage._blendTimer = null;
        }
        if (imageContainerStage._blendOverlay) {
          imageContainerStage._blendOverlay.remove();
          imageContainerStage._blendOverlay = null;
        }

        if (REDUCED_MOTION) {
          imageContainer.replaceChildren(buildPreviewImageFragment(nextImages));
          imageContainer.classList.remove("is-pre-blend");
          return Promise.resolve();
        }

        const overlay = imageContainer.cloneNode(true);
        overlay.removeAttribute("id");
        overlay.classList.add("image-container-overlay");
        imageContainerStage.appendChild(overlay);
        imageContainerStage._blendOverlay = overlay;

        imageContainer.replaceChildren(buildPreviewImageFragment(nextImages));
        imageContainer.classList.add("is-pre-blend");

        return new Promise((resolve) => {
          window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => {
              if (requestToken !== latestImageLoadToken) {
                resolve();
                return;
              }
              overlay.classList.add("is-exiting");
              imageContainer.classList.remove("is-pre-blend");
            });
          });

          imageContainerStage._blendTimer = window.setTimeout(() => {
            if (imageContainerStage._blendOverlay === overlay) {
              overlay.remove();
              imageContainerStage._blendOverlay = null;
            }
            imageContainerStage._blendTimer = null;
            resolve();
          }, FILE_SWITCH_IMAGE_FADE_MS + 55);
        });
      }

      const initialScalePayload = parseScalePayload();
      const initialScaleValues = new Map();
      const fileScaleOverrides = new Map();
      const fileScaleReverts = new Set();
      const initialScaleUi = new Map();

      function syncFileScaleMapInput() {
        if (!fileScaleMapInput) return;
        const payload = {};
        fileScaleOverrides.forEach((value, uuid) => {
          payload[uuid] = Number(formatScaleValue(value));
        });
        fileScaleMapInput.value = JSON.stringify(payload);
      }
      function syncFileScaleRevertInput() {
        if (!fileScaleRevertInput) return;
        fileScaleRevertInput.value = JSON.stringify(Array.from(fileScaleReverts));
      }
      function syncScaleInputs() {
        syncFileScaleMapInput();
        syncFileScaleRevertInput();
      }

      fileScaleInputs.forEach((input) => {
        const uuid = input.dataset.uuid;
        if (!uuid) return;
        const fallbackValue = sanitizeScaleValue(input.value, 0.1);
        const seededValue = sanitizeScaleValue(initialScalePayload[uuid], fallbackValue);
        initialScaleValues.set(uuid, seededValue);
        input.value = formatScaleValue(seededValue);
        const sourceBadge = document.querySelector(`[data-scale-source="${uuid}"]`);
        const summary = document.querySelector(`[data-scale-summary="${uuid}"]`);
        const note = document.querySelector(`[data-scale-note="${uuid}"]`);
        const revertButton = document.querySelector(`[data-scale-revert="${uuid}"]`);
        const initialSourceKey = String(input.dataset.sourceKey || "").trim().toLowerCase();
        const autoUi = buildAutoScaleUi(input, seededValue);

        initialScaleUi.set(uuid, {
          ...autoUi,
          initialSourceKey,
          seededValue,
        });

        const handleScaleUpdate = () => {
          const current = sanitizeScaleValue(input.value, seededValue);
          const baseUi = initialScaleUi.get(uuid) || autoUi;
          const autoScale = sanitizeScaleValue(baseUi.effectiveValue, seededValue);
          const baseline = initialScaleValues.get(uuid) ?? seededValue;
          const initialWasOverride = baseUi.initialSourceKey === "manual_override";
          const currentRounded = Number(formatScaleValue(current));
          const autoRounded = Number(formatScaleValue(autoScale));
          const isOverride = Math.abs(currentRounded - autoRounded) > SCALE_MATCH_TOLERANCE;

          if (isOverride) {
            if (!(initialWasOverride && Math.abs(current - baseline) <= SCALE_TOLERANCE)) {
              fileScaleOverrides.set(uuid, current);
            } else {
              fileScaleOverrides.delete(uuid);
            }
            fileScaleReverts.delete(uuid);
          } else {
            fileScaleOverrides.delete(uuid);
            if (initialWasOverride) {
              fileScaleReverts.add(uuid);
            } else {
              fileScaleReverts.delete(uuid);
            }
          }
          input.value = formatScaleValue(current);

          if (sourceBadge) {
            fadeScaleText(
              sourceBadge,
              isOverride ? "Override" : (baseUi.sourceLabel || "Metadata"),
              { direction: "left" },
            );
            sourceBadge.classList.toggle("warning", isOverride ? false : !!baseUi.sourceWarning);
            sourceBadge.title = isOverride
              ? buildManualOverrideTooltip(baseUi)
              : (baseUi.tooltip || "");
          }
          if (summary) {
            fadeScaleText(
              summary,
              isOverride
                ? `${formatScaleValue(current)} µm/px`
                : (baseUi.summary || `${formatScaleValue(baseline)} µm/px`),
              { direction: "top" },
            );
          }
          if (note) {
            fadeScaleText(
              note,
              isOverride ? "" : (baseUi.note || ""),
              { allowEmpty: true, direction: "top" },
            );
          }
          setRevertButtonState(
            revertButton,
            isOverride,
            getRevertTitle(baseUi),
          );
          syncScaleInputs();
        };

        setScaleText(
          sourceBadge,
          initialSourceKey === "manual_override" ? "Override" : (autoUi.sourceLabel || "Metadata"),
          { direction: "left" },
        );
        if (sourceBadge) {
          sourceBadge.classList.toggle("warning", initialSourceKey === "manual_override" ? false : !!autoUi.sourceWarning);
          sourceBadge.title = initialSourceKey === "manual_override"
            ? buildManualOverrideTooltip(autoUi)
            : (autoUi.tooltip || "");
        }
        setScaleText(
          summary,
          initialSourceKey === "manual_override"
            ? `${formatScaleValue(seededValue)} µm/px`
            : (autoUi.summary || `${formatScaleValue(seededValue)} µm/px`),
          { direction: "top" },
        );
        setScaleText(
          note,
          initialSourceKey === "manual_override" ? "" : (autoUi.note || ""),
          { allowEmpty: true, direction: "top" },
        );
        setRevertButtonState(
          revertButton,
          initialSourceKey === "manual_override",
          getRevertTitle(autoUi),
        );

        if (revertButton) {
          revertButton.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            if (document.body.classList.contains("analysis-locked")) return;
            input.value = formatScaleValue(autoUi.effectiveValue);
            handleScaleUpdate();
          });
        }

        input.addEventListener("input", handleScaleUpdate);
        input.addEventListener("change", handleScaleUpdate);
        input.addEventListener("click", (event) => event.stopPropagation());
        input.addEventListener("keydown", (event) => event.stopPropagation());
      });
      syncScaleInputs();

      function setAnalysisLocked(locked) {
        document.body.classList.toggle("analysis-locked", locked);
        fileScaleInputs.forEach((input) => {
          input.disabled = locked;
        });
        document.querySelectorAll(".channel-bar").forEach((bar) => {
          bar.style.pointerEvents = locked ? "none" : "";
        });
      }

      // Highlight active
      function updateSidebarActive(animate = false) {
        fileItems.forEach((i) => i.classList.remove("active"));
        const active = document.querySelector(`.file-item[data-index="${currentFileIndex}"]`);
        if (active) active.classList.add("active");

        const scaleSummaryLine = document.getElementById("preprocessScaleSummary");
        if (scaleSummaryLine) {
          const scaleSummary = active?.querySelector(".scale-summary")?.textContent?.trim() || "";
          const scaleSource = active?.querySelector(".scale-source-badge")?.textContent?.trim() || "";
          const combined = [scaleSummary, scaleSource].filter(Boolean).join(" · ");
          const nextSummary = combined || "Scale metadata unavailable.";
          if (animate) {
            blendTextContent(scaleSummaryLine, nextSummary);
          } else {
            setScaleText(scaleSummaryLine, nextSummary, { direction: "top" });
          }
        }
      }
      updateSidebarActive(false);

      function applyChannelVisibility(visible, persist) {
        sidebar.classList.toggle('channels-hidden', !visible);
        if (channelVisibilityBtn) {
          channelVisibilityBtn.classList.add('label-fade');
          if (channelLabelFadeTimer) {
            window.clearTimeout(channelLabelFadeTimer);
          }
          channelVisibilityBtn.textContent = visible ? 'Hide Channels' : 'Show Channels';
          channelLabelFadeTimer = window.setTimeout(() => {
            channelVisibilityBtn.classList.remove('label-fade');
            channelLabelFadeTimer = null;
          }, 170);
        }
        if (persist) {
          fetch('/dashboard/preferences/channels/', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': sidebarCsrfToken || '',
            },
            credentials: 'same-origin',
            body: JSON.stringify({ show_saved_file_channels: visible }),
          }).catch(() => null);
        }
      }

      function applyScaleVisibility(visible, persist) {
        sidebar.classList.toggle('scales-hidden', !visible);
        if (scaleVisibilityBtn) {
          scaleVisibilityBtn.classList.add('label-fade');
          if (scaleLabelFadeTimer) {
            window.clearTimeout(scaleLabelFadeTimer);
          }
          scaleVisibilityBtn.textContent = visible ? 'Hide Scale' : 'Show Scale';
          scaleLabelFadeTimer = window.setTimeout(() => {
            scaleVisibilityBtn.classList.remove('label-fade');
            scaleLabelFadeTimer = null;
          }, 170);
        }
        if (persist) {
          fetch('/dashboard/preferences/channels/', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': sidebarCsrfToken || '',
            },
            credentials: 'same-origin',
            body: JSON.stringify({ show_saved_file_scales: visible }),
          }).catch(() => null);
        }
      }

      const cancelClientAnalysis = () => {
        // Client-side cancellation first stops local polling/fetches; the server
        // cancellation endpoint below owns worker cleanup and status transitions.
        suppressAnalysisErrors = true;
        window.isAnalysisRunning = false;
        if (analysisPollTimer) {
          clearInterval(analysisPollTimer);
          analysisPollTimer = null;
        }
        if (analysisAbortController) {
          analysisAbortController.abort();
          analysisAbortController = null;
        }
      };
      let cancelPromise = null;
      const requestAnalysisCancel = async () => {
        // A single shared promise prevents repeated navigation/logout handlers
        // from issuing duplicate cancel requests for the same analysis job.
        if (!window.isAnalysisRunning) {
          return true;
        }
        if (cancelPromise) {
          return cancelPromise;
        }
          cancelPromise = (async () => {
            const startButton = document.getElementById("startAnalysisButton");
            const cancellingDetail = {
              phase: "Cancelling",
              status: "cancelling",
              message: "Cancelling analysis and cleaning up.",
            };
            setAsyncProgress(startButton, cancellingDetail);
            cancelClientAnalysis();
            const csrfEl = document.querySelector('#preprocessForm [name=csrfmiddlewaretoken]');
            const csrfToken = csrfEl?.value;
            const cancelUrl = `/api/progress/${encodeURIComponent(preprocessUuids)}/cancel/`;
          try {
            await fetch(cancelUrl, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken || '',
                'X-Requested-With': 'XMLHttpRequest',
              },
              body: JSON.stringify({ reason: 'user_cancelled' }),
              credentials: 'same-origin',
            });
            } catch (e) { /* ignore */ }

            const customTimeout = Number.isFinite(window.CANCEL_POLLING_TIMEOUT_MS)
              ? window.CANCEL_POLLING_TIMEOUT_MS
              : 0;
            const cancelPollingTimeoutMs = customTimeout > 0 ? customTimeout : 60000;
            const deadline = Date.now() + cancelPollingTimeoutMs;
            let delay = 400;
            while (Date.now() < deadline) {
              try {
                const pollUrl = new URL(`/api/progress/${encodeURIComponent(preprocessUuids)}/`, window.location.origin);
                const resp = await fetch(pollUrl, { cache: 'no-store' });
                if (resp.ok) {
                  const data = await resp.json();
                  setAsyncProgress(startButton, {
                    ...(data?.detail || {}),
                    phase: data?.phase || cancellingDetail.phase,
                    status: data?.status || cancellingDetail.status,
                  });
                  const phase = data?.phase || 'idle';
                  if (phase === 'Cancelled' || phase === 'Completed' || phase === 'idle') {
                    break;
                  }
                }
              } catch (e) { /* ignore */ }
              await new Promise((resolve) => setTimeout(resolve, delay));
              delay = Math.min(2000, Math.round(delay * 1.6));
            }
            if (Date.now() >= deadline) {
              console.warn('Cancel polling timed out.');
            }
            window.isAnalysisRunning = false;
            cancelPromise = null;
            clearAsyncProgress(startButton);
            return true;
        })();
        return cancelPromise;
      };
      window.cancelActiveAnalysis = cancelClientAnalysis;
      window.requestAnalysisCancel = requestAnalysisCancel;
      window.addEventListener("beforeunload", cancelClientAnalysis);

      function setupNavExitGuard() {
          const navLinks = document.querySelectorAll(
          '.navbar a[href="/"], .navbar a[href="/signin/"], .navbar a[href="/signup/"], .navbar a[href="/signup/?fresh=1"], .navbar a[href="/account-settings/"], .navbar a[href="/dashboard/"], .navbar a[href="/workflow-defaults/"]'
          );
        const preprocessBackButton = document.getElementById('preprocessBackButton');
        const backdrop = document.getElementById('navExitBackdrop');
        const cancel = document.getElementById('navExitCancel');
        const confirm = document.getElementById('navExitConfirm');
        const panel = backdrop ? backdrop.querySelector('.nav-exit-modal') : null;
        const MODAL_ENTER_MS = 170;
        const MODAL_EXIT_MS = 120;
        const prefersReducedMotion = !!(
          window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
        );
        const clearModalAnim = () => {
          if (!backdrop) return;
          backdrop.classList.remove('modal-enter', 'modal-exit');
          if (panel) {
            panel.classList.remove('modal-enter', 'modal-exit');
          }
        };

        if (!backdrop || !cancel || !confirm) {
          return;
        }

        let pendingHref = null;
        // Navigation uses the same cancel path as logout so workers see one
        // cancellation contract regardless of how the user leaves the page.
        const defaultTitle = 'Leave experiment?';
        const defaultBody = 'You have an active experiment session. Are you sure you want to leave this page?';
        const runningTitle = 'Leave experiment and cancel analysis?';
        const runningBody = 'Analysis is currently running. Leaving will cancel the analysis. Are you sure you want to leave this page?';
        const openModal = (href) => {
          pendingHref = href;
          if (window.isAnalysisRunning) {
            const titleEl = document.getElementById('navExitTitle');
            const bodyEl = document.querySelector('.nav-exit-body');
            if (titleEl) titleEl.textContent = runningTitle;
            if (bodyEl) bodyEl.textContent = runningBody;
          } else {
            const titleEl = document.getElementById('navExitTitle');
            const bodyEl = document.querySelector('.nav-exit-body');
            if (titleEl) titleEl.textContent = defaultTitle;
            if (bodyEl) bodyEl.textContent = defaultBody;
          }
          clearModalAnim();
          backdrop.style.display = 'flex';
          backdrop.setAttribute('aria-hidden', 'false');
          if (!prefersReducedMotion) {
            void backdrop.offsetWidth;
            backdrop.classList.add('modal-enter');
            if (panel) {
              panel.classList.add('modal-enter');
            }
            window.setTimeout(clearModalAnim, MODAL_ENTER_MS);
          }
        };
        const closeModal = () => {
          pendingHref = null;
          if (prefersReducedMotion || backdrop.style.display !== 'flex') {
            clearModalAnim();
            backdrop.style.display = 'none';
            backdrop.setAttribute('aria-hidden', 'true');
            return;
          }
          clearModalAnim();
          backdrop.classList.add('modal-exit');
          if (panel) {
            panel.classList.add('modal-exit');
          }
          backdrop.setAttribute('aria-hidden', 'true');
          window.setTimeout(() => {
            clearModalAnim();
            backdrop.style.display = 'none';
          }, MODAL_EXIT_MS);
        };
        const handleNavClick = (event) => {
          if (!Number.isFinite(totalFiles) || totalFiles <= 0) {
            return;
          }
          event.preventDefault();
          openModal(event.currentTarget.getAttribute('href'));
        };
        navLinks.forEach((link) => link.addEventListener('click', handleNavClick));
        if (preprocessBackButton) {
          preprocessBackButton.addEventListener('click', (event) => {
            const backHref = preprocessBackButton.dataset.href || preprocessExperimentUrl;
            if (!Number.isFinite(totalFiles) || totalFiles <= 0) {
              window.location.href = backHref;
              return;
            }
            event.preventDefault();
            openModal(backHref);
          });
        }

        cancel.addEventListener('click', closeModal);
        confirm.addEventListener('click', async () => {
          if (pendingHref) {
            const shouldCancelAnalysis = !!window.isAnalysisRunning;
            confirm.classList.add('loading');
            confirm.style.pointerEvents = 'none';
            confirm.disabled = true;
            const label = confirm.querySelector('.btn-label');
            if (label) {
              label.textContent = shouldCancelAnalysis ? 'Cancelling' : 'Leaving';
            }
            if (shouldCancelAnalysis) {
              setAsyncProgress(confirm, {
                phase: 'Cancelling',
                status: 'cancelling',
                message: 'Cancelling analysis and cleaning up.',
              });
            }
            await requestAnalysisCancel();
            if (shouldCancelAnalysis) {
              clearAsyncProgress(confirm);
            }
            window.location.href = pendingHref;
          }
        });
        backdrop.addEventListener('click', (event) => {
          if (event.target === backdrop) {
            closeModal();
          }
        });
        document.addEventListener('keydown', (event) => {
          if (event.key === 'Escape') {
            closeModal();
          }
        });
      }
      setupNavExitGuard();

      // Click file
      fileItems.forEach((item) => {
        item.addEventListener("click", () => {
          const idx = parseInt(item.dataset.index, 10);
          loadImage(idx);
        });
      });

      // Toggle sidebar
      const setSidebarCollapsed = (collapsed) => {
        const isCollapsed = sidebar.classList.contains('collapsed');
        if (collapsed === isCollapsed) {
          return;
        }
        if (collapsed) {
          sidebar.classList.remove('is-expanding');
          sidebar.classList.add('collapsed');
          return;
        }
        sidebar.classList.add('is-expanding');
        sidebar.classList.remove('collapsed');
      };
      toggleBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        setSidebarCollapsed(!sidebar.classList.contains("collapsed"));
      });

      // ALSO expand when collapsed sidebar area is clicked
      sidebar.addEventListener("click", (e) => {
        if (sidebar.classList.contains("collapsed")) {
          setSidebarCollapsed(false);
        }
      });
      if (channelVisibilityBtn) {
        channelVisibilityBtn.addEventListener('click', () => {
          applyChannelVisibility(sidebar.classList.contains('channels-hidden'), true);
        });
      }
      if (scaleVisibilityBtn) {
        scaleVisibilityBtn.addEventListener('click', () => {
          applyScaleVisibility(sidebar.classList.contains('scales-hidden'), true);
        });
      }
      applyChannelVisibility(!sidebar.classList.contains('channels-hidden'), false);
      applyScaleVisibility(!sidebar.classList.contains('scales-hidden'), false);

      const analysisButton = null;
      const analysisPopover = null;

      // Next / Prev buttons
      document.getElementById("nextButton").addEventListener("click", () => {
        loadImage((currentFileIndex + 1) % totalFiles);
      });
      document.getElementById("prevButton").addEventListener("click", () => {
        loadImage((currentFileIndex - 1 + totalFiles) % totalFiles);
      });

      // Intercept submit: disable inputs, poll accurate progress, POST via fetch, then navigate
      document.getElementById("preprocessForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const form = document.getElementById("preprocessForm");
        const btn = document.getElementById("startAnalysisButton");
        const textEl = btn.querySelector(".btn-text");
        const setAnalysisProgress = (payload) => setAsyncProgress(btn, payload);
        const clearAnalysisProgress = () => clearAsyncProgress(btn);
        suppressAnalysisErrors = false;
        window.isAnalysisRunning = true;

        btn.disabled = true;
        btn.classList.add("loading");
        btn.style.pointerEvents = "none";
        btn.style.cursor = "not-allowed";
        btn.style.backgroundColor = "#0056b3";
        if (textEl) textEl.textContent = "Processing Images";
        setAnalysisProgress({
          phase: "Processing Images",
          message: "Preparing analysis request.",
        });
        syncFileScaleMapInput();
        setAnalysisLocked(true);

        // Disable other interactive controls
        if (analysisButton) {
          analysisButton.disabled = true;
          analysisButton.style.pointerEvents = "none";
          analysisButton.style.opacity = "0.8";
          analysisButton.style.backgroundColor = "#0056b3";
        }
        if (analysisPopover) {
          analysisPopover.classList.remove("open");
          analysisPopover.setAttribute("aria-hidden", "true");
        }
        // Poll progress for accurate phases
        const uuids = preprocessUuids;
        const isWorkerAnalysis = preprocessAnalysisExecutionMode === "worker";
        analysisPollTimer = null;
        let consecutivePollFailures = 0;
        const maxConsecutivePollFailures = 5;
        const knownStatuses = new Set(["idle", "queued", "running", "cancelling", "succeeded", "failed", "cancelled"]);
        const stopPollingWithMessage = (message) => {
          if (analysisPollTimer) clearInterval(analysisPollTimer);
          window.isAnalysisRunning = false;
          btn.disabled = false;
          btn.classList.remove("loading");
          if (textEl) textEl.textContent = "Start Analysis";
          clearAnalysisProgress();
          setAnalysisLocked(false);
          if (window.showGlobalMessage && message) {
            window.showGlobalMessage(message);
          }
        };
        const persistDisplayInfoMessage = (message) => {
          if (!message) return;
          sessionStorage.setItem('cytocvDisplayInfoMessage', JSON.stringify({
            message,
            tone: 'warning',
          }));
        };
        const startPolling = () => {
          // Polling begins while the POST is still in flight so sync and worker
          // paths can share the same progress button contract.
          const poll = async () => {
            try {
              const pollUrl = new URL(`/api/progress/${encodeURIComponent(uuids)}/`, window.location.origin);
              const resp = await fetch(pollUrl, { cache: 'no-store' });
              if (!resp.ok) {
                consecutivePollFailures += 1;
                if (consecutivePollFailures >= maxConsecutivePollFailures) {
                  stopPollingWithMessage("Lost connection to analysis status. Please refresh and check the run state.");
                }
                return;
              }
              const data = await resp.json();
              consecutivePollFailures = 0;
              const status = typeof data?.status === "string" ? data.status.toLowerCase() : "";
              if (!knownStatuses.has(status)) {
                stopPollingWithMessage("Received an unexpected analysis status. Please refresh and try again.");
                return;
              }
              if (data && data.phase && textEl) {
                const phaseText = String(data.phase);
                if (phaseText === "Queued") {
                  textEl.textContent = "Queued";
                } else if (phaseText.startsWith("Preprocessing Images")) {
                  textEl.textContent = phaseText.replace("Preprocessing Images", "Processing Images");
                } else if (phaseText.startsWith("Detecting Cells")) {
                  textEl.textContent = phaseText;
                } else if (phaseText.startsWith("Segmenting Cell-Pairs")) {
                  textEl.textContent = phaseText;
                } else if (phaseText.startsWith("Calculating Statistics")) {
                  // Only show statistics phase if user selected at least one analysis at upload step.
                  const hasStats = preprocessPageConfig.hasSelectedStats === true;
                  if (hasStats) textEl.textContent = phaseText;
                }
              }
              if (data && (data.phase || data.detail)) {
                setAnalysisProgress({
                  ...(data.detail || {}),
                  phase: data.phase,
                  status: data.status,
                });
              }
              if (status === "succeeded") {
                if (analysisPollTimer) clearInterval(analysisPollTimer);
                analysisPollTimer = null;
                if (isWorkerAnalysis && data.redirect) {
                  // Worker completion redirects from the poll payload; sync mode
                  // waits for the original POST response below to avoid double navigation.
                  if (data.failure_summary) {
                    persistDisplayInfoMessage(data.failure_summary);
                  }
                  clearAnalysisProgress();
                  window.isAnalysisRunning = false;
                  window.location.href = data.redirect;
                  return;
                }
                if (!isWorkerAnalysis) {
                  if (textEl) textEl.textContent = "Completed";
                  setAnalysisProgress({
                    ...(data.detail || {}),
                    phase: data.phase || "Completed",
                    status: data.status,
                    message: "Analysis completed.",
                  });
                  return;
                }
                stopPollingWithMessage("Analysis completed, but the result page could not be resolved. Please refresh.");
                return;
              }
              if (status === "failed") {
                const failureMessage = data.failure_summary || "Analysis failed. Please try again.";
                stopPollingWithMessage(failureMessage);
                return;
              }
              if (status === "cancelled") {
                stopPollingWithMessage("Analysis cancelled.");
                return;
              }
            } catch (err) {
              consecutivePollFailures += 1;
              if (consecutivePollFailures >= maxConsecutivePollFailures) {
                stopPollingWithMessage("Lost connection to analysis status. Please refresh and check the run state.");
              }
            }
          };
          analysisPollTimer = setInterval(poll, 1000);
          // Kick off immediately
          poll();
        };
        startPolling();

        // Submit via fetch and expect a terminal JSON handoff from preprocess.
        try {
          analysisAbortController = new AbortController();
          const resp = await fetch(window.location.href, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: new FormData(form),
            credentials: 'same-origin',
            signal: analysisAbortController.signal,
          });
          if (!resp.ok) {
            const contentType = resp.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
              const payload = await resp.json();
              if (payload.status === 'cancelled') {
                stopPollingWithMessage("Analysis cancelled.");
                return;
              }
              if (payload.error) {
                throw new Error(payload.error);
              }
            }
            throw new Error('Analysis request failed.');
          }
          const contentType = resp.headers.get('content-type') || '';
          if (contentType.includes('application/json')) {
            const payload = await resp.json();
            if (payload.error) {
              throw new Error(payload.error);
            }
            if (payload.status === 'queued') {
              if (textEl) textEl.textContent = payload.phase || "Queued";
              setAnalysisProgress({
                ...(payload.detail || {}),
                phase: payload.phase || "Queued",
                status: payload.status,
              });
              return;
            }
            if (payload.status === 'succeeded' && payload.redirect) {
              if (analysisPollTimer) clearInterval(analysisPollTimer);
              if (payload.storage_warning_message) {
                persistDisplayInfoMessage(payload.storage_warning_message);
              }
              clearAnalysisProgress();
              window.isAnalysisRunning = false;
              window.location.href = payload.redirect;
              return;
            }
            if (payload.status === 'cancelled') {
              stopPollingWithMessage("Analysis cancelled.");
              return;
            }
            if (payload.status === 'failed') {
              stopPollingWithMessage(payload.failure_summary || "Analysis failed. Please try again.");
              return;
            }
            throw new Error('Unexpected analysis response.');
          }
          throw new Error('Analysis response was not JSON.');
        } catch (err) {
          if (analysisPollTimer) clearInterval(analysisPollTimer);
          if (suppressAnalysisErrors || (err && err.name === "AbortError")) {
            return;
          }
          window.isAnalysisRunning = false;
          // On error, re-enable button minimally and surface a message
          btn.disabled = false;
          btn.classList.remove("loading");
          if (textEl) textEl.textContent = "Start Analysis";
          clearAnalysisProgress();
          setAnalysisLocked(false);
          if (window.showGlobalMessage) {
            window.showGlobalMessage(
              err && err.message ? err.message : 'Failed to start analysis. Please try again.'
            );
          }
        }
      });

      // AJAX load
      async function loadImage(newIndex) {
        if (!Number.isFinite(newIndex)) return;
        if (newIndex < 0) newIndex = totalFiles - 1;
        if (newIndex >= totalFiles) newIndex = 0;
        if (newIndex === currentFileIndex) return;

        const requestToken = ++latestImageLoadToken;
        setFileSwitchState(true);

        try {
          const response = await fetch(`?file_index=${newIndex}&total_files=${totalFiles}`, {
            headers: { "X-Requested-With": "XMLHttpRequest" },
          });
          if (!response.ok) {
            throw new Error(`Failed to load preprocess preview (${response.status})`);
          }

          const data = await response.json();
          await preloadPreviewImages(data.images);
          if (requestToken !== latestImageLoadToken) {
            return;
          }

          blendTextContent(fileNameElement, data.file_name);
          blendTextContent(currentFileIndexElement, String(data.current_file_index + 1));
          currentFileIndex = data.current_file_index;
          updateSidebarActive(true);
          await transitionImageContainer(data.images, requestToken);
        } catch (error) {
          if (requestToken === latestImageLoadToken) {
            console.error("Failed to switch preprocess preview", error);
          }
        } finally {
          if (requestToken === latestImageLoadToken) {
            setFileSwitchState(false);
          }
        }
      }
