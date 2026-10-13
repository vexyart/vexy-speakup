# this_file: src/vexy_speakup/model_worker.py
"""Run one local model in a child process, so cancellation and deadlines can kill it.

`models.py` launches `python -m vexy_speakup.model_worker <command> ...`. Weights come
from the standard Hugging Face cache at pinned revisions; nothing outside this package
is needed. Requires the `models` extra (mlx-audio, speechonnxmetrics).
"""

import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

# Pinned Hugging Face repositories: (repo, revision).
NEMOTRON = ("mlx-community/Nemotron-3-Diarization-8bit", "dd8b8ce3d69a80540a7e50150e2beed1c34fee37")
SORTFORMER = ("mlx-community/diar_streaming_sortformer_4spk-v2.1-fp16", "e23e6404bd9859e93edbf94a740eb1c7fc58f12e")
# Same model.safetensors (sha256 fca0af2f...) as the DF3 CoreML package used before 1.1.
DEEPFILTER = ("iky1e/DeepFilterNet3-MLX", "2439328cfebafb28099d9feff6890e29dbae2241")
WEIGHTS = ["*.json", "*.safetensors"]
# Sortformer and Nemotron round their last 80 ms frame beyond EOF; clip only that frame.
EOF_FRAME = 0.081
NOREF = ("utmos", "dnsmos", "dnsmos_p808", "sigmos", "nisqa")


def snapshot(pinned: tuple[str, str]) -> Path:
    """Download (or reuse) pinned weights in the standard HF cache (HF_HOME/HF_HUB_CACHE)."""
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    repo, revision = pinned
    try:  # a pinned commit already in the cache needs no network round-trip
        folder = snapshot_download(
            repo, revision=revision, allow_patterns=WEIGHTS, local_files_only=True
        )
    except LocalEntryNotFoundError:
        folder = snapshot_download(repo, revision=revision, allow_patterns=WEIGHTS)
    return Path(folder)


def receipt(pinned: tuple[str, str], folder: Path) -> dict:
    return {
        "weights_repo": pinned[0],
        "weights_revision": pinned[1],
        "weights_files": [
            {"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(folder.glob("*"))
            if p.is_file()
        ],
    }


def mono16k(audio: Path, folder: Path) -> Path:
    converted = folder / "input-16k.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(audio), "-ar", "16000", "-ac", "1", str(converted)],
        check=True,
    )
    return converted


def clip_eof(rows: list[dict], duration: float) -> list[dict]:
    for row in rows:
        if duration < row["end"] <= duration + EOF_FRAME:
            row["end_before_eof_clip"] = row["end"]
            row["end"] = duration
    return [row for row in rows if row["start"] < row["end"]]


def diarize(audio: str, output: str, backend: str = "mlx") -> None:
    """Write {"segments": [...], ...receipt} for `turns.parse_turns`."""
    import mlx.core as mx
    from mlx_audio.vad import load

    pinned = {"mlx": NEMOTRON, "sortformer": SORTFORMER}[backend]
    folder = snapshot(pinned)
    start = time.monotonic()
    model = load(str(folder), strict=True)
    if backend == "mlx":
        model.set_streaming_config("offline")
    load_s = time.monotonic() - start
    with tempfile.TemporaryDirectory() as temporary:
        converted = mono16k(Path(audio), Path(temporary))
        duration = sf.info(converted).duration
        start = time.monotonic()
        if backend == "mlx":
            results = [model.generate(str(converted))]
        else:
            samples, _ = sf.read(converted, dtype="float32")
            results = model.generate_stream(samples, chunk_duration=30.0)
        segments = []
        for result in results:
            segments.extend(
                {"start": float(s.start), "end": float(s.end), "speaker": int(s.speaker)}
                for s in result.segments
            )
        mx.synchronize()
        wall = time.monotonic() - start
    report = {
        **receipt(pinned, folder),
        "backend": backend,
        "runtime": "mlx-audio",
        "input": str(audio),
        "duration_s": duration,
        "load_s": load_s,
        "wall_s": wall,
        "segments": clip_eof(segments, duration),
    }
    Path(output).write_text(json.dumps(report, indent=2) + "\n")


def _use_standard_hf_cache() -> None:
    """speechonnxmetrics caches under XDG_DATA_HOME; route its HF downloads to the HF cache."""
    from huggingface_hub import hf_hub_download
    from speechonnxmetrics import resolver

    def hf_download(repo, filename, revision=None, cache_dir=None):
        return hf_hub_download(repo_id=repo, filename=filename, revision=revision)

    resolver.hf_download = hf_download


def score(audio: str, output: str, metrics: str = "dnsmos,utmos") -> None:
    """Write {"audio", "scores"}; one unloadable metric is recorded, not fatal."""
    import speechonnxmetrics as som

    _use_standard_hf_cache()
    names = metrics.split(",") if isinstance(metrics, str) else list(metrics)
    scores: dict[str, float | str | None] = {}
    for metric in (m.strip() for m in names if m.strip()):
        if metric not in NOREF:
            raise ValueError(f"Unsupported no-reference metric: {metric}")
        try:
            values = som.score(audio, [metric])
        except Exception as exc:  # noqa: BLE001 - a failed metric is data, not a crash
            values = {"_errors": {metric: str(exc)}}
        for name, error in values.pop("_errors", {}).items():
            scores[f"{name}.error"] = str(error)[:200]
        scores.update({k: v for k, v in values.items() if v is not None})
    result = {"audio": audio, "scores": scores}
    Path(output).write_text(json.dumps(result, allow_nan=False) + "\n")


def deepfilter(source: str, output: str, receipt_path: str) -> None:
    """DeepFilterNet3 on a 48 kHz mono downmix; output keeps the exact sample count."""
    from mlx_audio.sts.models.deepfilternet.model import DeepFilterNetModel

    folder = snapshot(DEEPFILTER)
    model = DeepFilterNetModel.from_pretrained(str(folder), subfolder=None)
    audio, rate = sf.read(source, dtype="float32", always_2d=True)
    if rate != model.config.sample_rate:
        raise ValueError(f"DeepFilterNet needs {model.config.sample_rate} Hz, got {rate}")
    mono = audio.mean(axis=1)
    enhanced = model.enhance_array_streaming(mono)[: mono.size]
    enhanced = np.pad(enhanced, (0, mono.size - enhanced.size))
    sf.write(output, enhanced, rate, subtype="FLOAT")
    Path(receipt_path).write_text(
        json.dumps({**receipt(DEEPFILTER, folder), "runtime": "mlx-audio"}, indent=2)
        + "\n"
    )


if __name__ == "__main__":
    import fire

    fire.Fire({"diarize": diarize, "score": score, "deepfilter": deepfilter})
