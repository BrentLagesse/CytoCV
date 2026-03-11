"""Account area views for dashboard, settings, and preferences."""

from __future__ import annotations

import json
import math
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import UUID

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.template.response import TemplateResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django_tables2.export.export import TableExport

from accounts.preferences import (
    get_user_preferences,
    should_auto_save_experiments,
    update_user_preferences,
)
from core.config import get_channel_config_for_uuid
from core.models import CellStatistics, SegmentedImage, UploadedImage
from core.scale import get_scale_sidebar_payload
from core.stats_plugins import (
    ALWAYS_REQUIRED_CHANNELS,
    CHANNEL_INFO,
    CHANNEL_ORDER,
    PLUGIN_DEFINITIONS,
    PLUGIN_ORDER,
    build_plugin_ui_payload,
    build_requirement_summary,
    normalize_selected_plugins,
)
from core.tables import CellTable
from cytocv.settings import MEDIA_ROOT, MEDIA_URL

NUCLEAR_CELLULAR_MODES = {"green_nucleus", "red_nucleus"}
LENGTH_UNITS = {"px", "um"}


def _post_bool(request: HttpRequest, key: str) -> bool:
    return str(request.POST.get(key, "")).strip().lower() in {"1", "true", "on", "yes"}


def _parse_positive_int(raw_value: Any, default: int, minimum: int = 0) -> int:
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return default
    return value


def _parse_positive_float(raw_value: Any, default: float, minimum: float = 0) -> float:
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return default
    return value


def _normalize_unit(value: Any, default: str = "px") -> str:
    unit = str(value or "").strip().lower()
    if unit not in LENGTH_UNITS:
        return default
    return unit


def _normalize_nuclear_mode(value: Any, default: str = "green_nucleus") -> str:
    mode = str(value or "").strip()
    if mode not in NUCLEAR_CELLULAR_MODES:
        return default
    return mode


def _preferences_redirect(request: HttpRequest, section: str) -> HttpResponse:
    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(f"{reverse('preferences')}?section={section}")


def _extract_measurement_defaults(
    post_data: Any,
    defaults: dict[str, Any],
) -> dict[str, Any]:
    current_mcherry_width_unit = _normalize_unit(
        defaults.get("mcherry_width_unit"),
        default="px",
    )
    current_gfp_distance_unit = _normalize_unit(
        defaults.get("gfp_distance_unit"),
        default="px",
    )
    current_mcherry_width = _parse_positive_float(
        defaults.get("mcherry_width"),
        default=1,
        minimum=1 if current_mcherry_width_unit == "px" else 0,
    )
    current_gfp_distance = _parse_positive_float(
        defaults.get("gfp_distance"),
        default=37,
        minimum=0,
    )
    current_gfp_threshold = _parse_positive_int(
        defaults.get("gfp_threshold"),
        default=66,
        minimum=0,
    )
    current_microns_per_pixel = _parse_positive_float(
        defaults.get("microns_per_pixel"),
        default=0.1,
        minimum=0.0001,
    )
    current_use_metadata_scale = bool(defaults.get("use_metadata_scale", True))
    current_nuclear_mode = _normalize_nuclear_mode(
        defaults.get("nuclear_cellular_mode"),
        default="green_nucleus",
    )

    mcherry_width_unit = _normalize_unit(
        post_data.get("mcherry_width_unit"),
        default=current_mcherry_width_unit,
    )
    gfp_distance_unit = _normalize_unit(
        post_data.get("gfp_distance_unit"),
        default=current_gfp_distance_unit,
    )
    mcherry_minimum = 1 if mcherry_width_unit == "px" else 0
    raw_use_metadata_scale = post_data.get("use_metadata_scale")
    if raw_use_metadata_scale is None:
        use_metadata_scale = current_use_metadata_scale
    else:
        use_metadata_scale = str(raw_use_metadata_scale).strip().lower() in {
            "1",
            "true",
            "on",
            "yes",
        }
    return {
        "mcherry_width": _parse_positive_float(
            post_data.get("mcherry_width"),
            default=current_mcherry_width,
            minimum=mcherry_minimum,
        ),
        "gfp_distance": _parse_positive_float(
            post_data.get("gfp_distance"),
            default=current_gfp_distance,
            minimum=0,
        ),
        "gfp_threshold": _parse_positive_int(
            post_data.get("gfp_threshold"),
            default=current_gfp_threshold,
            minimum=0,
        ),
        "nuclear_cellular_mode": _normalize_nuclear_mode(
            post_data.get("nuclear_cellular_mode"),
            default=current_nuclear_mode,
        ),
        "mcherry_width_unit": mcherry_width_unit,
        "gfp_distance_unit": gfp_distance_unit,
        "microns_per_pixel": _parse_positive_float(
            post_data.get("microns_per_pixel"),
            default=current_microns_per_pixel,
            minimum=0.0001,
        ),
        "use_metadata_scale": use_metadata_scale,
    }


def _normalize_uuid_list(raw_values: Any) -> list[str]:
    if not isinstance(raw_values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        try:
            value_uuid = str(UUID(str(value)))
        except (TypeError, ValueError, AttributeError):
            return []
        if value_uuid in seen:
            continue
        seen.add(value_uuid)
        normalized.append(value_uuid)
    return normalized


def _media_path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return int(path.stat().st_size)
        except OSError:
            return 0

    total = 0
    try:
        for candidate in path.rglob("*"):
            if not candidate.is_file():
                continue
            try:
                total += int(candidate.stat().st_size)
            except OSError:
                continue
    except OSError:
        return total
    return total


def _recalculate_user_storage_usage(user: Any) -> None:
    if not getattr(user, "is_authenticated", False):
        return
    uuids = {
        str(value)
        for value in SegmentedImage.objects.filter(user=user).values_list("UUID", flat=True)
    }
    media_root = Path(MEDIA_ROOT)
    used_storage = 0
    for uuid_value in uuids:
        used_storage += _media_path_size(media_root / uuid_value)
        used_storage += _media_path_size(media_root / f"user_{uuid_value}")
    total_storage = max(int(getattr(user, "total_storage", 0) or 0), 0)
    user.used_storage = max(0, int(used_storage))
    user.available_storage = max(0, int(total_storage - user.used_storage))
    user.save(update_fields=["used_storage", "available_storage"])


def _build_cell_table_for_uuid(user: Any, uuid: str) -> CellTable:
    try:
        segmented_image = SegmentedImage.objects.get(user=user, UUID=uuid)
    except SegmentedImage.DoesNotExist:
        return CellTable(CellStatistics.objects.none(), intensity_mode=None)

    stats_qs = CellStatistics.objects.filter(segmented_image=segmented_image).order_by("cell_id")
    intensity_mode = _resolve_nuclear_cellular_mode(stats_qs)
    return CellTable(stats_qs, intensity_mode=intensity_mode)


def _resolve_nuclear_cellular_mode(stats_iterable: Any) -> str | None:
    modes = set()
    for stat in stats_iterable:
        props = stat.properties or {}
        mode = props.get("nuclear_cellular_mode")
        if mode in NUCLEAR_CELLULAR_MODES:
            modes.add(mode)
    return modes.pop() if len(modes) == 1 else None


def _serialize_cell_statistics(cell_stat: CellStatistics | None) -> dict[str, Any] | None:
    if not cell_stat:
        return None
    props = cell_stat.properties or {}
    return {
        "distance": cell_stat.distance,
        "line_gfp_intensity": cell_stat.line_gfp_intensity,
        "blue_contour_size": cell_stat.blue_contour_size,
        "red_contour_1_size": cell_stat.red_contour_1_size,
        "red_contour_2_size": cell_stat.red_contour_2_size,
        "red_contour_3_size": cell_stat.red_contour_3_size,
        "red_intensity_1": cell_stat.red_intensity_1,
        "red_intensity_2": cell_stat.red_intensity_2,
        "red_intensity_3": cell_stat.red_intensity_3,
        "green_intensity_1": cell_stat.green_intensity_1,
        "green_intensity_2": cell_stat.green_intensity_2,
        "green_intensity_3": cell_stat.green_intensity_3,
        "red_in_green_intensity_1": cell_stat.red_in_green_intensity_1,
        "red_in_green_intensity_2": cell_stat.red_in_green_intensity_2,
        "red_in_green_intensity_3": cell_stat.red_in_green_intensity_3,
        "green_in_green_intensity_1": cell_stat.green_in_green_intensity_1,
        "green_in_green_intensity_2": cell_stat.green_in_green_intensity_2,
        "green_in_green_intensity_3": cell_stat.green_in_green_intensity_3,
        "gfp_contour_1_size": cell_stat.gfp_contour_1_size,
        "gfp_contour_2_size": cell_stat.gfp_contour_2_size,
        "gfp_contour_3_size": cell_stat.gfp_contour_3_size,
        "gfp_to_mcherry_distance_1": cell_stat.gfp_to_mcherry_distance_1,
        "gfp_to_mcherry_distance_2": cell_stat.gfp_to_mcherry_distance_2,
        "gfp_to_mcherry_distance_3": cell_stat.gfp_to_mcherry_distance_3,
        "green_red_intensity_1": cell_stat.green_red_intensity_1,
        "green_red_intensity_2": cell_stat.green_red_intensity_2,
        "green_red_intensity_3": cell_stat.green_red_intensity_3,
        "nucleus_intensity_sum": cell_stat.nucleus_intensity_sum,
        "cellular_intensity_sum": cell_stat.cellular_intensity_sum,
        "cytoplasmic_intensity": cell_stat.cytoplasmic_intensity,
        "cellular_intensity_sum_DAPI": cell_stat.cellular_intensity_sum_DAPI,
        "nucleus_intensity_sum_DAPI": cell_stat.nucleus_intensity_sum_DAPI,
        "cytoplasmic_intensity_DAPI": cell_stat.cytoplasmic_intensity_DAPI,
        "nuclear_cellular_mode": props.get("nuclear_cellular_mode", "green_nucleus"),
        "nuclear_cellular_contour_channel": props.get(
            "nuclear_cellular_contour_channel",
            "GFP",
        ),
        "nuclear_cellular_measurement_channel": props.get(
            "nuclear_cellular_measurement_channel",
            "mCherry",
        ),
        "nuclear_cellular_status": props.get("nuclear_cellular_status", "unknown"),
        "category_GFP_dot": cell_stat.category_GFP_dot,
        "biorientation": cell_stat.biorientation,
    }


def _sanitize_for_json(value: Any) -> Any:
    """Convert nested values to strict JSON-safe equivalents."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_for_json(item) for item in value]
    return value


def _media_url_for_file(path: Path) -> str:
    media_root = Path(MEDIA_ROOT).resolve()
    try:
        relative = path.resolve().relative_to(media_root)
    except ValueError:
        return ""
    return f"{MEDIA_URL}{relative.as_posix()}"


def _scan_segmented_assets(segmented_dir: Path) -> tuple[
    dict[tuple[int, str], str],
    dict[tuple[int, int], str],
    dict[tuple[int, int], str],
]:
    debug_images: dict[tuple[int, str], str] = {}
    outlined_images: dict[tuple[int, int], str] = {}
    no_outline_images: dict[tuple[int, int], str] = {}
    if not segmented_dir.exists():
        return debug_images, outlined_images, no_outline_images

    debug_pattern = re.compile(r"^.+-(\d+)-(DAPI|GFP|mCherry)_debug\.png$")
    no_outline_pattern = re.compile(r"^.+-(\d+)-(\d+)-no_outline\.png$")
    outlined_pattern = re.compile(r"^.+-(\d+)-(\d+)\.png$")

    for path in segmented_dir.glob("*.png"):
        name = path.name
        debug_match = debug_pattern.match(name)
        if debug_match:
            cell_id = int(debug_match.group(1))
            channel_name = debug_match.group(2)
            debug_images[(cell_id, channel_name)] = _media_url_for_file(path)
            continue

        no_outline_match = no_outline_pattern.match(name)
        if no_outline_match:
            channel_idx = int(no_outline_match.group(1))
            cell_id = int(no_outline_match.group(2))
            no_outline_images[(channel_idx, cell_id)] = _media_url_for_file(path)
            continue

        outlined_match = outlined_pattern.match(name)
        if outlined_match:
            channel_idx = int(outlined_match.group(1))
            cell_id = int(outlined_match.group(2))
            outlined_images[(channel_idx, cell_id)] = _media_url_for_file(path)

    return debug_images, outlined_images, no_outline_images


def _scan_output_frames(output_dir: Path) -> dict[int, str]:
    frames: dict[int, str] = {}
    if not output_dir.exists():
        return frames
    frame_pattern = re.compile(r"^.+_frame_(\d+)\.png$")
    for path in output_dir.glob("*_frame_*.png"):
        match = frame_pattern.match(path.name)
        if not match:
            continue
        frame_idx = int(match.group(1))
        frames[frame_idx] = _media_url_for_file(path)
    return frames


def _build_dashboard_payload(user: Any) -> dict[str, Any]:
    segmented_images = list(
        SegmentedImage.objects.filter(user=user).order_by("-uploaded_date")
    )
    uuid_list = [str(image.UUID) for image in segmented_images]
    uploaded_map = {
        str(item.uuid): item
        for item in UploadedImage.objects.filter(user=user, uuid__in=uuid_list)
    }
    preferences = get_user_preferences(user)
    show_saved_file_channels = bool(preferences.get("show_saved_file_channels", True))
    show_saved_file_scales = bool(preferences.get("show_saved_file_scales", True))
    default_manual_scale = (
        preferences.get("experiment_defaults", {}).get("microns_per_pixel", 0.1)
    )

    files_data: dict[str, Any] = {}
    file_list: list[dict[str, Any]] = []
    first_table_uuid: str = ""
    cell_table = None

    channel_order = ["DIC", "DAPI", "mCherry", "GFP"]
    for segmented_image in segmented_images:
        uuid = str(segmented_image.UUID)
        uploaded = uploaded_map.get(uuid)
        if not uploaded:
            continue

        image_name = uploaded.name
        channel_config = get_channel_config_for_uuid(uuid)
        segmented_dir = Path(MEDIA_ROOT) / uuid / "segmented"
        output_dir = Path(MEDIA_ROOT) / uuid / "output"
        debug_images, outlined_images, no_outline_images = _scan_segmented_assets(
            segmented_dir
        )
        output_frames = _scan_output_frames(output_dir)
        detected_channels = [
            channel
            for channel, _ in sorted(channel_config.items(), key=lambda entry: entry[1])
        ]
        file_list.append(
            {
                "uuid": uuid,
                "name": image_name,
                "uploaded_date": segmented_image.uploaded_date,
                "num_cells": segmented_image.NumCells,
                "detected_channels": detected_channels,
                "scale": get_scale_sidebar_payload(
                    uploaded.scale_info,
                    manual_default=default_manual_scale,
                ),
            }
        )

        stats_qs = CellStatistics.objects.filter(segmented_image=segmented_image).order_by(
            "cell_id"
        )
        stats_by_id = {cell.cell_id: cell for cell in stats_qs}
        if stats_by_id and cell_table is None:
            first_table_uuid = uuid
            intensity_mode = _resolve_nuclear_cellular_mode(stats_by_id.values())
            cell_table = CellTable(stats_qs, intensity_mode=intensity_mode)

        if stats_by_id:
            cell_ids = sorted(stats_by_id.keys())
        else:
            cell_ids = sorted(
                int(path.stem.split("_", 1)[1])
                for path in segmented_dir.glob("cell_*.png")
                if path.stem.split("_", 1)[1].isdigit()
            )
        if not cell_ids:
            inferred_ids = sorted(
                {cell_id for (_, cell_id) in outlined_images.keys()}
                | {cell_id for (_, cell_id) in no_outline_images.keys()}
                | {cell_id for (cell_id, _) in debug_images.keys()}
            )
            cell_ids = inferred_ids

        cell_images: dict[str, list[str]] = {}
        statistics: dict[str, dict[str, Any] | None] = {}
        for cell_id in cell_ids:
            cell_images[str(cell_id)] = []
            for channel_name in channel_order:
                channel_index = channel_config.get(channel_name, channel_order.index(channel_name))
                outlined_url = ""
                if channel_name in {"mCherry", "GFP", "DAPI"}:
                    outlined_url = debug_images.get((cell_id, channel_name), "")
                if not outlined_url:
                    outlined_url = outlined_images.get((channel_index, cell_id), "")
                if not outlined_url:
                    outlined_url = next(
                        (
                            url
                            for (candidate_index, candidate_cell_id), url in outlined_images.items()
                            if candidate_cell_id == cell_id
                        ),
                        "",
                    )

                no_outline_url = no_outline_images.get((channel_index, cell_id), "")
                if not no_outline_url:
                    no_outline_url = next(
                        (
                            url
                            for (candidate_index, candidate_cell_id), url in no_outline_images.items()
                            if candidate_cell_id == cell_id
                        ),
                        "",
                    )
                if not no_outline_url:
                    no_outline_url = outlined_url

                cell_images[str(cell_id)].append(outlined_url)
                cell_images[str(cell_id)].append(no_outline_url)
            statistics[str(cell_id)] = _serialize_cell_statistics(
                stats_by_id.get(cell_id)
            )

        number_of_cells = max(len(cell_ids), int(segmented_image.NumCells or 0))
        if number_of_cells > 0 and not cell_ids:
            for cell_id in range(1, number_of_cells + 1):
                statistics[str(cell_id)] = None
                cell_images[str(cell_id)] = ["", "", "", "", "", "", "", ""]

        no_cells_warning = None
        if number_of_cells == 0:
            no_cells_warning = (
                "No segmented cells were produced for this file. "
                "Check channel mapping (DIC/DAPI/mCherry/GFP) and run the experiment again."
            )
        elif not output_frames:
            no_cells_warning = (
                "Preview assets were not found for this saved file. "
                "The statistics table is still available when data exists."
            )

        default_frame_idx = channel_config.get("mCherry", 0)
        main_image_url = output_frames.get(default_frame_idx) or output_frames.get(0)
        if not main_image_url and output_frames:
            first_frame_idx = sorted(output_frames.keys())[0]
            main_image_url = output_frames[first_frame_idx]

        files_data[uuid] = {
            "MainImagePath": main_image_url or "",
            "NumberOfCells": number_of_cells,
            "CellPairImages": cell_images,
            "Image_Name": image_name,
            "Statistics": statistics,
            "NoCellsWarning": no_cells_warning,
        }

    if cell_table is None:
        cell_table = CellTable(CellStatistics.objects.none(), intensity_mode=None)

    saved_file_count = len(file_list)
    stored_used_storage = max(int(getattr(user, "used_storage", 0) or 0), 0)
    if saved_file_count > 0 and stored_used_storage <= 0:
        _recalculate_user_storage_usage(user)
        user.refresh_from_db(fields=["used_storage", "total_storage", "available_storage"])
        stored_used_storage = max(int(getattr(user, "used_storage", 0) or 0), 0)

    total_storage = max(int(getattr(user, "total_storage", 0) or 0), 1)
    used_storage = stored_used_storage
    used_percentage = min(100, max(0, (used_storage / total_storage) * 100))
    remaining_storage = max(total_storage - used_storage, 0)
    average_file_size = 0.0
    additional_files_possible = 0
    max_files_at_current_average = saved_file_count
    file_capacity_projection_ready = False
    if saved_file_count > 0 and used_storage > 0:
        average_file_size = used_storage / saved_file_count
        if average_file_size > 0:
            file_capacity_projection_ready = True
            additional_files_possible = max(0, int(remaining_storage / average_file_size))
            max_files_at_current_average = saved_file_count + additional_files_possible
    files_data_json = json.dumps(_sanitize_for_json(files_data), allow_nan=False)

    return {
        "file_list": file_list,
        "files_data_json": files_data_json,
        "cell_table": cell_table,
        "table_uuid": first_table_uuid,
        "has_files": bool(file_list),
        "saved_file_count": saved_file_count,
        "max_files_at_current_average": max_files_at_current_average,
        "additional_files_possible": additional_files_possible,
        "file_capacity_projection_ready": file_capacity_projection_ready,
        "used_storage": used_storage,
        "total_storage": total_storage,
        "remaining_storage": remaining_storage,
        "used_storage_mb": used_storage / (1024 * 1024),
        "total_storage_gb": total_storage / (1024 * 1024 * 1024),
        "storage_percentage": used_percentage,
        "show_saved_file_channels": show_saved_file_channels,
        "show_saved_file_scales": show_saved_file_scales,
    }


def _safe_remove_media_path(path: Path) -> None:
    media_root = Path(MEDIA_ROOT).resolve()
    candidate = path.resolve()
    if candidate != media_root and media_root not in candidate.parents:
        return
    if candidate.is_file():
        candidate.unlink(missing_ok=True)
    elif candidate.is_dir():
        shutil.rmtree(candidate, ignore_errors=True)


def _delete_user_and_media(user: Any) -> None:
    uploaded_qs = UploadedImage.objects.filter(user=user)
    uploaded_uuids = [str(value) for value in uploaded_qs.values_list("uuid", flat=True)]

    segmented_by_uuid_qs = SegmentedImage.objects.filter(UUID__in=uploaded_uuids)
    segmented_owned_qs = SegmentedImage.objects.filter(user=user)
    segmented_uuids = {
        str(value) for value in segmented_owned_qs.values_list("UUID", flat=True)
    }
    segmented_uuids.update(str(value) for value in segmented_by_uuid_qs.values_list("UUID", flat=True))

    file_locations = [
        Path(MEDIA_ROOT) / str(value)
        for value in uploaded_qs.values_list("file_location", flat=True)
        if value
    ]
    file_locations.extend(
        Path(MEDIA_ROOT) / str(value)
        for value in segmented_by_uuid_qs.values_list("file_location", flat=True)
        if value
    )

    removable_dirs = set()
    for uuid in segmented_uuids.union(uploaded_uuids):
        removable_dirs.add(Path(MEDIA_ROOT) / uuid)
        removable_dirs.add(Path(MEDIA_ROOT) / f"user_{uuid}")

    with transaction.atomic():
        segmented_by_uuid_qs.delete()
        segmented_owned_qs.delete()
        user.delete()

    for path in sorted(file_locations, key=lambda item: len(item.parts), reverse=True):
        _safe_remove_media_path(path)
    for path in sorted(removable_dirs, key=lambda item: len(item.parts), reverse=True):
        _safe_remove_media_path(path)


def _delete_saved_files_for_user(user: Any, uuids: list[str]) -> list[str]:
    uuid_set = {str(value) for value in uuids}
    if not uuid_set:
        return []

    uploaded_qs = UploadedImage.objects.filter(user=user, uuid__in=uuid_set)
    deleted_names = list(uploaded_qs.values_list("name", flat=True))

    segmented_qs = SegmentedImage.objects.filter(user=user, UUID__in=uuid_set)
    file_locations = [
        Path(MEDIA_ROOT) / str(value)
        for value in uploaded_qs.values_list("file_location", flat=True)
        if value
    ]
    file_locations.extend(
        Path(MEDIA_ROOT) / str(value)
        for value in segmented_qs.values_list("file_location", flat=True)
        if value
    )

    removable_dirs = {
        Path(MEDIA_ROOT) / uuid_value
        for uuid_value in uuid_set
    }
    removable_dirs.update(Path(MEDIA_ROOT) / f"user_{uuid_value}" for uuid_value in uuid_set)

    with transaction.atomic():
        segmented_qs.delete()
        uploaded_qs.delete()

    for path in sorted(file_locations, key=lambda item: len(item.parts), reverse=True):
        _safe_remove_media_path(path)
    for path in sorted(removable_dirs, key=lambda item: len(item.parts), reverse=True):
        _safe_remove_media_path(path)

    _recalculate_user_storage_usage(user)
    return deleted_names


@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    export_format = request.GET.get("_export")
    export_uuid = str(request.GET.get("file_uuid") or "").strip()
    if TableExport.is_valid_format(export_format) and export_uuid:
        table = _build_cell_table_for_uuid(request.user, export_uuid)
        exporter = TableExport(export_format, table)
        return exporter.response(f"dashboard-{export_uuid}.{export_format}")

    context = _build_dashboard_payload(request.user)
    return TemplateResponse(request, "dashboard.html", context)


@login_required
@require_POST
def dashboard_bulk_delete_view(request: HttpRequest) -> HttpResponse:
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request payload."}, status=400)

    requested_uuids = _normalize_uuid_list(payload.get("uuids", []))
    if not requested_uuids:
        return JsonResponse({"error": "No valid files were selected."}, status=400)

    owned_uuids = {
        str(value)
        for value in UploadedImage.objects.filter(
            user=request.user,
            uuid__in=requested_uuids,
        ).values_list("uuid", flat=True)
    }
    if len(owned_uuids) != len(set(requested_uuids)):
        return JsonResponse(
            {"error": "One or more selected files are unavailable."},
            status=403,
        )

    deleted_names = _delete_saved_files_for_user(request.user, requested_uuids)
    context = _build_dashboard_payload(request.user)
    return JsonResponse(
        {
            "deleted_count": len(deleted_names),
            "deleted_names": deleted_names,
            "saved_file_count": context["saved_file_count"],
            "used_storage_mb": round(context["used_storage_mb"], 3),
            "storage_percentage": round(context["storage_percentage"], 2),
        }
    )


@login_required
@require_POST
def dashboard_channel_visibility_view(request: HttpRequest) -> HttpResponse:
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request payload."}, status=400)

    has_channels = "show_saved_file_channels" in payload
    has_scales = "show_saved_file_scales" in payload
    if not has_channels and not has_scales:
        return JsonResponse(
            {"error": "At least one visibility flag is required."},
            status=400,
        )

    show_saved_file_channels = payload.get("show_saved_file_channels")
    if has_channels and not isinstance(show_saved_file_channels, bool):
        return JsonResponse(
            {"error": "show_saved_file_channels must be a boolean."},
            status=400,
        )

    show_saved_file_scales = payload.get("show_saved_file_scales")
    if has_scales and not isinstance(show_saved_file_scales, bool):
        return JsonResponse(
            {"error": "show_saved_file_scales must be a boolean."},
            status=400,
        )

    current = get_user_preferences(request.user)
    next_payload = dict(current)
    if has_channels:
        next_payload["show_saved_file_channels"] = show_saved_file_channels
    if has_scales:
        next_payload["show_saved_file_scales"] = show_saved_file_scales
    updated = update_user_preferences(request.user, next_payload)
    return JsonResponse(
        {
            "show_saved_file_channels": bool(
                updated.get("show_saved_file_channels", True)
            ),
            "show_saved_file_scales": bool(
                updated.get("show_saved_file_scales", True)
            ),
        }
    )


@login_required
def account_settings_view(request: HttpRequest) -> HttpResponse:
    delete_error: str | None = None
    if request.method == "POST" and request.POST.get("action") == "delete_account":
        entered_email = (request.POST.get("confirm_email") or "").strip()
        expected_email = (request.user.email or "").strip()
        if not entered_email or entered_email.lower() != expected_email.lower():
            delete_error = "Incorrect email address entered."
        else:
            _delete_user_and_media(request.user)
            logout(request)
            messages.success(request, "Your account was deleted.")
            return redirect("homepage")

    full_name = " ".join(
        part for part in [request.user.first_name, request.user.last_name] if part
    ).strip()
    if not full_name:
        full_name = request.user.email

    return TemplateResponse(
        request,
        "settings.html",
        {
            "account_name": full_name,
            "email": request.user.email,
            "delete_error": delete_error,
            "open_delete_modal": bool(delete_error),
        },
    )


@login_required
def preferences_view(request: HttpRequest) -> HttpResponse:
    preferences = get_user_preferences(request.user)
    defaults = dict(preferences.get("experiment_defaults", {}))

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_plugin_defaults":
            selected_plugins = normalize_selected_plugins(
                request.POST.getlist("selected_plugins")
            )
            measurement_defaults = _extract_measurement_defaults(request.POST, defaults)
            next_defaults = dict(defaults)
            next_defaults["selected_plugins"] = selected_plugins
            next_defaults.update(measurement_defaults)
            next_payload = dict(preferences)
            next_payload["experiment_defaults"] = next_defaults
            preferences = update_user_preferences(request.user, next_payload)
            defaults = dict(preferences.get("experiment_defaults", {}))
            messages.success(request, "Plugin settings saved.")
            return _preferences_redirect(request, section="plugins")

        if action == "save_advanced_settings":
            module_enabled = _post_bool(request, "module_enabled")
            enforce_layer_count = module_enabled and _post_bool(
                request,
                "enforce_layer_count",
            )
            enforce_wavelengths = module_enabled and _post_bool(
                request,
                "enforce_wavelengths",
            )
            show_legacy_plugins = _post_bool(request, "show_legacy_plugins")
            gfp_filter_enabled = _post_bool(request, "gfp_filter_enabled")
            manual_required_channels = [
                channel
                for channel in request.POST.getlist("manual_required_channels")
                if channel in CHANNEL_ORDER and channel not in ALWAYS_REQUIRED_CHANNELS
            ]
            override_channels = {
                channel
                for channel in request.POST.getlist("override_required_channels")
                if channel in CHANNEL_ORDER and channel not in ALWAYS_REQUIRED_CHANNELS
            }
            measurement_defaults = _extract_measurement_defaults(request.POST, defaults)

            selected_plugins = normalize_selected_plugins(defaults.get("selected_plugins", []))
            removed_plugins: list[str] = []
            if override_channels:
                kept_plugins = []
                for plugin_id in selected_plugins:
                    required_channels = PLUGIN_DEFINITIONS[plugin_id].required_channels
                    if required_channels.intersection(override_channels):
                        removed_plugins.append(plugin_id)
                        continue
                    kept_plugins.append(plugin_id)
                selected_plugins = kept_plugins

            next_defaults = dict(defaults)
            next_defaults.update(
                {
                    "selected_plugins": selected_plugins,
                    "module_enabled": module_enabled,
                    "enforce_layer_count": enforce_layer_count,
                    "enforce_wavelengths": enforce_wavelengths,
                    "show_legacy_plugins": show_legacy_plugins,
                    "manual_required_channels": manual_required_channels,
                    "gfp_filter_enabled": gfp_filter_enabled,
                }
            )
            next_defaults.update(measurement_defaults)
            next_payload = dict(preferences)
            next_payload["experiment_defaults"] = next_defaults
            preferences = update_user_preferences(request.user, next_payload)
            defaults = dict(preferences.get("experiment_defaults", {}))
            if removed_plugins:
                removed_labels = ", ".join(
                    PLUGIN_DEFINITIONS[plugin_id].label for plugin_id in removed_plugins
                )
                messages.success(
                    request,
                    f"Advanced settings saved. Removed dependent plugins: {removed_labels}.",
                )
            else:
                messages.success(request, "Advanced settings saved.")
            return _preferences_redirect(request, section="advanced")

        if action == "save_behavior":
            next_payload = dict(preferences)
            next_payload["auto_save_experiments"] = _post_bool(
                request,
                "auto_save_experiments",
            )
            next_payload["show_saved_file_channels"] = _post_bool(
                request,
                "show_saved_file_channels",
            )
            next_payload["show_saved_file_scales"] = _post_bool(
                request,
                "show_saved_file_scales",
            )
            preferences = update_user_preferences(request.user, next_payload)
            if should_auto_save_experiments(request.user):
                messages.success(
                    request,
                    "Experiment autosave enabled. New runs will appear on your dashboard.",
                )
            else:
                messages.success(
                    request,
                    "Experiment autosave disabled. New runs will stay out of your dashboard history.",
                )
            return _preferences_redirect(request, section="saving")

    plugin_rows = []
    selected_plugins = set(defaults.get("selected_plugins", []))
    for plugin_id in PLUGIN_ORDER:
        definition = PLUGIN_DEFINITIONS[plugin_id]
        plugin_rows.append(
            {
                "id": plugin_id,
                "label": definition.label,
                "description": definition.description,
                "checked": plugin_id in selected_plugins,
                "is_legacy": definition.is_legacy,
                "required_channels": sorted(definition.required_channels, key=CHANNEL_ORDER.index),
            }
        )

    plugin_requirement_summary = build_requirement_summary(selected_plugins)
    plugin_dependency_payload = build_plugin_ui_payload()

    return TemplateResponse(
        request,
        "preferences.html",
        {
            "preferences": preferences,
            "plugins": plugin_rows,
            "channels": CHANNEL_ORDER,
            "channel_info": CHANNEL_INFO,
            "required_channels_by_plugins": plugin_requirement_summary["required_channels"],
            "plugin_dependency_payload_json": json.dumps(plugin_dependency_payload),
        },
    )


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """Compatibility alias for existing ``/profile/`` links."""
    return account_settings_view(request)
