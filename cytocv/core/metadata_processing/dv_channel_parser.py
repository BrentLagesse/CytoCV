import re
from collections.abc import Mapping

from mrc import DVFile
from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
)
from core.image_sources import (
    DV_IMAGE_EXTENSION,
    TIFF_IMAGE_EXTENSIONS,
    get_image_layer_count,
    is_recognized_image_file,
    source_image_extension,
)
from core.metadata_processing.tiff_channel_parser import extract_tiff_channel_config


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _map_channel_name(orig_name: str, wl_val: float | None) -> str:
    name = (orig_name or "").strip()
    lower = name.lower()

    if wl_val is not None:
        if abs(wl_val - 625) < 12:
            return CHANNEL_ROLE_RED
        if abs(wl_val - 525) < 12:
            return CHANNEL_ROLE_GREEN
        if abs(wl_val - 435) < 12:
            return CHANNEL_ROLE_BLUE
        # DIC is often encoded as negative (POL). Treat tiny positive values as DIC too.
        if wl_val < 0 or (1 <= wl_val < 200):
            return CHANNEL_ROLE_DIC

    compact = "".join(ch for ch in lower if ch.isalnum())
    if "dic" in compact or "brightfield" in compact or "transmission" in compact or compact == "bf":
        return CHANNEL_ROLE_DIC
    if "dapi" in compact or "hoechst" in compact:
        return CHANNEL_ROLE_BLUE
    if "gfp" in compact:
        return CHANNEL_ROLE_GREEN
    if "mcherry" in compact or "cherry" in compact:
        return CHANNEL_ROLE_RED

    return name


def _extract_from_dv_header(dv_file_path):
    """
    Read channel data from DV metadata first so we only use channels that truly
    exist in the file (e.g., nc=1 + wave1=-50 for DIC-only files).
    """
    dv = None
    try:
        dv = DVFile(dv_file_path)
        metadata = getattr(dv, "metadata", {}) or {}
        header = metadata.get("header", {})
        if not isinstance(header, Mapping):
            return {}

        try:
            channel_count = int(header.get("nc", 0) or 0)
        except (TypeError, ValueError):
            channel_count = 0
        if channel_count <= 0:
            return {}

        config = {}
        for idx in range(channel_count):
            wl_val = _safe_float(header.get(f"wave{idx + 1}"))
            channel = _map_channel_name("", wl_val)
            if channel:
                config[channel] = idx
        return config
    except Exception:
        return {}
    finally:
        if dv is not None:
            dv.close()


def extract_channel_config(dv_file_path):
    """
    Reads a source image file and returns a channel-name -> channel-index mapping.

    Primary source: structured DV metadata header (nc + wave1..waveN).
    Fallback source: XML snippets in the DV header text.
    TIFF uploads use dedicated TIFF metadata parsing with default fallback.
    """
    extension = source_image_extension(dv_file_path)
    if extension in TIFF_IMAGE_EXTENSIONS:
        return extract_tiff_channel_config(dv_file_path)
    if extension != DV_IMAGE_EXTENSION:
        return {}

    header_config = _extract_from_dv_header(dv_file_path)
    if header_config:
        return header_config

    # Fallback XML parsing for legacy files where structured metadata is missing.
    with open(dv_file_path, "rb") as f:
        header_bytes = f.read(16384)
    header_text = header_bytes.decode("latin1", errors="ignore")

    channel_tag_pattern = r"<Channel\b([^>]*)>"
    channel_tags = re.findall(channel_tag_pattern, header_text)
    channel_matches = []
    for attrs in channel_tags:
        name_match = re.search(r'\bname="([^"]+)"', attrs)
        index_match = re.search(r'\bindex="(\d+)"', attrs)
        if name_match and index_match:
            channel_matches.append((name_match.group(1), index_match.group(1)))

    emission_pattern = r"<EmissionFilter\b([^>]*)>"
    emission_tags = re.findall(emission_pattern, header_text)
    wavelength_matches = []
    wavelength_by_name = {}
    for attrs in emission_tags:
        name_match = re.search(r'\bname="([^"]+)"', attrs)
        wavelength_match = re.search(r'\bwavelength="([^"]+)"', attrs)
        wl_val = _safe_float(wavelength_match.group(1)) if wavelength_match else None
        wavelength_matches.append(wl_val)
        if name_match:
            wavelength_by_name[name_match.group(1).strip().lower()] = wl_val

    config = {}
    for i, (orig_name, idx) in enumerate(channel_matches):
        wl_val = wavelength_by_name.get((orig_name or "").strip().lower())
        if wl_val is None and i < len(wavelength_matches):
            wl_val = wavelength_matches[i]
        channel = _map_channel_name(orig_name, wl_val)
        try:
            config[channel] = int(idx)
        except (TypeError, ValueError):
            continue
    return config


def is_recognized_dv_file(dv_file_path):
    """
    Returns True if the file can be opened as a supported source image file.
    """
    return is_recognized_image_file(dv_file_path)


def get_dv_layer_count(dv_file_path):
    """
    Returns the number of image layers/channels in the source image file.
    """
    return get_image_layer_count(dv_file_path)


def is_valid_dv_file(dv_file_path):
    """
    Returns True only if the DV actually contains exactly 4 image layers.
    """
    return get_dv_layer_count(dv_file_path) == 4
