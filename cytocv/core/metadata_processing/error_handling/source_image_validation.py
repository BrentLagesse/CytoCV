from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Set, Tuple

from ...channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
    channel_display_label,
    normalize_channel_role,
)
from ...image_sources import get_image_layer_count, is_recognized_image_file
from ..dv_channel_parser import extract_channel_config
from ...stats_plugins import CHANNEL_ORDER
from ...services.channel_presence import (
    extract_reliable_metadata_channel_config,
)

EXPECTED_LAYER_COUNT = 4
REQUIRED_CHANNELS = {CHANNEL_ROLE_DIC, CHANNEL_ROLE_BLUE, CHANNEL_ROLE_RED, CHANNEL_ROLE_GREEN}


def _channel_sort_key(channel: str) -> int:
    try:
        return CHANNEL_ORDER.index(channel)
    except ValueError:
        return len(CHANNEL_ORDER)


def _normalize_channel_name(channel: str) -> str | None:
    normalized = normalize_channel_role(channel)
    return normalized if normalized in CHANNEL_ORDER else None


def _available_channels_from_config(channel_config: dict, layer_count: int) -> Set[str]:
    available: Set[str] = set()
    for raw_name, raw_index in (channel_config or {}).items():
        channel_name = _normalize_channel_name(str(raw_name))
        if not channel_name:
            continue
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if 0 <= index < layer_count:
            available.add(channel_name)
    return available


@dataclass(frozen=True)
class SourceImageValidationOptions:
    """Control which metadata checks run before preprocessing."""

    enforce_layer_count: bool = False
    enforce_wavelengths: bool = False
    required_channels: Set[str] = field(default_factory=set)
    prefer_metadata_channel_order: bool = True
    configured_experiment_label: str = "the configured experiment"


@dataclass(frozen=True)
class SourceImageValidationResult:
    """Hold metadata validation results for a single source image file."""

    is_valid: bool
    layer_count: int | None
    missing_channels: Set[str]
    required_channels: Set[str] = field(default_factory=set)
    error_message: str | None = None
    identified_channels: Set[str] = field(default_factory=set)


def get_effective_required_channels(options: SourceImageValidationOptions) -> Set[str]:
    """Return the full set of required channels for this validation run."""

    required = set(options.required_channels or set())
    if options.enforce_wavelengths:
        required.update(REQUIRED_CHANNELS)
    return required


def validate_source_image_file(
    source_image_path: Path,
    options: SourceImageValidationOptions,
) -> SourceImageValidationResult:
    """Run metadata validation and return results for a source image file."""

    required_channels = get_effective_required_channels(options)

    if not is_recognized_image_file(str(source_image_path)):
        return SourceImageValidationResult(
            is_valid=False,
            layer_count=None,
            missing_channels=set(),
            required_channels=required_channels,
            error_message="not a recognized supported image file",
        )

    layer_count = None
    should_check_layer_count = bool(
        options.enforce_layer_count
        or required_channels
    )
    if should_check_layer_count:
        try:
            layer_count = get_image_layer_count(str(source_image_path))
        except Exception:
            return SourceImageValidationResult(
                is_valid=False,
                layer_count=None,
                missing_channels=set(),
                required_channels=required_channels,
                error_message="not a recognized supported image file",
            )
        if options.enforce_layer_count and layer_count != EXPECTED_LAYER_COUNT:
            return SourceImageValidationResult(
                is_valid=False,
                layer_count=layer_count,
                missing_channels=set(),
                required_channels=required_channels,
            )
        if not options.enforce_layer_count and layer_count not in {3, EXPECTED_LAYER_COUNT}:
            suffix = "s" if layer_count != 1 else ""
            return SourceImageValidationResult(
                is_valid=False,
                layer_count=layer_count,
                missing_channels=set(),
                required_channels=required_channels,
                error_message=(
                    f"has {layer_count} layer{suffix}; CytoCV supports 3 or "
                    f"{EXPECTED_LAYER_COUNT} layers for this workflow"
                ),
            )

    if required_channels:
        if layer_count is None:
            try:
                layer_count = get_image_layer_count(str(source_image_path))
            except Exception:
                return SourceImageValidationResult(
                    is_valid=False,
                    layer_count=None,
                    missing_channels=set(),
                    required_channels=required_channels,
                    error_message="not a recognized supported image file",
                )

        if layer_count == 3:
            metadata_config = extract_reliable_metadata_channel_config(
                source_image_path,
                prefer_metadata=options.prefer_metadata_channel_order,
            )
            identified_channels = _available_channels_from_config(
                metadata_config,
                layer_count,
            )
            if len(identified_channels) == layer_count and CHANNEL_ROLE_DIC not in identified_channels:
                return SourceImageValidationResult(
                    is_valid=False,
                    layer_count=layer_count,
                    missing_channels={CHANNEL_ROLE_DIC},
                    required_channels=required_channels,
                    error_message=_dic_missing_error(
                        layer_count=layer_count,
                        identified_channels=identified_channels,
                    ),
                    identified_channels=identified_channels,
                )
            if len(identified_channels) != layer_count:
                return SourceImageValidationResult(
                    is_valid=False,
                    layer_count=layer_count,
                    missing_channels=set(),
                    required_channels=required_channels,
                    error_message=_metadata_insufficient_error(
                        layer_count=layer_count,
                        required_channels=required_channels,
                        options=options,
                    ),
                    identified_channels=identified_channels,
                )
            available_channels = identified_channels
        else:
            channel_config = extract_channel_config(
                source_image_path,
                prefer_metadata=options.prefer_metadata_channel_order,
            )
            available_channels = _available_channels_from_config(channel_config, layer_count)
        missing_channels = set(required_channels) - available_channels
        if missing_channels:
            return SourceImageValidationResult(
                is_valid=False,
                layer_count=layer_count,
                missing_channels=missing_channels,
                required_channels=required_channels,
                error_message=(
                    _required_channels_missing_error(
                        layer_count=layer_count,
                        identified_channels=available_channels,
                        required_channels=required_channels,
                        missing_channels=missing_channels,
                        options=options,
                    )
                    if layer_count == 3
                    else None
                ),
                identified_channels=available_channels,
            )

    return SourceImageValidationResult(
        is_valid=True,
        layer_count=layer_count,
        missing_channels=set(),
        required_channels=required_channels,
        identified_channels=available_channels if required_channels else set(),
    )


def _join_words(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _sorted_channels(channels: Set[str]) -> list[str]:
    return sorted(channels, key=_channel_sort_key)


def _sorted_channel_labels(channels: Set[str]) -> list[str]:
    return [channel_display_label(channel) for channel in _sorted_channels(channels)]


def _channel_list(channels: Set[str]) -> str:
    labels = _sorted_channel_labels(channels)
    return ", ".join(labels) if labels else "none"


def _configured_experiment_label(options: SourceImageValidationOptions) -> str:
    return str(options.configured_experiment_label or "the configured experiment")


def _suggestion_for_missing_channels(
    *,
    identified_channels: Set[str],
    missing_channels: Set[str],
) -> str:
    if CHANNEL_ROLE_GREEN in missing_channels and CHANNEL_ROLE_RED in identified_channels:
        return (
            "Change the puncta source to Red Puncta Only for red-only stacks, "
            "or upload a file containing Green."
        )
    if CHANNEL_ROLE_RED in missing_channels and CHANNEL_ROLE_GREEN in identified_channels:
        return (
            "Change the puncta source to Green Puncta Only for green-only stacks, "
            "or upload a file containing Red."
        )
    if CHANNEL_ROLE_BLUE in missing_channels:
        return "Disable Blue-dependent analyses, or upload a file containing Blue."
    return "Upload a file containing the required channel(s)."


def _metadata_insufficient_error(
    *,
    layer_count: int,
    required_channels: Set[str],
    options: SourceImageValidationOptions,
) -> str:
    return (
        f"has {layer_count} layers, but CytoCV could not identify the present "
        "channels from file metadata. "
        f"The configured experiment requires: {_channel_list(required_channels)} "
        f"for {_configured_experiment_label(options)}. "
        "Use a metadata-supported file that identifies DIC and the required "
        "fluorescence channels, or upload a stack containing the required channels."
    )


def _dic_missing_error(
    *,
    layer_count: int,
    identified_channels: Set[str],
) -> str:
    return (
        f"has {layer_count} layers. Metadata identified: "
        f"{_channel_list(identified_channels)}. DIC was not identified, but DIC "
        "is required for cell segmentation. This file cannot be processed with "
        "the current workflow."
    )


def _required_channels_missing_error(
    *,
    layer_count: int,
    identified_channels: Set[str],
    required_channels: Set[str],
    missing_channels: Set[str],
    options: SourceImageValidationOptions,
) -> str:
    return (
        f"has {layer_count} layers. Metadata identified: "
        f"{_channel_list(identified_channels)}. The configured experiment "
        f"requires: {_channel_list(required_channels)} for "
        f"{_configured_experiment_label(options)}. Missing required channel(s): "
        f"{_channel_list(missing_channels)}. "
        f"{_suggestion_for_missing_channels(identified_channels=identified_channels, missing_channels=missing_channels)}"
    )


def _failure_file_name(name: object) -> str:
    file_name = Path(str(name or "")).name
    if Path(file_name).suffix:
        return file_name
    return f"{file_name}.dv"


def build_source_image_error_messages(
    failures: Iterable[Tuple[str, SourceImageValidationResult]],
    options: SourceImageValidationOptions,
) -> list[str]:
    """Create user-facing error messages based on the enabled checks."""

    invalid_file_errors: list[str] = []
    layer_errors: list[str] = []
    wavelength_groups: dict[tuple[str, ...], list[str]] = {}
    required_channels = get_effective_required_channels(options)

    for name, result in failures:
        file_name = _failure_file_name(name)
        if result.error_message:
            prefix = "" if result.error_message.startswith("has ") else "is "
            invalid_file_errors.append(f"- {file_name} {prefix}{result.error_message}")
            continue

        if (
            options.enforce_layer_count
            and result.layer_count is not None
            and result.layer_count != EXPECTED_LAYER_COUNT
        ):
            count = result.layer_count
            suffix = "s" if count != 1 else ""
            layer_errors.append(f"- {file_name} has {count} layer{suffix} (expected {EXPECTED_LAYER_COUNT})")
            continue

        if result.missing_channels:
            missing_key = tuple(_sorted_channels(result.missing_channels))
            wavelength_groups.setdefault(missing_key, []).append(file_name)

    messages: list[str] = []

    def append_section(title: str, items: list[str]) -> None:
        if not items:
            return
        if messages:
            messages.append("")
        messages.append(title)
        messages.extend(items)

    append_section(
        "Could not process the following files:",
        invalid_file_errors,
    )
    append_section(
        "Could not process the following files due to invalid layer counts (expected 4 layers):",
        layer_errors,
    )

    if wavelength_groups:
        if messages:
            messages.append("")
        messages.append("Could not process the following files due to missing required wavelengths:")
        if required_channels:
            required_list = ", ".join(_sorted_channel_labels(required_channels))
            messages.append(f"The following wavelengths are required: {required_list}.")

        for missing_key in sorted(wavelength_groups.keys(), key=lambda key: (len(key), key)):
            files = sorted(wavelength_groups[missing_key])
            files_text = ", ".join(files)
            missing_set = set(missing_key)
            if required_channels and missing_set == set(required_channels) and len(required_channels) > 1:
                missing_text = "all required wavelengths"
            else:
                missing_text = _join_words(_sorted_channel_labels(missing_set))
            messages.append(f"- {files_text}: missing {missing_text}")

    return messages
