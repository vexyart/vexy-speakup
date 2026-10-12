# this_file: src/vexy_speakup/turns.py
"""Validate diarization and partition a timeline without duplicating overlaps."""

import math
import re
from itertools import pairwise


def parse_turns(raw: list | dict, duration: float) -> list[dict]:
    """Accept the local adapters' turns, native segments, or a bare segment list."""
    rows = raw.get("turns", raw.get("segments")) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise TypeError("Diarization requires a turns/segments array")
    result = []
    for row in rows:
        start, end, speaker = row["start"], row["end"], row["speaker"]
        if any(
            isinstance(t, bool)
            or not isinstance(t, (int, float))
            or not math.isfinite(t)
            for t in (start, end)
        ):
            raise ValueError("Turn timestamps must be finite numbers")
        if not 0 <= start < end <= duration + 0.001:
            raise ValueError(f"Turn outside audio duration: {row}")
        if (
            isinstance(speaker, bool)
            or not isinstance(speaker, (str, int))
            or not re.fullmatch(r"[\w-]+", str(speaker))
        ):
            raise ValueError("Speaker must be a safe nonempty identifier")
        result.append(
            {
                "start": float(start),
                "end": min(float(end), duration),
                "speaker": str(speaker),
            }
        )
    return sorted(result, key=lambda row: (row["start"], row["end"], row["speaker"]))


def partition(turns: list[dict], duration: float, max_chunk: float) -> list[dict]:
    """Produce disjoint intervals; overlap belongs to a shared mix, never two stems."""
    if not math.isfinite(max_chunk) or max_chunk <= 0:
        raise ValueError("max_chunk must be positive")
    events = {0.0: [], duration: []}
    for turn in turns:
        events.setdefault(turn["start"], []).append((turn["speaker"], 1))
        events.setdefault(turn["end"], []).append((turn["speaker"], -1))
    active, merged = {}, []
    times = sorted(events)
    for start, end in pairwise(times):
        for speaker, delta in events[start]:
            active[speaker] = active.get(speaker, 0) + delta
        speakers = sorted(k for k, count in active.items() if count > 0)
        if merged and merged[-1]["speakers"] == speakers:
            merged[-1]["end"] = end
        else:
            merged.append({"start": start, "end": end, "speakers": speakers})
    result = []
    for row in merged:
        start = row["start"]
        while start < row["end"]:
            end = min(row["end"], start + max_chunk)
            result.append({"start": start, "end": end, "speakers": row["speakers"]})
            start = end
    return result
