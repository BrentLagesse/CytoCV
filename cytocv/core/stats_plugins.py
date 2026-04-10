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

from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_ORDER,
    CHANNEL_ROLE_RED,
    channel_display_label,
    channel_sort_key,
)

CHANNEL_ORDER: tuple[str, ...] = CHANNEL_ROLE_ORDER
ALWAYS_REQUIRED_CHANNELS: frozenset[str] = frozenset({CHANNEL_ROLE_DIC})
SEGMENTATION_REQUIREMENT_LABEL = "Segmentation/CNN"

CHANNEL_INFO: dict[str, str] = {
    CHANNEL_ROLE_DIC: "Differential Interference Contrast channel used for segmentation/CNN preprocessing.",
    CHANNEL_ROLE_BLUE: "Blue fluorescence channel used for nucleus-related contours and legacy blue-channel metrics.",
    CHANNEL_ROLE_RED: "Red fluorescence channel used for dot contour detection and red intensity measurements.",
    CHANNEL_ROLE_GREEN: "Green fluorescence channel used for green intensity, contour, and CEN dot measurements.",
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
    "PunctaDistance",
    "CENDot",
    "GreenRedIntensity",
    "NuclearCellPairIntensity",
    "NucleusIntensity",
    "BlueNucleusIntensity",
    "RedBlueIntensity",
)

PLUGIN_ID_ALIASES: dict[str, str] = {
    "MCherryLine": "PunctaDistance",
    "RedLineIntensity": "PunctaDistance",
    "GFPDot": "CENDot",
    "DAPI_NucleusIntensity": "BlueNucleusIntensity",
    "NuclearCellularIntensity": "NuclearCellPairIntensity",
}


PLUGIN_DEFINITIONS: dict[str, StatsPluginDefinition] = {
    "PunctaDistance": StatsPluginDefinition(
        plugin_id="PunctaDistance",
        label="Puncta Distance",
        description=(
            "Draws a line between the selected puncta pair and measures intensity from "
            "the opposite channel along that line."
        ),
        module_name="core.cell_analysis.puncta_distance",
        class_name="PunctaDistance",
        required_channels=frozenset({CHANNEL_ROLE_RED, CHANNEL_ROLE_GREEN}),
    ),
    "CENDot": StatsPluginDefinition(
        plugin_id="CENDot",
        label="CEN dot Classification",
        description="Classifies CEN-dot category and biorientation relative to paired red puncta.",
        module_name="core.cell_analysis.cen_dot",
        class_name="CENDot",
        required_channels=frozenset({CHANNEL_ROLE_RED, CHANNEL_ROLE_GREEN}),
    ),
    "GreenRedIntensity": StatsPluginDefinition(
        plugin_id="GreenRedIntensity",
        label="Red/Green Contour Intensities",
        description=(
            "Computes raw masked-sum contour intensities across red and green channels, "
            "plus a secondary green/red ratio for red contours."
        ),
        module_name="core.cell_analysis.green_red_intensity",
        class_name="GreenRedIntensity",
        required_channels=frozenset({CHANNEL_ROLE_RED, CHANNEL_ROLE_GREEN}),
    ),
    "NuclearCellPairIntensity": StatsPluginDefinition(
        plugin_id="NuclearCellPairIntensity",
        label="Nuclear, Cell-Pair Intensity",
        description=(
            "Uses selected channel as nucleus contour source and measures intensity in the opposite "
            "channel within nucleus and cell-pair regions."
        ),
        module_name="core.cell_analysis.nuclear_cell_pair_intensity",
        class_name="NuclearCellPairIntensity",
        required_channels=frozenset({CHANNEL_ROLE_RED, CHANNEL_ROLE_GREEN}),
        exclusive_group="nuclear_cell_pair",
    ),
    "NucleusIntensity": StatsPluginDefinition(
        plugin_id="NucleusIntensity",
        label="Nucleus Green Intensity",
        description="Measures green intensity in nuclear vs cellular regions using Blue contour reference.",
        module_name="core.cell_analysis.nucleus_intensity",
        class_name="NucleusIntensity",
        required_channels=frozenset({CHANNEL_ROLE_BLUE, CHANNEL_ROLE_GREEN}),
        is_legacy=True,
        exclusive_group="nuclear_cell_pair",
    ),
    "BlueNucleusIntensity": StatsPluginDefinition(
        plugin_id="BlueNucleusIntensity",
        label="Nucleus Blue Intensity",
        description="Measures blue intensity in nucleus/cytoplasm using Blue contour reference.",
        module_name="core.cell_analysis.blue_nucleus_intensity",
        class_name="BlueNucleusIntensity",
        required_channels=frozenset({CHANNEL_ROLE_BLUE}),
        is_legacy=True,
        exclusive_group="nuclear_cell_pair",
    ),
    "RedBlueIntensity": StatsPluginDefinition(
        plugin_id="RedBlueIntensity",
        label="Red-in-Blue Intensity",
        description="Measures blue intensity around red-dot contour locations.",
        module_name="core.cell_analysis.red_blue_intensity",
        class_name="RedBlueIntensity",
        required_channels=frozenset({CHANNEL_ROLE_RED, CHANNEL_ROLE_BLUE}),
        is_legacy=True,
        exclusive_group="nuclear_cell_pair",
    ),
}


def _channel_sort_key(channel: str) -> int:
    return channel_sort_key(channel)


def normalize_selected_plugins(selected_plugins: Iterable[str]) -> list[str]:
    """Return plugin IDs filtered to known plugins in stable order."""

    selected_set = {
        PLUGIN_ID_ALIASES.get(name, name)
        for name in selected_plugins
        if PLUGIN_ID_ALIASES.get(name, name) in PLUGIN_DEFINITIONS
    }
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
                "required_channel_labels": [
                    channel_display_label(channel)
                    for channel in sorted(definition.required_channels, key=_channel_sort_key)
                ],
                "required_plugins": sorted(definition.required_plugins),
                "is_legacy": definition.is_legacy,
                "exclusive_group": definition.exclusive_group,
            }
        )

    return {
        "plugins": plugins,
        "channel_order": list(CHANNEL_ORDER),
        "channel_display_order": [channel_display_label(channel) for channel in CHANNEL_ORDER],
        "always_required_channels": sorted(ALWAYS_REQUIRED_CHANNELS, key=_channel_sort_key),
        "channel_info": CHANNEL_INFO,
        "channel_labels": {channel: channel_display_label(channel) for channel in CHANNEL_ORDER},
    }


def load_available_plugin_ids() -> list[str]:
    """Return stable plugin IDs independent of module filenames."""

    return list(PLUGIN_ORDER)


def get_plugin_class(plugin_id: str) -> type[Any]:
    """Resolve a plugin's class from explicit module metadata."""

    plugin_id = PLUGIN_ID_ALIASES.get(plugin_id, plugin_id)
    definition = PLUGIN_DEFINITIONS[plugin_id]
    module = import_module(definition.module_name)
    return getattr(module, definition.class_name)


def instantiate_selected_plugins(selected_plugins: Iterable[str]) -> list[Any]:
    """Instantiate selected plugins using explicit module/class mappings."""

    return _instantiate_plugin_ids(expand_selected_plugins(selected_plugins))
