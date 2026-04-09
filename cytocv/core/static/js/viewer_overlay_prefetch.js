(function () {
    'use strict';

    function normalizeMaxCells(maxCells) {
        const normalized = Number(maxCells || 0);
        if (!Number.isFinite(normalized) || normalized < 1) {
            return 0;
        }
        return Math.floor(normalized);
    }

    function targetCell(offset, currentCell, maxCells) {
        const normalizedMaxCells = normalizeMaxCells(maxCells);
        const normalizedCurrent = Number(currentCell || 0);
        if (!normalizedMaxCells || !Number.isFinite(normalizedCurrent)) {
            return 0;
        }
        return ((normalizedCurrent - 1 + offset + normalizedMaxCells) % normalizedMaxCells) + 1;
    }

    function buildCircularCellOrder(currentCell, maxCells, offsets) {
        const normalizedMaxCells = normalizeMaxCells(maxCells);
        if (!normalizedMaxCells) {
            return [];
        }

        const seen = new Set();
        const ordered = [];
        (offsets || []).forEach((offset) => {
            const cellNumber = targetCell(Number(offset || 0), currentCell, normalizedMaxCells);
            if (!cellNumber || seen.has(cellNumber)) {
                return;
            }
            seen.add(cellNumber);
            ordered.push(cellNumber);
        });
        return ordered;
    }

    function buildFullCircularCellOrder(currentCell, maxCells) {
        const normalizedMaxCells = normalizeMaxCells(maxCells);
        if (!normalizedMaxCells) {
            return [];
        }

        const offsets = [0];
        for (let step = 1; step < normalizedMaxCells; step += 1) {
            offsets.push(step);
            offsets.push(-step);
        }
        return buildCircularCellOrder(currentCell, normalizedMaxCells, offsets);
    }

    function createWarmCoordinator(options) {
        const resolveUrl = typeof options?.resolveUrl === 'function'
            ? options.resolveUrl
            : () => '';
        const warmUrl = typeof options?.warmUrl === 'function'
            ? options.warmUrl
            : async () => {};

        const stateByFileKey = new Map();

        function getFileState(fileKey) {
            const normalizedKey = String(fileKey || '');
            if (!stateByFileKey.has(normalizedKey)) {
                stateByFileKey.set(normalizedKey, {
                    warmed: new Set(),
                    inFlight: new Set(),
                    pending: [],
                    draining: false,
                });
            }
            return stateByFileKey.get(normalizedKey);
        }

        async function drain(fileKey) {
            const normalizedKey = String(fileKey || '');
            const state = getFileState(normalizedKey);
            if (state.draining) {
                return;
            }

            state.draining = true;
            try {
                while (state.pending.length > 0) {
                    const cellNumber = state.pending.shift();
                    if (
                        !Number.isFinite(cellNumber)
                        || state.warmed.has(cellNumber)
                        || state.inFlight.has(cellNumber)
                    ) {
                        continue;
                    }

                    state.inFlight.add(cellNumber);
                    try {
                        const url = resolveUrl({
                            fileKey: normalizedKey,
                            cellNumber,
                        });
                        if (!url) {
                            state.warmed.add(cellNumber);
                            continue;
                        }
                        await warmUrl(url, {
                            fileKey: normalizedKey,
                            cellNumber,
                        });
                        state.warmed.add(cellNumber);
                    } catch (error) {
                        // Leave the cell cold so a later navigation can retry.
                    } finally {
                        state.inFlight.delete(cellNumber);
                    }
                }
            } finally {
                state.draining = false;
            }
        }

        function scheduleCells(fileKey, cellNumbers, { prioritize = true } = {}) {
            const normalizedKey = String(fileKey || '');
            const state = getFileState(normalizedKey);
            const nextCells = [];

            (cellNumbers || []).forEach((cellNumber) => {
                const normalizedCell = Number(cellNumber || 0);
                if (!Number.isFinite(normalizedCell) || normalizedCell < 1) {
                    return;
                }
                if (
                    state.warmed.has(normalizedCell)
                    || state.inFlight.has(normalizedCell)
                    || state.pending.includes(normalizedCell)
                ) {
                    return;
                }
                nextCells.push(normalizedCell);
            });

            if (!nextCells.length) {
                return;
            }

            state.pending = prioritize
                ? [...nextCells, ...state.pending]
                : [...state.pending, ...nextCells];
            void drain(normalizedKey);
        }

        function markCellWarm(fileKey, cellNumber) {
            const normalizedCell = Number(cellNumber || 0);
            if (!Number.isFinite(normalizedCell) || normalizedCell < 1) {
                return;
            }
            getFileState(fileKey).warmed.add(normalizedCell);
        }

        function isCellWarm(fileKey, cellNumber) {
            const normalizedCell = Number(cellNumber || 0);
            if (!Number.isFinite(normalizedCell) || normalizedCell < 1) {
                return false;
            }
            return getFileState(fileKey).warmed.has(normalizedCell);
        }

        return {
            isCellWarm,
            markCellWarm,
            scheduleCells,
        };
    }

    window.CytoCVOverlayPrefetch = {
        buildCircularCellOrder,
        buildFullCircularCellOrder,
        createWarmCoordinator,
        targetCell,
    };
})();
