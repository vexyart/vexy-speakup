# this_file: src/vexy_speakup/audit.py
"""Plugin discovery, comparable quality windows, and separate processing attempts."""

import json
from pathlib import Path

import numpy as np
import soundfile as sf
from pedalboard import load_plugin

from .locations import plugin_root
from .media import decode, write_json
from .models import diarize, score
from .vst import load_chain


def evaluate_windows(
    before: Path, after: Path, turns: list[dict], work: Path, python: str
) -> list[dict]:
    """Score matching speech windows with two independent no-reference predictors."""
    rows = []
    if not turns:
        return [{"status": "skipped", "reason": "No speech turns"}]
    last_start = max(0, sf.info(before).duration - 30)
    starts = sorted(
        {
            min(turns[i]["start"], last_start)
            for i in (0, len(turns) // 2, len(turns) - 1)
        }
    )
    for index, start in enumerate(starts):
        directory = work / "evaluation" / str(index)
        directory.mkdir(parents=True)
        row = {"start": start}
        for label, path in (("before", before), ("after", after)):
            dest = directory / f"{label}.wav"
            decode(path, dest, start, 30)
            metric_dir = directory / label
            metric_dir.mkdir()
            try:
                row[label] = score(dest, metric_dir, python=python)["scores"]
            except (OSError, ImportError, RuntimeError, ValueError) as exc:
                row[label] = {"error": str(exc)}
        rows.append(row)
    write_json(work / "evaluation.json", rows)
    return rows


def inspect(plugin_path: str, output_path: str = "") -> str:
    """List the plugin's real controls and their ranges; license errors surface directly."""
    board, receipts = load_chain([{"path": plugin_path}])
    plugin = board[0]
    receipt = {
        **receipts[0],
        "ranges": {k: repr(v.range) for k, v in plugin.parameters.items()},
    }
    text = json.dumps(receipt, indent=2)
    if output_path:
        Path(output_path).write_text(text + "\n")
    return text


def probe_plugin(plugin_path: str, output_path: str, audio_path: str = "") -> str:
    """Load one plugin directly; save its live controls and a finite render probe."""
    plugin = load_plugin(plugin_path)
    controls = {
        name: {
            "value": str(getattr(plugin, name)),
            "raw": param.raw_value,
            "range": repr(param.range),
            "valid_values": repr(param.valid_values),
        }
        for name, param in plugin.parameters.items()
    }
    x = (
        sf.read(audio_path, dtype="float32", always_2d=True)[0].T
        if audio_path
        else np.zeros((2, 48000), np.float32)
    )
    x = np.pad(x, ((0, 0), (0, 96000)))
    y = plugin(x, 48000, buffer_size=2048)
    write_json(
        Path(output_path),
        {
            "path": plugin_path,
            "name": plugin.name,
            "controls": controls,
            "input_frames": x.shape[1],
            "output_frames": y.shape[1],
            "finite": bool(np.isfinite(y).all()),
            "peak": float(np.max(np.abs(y))),
        },
    )
    return f"{plugin.name}: {len(controls)} parameters; {y.shape}"


def inventory(output_path: str = "inventory.json") -> str:
    """Inventory bundles without loading every commercial plugin."""
    root = plugin_root()
    if not root.is_dir():
        raise FileNotFoundError(f"Plugin folder not found: {root}")
    paths = sorted(str(p) for p in root.rglob("*.vst3") if p.is_dir())
    write_json(
        Path(output_path),
        {"plugin_root": str(root), "count": len(paths), "plugins": paths},
    )
    return f"{len(paths)} plugins: {output_path}"


def attempts(
    input_path: str,
    work_dir: str = "",
    start: float = 120,
    duration: float = 45,
    profiles: str = "dx35,dx65,rx6-dx35",
    metrics_python: str = "",
    verbose: bool = True,
) -> str:
    """Retain separate preview attempts and model scores for human comparison."""
    from .cli import run

    source = Path(input_path).expanduser().resolve()
    root = (
        Path(work_dir).expanduser().resolve()
        if work_dir
        else source.with_name(source.stem + "_attempts")
    )
    root.mkdir(parents=True, exist_ok=True)
    sample = root / "sample.wav"
    decode(source, sample, start, duration)
    turns = diarize(sample, root, "mlx", "", sf.info(sample).duration, 1800)
    write_json(root / "turns.json", turns)
    reports = []
    names = profiles.split(",") if isinstance(profiles, str) else profiles
    for name in names:
        output = root / f"{name}.wav"
        run(
            str(sample),
            work_dir=str(root / name),
            output_path=str(output),
            profile_name=name,
            diarization_json=str(root / "turns.json"),
            metrics_python=metrics_python,
            verbose=verbose,
        )
        latest = json.loads((root / name / "latest.json").read_text())
        reports.append(json.loads(Path(latest["report"]).read_text()))
    write_json(root / "comparison.json", reports)
    return str(root / "comparison.json")
