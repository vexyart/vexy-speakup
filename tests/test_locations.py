# this_file: tests/test_locations.py
"""Installation roots resolve lazily and fail with setup guidance."""

import json
import sys
from pathlib import Path

import pytest

from vexy_speakup import __version__, models
from vexy_speakup.cli import version
from vexy_speakup.locations import DEFAULT_PLUGIN_ROOT, PLUGIN_ENV, plugin_root
from vexy_speakup.models import diarize, score
from vexy_speakup.vst import profile


def test_plugin_root_when_unset_then_macos_system_folder(monkeypatch):
    monkeypatch.delenv(PLUGIN_ENV, raising=False)
    assert str(plugin_root()) == DEFAULT_PLUGIN_ROOT, "Portable default plugin folder"


def test_profile_when_plugin_root_set_then_paths_follow_it(monkeypatch, tmp_path):
    monkeypatch.setenv(PLUGIN_ENV, str(tmp_path))
    chain = profile("rx6-dx35")
    assert [s["path"] for s in chain["speech"]] == [
        str(tmp_path / "RX 12 Voice De-noise.vst3"),
        str(tmp_path / "Accentize-dxRevivePro.vst3"),
    ], "Built-in profiles resolve against the configured root"
    assert profile("bypass") == {"speech": [], "speakers": {}, "master": []}
    with pytest.raises(ValueError):
        profile("unknown")


def test_model_adapters_when_extra_missing_then_install_hint(monkeypatch, tmp_path):
    monkeypatch.setattr(models.importlib.util, "find_spec", lambda name: None)
    audio = tmp_path / "a.wav"
    with pytest.raises(ModuleNotFoundError, match=r"vexy-speakup\[models\]"):
        diarize(audio, tmp_path, "mlx", "", 1, 10)
    with pytest.raises(ModuleNotFoundError, match="models"):
        score(audio, tmp_path)


def test_diarize_when_mlx_then_runs_bundled_worker(monkeypatch, tmp_path):
    calls = []

    def fake(args, timeout, log):
        calls.append(args)
        output = next(a for a in args if a.startswith("--output="))[9:]
        segments = [{"start": 0, "end": 1.05, "speaker": 0}]
        Path(output).write_text(json.dumps({"segments": segments}))
        return ""

    monkeypatch.setattr(models, "worker", lambda python="": [sys.executable, "-m", "w"])
    monkeypatch.setattr(models, "command", fake)
    turns = diarize(tmp_path / "a.wav", tmp_path, "mlx", "", 1.05, 10)
    assert turns == [{"start": 0.0, "end": 1.05, "speaker": "0"}], "Parsed worker turns"
    assert "--backend=mlx" in calls[0] and "diarize" in calls[0]


def test_clip_eof_when_last_frame_overruns_then_clipped():
    from vexy_speakup.model_worker import clip_eof

    rows = clip_eof([{"start": 0, "end": 10.05, "speaker": 0}], 10.0)
    assert rows[0]["end"] == 10.0 and rows[0]["end_before_eof_clip"] == 10.05


def test_diarize_when_backend_unknown_then_value_error(tmp_path):
    with pytest.raises(ValueError):
        diarize(tmp_path / "a.wav", tmp_path, "other", "", 1, 10)


def test_version_command_reports_package_version():
    assert version() == __version__ and __version__, "Version is nonempty"


def test_inventory_when_root_has_bundles_then_lists_them(monkeypatch, tmp_path):
    from vexy_speakup.audit import inventory

    root = tmp_path / "VST3"
    (root / "Vendor/B.vst3").mkdir(parents=True)
    (root / "A.vst3").mkdir()
    (root / "notes.vst3").parent.mkdir(exist_ok=True)
    monkeypatch.setenv(PLUGIN_ENV, str(root))
    output = tmp_path / "inventory.json"
    assert inventory(str(output)) == f"2 plugins: {output}"
    assert '"count": 2' in output.read_text(), "Only bundle directories counted"
    monkeypatch.setenv(PLUGIN_ENV, str(tmp_path / "absent"))
    with pytest.raises(FileNotFoundError):
        inventory(str(output))
