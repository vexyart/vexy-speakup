# this_file: src/vexy_speakup/effects.py
"""Built-in effects: explicit speech brightness, and an exact mono fold for upmixers."""

import math
from copy import deepcopy

import numpy as np
from pedalboard import HighShelfFilter

HIGH_SHELF = "builtin:high-shelf"
MONO_FOLD = "builtin:mono-fold"
# Side this far below mid counts as identical channels (dual-mono recordings).
IDENTICAL_DB = -60.0


class MonoFold:
    """Replace near-identical stereo with exact mono (L = R = mid).

    StageOne 2 only exposes a 2-in/2-out bus to pedalboard, so a mono source has to
    reach it as exact L = R. Real stereo and single-channel audio pass unchanged.
    """

    reported_latency_samples = 0

    def __call__(self, audio: np.ndarray) -> np.ndarray:
        if audio.shape[0] != 2:
            return audio
        mid = audio.mean(axis=0)
        side = (audio[0] - audio[1]) / 2
        if np.sqrt(np.mean(side**2)) > np.sqrt(np.mean(mid**2)) * 10 ** (
            IDENTICAL_DB / 20
        ):
            return audio
        return np.stack([mid, mid]).astype(audio.dtype)


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


def load_builtin(spec: dict) -> tuple[HighShelfFilter | MonoFold, dict]:
    """Load only the supported built-in effects; never interpret arbitrary class names."""
    if (
        spec["path"] == MONO_FOLD
        and not spec.get("parameters")
        and spec.keys()
        <= {
            "path",
            "parameters",
        }
    ):
        return MonoFold(), {
            "path": MONO_FOLD,
            "name": "MonoFold",
            "parameters": {"identical_db": IDENTICAL_DB},
            "reported_latency_samples": 0,
        }
    if spec["path"] != HIGH_SHELF or spec.keys() - {"path", "parameters"}:
        raise ValueError(
            "Supported built-ins: builtin:high-shelf with parameters, builtin:mono-fold"
        )
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
