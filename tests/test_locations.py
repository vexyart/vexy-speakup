# this_file: tests/test_locations.py
"""Installation roots resolve lazily and fail with setup guidance."""

import pytest

from vexy_speakup import __version__
from vexy_speakup.cli import version
from vexy_speakup.locations import (
    DEFAULT_PLUGIN_ROOT,
    PLUGIN_ENV,
    TTS_ENV,
    plugin_root,
    tts_root,
)
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


def test_tts_root_when_unset_or_missing_then_actionable_error(monkeypatch, tmp_path):
    monkeypatch.delenv(TTS_ENV, raising=False)
    with pytest.raises(FileNotFoundError, match=TTS_ENV):
        tts_root()
    monkeypatch.setenv(TTS_ENV, str(tmp_path / "absent"))
    with pytest.raises(FileNotFoundError, match="not a directory"):
        tts_root()
    monkeypatch.setenv(TTS_ENV, str(tmp_path))
    assert tts_root() == tmp_path


def test_model_adapters_when_tts_root_unset_then_fail_as_oserror(monkeypatch, tmp_path):
    monkeypatch.delenv(TTS_ENV, raising=False)
    audio = tmp_path / "a.wav"
    with pytest.raises(OSError):
        diarize(audio, tmp_path, "mlx", "", 1, 10)
    with pytest.raises(OSError):
        score(audio, tmp_path)


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
