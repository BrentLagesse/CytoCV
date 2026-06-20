from __future__ import annotations

import shutil
import subprocess
import json

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .frontend_contract_helpers import CORE_STATIC_ROOT, assert_in_order, create_display_file, login_user, response_text, static_text


class FrontendJavaScriptStaticContractTests(SimpleTestCase):
    def test_static_javascript_passes_node_syntax_check_when_node_is_available(self):
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

    def test_export_selection_quick_select_js_uses_metadata_not_labels(self):
        source = static_text("js/export_selection_modal.js")

        self.assertIn("family !== 'contour_intensity'", source)
        self.assertIn("item.combination", source)
        self.assertIn("item.statistic", source)
        self.assertIn("Number(item.slot)", source)
        self.assertNotIn("Red In Red", source)
        self.assertNotIn("Total Intensity", source)

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
  'Not available for selected files'
);
assert.strictEqual(hooks.isContourIntensityAvailable(null, true), true);
assert.strictEqual(hooks.isContourIntensityAvailable({{ red_green_intensity: false }}, true), false);

const collapsedState = hooks.deriveContourIntensityAccordionState(false, true);
assert.strictEqual(collapsedState.expanded, false);
assert.strictEqual(collapsedState.ariaExpanded, 'false');
assert.strictEqual(collapsedState.bodyHidden, true);
assert.strictEqual(collapsedState.toggleText, 'Show');
assert.strictEqual(collapsedState.controlsHidden, true);
assert.strictEqual(collapsedState.unavailableMessageHidden, true);

const unavailableExpandedState = hooks.deriveContourIntensityAccordionState(true, false);
assert.strictEqual(unavailableExpandedState.expanded, true);
assert.strictEqual(unavailableExpandedState.ariaExpanded, 'true');
assert.strictEqual(unavailableExpandedState.bodyHidden, false);
assert.strictEqual(unavailableExpandedState.toggleText, 'Hide');
assert.strictEqual(unavailableExpandedState.controlsHidden, true);
assert.strictEqual(unavailableExpandedState.unavailableMessageHidden, false);

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
        ):
            with self.subTest(helper=helper_name):
                self.assertIn(helper_name, source)

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
    def test_dashboard_and_display_load_shared_globals_before_consumers(self):
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
