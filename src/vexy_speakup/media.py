# this_file: src/vexy_speakup/media.py
"""FFmpeg decoding, loudness measurement and atomic audio/video publication."""

import hashlib
import json
import math
import os
from pathlib import Path

from .cancel import check
from .process import capture

RATE = 48000


def command(args: list[str], timeout: int = 1800, log: Path | None = None) -> str:
    """Run an argv command with a deadline and retain failures for diagnosis."""
    result = capture(list(map(str, args)), timeout)
    if log:
        log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(
            f"{args[0]} failed ({result.returncode}): {result.stderr[-2000:]}"
        )
    return result.stdout + result.stderr


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        while block := stream.read(1024 * 1024):
            check()
            digest.update(block)
        return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def destinations(
    source: Path, work_dir: str, output_path: str, suffix: str
) -> tuple[Path, Path]:
    work = Path(work_dir).expanduser().resolve() if work_dir else source.with_suffix("")
    output = (
        Path(output_path).expanduser().resolve()
        if output_path
        else source.with_name(source.stem + suffix + source.suffix)
    )
    if source == output or source == work or output == work or source in work.parents:
        raise ValueError("Input, output file and work directory must be distinct")
    return work, output


def probe(path: Path) -> dict:
    return json.loads(
        command(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                path,
            ]
        )
    )


def decode(
    source: Path,
    dest: Path,
    start: float = 0,
    duration: float = 0,
    timeline: bool = False,
) -> None:
    args = [
        "ffmpeg",
        "-v",
        "error",
        "-n",
        "-ss",
        str(start),
        "-i",
        source,
        "-map",
        "0:a:0",
        "-vn",
    ]
    if duration:
        args += ["-t", str(duration)]
    if timeline:
        args += ["-af", "aresample=async=1:first_pts=0"]
    command(
        args
        + ["-ar", str(RATE), "-ac", "2", "-c:a", "pcm_f32le", "-rf64", "auto", dest]
    )


def measure(path: Path, target: float = -16, peak: float = -2) -> dict:
    result = command(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            path,
            "-af",
            f"loudnorm=I={target}:TP={peak}:LRA=7:print_format=json",
            "-f",
            "null",
            "-",
        ]
    )
    return json.loads(result[result.rfind("{") : result.rfind("}") + 1])


def normalize(source: Path, dest: Path, target: float, peak: float) -> dict:
    """Two-pass EBU R128; retain silence without an undefined gain."""
    first = measure(source, target, peak)
    filt = f"loudnorm=I={target}:TP={peak}:LRA=7:print_format=json"
    if math.isfinite(float(first["input_i"])):
        filt += (
            f":measured_I={first['input_i']}:measured_TP={first['input_tp']}"
            f":measured_LRA={first['input_lra']}:measured_thresh={first['input_thresh']}"
            f":offset={first['target_offset']}:linear=true"
        )
    else:
        filt = "anull"
    command(
        [
            "ffmpeg",
            "-v",
            "error",
            "-n",
            "-i",
            source,
            "-af",
            filt,
            "-ar",
            str(RATE),
            "-c:a",
            "pcm_f32le",
            "-rf64",
            "auto",
            dest,
        ]
    )
    return {"before": first, "after": measure(dest, target, peak)}


def publish(
    source: Path,
    audio: Path,
    output: Path,
    video: bool,
    peak: float,
    target: float,
    force: bool,
) -> dict:
    """Remux unchanged video, encode one improved audio track, check encoded true peak."""
    codecs = {
        ".wav": "pcm_s24le",
        ".aiff": "pcm_s24be",
        ".aif": "pcm_s24be",
        ".flac": "flac",
        ".mp3": "libmp3lame",
        ".ogg": "libopus",
        ".opus": "libopus",
        ".webm": "libopus",
    }
    codec = codecs.get(output.suffix.lower(), "aac")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = output.with_name(f".{output.stem}.{os.getpid()}.partial{output.suffix}")
    base = ["ffmpeg", "-v", "error", "-y"]
    if video:
        base += [
            "-i",
            source,
            "-i",
            audio,
            "-map",
            "0:v",
            "-map",
            "1:a:0",
            "-map",
            "0:s?",
            "-map_metadata",
            "0",
            "-c:v",
            "copy",
            "-c:s",
            "copy",
        ]
    else:
        base += ["-i", audio, "-map", "0:a:0"]
    base += ["-c:a", codec]
    if codec in {"aac", "libmp3lame", "libopus", "libvorbis"}:
        base += ["-b:a", "192k"]
    gain = 0.0
    try:
        for attempt in range(3):
            command(base + ["-af", f"volume={gain}dB", stage])
            stats = measure(stage, target, peak)
            actual = float(stats["input_tp"])
            if actual <= peak + 0.1:
                if output.exists() and not force:
                    raise FileExistsError(output)
                stage.replace(output)
                return {
                    "codec": codec,
                    "encoded_loudness": stats,
                    "codec_gain_db": gain,
                    "sha256": sha(output),
                }
            gain -= actual - peak + 0.15
        raise ValueError("Encoded true-peak limit could not be satisfied")
    finally:
        stage.unlink(missing_ok=True)
