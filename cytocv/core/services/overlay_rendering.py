"""Exact fluorescence overlay replay and cache helpers for result viewers."""

from __future__ import annotations

import copy
import json
import logging
import os
import time
from pathlib import Path
from uuid import uuid4

import numpy as np
from django.conf import settings
from django.urls import reverse
from PIL import Image

from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
    channel_slug,
    normalize_channel_role,
)
from core.config import input_dir
from core.models import CellStatistics
from core.services.artifact_storage import PNG_PROFILE_ANALYSIS_FAST, save_png_image
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
    normalize_nuclear_cell_pair_contour_mode,
)
from core.services.signal_quantification import (
    SIGNAL_MODE_PUNCTA_DISTANCE,
    resolve_effective_alternate_nucleus_detection,
)
from core.stats_plugins import build_stats_execution_plan

logger = logging.getLogger(__name__)

OVERLAY_RENDER_SCHEMA_VERSION = 4
OVERLAY_RENDER_CONFIG_FILENAME = "overlay-render-config.json"
OVERLAY_CACHE_DIR_PREFIX = "overlay-cache-v"
OVERLAY_CACHE_DIRNAME = f"overlay-cache-v{OVERLAY_RENDER_SCHEMA_VERSION}"
OVERLAY_CHANNEL_LABELS = {
    "red": "Red",
    "green": "Green",
    "blue": "Blue",
}
OVERLAY_BASE_CHANNELS = (
    CHANNEL_ROLE_RED,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
)
OVERLAY_RENDER_CHANNELS = tuple(OVERLAY_CHANNEL_LABELS.keys())
OVERLAY_CACHE_LOCK_POLL_SECONDS = 0.05
OVERLAY_CACHE_LOCK_STALE_SECONDS = 45.0


def _normalize_render_config_payload(payload: dict[str, object]) -> dict[str, object]:
    """Normalize historical overlay snapshots to the current replay vocabulary."""

    normalized = dict(payload or {})
    channel_config = dict(normalized.get("channel_config", {}) or {})
    normalized["channel_config"] = {
        normalize_channel_role(channel_name) or str(channel_name): int(channel_index)
        for channel_name, channel_index in channel_config.items()
    }
    if "mCherry_line_width" in normalized and "puncta_line_width" not in normalized:
        normalized["puncta_line_width"] = normalized["mCherry_line_width"]
    if "red_line_width" in normalized and "puncta_line_width" not in normalized:
        normalized["puncta_line_width"] = normalized["red_line_width"]
    if "mcherry_width_px" in normalized and "puncta_line_width_px" not in normalized:
        normalized["puncta_line_width_px"] = normalized["mcherry_width_px"]
    if "red_line_width_px" in normalized and "puncta_line_width_px" not in normalized:
        normalized["puncta_line_width_px"] = normalized["red_line_width_px"]
    if "gfp_distance_value_used" in normalized and "cen_dot_distance_value_used" not in normalized:
        normalized["cen_dot_distance_value_used"] = normalized["gfp_distance_value_used"]
    if "gfp_threshold" in normalized and "biorientation_collinearity_threshold" not in normalized:
        normalized["biorientation_collinearity_threshold"] = normalized["gfp_threshold"]
    if (
        "cen_dot_collinearity_threshold" in normalized
        and "biorientation_collinearity_threshold" not in normalized
    ):
        normalized["biorientation_collinearity_threshold"] = normalized["cen_dot_collinearity_threshold"]
    if "gfp_filter_enabled" in normalized and "green_contour_filter_enabled" not in normalized:
        normalized["green_contour_filter_enabled"] = normalized["gfp_filter_enabled"]
    if "alternate_mcherry_detection" in normalized and "alternate_red_detection" not in normalized:
        normalized["alternate_red_detection"] = normalized["alternate_mcherry_detection"]
    if "alternate_nucleus_detection_enabled" not in normalized:
        normalized["alternate_nucleus_detection_enabled"] = normalized.get(
            "alternate_red_detection",
            False,
        )
    if "biorientation_green_split_enabled" in normalized and "green_dot_split_enabled" not in normalized:
        normalized["green_dot_split_enabled"] = normalized["biorientation_green_split_enabled"]
    normalized["green_dot_split_mode"] = normalize_dot_split_mode(
        normalized.get(
            "green_dot_split_mode",
            normalized.get("greenDotSplitMode", DEFAULT_DOT_SPLIT_MODE),
        )
    )
    normalized["red_dot_split_enabled"] = bool(
        normalized.get(
            "red_dot_split_enabled",
            normalized.get("redDotSplitEnabled", True),
        )
    )
    normalized["red_dot_split_mode"] = normalize_dot_split_mode(
        normalized.get(
            "red_dot_split_mode",
            normalized.get("redDotSplitMode", DEFAULT_DOT_SPLIT_MODE),
        )
    )
    normalized["nuclear_cell_pair_contour_mode"] = normalize_nuclear_cell_pair_contour_mode(
        normalized.get(
            "nuclear_cell_pair_contour_mode",
            normalized.get("nuclearCellPairContourMode"),
        )
    )
    if "stats_mcherry_width_unit" in normalized and "stats_puncta_line_width_unit" not in normalized:
        normalized["stats_puncta_line_width_unit"] = normalized["stats_mcherry_width_unit"]
    if "stats_red_line_width_unit" in normalized and "stats_puncta_line_width_unit" not in normalized:
        normalized["stats_puncta_line_width_unit"] = normalized["stats_red_line_width_unit"]
    if "stats_gfp_distance_unit" in normalized and "stats_cen_dot_distance_unit" not in normalized:
        normalized["stats_cen_dot_distance_unit"] = normalized["stats_gfp_distance_unit"]
    normalized["puncta_line_mode"] = normalize_puncta_line_mode(
        normalized.get("puncta_line_mode"),
        default=DEFAULT_PUNCTA_LINE_MODE,
    )
    if "nuclear_cellular_mode" in normalized and "nuclear_cell_pair_mode" not in normalized:
        normalized["nuclear_cell_pair_mode"] = normalized["nuclear_cellular_mode"]
    return normalized


def overlay_render_config_path(run_uuid: str) -> Path:
    """Return the per-run overlay replay snapshot path."""

    return Path(settings.MEDIA_ROOT) / str(run_uuid) / "segmented" / OVERLAY_RENDER_CONFIG_FILENAME


def overlay_cache_dir(run_uuid: str) -> Path:
    """Return the schema-versioned exact overlay cache directory."""

    return Path(settings.MEDIA_ROOT) / str(run_uuid) / "segmented" / OVERLAY_CACHE_DIRNAME


def overlay_cache_image_path(run_uuid: str, cell_id: int, channel: str) -> Path:
    """Return the stable cache filename for one cell/channel overlay image."""

    normalized_channel = normalize_overlay_channel(channel)
    return overlay_cache_dir(run_uuid) / f"cell-{cell_id}-{normalized_channel}.png"


def overlay_cache_image_paths_for_cell(run_uuid: str, cell_id: int) -> dict[str, Path]:
    """Return all exact overlay cache paths for a cell."""

    return {
        channel: overlay_cache_image_path(run_uuid, cell_id, channel)
        for channel in OVERLAY_RENDER_CHANNELS
    }


def overlay_cache_lock_path(run_uuid: str, cell_id: int) -> Path:
    """Return the cooperative per-cell cache lock marker path."""

    return overlay_cache_dir(run_uuid) / f"cell-{int(cell_id)}.lock"


def build_overlay_image_url(run_uuid: str, cell_id: int, channel: str) -> str:
    """Build the protected dynamic overlay endpoint URL for viewer payloads."""

    return reverse(
        "cell_overlay_image",
        kwargs={
            "uuid": str(run_uuid),
            "cell_id": int(cell_id),
            "channel": normalize_overlay_channel(channel),
        },
    )


def build_overlay_render_config(
    *,
    image_stem: str,
    channel_config: dict[str, int],
    kernel_size: int,
    kernel_deviation: int,
    puncta_line_width: int,
    arrested: str,
    selected_analysis: list[str],
    puncta_line_mode: str,
    nuclear_cell_pair_mode: str,
    puncta_line_width_px: int,
    cen_dot_distance_value_used: float,
    green_contour_filter_enabled: bool,
    alternate_red_detection: bool,
    signal_quantification_enabled: bool = True,
    signal_quantification_mode: str = "puncta_distance",
    puncta_contour_intensity_enabled: bool = True,
    alternate_nucleus_detection_enabled: bool | None = None,
    alternate_nucleus_detection_channel: str | None = None,
    puncta_line_width_unit: str | None = None,
    cen_dot_distance_unit: str | None = None,
    cen_dot_proximity_radius: float | None = None,
    cen_dot_proximity_radius_unit: str | None = None,
    biorientation_red_min_distance_value: float = 0.0,
    biorientation_red_min_distance_unit: str = "px",
    biorientation_red_max_distance_value: float = 37.0,
    biorientation_red_max_distance_unit: str = "px",
    biorientation_collinearity_threshold: int = DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX,
    green_dot_split_enabled: bool = True,
    green_dot_split_mode: str = DEFAULT_DOT_SPLIT_MODE,
    red_dot_split_enabled: bool = True,
    red_dot_split_mode: str = DEFAULT_DOT_SPLIT_MODE,
    nuclear_cell_pair_contour_mode: str = DEFAULT_NUCLEAR_CELL_PAIR_CONTOUR_MODE,
) -> dict[str, object]:
    """Capture all parameters needed to replay contour-on fluorescence images."""

    effective_alternate_enabled, effective_alternate_channel = (
        resolve_effective_alternate_nucleus_detection(
            signal_quantification_enabled=signal_quantification_enabled,
            signal_quantification_mode=signal_quantification_mode,
            nuclear_cell_pair_mode=nuclear_cell_pair_mode,
            alternate_nucleus_detection_enabled=(
                alternate_red_detection
                if alternate_nucleus_detection_enabled is None
                else alternate_nucleus_detection_enabled
            ),
            alternate_nucleus_detection_channel=alternate_nucleus_detection_channel,
        )
    )
    render_config: dict[str, object] = {
        "schema_version": OVERLAY_RENDER_SCHEMA_VERSION,
        "image_stem": str(image_stem),
        "channel_config": {
            str(channel_name): int(channel_index)
            for channel_name, channel_index in channel_config.items()
            if channel_index is not None
        },
        "selected_analysis": [str(plugin_name) for plugin_name in selected_analysis if str(plugin_name)],
        "kernel_size": int(kernel_size),
        "kernel_deviation": int(kernel_deviation),
        "puncta_line_width": int(puncta_line_width),
        "arrested": str(arrested),
        "puncta_line_mode": normalize_puncta_line_mode(puncta_line_mode),
        "nuclear_cell_pair_mode": str(nuclear_cell_pair_mode),
        "nuclear_cell_pair_contour_mode": normalize_nuclear_cell_pair_contour_mode(
            nuclear_cell_pair_contour_mode
        ),
        "puncta_line_width_px": int(puncta_line_width_px),
        "cen_dot_distance_value_used": float(cen_dot_distance_value_used),
        "biorientation_collinearity_threshold": int(biorientation_collinearity_threshold),
        "green_contour_filter_enabled": bool(green_contour_filter_enabled),
        "alternate_red_detection": effective_alternate_enabled,
        "signal_quantification_enabled": bool(signal_quantification_enabled),
        "signal_quantification_mode": str(signal_quantification_mode),
        "puncta_contour_intensity_enabled": bool(puncta_contour_intensity_enabled),
        "alternate_nucleus_detection_enabled": effective_alternate_enabled,
        "alternate_nucleus_detection_channel": effective_alternate_channel,
        "green_dot_split_enabled": bool(green_dot_split_enabled),
        "green_dot_split_mode": normalize_dot_split_mode(green_dot_split_mode),
        "red_dot_split_enabled": bool(red_dot_split_enabled),
        "red_dot_split_mode": normalize_dot_split_mode(red_dot_split_mode),
        "stats_biorientation_red_min_distance_value": float(biorientation_red_min_distance_value),
        "stats_biorientation_red_min_distance_unit": str(biorientation_red_min_distance_unit),
        "stats_biorientation_red_max_distance_value": float(biorientation_red_max_distance_value),
        "stats_biorientation_red_max_distance_unit": str(biorientation_red_max_distance_unit),
    }
    if puncta_line_width_unit:
        render_config["stats_puncta_line_width_unit"] = str(puncta_line_width_unit)
    if cen_dot_distance_unit:
        render_config["stats_cen_dot_distance_unit"] = str(cen_dot_distance_unit)
    if cen_dot_proximity_radius is not None:
        render_config["cen_dot_proximity_radius"] = float(cen_dot_proximity_radius)
    if cen_dot_proximity_radius_unit:
        render_config["stats_cen_dot_proximity_radius_unit"] = str(cen_dot_proximity_radius_unit)
    return render_config


def write_overlay_render_config(run_uuid: str, render_config: dict[str, object]) -> Path:
    """Persist the per-run snapshot used to replay overlay images later."""

    destination = overlay_render_config_path(run_uuid)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(render_config, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return destination


def load_overlay_render_config(run_uuid: str) -> dict[str, object]:
    """Load and validate the current overlay replay snapshot for a run."""

    path = overlay_render_config_path(run_uuid)
    payload = _normalize_render_config_payload(
        json.loads(path.read_text(encoding="utf-8"))
    )
    if int(payload.get("schema_version", 0)) != OVERLAY_RENDER_SCHEMA_VERSION:
        raise ValueError(f"Unsupported overlay render schema for run {run_uuid}")
    return payload


def overlay_render_config_exists(run_uuid: str) -> bool:
    """Return whether a replay snapshot exists for the run."""

    return overlay_render_config_path(run_uuid).exists()


def overlay_render_config_supported(run_uuid: str) -> bool:
    """Return whether the replay snapshot can be served by this code version."""

    try:
        payload = json.loads(
            overlay_render_config_path(run_uuid).read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    try:
        schema_version = int(payload.get("schema_version", 0))
    except (TypeError, ValueError):
        return False
    return schema_version == OVERLAY_RENDER_SCHEMA_VERSION


def _overlay_cache_dir_version(path: Path) -> int:
    name = path.name
    if not name.startswith(OVERLAY_CACHE_DIR_PREFIX):
        return -1
    try:
        return int(name.removeprefix(OVERLAY_CACHE_DIR_PREFIX))
    except ValueError:
        return -1


def find_historical_overlay_cache_image_path(
    run_uuid: str,
    cell_id: int,
    channel: str,
) -> Path | None:
    """Return the newest compatible overlay cache file from an older schema."""

    normalized_channel = normalize_overlay_channel(channel)
    segmented_dir = Path(settings.MEDIA_ROOT) / str(run_uuid) / "segmented"
    if not segmented_dir.exists():
        return None

    image_name = f"cell-{int(cell_id)}-{normalized_channel}.png"
    candidates: list[Path] = []
    for cache_dir in segmented_dir.glob(f"{OVERLAY_CACHE_DIR_PREFIX}*"):
        if not cache_dir.is_dir() or cache_dir.name == OVERLAY_CACHE_DIRNAME:
            continue
        candidate = cache_dir / image_name
        if candidate.exists():
            candidates.append(candidate)

    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda path: (_overlay_cache_dir_version(path.parent), path.parent.name),
        reverse=True,
    )[0]


def overlay_image_available(run_uuid: str, cell_id: int, channel: str) -> bool:
    """Return whether any current, replayable, or legacy overlay source exists."""

    normalized_channel = normalize_overlay_channel(channel)
    if overlay_cache_image_path(run_uuid, cell_id, normalized_channel).exists():
        return True
    if find_historical_overlay_cache_image_path(run_uuid, cell_id, normalized_channel) is not None:
        return True
    if overlay_render_config_supported(run_uuid):
        return True
    return find_legacy_debug_image_path(run_uuid, cell_id, normalized_channel) is not None


def normalize_overlay_channel(channel: str) -> str:
    """Normalize public channel names to overlay endpoint/cache slugs."""

    normalized_role = normalize_channel_role(channel)
    if normalized_role in {CHANNEL_ROLE_RED, CHANNEL_ROLE_GREEN, CHANNEL_ROLE_BLUE}:
        return channel_slug(normalized_role)
    normalized = str(channel).strip().lower()
    if normalized not in OVERLAY_CHANNEL_LABELS:
        raise ValueError(f"Unsupported overlay channel: {channel}")
    return normalized


def build_legacy_debug_image_path(
    run_uuid: str,
    image_stem: str,
    cell_id: int,
    channel: str,
) -> Path:
    """Return the historical debug-overlay path preserved for old runs."""

    channel_label = OVERLAY_CHANNEL_LABELS[normalize_overlay_channel(channel)]
    return (
        Path(settings.MEDIA_ROOT)
        / str(run_uuid)
        / "segmented"
        / f"{image_stem}-{cell_id}-{channel_label}_debug.png"
    )


def find_legacy_debug_image_path(run_uuid: str, cell_id: int, channel: str) -> Path | None:
    """Find a historical debug-overlay PNG for runs without replay cache."""

    normalized_channel = normalize_overlay_channel(channel)
    channel_label = OVERLAY_CHANNEL_LABELS[normalized_channel]
    segmented_dir = Path(settings.MEDIA_ROOT) / str(run_uuid) / "segmented"
    matches = sorted(segmented_dir.glob(f"*-{cell_id}-{channel_label}_debug.png"))
    if not matches:
        return None
    return matches[0]


def clone_cell_statistics_for_overlay(cell_stat: CellStatistics) -> CellStatistics:
    """Clone a statistics row so replay can mutate properties without saving."""

    clone = CellStatistics()
    for field in cell_stat._meta.concrete_fields:
        if field.primary_key:
            continue
        if field.name == "segmented_image":
            setattr(clone, field.attname, getattr(cell_stat, field.attname))
            clone.segmented_image = cell_stat.segmented_image
            continue
        setattr(clone, field.attname, copy.deepcopy(getattr(cell_stat, field.attname)))
    clone.properties = copy.deepcopy(getattr(cell_stat, "properties", {}) or {})
    return clone


def _build_overlay_conf(run_uuid: str, render_config: dict[str, object]) -> dict[str, object]:
    signal_quantification_enabled = bool(
        render_config.get("signal_quantification_enabled", True)
    )
    signal_quantification_mode = str(
        render_config.get("signal_quantification_mode", SIGNAL_MODE_PUNCTA_DISTANCE)
    )
    nuclear_cell_pair_mode = str(render_config.get("nuclear_cell_pair_mode", "green_nucleus"))
    nuclear_cell_pair_contour_mode = normalize_nuclear_cell_pair_contour_mode(
        render_config.get("nuclear_cell_pair_contour_mode")
    )
    effective_alternate_enabled, effective_alternate_channel = (
        resolve_effective_alternate_nucleus_detection(
            signal_quantification_enabled=signal_quantification_enabled,
            signal_quantification_mode=signal_quantification_mode,
            nuclear_cell_pair_mode=nuclear_cell_pair_mode,
            alternate_nucleus_detection_enabled=render_config.get(
                "alternate_nucleus_detection_enabled",
                render_config.get("alternate_red_detection", False),
            ),
            alternate_nucleus_detection_channel=render_config.get(
                "alternate_nucleus_detection_channel"
            ),
        )
    )
    return {
        "input_dir": input_dir,
        "output_dir": str(Path(settings.MEDIA_ROOT) / str(run_uuid)),
        "kernel_size": int(render_config["kernel_size"]),
        "puncta_line_width": int(render_config["puncta_line_width"]),
        "kernel_deviation": int(render_config["kernel_deviation"]),
        "arrested": str(render_config["arrested"]),
        "analysis": list(render_config.get("selected_analysis", [])),
        "puncta_line_mode": normalize_puncta_line_mode(
            render_config.get("puncta_line_mode"),
            default=DEFAULT_PUNCTA_LINE_MODE,
        ),
        "nuclear_cell_pair_mode": nuclear_cell_pair_mode,
        "nuclear_cell_pair_contour_mode": nuclear_cell_pair_contour_mode,
        "green_contour_filter_enabled": bool(
            render_config.get("green_contour_filter_enabled", False)
        ),
        "alternate_red_detection": effective_alternate_enabled,
        "signal_quantification_enabled": signal_quantification_enabled,
        "signal_quantification_mode": signal_quantification_mode,
        "puncta_contour_intensity_enabled": bool(
            render_config.get("puncta_contour_intensity_enabled", True)
        ),
        "alternate_nucleus_detection_enabled": effective_alternate_enabled,
        "alternate_nucleus_detection_channel": effective_alternate_channel,
        "green_dot_split_enabled": bool(
            render_config.get(
                "green_dot_split_enabled",
                render_config.get("biorientation_green_split_enabled", True),
            )
        ),
        "green_dot_split_mode": normalize_dot_split_mode(
            render_config.get("green_dot_split_mode", DEFAULT_DOT_SPLIT_MODE)
        ),
        "red_dot_split_enabled": bool(
            render_config.get("red_dot_split_enabled", True)
        ),
        "red_dot_split_mode": normalize_dot_split_mode(
            render_config.get("red_dot_split_mode", DEFAULT_DOT_SPLIT_MODE)
        ),
    }


def load_cached_overlay_images(
    run_uuid: str,
    cell_id: int,
    render_config: dict[str, object],
) -> dict[str, np.ndarray]:
    """Load no-outline channel crops used as deterministic replay inputs."""

    image_stem = str(render_config["image_stem"])
    channel_config = {
        str(channel_name): int(channel_index)
        for channel_name, channel_index in dict(render_config.get("channel_config", {})).items()
    }
    segmented_dir = Path(settings.MEDIA_ROOT) / str(run_uuid) / "segmented"
    cached_images: dict[str, np.ndarray] = {}

    for channel_name in OVERLAY_BASE_CHANNELS:
        channel_index = channel_config.get(channel_name)
        if channel_index is None:
            continue
        image_path = segmented_dir / f"{image_stem}-{channel_index}-{cell_id}-no_outline.png"
        if not image_path.exists():
            continue
        with Image.open(image_path) as image:
            cached_images[channel_name] = np.array(image, copy=True)

    return cached_images


def render_overlay_images_for_cell(
    run_uuid: str,
    cell_stat: CellStatistics,
    render_config: dict[str, object],
    *,
    cached_images: dict[str, np.ndarray] | None = None,
) -> dict[str, Image.Image]:
    """Replay ``get_stats`` to render contour-on fluorescence overlays."""

    from core.views.segment_image import get_stats

    render_cp = clone_cell_statistics_for_overlay(cell_stat)
    images_to_use = cached_images if cached_images is not None else load_cached_overlay_images(
        run_uuid,
        int(cell_stat.cell_id),
        render_config,
    )
    overlay_conf = _build_overlay_conf(run_uuid, render_config)
    execution_plan = build_stats_execution_plan(
        render_config.get("selected_analysis", []),
        puncta_line_mode=render_config.get("puncta_line_mode"),
    )
    render_cp.properties = dict(render_cp.properties or {})
    render_cp.properties["stats_biorientation_red_min_distance_value"] = render_config.get(
        "stats_biorientation_red_min_distance_value",
        0.0,
    )
    render_cp.properties["stats_biorientation_red_min_distance_unit"] = render_config.get(
        "stats_biorientation_red_min_distance_unit",
        "px",
    )
    render_cp.properties["stats_biorientation_red_max_distance_value"] = render_config.get(
        "stats_biorientation_red_max_distance_value",
        37.0,
    )
    render_cp.properties["stats_biorientation_red_max_distance_unit"] = render_config.get(
        "stats_biorientation_red_max_distance_unit",
        "px",
    )
    render_cp.properties["stats_biorientation_collinearity_threshold"] = render_config.get(
        "biorientation_collinearity_threshold",
        DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX,
    )
    render_cp.properties["stats_green_dot_split_enabled"] = render_config.get(
        "green_dot_split_enabled",
        render_config.get("biorientation_green_split_enabled", True),
    )
    render_cp.properties["stats_green_dot_split_mode"] = normalize_dot_split_mode(
        render_config.get("green_dot_split_mode", DEFAULT_DOT_SPLIT_MODE)
    )
    render_cp.properties["stats_red_dot_split_enabled"] = render_config.get(
        "red_dot_split_enabled",
        True,
    )
    render_cp.properties["stats_red_dot_split_mode"] = normalize_dot_split_mode(
        render_config.get("red_dot_split_mode", DEFAULT_DOT_SPLIT_MODE)
    )
    render_cp.properties["signal_quantification_enabled"] = overlay_conf[
        "signal_quantification_enabled"
    ]
    render_cp.properties["signal_quantification_mode"] = overlay_conf[
        "signal_quantification_mode"
    ]
    render_cp.properties["puncta_contour_intensity_enabled"] = bool(
        render_config.get("puncta_contour_intensity_enabled", True)
    )
    render_cp.properties["alternate_nucleus_detection_enabled"] = overlay_conf[
        "alternate_nucleus_detection_enabled"
    ]
    render_cp.properties["alternate_nucleus_detection_channel"] = overlay_conf[
        "alternate_nucleus_detection_channel"
    ]
    render_cp.properties["nuclear_cell_pair_contour_mode"] = overlay_conf[
        "nuclear_cell_pair_contour_mode"
    ]
    debug_red, debug_green, debug_blue = get_stats(
        render_cp,
        overlay_conf,
        execution_plan,
        int(render_config.get("puncta_line_width_px", 1)),
        float(render_config.get("cen_dot_distance_value_used", 37.0)),
        float(render_config.get("cen_dot_proximity_radius", 13)),
        bool(render_config.get("green_contour_filter_enabled", False)),
        overlay_conf["alternate_nucleus_detection_enabled"],
        bool(
            render_config.get(
                "green_dot_split_enabled",
                render_config.get("biorientation_green_split_enabled", True),
            )
        ),
        normalize_dot_split_mode(
            render_config.get("green_dot_split_mode", DEFAULT_DOT_SPLIT_MODE)
        ),
        bool(render_config.get("red_dot_split_enabled", True)),
        normalize_dot_split_mode(
            render_config.get("red_dot_split_mode", DEFAULT_DOT_SPLIT_MODE)
        ),
        cached_images=images_to_use,
        alternate_detection_channel=overlay_conf["alternate_nucleus_detection_channel"],
        nuclear_cell_pair_contour_mode=overlay_conf["nuclear_cell_pair_contour_mode"],
    )
    return {
        "red": debug_red,
        "green": debug_green,
        "blue": debug_blue,
    }


def _atomic_save_overlay_cache_image(image: Image.Image, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(f"{destination.name}.{uuid4().hex}.tmp")
    try:
        save_png_image(image, temp_path, profile=PNG_PROFILE_ANALYSIS_FAST)
        os.replace(temp_path, destination)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                logger.debug("Could not remove temporary overlay cache file %s", temp_path)
    return destination


def persist_overlay_cache_images(
    run_uuid: str,
    cell_id: int,
    images: dict[str, Image.Image],
    *,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Write exact overlay cache PNGs using stable per-cell/channel names."""

    destination_dir = overlay_cache_dir(run_uuid)
    destination_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for channel, image in images.items():
        cache_path = overlay_cache_image_path(run_uuid, cell_id, channel)
        if cache_path.exists() and not overwrite:
            written[channel] = cache_path
            continue
        _atomic_save_overlay_cache_image(image, cache_path)
        written[channel] = cache_path
    return written


def persist_debug_overlay_exports(
    run_uuid: str,
    image_stem: str,
    cell_id: int,
    images: dict[str, Image.Image],
    *,
    overwrite: bool = True,
) -> dict[str, Path]:
    """Write optional legacy debug overlays for deployments that enable them."""

    written: dict[str, Path] = {}
    for channel, image in images.items():
        debug_path = build_legacy_debug_image_path(run_uuid, image_stem, cell_id, channel)
        if debug_path.exists() and not overwrite:
            written[channel] = debug_path
            continue
        save_png_image(image, debug_path, profile=PNG_PROFILE_ANALYSIS_FAST)
        written[channel] = debug_path
    return written


def _overlay_cache_is_complete(paths: dict[str, Path]) -> bool:
    return all(path.exists() for path in paths.values())


def _overlay_lock_is_stale(lock_path: Path) -> bool:
    try:
        age_seconds = max(time.time() - lock_path.stat().st_mtime, 0.0)
    except OSError:
        return False
    return age_seconds >= OVERLAY_CACHE_LOCK_STALE_SECONDS


def _log_overlay_cache_event(
    *,
    event: str,
    run_uuid: str,
    cell_id: int,
    channel: str,
    started_at: float,
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    logger.info(
        "Overlay cache event=%s run_uuid=%s cell_id=%s channel=%s elapsed_ms=%.2f",
        event,
        run_uuid,
        int(cell_id),
        channel,
        elapsed_ms,
    )


def _acquire_overlay_cache_lock(run_uuid: str, cell_id: int) -> tuple[Path, bool]:
    lock_path = overlay_cache_lock_path(run_uuid, cell_id)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    waited = False
    while True:
        try:
            fd = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError:
            waited = True
            if _overlay_lock_is_stale(lock_path):
                try:
                    lock_path.unlink()
                    logger.warning(
                        "Removed stale overlay cache lock run_uuid=%s cell_id=%s",
                        run_uuid,
                        int(cell_id),
                    )
                except FileNotFoundError:
                    continue
                except OSError:
                    time.sleep(OVERLAY_CACHE_LOCK_POLL_SECONDS)
                    continue
                continue
            time.sleep(OVERLAY_CACHE_LOCK_POLL_SECONDS)
            continue

        with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
            lock_file.write(f"pid={os.getpid()} started_at={time.time():.6f}\n")
        return lock_path, waited


def ensure_overlay_cache_images_for_cell(
    run_uuid: str,
    cell_id: int,
    *,
    cell_stat: CellStatistics | None = None,
    render_config: dict[str, object] | None = None,
    requested_channel: str = "green",
) -> dict[str, Path]:
    """Ensure every overlay channel cache exists for one cell.

    The function renders all overlay channels together because ``get_stats``
    produces the red/green/blue debug images in one replay. The lock keeps
    concurrent viewer requests from racing on the same cache files.
    """

    normalized_channel = normalize_overlay_channel(requested_channel)
    cache_paths = overlay_cache_image_paths_for_cell(run_uuid, cell_id)
    started_at = time.perf_counter()
    if _overlay_cache_is_complete(cache_paths):
        _log_overlay_cache_event(
            event="hit",
            run_uuid=run_uuid,
            cell_id=cell_id,
            channel=normalized_channel,
            started_at=started_at,
        )
        return cache_paths

    lock_path, waited = _acquire_overlay_cache_lock(run_uuid, cell_id)
    try:
        if _overlay_cache_is_complete(cache_paths):
            _log_overlay_cache_event(
                event="wait" if waited else "hit",
                run_uuid=run_uuid,
                cell_id=cell_id,
                channel=normalized_channel,
                started_at=started_at,
            )
            return cache_paths

        resolved_render_config = render_config or load_overlay_render_config(run_uuid)
        resolved_cell_stat = cell_stat
        if resolved_cell_stat is None:
            resolved_cell_stat = (
                CellStatistics.objects.select_related("segmented_image")
                .get(segmented_image_id=run_uuid, cell_id=cell_id)
            )

        rendered_images = render_overlay_images_for_cell(
            run_uuid,
            resolved_cell_stat,
            resolved_render_config,
        )
        persist_overlay_cache_images(
            run_uuid,
            cell_id,
            rendered_images,
            overwrite=False,
        )
        _log_overlay_cache_event(
            event="render",
            run_uuid=run_uuid,
            cell_id=cell_id,
            channel=normalized_channel,
            started_at=started_at,
        )
        return cache_paths
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            logger.debug("Could not remove overlay cache lock %s", lock_path)


def ensure_overlay_cache_image(
    run_uuid: str,
    cell_id: int,
    channel: str,
    *,
    cell_stat: CellStatistics | None = None,
    render_config: dict[str, object] | None = None,
) -> Path:
    """Return the exact overlay cache path for one requested channel."""

    normalized_channel = normalize_overlay_channel(channel)
    cache_path = overlay_cache_image_path(run_uuid, cell_id, normalized_channel)
    if cache_path.exists():
        return cache_path
    cache_paths = ensure_overlay_cache_images_for_cell(
        run_uuid,
        cell_id,
        cell_stat=cell_stat,
        render_config=render_config,
        requested_channel=normalized_channel,
    )
    return cache_paths[normalized_channel]
