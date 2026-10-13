# this_file: tests/test_batch.py
"""Saved jobs retain choices, produce distinct variants and verify resumed outputs."""

import json
import subprocess
import sys

import numpy as np
import pytest
import soundfile as sf

from vexy_speakup.batch import create_job, read_job, save_job
from vexy_speakup.queue import run_job


def setup_recording(tmp_path):
    folder = tmp_path / "inputs"
    folder.mkdir()
    rate = 48000
    t = np.arange(rate) / rate
    sf.write(folder / "voice.wav", 0.15 * np.sin(2 * np.pi * 500 * t), rate)
    turns = tmp_path / "turns"
    turns.mkdir()
    (turns / "voice.json").write_text('[{"start":0,"end":1,"speaker":"A"}]')
    return folder, turns


def test_saved_job_when_run_then_distinct_outputs_and_verified_resume(
    tmp_path, monkeypatch
):
    folder, turns = setup_recording(tmp_path)
    config = tmp_path / "config.toml"
    config.write_text("""[candidates.plain]
profile = "bypass"
suffix = "_plain"
[candidates.brighter]
suffix = "_brighter"
master = []
[[candidates.brighter.speech]]
path = "builtin:high-shelf"
[candidates.brighter.speech.parameters]
gain_db = 3
""")
    monkeypatch.setenv("VEXY_SPEAKUP_CONFIG", str(config))
    path = create_job(
        str(folder),
        candidates="plain,brighter",
        job_path=str(tmp_path / "job.json"),
        diarization_dir=str(turns),
    )
    assert read_job(path).status == "scheduled"
    summary = run_job(path, workers=2, file_workers=2, verbose=False)
    assert summary["status"] == "complete" and summary["completed"] == 2
    job = read_job(path)
    assert all(sf.info(t.output).frames == 48000 for t in job.tasks), (
        "Variants retain the timeline"
    )
    assert {t.output.name for t in job.tasks} == {
        "voice_plain.wav",
        "voice_brighter.wav",
    }
    monkeypatch.setattr(
        "vexy_speakup.batch_render.run",
        lambda **kwargs: pytest.fail("Completed tasks rerendered"),
    )
    assert run_job(path, verbose=False)["completed"] == 2
    job.tasks[0].status = "running"
    job.tasks[0].output_sha256, job.tasks[0].report = "", ""
    save_job(path, job)
    assert run_job(path, verbose=False)["completed"] == 2, (
        "Recover interrupted state from a verified completed report"
    )
    job.tasks[0].output.write_bytes(b"changed")
    assert run_job(path, verbose=False)["status"] == "failed", (
        "Altered output cannot count as complete"
    )


def test_saved_job_when_source_changes_then_fail_without_output(tmp_path):
    folder, turns = setup_recording(tmp_path)
    path = create_job(
        str(folder),
        candidates="bypass",
        job_path=str(tmp_path / "job.json"),
        diarization_dir=str(turns),
    )
    (folder / "voice.wav").write_bytes(b"changed")
    summary = run_job(path, verbose=False)
    assert summary["status"] == "failed"
    assert "changed" in read_job(path).tasks[0].error.lower()
    assert not read_job(path).tasks[0].output.exists()
    result = subprocess.run(
        [sys.executable, "-m", "vexy_speakup", "job", str(path), "--verbose=False"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1 and "failed" in result.stdout, (
        "CLI signals batch failure"
    )


def test_create_when_empty_or_bad_candidate_then_reject(tmp_path):
    folder = tmp_path / "empty"
    folder.mkdir()
    with pytest.raises(ValueError, match="No media"):
        create_job(str(folder))
    folder, _ = setup_recording(tmp_path)
    with pytest.raises(ValueError, match="Unknown"):
        create_job(str(folder), candidates="absent")


def test_read_when_task_destination_is_input_then_reject(tmp_path):
    folder, turns = setup_recording(tmp_path)
    path = create_job(
        str(folder),
        candidates="bypass",
        job_path=str(tmp_path / "job.json"),
        diarization_dir=str(turns),
    )
    raw = json.loads(path.read_text())
    raw["tasks"][0]["output"] = raw["files"][0]["source"]
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        read_job(path)


def test_job_when_kernel_lock_is_held_then_second_runner_refused(tmp_path):
    import fcntl

    folder, _ = setup_recording(tmp_path)
    path = create_job(
        str(folder), candidates="bypass", job_path=str(tmp_path / "job.json")
    )
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="already running"):
            run_job(path)


def test_job_when_no_diarization_selected_then_run_without_models(tmp_path):
    folder, _ = setup_recording(tmp_path)
    path = create_job(
        str(folder), candidates="bypass", job_path=str(tmp_path / "job.json")
    )
    assert read_job(path).processing.diarizer == "none"
    assert run_job(path, verbose=False)["status"] == "complete"


def test_job_when_same_speaker_id_in_different_files_then_apply_separate_choices(
    tmp_path,
):
    folder, turns = setup_recording(tmp_path)
    rate = 48000
    t = np.arange(rate) / rate
    wave = 0.1 * (np.sin(2 * np.pi * 300 * t) + np.sin(2 * np.pi * 8000 * t))
    sf.write(folder / "voice.wav", wave, rate)
    sf.write(folder / "second.wav", wave, rate)
    (turns / "second.json").write_text((turns / "voice.json").read_text())
    path = create_job(
        str(folder),
        candidates="bypass",
        job_path=str(tmp_path / "job.json"),
        diarization_dir=str(turns),
    )
    job = read_job(path)
    for index, file in enumerate(job.files):
        gain = 3 if index == 0 else -3
        job.variants[0].file_speakers[str(file.source)] = {
            "A": [
                {
                    "path": "builtin:high-shelf",
                    "parameters": {"gain_db": gain, "cutoff_frequency_hz": 3000},
                }
            ]
        }
    save_job(path, job)
    assert (
        run_job(path, workers=2, file_workers=2, verbose=False)["status"] == "complete"
    )
    ratios = []
    for task in read_job(path).tasks:
        audio, _ = sf.read(task.output, always_2d=True)
        spectrum = np.abs(np.fft.rfft(audio[:, 0]))
        ratios.append(20 * np.log10(spectrum[8000] / spectrum[300]))
    assert ratios[0] - ratios[1] > 5, (
        "Each file's speaker A receives its own audible brightness choice"
    )
