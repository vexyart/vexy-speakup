# this_file: src/vexy_speakup/catalog.py
"""Detect researched speech plugins and build `auto-*` comparison chains from them.

`plugin_catalog.json` snapshots the Pluginary speech research (role, caveat) with
settings verified against installed versions. Detection matches bundle file names
only and never loads a plugin, so scanning a large VST3 folder stays fast and safe.
"""

import json
import os
from functools import cache
from pathlib import Path

from .assets import available
from .effects import MONO_FOLD
from .locations import plugin_root

STAGES = (
    "gate",
    "denoise",
    "dereverb",
    "restore",
    "integrated",
    "tone",
    "space",
    "master",
)


@cache
def catalog() -> dict:
    return json.loads(Path(__file__).with_name("plugin_catalog.json").read_text())


def scan(root: Path) -> dict[str, Path]:
    """Map bundle file name to path, recursing into vendor folders but not bundles.

    Cached per folder and modification time: profile resolution calls this often.
    """
    return dict(_scan(str(root), root.stat().st_mtime))


@cache
def _scan(root: str, mtime: float) -> tuple[tuple[str, Path], ...]:
    found: dict[str, Path] = {}
    for folder, directories, files in os.walk(root):
        for name in [*directories, *files]:
            if name.lower().endswith(".vst3"):
                found.setdefault(name, Path(folder) / name)
        directories[:] = [d for d in directories if not d.lower().endswith(".vst3")]
    return tuple(found.items())


def detect(root: Path | None = None) -> list[dict]:
    """Catalog plugins present in the VST3 folder, plus bundled free plugins."""
    root = root or plugin_root()
    installed = scan(root) if root.is_dir() else {}
    bundled = {entry["bundle"] for entry in available()}
    rows = []
    for entry in catalog()["plugins"]:
        name = entry["bundle"]
        if name in installed:
            rows.append({**entry, "path": str(installed[name]), "source": "installed"})
        elif name in bundled:
            rows.append({**entry, "path": str(root / name), "source": "bundled"})
    return rows


def downloads(root: Path | None = None) -> list[dict]:
    """Free plugins whose licence forbids bundling, when not installed: vendor links."""
    present = {row["bundle"] for row in detect(root)}
    return [
        {**entry, "source": "download"}
        for entry in catalog()["plugins"]
        if entry.get("download") and entry["bundle"] not in present
    ]


def _spec(row: dict) -> dict:
    return {"path": row["path"], "parameters": dict(row["parameters"])}


def auto_chains(root: Path | None = None) -> dict[str, dict]:
    """Deterministic chains, one plugin per stage, limiters only in `master`.

    The two open-source chains always exist (bundled plugins). Commercial chains
    appear only when their plugins are installed; the first listed wins a stage.
    """
    rows = detect(root)

    def best(stage: str, free: bool | None = None) -> dict | None:
        return next(
            (
                r
                for r in rows
                if r["stage"] == stage and (free is None or r["open_source"] == free)
            ),
            None,
        )

    def chain(speech: list, master: dict | None) -> dict | None:
        if any(s is None for s in speech) or master is None:
            return None
        specs = []
        for row in speech:
            if row.get("mono_input"):
                specs.append({"path": MONO_FOLD})
            specs.append(_spec(row))
        return {"speech": specs, "speakers": {}, "master": [_spec(master)]}

    pro_master = best("master", False) or best("master", True)

    def named(bundle: str) -> dict | None:
        return next((r for r in rows if r["bundle"] == bundle), None)

    candidates = {
        "auto-free-denoise": chain(
            [best("denoise", True), best("tone", True)], named("master_me.vst3")
        ),
        "auto-free-gate": chain(
            [best("gate", True), best("tone", True)], named("pp-master.vst3")
        ),
        "auto-restore": chain([best("restore", False)], pro_master),
        "auto-clean": chain(
            [best("denoise", False), best("dereverb", False), best("restore", False)],
            pro_master,
        ),
        "auto-gate": chain([best("gate", False), best("restore", False)], pro_master),
        # Spatial experiments after the Accentize gate and restoration.
        "auto-gate-wider": chain(
            [best("gate", False), best("restore", False), named("Wider.vst3")],
            pro_master,
        ),
        "auto-gate-stageone": chain(
            [best("gate", False), best("restore", False), named("StageOne2.vst3")],
            pro_master,
        ),
        "auto-dialogue": chain([best("integrated", False)], pro_master),
    }
    chains: dict[str, dict] = {}
    for name, config in candidates.items():
        if config is not None and config not in chains.values():
            chains[name] = config
    return chains


SUGGESTED = ("auto-free-denoise", "auto-clean")
