# this_file: src/vexy_speakup/locations.py
"""Resolve installation-specific roots lazily, so imports need none of them."""

import os
from pathlib import Path

from .settings import read_settings

PLUGIN_ENV = "VEXY_SPEAKUP_PLUGIN_ROOT"
DEFAULT_PLUGIN_ROOT = "/Library/Audio/Plug-Ins/VST3"


def plugin_root() -> Path:
    """VST3 folder used by built-in profiles and `inventory`; macOS system folder by default."""
    return Path(
        os.environ.get(PLUGIN_ENV) or read_settings()["paths"]["plugin_root"]
    ).expanduser()
