# this_file: src/vexy_speakup/profiles.py
"""Verified installed plugin controls for useful listening comparisons."""

from pathlib import Path

from .assets import available
from .effects import brighten
from .locations import plugin_root
from .settings import candidate_chain, read_settings

# Built-in profiles offered for listening, in display order (bypass is not a chain).
BUILTIN = (
    "podcast", "podcast-bright", "dx35", "dx35-bright", "dx65", "rx6", "rx6-dx35", "clear"
)


def chain_options() -> list[dict]:
    """Configured candidates and built-in profiles, with what each needs installed.

    A plugin counts as present when it is in plugin_root or bundled (downloaded on
    first use). `open_source` means every plugin is a bundled free plugin.
    """
    settings = read_settings()
    bundled = {entry["bundle"] for entry in available()}
    rows = []
    for name in dict.fromkeys([*settings["candidates"], *BUILTIN]):
        config = profile(name)
        plugins = [
            Path(spec["path"]).expanduser()
            for chain in (config["speech"], config["master"], *config["speakers"].values())
            for spec in chain
            if not spec["path"].startswith("builtin:")
        ]
        missing = [p.name for p in plugins if not p.exists() and p.name not in bundled]
        rows.append(
            {
                "name": name,
                "available": not missing,
                "missing": missing,
                "open_source": bool(plugins) and all(p.name in bundled for p in plugins),
                "suggested": name in settings["candidates"] and not missing,
            }
        )
    return rows


def plugin_spec(name: str, **parameters: object) -> dict:
    return {"path": str(plugin_root() / name), "parameters": parameters}


def profile(name: str) -> dict:
    """Only use controls verified against these locally installed plugin versions."""
    settings = read_settings()
    seen = set()
    while name in settings["candidates"]:
        if name in seen:
            raise ValueError(f"Circular candidate profile alias: {name}")
        seen.add(name)
        custom = candidate_chain(name, settings)
        if custom is not None:
            return custom
        alias = settings["candidates"][name]["profile"]
        if alias == name:
            break
        name = alias
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
    podcast = plugin_spec(
        "pp-track.vst3", timbre=0.0, style=-2.0, target_db=-18.0, bypass=0.0
    )
    podcast_master = plugin_spec(
        "pp-master.vst3", timbre=0.0, target_db=-16.0, bypass=0.0
    )
    clear = plugin_spec(
        "Clear.vst3",
        ambience_gain=-12.0,
        voice_gain=0.0,
        voice_reverb_gain=-6.0,
        bypass=False,
    )
    choices = {
        "dx35": [dx],
        "dx65": [{**dx, "parameters": {"mix": 65.0, "bypass": False}}],
        "rx6-dx35": [rx, dx],
        "rx6": [rx],
        "bypass": [],
        "podcast": [podcast],
        "podcast-bright": [
            {**podcast, "parameters": {**podcast["parameters"], "timbre": 2.0}}
        ],
        "clear": [clear],
        "dx35-bright": brighten({"speech": [dx], "master": []}, 3)["speech"],
    }
    if name not in choices:
        raise ValueError(f"Unknown profile {name}; choose {', '.join(choices)}")
    return {
        "speech": choices[name],
        "speakers": {},
        "master": []
        if name == "bypass"
        else [podcast_master]
        if name.startswith("podcast")
        else [master],
    }
