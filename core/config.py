# Global directory settings
input_dir = ""
output_dir = ""

import os
import json
from django.core.files.storage import default_storage

# Default channel configuration if no per‑file config is found.
DEFAULT_CHANNEL_CONFIG = {"GFP": 0, "mCherry": 1, "DAPI": 2, "DIC": 3}

# Default processing configuration for every user
# From legacy code
DEFAULT_PROCESS_CONFIG = dict(
    kernel_size=13,
    kernel_deviation=5,
    mCherry_line_width=1,
    useCache="on",
    mCherry_to_find_pairs="on",
    drop_ignore="off",
    arrested="Metaphase Arrested",
)


def get_channel_config_for_uuid(uuid):
    """
    Given a DV file's UUID, looks for a channel_config.json file in its folder.
    If found, returns the mapping; otherwise, returns the default configuration.
    """

    config_path = os.path.join(str(uuid), "channel_config.json")
    if default_storage.exists(config_path):
        with default_storage.open(config_path, "r") as f:
            return json.load(f)
    else:
        return DEFAULT_CHANNEL_CONFIG
