"""Central statistics plugin metadata and channel requirements.

This module is the single source of truth for:
1) Which statistics plugins are available to users.
2) Which wavelengths each plugin requires.
3) Which wavelengths are always required for segmentation/CNN.

Both frontend (upload settings UI) and backend (DV validation) consume this data.
"""

from __future__ import annotations

from importlib import import_module
from dataclasses import dataclass, field
from typing import Any, Iterable


CHANNEL_ORDER: tuple[str, ...] = ("DIC", "DAPI", "mCherry", "GFP")
ALWAYS_REQUIRED_CHANNELS: frozenset[str] = frozenset({"DIC"})
SEGMENTATION_REQUIREMENT_LABEL = "Segmentation/CNN"

CHANNEL_INFO: dict[str, str] = {
    "DIC": "Differential Interference Contrast channel used for segmentation/CNN preprocessing.",
    "DAPI": "Blue fluorescence channel used for nucleus-related contours and intensity metrics.",
    "mCherry": "Red fluorescence channel used for spindle pole body/dot contour detection.",
    "GFP": "Green fluorescence channel used for GFP intensity and GFP-dot related measurements.",
}


@dataclass(frozen=True)
class StatsPluginDefinition:
    plugin_id: str
    label: str
    description: str
    module_name: str
    class_name: str
    required_channels: frozenset[str] = field(default_factory=frozenset)
    required_plugins: frozenset[str] = field(default_factory=frozenset)
    is_legacy: bool = False
    exclusive_group: str | None = None


@dataclass(frozen=True)
class StatsExecutionPlan:
    """Run-scoped statistics setup reused across cells in one image."""

    normalized_plugins: tuple[str, ...] = field(default_factory=tuple)
    selected_plugins: tuple[str, ...] = field(default_factory=tuple)
    required_channels: tuple[str, ...] = field(default_factory=tuple)
    required_channel_set: frozenset[str] = field(default_factory=frozenset)
    analyses: tuple[Any, ...] = field(default_factory=tuple)


# Keep order stable for UI rendering.
PLUGIN_ORDER: tuple[str, ...] = (
    "MCherryLine",
    "GFPDot",
    "GreenRedIntensity",
    "NuclearCellularIntensity",
    "NucleusIntensity",
    "DAPI_NucleusIntensity",
    "RedBlueIntensity",
)


PLUGIN_DEFINITIONS: dict[str, StatsPluginDefinition] = {
    "MCherryLine": StatsPluginDefinition(
        plugin_id="MCherryLine",
        label="mCherry Line Intensity",
        description="Draws a line between red dot centers and measures GFP intensity along that line.",
        module_name="core.cell_analysis.mcherry_line",
        class_name="MCherryLine",
        required_channels=frozenset({"mCherry", "GFP"}),
    ),
    "GFPDot": StatsPluginDefinition(
        plugin_id="GFPDot",
        label="GFP Dot Classification",
        description="Classifies GFP-dot category/biorientation relative to paired red dots.",
        module_name="core.cell_analysis.gfp_dot",
        class_name="GFPDot",
        required_channels=frozenset({"mCherry", "GFP"}),
    ),
    "GreenRedIntensity": StatsPluginDefinition(
        plugin_id="GreenRedIntensity",
        label="Green/Red Intensity Ratio",
        description="Computes per-contour intensity combinations across red and green channels.",
        module_name="core.cell_analysis.green_red_intensity",
        class_name="GreenRedIntensity",
        required_channels=frozenset({"mCherry", "GFP"}),
    ),
    "NuclearCellularIntensity": StatsPluginDefinition(
        plugin_id="NuclearCellularIntensity",
        label="Nuclear, Cellular Intensity",
        description=(
            "Uses selected channel as nucleus contour source and measures intensity in the opposite "
            "channel within nucleus and whole-cell regions."
        ),
        module_name="core.cell_analysis.nuclear_cellular_intensity",
        class_name="NuclearCellularIntensity",
        required_channels=frozenset({"mCherry", "GFP"}),
        exclusive_group="nuclear_cellular",
    ),
    "NucleusIntensity": StatsPluginDefinition(
        plugin_id="NucleusIntensity",
        label="Nucleus GFP Intensity",
        description="Measures GFP intensity in nuclear vs cellular regions using DAPI contour reference.",
        module_name="core.cell_analysis.nucleus_intensity",
        class_name="NucleusIntensity",
        required_channels=frozenset({"DAPI", "GFP"}),
        is_legacy=True,
        exclusive_group="nuclear_cellular",
    ),
    "DAPI_NucleusIntensity": StatsPluginDefinition(
        plugin_id="DAPI_NucleusIntensity",
        label="Nucleus DAPI Intensity",
        description="Measures DAPI intensity in nucleus/cytoplasm using DAPI contour reference.",
        module_name="core.cell_analysis.dapi_nucleus_intensity",
        class_name="DAPI_NucleusIntensity",
        required_channels=frozenset({"DAPI"}),
        is_legacy=True,
        exclusive_group="nuclear_cellular",
    ),
    "RedBlueIntensity": StatsPluginDefinition(
        plugin_id="RedBlueIntensity",
        label="Red-in-Blue Intensity",
        description="Measures DAPI intensity around red-dot contour locations.",
        module_name="core.cell_analysis.red_blue_intensity",
        class_name="RedBlueIntensity",
        required_channels=frozenset({"mCherry", "DAPI"}),
        is_legacy=True,
        exclusive_group="nuclear_cellular",
    ),
}


def _channel_sort_key(channel: str) -> int:
    try:
        return CHANNEL_ORDER.index(channel)
    except ValueError:
        return len(CHANNEL_ORDER)


def normalize_selected_plugins(selected_plugins: Iterable[str]) -> list[str]:
    """Return plugin IDs filtered to known plugins in stable order."""

    selected_set = {name for name in selected_plugins if name in PLUGIN_DEFINITIONS}
    normalized: list[str] = []
    seen_exclusive_groups: set[str] = set()
    for plugin_id in PLUGIN_ORDER:
        if plugin_id not in selected_set:
            continue
        definition = PLUGIN_DEFINITIONS[plugin_id]
        if definition.exclusive_group and definition.exclusive_group in seen_exclusive_groups:
            continue
        if definition.exclusive_group:
            seen_exclusive_groups.add(definition.exclusive_group)
        normalized.append(plugin_id)
    return normalized


def _expand_normalized_plugins(normalized_plugins: Iterable[str]) -> list[str]:
    """Include dependency plugins for a pre-normalized plugin selection."""

    queue = list(normalized_plugins)
    resolved: set[str] = set(queue)
    while queue:
        plugin_id = queue.pop(0)
        for dep in PLUGIN_DEFINITIONS[plugin_id].required_plugins:
            if dep in PLUGIN_DEFINITIONS and dep not in resolved:
                resolved.add(dep)
                queue.append(dep)
    return [plugin_id for plugin_id in PLUGIN_ORDER if plugin_id in resolved]


def _get_required_channels_for_expanded_plugins(
    expanded_plugins: Iterable[str],
) -> list[str]:
    required_channels = set(ALWAYS_REQUIRED_CHANNELS)
    for plugin_id in expanded_plugins:
        required_channels.update(PLUGIN_DEFINITIONS[plugin_id].required_channels)
    return sorted(required_channels, key=_channel_sort_key)


def _instantiate_plugin_ids(plugin_ids: Iterable[str]) -> list[Any]:
    return [get_plugin_class(plugin_id)() for plugin_id in plugin_ids]


def expand_selected_plugins(selected_plugins: Iterable[str]) -> list[str]:
    """Include dependency plugins and return stable ordered IDs."""

    return _expand_normalized_plugins(normalize_selected_plugins(selected_plugins))


def get_required_channels_for_plugins(selected_plugins: Iterable[str]) -> tuple[list[str], list[str]]:
    """Return sorted required channels and normalized+expanded plugin IDs."""

    expanded_plugins = expand_selected_plugins(selected_plugins)
    return _get_required_channels_for_expanded_plugins(expanded_plugins), expanded_plugins


def build_requirement_summary(selected_plugins: Iterable[str]) -> dict:
    """Build channel requirement metadata for UI and validation."""

    required_channels, expanded_plugins = get_required_channels_for_plugins(selected_plugins)
    required_channel_set = set(required_channels)

    required_sources: dict[str, list[str]] = {channel: [] for channel in CHANNEL_ORDER}
    for channel in ALWAYS_REQUIRED_CHANNELS:
        if channel in required_sources:
            required_sources[channel].append(SEGMENTATION_REQUIREMENT_LABEL)
    for plugin_id in expanded_plugins:
        definition = PLUGIN_DEFINITIONS[plugin_id]
        for channel in definition.required_channels:
            required_sources.setdefault(channel, [])
            required_sources[channel].append(plugin_id)

    return {
        "selected_plugins": expanded_plugins,
        "required_channels": required_channels,
        "required_channel_set": required_channel_set,
        "required_sources": required_sources,
    }


def build_stats_execution_plan(selected_plugins: Iterable[str]) -> StatsExecutionPlan:
    """Build normalized stats setup once for reuse across all cells in a run."""

    normalized_plugins = normalize_selected_plugins(selected_plugins)
    expanded_plugins = _expand_normalized_plugins(normalized_plugins)
    required_channels = _get_required_channels_for_expanded_plugins(expanded_plugins)
    return StatsExecutionPlan(
        normalized_plugins=tuple(normalized_plugins),
        selected_plugins=tuple(expanded_plugins),
        required_channels=tuple(required_channels),
        required_channel_set=frozenset(required_channels),
        analyses=tuple(_instantiate_plugin_ids(expanded_plugins)),
    )


def build_plugin_ui_payload() -> dict:
    """Return serializable metadata for upload-page statistics settings."""

    plugins = []
    for plugin_id in PLUGIN_ORDER:
        definition = PLUGIN_DEFINITIONS[plugin_id]
        plugins.append(
            {
                "id": definition.plugin_id,
                "label": definition.label,
                "description": definition.description,
                "required_channels": sorted(definition.required_channels, key=_channel_sort_key),
                "required_plugins": sorted(definition.required_plugins),
                "is_legacy": definition.is_legacy,
                "exclusive_group": definition.exclusive_group,
            }
        )

    return {
        "plugins": plugins,
        "channel_order": list(CHANNEL_ORDER),
        "always_required_channels": sorted(ALWAYS_REQUIRED_CHANNELS, key=_channel_sort_key),
        "channel_info": CHANNEL_INFO,
    }


def load_available_plugin_ids() -> list[str]:
    """Return stable plugin IDs independent of module filenames."""

    return list(PLUGIN_ORDER)


def get_plugin_class(plugin_id: str) -> type[Any]:
    """Resolve a plugin's class from explicit module metadata."""

    definition = PLUGIN_DEFINITIONS[plugin_id]
    module = import_module(definition.module_name)
    return getattr(module, definition.class_name)


def instantiate_selected_plugins(selected_plugins: Iterable[str]) -> list[Any]:
    """Instantiate selected plugins using explicit module/class mappings."""

    return _instantiate_plugin_ids(expand_selected_plugins(selected_plugins))
