"""Helpers for account-level experiment preferences."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from core.channel_roles import CHANNEL_ROLE_ORDER
from core.stats_plugins import CHANNEL_ORDER, normalize_selected_plugins

NUCLEAR_CELLULAR_MODES = {"green_nucleus", "red_nucleus"}
LENGTH_UNITS = {"px", "um"}
DEFAULT_MICRONS_PER_PIXEL = 0.1

DEFAULT_USER_PREFERENCES: dict[str, Any] = {
    "experiment_defaults": {
        "selected_plugins": [
            "RedLineIntensity",
            "CENDot",
            "GreenRedIntensity",
            "NuclearCellularIntensity",
        ],
        "module_enabled": False,
        "enforce_layer_count": False,
        "enforce_wavelengths": False,
        "show_legacy_plugins": False,
        "manual_required_channels": [],
        "red_line_width": 1,
        "cen_dot_distance": 37,
        "cen_dot_collinearity_threshold": 66,
        "nuclear_cellular_mode": "green_nucleus",
        "green_contour_filter_enabled": False,
        "alternate_red_detection": False,
        "red_line_width_unit": "px",
        "cen_dot_distance_unit": "px",
        "microns_per_pixel": DEFAULT_MICRONS_PER_PIXEL,
        "use_metadata_scale": True,
    },
    "auto_save_experiments": True,
    "show_saved_file_channels": True,
    "show_saved_file_scales": True,
    "sidebar_starts_open": True,
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
    normalized["experiment_defaults"]["selected_plugins"] = normalize_selected_plugins(
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

    raw_required_channels = defaults_payload.get("manual_required_channels", [])
    if not isinstance(raw_required_channels, list):
        raw_required_channels = []
    normalized["experiment_defaults"]["manual_required_channels"] = [
        channel for channel in raw_required_channels if channel in CHANNEL_ORDER
    ]

    normalized["experiment_defaults"]["red_line_width_unit"] = _normalize_unit(
        defaults_payload.get(
            "red_line_width_unit",
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
    width_minimum = (
        1
        if normalized["experiment_defaults"]["red_line_width_unit"] == "px"
        else 0
    )
    normalized["experiment_defaults"]["red_line_width"] = _as_float(
        defaults_payload.get(
            "red_line_width",
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
    normalized["experiment_defaults"]["cen_dot_collinearity_threshold"] = _as_int(
        defaults_payload.get(
            "cen_dot_collinearity_threshold",
            defaults_payload.get("gfp_threshold"),
        ),
        default=66,
        minimum=0,
    )

    mode = str(defaults_payload.get("nuclear_cellular_mode") or "").strip()
    if mode not in NUCLEAR_CELLULAR_MODES:
        mode = "green_nucleus"
    normalized["experiment_defaults"]["nuclear_cellular_mode"] = mode

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
    return normalized


def get_user_preferences(user: Any) -> dict[str, Any]:
    """Read normalized preference payload from user config."""

    if not getattr(user, "is_authenticated", False):
        return deepcopy(DEFAULT_USER_PREFERENCES)
    config = user.config if isinstance(user.config, dict) else {}
    return normalize_preferences_payload(config.get("preferences"))


def update_user_preferences(user: Any, preference_payload: dict[str, Any]) -> dict[str, Any]:
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
