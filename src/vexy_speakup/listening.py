# this_file: src/vexy_speakup/listening.py
"""Turn explicit listening preferences into the same versioned jobs used by the CLI."""

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from platformdirs import user_data_path

from .batch import read_job, save_job
from .job_schema import Job, Task, Variant
from .media import sha


def _choice(group: dict, name: str, gain: int) -> dict:
    rows = [
        v for v in group["variants"] if v["chain"] == name and v["brightness"] == gain
    ]
    if len(rows) != 1 or "output" not in rows[0] or rows[0].get("error"):
        raise ValueError("Choose a successfully rendered listening variant")
    row = rows[0]
    if (
        not Path(row["output"]).is_file()
        or sha(Path(row["output"])) != row["output_sha256"]
    ):
        raise ValueError("Listening clip changed or is missing; prepare previews again")
    return row


def dominant(turns: list[dict] | dict | None, speakers: dict) -> str:
    """Speaker with the most speech among those chosen; ties go to the first ID."""
    rows = turns.get("turns", []) if isinstance(turns, dict) else turns or []
    total = {name: 0.0 for name in speakers}
    for row in rows:
        if str(row["speaker"]) in total:
            total[str(row["speaker"])] += row["end"] - row["start"]
    return max(sorted(total), key=lambda name: total[name])


def schedule_choices(
    manifest: dict,
    global_choices: dict[str, int],
    speaker_choices: dict[str, dict],
    output_dir: str = "",
    job_path: str = "",
    master_name: str = "",
) -> Path:
    """Snapshot only listened variants; speaker IDs remain scoped to their source file.

    Per-speaker jobs master with `master_name`'s master chain, or with loudness and
    peak normalization only when it is empty. Overlapping speech uses the chain chosen
    for the file's dominant speaker.
    """
    base = read_job(manifest["base_job"])
    for file in base.files:
        if not file.source.is_file() or sha(file.source) != file.sha256:
            raise ValueError("Input changed since preview; prepare previews again")
    variants = []
    if manifest["speaker_mode"]:
        if set(speaker_choices) != {g["id"] for g in manifest["groups"]}:
            raise ValueError("Choose a variant for every file/speaker")
        master = []
        if master_name:
            chosen = [v for v in base.variants if v.name == master_name]
            if not chosen:
                raise ValueError(f"Unknown master chain: {master_name}")
            master = deepcopy(chosen[0].config["master"])
        variant = Variant(
            name="per-speaker",
            suffix="_speakers",
            config={"speech": [], "speakers": {}, "master": master},
        )
        for group in manifest["groups"]:
            selected = speaker_choices[group["id"]]
            row = _choice(group, selected["chain"], selected["brightness"])
            variant.file_speakers.setdefault(group["source"], {})[group["speaker"]] = (
                deepcopy(row["config"]["speech"])
            )
        for file in base.files:
            chains = variant.file_speakers.get(str(file.source), {})
            if chains:
                chains["_overlap"] = deepcopy(chains[dominant(file.turns, chains)])
        variant.file_speakers = dict(variant.file_speakers)  # revalidate
        variants.append(variant)
    else:
        if not global_choices:
            raise ValueError("Select at least one chain output")
        for name, gain in global_choices.items():
            chosen = [_choice(group, name, gain) for group in manifest["groups"]]
            if any(row["config"] != chosen[0]["config"] for row in chosen):
                raise ValueError(
                    "Global chain choices must be consistent across previews"
                )
            original = next(v for v in base.variants if v.name == name)
            variants.append(
                Variant(
                    name=name,
                    suffix=original.suffix,
                    config=deepcopy(chosen[0]["config"]),
                )
            )
    output = (
        Path(output_dir).expanduser().resolve() if output_dir else base.output_directory
    )
    tasks = [
        Task(
            file=f,
            variant=v,
            output=output
            / file.relative.with_name(
                file.relative.stem + variant.suffix + file.relative.suffix
            ),
        )
        for f, file in enumerate(base.files)
        for v, variant in enumerate(variants)
    ]
    identifier = uuid4().hex
    job = Job(
        id=identifier,
        created_at=datetime.now(UTC).isoformat(),
        files=base.files,
        output_directory=output,
        variants=variants,
        processing=base.processing,
        tasks=tasks,
    )
    path = (
        Path(job_path).expanduser().resolve()
        if job_path
        else user_data_path("vexy-speakup", appauthor=False)
        / "jobs"
        / (identifier + ".json")
    )
    if path.exists():
        raise FileExistsError(path)
    save_job(path, job)
    return path
