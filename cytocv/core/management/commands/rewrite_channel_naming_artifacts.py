from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.channel_roles import (
    channel_display_label,
    normalize_channel_role,
)
from core.models import CellStatistics


CHANNEL_CONFIG_FILES = ("channel_config.json",)
OVERLAY_RENDER_CONFIG_FILENAME = "overlay-render-config.json"
OVERLAY_CHANNEL_SLUG_RENAMES = {
    "mcherry": "red",
    "gfp": "green",
    "dapi": "blue",
}
OVERLAY_DEBUG_LABEL_RENAMES = {
    "mCherry": "Red",
    "GFP": "Green",
    "DAPI": "Blue",
}
PLUGIN_RENAMES = {
    "MCherryLine": "PunctaDistance",
    "RedLineIntensity": "PunctaDistance",
    "GFPDot": "CENDot",
    "DAPI_NucleusIntensity": "BlueNucleusIntensity",
    "NuclearCellularIntensity": "NuclearCellPairIntensity",
}
JSON_KEY_RENAMES = {
    "mCherry_line_width": "red_line_width",
    "mCherryWidth": "redLineWidth",
    "mcherry_width": "red_line_width",
    "mcherry_width_unit": "red_line_width_unit",
    "stats_mcherry_width_unit": "stats_red_line_width_unit",
    "stats_mcherry_width_value": "stats_red_line_width_value",
    "gfp_distance": "cen_dot_distance",
    "gfp_distance_unit": "cen_dot_distance_unit",
    "stats_gfp_distance_unit": "stats_cen_dot_distance_unit",
    "stats_gfp_distance_value": "stats_cen_dot_distance_value",
    "gfp_threshold": "cen_dot_collinearity_threshold",
    "threshold": "cenDotCollinearityThreshold",
    "distance": "cenDotDistance",
    "gfpFilterEnabled": "greenContourFilterEnabled",
    "gfp_filter_enabled": "green_contour_filter_enabled",
    "alternateMCherryDetection": "alternateRedDetection",
    "alternate_mcherry_detection": "alternate_red_detection",
    "stats_mcherry_width_px": "stats_red_line_width_px",
    "stats_gfp_distance_px": "stats_cen_dot_distance_px",
    "stats_gfp_distance_threshold": "stats_cen_dot_distance_value",
    "stats_gfp_distance_mode": "stats_cen_dot_distance_mode",
    "red_line_width": "puncta_line_width",
    "redLineWidth": "punctaLineWidth",
    "red_line_width_unit": "puncta_line_width_unit",
    "stats_red_line_width_unit": "stats_puncta_line_width_unit",
    "stats_red_line_width_value": "stats_puncta_line_width_value",
    "stats_red_line_width_px": "stats_puncta_line_width_px",
    "distance": "puncta_distance",
    "line_green_intensity": "puncta_line_intensity",
    "green_to_red_distance_1": "distance_of_green_from_red_1",
    "green_to_red_distance_2": "distance_of_green_from_red_2",
    "green_to_red_distance_3": "distance_of_green_from_red_3",
    "cellular_intensity_sum": "cell_pair_intensity_sum",
    "cellular_intensity_sum_blue": "cell_pair_intensity_sum_blue",
    "nuclear_cellular_mode": "nuclear_cell_pair_mode",
    "nuclear_cellular_status": "nuclear_cell_pair_status",
    "nuclear_cellular_contour_channel": "nuclear_cell_pair_contour_channel",
    "nuclear_cellular_measurement_channel": "nuclear_cell_pair_measurement_channel",
    "nuclear_cellular_contour_source": "nuclear_cell_pair_contour_source",
}


def _rewrite_plugin_id(value: Any) -> Any:
    rewritten = value
    while rewritten in PLUGIN_RENAMES:
        next_value = PLUGIN_RENAMES[rewritten]
        if next_value == rewritten:
            break
        rewritten = next_value
    return rewritten


def _rewrite_json_key(key: str) -> str:
    rewritten = key
    while rewritten in JSON_KEY_RENAMES:
        next_key = JSON_KEY_RENAMES[rewritten]
        if next_key == rewritten:
            break
        rewritten = next_key
    return rewritten


def _rewrite_channel_role(value: Any) -> Any:
    normalized = normalize_channel_role(value)
    return normalized or value


def _rewrite_channel_display(value: Any) -> Any:
    normalized = normalize_channel_role(value)
    return channel_display_label(normalized) if normalized else value


def _rewrite_user_config_payload(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_rewrite_user_config_payload(item) for item in payload]
    if not isinstance(payload, dict):
        if isinstance(payload, str):
            return PLUGIN_RENAMES.get(payload, payload)
        return payload

    rewritten: dict[str, Any] = {}
    for key, value in payload.items():
        new_key = _rewrite_json_key(key)
        rewritten_value = _rewrite_user_config_payload(value)

        if new_key == "selected_plugins" and isinstance(rewritten_value, list):
            rewritten_value = [_rewrite_plugin_id(item) for item in rewritten_value]
        elif new_key in {"manual_required_channels", "required_channels"} and isinstance(
            rewritten_value,
            list,
        ):
            rewritten_value = [_rewrite_channel_role(item) for item in rewritten_value]
        elif new_key == "channel_config" and isinstance(rewritten_value, dict):
            rewritten_value = {
                _rewrite_channel_role(channel): index
                for channel, index in rewritten_value.items()
            }

        rewritten[new_key] = rewritten_value
    return rewritten


def _rewrite_overlay_render_config(payload: dict[str, Any]) -> dict[str, Any]:
    rewritten = _rewrite_user_config_payload(payload)
    channel_config = rewritten.get("channel_config")
    if isinstance(channel_config, dict):
        rewritten["channel_config"] = {
            _rewrite_channel_role(channel): index
            for channel, index in channel_config.items()
        }
    selected_analysis = rewritten.get("selected_analysis")
    if isinstance(selected_analysis, list):
        rewritten["selected_analysis"] = [_rewrite_plugin_id(item) for item in selected_analysis]
    return rewritten


def _rewrite_cell_properties(properties: dict[str, Any]) -> dict[str, Any]:
    rewritten = {}
    for key, value in properties.items():
        new_key = _rewrite_json_key(key)
        rewritten[new_key] = value

    for channel_key in (
        "nuclear_cell_pair_contour_channel",
        "nuclear_cell_pair_measurement_channel",
    ):
        if channel_key in rewritten:
            rewritten[channel_key] = _rewrite_channel_display(rewritten[channel_key])
    return rewritten


class Command(BaseCommand):
    help = "Rewrite saved run artifacts and stored JSON blobs to the generic channel naming scheme."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report planned rewrites without modifying files or database rows.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        media_root = Path(settings.MEDIA_ROOT)

        stats_rewritten = self._rewrite_cell_statistics(dry_run=dry_run)
        users_rewritten = self._rewrite_user_configs(dry_run=dry_run)
        files_rewritten = self._rewrite_run_artifacts(media_root, dry_run=dry_run)

        self.stdout.write(
            self.style.SUCCESS(
                f"Channel naming rewrite complete: stats={stats_rewritten}, users={users_rewritten}, files={files_rewritten}, dry_run={dry_run}"
            )
        )

    def _rewrite_cell_statistics(self, *, dry_run: bool) -> int:
        rewritten = 0
        for cell_stat in CellStatistics.objects.iterator():
            properties = dict(cell_stat.properties or {})
            if not properties:
                continue
            next_properties = _rewrite_cell_properties(properties)
            if next_properties == properties:
                continue
            rewritten += 1
            if not dry_run:
                cell_stat.properties = next_properties
                cell_stat.save(update_fields=["properties"])
        return rewritten

    def _rewrite_user_configs(self, *, dry_run: bool) -> int:
        rewritten = 0
        user_model = get_user_model()
        for user in user_model.objects.iterator():
            config = dict(user.config or {})
            next_config = _rewrite_user_config_payload(config)
            if next_config == config:
                continue
            rewritten += 1
            if not dry_run:
                user.config = next_config
                user.save(update_fields=["config"])
        return rewritten

    def _rewrite_run_artifacts(self, media_root: Path, *, dry_run: bool) -> int:
        rewritten = 0
        if not media_root.exists():
            return rewritten

        for run_dir in media_root.iterdir():
            if not run_dir.is_dir():
                continue

            for filename in CHANNEL_CONFIG_FILES:
                config_path = run_dir / filename
                if config_path.exists():
                    payload = json.loads(config_path.read_text(encoding="utf-8"))
                    next_payload = {
                        _rewrite_channel_role(channel): index
                        for channel, index in payload.items()
                    }
                    if next_payload != payload:
                        rewritten += 1
                        if not dry_run:
                            config_path.write_text(
                                json.dumps(next_payload, indent=2, sort_keys=True),
                                encoding="utf-8",
                            )

            overlay_render_path = run_dir / "segmented" / OVERLAY_RENDER_CONFIG_FILENAME
            if overlay_render_path.exists():
                payload = json.loads(overlay_render_path.read_text(encoding="utf-8"))
                next_payload = _rewrite_overlay_render_config(payload)
                if next_payload != payload:
                    rewritten += 1
                    if not dry_run:
                        overlay_render_path.write_text(
                            json.dumps(next_payload, indent=2, sort_keys=True),
                            encoding="utf-8",
                        )

            rewritten += self._rewrite_overlay_filenames(run_dir / "segmented", dry_run=dry_run)

        return rewritten

    def _rewrite_overlay_filenames(self, segmented_dir: Path, *, dry_run: bool) -> int:
        if not segmented_dir.exists():
            return 0

        rewritten = 0
        for path in segmented_dir.rglob("*.png"):
            name = path.name
            new_name = name

            cache_match = re.match(r"^(cell-\d+)-(mcherry|gfp|dapi)\.png$", name)
            if cache_match:
                new_name = f"{cache_match.group(1)}-{OVERLAY_CHANNEL_SLUG_RENAMES[cache_match.group(2)]}.png"

            debug_match = re.match(r"^(.+-\d+)-(mCherry|GFP|DAPI)_debug\.png$", name)
            if debug_match:
                new_name = f"{debug_match.group(1)}-{OVERLAY_DEBUG_LABEL_RENAMES[debug_match.group(2)]}_debug.png"

            if new_name == name:
                continue

            rewritten += 1
            if not dry_run:
                destination = path.with_name(new_name)
                if destination.exists():
                    destination.unlink()
                path.rename(destination)
        return rewritten
