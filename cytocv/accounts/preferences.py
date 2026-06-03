"""Helpers for account-level experiment preferences."""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from core.channel_roles import CHANNEL_ROLE_ORDER, channel_role_from_slug, channel_slug
from core.channel_ordering import (
    DEFAULT_FALLBACK_CHANNEL_ORDER,
    normalize_channel_order,
    validate_channel_order,
)
from core.services.biorientation_config import (
    DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX,
)
from core.services.puncta_line_mode import (
    DEFAULT_PUNCTA_LINE_MODE,
    normalize_puncta_line_mode,
)
from core.services.dot_split import (
    DEFAULT_DOT_SPLIT_MODE,
    normalize_dot_split_mode,
)
from core.services.nuclear_cell_pair_contour_mode import (
    DEFAULT_NUCLEAR_CELL_PAIR_CONTOUR_MODE,
    NUCLEAR_CELL_PAIR_CONTOUR_MODES,
    normalize_nuclear_cell_pair_contour_mode,
)
from core.services.signal_quantification import (
    DEFAULT_SIGNAL_SELECTED_PLUGINS,
    SIGNAL_MODE_PUNCTA_DISTANCE,
    SIGNAL_QUANTIFICATION_MODES,
    resolve_signal_quantification_selection,
)
from core.stats_plugins import (
    ALWAYS_REQUIRED_CHANNELS,
    CHANNEL_ORDER,
    PLUGIN_DEFINITIONS,
    PLUGIN_ID_ALIASES,
    expand_selected_plugins,
)

NUCLEAR_CELL_PAIR_MODES = {"green_nucleus", "red_nucleus"}
LENGTH_UNITS = {"px", "um"}
DEFAULT_MICRONS_PER_PIXEL = 0.1
MAIN_IMAGE_CHANNEL_SLUGS = frozenset(
    channel_slug(channel_role) for channel_role in CHANNEL_ROLE_ORDER
)


class PreferenceValidationError(ValueError):
    """Raised when an interactive preference payload is invalid."""


DEFAULT_USER_PREFERENCES: dict[str, Any] = {
    "experiment_defaults": {
        "selected_plugins": list(DEFAULT_SIGNAL_SELECTED_PLUGINS),
        "signal_quantification_enabled": True,
        "signal_quantification_mode": SIGNAL_MODE_PUNCTA_DISTANCE,
        "puncta_contour_intensity_enabled": True,
        "alternate_nucleus_detection_enabled": True,
        "module_enabled": False,
        "enforce_layer_count": False,
        "enforce_wavelengths": False,
        "show_legacy_plugins": False,
        "manual_required_channels": [],
        "puncta_line_width": 1,
        "cen_dot_distance": 37,
        "cen_dot_proximity_radius": 13,
        "biorientation_red_min_distance": 0,
        "biorientation_red_max_distance": 37,
        "biorientation_collinearity_threshold": DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX,
        "green_dot_split_enabled": True,
        "green_dot_split_mode": DEFAULT_DOT_SPLIT_MODE,
        "red_dot_split_enabled": True,
        "red_dot_split_mode": DEFAULT_DOT_SPLIT_MODE,
        "puncta_line_mode": DEFAULT_PUNCTA_LINE_MODE,
        "nuclear_cell_pair_mode": "green_nucleus",
        "nuclear_cell_pair_contour_mode": DEFAULT_NUCLEAR_CELL_PAIR_CONTOUR_MODE,
        "use_legacy_nuclear_cell_pair_pipeline": False,
        "green_contour_filter_enabled": False,
        "alternate_red_detection": False,
        "puncta_line_width_unit": "px",
        "cen_dot_distance_unit": "px",
        "cen_dot_proximity_radius_unit": "px",
        "biorientation_red_min_distance_unit": "px",
        "biorientation_red_max_distance_unit": "px",
        "microns_per_pixel": DEFAULT_MICRONS_PER_PIXEL,
        "use_metadata_scale": True,
        "spatial_stats_unit": "px",
        "use_metadata_channel_order": True,
        "fallback_channel_order": list(DEFAULT_FALLBACK_CHANNEL_ORDER),
    },
    "auto_save_experiments": True,
    "show_saved_file_channels": True,
    "show_saved_file_scales": True,
    "sidebar_starts_open": True,
    "confirm_cell_deletion": True,
    "confirm_multi_cell_deletion": True,
    "sidebar_spatial_stats_unit": "px",
    "main_image_channel": "",
}


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _as_int(value: Any, default: int, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum:
        return default
    return parsed


def _as_float(value: Any, default: float, minimum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum:
        return default
    return parsed


def _normalize_unit(value: Any, default: str) -> str:
    unit = str(value or "").strip().lower()
    if unit not in LENGTH_UNITS:
        return default
    return unit


def normalize_main_image_channel(value: Any, default: str = "") -> str:
    slug = str(value or "").strip().lower()
    if not slug:
        return default
    if not channel_role_from_slug(slug):
        return default
    return slug


def _strict_bool(value: Any, *, field: str) -> bool:
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
    raise PreferenceValidationError(f"{field} must be a boolean.")


def _strict_float(value: Any, *, field: str, minimum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise PreferenceValidationError(f"{field} must be a number.") from None
    if not math.isfinite(parsed) or parsed < minimum:
        raise PreferenceValidationError(f"{field} must be at least {minimum}.")
    return parsed


def _strict_int(value: Any, *, field: str, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise PreferenceValidationError(f"{field} must be an integer.") from None
    if parsed < minimum:
        raise PreferenceValidationError(f"{field} must be at least {minimum}.")
    return parsed


def _strict_unit(value: Any, *, field: str) -> str:
    unit = str(value or "").strip().lower()
    if unit not in LENGTH_UNITS:
        raise PreferenceValidationError(f"{field} must be 'px' or 'um'.")
    return unit


def _strict_mode(
    value: Any,
    *,
    field: str,
    allowed: set[str],
) -> str:
    mode = str(value or "").strip()
    if mode not in allowed:
        raise PreferenceValidationError(f"{field} is invalid.")
    return mode


def _strict_channel_order(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        raise PreferenceValidationError(f"{field} must be a list.")
    normalized = validate_channel_order(value)
    if normalized is None:
        raise PreferenceValidationError(
            f"{field} must contain DIC, Blue, Red, and Green exactly once."
        )
    return normalized


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def normalize_preferences_payload(raw_payload: Any) -> dict[str, Any]:
    """Normalize stored/posted preferences into a safe canonical shape."""

    normalized = deepcopy(DEFAULT_USER_PREFERENCES)
    if not isinstance(raw_payload, dict):
        return normalized

    defaults_payload = raw_payload.get("experiment_defaults")
    if not isinstance(defaults_payload, dict):
        defaults_payload = {}

    selected_plugins = defaults_payload.get(
        "selected_plugins",
        normalized["experiment_defaults"]["selected_plugins"],
    )
    if not isinstance(selected_plugins, list):
        selected_plugins = list(normalized["experiment_defaults"]["selected_plugins"])
    normalized["experiment_defaults"]["selected_plugins"] = expand_selected_plugins(
        selected_plugins
    )

    normalized["experiment_defaults"]["module_enabled"] = _as_bool(
        defaults_payload.get("module_enabled"), default=False
    )
    normalized["experiment_defaults"]["enforce_layer_count"] = _as_bool(
        defaults_payload.get("enforce_layer_count"), default=False
    )
    normalized["experiment_defaults"]["enforce_wavelengths"] = _as_bool(
        defaults_payload.get("enforce_wavelengths"), default=False
    )
    normalized["experiment_defaults"]["show_legacy_plugins"] = _as_bool(
        defaults_payload.get("show_legacy_plugins"), default=False
    )
    normalized["experiment_defaults"]["green_contour_filter_enabled"] = _as_bool(
        defaults_payload.get(
            "green_contour_filter_enabled",
            defaults_payload.get("gfp_filter_enabled"),
        ),
        default=False,
    )
    normalized["experiment_defaults"]["alternate_red_detection"] = _as_bool(
        defaults_payload.get(
            "alternate_red_detection",
            defaults_payload.get("alternate_mcherry_detection"),
        ),
        default=False,
    )
    normalized["experiment_defaults"]["alternate_nucleus_detection_enabled"] = _as_bool(
        defaults_payload.get(
            "alternate_nucleus_detection_enabled",
            defaults_payload.get(
                "alternate_red_detection",
                defaults_payload.get("alternate_mcherry_detection"),
            ),
        ),
        default=True,
    )

    raw_required_channels = defaults_payload.get("manual_required_channels", [])
    if not isinstance(raw_required_channels, list):
        raw_required_channels = []
    normalized["experiment_defaults"]["manual_required_channels"] = [
        channel for channel in raw_required_channels if channel in CHANNEL_ORDER
    ]

    normalized["experiment_defaults"]["puncta_line_width_unit"] = _normalize_unit(
        _first_present(
            defaults_payload.get("puncta_line_width_unit"),
            defaults_payload.get("red_line_width_unit"),
            defaults_payload.get("mcherry_width_unit"),
        ),
        default="px",
    )
    normalized["experiment_defaults"]["cen_dot_distance_unit"] = _normalize_unit(
        defaults_payload.get(
            "cen_dot_distance_unit",
            defaults_payload.get("gfp_distance_unit"),
        ),
        default="px",
    )
    normalized["experiment_defaults"]["microns_per_pixel"] = _as_float(
        defaults_payload.get("microns_per_pixel"),
        default=DEFAULT_MICRONS_PER_PIXEL,
        minimum=0.0001,
    )
    normalized["experiment_defaults"]["use_metadata_scale"] = _as_bool(
        defaults_payload.get("use_metadata_scale"),
        default=True,
    )
    normalized["experiment_defaults"]["spatial_stats_unit"] = _normalize_unit(
        defaults_payload.get("spatial_stats_unit"),
        default="px",
    )
    normalized["experiment_defaults"]["use_metadata_channel_order"] = _as_bool(
        defaults_payload.get("use_metadata_channel_order"),
        default=True,
    )
    normalized["experiment_defaults"]["fallback_channel_order"] = (
        normalize_channel_order(
            defaults_payload.get("fallback_channel_order"),
            default=DEFAULT_FALLBACK_CHANNEL_ORDER,
        )
    )
    width_minimum = (
        1 if normalized["experiment_defaults"]["puncta_line_width_unit"] == "px" else 0
    )
    normalized["experiment_defaults"]["puncta_line_width"] = _as_float(
        _first_present(
            defaults_payload.get("puncta_line_width"),
            defaults_payload.get("red_line_width"),
            defaults_payload.get("mcherry_width"),
        ),
        default=1,
        minimum=width_minimum,
    )
    normalized["experiment_defaults"]["cen_dot_distance"] = _as_float(
        defaults_payload.get(
            "cen_dot_distance",
            defaults_payload.get("gfp_distance"),
        ),
        default=37,
        minimum=0,
    )
    normalized["experiment_defaults"]["cen_dot_proximity_radius_unit"] = (
        _normalize_unit(
            defaults_payload.get("cen_dot_proximity_radius_unit"),
            default="px",
        )
    )
    normalized["experiment_defaults"]["cen_dot_proximity_radius"] = _as_float(
        defaults_payload.get("cen_dot_proximity_radius"),
        default=13,
        minimum=0,
    )
    normalized["experiment_defaults"]["biorientation_red_min_distance_unit"] = (
        _normalize_unit(
            defaults_payload.get("biorientation_red_min_distance_unit"),
            default="px",
        )
    )
    normalized["experiment_defaults"]["biorientation_red_min_distance"] = _as_float(
        defaults_payload.get("biorientation_red_min_distance"),
        default=0,
        minimum=0,
    )
    normalized["experiment_defaults"]["biorientation_red_max_distance_unit"] = (
        _normalize_unit(
            defaults_payload.get("biorientation_red_max_distance_unit"),
            default="px",
        )
    )
    normalized["experiment_defaults"]["biorientation_red_max_distance"] = _as_float(
        defaults_payload.get(
            "biorientation_red_max_distance",
            defaults_payload.get("cen_dot_distance"),
        ),
        default=37,
        minimum=0,
    )
    normalized["experiment_defaults"]["biorientation_collinearity_threshold"] = _as_int(
        defaults_payload.get(
            "biorientation_collinearity_threshold",
            defaults_payload.get(
                "cen_dot_collinearity_threshold",
                defaults_payload.get("gfp_threshold"),
            ),
        ),
        default=DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX,
        minimum=0,
    )
    normalized["experiment_defaults"]["green_dot_split_enabled"] = _as_bool(
        defaults_payload.get(
            "green_dot_split_enabled",
            defaults_payload.get("biorientation_green_split_enabled"),
        ),
        default=True,
    )
    raw_green_dot_split_mode = _first_present(
        defaults_payload.get("green_dot_split_mode"),
        defaults_payload.get("greenDotSplitMode"),
    )
    if raw_green_dot_split_mode is None:
        normalized["experiment_defaults"]["green_dot_split_mode"] = normalized[
            "experiment_defaults"
        ]["green_dot_split_mode"]
    else:
        normalized["experiment_defaults"]["green_dot_split_mode"] = (
            normalize_dot_split_mode(raw_green_dot_split_mode)
        )
    normalized["experiment_defaults"]["red_dot_split_enabled"] = _as_bool(
        defaults_payload.get("red_dot_split_enabled"),
        default=True,
    )
    raw_red_dot_split_mode = _first_present(
        defaults_payload.get("red_dot_split_mode"),
        defaults_payload.get("redDotSplitMode"),
    )
    if raw_red_dot_split_mode is None:
        normalized["experiment_defaults"]["red_dot_split_mode"] = normalized[
            "experiment_defaults"
        ]["red_dot_split_mode"]
    else:
        normalized["experiment_defaults"]["red_dot_split_mode"] = (
            normalize_dot_split_mode(raw_red_dot_split_mode)
        )
    normalized["experiment_defaults"]["puncta_line_mode"] = normalize_puncta_line_mode(
        defaults_payload.get("puncta_line_mode"),
        default=DEFAULT_PUNCTA_LINE_MODE,
    )

    mode = str(
        defaults_payload.get(
            "nuclear_cell_pair_mode",
            defaults_payload.get("nuclear_cellular_mode"),
        )
        or ""
    ).strip()
    if mode not in NUCLEAR_CELL_PAIR_MODES:
        mode = "green_nucleus"
    normalized["experiment_defaults"]["nuclear_cell_pair_mode"] = mode
    normalized["experiment_defaults"]["nuclear_cell_pair_contour_mode"] = (
        normalize_nuclear_cell_pair_contour_mode(
            defaults_payload.get(
                "nuclear_cell_pair_contour_mode",
                defaults_payload.get("nuclearCellPairContourMode"),
            )
        )
    )
    normalized["experiment_defaults"]["use_legacy_nuclear_cell_pair_pipeline"] = (
        _as_bool(
            defaults_payload.get("use_legacy_nuclear_cell_pair_pipeline"),
            default=False,
        )
    )

    signal_selection = resolve_signal_quantification_selection(
        payload=defaults_payload,
        selected_plugins=normalized["experiment_defaults"]["selected_plugins"],
        nuclear_cell_pair_mode=mode,
        puncta_line_mode=normalized["experiment_defaults"]["puncta_line_mode"],
        default_alternate_nucleus_detection_enabled=normalized["experiment_defaults"][
            "alternate_nucleus_detection_enabled"
        ],
    )
    normalized["experiment_defaults"][
        "signal_quantification_enabled"
    ] = signal_selection.enabled
    normalized["experiment_defaults"][
        "signal_quantification_mode"
    ] = signal_selection.mode
    normalized["experiment_defaults"][
        "puncta_contour_intensity_enabled"
    ] = signal_selection.puncta_contour_intensity_enabled
    normalized["experiment_defaults"][
        "alternate_nucleus_detection_enabled"
    ] = signal_selection.alternate_nucleus_detection_enabled
    normalized["experiment_defaults"][
        "alternate_red_detection"
    ] = signal_selection.alternate_nucleus_detection_enabled
    normalized["experiment_defaults"]["selected_plugins"] = list(
        signal_selection.configured_plugins
    )

    normalized["auto_save_experiments"] = _as_bool(
        raw_payload.get("auto_save_experiments"),
        default=True,
    )
    normalized["show_saved_file_channels"] = _as_bool(
        raw_payload.get("show_saved_file_channels"),
        default=True,
    )
    normalized["show_saved_file_scales"] = _as_bool(
        raw_payload.get("show_saved_file_scales"),
        default=True,
    )
    normalized["sidebar_starts_open"] = _as_bool(
        raw_payload.get("sidebar_starts_open"),
        default=True,
    )
    normalized["confirm_cell_deletion"] = _as_bool(
        raw_payload.get("confirm_cell_deletion"),
        default=True,
    )
    normalized["confirm_multi_cell_deletion"] = _as_bool(
        raw_payload.get("confirm_multi_cell_deletion"),
        default=True,
    )
    normalized["sidebar_spatial_stats_unit"] = _normalize_unit(
        raw_payload.get("sidebar_spatial_stats_unit"),
        default=normalized["experiment_defaults"]["spatial_stats_unit"],
    )
    normalized["main_image_channel"] = normalize_main_image_channel(
        raw_payload.get("main_image_channel"),
        default="",
    )
    return normalized


def build_experiment_defaults_from_popup_payload(
    raw_payload: Any,
    *,
    current_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate experiment-popup JSON and return normalized experiment defaults."""

    if not isinstance(raw_payload, dict):
        raise PreferenceValidationError("Request body must be a JSON object.")

    allowed_fields = {
        "selected_plugins",
        "signal_quantification_enabled",
        "signal_quantification_mode",
        "puncta_contour_intensity_enabled",
        "alternate_nucleus_detection_enabled",
        "module_enabled",
        "enforce_layer_count",
        "enforce_wavelengths",
        "show_legacy_plugins",
        "manual_required_channels",
        "green_contour_filter_enabled",
        "green_dot_split_enabled",
        "green_dot_split_mode",
        "red_dot_split_enabled",
        "red_dot_split_mode",
        "alternate_red_detection",
        "puncta_line_width",
        "puncta_line_width_unit",
        "cen_dot_distance",
        "cen_dot_distance_unit",
        "cen_dot_proximity_radius",
        "cen_dot_proximity_radius_unit",
        "biorientation_red_min_distance",
        "biorientation_red_min_distance_unit",
        "biorientation_red_max_distance",
        "biorientation_red_max_distance_unit",
        "biorientation_collinearity_threshold",
        "puncta_line_mode",
        "nuclear_cell_pair_mode",
        "nuclear_cell_pair_contour_mode",
        "use_legacy_nuclear_cell_pair_pipeline",
        "microns_per_pixel",
        "use_metadata_scale",
        "use_metadata_channel_order",
        "fallback_channel_order",
    }
    unknown_fields = sorted(set(raw_payload.keys()) - allowed_fields)
    if unknown_fields:
        raise PreferenceValidationError(
            f"Unknown workflow-default fields: {', '.join(unknown_fields)}."
        )

    current = normalize_preferences_payload(
        {"experiment_defaults": current_defaults or {}}
    )["experiment_defaults"]

    raw_selected_plugins = raw_payload.get("selected_plugins")
    if not isinstance(raw_selected_plugins, list):
        raise PreferenceValidationError("selected_plugins must be a list.")
    resolved_plugins: list[str] = []
    exclusive_groups: dict[str, str] = {}
    for raw_plugin in raw_selected_plugins:
        if not isinstance(raw_plugin, str):
            raise PreferenceValidationError("selected_plugins must contain strings.")
        plugin_id = PLUGIN_ID_ALIASES.get(raw_plugin.strip(), raw_plugin.strip())
        if plugin_id not in PLUGIN_DEFINITIONS:
            raise PreferenceValidationError(f"Unknown plugin ID: {raw_plugin}.")
        definition = PLUGIN_DEFINITIONS[plugin_id]
        if definition.exclusive_group:
            existing = exclusive_groups.get(definition.exclusive_group)
            if existing and existing != plugin_id:
                raise PreferenceValidationError(
                    "Only one plugin can be selected in each exclusive group."
                )
            exclusive_groups[definition.exclusive_group] = plugin_id
        resolved_plugins.append(plugin_id)
    selected_plugins = expand_selected_plugins(resolved_plugins)

    raw_manual_channels = raw_payload.get("manual_required_channels")
    if not isinstance(raw_manual_channels, list):
        raise PreferenceValidationError("manual_required_channels must be a list.")
    manual_required_channels: list[str] = []
    seen_channels: set[str] = set()
    for raw_channel in raw_manual_channels:
        if not isinstance(raw_channel, str):
            raise PreferenceValidationError(
                "manual_required_channels must contain strings."
            )
        channel = raw_channel.strip()
        if channel not in CHANNEL_ORDER or channel in ALWAYS_REQUIRED_CHANNELS:
            raise PreferenceValidationError(
                f"manual_required_channels contains an invalid channel: {raw_channel}."
            )
        if channel in seen_channels:
            continue
        seen_channels.add(channel)
        manual_required_channels.append(channel)

    puncta_line_width_unit = _strict_unit(
        raw_payload.get("puncta_line_width_unit"),
        field="puncta_line_width_unit",
    )
    cen_dot_distance_unit = _strict_unit(
        raw_payload.get("cen_dot_distance_unit"),
        field="cen_dot_distance_unit",
    )
    cen_dot_proximity_radius_unit = _strict_unit(
        raw_payload.get("cen_dot_proximity_radius_unit"),
        field="cen_dot_proximity_radius_unit",
    )
    biorientation_red_min_distance_unit = _strict_unit(
        raw_payload.get("biorientation_red_min_distance_unit"),
        field="biorientation_red_min_distance_unit",
    )
    biorientation_red_max_distance_unit = _strict_unit(
        raw_payload.get("biorientation_red_max_distance_unit"),
        field="biorientation_red_max_distance_unit",
    )

    puncta_line_width_minimum = 1.0 if puncta_line_width_unit == "px" else 0.01
    puncta_line_width = _strict_float(
        raw_payload.get("puncta_line_width"),
        field="puncta_line_width",
        minimum=puncta_line_width_minimum,
    )
    cen_dot_distance = _strict_float(
        raw_payload.get("cen_dot_distance"),
        field="cen_dot_distance",
        minimum=0.0,
    )
    cen_dot_proximity_radius = _strict_float(
        raw_payload.get("cen_dot_proximity_radius"),
        field="cen_dot_proximity_radius",
        minimum=0.0,
    )
    biorientation_red_min_distance = _strict_float(
        raw_payload.get("biorientation_red_min_distance"),
        field="biorientation_red_min_distance",
        minimum=0.0,
    )
    biorientation_red_max_distance = _strict_float(
        raw_payload.get("biorientation_red_max_distance"),
        field="biorientation_red_max_distance",
        minimum=0.0,
    )
    biorientation_collinearity_threshold = _strict_int(
        raw_payload.get("biorientation_collinearity_threshold"),
        field="biorientation_collinearity_threshold",
        minimum=0,
    )
    microns_per_pixel = _strict_float(
        raw_payload.get("microns_per_pixel"),
        field="microns_per_pixel",
        minimum=0.0001,
    )

    puncta_line_mode = _strict_mode(
        raw_payload.get("puncta_line_mode"),
        field="puncta_line_mode",
        allowed={"red_puncta", "green_puncta"},
    )
    nuclear_cell_pair_mode = _strict_mode(
        raw_payload.get("nuclear_cell_pair_mode"),
        field="nuclear_cell_pair_mode",
        allowed=NUCLEAR_CELL_PAIR_MODES,
    )
    nuclear_cell_pair_contour_mode = _strict_mode(
        raw_payload.get(
            "nuclear_cell_pair_contour_mode",
            current.get(
                "nuclear_cell_pair_contour_mode",
                DEFAULT_NUCLEAR_CELL_PAIR_CONTOUR_MODE,
            ),
        ),
        field="nuclear_cell_pair_contour_mode",
        allowed=set(NUCLEAR_CELL_PAIR_CONTOUR_MODES),
    )
    use_legacy_nuclear_cell_pair_pipeline = _strict_bool(
        raw_payload.get(
            "use_legacy_nuclear_cell_pair_pipeline",
            current.get("use_legacy_nuclear_cell_pair_pipeline", False),
        ),
        field="use_legacy_nuclear_cell_pair_pipeline",
    )
    green_dot_split_mode = _strict_mode(
        raw_payload.get("green_dot_split_mode"),
        field="green_dot_split_mode",
        allowed={"balanced", "aggressive"},
    )
    red_dot_split_mode = _strict_mode(
        raw_payload.get(
            "red_dot_split_mode",
            current.get("red_dot_split_mode", DEFAULT_DOT_SPLIT_MODE),
        ),
        field="red_dot_split_mode",
        allowed={"balanced", "aggressive"},
    )

    signal_payload: dict[str, Any] = {}
    if "signal_quantification_enabled" in raw_payload:
        signal_payload["signal_quantification_enabled"] = _strict_bool(
            raw_payload.get("signal_quantification_enabled"),
            field="signal_quantification_enabled",
        )
    if "signal_quantification_mode" in raw_payload:
        signal_payload["signal_quantification_mode"] = _strict_mode(
            raw_payload.get("signal_quantification_mode"),
            field="signal_quantification_mode",
            allowed=set(SIGNAL_QUANTIFICATION_MODES),
        )
    if "puncta_contour_intensity_enabled" in raw_payload:
        signal_payload["puncta_contour_intensity_enabled"] = _strict_bool(
            raw_payload.get("puncta_contour_intensity_enabled"),
            field="puncta_contour_intensity_enabled",
        )
    alternate_detection_field = (
        "alternate_nucleus_detection_enabled"
        if "alternate_nucleus_detection_enabled" in raw_payload
        else "alternate_red_detection"
    )
    if alternate_detection_field in raw_payload:
        signal_payload["alternate_nucleus_detection_enabled"] = _strict_bool(
            raw_payload.get(alternate_detection_field),
            field=alternate_detection_field,
        )

    signal_selection = resolve_signal_quantification_selection(
        payload=signal_payload,
        selected_plugins=selected_plugins,
        nuclear_cell_pair_mode=nuclear_cell_pair_mode,
        puncta_line_mode=puncta_line_mode,
        default_alternate_nucleus_detection_enabled=bool(
            current.get("alternate_nucleus_detection_enabled", True)
        ),
    )
    selected_plugins = list(signal_selection.configured_plugins)

    show_legacy_plugins = _strict_bool(
        raw_payload.get("show_legacy_plugins"),
        field="show_legacy_plugins",
    )
    if not show_legacy_plugins:
        legacy_plugins = [
            plugin_id
            for plugin_id in selected_plugins
            if PLUGIN_DEFINITIONS[plugin_id].is_legacy
        ]
        if legacy_plugins:
            raise PreferenceValidationError(
                "Legacy plugins can only be saved when show_legacy_plugins is enabled."
            )

    next_defaults = dict(current)
    next_defaults.update(
        {
            "selected_plugins": selected_plugins,
            "signal_quantification_enabled": signal_selection.enabled,
            "signal_quantification_mode": signal_selection.mode,
            "puncta_contour_intensity_enabled": (
                signal_selection.puncta_contour_intensity_enabled
            ),
            "alternate_nucleus_detection_enabled": (
                signal_selection.alternate_nucleus_detection_enabled
            ),
            "module_enabled": _strict_bool(
                raw_payload.get("module_enabled"),
                field="module_enabled",
            ),
            "enforce_layer_count": _strict_bool(
                raw_payload.get("enforce_layer_count"),
                field="enforce_layer_count",
            ),
            "enforce_wavelengths": _strict_bool(
                raw_payload.get("enforce_wavelengths"),
                field="enforce_wavelengths",
            ),
            "show_legacy_plugins": show_legacy_plugins,
            "manual_required_channels": manual_required_channels,
            "green_contour_filter_enabled": _strict_bool(
                raw_payload.get("green_contour_filter_enabled"),
                field="green_contour_filter_enabled",
            ),
            "green_dot_split_enabled": _strict_bool(
                raw_payload.get("green_dot_split_enabled"),
                field="green_dot_split_enabled",
            ),
            "green_dot_split_mode": green_dot_split_mode,
            "red_dot_split_enabled": _strict_bool(
                raw_payload.get(
                    "red_dot_split_enabled",
                    current.get("red_dot_split_enabled", True),
                ),
                field="red_dot_split_enabled",
            ),
            "red_dot_split_mode": red_dot_split_mode,
            "alternate_red_detection": (
                signal_selection.alternate_nucleus_detection_enabled
            ),
            "puncta_line_width": puncta_line_width,
            "puncta_line_width_unit": puncta_line_width_unit,
            "cen_dot_distance": cen_dot_distance,
            "cen_dot_distance_unit": cen_dot_distance_unit,
            "cen_dot_proximity_radius": cen_dot_proximity_radius,
            "cen_dot_proximity_radius_unit": cen_dot_proximity_radius_unit,
            "biorientation_red_min_distance": biorientation_red_min_distance,
            "biorientation_red_min_distance_unit": biorientation_red_min_distance_unit,
            "biorientation_red_max_distance": biorientation_red_max_distance,
            "biorientation_red_max_distance_unit": biorientation_red_max_distance_unit,
            "biorientation_collinearity_threshold": biorientation_collinearity_threshold,
            "puncta_line_mode": puncta_line_mode,
            "nuclear_cell_pair_mode": nuclear_cell_pair_mode,
            "nuclear_cell_pair_contour_mode": nuclear_cell_pair_contour_mode,
            "use_legacy_nuclear_cell_pair_pipeline": use_legacy_nuclear_cell_pair_pipeline,
            "microns_per_pixel": microns_per_pixel,
            "use_metadata_scale": _strict_bool(
                raw_payload.get("use_metadata_scale"),
                field="use_metadata_scale",
            ),
            "use_metadata_channel_order": _strict_bool(
                raw_payload.get("use_metadata_channel_order"),
                field="use_metadata_channel_order",
            ),
            "fallback_channel_order": _strict_channel_order(
                raw_payload.get("fallback_channel_order"),
                field="fallback_channel_order",
            ),
        }
    )
    return next_defaults


def get_user_preferences(user: Any) -> dict[str, Any]:
    """Read normalized preference payload from user config."""

    if not getattr(user, "is_authenticated", False):
        return deepcopy(DEFAULT_USER_PREFERENCES)
    config = user.config if isinstance(user.config, dict) else {}
    return normalize_preferences_payload(config.get("preferences"))


def update_user_preferences(
    user: Any, preference_payload: dict[str, Any]
) -> dict[str, Any]:
    """Persist normalized preferences in ``user.config``."""

    normalized = normalize_preferences_payload(preference_payload)
    config = dict(user.config or {})
    config["preferences"] = normalized
    user.config = config
    user.save(update_fields=["config"])
    return normalized


def should_auto_save_experiments(user: Any) -> bool:
    """Return whether experiment results should be persisted to account history."""

    return bool(get_user_preferences(user).get("auto_save_experiments", True))
