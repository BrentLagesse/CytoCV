"""Central statistics plugin metadata and channel requirements.

This module is the single source of truth for:
1) Which statistics plugins are available to users.
2) Which wavelengths each plugin requires.
3) Which wavelengths are always required for segmentation/CNN.

Both frontend (upload settings UI) and backend (DV validation) consume this data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


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
    required_channels: frozenset[str] = field(default_factory=frozenset)
    required_plugins: frozenset[str] = field(default_factory=frozenset)


# Keep order stable for UI rendering.
PLUGIN_ORDER: tuple[str, ...] = (
    "MCherryLine",
    "GFPDot",
    "GreenRedIntensity",
    "NucleusIntensity",
    "DAPI_NucleusIntensity",
    "RedBlueIntensity",
)


PLUGIN_DEFINITIONS: dict[str, StatsPluginDefinition] = {
    "MCherryLine": StatsPluginDefinition(
        plugin_id="MCherryLine",
        label="MCherry Line Intensity",
        description="Draws a line between red dot centers and measures GFP intensity along that line.",
        required_channels=frozenset({"mCherry", "GFP"}),
    ),
    "GFPDot": StatsPluginDefinition(
        plugin_id="GFPDot",
        label="GFP Dot Classification",
        description="Classifies GFP-dot category/biorientation relative to paired red dots.",
        required_channels=frozenset({"mCherry", "GFP"}),
    ),
    "GreenRedIntensity": StatsPluginDefinition(
        plugin_id="GreenRedIntensity",
        label="Green/Red Intensity Ratio",
        description="Computes GFP-to-mCherry intensity ratios around detected red dots.",
        required_channels=frozenset({"mCherry", "GFP"}),
    ),
    "NucleusIntensity": StatsPluginDefinition(
        plugin_id="NucleusIntensity",
        label="Nucleus GFP Intensity",
        description="Measures GFP intensity in nuclear vs cellular regions using DAPI contour reference.",
        required_channels=frozenset({"DAPI", "GFP"}),
    ),
    "DAPI_NucleusIntensity": StatsPluginDefinition(
        plugin_id="DAPI_NucleusIntensity",
        label="Nucleus DAPI Intensity",
        description="Measures DAPI intensity in nucleus/cytoplasm using DAPI contour reference.",
        required_channels=frozenset({"DAPI"}),
    ),
    "RedBlueIntensity": StatsPluginDefinition(
        plugin_id="RedBlueIntensity",
        label="Red-in-Blue Intensity",
        description="Measures DAPI intensity around red-dot contour locations.",
        required_channels=frozenset({"mCherry", "DAPI"}),
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
    return [plugin_id for plugin_id in PLUGIN_ORDER if plugin_id in selected_set]


def expand_selected_plugins(selected_plugins: Iterable[str]) -> list[str]:
    """Include dependency plugins and return stable ordered IDs."""

    queue = list(normalize_selected_plugins(selected_plugins))
    resolved: set[str] = set(queue)
    while queue:
        plugin_id = queue.pop(0)
        for dep in PLUGIN_DEFINITIONS[plugin_id].required_plugins:
            if dep in PLUGIN_DEFINITIONS and dep not in resolved:
                resolved.add(dep)
                queue.append(dep)
    return [plugin_id for plugin_id in PLUGIN_ORDER if plugin_id in resolved]


def get_required_channels_for_plugins(selected_plugins: Iterable[str]) -> tuple[list[str], list[str]]:
    """Return sorted required channels and normalized+expanded plugin IDs."""

    expanded_plugins = expand_selected_plugins(selected_plugins)
    required_channels = set(ALWAYS_REQUIRED_CHANNELS)
    for plugin_id in expanded_plugins:
        required_channels.update(PLUGIN_DEFINITIONS[plugin_id].required_channels)
    sorted_channels = sorted(required_channels, key=_channel_sort_key)
    return sorted_channels, expanded_plugins


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
            }
        )

    return {
        "plugins": plugins,
        "channel_order": list(CHANNEL_ORDER),
        "always_required_channels": sorted(ALWAYS_REQUIRED_CHANNELS, key=_channel_sort_key),
        "channel_info": CHANNEL_INFO,
    }
