# this_file: src/vexy_speakup/cli.py
"""Diarize, restore, level and master speech, retaining video and timeline."""

import json
import math
import os
from datetime import datetime
from pathlib import Path

import fire
import soundfile as sf

from . import __version__
from .audit import attempts, evaluate_windows, inspect, inventory, probe_plugin
from .media import decode, destinations, probe, publish, sha, write_json
from .models import deepfilter, diarize
from .pipeline import (
    assemble,
    export_mastered_fragments,
    master,
    prepare_jobs,
    render_speakers,
)
from .vst import profile, render_jobs, render_master


def run(
    input_path: str,
    work_dir: str = "",
    output_path: str = "",
    suffix: str = "_improved",
    profile_name: str = "dx35",
    config_path: str = "",
    diarizer: str = "mlx",
    diarization_json: str = "",
    target_lufs: float = -16,
    true_peak: float = -2,
    max_chunk: float = 30,
    start: float = 0,
    duration: float = 0,
    evaluate: bool = True,
    metrics_python: str = "",
    ai: str = "none",
    timeout: int = 1800,
    force: bool = False,
    verbose: bool = False,
) -> str:
    """Process audio/video. Preview with --start/--duration; default processes the full file.

    --diarization_json accepts [{start,end,speaker}], or a turns/segments report.
    --config_path accepts speech/master VST chains and optional speakers overrides.
    --ai=deepfilter adds the locally cached DF3 CoreML pass before VSTs.
    Evaluation uses three up-to-30s speech windows, not the entire recording.
    """
    source = Path(input_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    values = (target_lufs, true_peak, max_chunk, start, duration)
    if not all(math.isfinite(v) for v in values) or not (
        -70 <= target_lufs <= -5 and -9 <= true_peak <= 0
    ):
        raise ValueError(
            "Require finite arguments, target_lufs [-70,-5], true_peak [-9,0]"
        )
    if (
        min(start, duration) < 0
        or max_chunk <= 0
        or timeout <= 0
        or ai not in {"none", "deepfilter"}
    ):
        raise ValueError("Invalid range, timeout, max_chunk or ai (none/deepfilter)")
    work, output = destinations(source, work_dir, output_path, suffix)
    if (start or duration) and not output_path:
        output = output.with_name(output.stem + "_preview" + output.suffix)
    if output.exists() and not force:
        raise FileExistsError(f"Output exists: {output}; use --force")
    info = probe(source)
    video = any(
        s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")
        for s in info["streams"]
    )
    output_video = video and output.suffix.lower() not in {
        ".wav",
        ".mp3",
        ".m4a",
        ".aac",
        ".flac",
        ".ogg",
        ".opus",
        ".aif",
        ".aiff",
        ".caf",
        ".wma",
        ".ac3",
    }
    if video and (start or duration):
        raise ValueError(
            "Video preview needs a pretrimmed video; audio previews support --start/--duration"
        )
    config = (
        json.loads(Path(config_path).expanduser().read_text())
        if config_path
        else profile(profile_name)
    )
    if not isinstance(config.get("speech"), list) or not isinstance(
        config.get("master"), list
    ):
        raise TypeError("Config requires speech and master chain arrays")
    work.mkdir(parents=True, exist_ok=True)
    session = work / datetime.now().astimezone().strftime("run-%Y%m%d-%H%M%S-%f")
    session.mkdir()
    os.environ["HF_HUB_OFFLINE"] = "1"
    report = {
        "input": str(source),
        "input_sha256": sha(source),
        "output": str(output),
        "video": video,
        "output_video": output_video,
        "profile": profile_name,
        "config": config,
        "ai": ai,
        "preview_start": start,
        "target_lufs": target_lufs,
        "true_peak": true_peak,
        "status": "running",
    }
    write_json(session / "report.json", report)
    try:
        print(f"Work: {session}", flush=True)
        audio = session / "input.wav"
        decode(source, audio, start, duration, timeline=video)
        seconds = sf.info(audio).duration
        turns = diarize(audio, session, diarizer, diarization_json, seconds, timeout)
        if verbose:
            print(f"Diarized {seconds:.2f}s: {len(turns)} turns", flush=True)
        restored = audio
        if ai == "deepfilter":
            mono = session / "deepfilter-mono.wav"
            deepfilter(audio, mono, session, timeout)
            restored = session / "deepfilter.wav"
            decode(mono, restored)
            if sf.info(restored).frames != sf.info(audio).frames:
                raise ValueError("AI enhancement changed duration")
        jobs, groups = prepare_jobs(restored, turns, session, config, max_chunk)
        render_speakers(groups, session, config, timeout, verbose)
        if verbose:
            print("Leveling fragments and assembling the original timeline", flush=True)
        joined = assemble(restored, jobs, session, target_lufs - 2)
        if verbose:
            print("Normalizing and mastering the complete recording", flush=True)
        final, levels = master(joined, session, config, target_lufs, true_peak, timeout)
        export_mastered_fragments(final, jobs)
        write_json(session / "fragments.json", jobs)
        report.update(
            {
                "duration_s": seconds,
                "fragments": len(jobs),
                "speakers": sorted({t["speaker"] for t in turns}),
                "overlap_s": sum(
                    j["end"] - j["start"] for j in jobs if len(j["speakers"]) > 1
                ),
                "levels": levels,
            }
        )
        if evaluate:
            if verbose:
                print("Evaluating matching speech windows", flush=True)
            report["evaluation"] = evaluate_windows(
                audio, final, turns, session, metrics_python
            )
        if verbose:
            print("Encoding and verifying final output levels", flush=True)
        report["publication"] = publish(
            source, final, output, output_video, true_peak, target_lufs, force
        )
        report["status"] = "complete"
        write_json(session / "report.json", report)
        write_json(
            work / "latest.json",
            {"run": str(session), "report": str(session / "report.json")},
        )
        print(f"Output: {output}", flush=True)
        return str(output)
    except Exception as exc:
        report.update({"status": "failed", "error": str(exc)})
        write_json(session / "report.json", report)
        raise


def _render(job_file: str) -> None:
    path = Path(job_file)
    job = json.loads(path.read_text())
    render_jobs(job["jobs"], job["specs"], path.with_name("vst-receipt.json"))


def _master(job_file: str) -> None:
    path = Path(job_file)
    job = json.loads(path.read_text())
    render_master(
        Path(job["source"]),
        Path(job["output"]),
        job["specs"],
        path.with_name("master-receipt.json"),
    )


def version() -> str:
    """Print the installed package version."""
    return __version__


def main() -> None:
    fire.Fire(
        {
            "run": run,
            "attempts": attempts,
            "inspect": inspect,
            "inventory": inventory,
            "probe": probe_plugin,
            "version": version,
            "_render": _render,
            "_master": _master,
        }
    )


if __name__ == "__main__":
    main()
