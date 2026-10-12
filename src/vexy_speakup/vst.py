# this_file: src/vexy_speakup/vst.py
"""Isolated VST rendering, real exposed parameters and bounded streaming memory."""

from pathlib import Path

import numpy as np
import soundfile as sf
from pedalboard import Pedalboard, load_plugin

from .locations import plugin_root
from .media import RATE, write_json


def plugin_spec(name: str, **parameters: object) -> dict:
    return {"path": str(plugin_root() / name), "parameters": parameters}


def profile(name: str) -> dict:
    """Only use controls verified against these locally installed plugin versions."""
    dx = plugin_spec("Accentize-dxRevivePro.vst3", mix=35.0, bypass=False)
    rx = plugin_spec(
        "RX 12 Voice De-noise.vst3",
        reduction=6.0,
        adaptive_mode=True,
        global_bypass=False,
    )
    master = plugin_spec(
        "Ozone 12 Maximizer.vst3",
        max_output_level=-2.0,
        max_input_gain_db=0.0,
        max_upward_compression_amt_db=0.0,
        max_soft_clip_on_off=False,
        global_bypass=False,
    )
    choices = {
        "dx35": [dx],
        "dx65": [{**dx, "parameters": {"mix": 65.0, "bypass": False}}],
        "rx6-dx35": [rx, dx],
        "rx6": [rx],
        "bypass": [],
    }
    if name not in choices:
        raise ValueError(f"Unknown profile {name}; choose {', '.join(choices)}")
    return {
        "speech": choices[name],
        "speakers": {},
        "master": [] if name == "bypass" else [master],
    }


def load_chain(specs: list[dict]) -> tuple[Pedalboard, list[dict]]:
    plugins, receipts = [], []
    for spec in specs:
        path = Path(spec["path"]).expanduser().resolve()
        plugin = load_plugin(
            str(path), plugin_name=spec.get("plugin_name"), initialization_timeout=15
        )
        if not plugin.is_effect:
            raise ValueError(f"Not an effect: {path}")
        if spec.get("preset"):
            plugin.load_preset(str(Path(spec["preset"]).expanduser().resolve()))
        for name, value in spec.get("parameters", {}).items():
            if name not in plugin.parameters:
                raise ValueError(
                    f"Unknown parameter {name} for {plugin.name}; use inspect"
                )
            setattr(plugin, name, value)
        plugins.append(plugin)
        receipts.append(
            {
                "path": str(path),
                "name": plugin.name,
                "reported_latency_samples": plugin.reported_latency_samples,
                "parameters": {
                    name: str(getattr(plugin, name)) for name in plugin.parameters
                },
            }
        )
    return Pedalboard(plugins), receipts


def render_chunk(board: Pedalboard, audio: np.ndarray, rate: int) -> np.ndarray:
    """Pad to drain latency, then crop the automatically compensated waveform."""
    n = len(audio)
    padded = np.pad(audio.T, ((0, 0), (0, rate * 2)))
    result = board(padded, rate, buffer_size=2048, reset=True).T
    if (
        len(result) < n
        or result.shape[1] != audio.shape[1]
        or not np.isfinite(result).all()
    ):
        raise ValueError("VST returned invalid geometry or non-finite samples")
    if np.max(np.abs(audio)) > 1e-5 and np.max(np.abs(result[:n])) < 1e-8:
        raise ValueError("VST unexpectedly silenced input; check license and settings")
    return result[:n]


def render_jobs(jobs: list[dict], specs: list[dict], receipt: Path) -> None:
    """One process per speaker, one plugin chain, independent state per fragment."""
    board, plugins = load_chain(specs)
    for job in jobs:
        x, rate = sf.read(job["input"], dtype="float32", always_2d=True)
        result = render_chunk(board, x, rate)
        sf.write(job["output"], result, rate, subtype="FLOAT")
    write_json(receipt, {"plugins": plugins, "jobs": len(jobs)})


def render_master(source: Path, output: Path, specs: list[dict], receipt: Path) -> None:
    """Keep master state continuous across blocks and drain buffered output at EOF."""
    board, plugins = load_chain(specs)
    written, first = 0, True
    with (
        sf.SoundFile(source) as reader,
        sf.SoundFile(
            output,
            "w",
            samplerate=reader.samplerate,
            channels=reader.channels,
            subtype="FLOAT",
            format="RF64",
        ) as writer,
    ):
        frames, rate, channels = len(reader), reader.samplerate, reader.channels
        while reader.tell() < frames:
            x = reader.read(RATE * 10, dtype="float32", always_2d=True)
            y = board(x.T, rate, buffer_size=2048, reset=first).T
            first = False
            if not np.isfinite(y).all() or y.shape[1] != channels:
                raise ValueError("Invalid master render")
            writer.write(y[: frames - written])
            written += min(len(y), frames - written)
        for _ in range(10):
            if written == frames:
                break
            y = board(
                np.zeros((channels, rate), np.float32),
                rate,
                buffer_size=2048,
                reset=False,
            ).T
            if not np.isfinite(y).all():
                raise ValueError("Non-finite master tail")
            writer.write(y[: frames - written])
            written += min(len(y), frames - written)
        if written != frames:
            raise ValueError("Master tail drain did not preserve duration")
    write_json(receipt, {"plugins": plugins, "frames": written})
