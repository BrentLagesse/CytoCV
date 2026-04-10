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
    channel_display_label,
    channel_role_from_slug,
    channel_slug,
    normalize_channel_role,
)
from core.config import input_dir
from core.models import CellStatistics
from core.services.artifact_storage import PNG_PROFILE_ANALYSIS_FAST, save_png_image
from core.services.puncta_line_mode import (
    DEFAULT_PUNCTA_LINE_MODE,
    normalize_puncta_line_mode,
)
from core.stats_plugins import build_stats_execution_plan

logger = logging.getLogger(__name__)

OVERLAY_RENDER_SCHEMA_VERSION = 1
OVERLAY_RENDER_CONFIG_FILENAME = "overlay-render-config.json"
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
    if "gfp_threshold" in normalized and "cen_dot_collinearity_threshold" not in normalized:
        normalized["cen_dot_collinearity_threshold"] = normalized["gfp_threshold"]
    if "gfp_filter_enabled" in normalized and "green_contour_filter_enabled" not in normalized:
        normalized["green_contour_filter_enabled"] = normalized["gfp_filter_enabled"]
    if "alternate_mcherry_detection" in normalized and "alternate_red_detection" not in normalized:
        normalized["alternate_red_detection"] = normalized["alternate_mcherry_detection"]
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
    return Path(settings.MEDIA_ROOT) / str(run_uuid) / "segmented" / OVERLAY_RENDER_CONFIG_FILENAME


def overlay_cache_dir(run_uuid: str) -> Path:
    return Path(settings.MEDIA_ROOT) / str(run_uuid) / "segmented" / OVERLAY_CACHE_DIRNAME


def overlay_cache_image_path(run_uuid: str, cell_id: int, channel: str) -> Path:
    normalized_channel = normalize_overlay_channel(channel)
    return overlay_cache_dir(run_uuid) / f"cell-{cell_id}-{normalized_channel}.png"


def overlay_cache_image_paths_for_cell(run_uuid: str, cell_id: int) -> dict[str, Path]:
    return {
        channel: overlay_cache_image_path(run_uuid, cell_id, channel)
        for channel in OVERLAY_RENDER_CHANNELS
    }


def overlay_cache_lock_path(run_uuid: str, cell_id: int) -> Path:
    return overlay_cache_dir(run_uuid) / f"cell-{int(cell_id)}.lock"


def build_overlay_image_url(run_uuid: str, cell_id: int, channel: str) -> str:
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
    cen_dot_collinearity_threshold: int,
    green_contour_filter_enabled: bool,
    alternate_red_detection: bool,
    puncta_line_width_unit: str | None = None,
    cen_dot_distance_unit: str | None = None,
    cen_dot_proximity_radius: float | None = None,
    cen_dot_proximity_radius_unit: str | None = None,
) -> dict[str, object]:
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
        "puncta_line_width_px": int(puncta_line_width_px),
        "cen_dot_distance_value_used": float(cen_dot_distance_value_used),
        "cen_dot_collinearity_threshold": int(cen_dot_collinearity_threshold),
        "green_contour_filter_enabled": bool(green_contour_filter_enabled),
        "alternate_red_detection": bool(alternate_red_detection),
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
    destination = overlay_render_config_path(run_uuid)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(render_config, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return destination


def load_overlay_render_config(run_uuid: str) -> dict[str, object]:
    path = overlay_render_config_path(run_uuid)
    payload = _normalize_render_config_payload(
        json.loads(path.read_text(encoding="utf-8"))
    )
    if int(payload.get("schema_version", 0)) != OVERLAY_RENDER_SCHEMA_VERSION:
        raise ValueError(f"Unsupported overlay render schema for run {run_uuid}")
    return payload


def overlay_render_config_exists(run_uuid: str) -> bool:
    return overlay_render_config_path(run_uuid).exists()


def normalize_overlay_channel(channel: str) -> str:
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
    channel_label = OVERLAY_CHANNEL_LABELS[normalize_overlay_channel(channel)]
    return (
        Path(settings.MEDIA_ROOT)
        / str(run_uuid)
        / "segmented"
        / f"{image_stem}-{cell_id}-{channel_label}_debug.png"
    )


def find_legacy_debug_image_path(run_uuid: str, cell_id: int, channel: str) -> Path | None:
    normalized_channel = normalize_overlay_channel(channel)
    channel_label = OVERLAY_CHANNEL_LABELS[normalized_channel]
    segmented_dir = Path(settings.MEDIA_ROOT) / str(run_uuid) / "segmented"
    matches = sorted(segmented_dir.glob(f"*-{cell_id}-{channel_label}_debug.png"))
    if not matches:
        return None
    return matches[0]


def clone_cell_statistics_for_overlay(cell_stat: CellStatistics) -> CellStatistics:
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
        "nuclear_cell_pair_mode": str(render_config.get("nuclear_cell_pair_mode", "green_nucleus")),
        "green_contour_filter_enabled": bool(
            render_config.get("green_contour_filter_enabled", False)
        ),
        "alternate_red_detection": bool(
            render_config.get("alternate_red_detection", False)
        ),
    }


def load_cached_overlay_images(
    run_uuid: str,
    cell_id: int,
    render_config: dict[str, object],
) -> dict[str, np.ndarray]:
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
    from core.views.segment_image import get_stats

    render_cp = clone_cell_statistics_for_overlay(cell_stat)
    images_to_use = cached_images if cached_images is not None else load_cached_overlay_images(
        run_uuid,
        int(cell_stat.cell_id),
        render_config,
    )
    execution_plan = build_stats_execution_plan(render_config.get("selected_analysis", []))
    debug_red, debug_green, debug_blue = get_stats(
        render_cp,
        _build_overlay_conf(run_uuid, render_config),
        execution_plan,
        int(render_config.get("puncta_line_width_px", 1)),
        float(render_config.get("cen_dot_distance_value_used", 37.0)),
        int(render_config.get("cen_dot_collinearity_threshold", 66)),
        float(render_config.get("cen_dot_proximity_radius", 13)),
        bool(render_config.get("green_contour_filter_enabled", False)),
        bool(render_config.get("alternate_red_detection", False)),
        cached_images=images_to_use,
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
    normalized_channel = normalize_overlay_channel(channel)
    cache_paths = ensure_overlay_cache_images_for_cell(
        run_uuid,
        cell_id,
        cell_stat=cell_stat,
        render_config=render_config,
        requested_channel=normalized_channel,
    )
    return cache_paths[normalized_channel]
