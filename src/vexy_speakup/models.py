# this_file: src/vexy_speakup/models.py
"""Run bundled model adapters (`model_worker`) as killable child processes.

Weights load from the standard Hugging Face cache at pinned revisions. The adapters
need the `models` extra; a missing extra raises ModuleNotFoundError with the fix.
"""

import importlib.util
import json
import sys
from pathlib import Path

from .media import command, sha, write_json
from .turns import parse_turns

EXTRA_HINT = (
    "Local models need the 'models' extra: uv pip install 'vexy-speakup[models]' "
    "(or run ./run-gui.sh, which adds it). Alternatively pass --diarization_json "
    "and --evaluate=False"
)


def worker(python: str = "") -> list[str]:
    """Interpreter + module argv; checks the extra only for our own interpreter."""
    if not python:
        for module in ("mlx_audio", "speechonnxmetrics", "huggingface_hub"):
            if importlib.util.find_spec(module) is None:
                raise ModuleNotFoundError(f"{module} is not installed. {EXTRA_HINT}")
    return [python or sys.executable, "-m", "vexy_speakup.model_worker"]


def diarize(
    audio: Path, work: Path, backend: str, supplied: str, duration: float, timeout: int
) -> list[dict]:
    """MLX Nemotron or Sortformer keep speaker state across a full file; JSON import too."""
    if supplied:
        raw = json.loads(Path(supplied).expanduser().read_text())
    elif backend == "none":
        raw = [{"start": 0, "end": duration, "speaker": "speech"}] if duration > 0 else []
    elif backend in {"mlx", "sortformer"}:
        destination = work / "diarization-native.json"
        command(
            [*worker(), "diarize", f"--audio={audio}", f"--output={destination}",
             f"--backend={backend}"],
            timeout,
            work / "diarization.log",
        )
        raw = json.loads(destination.read_text())
    else:
        raise ValueError(
            "diarizer must be none, mlx or sortformer, or supply --diarization_json"
        )
    turns = parse_turns(raw, duration)
    write_json(work / "turns.json", turns)
    return turns


def score(
    audio: Path, work: Path, metrics: str = "dnsmos,utmos", python: str = ""
) -> dict:
    """Score with cached ONNX MOS models; failures are recorded, never invented."""
    destination = work / "scores.json"
    command(
        [*worker(python), "score", f"--audio={audio}", f"--output={destination}",
         f"--metrics={metrics}"],
        900,
        work / "metrics.log",
    )
    return json.loads(destination.read_text())


def deepfilter(source: Path, output: Path, work: Path, timeout: int) -> None:
    """DeepFilterNet3 (MLX) on a mono downmix; same weights as the former CoreML pass."""
    receipt = work / "deepfilter-receipt.json"
    command(
        [*worker(), "deepfilter", f"--source={source}", f"--output={output}",
         f"--receipt_path={receipt}"],
        timeout,
        work / "deepfilter.log",
    )
    write_json(receipt, {**json.loads(receipt.read_text()), "output_sha256": sha(output)})
