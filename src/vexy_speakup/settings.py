# this_file: src/vexy_speakup/settings.py
"""Portable TOML application settings, separate from per-run JSON chains."""

import math
import os
import re
import tomllib
from copy import deepcopy
from pathlib import Path

import tomli_w
from platformdirs import user_config_path

CONFIG_ENV = "VEXY_SPEAKUP_CONFIG"
DEFAULTS = {
    "schema_version": 1,
    "paths": {"plugin_root": "/Library/Audio/Plug-Ins/VST3"},
    "processing": {
        "profile": "dx35",
        "workers": 4,
        "max_chunk": 30,
        "target_lufs": -16,
        "true_peak": -2,
        "brightness_db": 0,
    },
    "candidates": {
        name: {"profile": name, "suffix": f"_{name}"}
        for name in ("podcast", "dx35", "dx35-bright", "clear")
    },
}


def config_file() -> Path:
    """Use an explicit environment override or the OS user-config folder."""
    override = os.environ.get(CONFIG_ENV)
    return (
        Path(override).expanduser()
        if override
        else user_config_path("vexy-speakup", appauthor=False) / "config.toml"
    )


def read_settings(path: Path | None = None) -> dict:
    """Merge defaults with TOML; reject typos and invalid values at the boundary."""
    explicit = path is not None
    path = path or config_file()
    settings = deepcopy(DEFAULTS)
    if not explicit and not path.exists():
        return settings
    with path.open("rb") as reader:
        raw = tomllib.load(reader)
    version = raw.get("schema_version", 1)
    if raw.keys() - DEFAULTS.keys() or type(version) is not int or version != 1:
        raise ValueError(f"Unknown settings or unsupported schema_version in {path}")
    for section in ("paths", "processing", "candidates"):
        value = raw.get(section, {})
        if not isinstance(value, dict):
            raise TypeError(f"{section} must be a TOML table")
        if section == "paths":
            # tts_root (before 1.1) is obsolete: models now use the HF cache.
            value = {k: v for k, v in value.items() if k != "tts_root"}
        if section != "candidates" and value.keys() - DEFAULTS[section].keys():
            raise ValueError(f"Unknown {section} setting in {path}")
        settings[section].update(value)
    _validate(settings)
    return settings


def _validate(settings: dict) -> None:
    for name, value in settings["paths"].items():
        if not isinstance(value, str) or (name == "plugin_root" and not value):
            raise ValueError(f"paths.{name} must be a path string")
    processing = settings["processing"]
    if type(processing["workers"]) is not int or not 1 <= processing["workers"] <= 128:
        raise ValueError("processing.workers must be an integer in [1,128]")
    for key, low, high in (
        ("max_chunk", 0.01, 3600),
        ("target_lufs", -70, -5),
        ("true_peak", -9, 0),
        ("brightness_db", -12, 12),
    ):
        value = processing[key]
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not low <= value <= high
        ):
            raise ValueError(f"processing.{key} must be finite in [{low},{high}]")
    if not isinstance(processing["profile"], str) or not processing["profile"]:
        raise ValueError("processing.profile must be a nonempty string")
    suffixes = set()
    for name, candidate in settings["candidates"].items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name) or not isinstance(candidate, dict):
            raise ValueError(f"Invalid candidate: {name}")
        if candidate.keys() - {"profile", "suffix", "speech", "master", "speakers"}:
            raise ValueError(f"Unknown candidate setting: {name}")
        suffix = candidate.get("suffix", "")
        if not isinstance(suffix, str) or not re.fullmatch(r"_[A-Za-z0-9_-]+", suffix):
            raise ValueError(f"Candidate {name} requires a safe basename suffix")
        if suffix in suffixes:
            raise ValueError(f"Duplicate candidate suffix: {suffix}")
        suffixes.add(suffix)
        if "profile" in candidate:
            if not isinstance(candidate["profile"], str) or not candidate["profile"]:
                raise ValueError(f"Candidate {name} requires a profile name")
            if candidate.keys() & {"speech", "master", "speakers"}:
                raise ValueError(f"Candidate {name}: choose profile or explicit chains")
        else:
            validate_chain(candidate)


def validate_chain(config: dict) -> None:
    """Validate plugin specs without loading native code or requiring licences."""
    if not isinstance(config, dict):
        raise TypeError("Chain config must be an object")
    overrides = config.get("speakers", {})
    if not isinstance(overrides, dict):
        raise TypeError("speakers must be a table of chains")
    for chain in [config.get("speech"), config.get("master"), *overrides.values()]:
        if not isinstance(chain, list):
            raise TypeError("speech, master and speaker chains must be arrays")
        for spec in chain:
            if (
                not isinstance(spec, dict)
                or not isinstance(spec.get("path"), str)
                or not spec["path"]
            ):
                raise ValueError("Each plugin requires a nonempty path string")
            if spec.keys() - {"path", "parameters", "preset", "plugin_name"}:
                raise ValueError("Unknown plugin spec field")
            if not isinstance(spec.get("parameters", {}), dict):
                raise TypeError("Plugin parameters must be a table")
            for key in ("preset", "plugin_name"):
                if key in spec and not isinstance(spec[key], str):
                    raise TypeError(f"Plugin {key} must be a string")


def candidate_chain(name: str, settings: dict | None = None) -> dict | None:
    """Resolve explicit candidate specs; built-in profile aliases are handled in vst."""
    settings = settings or read_settings()
    candidate = settings["candidates"].get(name)
    if not candidate or "profile" in candidate:
        return None
    config = deepcopy(
        {key: candidate.get(key, {}) for key in ("speech", "master", "speakers")}
    )
    root = Path(
        os.environ.get("VEXY_SPEAKUP_PLUGIN_ROOT") or settings["paths"]["plugin_root"]
    ).expanduser()
    for chain in [config["speech"], config["master"], *config["speakers"].values()]:
        for spec in chain:
            if spec["path"].startswith("builtin:"):
                continue
            path = Path(spec["path"]).expanduser()
            spec["path"] = str(path if path.is_absolute() else root / path)
    return config


def init_config(output_path: str = "") -> Path:
    """Write editable defaults; exclusive creation protects existing user settings."""
    path = Path(output_path).expanduser() if output_path else config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "# vexy-speakup application settings\n" + tomli_w.dumps(DEFAULTS)
    with path.open("x") as writer:
        writer.write(content)
    return path
