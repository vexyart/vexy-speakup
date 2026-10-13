# this_file: tests/test_settings.py
"""TOML app settings resolve portable paths and real candidate chains."""

import tomllib

import pytest
from platformdirs import user_config_path

from vexy_speakup.locations import plugin_root
from vexy_speakup.settings import config_file, init_config, read_settings
from vexy_speakup.vst import profile


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    monkeypatch.setenv("VEXY_SPEAKUP_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.delenv("VEXY_SPEAKUP_PLUGIN_ROOT", raising=False)


def test_config_file_when_no_override_then_platformdirs(monkeypatch):
    monkeypatch.delenv("VEXY_SPEAKUP_CONFIG")
    assert (
        config_file()
        == user_config_path("vexy-speakup", appauthor=False) / "config.toml"
    )


def test_init_when_new_then_roundtrips_without_overwriting():
    path = init_config()
    assert tomllib.loads(path.read_text()) == read_settings(), (
        "Generated TOML roundtrips"
    )
    with pytest.raises(FileExistsError):
        init_config()


def test_roots_when_configured_then_used_with_environment_precedence(
    monkeypatch, tmp_path
):
    config_file().write_text(
        f'[paths]\nplugin_root = "{tmp_path}"\ntts_root = "{tmp_path}"\n'
    )
    assert plugin_root() == tmp_path, "Plugin root uses TOML"
    assert "tts_root" not in read_settings()["paths"], "Legacy tts_root is ignored"
    monkeypatch.setenv("VEXY_SPEAKUP_PLUGIN_ROOT", str(tmp_path / "env"))
    assert plugin_root() == tmp_path / "env", "Environment wins over TOML"


def test_profile_when_candidate_has_relative_paths_then_resolve_root(tmp_path):
    config_file().write_text(f'''[paths]
plugin_root = "{tmp_path}"
[candidates.custom]
suffix = "_custom"
master = []
[[candidates.custom.speech]]
path = "Vendor/Voice.vst3"
[candidates.custom.speech.parameters]
mix = 25.0
''')
    assert profile("custom") == {
        "speech": [
            {"path": str(tmp_path / "Vendor/Voice.vst3"), "parameters": {"mix": 25.0}}
        ],
        "speakers": {},
        "master": [],
    }, "Custom candidate renders through the existing chain interface"


@pytest.mark.parametrize(
    "text",
    [
        "schema_version = 2",
        "schema_version = true",
        "typo = true",
        "[paths]\nplugin_root = 1",
        "[processing]\nworkers = 0",
        "[processing]\nworkers = true",
        "[processing]\nmax_chunk = nan",
        "[processing]\ntarget_lufs = -1",
        '[candidates.bad]\nsuffix = "../bad"\nprofile = "dx35"',
        '[candidates.bad]\nsuffix = "_ok"',
        '[candidates.bad]\nsuffix = "_ok"\nspeech = [1]\nmaster = []',
        "[processing]\nunknown = 1",
    ],
)
def test_settings_when_invalid_then_fail_before_processing(text):
    config_file().write_text(text)
    with pytest.raises((ValueError, TypeError)):
        read_settings()


def test_settings_when_explicit_missing_then_fail(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_settings(tmp_path / "missing.toml")


def test_settings_when_customized_then_merge_defaults():
    config_file().write_text("[processing]\nworkers = 7\n")
    settings = read_settings()
    assert settings["processing"]["workers"] == 7
    assert settings["processing"]["max_chunk"] == 30, "Partial TOML retains defaults"


def test_profile_when_alias_cycle_then_fail():
    config_file().write_text("""[candidates.a]
profile = "b"
suffix = "_a"
[candidates.b]
profile = "a"
suffix = "_b"
""")
    with pytest.raises(ValueError, match="Circular"):
        profile("a")


def test_profile_when_alias_then_use_builtin():
    config_file().write_text(
        '[candidates.clean]\nprofile = "bypass"\nsuffix = "_clean"\n'
    )
    assert profile("clean") == {"speech": [], "speakers": {}, "master": []}
