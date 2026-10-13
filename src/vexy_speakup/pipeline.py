# this_file: src/vexy_speakup/pipeline.py
"""Speaker processing, bounded level correction and timeline-preserving assembly."""

import math
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
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
    groups: dict,
    work: Path,
    config: dict,
    timeout: int,
    verbose: bool,
    workers: int = 1,
) -> None:
    """Render independent chunk shards in bounded, isolated native processes."""
    if type(workers) is not int or not 1 <= workers <= 128:
        raise ValueError("workers must be an integer in [1,128]")
    tasks = []
    for owner, jobs in groups.items():
        if verbose:
            print(f"Processing {owner}: {len(jobs)} fragments", flush=True)
        specs = config.get("speakers", {}).get(owner, config["speech"])
        for index in range(min(workers, len(jobs))):
            directory = work / "speakers" / owner
            if workers > 1:
                directory /= f"worker-{index:03d}"
            directory.mkdir(parents=True, exist_ok=True)
            job_file = directory / "jobs.json"
            write_json(job_file, {"jobs": jobs[index::workers], "specs": specs})
            tasks.append(job_file)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                copy_context().run,
                command,
                [*WORKER, "_render", f"--job_file={path}"],
                timeout,
                path.with_suffix(".log"),
            )
            for path in tasks
        ]
        try:
            for future in futures:
                future.result()
        except BaseException:
            for future in futures:
                future.cancel()
            raise


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


# Half-width of the crossfade at each fragment junction (40 ms in total).
BLEND = 0.02


def _signal(job: dict, reader: sf.SoundFile, a: int, b: int) -> np.ndarray:
    """A job's audio at absolute frames [a, b): processed render with its gain, else original.

    Renders carry half a second of context, so neighbours can be heard past the cut.
    """
    render = job.get("_render")
    offset = job["crop_start"] + a - job["start_frame"]
    if render is not None and offset >= 0 and offset + b - a <= len(render):
        return render[offset : offset + b - a] * np.float32(10 ** (job["_gain"] / 20))
    reader.seek(a)
    return reader.read(b - a, dtype="float32", always_2d=True)


def _blend(previous: dict, job: dict, reader: sf.SoundFile) -> None:
    """Linear crossfade centred on the junction, using both jobs' own audio either side."""
    a, b = previous["_body"], job["_body"]
    half = min(round(BLEND * RATE), len(a) // 2, len(b) // 2)
    if not half:
        return
    cut = job["start_frame"]
    ramp = ((np.arange(2 * half) + 0.5) / (2 * half)).astype(np.float32)[:, None]
    outgoing = np.concatenate([a[-half:], _signal(previous, reader, cut, cut + half)])
    incoming = np.concatenate([_signal(job, reader, cut - half, cut), b[:half]])
    mixed = outgoing * (1 - ramp) + incoming * ramp
    a[-half:], b[:half] = mixed[:half], mixed[half:]


def assemble(audio: Path, jobs: list[dict], work: Path, target: float) -> Path:
    """Write each timeline sample once; adjacent fragments crossfade into each other.

    Shared overlaps stay a single mixed fragment. A job is written only after its
    successor has blended into its tail, so at most two fragments sit in memory.
    """
    gains = collect_levels(jobs, target)
    output = work / "assembled.wav"
    with (
        sf.SoundFile(audio) as reader,
        sf.SoundFile(
            output, "w", samplerate=RATE, channels=2, subtype="FLOAT", format="RF64"
        ) as writer,
    ):

        def flush(job: dict) -> None:
            sf.write(job["fragment"], job["_body"], RATE, subtype="FLOAT")
            writer.write(job["_body"])
            for key in ("_body", "_render", "_gain"):
                job.pop(key, None)

        previous = None
        for job in jobs:
            n = job["end_frame"] - job["start_frame"]
            job["_gain"] = 0.0
            if job["speakers"]:
                job["_render"], _ = sf.read(job["output"], dtype="float32", always_2d=True)
                crop = job["_render"][job["crop_start"] : job["crop_start"] + n]
                if len(crop) != n:
                    raise ValueError(f"Render shorter than fragment {job['index']}")
                job["_gain"] = job["gain_db"] = level_gain(
                    crop, RATE, target, gains.get(job["owner"], 0)
                )
            job["_body"] = _signal(job, reader, job["start_frame"], job["end_frame"])
            if previous is not None:
                _blend(previous, job, reader)
                flush(previous)
            previous = job
        if previous is not None:
            flush(previous)
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
