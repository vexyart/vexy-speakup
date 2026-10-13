# this_file: tests/test_preview.py
"""Listening choices must render real clips and survive scheduling."""


import numpy as np
import pytest
import soundfile as sf

from vexy_speakup.batch import read_job
from vexy_speakup.listening import schedule_choices
from vexy_speakup.preview import prepare_preview, speaker_windows


def test_speaker_windows_when_overlap_only_then_identify_mixed_excerpt():
    rows = speaker_windows(
        [
            {"start": 0, "end": 2, "speaker": "A"},
            {"start": 0, "end": 2, "speaker": "B"},
        ],
        2,
        1,
    )
    assert len(rows) == 2 and all(r["overlap"] for r in rows)


def test_preview_when_global_then_four_chains_and_saved_choice(tmp_path, monkeypatch):
    folder = tmp_path / "inputs"
    folder.mkdir()
    sf.write(folder / "voice.wav", np.sin(np.arange(48000) * 0.1) * 0.1, 48000)
    config = tmp_path / "config.toml"
    config.write_text(
        "\n".join(
            f'[candidates.{name}]\nprofile = "bypass"\nsuffix = "_{name}"'
            for name in ["podcast", "dx35", "dx35-bright", "clear"]
        )
    )
    monkeypatch.setenv("VEXY_SPEAKUP_CONFIG", str(config))
    manifest = prepare_preview(
        str(folder), session_dir=str(tmp_path / "preview"), duration=0.5, workers=2
    )
    row = manifest["groups"][0]
    assert len(row["variants"]) == 12, "Four families, three brightness choices each"
    assert all(
        "output" in v and sf.info(v["output"]).frames == 24000 for v in row["variants"]
    )
    path = schedule_choices(
        manifest, {"dx35": 3}, {}, job_path=str(tmp_path / "chosen.json")
    )
    job = read_job(path)
    assert len(job.variants) == 1
    assert job.variants[0].config["speech"][-1]["parameters"]["gain_db"] == 3
    assert job.tasks[0].output.name == "voice_dx35.wav"
    (folder / "voice.wav").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        schedule_choices(
            manifest, {"dx35": 0}, {}, job_path=str(tmp_path / "changed.json")
        )


def bypass_config(tmp_path, monkeypatch, names):
    config = tmp_path / "config.toml"
    config.write_text(
        "\n".join(
            f'[candidates.{name}]\nprofile = "bypass"\nsuffix = "_{name}"'
            for name in names
        )
    )
    monkeypatch.setenv("VEXY_SPEAKUP_CONFIG", str(config))


def test_preview_when_chains_given_then_only_those_auditioned(tmp_path, monkeypatch):
    folder = tmp_path / "inputs"
    folder.mkdir()
    sf.write(folder / "voice.wav", np.sin(np.arange(48000) * 0.1) * 0.1, 48000)
    bypass_config(tmp_path, monkeypatch, ["a", "b", "c"])
    manifest = prepare_preview(
        str(folder), session_dir=str(tmp_path / "p"), duration=0.5, workers=2,
        chains=["a", "c"],
    )
    assert {v["chain"] for v in manifest["groups"][0]["variants"]} == {"a", "c"}


def test_schedule_when_speakers_without_master_then_speech_only_and_overlap(
    tmp_path, monkeypatch
):
    folder = tmp_path / "inputs"
    folder.mkdir()
    sf.write(folder / "talk.wav", np.sin(np.arange(96000) * 0.1) * 0.1, 48000)
    turns = folder.parent / "turns"
    turns.mkdir()
    (turns / "talk.json").write_text(
        '[{"start": 0, "end": 1.2, "speaker": "A"}, {"start": 1.2, "end": 2, "speaker": "B"}]'
    )
    bypass_config(tmp_path, monkeypatch, ["a", "b"])
    manifest = prepare_preview(
        str(folder), session_dir=str(tmp_path / "p"), duration=0.5, workers=2,
        speaker_mode=True, diarization_dir=str(turns),
    )
    assert all(v["config"]["master"] == [] for g in manifest["groups"] for v in g["variants"])
    choices = {g["id"]: {"chain": "a" if g["speaker"] == "A" else "b", "brightness": 3}
               for g in manifest["groups"]}
    job = read_job(schedule_choices(manifest, {}, choices, job_path=str(tmp_path / "j.json")))
    variant = job.variants[0]
    chains = variant.file_speakers[str((folder / "talk.wav").resolve())]
    assert variant.config["master"] == [], "No master unless one is chosen"
    assert chains["_overlap"] == chains["A"], "Overlap follows the dominant speaker"
    with pytest.raises(ValueError, match="Unknown master"):
        schedule_choices(manifest, {}, choices, job_path=str(tmp_path / "k.json"),
                         master_name="absent")


def test_dominant_when_tied_or_unlisted_then_stable_choice():
    from vexy_speakup.listening import dominant

    rows = [{"start": 0, "end": 1, "speaker": "B"}, {"start": 1, "end": 2, "speaker": "A"},
            {"start": 2, "end": 9, "speaker": "C"}]
    assert dominant(rows, {"A": [], "B": []}) == "A"
    assert dominant({"turns": rows}, {"B": [], "C": []}) == "C"


def test_chain_options_when_plugins_missing_then_reported(tmp_path, monkeypatch):
    from vexy_speakup.profiles import chain_options

    bypass_config(tmp_path, monkeypatch, ["plain"])
    monkeypatch.setenv("VEXY_SPEAKUP_PLUGIN_ROOT", str(tmp_path / "empty"))
    rows = {r["name"]: r for r in chain_options()}
    assert rows["plain"]["available"] and rows["plain"]["suggested"]
    assert not rows["plain"]["open_source"], "No plugins at all is not a free chain"
    assert rows["podcast"]["available"] and rows["podcast"]["open_source"]
    assert not rows["dx35"]["available"]
    assert "Accentize-dxRevivePro.vst3" in rows["dx35"]["missing"]
