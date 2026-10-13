# this_file: tests/test_assets.py
"""Bundled free plugins download from the pinned LFS repo, verified and on demand."""

import hashlib
import io
import zipfile

import pytest

from vexy_speakup import assets


def bundle_zip(name: str = "Free.vst3", member: str = "Contents/MacOS/Free") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as writer:
        info = zipfile.ZipInfo(f"{name}/{member}")
        info.external_attr = 0o755 << 16
        writer.writestr(info, b"binary")
    return buffer.getvalue()


@pytest.fixture
def served(monkeypatch, tmp_path):
    """Serve one manifest entry from memory; count downloads."""
    data = bundle_zip()
    entry = {
        "path": "plugins/free/1/macos/Free.vst3.zip",
        "bundle": "Free.vst3",
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }
    calls = []

    def urlopen(url, timeout):
        calls.append(url)
        return io.BytesIO(data)

    monkeypatch.setenv(assets.ASSETS_ENV, str(tmp_path))
    monkeypatch.setattr(assets, "platform_key", lambda: "macos")
    monkeypatch.setattr(assets.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(
        assets,
        "manifest",
        lambda: {"plugins": [{"id": "free", "name": "Free", "version": "1",
                              "license": "GPL-3.0", "files": {"macos": [entry]}}]},
    )
    return entry, calls


def test_shipped_manifest_when_loaded_then_pins_every_file():
    for plugin in assets.manifest()["plugins"]:
        assert plugin["license"] and plugin["files"].get("macos"), plugin["id"]
        for files in plugin["files"].values():
            assert all(len(f["sha256"]) == 64 for f in files), "Every file is pinned"


def test_url_when_path_has_spaces_then_quoted_and_pinned():
    link = assets.url("plugins/x/1/macos/Noise Repellent.vst3.zip")
    assert assets.ASSETS_REVISION in link and "Noise%20Repellent" in link


def test_bundled_plugin_when_missing_then_downloads_once(served):
    _, calls = served
    path = assets.bundled_plugin("Free.vst3")
    assert path == assets.assets_dir() / "Free.vst3" and path.is_dir()
    assert (path / "Contents/MacOS/Free").stat().st_mode & 0o111, "Mode restored"
    assert assets.bundled_plugin("Free.vst3") == path and len(calls) == 1, "Reused"
    assert assets.bundled_plugin("Absent.vst3") is None
    assert assets.listing()[0]["installed"] is True


def test_install_when_race_lost_then_keeps_existing_bundle(served):
    entry, _ = served
    existing = assets.assets_dir() / "Free.vst3"
    (existing / "keep").mkdir(parents=True)
    assert assets.install(entry) == existing and (existing / "keep").is_dir()


def test_install_when_hash_differs_then_refuses(served):
    entry, _ = served
    with pytest.raises(ValueError, match="sha256"):
        assets.install({**entry, "sha256": "0" * 64})
    assert not (assets.assets_dir() / "Free.vst3").exists()


def test_extract_when_member_escapes_then_refuses(tmp_path):
    archive = tmp_path / "evil.zip"
    archive.write_bytes(bundle_zip("..", "evil"))
    with pytest.raises(ValueError, match="Unsafe"):
        assets._extract(archive, tmp_path / "out")


def test_fetch_when_platform_unsupported_then_error(monkeypatch):
    monkeypatch.setattr(assets, "platform_key", lambda: None)
    with pytest.raises(RuntimeError, match="macOS and Windows"):
        assets.fetch()


def test_install_when_bundle_is_single_file_then_reused_and_forced(served, monkeypatch):
    entry, _ = served
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as writer:
        writer.writestr("Free.vst3", b"dll")
    data = buffer.getvalue()
    entry.update(sha256=hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(
        assets.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(data)
    )
    path = assets.install(entry)
    assert path.is_file() and path.read_bytes() == b"dll"
    assert assets.install(entry) == path, "A verified single-file bundle is reused"
    assert assets.install(entry, force=True).read_bytes() == b"dll", "Force replaces"


@pytest.fixture
def installer(monkeypatch, tmp_path):
    """A Windows installer entry whose 'run' creates the bundle in Common Files."""
    data = b"MZ installer"
    entry = {
        "path": "plugins/gate/1/windows-x64/Gate_Installer.exe",
        "bundle": "Gate.vst3",
        "sha256": hashlib.sha256(data).hexdigest(),
        "installer": "inno",
        "args": ["/VERYSILENT"],
    }
    common = tmp_path / "Common Files"
    runs = []

    def run(args, timeout, check):
        runs.append(args)
        (common / "VST3" / "Gate.vst3").mkdir(parents=True)
        return assets.subprocess.CompletedProcess(args, 0)

    monkeypatch.setenv(assets.ASSETS_ENV, str(tmp_path / "data"))
    monkeypatch.setenv("CommonProgramW6432", str(common))
    monkeypatch.setattr(assets.urllib.request, "urlopen", lambda u, timeout: io.BytesIO(data))
    monkeypatch.setattr(assets.subprocess, "run", run)
    return entry, runs, common / "VST3" / "Gate.vst3"


def test_install_when_installer_then_runs_silently_once(installer):
    entry, runs, target = installer
    assert assets.install(entry) == target and target.is_dir()
    assert runs[0][1] == "/VERYSILENT" and runs[0][-1].startswith("/LOG="), runs
    assert assets.install(entry) == target and len(runs) == 1, "Installed: not rerun"
    assert not list(assets.assets_dir().glob(".*.lock")), "Lock released"
    assert assets.location(entry) == target


def test_install_when_installer_fails_then_error_and_lock_released(installer, monkeypatch):
    entry, _, target = installer
    monkeypatch.setattr(
        assets.subprocess, "run",
        lambda args, timeout, check: assets.subprocess.CompletedProcess(args, 1),
    )
    with pytest.raises(RuntimeError, match="UAC"):
        assets.install(entry)
    assert not target.exists() and not list(assets.assets_dir().glob(".*.lock"))


def test_install_when_installer_locked_elsewhere_then_times_out(installer, monkeypatch):
    entry, runs, _ = installer
    assets.assets_dir().mkdir(parents=True)
    (assets.assets_dir() / ".Gate.vst3.lock").touch()
    monkeypatch.setattr(assets, "INSTALLER_TIMEOUT", 0)
    with pytest.raises(TimeoutError):
        assets.install(entry)
    assert runs == [], "Never runs a second installer concurrently"


def test_shipped_manifest_when_windows_then_vocal_gate_uses_installer(monkeypatch):
    monkeypatch.setattr(assets, "platform_key", lambda: "windows-x64")
    gate = [e for e in assets.available() if e["bundle"] == "Vocal Gate.vst3"]
    assert gate and gate[0]["installer"] == "inno" and "/VERYSILENT" in gate[0]["args"]
