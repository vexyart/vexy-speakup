# this_file: src/vexy_speakup/levels.py
"""Bounded speech loudness adjustment, leaving silence and room tone alone."""

import numpy as np
import pyloudnorm as pyln


def loudness(audio: np.ndarray, rate: int) -> float:
    """Measure integrated loudness; pad sub-400ms turns only for measurement."""
    if not np.isfinite(audio).all() or len(audio) == 0:
        raise ValueError("Audio must be finite and nonempty")
    padded = np.pad(audio, ((0, max(0, round(0.4 * rate) + 1 - len(audio))), (0, 0)))
    return float(pyln.Meter(rate).integrated_loudness(padded))


def level_gain(
    audio: np.ndarray, rate: int, target: float, speaker_gain: float | None = None
) -> float:
    """Use a speaker baseline with at most 3 dB turn correction and 12 dB total gain."""
    if np.sqrt(np.mean(audio.astype(np.float64) ** 2)) < 1e-6:
        return 0.0
    measured = loudness(audio, rate)
    if not np.isfinite(measured):
        return 0.0
    gain = target - measured
    if speaker_gain is not None:
        gain = speaker_gain + np.clip(gain - speaker_gain, -3, 3)
    return float(np.clip(gain, -12, 12))
