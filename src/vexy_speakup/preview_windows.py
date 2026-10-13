# this_file: src/vexy_speakup/preview_windows.py
"""Bounded representative and exclusive-speaker sample selection."""

from pathlib import Path

import numpy as np
import soundfile as sf

from .turns import partition


def speaker_windows(turns: list[dict], seconds: float, length: float) -> list[dict]:
    """Prefer longest exclusive speech; label overlap-only samples as mixed audio."""
    parts = partition(turns, seconds, max(seconds, 1))
    rows = []
    for speaker in sorted({t["speaker"] for t in turns}):
        exclusive = [p for p in parts if p["speakers"] == [speaker]]
        candidates = exclusive or [p for p in parts if speaker in p["speakers"]]
        selected = max(candidates, key=lambda p: p["end"] - p["start"])
        rows.append(
            {
                "speaker": speaker,
                "start": selected["start"],
                "duration": min(length, selected["end"] - selected["start"]),
                "overlap": not bool(exclusive),
            }
        )
    return rows


def representative(audio: Path, length: float) -> dict:
    """Choose an energy-rich window from evenly sampled positions without loading a full recording."""
    best, score = 0.0, -1.0
    with sf.SoundFile(audio) as reader:
        seconds = len(reader) / reader.samplerate
        duration = min(length, seconds)
        for start in np.linspace(0, max(0, seconds - duration), 17):
            reader.seek(round(start * reader.samplerate))
            chunk = reader.read(
                round(duration * reader.samplerate), dtype="float32", always_2d=True
            )
            energy = float(np.mean(chunk**2))
            if energy > score:
                best, score = float(start), energy
    return {"speaker": None, "start": best, "duration": duration, "overlap": False}
