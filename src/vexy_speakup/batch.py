# this_file: src/vexy_speakup/batch.py
"""Discover media and save immutable processing choices for later execution."""

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from platformdirs import user_data_path

from .effects import brighten
from .job_schema import InputFile, Job, Processing, Task, Variant
from .media import sha
from .profiles import profile
from .settings import read_settings

MEDIA_SUFFIXES = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
    ".opus",
    ".aac",
    ".aif",
    ".aiff",
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".m4v",
    ".caf",
    ".wma",
    ".ac3",
}


def discover(
    folder: Path, recursive: bool = False, exclude: Path | None = None
) -> list[Path]:
    """List media in stable order, excluding the output subtree on recursive scans."""
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    paths = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(
        p
        for p in paths
        if p.is_file()
        and p.suffix.lower() in MEDIA_SUFFIXES
        and (exclude is None or not p.resolve().is_relative_to(exclude.resolve()))
    )


def save_job(path: Path, job: Job) -> None:
    """Atomically replace state so an interrupted write cannot corrupt the queue."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as writer:
        temporary = Path(writer.name)
        writer.write(job.model_dump_json(indent=2))
        writer.flush()
        os.fsync(writer.fileno())
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_job(path: str | Path) -> Job:
    """Parse the complete job contract before scheduling any work."""
    return Job.model_validate_json(Path(path).expanduser().read_text())


def create_job(
    input_dir: str,
    candidates: str = "",
    output_dir: str = "",
    job_path: str = "",
    recursive: bool = False,
    diarization_dir: str = "",
    diarizer: str = "none",
) -> Path:
    """Schedule chosen candidate variants without processing media or loading models.

    Supplied turns live in diarization_dir at matching relative paths with .json
    suffixes. The job snapshots their contents, all chain specs and source hashes.
    """
    folder = Path(input_dir).expanduser().resolve()
    output = (
        Path(output_dir).expanduser().resolve()
        if output_dir
        else folder / "speakup-output"
    )
    paths = discover(folder, recursive, output)
    if not paths:
        raise ValueError("No media files found in input folder")
    settings = read_settings()
    names = candidates.split(",") if candidates else list(settings["candidates"])
    variants = []
    for name in names:
        name = name.strip()
        candidate = settings["candidates"].get(name)
        config = brighten(profile(name), settings["processing"]["brightness_db"])
        variants.append(
            Variant(
                name=name,
                suffix=candidate["suffix"] if candidate else "_" + name,
                config=config,
            )
        )
    files = []
    for source in paths:
        relative = source.relative_to(folder)
        annotation = Path(diarization_dir).expanduser() / relative.with_suffix(".json")
        turns = json.loads(annotation.read_text()) if diarization_dir else None
        files.append(
            InputFile(
                source=source.resolve(),
                relative=relative,
                sha256=sha(source),
                turns=turns,
            )
        )
    identifier = uuid4().hex
    tasks = [
        Task(
            file=f,
            variant=v,
            output=output
            / row.relative.with_name(
                row.relative.stem + variant.suffix + row.relative.suffix
            ),
        )
        for f, row in enumerate(files)
        for v, variant in enumerate(variants)
    ]
    options = {
        k: settings["processing"][k]
        for k in ("workers", "max_chunk", "target_lufs", "true_peak")
    }
    job = Job(
        id=identifier,
        created_at=datetime.now(UTC).isoformat(),
        output_directory=output,
        files=files,
        variants=variants,
        tasks=tasks,
        processing=Processing(diarizer=diarizer, **options),
    )
    path = (
        Path(job_path).expanduser().resolve()
        if job_path
        else user_data_path("vexy-speakup", appauthor=False)
        / "jobs"
        / (identifier + ".json")
    )
    if path.exists():
        raise FileExistsError(f"Job already exists: {path}")
    save_job(path, job)
    return path
