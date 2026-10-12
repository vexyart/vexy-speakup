# this_file: src/vexy_speakup/locations.py
"""Resolve installation-specific roots lazily, so imports and imported turns need neither."""

import os
from pathlib import Path

PLUGIN_ENV = "VEXY_SPEAKUP_PLUGIN_ROOT"
TTS_ENV = "VEXY_SPEAKUP_TTS_ROOT"
DEFAULT_PLUGIN_ROOT = "/Library/Audio/Plug-Ins/VST3"


def plugin_root() -> Path:
    """VST3 folder used by built-in profiles and `inventory`; macOS system folder by default."""
    return Path(os.environ.get(PLUGIN_ENV) or DEFAULT_PLUGIN_ROOT).expanduser()


def tts_root() -> Path:
    """Folder holding the myasr/myaud adapters and native model hosts.

    Raises FileNotFoundError (an OSError, which evaluation records per window) when unset.
    """
    value = os.environ.get(TTS_ENV)
    if not value:
        raise FileNotFoundError(
            f"Set {TTS_ENV} to the folder containing myasr/ and myaud/, "
            "or pass --diarization_json and --evaluate=False"
        )
    root = Path(value).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"{TTS_ENV} is not a directory: {root}")
    return root
