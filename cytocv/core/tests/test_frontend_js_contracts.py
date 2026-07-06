"""JavaScript contract tests for source syntax and shared viewer/export APIs."""

from __future__ import annotations

import shutil
import subprocess
import json

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .frontend_contract_helpers import CORE_STATIC_ROOT, assert_in_order, create_display_file, login_user, response_text, static_text


class FrontendJavaScriptStaticContractTests(SimpleTestCase):
    """Validate static JS without requiring a browser or Node build pipeline."""

    def test_static_javascript_passes_node_syntax_check_when_node_is_available(self):
        # Node validation catches syntax regressions in comments-adjacent edits
        # without requiring the full Django test client or a browser.
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not available for static JavaScript syntax checks.")

        for js_path in (CORE_STATIC_ROOT / "js").rglob("*.js"):
            with self.subTest(js=js_path.relative_to(CORE_STATIC_ROOT)):
                result = subprocess.run(
                    [node, "--check", str(js_path)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_expected_window_globals_are_defined_by_their_owner_files(self):
        # Shared page controllers communicate through explicit globals because
        # the project serves Django templates without a frontend bundler.
        owner_contracts = {
            "js/export_selection_modal.js": "window.CytoCVExportSelection =",
            "js/viewer_overlay_prefetch.js": "window.CytoCVOverlayPrefetch =",
            "js/shared/async-progress.js": "window.CytoCVAsyncProgress =",
            "js/shared/base-interactions.js": "window.showGlobalMessage =",
            "js/shared/results-viewer.js": "global.CytoCVResultsViewerShared =",
            "js/shared/results-cell-actions.js": "global.CytoCVResultsCellActions =",
        }

        for path, marker in owner_contracts.items():
            with self.subTest(path=path):
                self.assertIn(marker, static_text(path))

    def test_workflow_defaults_tracks_result_display_filter_preference(self):
        source = static_text("js/workflow_defaults.js")

        self.assertIn("default_puncta_source_contour_count_filter", source)
        self.assertIn("defaultPunctaSourceContourCountFilter", source)
        self.assertIn("normalizePunctaSourceContourCountFilter", source)
        self.assertIn("punctaSourceContourCountFilterLabel", source)
        self.assertIn("Default Source Contour Count Filter:", source)
        self.assertIn("refreshCustomSelect(defaultPunctaSourceContourCountFilterInput)", source)

    def test_experiment_puncta_source_dropdown_exposes_single_channel_modes(self):
        source = static_text("js/pages/experiment.js")

        for key, label in (
            ("red_puncta", "Red Puncta (Measure Green)"),
            ("green_puncta", "Green Puncta (Measure Red)"),
            ("red_puncta_only", "Red Puncta Only"),
            ("green_puncta_only", "Green Puncta Only"),
        ):
            with self.subTest(mode=key):
                self.assertIn(key, source)
                self.assertIn(label, source)

        self.assertIn("statsPayload.puncta_line_modes", source)
        self.assertIn("punctaPlugin.puncta_line_modes", source)
        assert_in_order(
            self,
            source,
            "function renderSignalQuantificationModule(list)",
            "punctaLineModeSelect = buildCustomModeSelect(",
            "punctaModeOptions,",
        )
        self.assertNotIn("getDisabledPunctaModeValues", source)

    def test_experiment_upload_uses_metadata_not_manual_missing_channel_selector(self):
        source = static_text("js/pages/experiment.js")

        self.assertNotIn("Missing Channel For 3-Plane Files", source)
        self.assertNotIn("Missing Blue", source)
        self.assertNotIn("Missing Red", source)
        self.assertNotIn("Missing Green", source)
        self.assertNotIn("prepData.append('missing_channel'", source)
        self.assertNotIn("normalizeMissingChannel", source)

    def test_experiment_single_channel_puncta_modes_drive_required_channels(self):
        source = static_text("js/pages/experiment.js")

        self.assertIn("function getPunctaModeRequiredChannels", source)
        self.assertIn("if (normalized === 'red_puncta_only') return ['channel_red'];", source)
        self.assertIn("if (normalized === 'green_puncta_only') return ['channel_green'];", source)
        self.assertIn("return ['channel_red', 'channel_green'];", source)
        self.assertIn("return getPunctaModeRequiredChannels();", source)
        self.assertIn("isSingleChannelPunctaSignalModeActive() && redGreenPairedPluginIds.has(pluginId)", source)
        self.assertIn("Single-channel puncta mode on. Paired Red/Green modules disabled.", source)
        self.assertIn("if (mode === 'red_puncta_only') return 'Red Contour Intensities';", source)
        self.assertIn("if (mode === 'green_puncta_only') return 'Green Contour Intensities';", source)

    def test_experiment_single_channel_puncta_modes_pause_without_forgetting_paired_modules(self):
        source = static_text("js/pages/experiment.js")

        self.assertNotIn(
            "redGreenPairedPluginIds.forEach((pluginId) => statsState.selectedPlugins.delete(pluginId));",
            source,
        )
        assert_in_order(
            self,
            source,
            "function syncSignalSelectedPlugins()",
            "statsState.selectedPlugins.add('PunctaDistance');",
            "if (statsState.punctaContourIntensityEnabled && !isSingleChannelPunctaMode())",
        )
        assert_in_order(
            self,
            source,
            "function getEffectiveSelectedPlugins()",
            "if (isSingleChannelPunctaSignalModeActive())",
            "[...statsState.selectedPlugins].filter((pluginId) => !redGreenPairedPluginIds.has(pluginId))",
        )
        self.assertIn(
            "return isSingleChannelPunctaSignalModeActive() && redGreenPairedPluginIds.has(pluginId);",
            source,
        )

    def test_export_selection_quick_select_js_uses_metadata_not_labels(self):
        source = static_text("js/export_selection_modal.js")

        self.assertIn("family !== 'contour_intensity'", source)
        self.assertIn("item.combination", source)
        self.assertIn("item.statistic", source)
        self.assertIn("Number(item.slot)", source)
        self.assertNotIn("Red In Red", source)
        self.assertNotIn("Total Intensity", source)

    def test_export_selection_counts_use_text_fade(self):
        source = static_text("js/export_selection_modal.js")

        self.assertIn("updateTextWithFade(\n          statCountEl,", source)
        self.assertIn("updateTextWithFade(\n          fileCountEl,", source)
        self.assertNotIn("statCountEl.textContent = count === 1", source)
        self.assertNotIn("fileCountEl.textContent = count === 1", source)

    def test_contour_intensity_selector_uses_slider_state_and_text_blend(self):
        shared_source = static_text("js/shared/results-viewer.js")
        display_source = static_text("js/pages/display-viewer.js")
        dashboard_source = static_text("js/pages/dashboard-viewer.js")

        self.assertIn("document.querySelectorAll('.contour-intensity-toggle')", shared_source)
        self.assertIn("toggle.dataset.activeIntensity = normalizedType;", shared_source)

        for name, source in (("display", display_source), ("dashboard", dashboard_source)):
            with self.subTest(source=name):
                self.assertIn(
                    "document.querySelectorAll('[data-contour-intensity-type-label]')",
                    source,
                )
                self.assertIn(
                    "setTextWithBlend(element, contourIntensityTypeLabel, { blend: blendText })",
                    source,
                )
                self.assertNotIn(
                    "element.textContent = state.labels.contourIntensityTypeLabel || 'Total';",
                    source,
                )

    def test_export_selection_contour_intensity_helpers_select_concrete_fields(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not available for static JavaScript helper checks.")

        js_path = CORE_STATIC_ROOT / "js" / "export_selection_modal.js"
        script = f"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync({json.dumps(str(js_path))}, 'utf8');
const context = {{ window: {{}} }};
vm.runInNewContext(source, context);
const hooks = context.window.CytoCVExportSelection.__testHooks;
assert.ok(hooks);

const combinations = ['red_in_red', 'green_in_red', 'red_in_green', 'green_in_green'];
const statistics = ['total', 'max', 'average'];
const slots = [1, 2, 3];
const items = [];
for (const combination of combinations) {{
  for (const statistic of statistics) {{
    for (const slot of slots) {{
      items.push({{
        id: `${{combination}}_${{statistic}}_intensity_${{slot}}`,
        tableField: `${{combination}}_${{statistic}}_intensity_${{slot}}`,
        family: 'contour_intensity',
        combination,
        statistic,
        slot,
      }});
    }}
  }}
}}
items.push({{ id: 'puncta_distance', tableField: 'puncta_distance', group: 'puncta_distance' }});
const concreteIds = new Set(items.map((item) => item.id));

function selectedIntensityIds(selected) {{
  return Array.from(selected).filter((id) => id.includes('_intensity_'));
}}

function assertConcreteSelection(selected) {{
  for (const id of selected) {{
    assert.ok(concreteIds.has(id), `expected concrete field id: ${{id}}`);
    assert.notStrictEqual(id, 'contour_intensity');
  }}
}}

function choose(filters, starting = ['puncta_distance']) {{
  const selected = new Set(hooks.applyContourIntensitySelection(items, starting, filters));
  assertConcreteSelection(selected);
  return selected;
}}

function filtersToObject(filters) {{
  return {{
    statistics: Array.from(filters.statistics).sort(),
    slots: Array.from(filters.slots).sort((a, b) => a - b),
    combinations: Array.from(filters.combinations).sort(),
  }};
}}

const scopedCurrentFilters = {{
  statistics: ['max', 'average'],
  slots: [2],
  combinations: ['red_in_red', 'green_in_green'],
}};
assert.deepStrictEqual(filtersToObject(hooks.intensityFiltersForAction('totals', scopedCurrentFilters)), {{
  statistics: ['total'],
  slots: [2],
  combinations: ['green_in_green', 'red_in_red'],
}});
assert.deepStrictEqual(filtersToObject(hooks.intensityFiltersForAction('total_max', scopedCurrentFilters)), {{
  statistics: ['max', 'total'],
  slots: [2],
  combinations: ['green_in_green', 'red_in_red'],
}});
assert.deepStrictEqual(filtersToObject(hooks.intensityFiltersForAction('average', scopedCurrentFilters)), {{
  statistics: ['average'],
  slots: [2],
  combinations: ['green_in_green', 'red_in_red'],
}});
assert.deepStrictEqual(filtersToObject(hooks.intensityFiltersForAction('slots_1_2', scopedCurrentFilters)), {{
  statistics: ['average', 'max'],
  slots: [1, 2],
  combinations: ['green_in_green', 'red_in_red'],
}});
assert.deepStrictEqual(filtersToObject(hooks.intensityFiltersForAction('clear', scopedCurrentFilters)), {{
  statistics: [],
  slots: [],
  combinations: [],
}});
assert.deepStrictEqual(filtersToObject(hooks.intensityFiltersForAction('all', scopedCurrentFilters)), {{
  statistics: ['average', 'max', 'total'],
  slots,
  combinations: ['green_in_green', 'green_in_red', 'red_in_green', 'red_in_red'],
}});

const scopedTotals = choose(
  hooks.intensityFiltersForAction('totals', scopedCurrentFilters),
  ['puncta_distance', 'red_in_red_max_intensity_1']
);
assert.deepStrictEqual(
  selectedIntensityIds(scopedTotals).sort(),
  ['green_in_green_total_intensity_2', 'red_in_red_total_intensity_2'].sort()
);
assert.ok(scopedTotals.has('puncta_distance'));

const clearedViaPreset = choose(
  hooks.intensityFiltersForAction('clear', scopedCurrentFilters),
  ['puncta_distance', 'red_in_red_total_intensity_1']
);
assert.deepStrictEqual(Array.from(clearedViaPreset), ['puncta_distance']);

const allViaPreset = choose(hooks.intensityFiltersForAction('all', scopedCurrentFilters));
assert.strictEqual(selectedIntensityIds(allViaPreset).length, 36);
assert.ok(allViaPreset.has('puncta_distance'));

const totalOnly = choose({{
  statistics: ['total'],
  slots,
  combinations,
}});
assert.strictEqual(selectedIntensityIds(totalOnly).length, 12);
assert.ok(totalOnly.has('puncta_distance'));
assert.ok(Array.from(totalOnly).every((id) => id === 'puncta_distance' || id.includes('_total_intensity_')));

const totalMax = choose({{
  statistics: ['total', 'max'],
  slots,
  combinations,
}});
assert.strictEqual(selectedIntensityIds(totalMax).length, 24);
assert.ok(Array.from(totalMax).some((id) => id.includes('_max_intensity_')));
assert.ok(!Array.from(totalMax).some((id) => id.includes('_average_intensity_')));

const averageOnly = choose({{
  statistics: ['average'],
  slots,
  combinations,
}});
assert.strictEqual(selectedIntensityIds(averageOnly).length, 12);
assert.ok(Array.from(averageOnly).every((id) => (
  id === 'puncta_distance' || id.includes('_average_intensity_')
)));

const slotsOneTwo = choose({{
  statistics,
  slots: [1, 2],
  combinations,
}});
assert.strictEqual(selectedIntensityIds(slotsOneTwo).length, 24);
assert.ok(!Array.from(slotsOneTwo).some((id) => id.endsWith('_3')));

const sameChannelTotals = choose({{
  statistics: ['total'],
  slots: [1, 2],
  combinations: ['red_in_red', 'green_in_green'],
}});
assert.deepStrictEqual(
  selectedIntensityIds(sameChannelTotals).sort(),
  [
    'green_in_green_total_intensity_1',
    'green_in_green_total_intensity_2',
    'red_in_red_total_intensity_1',
    'red_in_red_total_intensity_2',
  ].sort()
);

const averageSlotThree = choose({{
  statistics: ['average'],
  slots: [3],
  combinations,
}});
assert.strictEqual(selectedIntensityIds(averageSlotThree).length, 4);
assert.ok(Array.from(averageSlotThree).every((id) => (
  id === 'puncta_distance' || (id.includes('_average_intensity_') && id.endsWith('_3'))
)));

const cleared = new Set(hooks.clearContourIntensitySelection(items, Array.from(totalMax)));
assert.deepStrictEqual(Array.from(cleared), ['puncta_distance']);

const unavailableSelection = new Set(hooks.applyContourIntensitySelection(
  items,
  ['puncta_distance'],
  {{ statistics, slots, combinations }},
  {{ applicable: false }}
));
assert.deepStrictEqual(Array.from(unavailableSelection), ['puncta_distance']);
assert.strictEqual(
  hooks.formatContourIntensitySummary(items, Array.from(unavailableSelection), false),
  'Contour intensity was not computed for this file set.'
);
assert.strictEqual(hooks.isContourIntensityAvailable(null, true), true);
assert.strictEqual(hooks.isContourIntensityAvailable({{ red_green_intensity: false }}, true), false);
assert.strictEqual(hooks.contourIntensityActiveFilterCount({{
  statistics,
  slots,
  combinations,
}}), 0);
assert.strictEqual(hooks.formatContourIntensityFilterStatus({{
  statistics,
  slots,
  combinations,
}}), '0 filters applied');
assert.strictEqual(hooks.contourIntensityActiveFilterCount({{
  statistics: ['total'],
  slots,
  combinations,
}}), 1);
assert.strictEqual(hooks.formatContourIntensityFilterStatus({{
  statistics: ['total'],
  slots,
  combinations,
}}), '1 filter applied');
assert.strictEqual(hooks.contourIntensityActiveFilterCount({{
  statistics,
  slots: [1, 2],
  combinations,
}}), 1);
assert.strictEqual(hooks.contourIntensityActiveFilterCount({{
  statistics: ['total', 'max'],
  slots: [1, 2],
  combinations,
}}), 2);
assert.strictEqual(hooks.formatContourIntensityFilterStatus({{
  statistics: ['total', 'max'],
  slots: [1, 2],
  combinations,
}}), '2 filters applied');
assert.strictEqual(hooks.contourIntensityActiveFilterCount({{
  statistics: ['total'],
  slots: [1, 2],
  combinations: ['red_in_red', 'green_in_green'],
}}), 3);
const statusElement = {{
  textContent: '0 filters applied',
  classList: {{
    values: new Set(),
    add(value) {{ this.values.add(value); }},
    remove(value) {{ this.values.delete(value); }},
    contains(value) {{ return this.values.has(value); }},
  }},
}};
assert.strictEqual(hooks.updateTextWithFade(statusElement, '1 filter applied'), true);
assert.strictEqual(statusElement.textContent, '1 filter applied');
assert.strictEqual(statusElement.classList.contains('is-updating'), false);
assert.strictEqual(hooks.updateTextWithFade(statusElement, '1 filter applied'), false);

const startingSelection = [
  'puncta_distance',
  'red_in_red_total_intensity_1',
  'green_in_green_average_intensity_3',
];
const snapshot = hooks.captureContourIntensitySelection(items, startingSelection);
assert.deepStrictEqual(
  snapshot.sort(),
  ['green_in_green_average_intensity_3', 'red_in_red_total_intensity_1'].sort()
);
const changedSelection = hooks.applyContourIntensitySelection(
  items,
  ['puncta_distance', 'red_in_red_max_intensity_2'],
  {{ statistics: ['max'], slots: [2], combinations: ['red_in_red'] }}
);
assert.ok(changedSelection.includes('red_in_red_max_intensity_2'));
assert.ok(changedSelection.includes('puncta_distance'));
const restoredSelection = hooks.restoreContourIntensitySelection(
  items,
  changedSelection,
  snapshot
);
assertConcreteSelection(restoredSelection);
assert.ok(restoredSelection.includes('puncta_distance'));
assert.ok(restoredSelection.includes('red_in_red_total_intensity_1'));
assert.ok(restoredSelection.includes('green_in_green_average_intensity_3'));
assert.ok(!restoredSelection.includes('red_in_red_max_intensity_2'));
const unavailableRestore = hooks.restoreContourIntensitySelection(
  items,
  changedSelection,
  snapshot,
  {{ applicable: false }}
);
assert.deepStrictEqual(Array.from(unavailableRestore), ['puncta_distance']);
let fileType = 'xlsx';
hooks.applyContourIntensitySelection(items, ['puncta_distance'], {{
  statistics: ['total'],
  slots: [1],
  combinations: ['red_in_red'],
}});
assert.strictEqual(fileType, 'xlsx');

const manualOverride = new Set(totalOnly);
manualOverride.add('red_in_red_average_intensity_1');
manualOverride.delete('red_in_red_total_intensity_1');
assert.ok(manualOverride.has('red_in_red_average_intensity_1'));
assert.ok(!manualOverride.has('red_in_red_total_intensity_1'));
assert.strictEqual(hooks.contourIntensitySelectedCount(items, Array.from(manualOverride)), 12);
assert.strictEqual(
  hooks.formatContourIntensitySummary(items, Array.from(manualOverride), true),
  '12 intensity columns selected'
);
"""
        result = subprocess.run(
            [node, "-e", script],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_results_viewer_shared_namespace_exposes_documented_helpers(self):
        source = static_text("js/shared/results-viewer.js")
        for helper_name in (
            "readJsonConfig",
            "createBlendHelpers",
            "preloadImageSet",
            "getSortedCellIds",
            "getCircularWarmQueue",
            "normalizeMainImageChannel",
            "createMainImageHelpers",
            "createStatisticsHelpers",
            "getEffectiveCellCardMode",
            "getVisibleCellCardSections",
            "getContourIntensityDisplayFields",
            "bindContourIntensityDisplayControls",
            "setCellPairImagesLoading",
            "setCellDataRegionLoading",
            "createCellDataRegionLoadingController",
            "bindFilterMenuPointerAwayClose",
        ):
            with self.subTest(helper=helper_name):
                self.assertIn(helper_name, source)

    def test_cell_data_region_loading_controller_keeps_regions_busy_through_transition(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not available for static JavaScript helper checks.")

        js_path = CORE_STATIC_ROOT / "js" / "shared" / "results-viewer.js"
        script = f"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync({json.dumps(str(js_path))}, 'utf8');
const context = {{ window: {{}} }};
vm.runInNewContext(source, context);
const shared = context.window.CytoCVResultsViewerShared;

function makeRegion() {{
  const classes = new Set();
  const attributes = {{}};
  return {{
    classList: {{
      toggle: (name, enabled) => enabled ? classes.add(name) : classes.delete(name),
      contains: (name) => classes.has(name),
    }},
    setAttribute: (name, value) => {{ attributes[name] = value; }},
    getAttribute: (name) => attributes[name],
  }};
}}

(async () => {{
  const table = makeRegion();
  const strip = makeRegion();
  const root = {{
    querySelector: (selector) => selector === '#tableScrollFrame' ? table : null,
    querySelectorAll: (selector) => selector === '[data-ui-region="cell-metrics-strip"]' ? [strip] : [],
  }};
  let now = 0;
  const waits = [];
  const controller = shared.createCellDataRegionLoadingController({{
    root,
    minimumDurationMs: 160,
    getNow: () => now,
    wait: (ms) => {{
      waits.push(ms);
      now += ms;
      return Promise.resolve();
    }},
  }});

  const result = await controller.run(async () => {{
    assert.strictEqual(table.classList.contains('is-contour-filter-applying'), true);
    assert.strictEqual(strip.classList.contains('is-contour-filter-applying'), true);
    assert.strictEqual(table.getAttribute('aria-busy'), 'true');
    now += 40;
    return 'rendered';
  }});

  assert.strictEqual(result, 'rendered');
  assert.deepStrictEqual(waits, [120]);
  assert.strictEqual(table.classList.contains('is-contour-filter-applying'), false);
  assert.strictEqual(strip.classList.contains('is-contour-filter-applying'), false);
  assert.strictEqual(table.getAttribute('aria-busy'), 'false');
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
        result = subprocess.run(
            [node, "-e", script],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_cell_pair_card_mode_visibility_and_contour_display_helpers(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not available for static JavaScript helper checks.")

        js_path = CORE_STATIC_ROOT / "js" / "shared" / "results-viewer.js"
        script = f"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync({json.dumps(str(js_path))}, 'utf8');

function makeClassList() {{
  const values = new Set();
  return {{
    toggle(name, force) {{
      if (force) values.add(name);
      else values.delete(name);
    }},
    contains(name) {{
      return values.has(name);
    }},
  }};
}}

function makeButton(type) {{
  return {{
    dataset: {{ contourIntensityDisplay: type }},
    attrs: {{}},
    classList: makeClassList(),
    handlers: {{}},
    setAttribute(name, value) {{
      this.attrs[name] = value;
    }},
    addEventListener(eventName, handler) {{
      this.handlers[eventName] = handler;
    }},
  }};
}}

function makeElement(dataset = {{}}) {{
  return {{
    dataset: {{ ...dataset }},
    attrs: {{}},
    hidden: false,
    classList: makeClassList(),
    setAttribute(name, value) {{
      this.attrs[name] = value;
    }},
    querySelectorAll() {{
      return [];
    }},
  }};
}}

const selectorButtons = [makeButton('total'), makeButton('max'), makeButton('average')];
const contourIntensityToggle = makeElement({{ activeIntensity: '' }});
const rootEl = makeElement({{ cellCardMode: 'puncta_distance' }});
const referenceSection = makeElement({{ cellCardSection: 'reference' }});
const nuclearSection = makeElement({{ cellCardSection: 'nuclear_cell_pair_intensity' }});
const punctaSection = makeElement({{ cellCardSection: 'puncta_distance' }});
const biorientationSection = makeElement({{ cellCardSection: 'biorientation' }});
const cenDotSection = makeElement({{ cellCardSection: 'cen_dot' }});
const measurementSection = makeElement({{ cellCardSection: 'measurement_contour' }});
const contourSection = makeElement({{ cellCardSection: 'contour_intensity' }});
const redInRedCombination = makeElement({{ contourIntensityCombination: 'red_in_red' }});
const greenInRedCombination = makeElement({{ contourIntensityCombination: 'green_in_red' }});
const redInGreenCombination = makeElement({{ contourIntensityCombination: 'red_in_green' }});
const greenInGreenCombination = makeElement({{ contourIntensityCombination: 'green_in_green' }});
const detailRow = makeElement();
detailRow.querySelectorAll = (selector) => (
  selector === '[data-cell-card-section]' ? [measurementSection, contourSection] : []
);
const statRows = [
  makeElement({{ statRow: 'puncta_distance' }}),
  makeElement({{ statRow: 'cen_dot' }}),
];
const cellCardSections = [
  referenceSection,
  nuclearSection,
  punctaSection,
  biorientationSection,
  cenDotSection,
  measurementSection,
  contourSection,
];
const contourIntensityCombinations = [
  redInRedCombination,
  greenInRedCombination,
  redInGreenCombination,
  greenInGreenCombination,
];
const context = {{
  window: {{}},
  document: {{
    querySelectorAll(selector) {{
      if (selector === '.contour-intensity-toggle') return [contourIntensityToggle];
      if (selector === '[data-contour-intensity-display]') return selectorButtons;
      if (selector === '[data-cell-card-root]') return [rootEl];
      if (selector === '[data-contour-intensity-combination]') return contourIntensityCombinations;
      if (selector === '[data-cell-card-section]') return cellCardSections;
      if (selector === '[data-stat-section]:not([data-cell-card-section])') return [];
      if (selector === '[data-stat-row]') return statRows;
      if (selector === '[data-cell-card-detail-row]') return [detailRow];
      return [];
    }},
  }},
}};
vm.runInNewContext(source, context);
const shared = context.window.CytoCVResultsViewerShared;
const trueKeys = (sections) => Object.entries(sections)
  .filter(([, value]) => value === true)
  .map(([key]) => key)
  .sort();
const ownArray = (values) => Array.from(values);

assert.strictEqual(
  shared.getEffectiveCellCardMode({{ signal_quantification_mode: 'nuclear_cell_pair' }}),
  'nuclear_cell_pair'
);
assert.strictEqual(
  shared.getEffectiveCellCardMode({{ signal_quantification_mode: 'puncta_distance' }}),
  'puncta_distance'
);
assert.strictEqual(
  shared.getEffectiveCellCardMode({{
    stat_visibility: {{ nuclear_cell_pair_intensity: true, puncta_distance: false }},
  }}),
  'nuclear_cell_pair'
);
assert.strictEqual(
  shared.getEffectiveCellCardMode({{ selected_analysis: ['NuclearCellPairIntensity'] }}),
  'nuclear_cell_pair'
);
assert.strictEqual(shared.getEffectiveCellCardMode({{}}), 'puncta_distance');

const nuclearStats = {{
  signal_quantification_mode: 'nuclear_cell_pair',
  selected_analysis: ['NuclearCellPairIntensity'],
  stat_visibility: {{
    nuclear_cell_pair_intensity: true,
    puncta_distance: false,
    red_green_intensity: false,
    cen_dot: false,
    biorientation: false,
  }},
  nucleus_intensity_sum: 40,
  cell_pair_intensity_sum: 100,
  cytoplasmic_intensity: 60,
  nuclear_cytoplasmic_ratio: 0.667,
  red_in_red_total_intensity_1: 500,
  category_cen_dot: 1,
  colinear_dots: 2,
}};
assert.deepStrictEqual(
  trueKeys(shared.getVisibleCellCardSections(nuclearStats)),
  ['nuclear_cell_pair_intensity', 'reference']
);

const punctaStats = {{
  signal_quantification_mode: 'puncta_distance',
  selected_analysis: ['PunctaDistance', 'GreenRedIntensity', 'CENDot', 'Biorientation'],
  stat_visibility: {{
    nuclear_cell_pair_intensity: false,
    puncta_distance: true,
    red_green_intensity: true,
    cen_dot: true,
    biorientation: true,
  }},
  puncta_distance: 7,
  puncta_line_intensity: 13,
  measurement_contour_ratio_1: 0,
  measurement_contour_ratio_2: 1.25,
  measurement_contour_ratio_3: null,
  measurement_contour_ratio_display_text: 'Red / green contour intensity',
  red_in_red_total_intensity_1: 11,
  red_in_red_max_intensity_1: 111,
  red_in_red_average_intensity_1: 1.5,
  green_in_red_total_intensity_1: 12,
  red_in_green_total_intensity_1: 13,
  green_in_green_total_intensity_1: 14,
  category_cen_dot_label: 'CEN dot',
  cell_parentage_label: 'Mother/Daughter identified',
  colinear_dots: 0,
  off_axis_dots: 1,
}};
assert.deepStrictEqual(
  trueKeys(shared.getVisibleCellCardSections(punctaStats)),
  [
    'biorientation',
    'cen_dot',
    'contour_intensity',
    'measurement_contour',
    'puncta_distance',
    'reference',
  ]
);

const punctaWithoutIndependentModules = {{
  ...punctaStats,
  selected_analysis: ['PunctaDistance'],
  stat_visibility: {{
    nuclear_cell_pair_intensity: false,
    puncta_distance: true,
    red_green_intensity: false,
    cen_dot: false,
    biorientation: false,
  }},
}};
assert.deepStrictEqual(
  trueKeys(shared.getVisibleCellCardSections(punctaWithoutIndependentModules)),
  ['puncta_distance', 'reference']
);

const redGreenDisabledWithLegacyValues = {{
  ...punctaStats,
  stat_visibility: {{
    nuclear_cell_pair_intensity: false,
    puncta_distance: true,
    red_green_intensity: false,
    cen_dot: false,
    biorientation: false,
  }},
}};
const disabledSections = shared.getVisibleCellCardSections(redGreenDisabledWithLegacyValues);
assert.strictEqual(disabledSections.measurement_contour, false);
assert.strictEqual(disabledSections.contour_intensity, false);

const expectedCombinations = ['red_in_red', 'green_in_red', 'red_in_green', 'green_in_green'];
assert.deepStrictEqual(
  ownArray(shared.getVisibleContourIntensityCombinations(punctaStats)),
  expectedCombinations
);
const redOnlyStats = {{
  ...punctaStats,
  puncta_line_mode: 'red_puncta_only',
  measurement_contour_ratio_1: null,
  measurement_contour_ratio_2: null,
  measurement_contour_ratio_3: null,
  measurement_contour_ratio_display_text: 'N/A',
  green_in_red_total_intensity_1: 12,
  red_in_green_total_intensity_1: 13,
  green_in_green_total_intensity_1: 14,
}};
assert.deepStrictEqual(ownArray(shared.getVisibleContourIntensityCombinations(redOnlyStats)), ['red_in_red']);
assert.deepStrictEqual(
  trueKeys(shared.getVisibleCellCardSections(redOnlyStats)),
  ['biorientation', 'cen_dot', 'contour_intensity', 'puncta_distance', 'reference']
);
const greenOnlyStats = {{
  ...punctaStats,
  puncta_line_mode: 'green_puncta_only',
  measurement_contour_ratio_1: null,
  measurement_contour_ratio_2: null,
  measurement_contour_ratio_3: null,
  measurement_contour_ratio_display_text: 'N/A',
  red_in_red_total_intensity_1: 11,
  green_in_red_total_intensity_1: 12,
  red_in_green_total_intensity_1: 13,
  green_in_green_total_intensity_1: 14,
}};
assert.deepStrictEqual(ownArray(shared.getVisibleContourIntensityCombinations(greenOnlyStats)), ['green_in_green']);
assert.deepStrictEqual(
  trueKeys(shared.getVisibleCellCardSections(greenOnlyStats)),
  ['biorientation', 'cen_dot', 'contour_intensity', 'puncta_distance', 'reference']
);
for (const type of ['total', 'max', 'average']) {{
  const fields = shared.getContourIntensityDisplayFields(type);
  assert.strictEqual(fields.length, 12);
  assert.ok(fields.every((field) => field.statistic === type));
  assert.ok(fields.every((field) => field.fieldName.includes(`_${{type}}_intensity_`)));
  assert.strictEqual(
    JSON.stringify(Array.from(new Set(fields.map((field) => field.combination)))),
    JSON.stringify(expectedCombinations)
  );
}}
assert.strictEqual(
  JSON.stringify(shared.getContourIntensityDisplayFields('total').slice(0, 3).map((field) => field.fieldName)),
  JSON.stringify([
    'red_in_red_total_intensity_1',
    'red_in_red_total_intensity_2',
    'red_in_red_total_intensity_3',
  ])
);
assert.strictEqual(
  JSON.stringify(shared.getContourIntensityDisplayFields('max').slice(0, 3).map((field) => field.fieldName)),
  JSON.stringify([
    'red_in_red_max_intensity_1',
    'red_in_red_max_intensity_2',
    'red_in_red_max_intensity_3',
  ])
);
assert.strictEqual(
  JSON.stringify(shared.getContourIntensityDisplayFields('average').slice(0, 3).map((field) => field.fieldName)),
  JSON.stringify([
    'red_in_red_average_intensity_1',
    'red_in_red_average_intensity_2',
    'red_in_red_average_intensity_3',
  ])
);
const allGeneratedFields = shared.getAllContourIntensityDisplayFields().map((field) => field.fieldName);
assert.strictEqual(allGeneratedFields.length, 36);
for (const oldName of [
  'red_in_red_intensity_1',
  'green_in_red_intensity_1',
  'red_in_green_intensity_1',
  'green_in_green_intensity_1',
]) {{
  assert.ok(!allGeneratedFields.includes(oldName));
}}

let currentType = 'total';
let rerenderedType = null;
const exportState = {{ activeFormat: 'xlsx' }};
const selectedMetricCheckbox = {{ checked: true }};
shared.bindContourIntensityDisplayControls({{
  getCurrentType: () => currentType,
  setCurrentType: (type) => {{
    currentType = type;
  }},
  rerender: (type) => {{
    rerenderedType = type;
  }},
}});
assert.strictEqual(contourIntensityToggle.dataset.activeIntensity, 'total');
assert.strictEqual(selectorButtons[0].attrs['aria-pressed'], 'true');
assert.strictEqual(selectorButtons[0].classList.contains('active'), true);
assert.strictEqual(selectorButtons[1].attrs['aria-pressed'], 'false');
selectorButtons[1].handlers.click();
assert.strictEqual(currentType, 'max');
assert.strictEqual(rerenderedType, 'max');
assert.strictEqual(contourIntensityToggle.dataset.activeIntensity, 'max');
assert.strictEqual(selectorButtons[0].attrs['aria-pressed'], 'false');
assert.strictEqual(selectorButtons[1].attrs['aria-pressed'], 'true');
selectorButtons[2].handlers.click();
assert.strictEqual(currentType, 'average');
assert.strictEqual(rerenderedType, 'average');
assert.strictEqual(contourIntensityToggle.dataset.activeIntensity, 'average');
assert.deepStrictEqual(exportState, {{ activeFormat: 'xlsx' }});
assert.strictEqual(selectedMetricCheckbox.checked, true);

const helpers = shared.createStatisticsHelpers({{
  tableFieldOrder: [],
  statFieldGroups: {{}},
  spatialFieldKinds: {{}},
  spatialHeaderBaseLabels: {{}},
  defaultSpatialStatsUnit: 'px',
  getCurrentSpatialStatsUnit: () => 'px',
  setCurrentSpatialStatsUnit: () => {{}},
}});
const builtTotal = helpers.buildCellCardMetricValues(punctaStats, {{ contourIntensityType: 'total' }});
assert.strictEqual(builtTotal.contourIntensityType, 'total');
assert.strictEqual(builtTotal.metricValues.redInRedIntensity1, '11');
assert.strictEqual(builtTotal.metricValues.measurementContourRatio1, '0');
assert.strictEqual(builtTotal.metricValues.colinearDots, '0');
assert.strictEqual(builtTotal.labels.contourIntensityTypeLabel, 'Total');
assert.strictEqual(builtTotal.labels.contourIntensityLabels.redInRedIntensity1, 'Red In Red Total Intensity 1');
assert.deepStrictEqual(ownArray(builtTotal.visibleContourIntensityCombinations), expectedCombinations);
const builtRedOnly = helpers.buildCellCardMetricValues(redOnlyStats, {{ contourIntensityType: 'total' }});
assert.deepStrictEqual(ownArray(builtRedOnly.visibleContourIntensityCombinations), ['red_in_red']);
assert.strictEqual(builtRedOnly.sections.measurement_contour, false);
assert.strictEqual(builtRedOnly.sections.contour_intensity, true);
const builtGreenOnly = helpers.buildCellCardMetricValues(greenOnlyStats, {{ contourIntensityType: 'total' }});
assert.deepStrictEqual(ownArray(builtGreenOnly.visibleContourIntensityCombinations), ['green_in_green']);
assert.strictEqual(builtGreenOnly.sections.measurement_contour, false);
assert.strictEqual(builtGreenOnly.sections.contour_intensity, true);
const builtMax = helpers.buildCellCardMetricValues(punctaStats, {{ contourIntensityType: 'max' }});
assert.strictEqual(builtMax.contourIntensityType, 'max');
assert.strictEqual(builtMax.metricValues.redInRedIntensity1, '111');
assert.strictEqual(builtMax.labels.contourIntensityTypeLabel, 'Max');
assert.strictEqual(builtMax.labels.contourIntensityLabels.redInRedIntensity1, 'Red In Red Max Intensity 1');
const builtAverage = helpers.buildCellCardMetricValues(punctaStats, {{ contourIntensityType: 'average' }});
assert.strictEqual(builtAverage.contourIntensityType, 'average');
assert.strictEqual(builtAverage.metricValues.redInRedIntensity1, '1.500');
assert.strictEqual(builtAverage.labels.contourIntensityTypeLabel, 'Average');
assert.strictEqual(builtAverage.labels.contourIntensityLabels.redInRedIntensity1, 'Red In Red Average Intensity 1');

helpers.applyMetricVisibility(
  shared.getVisibleCellCardSections(nuclearStats),
  {{ mode: shared.getEffectiveCellCardMode(nuclearStats) }}
);
assert.strictEqual(rootEl.dataset.cellCardMode, 'nuclear_cell_pair');
assert.strictEqual(referenceSection.hidden, false);
assert.strictEqual(nuclearSection.hidden, false);
assert.strictEqual(punctaSection.hidden, true);
assert.strictEqual(biorientationSection.hidden, true);
assert.strictEqual(cenDotSection.hidden, true);
assert.strictEqual(measurementSection.hidden, true);
assert.strictEqual(contourSection.hidden, true);
assert.strictEqual(detailRow.hidden, true);

helpers.applyMetricVisibility(
  shared.getVisibleCellCardSections(punctaStats),
  {{ mode: shared.getEffectiveCellCardMode(punctaStats) }}
);
assert.strictEqual(rootEl.dataset.cellCardMode, 'puncta_distance');
assert.strictEqual(rootEl.dataset.contourIntensityCombinationCount, '4');
assert.strictEqual(referenceSection.hidden, false);
assert.strictEqual(nuclearSection.hidden, true);
assert.strictEqual(punctaSection.hidden, false);
assert.strictEqual(biorientationSection.hidden, false);
assert.strictEqual(cenDotSection.hidden, false);
assert.strictEqual(measurementSection.hidden, false);
assert.strictEqual(contourSection.hidden, false);
assert.strictEqual(redInRedCombination.hidden, false);
assert.strictEqual(greenInRedCombination.hidden, false);
assert.strictEqual(redInGreenCombination.hidden, false);
assert.strictEqual(greenInGreenCombination.hidden, false);
assert.strictEqual(detailRow.hidden, false);

helpers.applyMetricVisibility(
  shared.getVisibleCellCardSections(redOnlyStats),
  {{
    mode: shared.getEffectiveCellCardMode(redOnlyStats),
    contourIntensityCombinations: shared.getVisibleContourIntensityCombinations(redOnlyStats),
  }}
);
assert.strictEqual(rootEl.dataset.cellCardMode, 'puncta_distance');
assert.strictEqual(rootEl.dataset.contourIntensityCombinationCount, '1');
assert.strictEqual(measurementSection.hidden, true);
assert.strictEqual(contourSection.hidden, false);
assert.strictEqual(redInRedCombination.hidden, false);
assert.strictEqual(greenInRedCombination.hidden, true);
assert.strictEqual(redInGreenCombination.hidden, true);
assert.strictEqual(greenInGreenCombination.hidden, true);
assert.strictEqual(detailRow.hidden, false);

helpers.applyMetricVisibility(
  shared.getVisibleCellCardSections(greenOnlyStats),
  {{
    mode: shared.getEffectiveCellCardMode(greenOnlyStats),
    contourIntensityCombinations: shared.getVisibleContourIntensityCombinations(greenOnlyStats),
  }}
);
assert.strictEqual(rootEl.dataset.contourIntensityCombinationCount, '1');
assert.strictEqual(redInRedCombination.hidden, true);
assert.strictEqual(greenInRedCombination.hidden, true);
assert.strictEqual(redInGreenCombination.hidden, true);
assert.strictEqual(greenInGreenCombination.hidden, false);
assert.strictEqual(detailRow.hidden, false);
"""
        result = subprocess.run(
            [node, "-e", script],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_spatial_unit_control_binding_is_shared(self):
        shared_source = static_text("js/shared/results-viewer.js")
        display_source = static_text("js/pages/display-viewer.js")
        dashboard_source = static_text("js/pages/dashboard-viewer.js")

        self.assertIn("function bindSpatialUnitControls", shared_source)
        self.assertIn("[data-spatial-unit-toggle]", shared_source)
        self.assertIn("bindSpatialUnitControls({", display_source)
        self.assertIn("bindSpatialUnitControls({", dashboard_source)
        self.assertIn("getStatLabel: getExportSelectionStatLabel", display_source)
        self.assertIn("getStatLabel: getExportSelectionStatLabel", dashboard_source)
        self.assertIn("refreshStatLabels", static_text("js/export_selection_modal.js"))
        self.assertIn("refreshStatLabels", display_source)
        self.assertIn("refreshStatLabels", dashboard_source)
        self.assertNotIn("const sidebarSpatialUnitToggle", display_source)
        self.assertNotIn("const sidebarSpatialUnitToggle", dashboard_source)

    def test_shared_spatial_unit_binding_syncs_sidebar_table_and_modal_controls(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not available for static JavaScript helper checks.")

        js_path = CORE_STATIC_ROOT / "js" / "shared" / "results-viewer.js"
        script = f"""
(async () => {{
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync({json.dumps(str(js_path))}, 'utf8');

function makeClassList() {{
  const values = new Set();
  return {{
    toggle(name, force) {{
      if (force) values.add(name);
      else values.delete(name);
    }},
    contains(name) {{
      return values.has(name);
    }},
  }};
}}

function makeButton(unit) {{
  return {{
    dataset: {{ spatialUnit: unit }},
    attrs: {{}},
    classList: makeClassList(),
    handlers: {{}},
    setAttribute(name, value) {{
      this.attrs[name] = value;
    }},
    addEventListener(eventName, handler) {{
      this.handlers[eventName] = handler;
    }},
  }};
}}

function makeToggle(name) {{
  return {{
    name,
    dataset: {{}},
    buttons: [makeButton('px'), makeButton('um')],
    querySelectorAll(selector) {{
      assert.strictEqual(selector, '[data-spatial-unit]');
      return this.buttons;
    }},
  }};
}}

const toggles = [makeToggle('sidebar'), makeToggle('table'), makeToggle('modal')];
const context = {{
  window: {{}},
  document: {{
    querySelectorAll(selector) {{
      return selector === '[data-spatial-unit-toggle]' ? toggles : [];
    }},
  }},
}};
vm.runInNewContext(source, context);

let currentUnit = 'px';
let rerenderCount = 0;
const persistedUnits = [];
const helpers = context.window.CytoCVResultsViewerShared.createStatisticsHelpers({{
  tableFieldOrder: [],
  statFieldGroups: {{}},
  spatialFieldKinds: {{}},
  spatialHeaderBaseLabels: {{}},
  defaultSpatialStatsUnit: 'px',
  getCurrentSpatialStatsUnit: () => currentUnit,
  setCurrentSpatialStatsUnit: (unit) => {{
    currentUnit = unit;
  }},
}});

function assertSynced(expectedUnit) {{
  for (const toggle of toggles) {{
    assert.strictEqual(toggle.dataset.activeUnit, expectedUnit);
    for (const button of toggle.buttons) {{
      const active = button.dataset.spatialUnit === expectedUnit;
      assert.strictEqual(button.attrs['aria-pressed'], active ? 'true' : 'false');
      assert.strictEqual(button.classList.contains('active'), active);
    }}
  }}
}}

helpers.bindSpatialUnitControls({{
  getCurrentFileData: () => null,
  rerender: () => {{
    rerenderCount += 1;
  }},
  persistSpatialUnit: async (unit) => {{
    persistedUnits.push(unit);
    return unit;
  }},
}});

assertSynced('px');
await toggles[2].buttons[1].handlers.click();
assert.strictEqual(currentUnit, 'um');
assertSynced('um');
assert.deepStrictEqual(persistedUnits, ['um']);
assert.strictEqual(rerenderCount, 2);

await toggles[0].buttons[0].handlers.click();
assert.strictEqual(currentUnit, 'px');
assertSynced('px');
assert.deepStrictEqual(persistedUnits, ['um', 'px']);
assert.strictEqual(rerenderCount, 4);
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
        result = subprocess.run(
            [node, "-e", script],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_row_filter_ui_state_helpers_use_base_rows(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not available for static JavaScript helper checks.")

        js_path = CORE_STATIC_ROOT / "js" / "shared" / "results-viewer.js"
        script = f"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync({json.dumps(str(js_path))}, 'utf8');
const context = {{ window: {{}} }};
vm.runInNewContext(source, context);
const helpers = context.window.CytoCVResultsViewerShared.createStatisticsHelpers({{
  tableFieldOrder: ['cell_id'],
  statFieldGroups: {{}},
  spatialFieldKinds: {{}},
  spatialHeaderBaseLabels: {{}},
  defaultSpatialStatsUnit: 'px',
  getCurrentSpatialStatsUnit: () => 'px',
  setCurrentSpatialStatsUnit: () => {{}},
}});
const ownArray = (values) => Array.from(values);

const mixed = {{
  '1': {{
    cell_type: 'single_cell',
    signal_quantification_mode: 'puncta_distance',
    puncta_line_mode: 'red_puncta',
    puncta_source_contour_count: 1,
    puncta_source_contour_count_channel: 'red',
  }},
  '2': {{
    cell_type: 'cell_pair',
    signal_quantification_mode: 'puncta_distance',
    puncta_line_mode: 'red_puncta',
    puncta_source_contour_count: 2,
    puncta_source_contour_count_channel: 'red',
  }},
}};
assert.deepStrictEqual(ownArray(helpers.getAvailableCellTypes(mixed)), ['single_cell', 'cell_pair']);
let state = helpers.getCellTypeFilterUiState(mixed, 'single_cell');
assert.strictEqual(state.enabled, true);
assert.strictEqual(state.effectiveFilter, 'single_cell');
assert.strictEqual(state.displayLabel, 'Only single cells');

state = helpers.getCellTypeFilterUiState(mixed, 'all');
assert.strictEqual(state.enabled, true);
assert.strictEqual(state.effectiveFilter, 'all');
assert.strictEqual(state.displayLabel, 'Both cells');

state = helpers.getCellTypeFilterUiState({{ '1': {{ cell_type: 'cell_pair' }} }}, 'single_cell');
assert.strictEqual(state.enabled, false);
assert.strictEqual(state.effectiveFilter, 'all');
assert.strictEqual(state.displayLabel, 'Only cell pairs');
assert.strictEqual(state.resetRequestedFilter, true);

state = helpers.getCellTypeFilterUiState({{ '1': {{ cell_type: 'single_cell' }} }}, 'cell_pair');
assert.strictEqual(state.enabled, false);
assert.strictEqual(state.effectiveFilter, 'all');
assert.strictEqual(state.displayLabel, 'Only single cells');
assert.strictEqual(state.resetRequestedFilter, true);

state = helpers.getCellTypeFilterUiState({{ '1': {{ cell_type: null }}, '2': {{}} }}, 'cell_pair');
assert.deepStrictEqual(ownArray(state.availableCellTypes), ['unknown']);
assert.strictEqual(state.enabled, false);
assert.strictEqual(state.effectiveFilter, 'all');
assert.strictEqual(state.displayLabel, 'Cell types unknown');

state = helpers.getCellTypeFilterUiState({{}}, 'single_cell');
assert.strictEqual(state.enabled, false);
assert.strictEqual(state.effectiveFilter, 'all');
assert.strictEqual(state.displayLabel, 'No cells');

let badgeState = helpers.getCellCardFilterBadgeState({{ '1': {{ cell_type: 'single_cell' }} }}, {{
  cellTypeFilter: 'all',
  punctaSourceContourCountFilter: 'all',
}});
assert.strictEqual(badgeState.hidden, false);
assert.strictEqual(badgeState.prefix, 'Retained cells');
assert.strictEqual(badgeState.value, 'Only single cells');

badgeState = helpers.getCellCardFilterBadgeState({{ '1': {{ cell_type: 'cell_pair' }} }}, {{
  cellTypeFilter: 'all',
  punctaSourceContourCountFilter: 'all',
}});
assert.strictEqual(badgeState.prefix, 'Retained cells');
assert.strictEqual(badgeState.value, 'Only cell pairs');

badgeState = helpers.getCellCardFilterBadgeState(mixed, {{
  cellTypeFilter: 'all',
  punctaSourceContourCountFilter: 'all',
}});
assert.strictEqual(badgeState.prefix, 'Retained cells');
assert.strictEqual(badgeState.value, 'Both cells');

badgeState = helpers.getCellCardFilterBadgeState(mixed, {{
  cellTypeFilter: 'single_cell',
  punctaSourceContourCountFilter: 'all',
}});
assert.strictEqual(badgeState.prefix, 'Filtered view');
assert.strictEqual(badgeState.value, 'Only single cells');

badgeState = helpers.getCellCardFilterBadgeState(mixed, {{
  cellTypeFilter: 'single_cell',
  punctaSourceContourCountFilter: 'exactly_1',
}});
assert.strictEqual(badgeState.prefix, 'Filtered view');
assert.strictEqual(badgeState.value, 'Only single cells / Exactly 1 red source contour');

badgeState = helpers.getCellCardFilterBadgeState({{}}, {{
  cellTypeFilter: 'single_cell',
  punctaSourceContourCountFilter: 'all',
}});
assert.strictEqual(badgeState.hidden, true);

const sourceState = helpers.getPunctaSourceContourFilterUiState(mixed, 'exactly_2');
assert.strictEqual(sourceState.enabled, true);
assert.strictEqual(sourceState.effectiveFilter, 'exactly_2');
assert.strictEqual(sourceState.controlLabel, 'Red Source Contour Count');
assert.strictEqual(helpers.getPunctaSourceContourCountFilterLabel('exactly_1'), '1 contour');
assert.strictEqual(helpers.getPunctaSourceContourCountFilterLabel('exactly_2'), '2 contours');
assert.deepStrictEqual(
  ownArray(helpers.getFilteredStatisticsEntries(mixed, {{
    cellTypeFilter: 'single_cell',
    punctaSourceContourCountFilter: 'exactly_2',
  }})),
  []
);
assert.strictEqual(
  helpers.getPunctaSourceContourFilterUiState(mixed, 'exactly_2').enabled,
  true
);

assert.strictEqual(
  helpers.getPunctaSourceContourFilterUiState({{ '1': {{ signal_quantification_mode: 'nuclear_cell_pair' }} }}, 'exactly_1').effectiveFilter,
  'all'
);
assert.strictEqual(
  helpers.getPunctaSourceContourFilterUiState({{ '1': {{ signal_quantification_mode: 'puncta_distance', puncta_line_mode: 'red_puncta' }} }}, 'exactly_1').enabled,
  false
);
assert.strictEqual(
  helpers.getRowFilterEmptyMessage({{}}, 0),
  'No retained cells are available for this result.'
);
assert.strictEqual(
  helpers.getRowFilterEmptyMessage(mixed, 0, {{
    cellTypeState: helpers.getCellTypeFilterUiState(mixed, 'single_cell'),
    punctaSourceContourState: helpers.getPunctaSourceContourFilterUiState(mixed, 'all'),
  }}),
  'No cells match the current Cell Type Filter. Switch to Both cells to view every retained cell.'
);
assert.strictEqual(
  helpers.getRowFilterEmptyMessage(mixed, 0, {{
    cellTypeState: helpers.getCellTypeFilterUiState(mixed, 'all'),
    punctaSourceContourState: helpers.getPunctaSourceContourFilterUiState(mixed, 'exactly_2'),
  }}),
  'No cells match the current source contour filter. Show all source contours to view every retained cell.'
);
assert.strictEqual(
  helpers.getRowFilterEmptyMessage(mixed, 0, {{
    cellTypeState: helpers.getCellTypeFilterUiState(mixed, 'single_cell'),
    punctaSourceContourState: helpers.getPunctaSourceContourFilterUiState(mixed, 'exactly_2'),
  }}),
  'No cells match the current row filters. Switch to Both cells and all source contours to view every retained cell.'
);
"""
        result = subprocess.run(
            [node, "-e", script],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_puncta_source_contour_filter_helpers_are_source_aware(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not available for static JavaScript helper checks.")

        js_path = CORE_STATIC_ROOT / "js" / "shared" / "results-viewer.js"
        script = f"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync({json.dumps(str(js_path))}, 'utf8');
const context = {{ window: {{}} }};
vm.runInNewContext(source, context);
const helpers = context.window.CytoCVResultsViewerShared.createStatisticsHelpers({{
  tableFieldOrder: ['cell_id'],
  statFieldGroups: {{}},
  spatialFieldKinds: {{}},
  spatialHeaderBaseLabels: {{}},
  defaultSpatialStatsUnit: 'px',
  getCurrentSpatialStatsUnit: () => 'px',
  setCurrentSpatialStatsUnit: () => {{}},
}});
const ownArray = (values) => Array.from(values);

const redFile = {{
  Statistics: {{
    '1': {{
      signal_quantification_mode: 'puncta_distance',
      puncta_line_mode: 'red_puncta',
      puncta_source_contour_count: 1,
      puncta_source_contour_count_channel: 'red',
    }},
    '2': {{
      signal_quantification_mode: 'puncta_distance',
      puncta_line_mode: 'red_puncta',
      puncta_source_contour_count: 2,
      puncta_source_contour_count_channel: 'red',
    }},
    '3': {{
      signal_quantification_mode: 'puncta_distance',
      puncta_line_mode: 'red_puncta',
      puncta_source_contour_count: 3,
      puncta_source_contour_count_channel: 'red',
    }},
  }},
}};
assert.strictEqual(helpers.getPunctaSourceContourContext(redFile.Statistics).controlLabel, 'Red Source Contour Count');
assert.deepStrictEqual(ownArray(helpers.getPunctaSourceContourFilteredCellIds(redFile, 'exactly_1')), [1]);
assert.deepStrictEqual(ownArray(helpers.getPunctaSourceContourFilteredCellIds(redFile, 'exactly_2')), [2]);
assert.deepStrictEqual(ownArray(helpers.getPunctaSourceContourFilteredCellIds(redFile, 'all')), [1, 2, 3]);

const greenFile = {{
  Statistics: {{
    '1': {{
      signal_quantification_mode: 'puncta_distance',
      puncta_line_mode: 'green_puncta',
      green_contour_1_size: 4,
      green_contour_2_size: 0,
      red_contour_1_size: 9,
    }},
    '2': {{
      signal_quantification_mode: 'puncta_distance',
      puncta_line_mode: 'green_puncta',
      green_contour_1_size: 4,
      green_contour_2_size: '2.5',
      red_contour_1_size: 9,
    }},
  }},
}};
assert.strictEqual(helpers.getPunctaSourceContourContext(greenFile.Statistics).controlLabel, 'Green Source Contour Count');
assert.strictEqual(helpers.derivePunctaSourceContourCount(greenFile.Statistics['1']), 1);
assert.strictEqual(helpers.derivePunctaSourceContourCount(greenFile.Statistics['2']), 2);
assert.deepStrictEqual(ownArray(helpers.getPunctaSourceContourFilteredCellIds(greenFile, 'exactly_2')), [2]);

const nuclearFile = {{
  Statistics: {{
    '1': {{ signal_quantification_mode: 'nuclear_cell_pair' }},
    '2': {{ signal_quantification_mode: 'nuclear_cell_pair' }},
  }},
}};
assert.strictEqual(helpers.getPunctaSourceContourContext(nuclearFile.Statistics).applicable, false);
assert.deepStrictEqual(ownArray(helpers.getPunctaSourceContourFilteredCellIds(nuclearFile, 'exactly_2')), [1, 2]);

assert.strictEqual(
  helpers.findNearestMatchingCellByOriginalOrder(10, [1, 5, 10, 12, 14], [5, 12]),
  12
);
assert.strictEqual(
  helpers.findNearestMatchingCellByOriginalOrder(14, [1, 5, 10, 12, 14], [5, 12]),
  12
);
assert.strictEqual(helpers.getAdjacentFilteredCellId(12, [5, 12], 'next'), 5);
assert.strictEqual(helpers.getAdjacentFilteredCellId(5, [5, 12], 'previous'), 12);
assert.strictEqual(helpers.getAdjacentFilteredCellId(99, [5, 12], 'next'), 5);
assert.strictEqual(helpers.getAdjacentFilteredCellId(99, [5, 12], 'previous'), 12);
"""
        result = subprocess.run(
            [node, "-e", script],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_export_selection_refreshes_stat_labels_without_rebuilding_state(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not available for static JavaScript helper checks.")

        js_path = CORE_STATIC_ROOT / "js" / "export_selection_modal.js"
        script = f"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync({json.dumps(str(js_path))}, 'utf8');
const context = {{ window: {{}} }};
vm.runInNewContext(source, context);
const hooks = context.window.CytoCVExportSelection.__testHooks;

const itemById = new Map([
  ['puncta_distance', {{
    id: 'puncta_distance',
    label: 'Distance Between Red Puncta (px)',
  }}],
  ['red_in_red_total_intensity_1', {{
    id: 'red_in_red_total_intensity_1',
    label: 'Red In Red Total Intensity 1',
  }}],
]);
const labelElements = [
  {{
    dataset: {{ exportStatLabelFor: 'puncta_distance' }},
    textContent: 'Distance Between Red Puncta (px)',
  }},
  {{
    dataset: {{ exportStatLabelFor: 'red_in_red_total_intensity_1' }},
    textContent: 'Red In Red Total Intensity 1',
  }},
];
const selectedCheckbox = {{ checked: true }};
const formatState = {{ activeFormat: 'xlsx' }};
const intensityFilter = {{ checked: true }};
const statList = {{
  querySelectorAll(selector) {{
    assert.strictEqual(selector, '[data-export-stat-label-for]');
    return labelElements;
  }},
}};
const headerLabels = new Map([
  ['puncta_distance', 'Distance Between Red Puncta (µm)'],
]);

const updated = hooks.refreshStatLabelElements(
  statList,
  itemById,
  headerLabels,
  (item, context) => item.id === 'puncta_distance' ? context.currentTableLabel : '',
  {{ activeMode: 'single' }}
);

assert.strictEqual(updated, 2);
assert.strictEqual(labelElements[0].textContent, 'Distance Between Red Puncta (µm)');
assert.strictEqual(labelElements[1].textContent, 'Red In Red Total Intensity 1');
assert.strictEqual(selectedCheckbox.checked, true);
assert.strictEqual(formatState.activeFormat, 'xlsx');
assert.strictEqual(intensityFilter.checked, true);
assert.strictEqual(
  hooks.resolveStatLabel(
    {{ id: 'blue_contour_size', label: 'Blue Contour Size (px²)' }},
    new Map(),
    (item) => item.label.replace('(px²)', '(µm²)'),
    {{}}
  ),
  'Blue Contour Size (µm²)'
);
"""
        result = subprocess.run(
            [node, "-e", script],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_dashboard_quota_fill_width_is_applied_from_data_attribute(self):
        source = static_text("js/pages/dashboard-viewer.js")
        self.assertIn(".quota-fill[data-quota-fill-width]", source)
        self.assertIn("dataset.quotaFillWidth", source)
        self.assertIn("--quota-fill-width", source)
        self.assertIn("`${quotaFillWidth}%`", source)


class FrontendJavaScriptRenderedOrderTests(TestCase):
    """Protect template script order for shared globals and page consumers."""

    def test_dashboard_and_display_load_shared_globals_before_consumers(self):
        # Page controllers call shared namespaces during module load, so the
        # rendered include order is part of the frontend runtime contract.
        user = login_user(self, "frontend-js-order@example.com")
        uuid_value = create_display_file(uploaded_owner=user, filename="js_order")

        for route_name, page_script, page_cell_script in (
            ("dashboard", "js/pages/dashboard-viewer.js", "js/pages/dashboard-cell-actions.js"),
            ("display", "js/pages/display-viewer.js", "js/pages/display-cell-actions.js"),
        ):
            with self.subTest(route=route_name):
                url = reverse(route_name, args=[uuid_value]) if route_name == "display" else reverse(route_name)
                content = response_text(self.client.get(url))
                assert_in_order(self, content, "js/shared/results-viewer.js", page_script)
                assert_in_order(self, content, "js/shared/results-cell-actions.js", page_cell_script)
                assert_in_order(self, content, "js/export_selection_modal.js", page_script)
                assert_in_order(self, content, "js/viewer_overlay_prefetch.js", page_script)

    def test_base_global_scripts_are_included_on_dynamic_pages(self):
        login_user(self, "frontend-base-js@example.com")
        content = response_text(self.client.get(reverse("experiment")))
        self.assertIn("js/shared/async-progress.js", content)
        self.assertIn("js/shared/base-interactions.js", content)
        self.assertIn("js/pages/experiment.js", content)
