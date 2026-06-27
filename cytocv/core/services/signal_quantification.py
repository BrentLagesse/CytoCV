"""Shared Signal Quantification mode resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from core.channel_roles import CHANNEL_ROLE_GREEN, CHANNEL_ROLE_RED, normalize_channel_role
from core.services.puncta_line_mode import (
    DEFAULT_PUNCTA_LINE_MODE,
    is_single_channel_puncta_line_mode,
    normalize_puncta_line_mode,
)


SIGNAL_MODE_PUNCTA_DISTANCE = "puncta_distance"
SIGNAL_MODE_NUCLEAR_CELL_PAIR = "nuclear_cell_pair"
SIGNAL_QUANTIFICATION_MODES = frozenset(
    {SIGNAL_MODE_PUNCTA_DISTANCE, SIGNAL_MODE_NUCLEAR_CELL_PAIR}
)

PUNCTA_DISTANCE_PLUGIN = "PunctaDistance"
GREEN_RED_INTENSITY_PLUGIN = "GreenRedIntensity"
NUCLEAR_CELL_PAIR_PLUGIN = "NuclearCellPairIntensity"
CEN_DOT_PLUGIN = "CENDot"
BIORIENTATION_PLUGIN = "Biorientation"
RED_GREEN_PAIRED_PLUGIN_IDS = frozenset(
    {
        GREEN_RED_INTENSITY_PLUGIN,
        CEN_DOT_PLUGIN,
        BIORIENTATION_PLUGIN,
        NUCLEAR_CELL_PAIR_PLUGIN,
    }
)
LEGACY_BLUE_INTENSITY_PLUGIN_IDS = frozenset(
    {"NucleusIntensity", "BlueNucleusIntensity", "RedBlueIntensity"}
)

SIGNAL_QUANTIFICATION_PLUGIN_IDS = frozenset(
    {
        PUNCTA_DISTANCE_PLUGIN,
        GREEN_RED_INTENSITY_PLUGIN,
        NUCLEAR_CELL_PAIR_PLUGIN,
    }
)

DEFAULT_SIGNAL_SELECTED_PLUGINS = (
    PUNCTA_DISTANCE_PLUGIN,
    CEN_DOT_PLUGIN,
    BIORIENTATION_PLUGIN,
    GREEN_RED_INTENSITY_PLUGIN,
)
PLUGIN_ORDER = (
    PUNCTA_DISTANCE_PLUGIN,
    CEN_DOT_PLUGIN,
    BIORIENTATION_PLUGIN,
    GREEN_RED_INTENSITY_PLUGIN,
    NUCLEAR_CELL_PAIR_PLUGIN,
    "NucleusIntensity",
    "BlueNucleusIntensity",
    "RedBlueIntensity",
)
PLUGIN_ID_ALIASES = {
    "MCherryLine": PUNCTA_DISTANCE_PLUGIN,
    "RedLineIntensity": PUNCTA_DISTANCE_PLUGIN,
    "GFPIntensity": CEN_DOT_PLUGIN,
    "CenDotCollinearity": BIORIENTATION_PLUGIN,
    "NuclearCellularIntensity": NUCLEAR_CELL_PAIR_PLUGIN,
}

RATIO_MODE_RED_CONTOUR = "red_contour"
RATIO_MODE_GREEN_CONTOUR = "green_contour"


@dataclass(frozen=True, slots=True)
class SignalQuantificationSelection:
    """Resolved plugin selection and visibility state for one workflow payload."""

    enabled: bool
    mode: str
    puncta_contour_intensity_enabled: bool
    alternate_nucleus_detection_enabled: bool
    alternate_nucleus_detection_channel: str | None
    configured_plugins: tuple[str, ...]
    selected_plugins: tuple[str, ...]
    independent_plugins: tuple[str, ...]
    paused_plugins: tuple[str, ...]
    stat_visibility: dict[str, bool]
    measurement_contour_ratio_mode: str


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, float) and value in {0.0, 1.0}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _has_key(payload: dict[str, Any] | None, *keys: str) -> bool:
    if not isinstance(payload, dict):
        return False
    return any(key in payload for key in keys)


def normalize_signal_quantification_mode(
    value: Any,
    default: str = SIGNAL_MODE_PUNCTA_DISTANCE,
) -> str:
    """Normalize legacy plugin and UI mode aliases into the two active modes."""

    mode = str(value or "").strip()
    aliases = {
        "puncta": SIGNAL_MODE_PUNCTA_DISTANCE,
        "puncta_distance": SIGNAL_MODE_PUNCTA_DISTANCE,
        PUNCTA_DISTANCE_PLUGIN: SIGNAL_MODE_PUNCTA_DISTANCE,
        "nuclear": SIGNAL_MODE_NUCLEAR_CELL_PAIR,
        "nuclear_cell_pair": SIGNAL_MODE_NUCLEAR_CELL_PAIR,
        NUCLEAR_CELL_PAIR_PLUGIN: SIGNAL_MODE_NUCLEAR_CELL_PAIR,
    }
    return aliases.get(mode, default)


def expand_selected_plugins(selected_plugins: Iterable[Any]) -> tuple[str, ...]:
    """Return known plugin ids in canonical execution/display order."""

    seen: set[str] = set()
    selected: list[str] = []
    known = set(PLUGIN_ORDER)
    for raw_plugin in selected_plugins or []:
        plugin_id = PLUGIN_ID_ALIASES.get(str(raw_plugin).strip(), str(raw_plugin).strip())
        if plugin_id not in known or plugin_id in seen:
            continue
        seen.add(plugin_id)
        selected.append(plugin_id)
    order = {plugin_id: index for index, plugin_id in enumerate(PLUGIN_ORDER)}
    selected.sort(key=lambda plugin_id: order.get(plugin_id, len(order)))
    return tuple(selected)


def infer_signal_quantification_mode(selected_plugins: Iterable[Any]) -> str:
    """Infer the primary Signal Quantification mode from legacy selections."""

    plugins = set(expand_selected_plugins(selected_plugins))
    if PUNCTA_DISTANCE_PLUGIN in plugins:
        return SIGNAL_MODE_PUNCTA_DISTANCE
    if NUCLEAR_CELL_PAIR_PLUGIN in plugins:
        return SIGNAL_MODE_NUCLEAR_CELL_PAIR
    return SIGNAL_MODE_PUNCTA_DISTANCE


def measurement_ratio_mode_for_puncta_line_mode(puncta_line_mode: Any) -> str:
    mode = normalize_puncta_line_mode(
        puncta_line_mode,
        default=DEFAULT_PUNCTA_LINE_MODE,
    )
    if mode in {"green_puncta", "green_puncta_only"}:
        return RATIO_MODE_GREEN_CONTOUR
    return RATIO_MODE_RED_CONTOUR


def alternate_detection_channel_for_nuclear_mode(
    nuclear_cell_pair_mode: Any,
    *,
    enabled: bool,
) -> str | None:
    # Alternate contour selection only applies to the nuclear workflow.
    if not enabled:
        return None
    return CHANNEL_ROLE_RED if str(nuclear_cell_pair_mode) == "red_nucleus" else CHANNEL_ROLE_GREEN


def resolve_effective_alternate_nucleus_detection(
    *,
    signal_quantification_enabled: Any,
    signal_quantification_mode: Any,
    nuclear_cell_pair_mode: Any,
    alternate_nucleus_detection_enabled: Any,
    alternate_nucleus_detection_channel: Any = None,
) -> tuple[bool, str | None]:
    """Return the operational alternate nucleus setting for stats execution."""

    if not _as_bool(signal_quantification_enabled, default=False):
        return False, None
    if normalize_signal_quantification_mode(signal_quantification_mode) != SIGNAL_MODE_NUCLEAR_CELL_PAIR:
        return False, None
    if not _as_bool(alternate_nucleus_detection_enabled, default=False):
        return False, None

    derived_channel = alternate_detection_channel_for_nuclear_mode(
        nuclear_cell_pair_mode,
        enabled=True,
    )
    requested_channel = normalize_channel_role(alternate_nucleus_detection_channel)
    if requested_channel == derived_channel:
        return True, requested_channel
    return bool(derived_channel), derived_channel


def build_stat_visibility(selected_plugins: Iterable[Any]) -> dict[str, bool]:
    plugins = set(expand_selected_plugins(selected_plugins))
    return {
        "puncta_distance": PUNCTA_DISTANCE_PLUGIN in plugins,
        "red_green_intensity": GREEN_RED_INTENSITY_PLUGIN in plugins,
        "nuclear_cell_pair_intensity": NUCLEAR_CELL_PAIR_PLUGIN in plugins,
        "cen_dot": CEN_DOT_PLUGIN in plugins,
        "biorientation": BIORIENTATION_PLUGIN in plugins,
        "legacy_blue_intensity": bool(plugins & LEGACY_BLUE_INTENSITY_PLUGIN_IDS),
    }


def resolve_signal_quantification_selection(
    *,
    payload: dict[str, Any] | None = None,
    selected_plugins: Iterable[Any] | None = None,
    nuclear_cell_pair_mode: Any = "green_nucleus",
    puncta_line_mode: Any = DEFAULT_PUNCTA_LINE_MODE,
    default_enabled: bool | None = None,
    default_mode: str | None = None,
    default_puncta_contour_intensity_enabled: bool | None = None,
    default_alternate_nucleus_detection_enabled: bool | None = None,
) -> SignalQuantificationSelection:
    """Resolve Signal Quantification fields and derived plugin selection."""

    payload = payload if isinstance(payload, dict) else {}
    normalized_puncta_line_mode = normalize_puncta_line_mode(
        puncta_line_mode,
        default=DEFAULT_PUNCTA_LINE_MODE,
    )
    single_channel_puncta_mode = is_single_channel_puncta_line_mode(
        normalized_puncta_line_mode
    )
    legacy_plugins = tuple(expand_selected_plugins(selected_plugins or ()))
    legacy_plugin_set = set(legacy_plugins)
    has_primary_legacy = bool(legacy_plugin_set & SIGNAL_QUANTIFICATION_PLUGIN_IDS)

    inferred_enabled = has_primary_legacy
    if default_enabled is not None:
        inferred_enabled = bool(default_enabled)
    enabled = _as_bool(
        payload.get(
            "signal_quantification_enabled",
            payload.get("signalQuantificationEnabled"),
        ),
        default=inferred_enabled,
    )

    inferred_mode = default_mode or infer_signal_quantification_mode(legacy_plugins)
    mode = normalize_signal_quantification_mode(
        payload.get(
            "signal_quantification_mode",
            payload.get("signalQuantificationMode"),
        ),
        default=inferred_mode,
    )

    if default_puncta_contour_intensity_enabled is None:
        inferred_contour_enabled = GREEN_RED_INTENSITY_PLUGIN in legacy_plugin_set
    else:
        inferred_contour_enabled = bool(default_puncta_contour_intensity_enabled)
    puncta_contour_intensity_enabled = _as_bool(
        payload.get(
            "puncta_contour_intensity_enabled",
            payload.get("punctaContourIntensityEnabled"),
        ),
        default=inferred_contour_enabled,
    )

    legacy_alternate = payload.get(
        "alternate_nucleus_detection_enabled",
        payload.get(
            "alternateNucleusDetectionEnabled",
            payload.get(
                "alternateRedDetection",
                payload.get(
                    "alternate_red_detection",
                    payload.get("alternateMCherryDetection"),
                ),
            ),
        ),
    )
    if default_alternate_nucleus_detection_enabled is None:
        default_alternate_nucleus_detection_enabled = False
    alternate_enabled = _as_bool(
        legacy_alternate,
        default=bool(default_alternate_nucleus_detection_enabled),
    )

    independent_plugins = tuple(
        plugin_id
        for plugin_id in legacy_plugins
        if plugin_id not in SIGNAL_QUANTIFICATION_PLUGIN_IDS
        and not (single_channel_puncta_mode and plugin_id in RED_GREEN_PAIRED_PLUGIN_IDS)
    )

    configured: list[str] = []
    if enabled:
        if mode == SIGNAL_MODE_NUCLEAR_CELL_PAIR:
            configured.append(NUCLEAR_CELL_PAIR_PLUGIN)
        else:
            configured.append(PUNCTA_DISTANCE_PLUGIN)
            if puncta_contour_intensity_enabled and not single_channel_puncta_mode:
                configured.append(GREEN_RED_INTENSITY_PLUGIN)
    configured.extend(independent_plugins)
    configured_plugins_tuple = tuple(expand_selected_plugins(configured))

    effective: list[str] = []
    if enabled:
        if mode == SIGNAL_MODE_NUCLEAR_CELL_PAIR:
            effective.append(NUCLEAR_CELL_PAIR_PLUGIN)
        else:
            effective.append(PUNCTA_DISTANCE_PLUGIN)
            if puncta_contour_intensity_enabled and not single_channel_puncta_mode:
                effective.append(GREEN_RED_INTENSITY_PLUGIN)
            effective.extend(independent_plugins)
    else:
        effective.extend(independent_plugins)
    selected_plugins_tuple = tuple(expand_selected_plugins(effective))
    effective_plugin_set = set(selected_plugins_tuple)
    paused_plugins_tuple = tuple(
        plugin_id
        for plugin_id in configured_plugins_tuple
        if plugin_id not in effective_plugin_set
    )

    return SignalQuantificationSelection(
        enabled=enabled,
        mode=mode,
        puncta_contour_intensity_enabled=puncta_contour_intensity_enabled,
        alternate_nucleus_detection_enabled=alternate_enabled,
        alternate_nucleus_detection_channel=alternate_detection_channel_for_nuclear_mode(
            nuclear_cell_pair_mode,
            enabled=enabled and mode == SIGNAL_MODE_NUCLEAR_CELL_PAIR and alternate_enabled,
        ),
        configured_plugins=configured_plugins_tuple,
        selected_plugins=selected_plugins_tuple,
        independent_plugins=tuple(expand_selected_plugins(independent_plugins)),
        paused_plugins=paused_plugins_tuple,
        stat_visibility=build_stat_visibility(selected_plugins_tuple),
        measurement_contour_ratio_mode=measurement_ratio_mode_for_puncta_line_mode(
            normalized_puncta_line_mode
        ),
    )


def resolve_signal_quantification_from_defaults(
    defaults: dict[str, Any] | None,
) -> SignalQuantificationSelection:
    """Resolve account defaults through the same contract as request payloads."""

    defaults = defaults if isinstance(defaults, dict) else {}
    selected_plugins = defaults.get("selected_plugins", DEFAULT_SIGNAL_SELECTED_PLUGINS)
    return resolve_signal_quantification_selection(
        payload=defaults,
        selected_plugins=selected_plugins,
        nuclear_cell_pair_mode=defaults.get("nuclear_cell_pair_mode", "green_nucleus"),
        puncta_line_mode=defaults.get("puncta_line_mode", DEFAULT_PUNCTA_LINE_MODE),
        default_enabled=(
            _as_bool(defaults.get("signal_quantification_enabled"), default=True)
            if _has_key(defaults, "signal_quantification_enabled")
            else None
        ),
        default_mode=(
            normalize_signal_quantification_mode(defaults.get("signal_quantification_mode"))
            if _has_key(defaults, "signal_quantification_mode")
            else None
        ),
        default_puncta_contour_intensity_enabled=(
            _as_bool(defaults.get("puncta_contour_intensity_enabled"), default=True)
            if _has_key(defaults, "puncta_contour_intensity_enabled")
            else None
        ),
        default_alternate_nucleus_detection_enabled=_as_bool(
            defaults.get(
                "alternate_nucleus_detection_enabled",
                defaults.get("alternate_red_detection"),
            ),
            default=False,
        ),
    )
