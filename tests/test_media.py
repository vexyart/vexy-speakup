# this_file: tests/test_media.py
"""Actual codec and video remux checks, not mocked FFmpeg success."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from pedalboard import Gain, Pedalboard

from vexy_speakup.media import command, decode, normalize, probe, publish
from vexy_speakup.pipeline import export_mastered_fragments
from vexy_speakup.vst import render_chunk, render_master


@pytest.fixture
def source(tmp_path):
    rate = 48000
    x = 0.05 * np.sin(np.arange(rate * 2) * 2 * np.pi * 220 / rate)
    audio = tmp_path / "source.wav"
    sf.write(audio, np.stack([x, x], axis=1), rate, subtype="FLOAT")
    return audio


@pytest.mark.parametrize("extension", [".mp3", ".m4a", ".flac", ".ogg", ".opus"])
def test_encoded_audio_decodes_with_target_loudness_and_peak(source, extension):
    master = source.with_name("master.wav")
    normalize(source, master, -16, -2)
    output = source.with_name("result" + extension)
    receipt = publish(source, master, output, False, -2, -16, False)
    assert output.is_file(), "Encoded output must exist"
    assert float(receipt["encoded_loudness"]["input_tp"]) <= -1.9, (
        "Encoded peaks must remain safe"
    )
    decoded = source.with_name("decoded.wav")
    decode(output, decoded)
    assert abs(sf.info(decoded).duration - 2) < 0.1, "Codec delay must remain bounded"


def test_video_remux_keeps_video_packet_payload_and_audio_duration(source):
    video = source.with_name("meeting.mp4")
    command(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:r=10",
            "-i",
            source,
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            video,
        ]
    )
    output = video.with_name("meeting_improved.mp4")
    receipt = publish(video, source, output, True, -2, -16, False)

    def packet_hash(path):
        return command(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                path,
                "-map",
                "0:v:0",
                "-c",
                "copy",
                "-f",
                "hash",
                "-",
            ]
        )

    assert packet_hash(video) == packet_hash(output), (
        "Video packet bytes must be unchanged"
    )
    assert len(probe(output)["streams"]) == 2, (
        "Video and replacement audio both present"
    )
    assert float(receipt["encoded_loudness"]["input_tp"]) <= -1.9


def test_master_streaming_matches_single_render_and_drains_latency(source):
    output = source.with_name("rendered.wav")
    render_master(source, output, [], source.with_name("receipt.json"))
    x, _ = sf.read(source, dtype="float32", always_2d=True)
    y, _ = sf.read(output, dtype="float32", always_2d=True)
    np.testing.assert_array_equal(
        x, y, err_msg="Empty mastering chain preserves every sample"
    )
    amplified = render_chunk(Pedalboard([Gain(gain_db=3)]), x, 48000)
    assert amplified.shape == x.shape, "Tail crop preserves input length"
    np.testing.assert_allclose(amplified, x * 10 ** (3 / 20), rtol=1e-6)


def test_silent_normalization_preserves_exact_duration(tmp_path):
    source = tmp_path / "silence.wav"
    sf.write(source, np.zeros((48000, 2), np.float32), 48000)
    dest = tmp_path / "normalized.wav"
    normalize(source, dest, -16, -2)
    assert sf.info(dest).frames == 48000, "Silence must not gain duration or noise"
    assert np.max(np.abs(sf.read(dest)[0])) == 0


def test_fire_cli_processes_disjoint_speakers_and_preserves_timeline(source):
    turns = source.with_name("turns.json")
    turns.write_text(
        json.dumps(
            [
                {"start": 0.2, "end": 1, "speaker": "A"},
                {"start": 0.8, "end": 1.8, "speaker": "B"},
            ]
        )
    )
    command(
        [
            sys.executable,
            "-m",
            "vexy_speakup",
            "run",
            source,
            "--profile_name=bypass",
            "--evaluate=False",
            f"--diarization_json={turns}",
        ]
    )
    work = source.with_suffix("")
    latest = json.loads((work / "latest.json").read_text())
    report = json.loads(Path(latest["report"]).read_text())
    session = Path(latest["run"])
    assert report["status"] == "complete", "Whole Fire CLI finishes"
    assert report["speakers"] == ["A", "B"], "Speaker identity preserved"
    assert abs(report["overlap_s"] - 0.2) < 1e-8, "Overlap processed once"
    assert sf.info(session / "master.wav").frames == sf.info(source).frames
    assert (session / "speakers/_overlap").is_dir(), "Mixed overlap explicitly labelled"
    assert source.with_name("source_improved.wav").is_file(), (
        "Default output path contract"
    )


def test_native_latency_is_compensated_without_losing_tail(source):
    from pedalboard_native._internal import AddLatency

    x, rate = sf.read(source, dtype="float32", always_2d=True)
    y = render_chunk(Pedalboard([AddLatency(samples=8192)]), x, rate)
    np.testing.assert_allclose(
        x, y, atol=1e-7, err_msg="Latency compensation preserves tail and timing"
    )


@pytest.mark.parametrize("extension,codec", [(".m4a", "aac"), (".mp3", "libmp3lame")])
def test_fire_cli_decodes_compressed_input_and_keeps_its_extension(
    source, extension, codec
):
    compressed = source.with_name("compressed" + extension)
    command(["ffmpeg", "-v", "error", "-i", source, "-c:a", codec, compressed])
    turns = source.with_name("compressed-turns.json")
    turns.write_text(json.dumps([{"start": 0, "end": 1.5, "speaker": "S"}]))
    command(
        [
            sys.executable,
            "-m",
            "vexy_speakup",
            "run",
            compressed,
            "--profile_name=bypass",
            "--evaluate=False",
            f"--diarization_json={turns}",
        ]
    )
    output = source.with_name("compressed_improved" + extension)
    assert output.is_file(), "Input audio extension retained"
    decoded = source.with_name("result-decoded.wav")
    decode(output, decoded)
    assert abs(sf.info(decoded).duration - 2) < 0.1, (
        "Compressed roundtrip timeline preserved"
    )


def test_video_audio_extraction_preserves_delayed_audio_start(source):
    video = source.with_name("delayed.mp4")
    command(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:r=10",
            "-itsoffset",
            "0.4",
            "-i",
            source,
            "-t",
            "2.4",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            video,
        ]
    )
    audio = source.with_name("aligned.wav")
    decode(video, audio, timeline=True)
    x, rate = sf.read(audio, always_2d=True)
    assert np.max(np.abs(x[: int(0.3 * rate)])) < 1e-6, (
        "Leading audio offset must become silence"
    )
    assert np.max(np.abs(x[int(0.5 * rate) : int(1 * rate)])) > 0.01, (
        "Delayed speech must still be present"
    )


def test_deliverable_fragments_are_exact_cuts_from_master(source):
    fragment = source.with_name("fragment.wav")
    job = {
        "speakers": ["A"],
        "start_frame": 24000,
        "end_frame": 48000,
        "fragment": str(fragment),
    }
    export_mastered_fragments(source, [job])
    cut, rate = sf.read(job["mastered_fragment"], always_2d=True)
    master, _ = sf.read(source, always_2d=True)
    assert sf.info(job["mastered_fragment"]).subtype == "PCM_24", (
        "Deliverable bit depth"
    )
    assert len(cut) == 24000 and rate == 48000, (
        "Mastered fragment retains source positions"
    )
    np.testing.assert_allclose(cut, master[24000:48000], atol=1.2e-7)


def test_preview_does_not_conflict_with_existing_full_output(source):
    full = source.with_name("source_improved.wav")
    full.write_bytes(b"existing full output")
    turns = source.with_name("preview-turns.json")
    turns.write_text(json.dumps([{"start": 0, "end": 0.8, "speaker": "A"}]))
    command(
        [
            sys.executable,
            "-m",
            "vexy_speakup",
            "run",
            source,
            "--duration=1",
            "--profile_name=bypass",
            "--evaluate=False",
            f"--diarization_json={turns}",
        ]
    )
    assert full.read_bytes() == b"existing full output", (
        "Existing full export remains unchanged"
    )
    assert source.with_name("source_improved_preview.wav").is_file(), (
        "Preview uses its own suffix"
    )


def test_video_can_explicitly_export_audio_only(source):
    video = source.with_name("input-video.mp4")
    command(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:r=10",
            "-i",
            source,
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            video,
        ]
    )
    output = source.with_name("audio-only.wav")
    turns = source.with_name("video-turns.json")
    turns.write_text(json.dumps([{"start": 0, "end": 1.5, "speaker": "A"}]))
    command(
        [
            sys.executable,
            "-m",
            "vexy_speakup",
            "run",
            video,
            "--profile_name=bypass",
            "--evaluate=False",
            f"--diarization_json={turns}",
            f"--output_path={output}",
        ]
    )
    assert [s["codec_type"] for s in probe(output)["streams"]] == ["audio"], (
        "Explicit WAV omits video"
    )
    assert abs(sf.info(output).duration - 2) < 0.1
