# this_file: tests/test_effects.py
"""Brightness changes high-frequency energy without shifting the timeline."""

import numpy as np
import pytest

from vexy_speakup.effects import brighten
from vexy_speakup.vst import load_chain, profile, render_chunk


def test_brightness_when_positive_then_raise_upper_band_without_changing_frames():
    rate = 48000
    t = np.arange(rate) / rate
    x = 0.1 * np.sin(2 * np.pi * 300 * t) + 0.1 * np.sin(2 * np.pi * 8000 * t)
    audio = np.stack([x, x], axis=1).astype(np.float32)
    config = brighten({"speech": [], "master": [], "speakers": {}}, 3)
    board, receipt = load_chain(config["speech"])
    out = render_chunk(board, audio, rate)
    gain = np.abs(np.fft.rfft(out[:, 0])) / np.maximum(
        np.abs(np.fft.rfft(audio[:, 0])), 1e-10
    )
    assert out.shape == audio.shape and np.isfinite(out).all()
    assert 2.8 < 20 * np.log10(gain[8000]) < 3.2, "Upper band boosted by 3 dB"
    assert abs(20 * np.log10(gain[300])) < 0.1, "Low band stays neutral"
    assert receipt[0]["path"] == "builtin:high-shelf"


def test_brighten_when_speaker_overrides_then_copy_every_speech_chain():
    original = {"speech": [], "master": [], "speakers": {"A": []}}
    result = brighten(original, 4)
    assert len(result["speech"]) == len(result["speakers"]["A"]) == 1
    assert (
        result["master"] == [] and original["speech"] == original["speakers"]["A"] == []
    )


@pytest.mark.parametrize("value", [float("nan"), 13, -13, True])
def test_brighten_when_invalid_then_reject(value):
    with pytest.raises(ValueError):
        brighten({"speech": [], "master": []}, value)


def test_profiles_when_open_source_then_use_supplied_podcast_components():
    config = profile("podcast")
    assert config["speech"][0]["path"].endswith("/pp-track.vst3")
    assert config["master"][0]["path"].endswith("/pp-master.vst3")
    assert profile("podcast-bright")["speech"][0]["parameters"]["timbre"] == 2
    assert profile("dx35-bright")["speech"][-1]["path"] == "builtin:high-shelf"


def test_builtin_when_unknown_or_native_fields_then_reject():
    with pytest.raises(ValueError):
        load_chain([{"path": "builtin:unknown"}])
    with pytest.raises(ValueError):
        load_chain([{"path": "builtin:high-shelf", "preset": "x"}])
