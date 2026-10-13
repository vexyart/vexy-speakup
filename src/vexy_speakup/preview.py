# this_file: src/vexy_speakup/preview.py
"""Representative listening excerpts rendered through the same full pipeline as jobs."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import numpy as np
import soundfile as sf
from platformdirs import user_cache_path

from .batch import create_job, read_job, save_job
from .batch_render import _prepare
from .cancel import check
from .cli import run
from .effects import brighten
from .media import RATE, normalize, sha, write_json
from .preview_windows import representative, speaker_windows

__all__ = ["prepare_preview", "representative", "speaker_windows"]

BRIGHTNESS = (0, 3, -3)


def _render_variant(
    sample: Path, output: Path, config: dict, work: Path, target: float, peak: float
) -> str:
    work.mkdir(parents=True, exist_ok=True)
    chain = work / "chain.json"
    write_json(chain, config)
    return run(
        str(sample),
        output_path=str(output),
        work_dir=str(work),
        config_path=str(chain),
        diarizer="none",
        evaluate=False,
        workers=1,
        target_lufs=target,
        true_peak=peak,
        brightness_db=0,
    )


def prepare_preview(
    input_dir: str,
    session_dir: str = "",
    speaker_mode: bool = False,
    diarizer: str = "mlx",
    diarization_dir: str = "",
    duration: float = 10,
    workers: int = 4,
    progress=None,
    chains: list[str] | None = None,
) -> dict:
    """Prepare all file/speaker samples and three listening variants per configured chain.

    Each variant either has a real output or an explicit error. No failed processor
    is replaced by bypass. `chains` limits which candidates/profiles are auditioned.
    Speaker clips use the speech chain only, then loudness and peak normalization,
    because the final master is one continuous chain chosen after listening.
    """
    if (
        not np.isfinite(duration)
        or not 0.25 <= duration <= 60
        or type(workers) is not int
        or not 1 <= workers <= 128
    ):
        raise ValueError("Require preview duration [.25,60] and workers [1,128]")
    root = (
        Path(session_dir).expanduser().resolve()
        if session_dir
        else user_cache_path("vexy-speakup", appauthor=False) / "previews" / uuid4().hex
    )
    root.mkdir(parents=True, exist_ok=True)
    base_path = create_job(
        input_dir,
        candidates=",".join(chains or []),
        job_path=str(root / "base.json"),
        diarization_dir=diarization_dir,
        diarizer=diarizer if speaker_mode else "none",
    )
    job = read_job(base_path)
    manifest = {
        "version": 1,
        "base_job": str(base_path),
        "speaker_mode": speaker_mode,
        "masters": [v.name for v in job.variants if v.config["master"]],
        "groups": [],
    }
    tasks = []
    for index, file in enumerate(job.files):
        check()
        if progress:
            progress(f"Preparing {file.relative}")
        audio, annotation = _prepare(job, index, root / "prepared")
        turns = json.loads(annotation.read_text())
        file.turns = turns
        windows = (
            speaker_windows(turns, sf.info(audio).duration, duration)
            if speaker_mode
            else [representative(audio, duration)]
        )
        for window in windows:
            group_id = f"{index}-{window['speaker'] or 'global'}"
            folder = root / group_id
            folder.mkdir()
            sample, original = folder / "sample.wav", folder / "original.wav"
            with sf.SoundFile(audio) as reader:
                reader.seek(round(window["start"] * RATE))
                sf.write(
                    sample,
                    reader.read(
                        round(window["duration"] * RATE),
                        dtype="float32",
                        always_2d=True,
                    ),
                    RATE,
                    subtype="FLOAT",
                )
            normalize(
                sample, original, job.processing.target_lufs, job.processing.true_peak
            )
            group = {
                **window,
                "id": group_id,
                "file": index,
                "source": str(file.source),
                "label": str(file.relative),
                "original": str(original),
                "variants": [],
            }
            for variant in job.variants:
                for gain in BRIGHTNESS:
                    config = brighten(variant.config, gain)
                    if speaker_mode:
                        config["speech"] = deepcopy(
                            config.get("speakers", {}).get(
                                window["speaker"], config["speech"]
                            )
                        )
                        config["speakers"] = {}
                        config["master"] = []
                    row = {"chain": variant.name, "brightness": gain, "config": config}
                    output = folder / f"{variant.name}-{gain}.wav"
                    group["variants"].append(row)
                    tasks.append(
                        (
                            row,
                            sample,
                            output,
                            config,
                            folder / f"work-{variant.name}-{gain}",
                        )
                    )
            manifest["groups"].append(group)
    save_job(base_path, job)
    if not manifest["groups"]:
        raise ValueError("No speaker intervals found")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                copy_context().run,
                _render_variant,
                sample,
                output,
                config,
                work,
                job.processing.target_lufs,
                job.processing.true_peak,
            ): row
            for row, sample, output, config, work in tasks
        }
        for count, future in enumerate(as_completed(futures), 1):
            row = futures[future]
            try:
                row["output"] = future.result()
                row["output_sha256"] = sha(Path(row["output"]))
            except Exception as exc:  # noqa: BLE001 -- preserve each preview failure without bypassing it
                row["error"] = str(exc)
            if progress:
                progress(f"Rendered {count}/{len(tasks)} listening variants")
    check()
    manifest["manifest_path"] = str(root / "preview.json")
    write_json(root / "preview.json", manifest)
    return manifest
