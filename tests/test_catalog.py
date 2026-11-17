# this_file: tests/test_catalog.py
"""Researched plugins are detected by file name; auto chains follow installed plugins."""

import json

import pytest

from vexy_speakup import catalog
from vexy_speakup.profiles import profile


@pytest.fixture
def root(tmp_path, monkeypatch):
    """A VST3 folder with a vendor subfolder, a nested Windows binary and an unknown plugin."""
    folder = tmp_path / "VST3"
    (folder / "iZotope" / "RX 12 Voice De-noise.vst3" / "Contents").mkdir(parents=True)
    (folder / "Accentize-dxRevivePro.vst3" / "Contents" / "x86_64-win").mkdir(parents=True)
    (folder / "Accentize-dxRevivePro.vst3" / "Contents" / "x86_64-win" / "Inner.vst3").touch()
    (folder / "Accentize-DeRoomPro2.vst3").mkdir()
    (folder / "Ozone 12 Maximizer.vst3").mkdir()
    (folder / "Unknown.vst3").mkdir()
    monkeypatch.setenv("VEXY_SPEAKUP_PLUGIN_ROOT", str(folder))
    monkeypatch.setenv("VEXY_SPEAKUP_CONFIG", str(tmp_path / "none.toml"))
    return folder


def test_scan_when_nested_then_bundles_only(root):
    found = catalog.scan(root)
    assert found["RX 12 Voice De-noise.vst3"] == root / "iZotope" / "RX 12 Voice De-noise.vst3"
    assert "Inner.vst3" not in found, "Never descends into a bundle"
    assert "Unknown.vst3" in found


def test_detect_when_installed_or_bundled_then_catalog_rows(root):
    rows = {r["bundle"]: r for r in catalog.detect(root)}
    assert rows["RX 12 Voice De-noise.vst3"]["source"] == "installed"
    assert rows["Noise Repellent.vst3"]["source"] == "bundled", "Free plugins always offered"
    assert "Unknown.vst3" not in rows and "Clear.vst3" not in rows
    assert all(r["role"] and r["stage"] in catalog.STAGES for r in rows.values())


def test_auto_chains_when_partial_install_then_only_complete_chains(root):
    chains = catalog.auto_chains(root)
    assert {"auto-free-denoise", "auto-free-gate", "auto-restore", "auto-clean"} <= set(chains)
    assert "auto-dialogue" not in chains and "auto-gate" not in chains, "Missing plugins"
    clean = chains["auto-clean"]
    assert [s["path"].split("/")[-1] for s in clean["speech"]] == [
        "RX 12 Voice De-noise.vst3", "Accentize-DeRoomPro2.vst3", "Accentize-dxRevivePro.vst3"
    ], "Stage order denoise, dereverb, restore; installed path used"
    assert clean["speech"][0]["path"] == str(root / "iZotope" / "RX 12 Voice De-noise.vst3")
    assert [s["path"].split("/")[-1] for s in clean["master"]] == ["Ozone 12 Maximizer.vst3"]
    assert catalog.auto_chains(root) == chains, "Deterministic for a given install"


def test_auto_chains_when_nothing_installed_then_open_source_chains(tmp_path):
    chains = catalog.auto_chains(tmp_path / "absent")
    assert set(chains) == {"auto-free-denoise", "auto-free-gate"}
    names = {s["path"].split("/")[-1] for c in chains.values()
             for s in c["speech"] + c["master"]}
    assert names <= {"Noise Repellent.vst3", "Vocal Gate.vst3", "pp-track.vst3",
                     "pp-master.vst3", "master_me.vst3"}


def test_profile_when_auto_name_then_resolves_or_explains(root):
    assert profile("auto-clean")["master"][0]["path"].endswith("Ozone 12 Maximizer.vst3")
    with pytest.raises(ValueError, match="not installed"):
        profile("auto-dialogue")


def test_catalog_when_loaded_then_has_provenance_and_no_limiter_in_speech():
    data = catalog.catalog()
    assert len(data["source_sha256"]) == 64 and data["excluded"]
    stages = {p["bundle"]: p["stage"] for p in data["plugins"]}
    assert stages["Ozone 12 Maximizer.vst3"] == "master"
    for plugin in data["plugins"]:
        json.dumps(plugin["parameters"])  # serialisable into job snapshots


def test_auto_chains_when_space_plugins_installed_then_after_accentize(root):
    for name in ("Accentize-VoiceGate2.vst3", "Wider.vst3", "StageOne2.vst3"):
        (root / name).mkdir()
    chains = catalog.auto_chains(root)
    names = lambda c: [s["path"].split("/")[-1] for s in chains[c]["speech"]]
    base = ["Accentize-VoiceGate2.vst3", "Accentize-dxRevivePro.vst3"]
    assert names("auto-gate") == base, "The liked Accentize chain stays unchanged"
    assert names("auto-gate-wider") == [*base, "Wider.vst3"], "Space comes after restore"
    assert names("auto-gate-stageone") == [*base, "builtin:mono-fold", "StageOne2.vst3"]
    assert chains["auto-gate-wider"]["master"] == chains["auto-gate"]["master"]


def test_downloads_when_free_plugin_missing_then_vendor_link(root):
    rows = {r["bundle"]: r for r in catalog.downloads(root)}
    assert rows["Wider.vst3"]["download"].startswith("https://polyversemusic.com/")
    assert not rows["Wider.vst3"]["open_source"], "Freeware, not redistributable"
    (root / "Wider.vst3").mkdir()
    assert "Wider.vst3" not in {r["bundle"] for r in catalog.downloads(root)}


def test_auto_chains_when_stageone_then_mono_fold_directly_before_it(root):
    for name in ("Accentize-VoiceGate2.vst3", "StageOne2.vst3"):
        (root / name).mkdir()
    speech = catalog.auto_chains(root)["auto-gate-stageone"]["speech"]
    paths = [s["path"].split("/")[-1] for s in speech]
    assert paths[-2:] == ["builtin:mono-fold", "StageOne2.vst3"]
    assert "builtin:mono-fold" not in str(catalog.auto_chains(root)["auto-gate"])
