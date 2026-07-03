"""Channel-role resolution for DV files and the shared source-image facade."""

import re
from collections.abc import Mapping

from mrc import DVFile
from core.channel_roles import (
    CHANNEL_ROLE_BLUE,
    CHANNEL_ROLE_DIC,
    CHANNEL_ROLE_GREEN,
    CHANNEL_ROLE_RED,
    normalize_channel_role,
)
from core.channel_ordering import resolve_channel_config
from core.image_sources import (
    DV_IMAGE_EXTENSION,
    TIFF_IMAGE_EXTENSIONS,
    get_image_layer_count,
    is_recognized_image_file,
    source_image_extension,
)
from core.metadata_processing.tiff_channel_parser import extract_tiff_channel_config


def _safe_float(value):
    """Parse a DV wavelength field without raising on malformed metadata."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _map_channel_name(orig_name: str, wl_val: float | None) -> str | None:
    """Map DV channel label/wavelength metadata to a logical channel role."""

    name = (orig_name or "").strip()
    lower = name.lower()

    # Prefer wavelength metadata when present because DV channel labels are often
    # generic, localized, or omitted.
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

    return normalize_channel_role(name)


def _store_channel_mapping(
    config: dict[str, int],
    used_indices: set[int],
    channel: str | None,
    raw_index,
) -> bool:
    """Store one unique channel role/index pair into a parsed config."""

    role = normalize_channel_role(channel)
    if role is None:
        return True
    try:
        index = int(raw_index)
    except (TypeError, ValueError):
        return False
    if role in config or index in used_indices or index < 0:
        return False
    config[role] = index
    used_indices.add(index)
    return True


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
            return None

        try:
            channel_count = int(header.get("nc", 0) or 0)
        except (TypeError, ValueError):
            channel_count = 0
        if channel_count <= 0:
            return None

        config = {}
        used_indices = set()
        for idx in range(channel_count):
            # Structured DV headers list channel count and waveN fields in order;
            # indices therefore come from header position, not from fallback order.
            wl_val = _safe_float(header.get(f"wave{idx + 1}"))
            channel = _map_channel_name("", wl_val)
            if not _store_channel_mapping(config, used_indices, channel, idx):
                return {}
        return config or None
    except Exception:
        # Header parsing is optional metadata enrichment.  Return None so the XML
        # snippet parser or fallback order can still run.
        return None
    finally:
        if dv is not None:
            dv.close()


def extract_dv_metadata_channel_config(dv_file_path):
    """
    Return DV metadata-derived channel config, or an empty mapping when unavailable.

    Primary source: structured DV metadata header (nc + wave1..waveN).
    Secondary source: XML snippets in the DV header text.
    """
    header_config = _extract_from_dv_header(dv_file_path)
    if header_config is not None:
        return header_config

    # Legacy DV exports can omit structured wavelength fields but still include
    # XML-like channel snippets in the header bytes.
    with open(dv_file_path, "rb") as f:
        header_bytes = f.read(16384)
    header_text = header_bytes.decode("latin1", errors="ignore")

    channel_tag_pattern = r"<Channel\b([^>]*)>"
    channel_tags = re.findall(channel_tag_pattern, header_text)
    channel_matches = []
    for attrs in channel_tags:
        # XML-like snippets may appear in older DV files; extract only explicit
        # name/index pairs so the parser does not infer channels from arbitrary text.
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
    used_indices = set()
    for i, (orig_name, idx) in enumerate(channel_matches):
        # Header snippets can list names and emission filters separately; match by
        # name first, then fall back to positional wavelength order.
        wl_val = wavelength_by_name.get((orig_name or "").strip().lower())
        if wl_val is None and i < len(wavelength_matches):
            wl_val = wavelength_matches[i]
        channel = _map_channel_name(orig_name, wl_val)
        if not _store_channel_mapping(config, used_indices, channel, idx):
            return {}
    return config


def extract_channel_config(
    dv_file_path,
    *,
    prefer_metadata: bool = True,
    fallback_order: list[str] | tuple[str, ...] | None = None,
):
    """
    Reads a source image file and returns a channel-name -> channel-index mapping.

    Metadata-derived order is used when available and enabled. Otherwise, the
    configured fallback image-plane order is used for supported source images.
    TIFF uploads use dedicated TIFF metadata parsing with the same fallback.
    """
    extension = source_image_extension(dv_file_path)
    if extension in TIFF_IMAGE_EXTENSIONS:
        # TIFF parsing lives in its own module because ImageJ labels and DV
        # wavelength metadata have different failure modes, but both return the
        # same channel_config.json shape.
        return extract_tiff_channel_config(
            dv_file_path,
            prefer_metadata=prefer_metadata,
            fallback_order=fallback_order,
        )
    if extension != DV_IMAGE_EXTENSION:
        return {}

    # The final resolution step centralizes preference and fallback behavior so
    # DV and TIFF channel_config.json payloads stay in the same shape.
    metadata_config = extract_dv_metadata_channel_config(dv_file_path) if prefer_metadata else {}
    return resolve_channel_config(
        metadata_config,
        prefer_metadata=prefer_metadata,
        fallback_order=fallback_order,
    )


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
    # This legacy helper remains intentionally strict for older call sites that
    # predate conditional required-channel validation.
    return get_dv_layer_count(dv_file_path) == 4
