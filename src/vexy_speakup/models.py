# this_file: src/vexy_speakup/models.py
"""Reuse inspected local model adapters in their isolated uv environments."""

import json
from pathlib import Path

from .locations import tts_root
from .media import command, sha, write_json
from .turns import parse_turns


def diarize(
    audio: Path, work: Path, backend: str, supplied: str, duration: float, timeout: int
) -> list[dict]:
    """MLX Nemotron keeps speaker state across a full file; imported JSON is also supported."""
    if supplied:
        raw = json.loads(Path(supplied).expanduser().read_text())
    elif backend == "mlx":
        script = tts_root() / "myasr/tools/diarize-mlx.py"
        destination = work / "diarization-native"
        command(
            [
                "uv",
                "run",
                "--offline",
                "--script",
                script,
                "run",
                f"--audio={audio}",
                f"--output={destination}",
                "--mode=offline",
                f"--timeout={timeout}",
            ],
            timeout,
            work / "diarization.log",
        )
        raw = json.loads((destination / "report.json").read_text())
    elif backend == "sortformer":
        binary = (
            tts_root() / ".external/NeMo-Speech.cpp/build/metal-asr/bin/nemo-speech"
        )
        model = (
            Path.home()
            / ".cache/huggingface/hub/models--nvidia--diar_streaming_sortformer_4spk-v2/snapshots/5240a64075176943f677d30fa2171c780229f341/diar_streaming_sortformer_4spk-v2.q8_0.gguf"
        )
        text = command(
            [
                binary,
                "diarize",
                audio,
                "--model",
                model,
                "--device",
                "metal",
                "--format",
                "json",
            ],
            timeout,
            work / "diarization.log",
        )
        raw = json.loads(text[text.index("{") : text.rfind("}") + 1])
        # Sortformer rounds its last 80ms frame beyond EOF; record and clip that frame only.
        for row in raw["segments"]:
            if duration < row["end"] <= duration + 0.081:
                row["end_before_eof_clip"] = row["end"]
                row["end"] = duration
        write_json(work / "diarization-native.json", raw)
    else:
        raise ValueError(
            "diarizer must be mlx or sortformer, or supply --diarization_json"
        )
    turns = parse_turns(raw, duration)
    write_json(work / "turns.json", turns)
    return turns


def score(
    audio: Path, work: Path, metrics: str = "dnsmos,utmos", python: str = ""
) -> dict:
    """Invoke cached ONNX MOS models; record missing-model failures rather than invent scores."""
    script = tts_root() / "myaud/tools/aud-metrics.py"
    if python:
        interpreter = Path(python)
    else:
        candidates = sorted(
            (Path.home() / ".cache/uv/environments-v2").glob("aud-metrics-*/bin/python")
        )
        if not candidates:
            raise FileNotFoundError(
                "No cached aud-metrics environment; pass --metrics_python"
            )
        interpreter = candidates[0]
    text = command(
        [interpreter, script, "score", f"--audio={audio}", f"--metrics={metrics}"],
        900,
        work / "metrics.log",
    )
    rows = [line for line in text.splitlines() if line.startswith('{"audio"')]
    if not rows:
        raise ValueError("Metric adapter did not return score JSON")
    result = json.loads(rows[-1])
    write_json(work / "scores.json", result)
    return result


def deepfilter(source: Path, output: Path, work: Path, timeout: int) -> None:
    """Use the original pinned native host with an explicit directory URL after cache migration."""
    tts = tts_root()
    catalog = json.loads((tts / "myaud/catalogs/deepfilternet-coreml.json").read_text())
    assets = (tts / ".cache/issue201/deepfilternet-coreml-materialized").resolve()
    engine = tts / ".external/DeepFilterNet-mlx"
    binary = engine / catalog["binary_relative"]
    if sha(binary) != catalog["binary_sha256"]:
        raise ValueError("DeepFilterNet binary differs from qualified catalog")
    for name, expected in catalog["files"].items():
        if sha(assets / name) != expected:
            raise ValueError(f"DeepFilterNet model asset differs: {name}")
    native = work / "deepfilter-native"
    native.mkdir()
    model_directory = str(assets) + "/"
    command(
        [
            binary,
            source,
            "--model",
            model_directory,
            "--coreml-model-dir",
            model_directory,
            "--engines",
            "coreml",
            "--coreml-compute-units",
            "cpuOnly",
            "--skip-offline",
            "--warmup",
            "0",
            "--runs",
            "1",
            "--save-output",
            "--output-dir",
            native,
        ],
        timeout,
        work / "deepfilter.log",
    )
    result = native / "output_deepfilternet3_core_ml_batch1.wav"
    result.replace(output)
    write_json(
        work / "deepfilter-receipt.json",
        {
            "catalog": catalog,
            "assets": str(assets),
            "directory_url_fix": True,
            "output_sha256": sha(output),
        },
    )
