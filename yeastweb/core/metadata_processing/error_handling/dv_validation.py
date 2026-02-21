from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Set, Tuple

from ..dv_channel_parser import extract_channel_config, get_dv_layer_count, is_recognized_dv_file
from ...stats_plugins import CHANNEL_ORDER

EXPECTED_LAYER_COUNT = 4
REQUIRED_CHANNELS = {"DIC", "DAPI", "mCherry", "GFP"}
CHANNEL_NAME_ALIASES = {
    "dic": "DIC",
    "dapi": "DAPI",
    "gfp": "GFP",
    "mcherry": "mCherry",
    "m-cherry": "mCherry",
}


def _channel_sort_key(channel: str) -> int:
    try:
        return CHANNEL_ORDER.index(channel)
    except ValueError:
        return len(CHANNEL_ORDER)


def _normalize_channel_name(channel: str) -> str | None:
    raw = str(channel).strip()
    if not raw:
        return None
    lower = raw.lower()
    alias = CHANNEL_NAME_ALIASES.get(lower)
    if alias:
        return alias
    # Handle common DV labels like "w1DIC", "Brightfield", etc.
    compact = "".join(ch for ch in lower if ch.isalnum())
    if "dic" in compact or "brightfield" in compact or "transmission" in compact or compact == "bf":
        return "DIC"
    if "dapi" in compact or "hoechst" in compact:
        return "DAPI"
    if "gfp" in compact:
        return "GFP"
    if "mcherry" in compact or "cherry" in compact:
        return "mCherry"
    return raw if raw in CHANNEL_ORDER else None


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
class DVValidationOptions:
    """Control which metadata checks run before preprocessing."""

    enforce_layer_count: bool = False
    enforce_wavelengths: bool = False
    required_channels: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class DVValidationResult:
    """Hold metadata validation results for a single DV file."""

    is_valid: bool
    layer_count: int | None
    missing_channels: Set[str]
    required_channels: Set[str] = field(default_factory=set)
    error_message: str | None = None


def get_effective_required_channels(options: DVValidationOptions) -> Set[str]:
    """Return the full set of required channels for this validation run."""

    required = set(options.required_channels or set())
    if options.enforce_wavelengths:
        required.update(REQUIRED_CHANNELS)
    return required


def validate_dv_file(dv_file_path: Path, options: DVValidationOptions) -> DVValidationResult:
    """Run metadata validation and return the results for the DV file."""

    required_channels = get_effective_required_channels(options)

    if not is_recognized_dv_file(str(dv_file_path)):
        return DVValidationResult(
            is_valid=False,
            layer_count=None,
            missing_channels=set(),
            required_channels=required_channels,
            error_message="not a recognized DV file",
        )

    layer_count = None
    if options.enforce_layer_count:
        try:
            layer_count = get_dv_layer_count(str(dv_file_path))
        except Exception:
            return DVValidationResult(
                is_valid=False,
                layer_count=None,
                missing_channels=set(),
                required_channels=required_channels,
                error_message="not a recognized DV file",
            )
        if layer_count != EXPECTED_LAYER_COUNT:
            return DVValidationResult(
                is_valid=False,
                layer_count=layer_count,
                missing_channels=set(),
                required_channels=required_channels,
            )

    if required_channels:
        channel_config = extract_channel_config(dv_file_path)
        if layer_count is None:
            try:
                layer_count = get_dv_layer_count(str(dv_file_path))
            except Exception:
                return DVValidationResult(
                    is_valid=False,
                    layer_count=None,
                    missing_channels=set(),
                    required_channels=required_channels,
                    error_message="not a recognized DV file",
                )

        available_channels = _available_channels_from_config(channel_config, layer_count)
        missing_channels = set(required_channels) - available_channels
        if missing_channels:
            return DVValidationResult(
                is_valid=False,
                layer_count=layer_count,
                missing_channels=missing_channels,
                required_channels=required_channels,
            )

    return DVValidationResult(
        is_valid=True,
        layer_count=layer_count,
        missing_channels=set(),
        required_channels=required_channels,
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


def build_dv_error_messages(
    failures: Iterable[Tuple[str, DVValidationResult]],
    options: DVValidationOptions,
) -> list[str]:
    """Create user-facing error messages based on the enabled checks."""

    invalid_file_errors: list[str] = []
    layer_errors: list[str] = []
    wavelength_groups: dict[tuple[str, ...], list[str]] = {}
    required_channels = get_effective_required_channels(options)

    for name, result in failures:
        file_name = f"{name}.dv"
        if result.error_message:
            invalid_file_errors.append(f"- {file_name} is {result.error_message}")
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
        "Could not process the following files because they are not recognized DV files:",
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
            required_list = ", ".join(_sorted_channels(required_channels))
            messages.append(f"The following wavelengths are required: {required_list}.")

        for missing_key in sorted(wavelength_groups.keys(), key=lambda key: (len(key), key)):
            files = sorted(wavelength_groups[missing_key])
            files_text = ", ".join(files)
            missing_set = set(missing_key)
            if required_channels and missing_set == set(required_channels) and len(required_channels) > 1:
                missing_text = "all required wavelengths"
            else:
                missing_text = _join_words(list(missing_key))
            messages.append(f"- {files_text}: missing {missing_text}")

    return messages
