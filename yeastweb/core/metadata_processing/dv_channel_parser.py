import re
from mrc import DVFile

def extract_channel_config(dv_file_path):
    """
    Reads the header of a DV file and extracts channel mapping.
    Returns a dictionary mapping channel names (e.g. "mCherry", "GFP", etc.)
    to their corresponding indices.
    
    The method assumes that the DV header includes XML snippets like:
      <Channel name="Red" index="0" ...>
    and an emission filter tag like:
      <EmissionFilter name="Red" wavelength="625" unit="nm"/>
    
    We then map:
      - wavelength ~625 nm  -> mCherry
      - wavelength ~525 nm  -> GFP
      - wavelength ~435 nm  -> DAPI
      - wavelength negative or very low -> DIC
    """
    # Increase read size to capture more header content (8KB instead of 4KB)
    with open(dv_file_path, "rb") as f:
        header_bytes = f.read(8192)
    header_text = header_bytes.decode("latin1", errors="ignore")
    
    # Find all Channel tags with a name and index
    channel_pattern = r'<Channel\s+name="([^"]+)"\s+index="(\d+)"'
    channel_matches = re.findall(channel_pattern, header_text)
    
    # Use a more generic regex to capture the wavelength from the emission filter tag
    emission_pattern = r'<EmissionFilter\s+.*?wavelength="([^"]+)"'
    wavelength_matches = re.findall(emission_pattern, header_text, re.DOTALL)
    
    # Print all extracted wavelengths for debugging
    print("Extracted wavelengths:", wavelength_matches)
    
    config = {}
    for (orig_name, idx), wl in zip(channel_matches, wavelength_matches):
        try:
            wl_val = float(wl)
        except ValueError:
            wl_val = 0
        print(f"Channel {orig_name} with index {idx} has wavelength: {wl_val}")
        if abs(wl_val - 625) < 10:
            channel = "mCherry"
        elif abs(wl_val - 525) < 10:
            channel = "GFP"
        elif abs(wl_val - 435) < 10:
            channel = "DAPI"
        elif wl_val < 0:
            channel = "DIC"
        else:
            channel = orig_name  # fallback if no match
        config[channel] = int(idx)
    return config

def get_dv_layer_count(dv_file_path):
    """
    Returns the actual number of Z‑slices (layers) in the DV.
    Handles shapes of:
      - 2D arrays  → 1 layer
      - 3D arrays where the small dimension is Z, e.g. (Z, H, W) or (H, W, Z).
    """
    print(f"Reading DV file metadata: {dv_file_path}")
    dv = DVFile(dv_file_path)
    try:
        arr = dv.asarray()
        # 2D, exactly one layer
        if arr.ndim == 2:
            return 1
        # 3D, assume the smallest axis is the Z dimension
        elif arr.ndim == 3:
            return min(arr.shape)
        else:
            # Unexpected rank, treat as zero
            return 0
    finally:
        dv.close()

def is_valid_dv_file(dv_file_path):
    """
    Returns True only if the DV actually contains exactly 4 image layers.
    """
    return get_dv_layer_count(dv_file_path) == 4