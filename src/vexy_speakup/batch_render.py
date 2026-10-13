# this_file: src/vexy_speakup/batch_render.py
"""Shared decoding, diarization and full-pipeline rendering for durable jobs."""

import json
from copy import deepcopy
from pathlib import Path

import soundfile as sf

from .cli import run
from .job_schema import Job, Task
from .media import decode, probe, sha, write_json
from .models import diarize


def _prepare(job: Job, index: int, work: Path) -> tuple[Path, Path]:
    """Decode/diarize each original once, sharing the complete timeline across variants."""
    file = job.files[index]
    folder = work / f"input-{index:05d}"
    folder.mkdir(parents=True, exist_ok=True)
    audio, annotation = folder / "input.wav", folder / "supplied-turns.json"
    info = probe(file.source)
    video = any(
        s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")
        for s in info["streams"]
    )
    decode(file.source, audio, timeline=video)
    supplied = ""
    if file.turns is not None:
        write_json(annotation, file.turns)
        supplied = str(annotation)
    turns = diarize(
        audio, folder, job.processing.diarizer, supplied, sf.info(audio).duration, 1800
    )
    write_json(annotation, turns)
    return audio, annotation


def _execute(
    job: Job,
    task: Task,
    prepared: tuple[Path, Path],
    work: Path,
    workers: int,
    force: bool,
    verbose: bool,
) -> dict:
    """Use the same full pipeline as previews and ordinary CLI runs."""
    variant, file = job.variants[task.variant], job.files[task.file]
    directory = work / f"task-{task.file:05d}-{task.variant:03d}"
    directory.mkdir(parents=True, exist_ok=True)
    config = deepcopy(variant.config)
    selected = variant.file_speakers.get(str(file.source), {})
    turns = json.loads(prepared[1].read_text())
    if selected.keys() - ({t["speaker"] for t in turns} | {"_overlap"}):
        raise ValueError("Speaker choices do not match this file's diarization")
    config.setdefault("speakers", {}).update(selected)
    config_file = directory / "chain.json"
    write_json(config_file, config)
    task.output.parent.mkdir(parents=True, exist_ok=True)
    options = job.processing.model_dump(exclude={"workers"})
    run(
        input_path=str(file.source),
        work_dir=str(directory),
        output_path=str(task.output),
        profile_name=variant.name,
        config_path=str(config_file),
        workers=workers,
        diarization_json=str(prepared[1]),
        _decoded_audio=str(prepared[0]),
        brightness_db=0,
        force=force,
        verbose=verbose,
        **options,
    )
    latest = json.loads((directory / "latest.json").read_text())
    return {"output_sha256": sha(task.output), "report": latest["report"]}


def _completed(job: Job, task: Task, work: Path) -> bool:
    """Recorded completion requires the unchanged output and a successful run report."""
    if task.status != "complete":
        if task.status not in {"running", "cancelled"}:
            return False
        latest = work / f"task-{task.file:05d}-{task.variant:03d}" / "latest.json"
        if not latest.is_file():
            return False
        task.report = json.loads(latest.read_text())["report"]
        completed_report = json.loads(Path(task.report).read_text())
        if completed_report.get("status") != "complete" or not completed_report.get(
            "output_sha256"
        ):
            return False
        task.output_sha256 = completed_report["output_sha256"]
    if not task.output.is_file() or sha(task.output) != task.output_sha256:
        raise ValueError(
            "Completed output changed or is missing; rerun with force to replace it"
        )
    report = json.loads(Path(task.report).read_text())
    if (
        report.get("status") != "complete"
        or Path(report["output"]).resolve() != task.output.resolve()
    ):
        raise ValueError("Completed task has no matching successful report")
    config = deepcopy(job.variants[task.variant].config)
    config.setdefault("speakers", {}).update(
        job.variants[task.variant].file_speakers.get(
            str(job.files[task.file].source), {}
        )
    )
    if (
        report.get("config") != config
        or report.get("input_sha256") != job.files[task.file].sha256
    ):
        raise ValueError(
            "Completed task does not match the saved source and chain choices"
        )
    for key in ("target_lufs", "true_peak", "max_chunk"):
        if report.get(key) != getattr(job.processing, key):
            raise ValueError(f"Completed task has different {key} settings")
    task.status = "complete"
    return True
