"""Account area views for dashboard, settings, and preferences."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.template.response import TemplateResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django_tables2.export.export import TableExport

from accounts.preferences import (
    get_user_preferences,
    normalize_main_image_channel,
    MAIN_IMAGE_CHANNEL_SLUGS,
    resolve_initial_puncta_source_contour_count_filter,
    should_auto_save_experiments,
    update_user_preferences,
)
from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
    channel_display_label,
    channel_slug,
)
from core.channel_ordering import (
    DEFAULT_FALLBACK_CHANNEL_ORDER,
    normalize_channel_order,
)
from core.config import DEFAULT_CHANNEL_CONFIG, get_channel_config_for_uuid
from core.cell_types import (
    filter_statistics_by_cell_type,
    normalize_cell_inclusion_mode,
    normalize_cell_type_filter,
    resolve_effective_cell_type_filter,
)
from core.models import (
    CellStatistics,
    SegmentedImage,
    UploadedImage,
)
from core.services.artifact_storage import (
    get_user_storage_projection,
    refresh_user_storage_usage,
    sweep_user_run_artifacts,
)
from core.services.biorientation_config import (
    DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX,
)
from core.services.cell_statistics_payload import serialize_cell_statistics_payload
from core.services.combined_stat_export import (
    CombinedStatisticsExportError,
    build_combined_statistics_export_response,
)
from core.services.export_filenames import (
    build_statistics_export_filename,
)
from core.services.main_image_urls import build_main_image_paths
from core.services.overlay_rendering import (
    build_overlay_image_url,
    overlay_image_available,
)
from core.services.puncta_line_mode import (
    DEFAULT_PUNCTA_LINE_MODE,
    normalize_puncta_line_mode,
)
from core.services.dot_split import (
    normalize_dot_split_mode,
)
from core.services.nuclear_cell_pair_contour_mode import (
    DEFAULT_NUCLEAR_CELL_PAIR_CONTOUR_MODE,
    normalize_nuclear_cell_pair_contour_mode,
)
from core.services.signal_quantification import (
    resolve_signal_quantification_from_defaults,
    resolve_signal_quantification_selection,
)
from core.services.stat_export_selection import (
    ExportColumnSelectionError,
    export_exclude_columns,
    export_metric_scope,
    export_selection_config,
)
from core.services.stat_export_requests import (
    build_statistics_export_sources,
    normalize_uuid_list,
)
from core.services.result_view_payloads import (
    NUCLEAR_CELL_PAIR_MODES,
    RESULT_CHANNEL_ORDER,
    channel_config_payload,
    detected_channel_labels,
    resolve_cell_table_modes,
    sanitize_for_json,
)
from core.services.puncta_source_contour_count_filter import (
    filter_statistics_by_puncta_source_contour_count,
    normalize_puncta_source_contour_count_filter,
    resolve_effective_puncta_source_contour_count_filter,
)
from core.scale import (
    get_scale_context_payload,
    get_scale_sidebar_payload,
    normalize_spatial_stats_unit,
)
from core.stats_plugins import (
    ALWAYS_REQUIRED_CHANNELS,
    CHANNEL_INFO,
    CHANNEL_ORDER,
    PLUGIN_DEFINITIONS,
    PLUGIN_UI_ORDER,
    build_plugin_ui_payload,
    build_requirement_summary,
    expand_selected_plugins,
    normalize_selected_plugins,
)
from core.tables import CellTable
from cytocv.settings import MEDIA_ROOT, MEDIA_URL
from core.services.artifact_paths import normalize_media_field_path

LENGTH_UNITS = {"px", "um"}


def _post_bool(request: HttpRequest, key: str) -> bool:
    """Parse checkbox-style POST booleans used by preferences forms."""

    return str(request.POST.get(key, "")).strip().lower() in {"1", "true", "on", "yes"}


def _payload_bool(
    post_data: Any, key: str, *, default: bool = False, legacy_key: str | None = None
) -> bool:
    """Parse a boolean from current or legacy preference field names."""

    raw_value = post_data.get(key)
    if raw_value is None and legacy_key is not None:
        raw_value = post_data.get(legacy_key)
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in {"1", "true", "on", "yes"}


def _parse_positive_int(raw_value: Any, default: int, minimum: int = 0) -> int:
    """Return a bounded integer preference value or its existing default."""

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return default
    return value


def _parse_positive_float(raw_value: Any, default: float, minimum: float = 0) -> float:
    """Return a bounded float preference value or its existing default."""

    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return default
    return value


def _normalize_unit(value: Any, default: str = "px") -> str:
    """Normalize stored/requested length units for workflow defaults."""

    unit = str(value or "").strip().lower()
    if unit not in LENGTH_UNITS:
        return default
    return unit


def _normalize_nuclear_mode(value: Any, default: str = "green_nucleus") -> str:
    """Normalize nuclear/cell-pair mode names from preference forms."""

    mode = str(value or "").strip()
    if mode not in NUCLEAR_CELL_PAIR_MODES:
        return default
    return mode


def _normalize_nuclear_contour_mode(
    value: Any,
    default: str = DEFAULT_NUCLEAR_CELL_PAIR_CONTOUR_MODE,
) -> str:
    """Normalize the contour-source mode used by nuclear/cell-pair analysis."""

    return normalize_nuclear_cell_pair_contour_mode(value, default=default)


def _normalize_puncta_mode(value: Any, default: str = DEFAULT_PUNCTA_LINE_MODE) -> str:
    """Normalize puncta-line mode names from preference forms."""

    return normalize_puncta_line_mode(value, default=default)


def _preferences_redirect(request: HttpRequest, section: str) -> HttpResponse:
    """Return to a safe caller-provided URL or the workflow-defaults section."""

    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(f"{reverse('workflow_defaults')}?section={section}")


def _extract_measurement_defaults(
    post_data: Any,
    defaults: dict[str, Any],
) -> dict[str, Any]:
    """Merge posted workflow-default measurements with existing preferences."""

    # Existing preferences provide defaults for partial section saves, so unrelated
    # workflow-default controls do not reset when one form group is submitted.
    current_puncta_line_width_unit = _normalize_unit(
        defaults.get("puncta_line_width_unit", defaults.get("red_line_width_unit")),
        default="px",
    )
    current_cen_dot_distance_unit = _normalize_unit(
        defaults.get("cen_dot_distance_unit"),
        default="px",
    )
    current_biorientation_red_min_distance_unit = _normalize_unit(
        defaults.get("biorientation_red_min_distance_unit"),
        default="px",
    )
    current_biorientation_red_max_distance_unit = _normalize_unit(
        defaults.get("biorientation_red_max_distance_unit"),
        default="px",
    )
    current_puncta_line_width = _parse_positive_float(
        defaults.get("puncta_line_width", defaults.get("red_line_width")),
        default=1,
        minimum=1 if current_puncta_line_width_unit == "px" else 0,
    )
    current_cen_dot_distance = _parse_positive_float(
        defaults.get("cen_dot_distance"),
        default=37,
        minimum=0,
    )
    current_biorientation_red_min_distance = _parse_positive_float(
        defaults.get("biorientation_red_min_distance"),
        default=0,
        minimum=0,
    )
    current_biorientation_red_max_distance = _parse_positive_float(
        defaults.get("biorientation_red_max_distance"),
        default=37,
        minimum=0,
    )
    current_biorientation_collinearity_threshold = _parse_positive_int(
        defaults.get(
            "biorientation_collinearity_threshold",
            defaults.get("cen_dot_collinearity_threshold"),
        ),
        default=DEFAULT_BIORIENTATION_COLLINEARITY_THRESHOLD_PX,
        minimum=0,
    )
    current_microns_per_pixel = _parse_positive_float(
        defaults.get("microns_per_pixel"),
        default=0.1,
        minimum=0.0001,
    )
    current_use_metadata_scale = bool(defaults.get("use_metadata_scale", True))
    current_use_metadata_channel_order = bool(
        defaults.get("use_metadata_channel_order", True)
    )
    current_fallback_channel_order = normalize_channel_order(
        defaults.get("fallback_channel_order"),
        default=DEFAULT_FALLBACK_CHANNEL_ORDER,
    )
    current_spatial_stats_unit = normalize_spatial_stats_unit(
        defaults.get("spatial_stats_unit"),
        default="px",
    )
    current_puncta_mode = _normalize_puncta_mode(
        defaults.get("puncta_line_mode"),
        default=DEFAULT_PUNCTA_LINE_MODE,
    )
    current_nuclear_mode = _normalize_nuclear_mode(
        defaults.get("nuclear_cell_pair_mode", defaults.get("nuclear_cellular_mode")),
        default="green_nucleus",
    )
    current_nuclear_contour_mode = _normalize_nuclear_contour_mode(
        defaults.get("nuclear_cell_pair_contour_mode"),
    )
    current_cell_inclusion_mode = normalize_cell_inclusion_mode(
        defaults.get("cell_inclusion_mode")
    )
    current_legacy_nuclear_cell_pair = bool(
        defaults.get("use_legacy_nuclear_cell_pair_pipeline", False)
    )
    raw_legacy_nuclear_cell_pair = post_data.get(
        "use_legacy_nuclear_cell_pair_pipeline"
    )
    if raw_legacy_nuclear_cell_pair is None:
        use_legacy_nuclear_cell_pair_pipeline = current_legacy_nuclear_cell_pair
    else:
        use_legacy_nuclear_cell_pair_pipeline = str(
            raw_legacy_nuclear_cell_pair
        ).strip().lower() in {"1", "true", "on", "yes"}

    puncta_line_width_unit = _normalize_unit(
        post_data.get("puncta_line_width_unit", post_data.get("red_line_width_unit")),
        default=current_puncta_line_width_unit,
    )
    cen_dot_distance_unit = _normalize_unit(
        post_data.get("cen_dot_distance_unit"),
        default=current_cen_dot_distance_unit,
    )
    biorientation_red_min_distance_unit = _normalize_unit(
        post_data.get("biorientation_red_min_distance_unit"),
        default=current_biorientation_red_min_distance_unit,
    )
    biorientation_red_max_distance_unit = _normalize_unit(
        post_data.get("biorientation_red_max_distance_unit"),
        default=current_biorientation_red_max_distance_unit,
    )
    puncta_line_minimum = 1 if puncta_line_width_unit == "px" else 0
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
    raw_use_metadata_channel_order = post_data.get("use_metadata_channel_order")
    if raw_use_metadata_channel_order is None:
        use_metadata_channel_order = current_use_metadata_channel_order
    else:
        use_metadata_channel_order = str(
            raw_use_metadata_channel_order
        ).strip().lower() in {
            "1",
            "true",
            "on",
            "yes",
        }
    raw_fallback_channel_order = (
        post_data.getlist("fallback_channel_order")
        if hasattr(post_data, "getlist")
        else post_data.get("fallback_channel_order")
    )
    # Channel-order fallbacks are persisted as role names rather than layer indexes
    # because upload preparation resolves the actual source stack later.
    fallback_channel_order = normalize_channel_order(
        raw_fallback_channel_order,
        default=current_fallback_channel_order,
    )
    return {
        "puncta_line_width": _parse_positive_float(
            post_data.get("puncta_line_width", post_data.get("red_line_width")),
            default=current_puncta_line_width,
            minimum=puncta_line_minimum,
        ),
        "cen_dot_distance": _parse_positive_float(
            post_data.get("cen_dot_distance"),
            default=current_cen_dot_distance,
            minimum=0,
        ),
        "biorientation_red_min_distance": _parse_positive_float(
            post_data.get("biorientation_red_min_distance"),
            default=current_biorientation_red_min_distance,
            minimum=0,
        ),
        "biorientation_red_max_distance": _parse_positive_float(
            post_data.get("biorientation_red_max_distance"),
            default=current_biorientation_red_max_distance,
            minimum=0,
        ),
        "biorientation_collinearity_threshold": _parse_positive_int(
            post_data.get("biorientation_collinearity_threshold"),
            default=current_biorientation_collinearity_threshold,
            minimum=0,
        ),
        "puncta_line_mode": _normalize_puncta_mode(
            post_data.get("puncta_line_mode"),
            default=current_puncta_mode,
        ),
        "nuclear_cell_pair_mode": _normalize_nuclear_mode(
            post_data.get(
                "nuclear_cell_pair_mode", post_data.get("nuclear_cellular_mode")
            ),
            default=current_nuclear_mode,
        ),
        "nuclear_cell_pair_contour_mode": _normalize_nuclear_contour_mode(
            post_data.get("nuclear_cell_pair_contour_mode"),
            default=current_nuclear_contour_mode,
        ),
        "cell_inclusion_mode": normalize_cell_inclusion_mode(
            post_data.get("cell_inclusion_mode", current_cell_inclusion_mode)
        ),
        "use_legacy_nuclear_cell_pair_pipeline": use_legacy_nuclear_cell_pair_pipeline,
        "puncta_line_width_unit": puncta_line_width_unit,
        "cen_dot_distance_unit": cen_dot_distance_unit,
        "biorientation_red_min_distance_unit": biorientation_red_min_distance_unit,
        "biorientation_red_max_distance_unit": biorientation_red_max_distance_unit,
        "microns_per_pixel": _parse_positive_float(
            post_data.get("microns_per_pixel"),
            default=current_microns_per_pixel,
            minimum=0.0001,
        ),
        "use_metadata_scale": use_metadata_scale,
        "spatial_stats_unit": normalize_spatial_stats_unit(
            post_data.get("spatial_stats_unit"),
            default=current_spatial_stats_unit,
        ),
        "use_metadata_channel_order": use_metadata_channel_order,
        "fallback_channel_order": fallback_channel_order,
    }


def _channel_summary_meta(channel: str) -> str:
    """Return concise help text for the required-channel summary UI."""

    if channel == CHANNEL_ROLE_DIC:
        return "Brightfield morphology reference"
    if channel == CHANNEL_ROLE_BLUE:
        return "Blue fluorescence channel used for nucleus contour and legacy blue-channel metrics."
    if channel == CHANNEL_ROLE_RED:
        return "Red fluorescence signal channel"
    if channel == CHANNEL_ROLE_GREEN:
        return "Green fluorescence signal channel and Cen Dot Measurements."
    return "Channel data used in analysis"


def _resolve_required_channel_state(
    *,
    channel: str,
    stats_required: set[str],
    manual_required: set[str],
    module_enabled: bool,
    enforce_wavelengths: bool,
) -> dict[str, Any]:
    """Resolve one channel's required/paused/toggle state for preferences."""

    if channel in ALWAYS_REQUIRED_CHANNELS:
        # DIC remains locked because segmentation depends on a morphology channel
        # regardless of optional statistics plugins.
        return {
            "summary_label": "Always required",
            "summary_required": True,
            "summary_paused": False,
            "row_checked": True,
            "toggle_disabled": True,
            "row_disabled": True,
            "row_locked": True,
            "row_help": "Always required for segmentation.",
        }

    if channel in stats_required:
        # Plugin-required channels can be inspected but not unchecked while their
        # dependent plugins remain selected.
        return {
            "summary_label": "Required by stats",
            "summary_required": True,
            "summary_paused": False,
            "row_checked": True,
            "toggle_disabled": False,
            "row_disabled": False,
            "row_locked": True,
            "row_help": "Required because selected statistical plugins need this channel.",
        }

    if module_enabled and enforce_wavelengths:
        # All-channel enforcement makes every logical channel mandatory without
        # implying that a specific statistics plugin uses that channel.
        return {
            "summary_label": "Required by all-channels",
            "summary_required": True,
            "summary_paused": False,
            "row_checked": True,
            "toggle_disabled": True,
            "row_disabled": True,
            "row_locked": False,
            "row_help": 'Required because "Enforce Required Channels" is enabled.',
        }

    if module_enabled and channel in manual_required:
        return {
            "summary_label": "Required manually",
            "summary_required": True,
            "summary_paused": False,
            "row_checked": True,
            "toggle_disabled": False,
            "row_disabled": False,
            "row_locked": False,
            "row_help": "Optional advanced enforcement is enabled.",
        }

    if enforce_wavelengths:
        # Saved all-channel enforcement is paused, not discarded, when the
        # validation module is disabled.
        return {
            "summary_label": "Paused by all-channels",
            "summary_required": False,
            "summary_paused": True,
            "row_checked": True,
            "toggle_disabled": True,
            "row_disabled": True,
            "row_locked": False,
            "row_help": 'Paused because "Enforce Required Channels" is saved while the validation module is OFF.',
        }

    if channel in manual_required:
        return {
            "summary_label": "Paused manually",
            "summary_required": False,
            "summary_paused": True,
            "row_checked": True,
            "toggle_disabled": True,
            "row_disabled": True,
            "row_locked": False,
            "row_help": "Paused until the validation module is turned back on.",
        }

    return {
        "summary_label": "Optional",
        "summary_required": False,
        "summary_paused": False,
        "row_checked": False,
        "toggle_disabled": not module_enabled,
        "row_disabled": not module_enabled,
        "row_locked": False,
        "row_help": (
            "Optional."
            if module_enabled
            else "Optional. Turn the validation module on to edit."
        ),
    }


def _build_required_channel_rows(
    defaults: dict[str, Any],
    selected_plugins: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build channel rows plus plugin-derived requirement metadata."""

    requirement_summary = build_requirement_summary(selected_plugins)
    stats_required = set(requirement_summary["required_channels"])
    manual_required = {
        channel
        for channel in defaults.get("manual_required_channels", [])
        if channel in CHANNEL_ORDER and channel not in ALWAYS_REQUIRED_CHANNELS
    }
    module_enabled = bool(defaults.get("module_enabled", False))
    enforce_wavelengths = bool(defaults.get("enforce_wavelengths", False))

    rows: list[dict[str, Any]] = []
    for channel in CHANNEL_ORDER:
        state = _resolve_required_channel_state(
            channel=channel,
            stats_required=stats_required,
            manual_required=manual_required,
            module_enabled=module_enabled,
            enforce_wavelengths=enforce_wavelengths,
        )
        rows.append(
            {
                "channel": channel,
                "channel_label": channel_display_label(channel),
                "summary_meta": _channel_summary_meta(channel),
                "manual_selected": channel in manual_required,
                **state,
            }
        )

    return rows, requirement_summary


def _recalculate_user_storage_usage(user: Any) -> None:
    """Refresh cached quota usage after dashboard/account media mutations."""

    refresh_user_storage_usage(user)


def _build_cell_table_for_uuid(
    user: Any,
    uuid: str,
    *,
    spatial_stats_unit: str = "px",
    cell_type_filter: str = "all",
    puncta_source_contour_count_filter: str = "all",
) -> CellTable:
    """Build the saved-run table used by dashboard direct exports."""

    preferences = get_user_preferences(user)
    default_manual_scale = preferences.get("experiment_defaults", {}).get(
        "microns_per_pixel", 0.1
    )
    try:
        segmented_image = SegmentedImage.objects.get(user=user, UUID=uuid)
    except SegmentedImage.DoesNotExist:
        return CellTable(
            CellStatistics.objects.none(),
            intensity_mode=None,
            puncta_line_mode=None,
            spatial_stats_unit=spatial_stats_unit,
            scale_context=None,
        )

    uploaded = (
        UploadedImage.objects.filter(user=user, uuid=uuid).only("scale_info").first()
    )
    scale_context = get_scale_context_payload(
        getattr(uploaded, "scale_info", None),
        manual_default=default_manual_scale,
    )

    stats_qs = CellStatistics.objects.filter(segmented_image=segmented_image).order_by(
        "cell_id"
    )
    effective_cell_type_filter = resolve_effective_cell_type_filter(
        stats_qs,
        cell_type_filter,
    )
    effective_puncta_source_contour_count_filter = (
        resolve_effective_puncta_source_contour_count_filter(
            stats_qs,
            puncta_source_contour_count_filter,
        )
    )
    stats = filter_statistics_by_cell_type(stats_qs, effective_cell_type_filter)
    stats = filter_statistics_by_puncta_source_contour_count(
        stats,
        effective_puncta_source_contour_count_filter,
    )
    intensity_mode, puncta_line_mode = resolve_cell_table_modes(stats)
    return CellTable(
        stats,
        intensity_mode=intensity_mode,
        puncta_line_mode=puncta_line_mode,
        spatial_stats_unit=spatial_stats_unit,
        scale_context=scale_context,
    )


def _dashboard_available_export_uuid_set(user: Any) -> set[str]:
    """Return saved dashboard files that can participate in statistics export."""

    segmented_uuids = {
        str(value)
        for value in SegmentedImage.objects.filter(user=user).values_list(
            "UUID", flat=True
        )
    }
    if not segmented_uuids:
        return set()
    return {
        str(value)
        for value in UploadedImage.objects.filter(
            user=user,
            uuid__in=segmented_uuids,
        ).values_list("uuid", flat=True)
    }


def _serialize_cell_statistics(
    cell_stat: CellStatistics | None,
) -> dict[str, Any] | None:
    """Serialize one dashboard cell row with the shared viewer payload shape."""

    return serialize_cell_statistics_payload(cell_stat)


def _media_url_for_file(path: Path) -> str:
    """Return a MEDIA_URL for a file only when it is under MEDIA_ROOT."""

    media_root = Path(MEDIA_ROOT).resolve()
    try:
        relative = path.resolve().relative_to(media_root)
    except ValueError:
        # Asset scanners ignore paths outside MEDIA_ROOT rather than exposing
        # filesystem locations in serialized dashboard payloads.
        return ""
    return f"{MEDIA_URL}{relative.as_posix()}"


def _scan_segmented_assets(segmented_dir: Path) -> tuple[
    dict[tuple[int, str], str],
    dict[tuple[int, int], str],
    dict[tuple[int, int], str],
]:
    """Index segmented crop/debug assets by the conventions viewers expect."""

    debug_images: dict[tuple[int, str], str] = {}
    outlined_images: dict[tuple[int, int], str] = {}
    no_outline_images: dict[tuple[int, int], str] = {}
    if not segmented_dir.exists():
        return debug_images, outlined_images, no_outline_images

    debug_pattern = re.compile(r"^.+-(\d+)-(Blue|Green|Red)_debug\.png$")
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
    """Index preprocessed output frames by their logical channel index."""

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


def _build_dashboard_payload(user: Any, request: HttpRequest | None = None) -> dict[str, Any]:
    """Build the saved-run Dashboard payload and rendered context.

    Display and Dashboard share serialization primitives, but Dashboard only
    works with saved user-owned runs and therefore owns saved-file preferences,
    quota state, and dashboard-specific export/delete behavior.
    """

    segmented_images = list(
        SegmentedImage.objects.filter(user=user).order_by("-uploaded_date")
    )
    uuid_list = [str(image.UUID) for image in segmented_images]
    uploaded_map = {
        str(item.uuid): item
        for item in UploadedImage.objects.filter(user=user, uuid__in=uuid_list)
    }
    preferences = get_user_preferences(user)
    # Dashboard preferences are view-specific; display uses the same payload shape
    # but keeps transient-run ownership and saved warnings separate.
    show_saved_file_channels = bool(preferences.get("show_saved_file_channels", True))
    show_saved_file_scales = bool(preferences.get("show_saved_file_scales", True))
    sidebar_starts_open = bool(preferences.get("sidebar_starts_open", True))
    confirm_cell_deletion = bool(preferences.get("confirm_cell_deletion", True))
    confirm_multi_cell_deletion = bool(
        preferences.get("confirm_multi_cell_deletion", True)
    )
    default_manual_scale = preferences.get("experiment_defaults", {}).get(
        "microns_per_pixel", 0.1
    )
    default_spatial_stats_unit = normalize_spatial_stats_unit(
        preferences.get("experiment_defaults", {}).get("spatial_stats_unit"),
        default="px",
    )
    sidebar_spatial_stats_unit = normalize_spatial_stats_unit(
        preferences.get("sidebar_spatial_stats_unit"),
        default=default_spatial_stats_unit,
    )
    main_image_channel = normalize_main_image_channel(
        preferences.get("main_image_channel"),
        default="",
    )
    initial_puncta_source_contour_count_filter = (
        resolve_initial_puncta_source_contour_count_filter(request, preferences)
    )
    initial_cell_type_filter = normalize_cell_type_filter(
        request.GET.get("_cell_type") if request is not None else None
    )
    effective_initial_puncta_source_contour_count_filter = (
        initial_puncta_source_contour_count_filter
    )
    effective_initial_cell_type_filter = initial_cell_type_filter

    files_data: dict[str, Any] = {}
    file_list: list[dict[str, Any]] = []
    first_table_uuid: str = ""
    cell_table = None

    channel_order = RESULT_CHANNEL_ORDER
    for segmented_image in segmented_images:
        uuid = str(segmented_image.UUID)
        uploaded = uploaded_map.get(uuid)
        if not uploaded:
            # Segmented rows without a saved upload row are ignored on Dashboard;
            # cleanup handles stale artifacts separately.
            continue

        image_name = uploaded.name
        channel_config = get_channel_config_for_uuid(uuid)
        segmented_dir = Path(MEDIA_ROOT) / uuid / "segmented"
        output_dir = Path(MEDIA_ROOT) / uuid / "output"
        debug_images, outlined_images, no_outline_images = _scan_segmented_assets(
            segmented_dir
        )
        output_frames = _scan_output_frames(output_dir)
        detected_channels = detected_channel_labels(channel_config)
        # Sidebar scale payloads are compact display data; table conversions below
        # use the full scale context so exported units remain consistent.
        scale_payload = get_scale_sidebar_payload(
            uploaded.scale_info,
            manual_default=default_manual_scale,
        )
        scale_context = get_scale_context_payload(
            uploaded.scale_info,
            manual_default=default_manual_scale,
        )
        stats_qs = CellStatistics.objects.filter(
            segmented_image=segmented_image
        ).order_by("cell_id")
        stats_by_id = {cell.cell_id: cell for cell in stats_qs}
        if stats_by_id and cell_table is None:
            # The first file with statistics owns the initial table; later files are
            # serialized for the viewer and can be selected client-side.
            first_table_uuid = uuid
            effective_initial_cell_type_filter = resolve_effective_cell_type_filter(
                stats_qs,
                initial_cell_type_filter,
            )
            effective_initial_puncta_source_contour_count_filter = (
                resolve_effective_puncta_source_contour_count_filter(
                    stats_qs,
                    initial_puncta_source_contour_count_filter,
                )
            )
            initial_table_stats = filter_statistics_by_cell_type(
                stats_qs,
                effective_initial_cell_type_filter,
            )
            initial_table_stats = filter_statistics_by_puncta_source_contour_count(
                initial_table_stats,
                effective_initial_puncta_source_contour_count_filter,
            )
            intensity_mode, puncta_line_mode = resolve_cell_table_modes(
                initial_table_stats
            )
            cell_table = CellTable(
                initial_table_stats,
                intensity_mode=intensity_mode,
                puncta_line_mode=puncta_line_mode,
                spatial_stats_unit=sidebar_spatial_stats_unit,
                scale_context=scale_context,
            )

        if stats_by_id:
            cell_ids = sorted(stats_by_id.keys())
        else:
            cell_ids = sorted(
                int(path.stem.split("_", 1)[1])
                for path in segmented_dir.glob("cell_*.png")
                if path.stem.split("_", 1)[1].isdigit()
            )
        if not cell_ids:
            # Some restored artifacts may have images before statistics rows. Infer
            # IDs from asset names so the viewer can still present available crops.
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
            cell_stat = stats_by_id.get(cell_id)
            for channel_name in channel_order:
                channel_index = channel_config.get(
                    channel_name,
                    DEFAULT_CHANNEL_CONFIG.get(
                        channel_name, channel_order.index(channel_name)
                    ),
                )
                outlined_url = ""
                if (
                    channel_name
                    in {CHANNEL_ROLE_RED, CHANNEL_ROLE_GREEN, CHANNEL_ROLE_BLUE}
                    and cell_stat is not None
                    and overlay_image_available(uuid, cell_id, channel_name)
                ):
                    # Dashboard overlay URLs replay server-rendered contours instead
                    # of trusting stale debug PNGs when cache data is available.
                    outlined_url = build_overlay_image_url(uuid, cell_id, channel_name)
                else:
                    outlined_url = outlined_images.get((channel_index, cell_id), "")
                if not outlined_url:
                    # Legacy saved runs may have channel indexes that no longer
                    # match the current channel config; fall back by cell id so
                    # available outlines remain visible.
                    outlined_url = next(
                        (
                            url
                            for (
                                candidate_index,
                                candidate_cell_id,
                            ), url in outlined_images.items()
                            if candidate_cell_id == cell_id
                        ),
                        "",
                    )

                no_outline_url = no_outline_images.get((channel_index, cell_id), "")
                if not no_outline_url:
                    # The same by-cell fallback keeps raw crop previews available
                    # for restored runs with incomplete channel metadata.
                    no_outline_url = next(
                        (
                            url
                            for (
                                candidate_index,
                                candidate_cell_id,
                            ), url in no_outline_images.items()
                            if candidate_cell_id == cell_id
                        ),
                        "",
                    )
                if not no_outline_url:
                    no_outline_url = outlined_url

                cell_images[str(cell_id)].append(outlined_url)
                cell_images[str(cell_id)].append(no_outline_url)
            if cell_stat is not None:
                statistics[str(cell_id)] = _serialize_cell_statistics(cell_stat)

        number_of_cells = len(cell_ids)
        file_list.append(
            {
                "uuid": uuid,
                "name": image_name,
                "uploaded_date": segmented_image.uploaded_date,
                "num_cells": number_of_cells,
                "detected_channels": detected_channels,
                "scale": scale_payload,
            }
        )

        no_cells_warning = None
        if number_of_cells == 0:
            no_cells_warning = (
                "No segmented cells were produced for this file. "
                "Check channel mapping (DIC/Blue/Red/Green) and run the experiment again."
            )
        elif not output_frames:
            # Main-image paths are optional because statistics tables can still be
            # useful when preview frame artifacts were cleaned up or not produced.
            no_cells_warning = (
                "Preview images are unavailable for this saved file. "
                "The statistics table is still available when data exists."
            )

        main_image_paths = build_main_image_paths(
            uuid=uuid,
            image_name=image_name,
            channel_config=channel_config,
            available_frames=output_frames,
        )
        default_frame_idx = channel_config.get(
            CHANNEL_ROLE_RED,
            DEFAULT_CHANNEL_CONFIG.get(CHANNEL_ROLE_RED, 0),
        )
        main_image_url = output_frames.get(default_frame_idx) or output_frames.get(
            DEFAULT_CHANNEL_CONFIG.get(CHANNEL_ROLE_RED, 0)
        )
        if not main_image_url and output_frames:
            first_frame_idx = sorted(output_frames.keys())[0]
            main_image_url = output_frames[first_frame_idx]

        files_data[uuid] = {
            "MainImagePath": main_image_url or "",
            "MainImagePaths": main_image_paths,
            "NumberOfCells": number_of_cells,
            "CellPairImages": cell_images,
            "Image_Name": image_name,
            "ScaleContext": scale_context,
            "ChannelConfig": channel_config_payload(channel_config),
            "Statistics": statistics,
            "NoCellsWarning": no_cells_warning,
        }

    if cell_table is None:
        # Empty dashboards still receive a table instance so the template and
        # static table/export code can use a single rendering path.
        cell_table = CellTable(
            CellStatistics.objects.none(),
            intensity_mode=None,
            puncta_line_mode=None,
            spatial_stats_unit=sidebar_spatial_stats_unit,
            scale_context=None,
        )

    saved_file_count = len(file_list)
    storage_projection = get_user_storage_projection(user)
    # Capacity projections are advisory UI values; quota enforcement remains in
    # artifact_storage when a save/delete action is attempted.
    total_storage = max(int(storage_projection.get("total_storage", 0) or 0), 1)
    used_storage = max(int(storage_projection.get("used_storage", 0) or 0), 0)
    used_percentage = min(100, max(0, (used_storage / total_storage) * 100))
    remaining_storage = max(int(storage_projection.get("available_storage", 0) or 0), 0)
    average_file_size = float(
        storage_projection.get("average_saved_run_bytes", 0.0) or 0.0
    )
    additional_files_possible = max(
        int(storage_projection.get("additional_files_possible", 0) or 0),
        0,
    )
    max_files_at_current_average = saved_file_count
    file_capacity_projection_ready = bool(
        storage_projection.get("projection_ready", False)
    )
    if file_capacity_projection_ready:
        max_files_at_current_average = saved_file_count + additional_files_possible
    files_data_json = json.dumps(sanitize_for_json(files_data), allow_nan=False)

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
        "sidebar_starts_open": sidebar_starts_open,
        "confirm_cell_deletion": confirm_cell_deletion,
        "confirm_multi_cell_deletion": confirm_multi_cell_deletion,
        "default_spatial_stats_unit": default_spatial_stats_unit,
        "sidebar_spatial_stats_unit": sidebar_spatial_stats_unit,
        "main_image_channel": main_image_channel,
        "cell_type_filter": effective_initial_cell_type_filter,
        "puncta_source_contour_count_filter": effective_initial_puncta_source_contour_count_filter,
        "export_selection_config": export_selection_config(),
    }


def _safe_remove_media_path(path: Path) -> None:
    """Remove media only after confirming it stays under MEDIA_ROOT."""

    media_root = Path(MEDIA_ROOT).resolve()
    candidate = path.resolve()
    if candidate != media_root and media_root not in candidate.parents:
        return
    if candidate.is_file():
        candidate.unlink(missing_ok=True)
    elif candidate.is_dir():
        shutil.rmtree(candidate, ignore_errors=True)


def _delete_user_and_media(user: Any) -> None:
    """Delete an account and the media namespaces it owns."""

    # Capture all owned upload UUIDs before deleting the user so both direct
    # uploads and segmented rows reachable only by UUID can be cleaned afterward.
    uploaded_qs = UploadedImage.objects.filter(user=user)
    uploaded_uuids = [
        str(value) for value in uploaded_qs.values_list("uuid", flat=True)
    ]

    segmented_by_uuid_qs = SegmentedImage.objects.filter(UUID__in=uploaded_uuids)
    segmented_owned_qs = SegmentedImage.objects.filter(user=user)
    segmented_uuids = {
        str(value) for value in segmented_owned_qs.values_list("UUID", flat=True)
    }
    segmented_uuids.update(
        str(value) for value in segmented_by_uuid_qs.values_list("UUID", flat=True)
    )

    file_locations = [
        path
        for value in uploaded_qs.values_list("file_location", flat=True)
        if (path := normalize_media_field_path(value)) is not None
    ]
    file_locations.extend(
        path
        for value in segmented_by_uuid_qs.values_list("file_location", flat=True)
        if (path := normalize_media_field_path(value)) is not None
    )

    removable_dirs = set()
    # Remove both shared run namespaces and user-scoped artifact namespaces; old
    # experiments can have files in either location depending on save history.
    for uuid in segmented_uuids.union(uploaded_uuids):
        removable_dirs.add(Path(MEDIA_ROOT) / uuid)
        removable_dirs.add(Path(MEDIA_ROOT) / f"user_{uuid}")

    with transaction.atomic():
        # Database ownership is removed before files so a failed filesystem cleanup
        # cannot leave an active account pointing at partially deleted media.
        segmented_by_uuid_qs.delete()
        segmented_owned_qs.delete()
        user.delete()

    # Filesystem cleanup happens after the database transaction because media
    # deletion cannot roll back and should not leave active rows pointing at gone files.
    for path in sorted(file_locations, key=lambda item: len(item.parts), reverse=True):
        _safe_remove_media_path(path)
    for path in sorted(removable_dirs, key=lambda item: len(item.parts), reverse=True):
        _safe_remove_media_path(path)


def _delete_saved_files_for_user(user: Any, uuids: list[str]) -> list[str]:
    """Delete saved dashboard files and their run/user media directories."""

    uuid_set = {str(value) for value in uuids}
    if not uuid_set:
        return []

    # Dashboard deletion is scoped through UploadedImage ownership first; the UI
    # treats missing ownership as a stale selection instead of a partial delete.
    uploaded_qs = UploadedImage.objects.filter(user=user, uuid__in=uuid_set)
    deleted_names = list(uploaded_qs.values_list("name", flat=True))

    segmented_qs = SegmentedImage.objects.filter(user=user, UUID__in=uuid_set)
    file_locations = [
        path
        for value in uploaded_qs.values_list("file_location", flat=True)
        if (path := normalize_media_field_path(value)) is not None
    ]
    file_locations.extend(
        path
        for value in segmented_qs.values_list("file_location", flat=True)
        if (path := normalize_media_field_path(value)) is not None
    )

    removable_dirs = {Path(MEDIA_ROOT) / uuid_value for uuid_value in uuid_set}
    removable_dirs.update(
        Path(MEDIA_ROOT) / f"user_{uuid_value}" for uuid_value in uuid_set
    )

    with transaction.atomic():
        # Delete related database rows together so saved-file counts never observe
        # a segmented row without its uploaded source, or the reverse.
        segmented_qs.delete()
        uploaded_qs.delete()

    # Media removal is best-effort and sorted deepest-first to avoid deleting a
    # parent directory before a normalized field path inside it is checked.
    for path in sorted(file_locations, key=lambda item: len(item.parts), reverse=True):
        _safe_remove_media_path(path)
    for path in sorted(removable_dirs, key=lambda item: len(item.parts), reverse=True):
        _safe_remove_media_path(path)

    # Recalculate after deletion so dashboard quota cards and subsequent save
    # checks use the filesystem state that remains after cleanup.
    _recalculate_user_storage_usage(user)
    return deleted_names


@login_required
@never_cache
def dashboard_view(request: HttpRequest) -> HttpResponse:
    """Render the saved-run Dashboard or direct single-file table export."""

    # The dashboard is the retained-file view, so it can safely sweep stale saved
    # artifacts while protecting transient session runs still in display flows.
    cleanup_summary = sweep_user_run_artifacts(
        request.user,
        protected_uuids=request.session.get("transient_experiment_uuids", []),
    )
    if cleanup_summary["cleaned_saved_runs"]:
        _recalculate_user_storage_usage(request.user)

    export_format = request.GET.get("_export")
    export_uuid = str(request.GET.get("file_uuid") or "").strip()
    export_unit = normalize_spatial_stats_unit(request.GET.get("_unit"), default="px")
    if TableExport.is_valid_format(export_format) and export_uuid:
        # Single-file export uses the same column-selection contract as the modal,
        # but ownership is enforced by the table builder below.
        raw_columns = request.GET.getlist("_columns")
        columns_present = "_columns" in request.GET
        try:
            exclude_columns = export_exclude_columns(
                raw_columns,
                columns_present=columns_present,
            )
            metric_scope = export_metric_scope(
                raw_columns,
                columns_present=columns_present,
            )
        except ExportColumnSelectionError as exc:
            return HttpResponse(str(exc), status=400)
        table = _build_cell_table_for_uuid(
            request.user,
            export_uuid,
            spatial_stats_unit=export_unit,
            cell_type_filter=request.GET.get("_cell_type"),
            puncta_source_contour_count_filter=request.GET.get(
                "_puncta_source_contour_count",
                request.GET.get("_red_contour_count"),
            ),
        )
        download_name = build_statistics_export_filename(
            scope=metric_scope,
            file_count=1,
            export_format=export_format,
        )
        exporter = TableExport(
            export_format,
            table,
            exclude_columns=exclude_columns,
        )
        return exporter.response(download_name)

    context = _build_dashboard_payload(request.user, request=request)
    return TemplateResponse(request, "dashboard.html", context)


@login_required
@require_POST
def dashboard_bulk_delete_view(request: HttpRequest) -> HttpResponse:
    """Delete selected saved dashboard files and return refreshed quota state."""

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Your request could not be processed. Please try again."},
            status=400,
        )

    requested_uuids = normalize_uuid_list(payload.get("uuids", []))
    if not requested_uuids:
        return JsonResponse(
            {"error": "Select at least one saved file to continue."},
            status=400,
        )

    # Reject the whole request when any UUID is not currently owned. This keeps
    # stale browser selections from deleting a different subset than the user saw.
    owned_uuids = {
        # Require ownership through UploadedImage before deleting rows or media.
        str(value)
        for value in UploadedImage.objects.filter(
            user=request.user,
            uuid__in=requested_uuids,
        ).values_list("uuid", flat=True)
    }
    if len(owned_uuids) != len(set(requested_uuids)):
        return JsonResponse(
            {
                "error": "One or more selected files are no longer available. Refresh and try again."
            },
            status=403,
        )

    deleted_names = _delete_saved_files_for_user(request.user, requested_uuids)
    # Rebuild the dashboard payload after deletion so response counters match the
    # same serializer used for a full page refresh.
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
def dashboard_bulk_export_view(request: HttpRequest) -> HttpResponse:
    """Return a combined export for selected saved dashboard files."""

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Your request could not be processed. Please try again."},
            status=400,
        )

    requested_uuids = normalize_uuid_list(payload.get("uuids", []))
    if not requested_uuids:
        return JsonResponse(
            {"error": "Select at least one saved file to continue."},
            status=400,
        )

    uploaded_map = {
        str(item.uuid): item
        for item in UploadedImage.objects.filter(
            user=request.user,
            uuid__in=requested_uuids,
        )
    }
    segmented_map = {
        str(item.UUID): item
        for item in SegmentedImage.objects.filter(
            user=request.user,
            UUID__in=requested_uuids,
        )
    }
    if len(uploaded_map) != len(set(requested_uuids)) or len(segmented_map) != len(
        set(requested_uuids)
    ):
        # Keep the error generic so missing and unauthorized UUIDs are not
        # distinguishable to the caller.
        return JsonResponse(
            {
                "error": "One or more selected files are no longer available. Refresh and try again."
            },
            status=403,
        )

    preferences = get_user_preferences(request.user)
    default_manual_scale = preferences.get("experiment_defaults", {}).get(
        "microns_per_pixel", 0.1
    )
    sources = build_statistics_export_sources(
        requested_uuids,
        uploaded_map=uploaded_map,
        segmented_map=segmented_map,
    )
    try:
        return build_combined_statistics_export_response(
            sources,
            export_format=str(payload.get("_export") or ""),
            raw_columns=payload.get("_columns"),
            spatial_stats_unit=str(payload.get("_unit") or "px"),
            default_manual_scale=default_manual_scale,
            cell_type_filter=payload.get("_cell_type"),
            puncta_source_contour_count_filter=payload.get(
                "_puncta_source_contour_count",
                payload.get("_red_contour_count"),
            ),
        )
    except (CombinedStatisticsExportError, ExportColumnSelectionError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@login_required
@require_POST
def dashboard_channel_visibility_view(request: HttpRequest) -> HttpResponse:
    """Persist Dashboard viewer preferences from the static page controller."""

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Your request could not be processed. Please try again."},
            status=400,
        )

    has_channels = "show_saved_file_channels" in payload
    has_scales = "show_saved_file_scales" in payload
    has_sidebar_unit = "sidebar_spatial_stats_unit" in payload
    has_main_image_channel = "main_image_channel" in payload
    # The endpoint supports partial preference updates because separate dashboard
    # controls post independently from the static page controller.
    if (
        not has_channels
        and not has_scales
        and not has_sidebar_unit
        and not has_main_image_channel
    ):
        return JsonResponse(
            {"error": "At least one preference is required."},
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

    sidebar_spatial_stats_unit = normalize_spatial_stats_unit(
        payload.get("sidebar_spatial_stats_unit"),
        default="px",
    )
    if has_sidebar_unit and sidebar_spatial_stats_unit != payload.get(
        "sidebar_spatial_stats_unit"
    ):
        return JsonResponse(
            {"error": "sidebar_spatial_stats_unit must be 'px' or 'um'."},
            status=400,
        )

    raw_main_image_channel = payload.get("main_image_channel")
    main_image_channel = normalize_main_image_channel(
        raw_main_image_channel, default=""
    )
    if has_main_image_channel and main_image_channel not in MAIN_IMAGE_CHANNEL_SLUGS:
        return JsonResponse(
            {
                "error": "main_image_channel must be one of: dic, blue, red, green.",
            },
            status=400,
        )

    current = get_user_preferences(request.user)
    next_payload = dict(current)
    if has_channels:
        next_payload["show_saved_file_channels"] = show_saved_file_channels
    if has_scales:
        next_payload["show_saved_file_scales"] = show_saved_file_scales
    if has_sidebar_unit:
        next_payload["sidebar_spatial_stats_unit"] = sidebar_spatial_stats_unit
    if has_main_image_channel:
        next_payload["main_image_channel"] = main_image_channel
    updated = update_user_preferences(request.user, next_payload)
    return JsonResponse(
        {
            "show_saved_file_channels": bool(
                updated.get("show_saved_file_channels", True)
            ),
            "show_saved_file_scales": bool(updated.get("show_saved_file_scales", True)),
            "sidebar_spatial_stats_unit": normalize_spatial_stats_unit(
                updated.get("sidebar_spatial_stats_unit"),
                default=normalize_spatial_stats_unit(
                    updated.get("experiment_defaults", {}).get("spatial_stats_unit"),
                    default="px",
                ),
            ),
            "main_image_channel": normalize_main_image_channel(
                updated.get("main_image_channel"),
                default="",
            ),
        }
    )


@login_required
def account_settings_view(request: HttpRequest) -> HttpResponse:
    """Render account settings and handle explicit account deletion."""

    delete_error: str | None = None
    if request.method == "POST" and request.POST.get("action") == "delete_account":
        # Email confirmation is case-insensitive, but the response stays generic
        # enough to avoid revealing anything beyond the signed-in user's account.
        entered_email = (request.POST.get("confirm_email") or "").strip()
        expected_email = (request.user.email or "").strip()
        if not entered_email or entered_email.lower() != expected_email.lower():
            delete_error = "Incorrect email address entered."
        else:
            _delete_user_and_media(request.user)
            logout(request)
            messages.success(request, "Your account was deleted.")
            return redirect("home")

    full_name = " ".join(
        part for part in [request.user.first_name, request.user.last_name] if part
    ).strip()
    if not full_name:
        full_name = request.user.email

    return TemplateResponse(
        request,
        "account_settings.html",
        {
            "account_name": full_name,
            "email": request.user.email,
            "delete_error": delete_error,
            "open_delete_modal": bool(delete_error),
        },
    )


@login_required
def preferences_view(request: HttpRequest) -> HttpResponse:
    """Render and persist workflow defaults used by new experiment uploads."""

    preferences = get_user_preferences(request.user)
    defaults = dict(preferences.get("experiment_defaults", {}))

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_plugin_defaults":
            # Plugin defaults are saved as configured plugins plus derived
            # visibility/mode fields so new experiments do not have to infer from
            # legacy plugin lists on every request.
            selected_plugins = expand_selected_plugins(
                request.POST.getlist("selected_plugins")
            )
            measurement_defaults = _extract_measurement_defaults(request.POST, defaults)
            green_dot_split_enabled = _payload_bool(
                request.POST,
                "green_dot_split_enabled",
                default=bool(defaults.get("green_dot_split_enabled", True)),
                legacy_key="biorientation_green_split_enabled",
            )
            green_dot_split_mode = normalize_dot_split_mode(
                request.POST.get(
                    "green_dot_split_mode",
                    defaults.get("green_dot_split_mode"),
                )
            )
            red_dot_split_enabled = _payload_bool(
                request.POST,
                "red_dot_split_enabled",
                default=bool(defaults.get("red_dot_split_enabled", True)),
            )
            red_dot_split_mode = normalize_dot_split_mode(
                request.POST.get(
                    "red_dot_split_mode",
                    defaults.get("red_dot_split_mode"),
                )
            )
            signal_payload: dict[str, object] = {}
            if "signal_quantification_enabled" in request.POST:
                signal_payload["signal_quantification_enabled"] = _payload_bool(
                    request.POST,
                    "signal_quantification_enabled",
                    default=bool(defaults.get("signal_quantification_enabled", True)),
                )
            if "signal_quantification_mode" in request.POST:
                signal_payload["signal_quantification_mode"] = request.POST.get(
                    "signal_quantification_mode",
                    defaults.get("signal_quantification_mode", "puncta_distance"),
                )
            if "puncta_contour_intensity_enabled" in request.POST:
                signal_payload["puncta_contour_intensity_enabled"] = _payload_bool(
                    request.POST,
                    "puncta_contour_intensity_enabled",
                    default=bool(
                        defaults.get("puncta_contour_intensity_enabled", True)
                    ),
                )
            if (
                "alternate_nucleus_detection_enabled" in request.POST
                or "alternate_red_detection" in request.POST
            ):
                signal_payload["alternate_nucleus_detection_enabled"] = _payload_bool(
                    request.POST,
                    "alternate_nucleus_detection_enabled",
                    default=bool(
                        defaults.get(
                            "alternate_nucleus_detection_enabled",
                            defaults.get("alternate_red_detection", False),
                        )
                    ),
                    legacy_key="alternate_red_detection",
                )
            signal_selection = resolve_signal_quantification_selection(
                payload=signal_payload,
                selected_plugins=selected_plugins,
                nuclear_cell_pair_mode=measurement_defaults.get(
                    "nuclear_cell_pair_mode",
                    defaults.get("nuclear_cell_pair_mode", "green_nucleus"),
                ),
                puncta_line_mode=measurement_defaults.get(
                    "puncta_line_mode",
                    defaults.get("puncta_line_mode", DEFAULT_PUNCTA_LINE_MODE),
                ),
            )
            next_defaults = dict(defaults)
            next_defaults["selected_plugins"] = list(
                signal_selection.configured_plugins
            )
            next_defaults.update(
                {
                    "signal_quantification_enabled": signal_selection.enabled,
                    "signal_quantification_mode": signal_selection.mode,
                    "puncta_contour_intensity_enabled": (
                        signal_selection.puncta_contour_intensity_enabled
                    ),
                    "alternate_nucleus_detection_enabled": (
                        signal_selection.alternate_nucleus_detection_enabled
                    ),
                    "green_contour_filter_enabled": _payload_bool(
                        request.POST,
                        "green_contour_filter_enabled",
                        default=bool(
                            defaults.get("green_contour_filter_enabled", False)
                        ),
                    ),
                    "green_dot_split_enabled": green_dot_split_enabled,
                    "green_dot_split_mode": green_dot_split_mode,
                    "red_dot_split_enabled": red_dot_split_enabled,
                    "red_dot_split_mode": red_dot_split_mode,
                    "alternate_red_detection": (
                        signal_selection.alternate_nucleus_detection_enabled
                    ),
                }
            )
            next_defaults.update(measurement_defaults)
            next_payload = dict(preferences)
            next_payload["experiment_defaults"] = next_defaults
            preferences = update_user_preferences(request.user, next_payload)
            defaults = dict(preferences.get("experiment_defaults", {}))
            messages.success(request, "Plugin settings saved.")
            return _preferences_redirect(request, section="plugins")

        if action == "save_advanced_settings":
            # Advanced channel validation can remove plugins whose required
            # channels the user explicitly disables; that keeps future experiment
            # defaults internally consistent.
            module_enabled = _post_bool(request, "module_enabled")
            enforce_layer_count = _post_bool(request, "enforce_layer_count")
            enforce_wavelengths = _post_bool(request, "enforce_wavelengths")
            show_legacy_plugins = _post_bool(request, "show_legacy_plugins")
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

            selected_plugins = normalize_selected_plugins(
                defaults.get("selected_plugins", [])
            )
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
            signal_selection = resolve_signal_quantification_selection(
                payload={},
                selected_plugins=selected_plugins,
                nuclear_cell_pair_mode=measurement_defaults.get(
                    "nuclear_cell_pair_mode",
                    defaults.get("nuclear_cell_pair_mode", "green_nucleus"),
                ),
                puncta_line_mode=measurement_defaults.get(
                    "puncta_line_mode",
                    defaults.get("puncta_line_mode", DEFAULT_PUNCTA_LINE_MODE),
                ),
                default_alternate_nucleus_detection_enabled=bool(
                    defaults.get(
                        "alternate_nucleus_detection_enabled",
                        defaults.get("alternate_red_detection", False),
                    )
                ),
            )
            selected_plugins = list(signal_selection.configured_plugins)

            next_defaults = dict(defaults)
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
                    "alternate_red_detection": (
                        signal_selection.alternate_nucleus_detection_enabled
                    ),
                    "module_enabled": module_enabled,
                    "enforce_layer_count": enforce_layer_count,
                    "enforce_wavelengths": enforce_wavelengths,
                    "show_legacy_plugins": show_legacy_plugins,
                    "manual_required_channels": manual_required_channels,
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
            # Behavior settings live at the top level of the preference payload
            # because Dashboard and Display read them outside experiment defaults.
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
            next_payload["sidebar_starts_open"] = _post_bool(
                request,
                "sidebar_starts_open",
            )
            next_payload["confirm_cell_deletion"] = _post_bool(
                request,
                "confirm_cell_deletion",
            )
            next_payload["confirm_multi_cell_deletion"] = _post_bool(
                request,
                "confirm_multi_cell_deletion",
            )
            if "default_puncta_source_contour_count_filter" in request.POST:
                next_payload["default_puncta_source_contour_count_filter"] = (
                    normalize_puncta_source_contour_count_filter(
                        request.POST.get("default_puncta_source_contour_count_filter")
                    )
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
    signal_defaults = resolve_signal_quantification_from_defaults(defaults)
    selected_plugins = set(signal_defaults.configured_plugins)
    effective_selected_plugins = set(signal_defaults.selected_plugins)
    # The rendered plugin list carries both dependency metadata and legacy flags;
    # the frontend reads the JSON dependency payload for interactive disabling.
    for plugin_id in PLUGIN_UI_ORDER:
        definition = PLUGIN_DEFINITIONS[plugin_id]
        plugin_rows.append(
            {
                "id": plugin_id,
                "label": definition.label,
                "description": definition.description,
                "checked": plugin_id in selected_plugins,
                "is_legacy": definition.is_legacy,
                "required_channels": sorted(
                    definition.required_channels, key=CHANNEL_ORDER.index
                ),
                "required_channel_labels": [
                    channel_display_label(channel)
                    for channel in sorted(
                        definition.required_channels, key=CHANNEL_ORDER.index
                    )
                ],
            }
        )

    required_channel_rows, plugin_requirement_summary = _build_required_channel_rows(
        defaults,
        list(effective_selected_plugins),
    )
    plugin_dependency_payload = build_plugin_ui_payload()
    fallback_channel_order_rows = [
        {
            "channel": channel,
            "label": channel_display_label(channel),
            "slug": channel_slug(channel),
        }
        for channel in normalize_channel_order(
            defaults.get("fallback_channel_order"),
            default=DEFAULT_FALLBACK_CHANNEL_ORDER,
        )
    ]

    return TemplateResponse(
        request,
        "workflow_defaults.html",
        {
            "preferences": preferences,
            "plugins": plugin_rows,
            "channels": CHANNEL_ORDER,
            "channel_info": CHANNEL_INFO,
            "required_channel_rows": required_channel_rows,
            "required_channels_by_plugins": plugin_requirement_summary[
                "required_channels"
            ],
            "plugin_dependency_payload_json": json.dumps(plugin_dependency_payload),
            "fallback_channel_order_rows": fallback_channel_order_rows,
        },
    )
