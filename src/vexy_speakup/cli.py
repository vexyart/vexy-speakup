# this_file: src/vexy_speakup/cli.py
"""Diarize, restore, level and master speech, retaining video and timeline."""

import json
import math
from datetime import datetime
from pathlib import Path

import fire
import soundfile as sf

from . import __version__
from .audit import attempts, evaluate_windows, inspect, inventory, probe_plugin
from .effects import brighten
from .media import decode, destinations, probe, publish, sha, write_json
from .models import deepfilter, diarize
from .pipeline import (
    assemble,
    export_mastered_fragments,
    master,
    prepare_jobs,
    render_speakers,
)
from .settings import config_file, init_config, read_settings, validate_chain
from .vst import profile, render_jobs, render_master


def run(
    input_path: str,
    work_dir: str = "",
    output_path: str = "",
    suffix: str = "_improved",
    profile_name: str | None = None,
    config_path: str = "",
    diarizer: str = "mlx",
    diarization_json: str = "",
    target_lufs: float | None = None,
    true_peak: float | None = None,
    max_chunk: float | None = None,
    start: float = 0,
    duration: float = 0,
    evaluate: bool = True,
    metrics_python: str = "",
    ai: str = "none",
    timeout: int = 1800,
    force: bool = False,
    verbose: bool = False,
    workers: int | None = None,
    brightness_db: float | None = None,
    _decoded_audio: str = "",
) -> str:
    """Process audio/video. Preview with --start/--duration; default processes the full file.

    --diarization_json accepts [{start,end,speaker}], or a turns/segments report.
    --config_path accepts speech/master VST chains and optional speakers overrides.
    --ai=deepfilter adds the locally cached DF3 CoreML pass before VSTs.
    Evaluation uses three up-to-30s speech windows, not the entire recording.
    """
    settings = read_settings()["processing"]
    profile_name = settings["profile"] if profile_name is None else profile_name
    target_lufs = settings["target_lufs"] if target_lufs is None else target_lufs
    true_peak = settings["true_peak"] if true_peak is None else true_peak
    max_chunk = settings["max_chunk"] if max_chunk is None else max_chunk
    workers = settings["workers"] if workers is None else workers
    brightness_db = (
        settings["brightness_db"] if brightness_db is None else brightness_db
    )
    if type(workers) is not int or not 1 <= workers <= 128:
        raise ValueError("workers must be an integer in [1,128]")
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
    config = brighten(config, brightness_db)
    validate_chain(config)
    work.mkdir(parents=True, exist_ok=True)
    session = work / datetime.now().astimezone().strftime("run-%Y%m%d-%H%M%S-%f")
    session.mkdir()
    report = {
        "input": str(source),
        "input_sha256": sha(source),
        "output": str(output),
        "video": video,
        "output_video": output_video,
        "profile": profile_name,
        "config": config,
        "ai": ai,
        "diarizer": diarizer,
        "preview_start": start,
        "target_lufs": target_lufs,
        "true_peak": true_peak,
        "status": "running",
        "workers": workers,
        "max_chunk": max_chunk,
        "brightness_db": brightness_db,
    }
    write_json(session / "report.json", report)
    try:
        print(f"Work: {session}", flush=True)
        audio = Path(_decoded_audio) if _decoded_audio else session / "input.wav"
        if _decoded_audio:
            cached = sf.info(audio)
            if start or duration or cached.samplerate != 48000 or cached.channels != 2:
                raise ValueError(
                    "Prepared audio requires a full 48 kHz stereo timeline"
                )
            report["prepared_audio"] = str(audio)
        else:
            decode(source, audio, start, duration, timeline=video)
        seconds = sf.info(audio).duration
        turns = diarize(audio, session, diarizer, diarization_json, seconds, timeout)
        if verbose:
            print(f"Prepared {seconds:.2f}s: {len(turns)} speech intervals", flush=True)
        restored = audio
        if ai == "deepfilter":
            mono = session / "deepfilter-mono.wav"
            deepfilter(audio, mono, session, timeout)
            restored = session / "deepfilter.wav"
            decode(mono, restored)
            if sf.info(restored).frames != sf.info(audio).frames:
                raise ValueError("AI enhancement changed duration")
        jobs, groups = prepare_jobs(restored, turns, session, config, max_chunk)
        render_speakers(groups, session, config, timeout, verbose, workers)
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
        report["output_sha256"] = sha(output)
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


def gui(input_dir: str = "", port: int = 8765, open_browser: bool = True) -> None:
    """Open the local browser listening interface (install vexy-speakup[gui])."""
    try:
        from .web import gui as launch_gui
    except ModuleNotFoundError as exc:
        if exc.name in {"fastapi", "uvicorn"}:
            raise RuntimeError(
                "Install the GUI extra: uv tool install 'vexy-speakup[gui]'"
            ) from exc
        raise
    launch_gui(input_dir, port, open_browser)


def main() -> None:
    from . import assets
    from .batch import create_job
    from .queue import batch, run_job

    result = fire.Fire(
        {
            "run": run,
            "gui": gui,
            "batch": batch,
            "schedule": create_job,
            "job": run_job,
            "attempts": attempts,
            "inspect": inspect,
            "inventory": inventory,
            "probe": probe_plugin,
            "version": version,
            "assets": {"fetch": assets.fetch, "list": assets.listing},
            "config": {
                "path": lambda: str(config_file()),
                "init": lambda output_path="": str(init_config(output_path)),
                "show": lambda: json.dumps(read_settings(), indent=2),
            },
            "_render": _render,
            "_master": _master,
        }
    )
    if isinstance(result, dict) and result.get("status") == "failed":
        raise SystemExit(1)
    if isinstance(result, dict) and result.get("status") == "cancelled":
        raise SystemExit(130)


if __name__ == "__main__":
    main()
