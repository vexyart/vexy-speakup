# this_file: tests/test_assemble.py
"""Adjacent processed fragments blend into each other, not through unprocessed audio."""

import numpy as np
import soundfile as sf

from vexy_speakup.media import RATE
from vexy_speakup.pipeline import BLEND, assemble


def make_job(tmp_path, index, start, end, speakers, render_value, frames):
    """A job whose render is a constant `render_value` over its 0.5 s context."""
    a, b = max(0, start - RATE // 2), min(frames, end + RATE // 2)
    render = tmp_path / f"{index}-render.wav"
    if speakers:
        sf.write(render, np.full((b - a, 2), render_value, np.float32), RATE, subtype="FLOAT")
    return {
        "index": index,
        "speakers": speakers,
        "owner": speakers[0] if speakers else "_background",
        "start_frame": start,
        "end_frame": end,
        "crop_start": start - a,
        "output": str(render),
        "fragment": str(tmp_path / f"{index}.wav"),
    }


def test_assemble_when_two_speakers_adjacent_then_blend_without_original(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("vexy_speakup.pipeline.collect_levels", lambda jobs, t: {})
    monkeypatch.setattr("vexy_speakup.pipeline.level_gain", lambda *a: 0.0)
    frames = 2 * RATE
    source = tmp_path / "source.wav"
    sf.write(source, np.zeros((frames, 2), np.float32), RATE, subtype="FLOAT")
    jobs = [
        make_job(tmp_path, 0, 0, RATE, ["A"], 0.2, frames),
        make_job(tmp_path, 1, RATE, frames, ["B"], 0.6, frames),
    ]
    out, _ = sf.read(assemble(source, jobs, tmp_path, -16), dtype="float32")
    half = round(BLEND * RATE)
    junction = out[RATE - half : RATE + half, 0]
    assert len(out) == frames, "Timeline length preserved"
    assert junction.min() >= 0.2 - 1e-6, "Never dips toward the silent original"
    assert np.all(np.diff(junction) >= -1e-7), "Monotonic A to B crossfade"
    assert abs(out[RATE - half - 1, 0] - 0.2) < 1e-6 and abs(out[RATE + half, 0] - 0.6) < 1e-6
    assert abs(out[0, 0] - 0.2) < 1e-6 and abs(out[-1, 0] - 0.6) < 1e-6, "No edge fades"


def test_assemble_when_speech_meets_background_then_blend_with_original(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("vexy_speakup.pipeline.collect_levels", lambda jobs, t: {})
    monkeypatch.setattr("vexy_speakup.pipeline.level_gain", lambda *a: 0.0)
    frames = 2 * RATE
    source = tmp_path / "source.wav"
    sf.write(source, np.full((frames, 2), 0.1, np.float32), RATE, subtype="FLOAT")
    jobs = [
        make_job(tmp_path, 0, 0, RATE, [], 0, frames),
        make_job(tmp_path, 1, RATE, frames, ["B"], 0.5, frames),
    ]
    out, _ = sf.read(assemble(source, jobs, tmp_path, -16), dtype="float32")
    half = round(BLEND * RATE)
    assert abs(out[RATE - half - 1, 0] - 0.1) < 1e-6, "Background stays original"
    assert 0.1 < out[RATE, 0] < 0.5 and abs(out[RATE + half, 0] - 0.5) < 1e-6
    fragment, _ = sf.read(jobs[1]["fragment"], dtype="float32")
    assert len(fragment) == RATE, "Fragments keep their exact extent"


def test_assemble_when_fragment_short_then_blend_fits_inside(tmp_path, monkeypatch):
    monkeypatch.setattr("vexy_speakup.pipeline.collect_levels", lambda jobs, t: {})
    monkeypatch.setattr("vexy_speakup.pipeline.level_gain", lambda *a: 0.0)
    frames = RATE
    source = tmp_path / "source.wav"
    sf.write(source, np.zeros((frames, 2), np.float32), RATE, subtype="FLOAT")
    cuts = [0, 100, 150, frames]
    jobs = [
        make_job(tmp_path, i, cuts[i], cuts[i + 1], [s], v, frames)
        for i, (s, v) in enumerate([("A", 0.2), ("B", 0.4), ("A", 0.2)])
    ]
    out, _ = sf.read(assemble(source, jobs, tmp_path, -16), dtype="float32")
    assert len(out) == frames and out[:, 0].min() >= 0.2 - 1e-6
