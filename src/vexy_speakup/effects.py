# this_file: src/vexy_speakup/effects.py
"""Explicit speech brightness using Pedalboard's open-source high-shelf filter."""

import math
from copy import deepcopy

from pedalboard import HighShelfFilter

HIGH_SHELF = "builtin:high-shelf"


def brighten(config: dict, gain_db: float) -> dict:
    """Add a 3 kHz shelf to shared/per-speaker chains, leaving master processing alone."""
    if (
        type(gain_db) not in (float, int)
        or not math.isfinite(gain_db)
        or not -12 <= gain_db <= 12
    ):
        raise ValueError("brightness_db must be finite in [-12,12]")
    result = deepcopy(config)
    if gain_db:
        spec = {
            "path": HIGH_SHELF,
            "parameters": {
                "cutoff_frequency_hz": 3000.0,
                "gain_db": gain_db,
                "q": 0.707,
            },
        }
        for chain in [result["speech"], *result.get("speakers", {}).values()]:
            chain.append(deepcopy(spec))
    return result


def load_builtin(spec: dict) -> tuple[HighShelfFilter, dict]:
    """Load only the supported built-in effect; never interpret arbitrary class names."""
    if spec["path"] != HIGH_SHELF or spec.keys() - {"path", "parameters"}:
        raise ValueError("Supported built-in: builtin:high-shelf with parameters")
    plugin = HighShelfFilter(**spec.get("parameters", {}))
    parameters = {
        key: getattr(plugin, key) for key in ("cutoff_frequency_hz", "gain_db", "q")
    }
    if not all(math.isfinite(v) for v in parameters.values()):
        raise ValueError("High-shelf parameters must be finite")
    return plugin, {
        "path": HIGH_SHELF,
        "name": "HighShelfFilter",
        "parameters": parameters,
        "reported_latency_samples": 0,
    }
