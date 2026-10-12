# this_file: src/vexy_speakup/pipeline.py
"""Speaker processing, bounded level correction and timeline-preserving assembly."""

import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf

from .levels import level_gain, loudness
from .media import RATE, command, normalize, write_json
from .turns import partition

WORKER = [sys.executable, "-m", "vexy_speakup"]


def prepare_jobs(
    audio: Path, turns: list[dict], work: Path, config: dict, max_chunk: float
) -> tuple[list[dict], dict]:
    """Extract half-second context and keep sample-exact start/end offsets."""
    jobs, groups = [], defaultdict(list)
    with sf.SoundFile(audio) as reader:
        duration, frames = len(reader) / RATE, len(reader)
        for index, row in enumerate(partition(turns, duration, max_chunk)):
            start, end = round(row["start"] * RATE), round(row["end"] * RATE)
            if end <= start:
                continue
            speakers = row["speakers"]
            owner = (
                speakers[0]
                if len(speakers) == 1
                else "_overlap"
                if speakers
                else "_background"
            )
            directory = work / "speakers" / owner
            directory.mkdir(parents=True, exist_ok=True)
            a, b = max(0, start - RATE // 2), min(frames, end + RATE // 2)
            reader.seek(a)
            context = reader.read(b - a, dtype="float32", always_2d=True)
            path = directory / f"{index:06d}"
            sf.write(str(path) + "-context.wav", context, RATE, subtype="FLOAT")
            job = {
                **row,
                "index": index,
                "owner": owner,
                "start_frame": start,
                "end_frame": end,
                "crop_start": start - a,
                "input": str(path) + "-context.wav",
                "output": str(path) + "-render.wav",
                "fragment": str(path) + ".wav",
            }
            jobs.append(job)
            if speakers:
                groups[owner].append(job)
    write_json(work / "fragments.json", jobs)
    return jobs, groups


def render_speakers(
    groups: dict, work: Path, config: dict, timeout: int, verbose: bool
) -> None:
    """Crash and timeout isolation around each speaker's native plugin process."""
    for owner, jobs in groups.items():
        if verbose:
            print(f"Processing {owner}: {len(jobs)} fragments", flush=True)
        specs = config.get("speakers", {}).get(owner, config["speech"])
        job_file = work / "speakers" / owner / "jobs.json"
        write_json(job_file, {"jobs": jobs, "specs": specs})
        command(
            [*WORKER, "_render", f"--job_file={job_file}"],
            timeout,
            job_file.with_suffix(".log"),
        )


def collect_levels(jobs: list[dict], target: float) -> dict[str, float]:
    """Robust per-speaker baseline; short turns do not dominate the calibration."""
    by_speaker = defaultdict(list)
    for job in jobs:
        if not job["speakers"]:
            continue
        data, _ = sf.read(job["output"], dtype="float32", always_2d=True)
        start, n = job["crop_start"], job["end_frame"] - job["start_frame"]
        measured = loudness(data[start : start + n], RATE)
        job["loudness_before"] = measured if math.isfinite(measured) else None
        if math.isfinite(measured):
            by_speaker[job["owner"]].append((measured, n))
    gains = {}
    for owner, values in by_speaker.items():
        values.sort()
        midpoint = sum(n for _, n in values) / 2
        cumulative = 0
        for value, n in values:
            cumulative += n
            if cumulative >= midpoint:
                gains[owner] = float(np.clip(target - value, -12, 12))
                break
    return gains


def assemble(audio: Path, jobs: list[dict], work: Path, target: float) -> Path:
    """Write each timeline sample once; shared overlaps stay a single mixed fragment."""
    gains = collect_levels(jobs, target)
    output = work / "assembled.wav"
    with (
        sf.SoundFile(audio) as reader,
        sf.SoundFile(
            output, "w", samplerate=RATE, channels=2, subtype="FLOAT", format="RF64"
        ) as writer,
    ):
        for job in jobs:
            n = job["end_frame"] - job["start_frame"]
            reader.seek(job["start_frame"])
            original = reader.read(n, dtype="float32", always_2d=True)
            result = original.copy()
            if job["speakers"]:
                data, _ = sf.read(job["output"], dtype="float32", always_2d=True)
                result = data[job["crop_start"] : job["crop_start"] + n].copy()
                gain = level_gain(result, RATE, target, gains.get(job["owner"], 0))
                result *= 10 ** (gain / 20)
                job["gain_db"] = gain
                fade = min(round(0.01 * RATE), n // 2)
                if fade:
                    ramp = np.linspace(0, 1, fade, dtype=np.float32)[:, None]
                    result[:fade] = original[:fade] * (1 - ramp) + result[:fade] * ramp
                    result[-fade:] = original[-fade:] * ramp + result[-fade:] * (
                        1 - ramp
                    )
            sf.write(job["fragment"], result, RATE, subtype="FLOAT")
            writer.write(result)
        if writer.tell() != len(reader):
            raise ValueError("Assembly changed timeline length")
    write_json(work / "fragments.json", jobs)
    write_json(work / "speaker-gains.json", gains)
    return output


def master(
    assembled: Path, work: Path, config: dict, target: float, peak: float, timeout: int
) -> tuple[Path, dict]:
    """Pre-level, continuous VST mastering, then measured final loudness/true peak."""
    pre = work / "premaster.wav"
    before = normalize(assembled, pre, target, peak)
    job_file = work / "master-job.json"
    rendered = work / "master-vst.wav"
    write_json(
        job_file,
        {"source": str(pre), "output": str(rendered), "specs": config["master"]},
    )
    command(
        [*WORKER, "_master", f"--job_file={job_file}"],
        timeout,
        work / "master.log",
    )
    final = work / "master.wav"
    after = normalize(rendered, final, target, peak)
    if sf.info(final).frames != sf.info(assembled).frames:
        raise ValueError("Mastering changed timeline length")
    return final, {"premaster": before, "final": after}


def export_mastered_fragments(final: Path, jobs: list[dict]) -> None:
    """Cut deliverable fragments from the final master, retaining global limiter behavior."""
    with sf.SoundFile(final) as reader:
        for job in jobs:
            if not job["speakers"]:
                continue
            reader.seek(job["start_frame"])
            x = reader.read(
                job["end_frame"] - job["start_frame"], dtype="float32", always_2d=True
            )
            output = Path(job["fragment"]).with_name(
                Path(job["fragment"]).stem + "-mastered.wav"
            )
            sf.write(output, x, reader.samplerate, subtype="PCM_24")
            job["mastered_fragment"] = str(output)
