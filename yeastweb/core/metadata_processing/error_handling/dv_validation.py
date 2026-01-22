from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Set, Tuple

from ..dv_channel_parser import extract_channel_config, get_dv_layer_count, is_recognized_dv_file

EXPECTED_LAYER_COUNT = 4
REQUIRED_CHANNELS = {"DIC", "DAPI", "mCherry", "GFP"}


@dataclass(frozen=True)
class DVValidationOptions:
    """Control which metadata checks run before preprocessing."""

    enforce_layer_count: bool = True
    enforce_wavelengths: bool = True


@dataclass(frozen=True)
class DVValidationResult:
    """Hold metadata validation results for a single DV file."""

    is_valid: bool
    layer_count: int | None
    missing_channels: Set[str]
    error_message: str | None = None


def _effective_wavelength_check(options: DVValidationOptions) -> bool:
    """Wavelength checks only apply when layer count checks are enabled."""

    return options.enforce_layer_count and options.enforce_wavelengths


def validate_dv_file(dv_file_path: Path, options: DVValidationOptions) -> DVValidationResult:
    """Run metadata validation and return the results for the DV file."""

    if not is_recognized_dv_file(str(dv_file_path)):
        return DVValidationResult(
            is_valid=False,
            layer_count=None,
            missing_channels=set(),
            error_message="not a recognized DV file",
        )

    if not options.enforce_layer_count:
        return DVValidationResult(is_valid=True, layer_count=None, missing_channels=set())

    try:
        layer_count = get_dv_layer_count(str(dv_file_path))
    except Exception:
        return DVValidationResult(
            is_valid=False,
            layer_count=None,
            missing_channels=set(),
            error_message="not a recognized DV file",
        )
    if layer_count != EXPECTED_LAYER_COUNT:
        return DVValidationResult(
            is_valid=False,
            layer_count=layer_count,
            missing_channels=set(),
        )

    if _effective_wavelength_check(options):
        channel_config = extract_channel_config(dv_file_path)
        missing_channels = REQUIRED_CHANNELS - set(channel_config.keys())
        if missing_channels:
            return DVValidationResult(
                is_valid=False,
                layer_count=layer_count,
                missing_channels=missing_channels,
            )

    return DVValidationResult(is_valid=True, layer_count=layer_count, missing_channels=set())


def build_dv_error_messages(
    failures: Iterable[Tuple[str, DVValidationResult]],
    options: DVValidationOptions,
) -> list[str]:
    """Create user-facing error messages based on the enabled checks."""

    invalid_file_errors: list[str] = []
    layer_errors: list[str] = []
    wavelength_errors: list[str] = []
    for name, result in failures:
        if result.error_message:
            invalid_file_errors.append(f"- {name}.dv is {result.error_message}")
            continue

        if result.layer_count is not None and result.layer_count != EXPECTED_LAYER_COUNT:
            count = result.layer_count
            suffix = "s" if count != 1 else ""
            layer_errors.append(f"- {name}.dv has {count} layer{suffix} (expected {EXPECTED_LAYER_COUNT})")
            continue

        if _effective_wavelength_check(options) and result.missing_channels:
            missing_list = ", ".join(sorted(result.missing_channels))
            wavelength_errors.append(
                f"- {name}.dv has incorrect image wavelengths for {missing_list}"
            )

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
    append_section(
        "Could not process the following files due to missing required wavelengths:",
        wavelength_errors,
    )

    return messages
