# this_file: src/vexy_speakup/assets.py
"""Download bundled free plugins from vexy-speakup-assets (Git LFS) on demand.

The manifest shipped with the package pins every file by commit and SHA-256, so a
download is either the exact published bundle or an error. Installed bundles live in
the user data folder, one directory per platform.
"""

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from platformdirs import user_data_path

ASSETS_REPO = "vexyart/vexy-speakup-assets"
ASSETS_REVISION = "fd90393f4ca32dfb674c93c02c479a7594dfb844"
ASSETS_ENV = "VEXY_SPEAKUP_ASSETS_DIR"
TIMEOUT = 120
INSTALLER_TIMEOUT = 900


def manifest() -> dict:
    return json.loads((Path(__file__).with_name("assets_manifest.json")).read_text())


def platform_key() -> str | None:
    """`macos` or `windows-x64`; None where no bundled builds exist."""
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "win32" and platform.machine().lower() in {"amd64", "x86_64"}:
        return "windows-x64"
    return None


def assets_dir() -> Path:
    override = os.environ.get(ASSETS_ENV)
    root = Path(override).expanduser() if override else user_data_path("vexy-speakup")
    return root / "plugins" / (platform_key() or "unsupported")


def available() -> list[dict]:
    """Manifest entries for this platform, flattened to one row per bundle."""
    key = platform_key()
    return [
        {**entry, "id": plugin["id"], "name": plugin["name"],
         "version": plugin["version"], "license": plugin["license"]}
        for plugin in manifest()["plugins"]
        for entry in plugin["files"].get(key or "", [])
    ]


def url(path: str) -> str:
    quoted = urllib.parse.quote(path)
    return f"https://media.githubusercontent.com/media/{ASSETS_REPO}/{ASSETS_REVISION}/{quoted}"


def _extract(archive: Path, destination: Path) -> None:
    """Unzip keeping Unix modes, refusing paths that escape the destination."""
    with zipfile.ZipFile(archive) as reader:
        for info in reader.infolist():
            target = (destination / info.filename).resolve()
            if destination.resolve() not in target.parents:
                raise ValueError(f"Unsafe path in {archive.name}: {info.filename}")
            reader.extract(info, destination)
            mode = (info.external_attr >> 16) & 0o777
            if mode:
                os.chmod(target, mode)


def _remove(path: Path) -> None:
    """VST3 bundles are folders on macOS; a Windows VST3 may be a single DLL."""
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def _download(entry: dict, destination: Path) -> Path:
    """Fetch one pinned LFS file and refuse it unless its SHA-256 matches."""
    with urllib.request.urlopen(url(entry["path"]), timeout=TIMEOUT) as response:
        destination.write_bytes(response.read())
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    if digest != entry["sha256"]:
        raise ValueError(f"{entry['bundle']}: sha256 {digest} != {entry['sha256']}")
    return destination


def common_vst3() -> Path:
    """Windows system VST3 folder (`{commoncf64}\\VST3`), where vendor installers write."""
    common = os.environ.get("CommonProgramW6432") or os.environ.get(
        "CommonProgramFiles", r"C:\Program Files\Common Files"
    )
    return Path(common) / "VST3"


def _run_installer(entry: dict, force: bool = False) -> Path:
    """Run a vendor installer silently; it asks for admin rights (UAC) itself.

    One process installs at a time (lock file); the others wait, then reuse the result.
    """
    target = common_vst3() / entry["bundle"]
    if target.exists() and not force:
        return target
    root = assets_dir()
    root.mkdir(parents=True, exist_ok=True)
    lock = root / f".{entry['bundle']}.lock"
    deadline = time.monotonic() + INSTALLER_TIMEOUT
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                raise TimeoutError(f"Another install of {entry['bundle']} holds {lock}")
            time.sleep(1)
    try:
        if target.exists() and not force:
            return target
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            setup = _download(entry, Path(temporary) / Path(entry["path"]).name)
            log = root / f"{Path(entry['path']).stem}.log"
            result = subprocess.run(
                [str(setup), *entry.get("args", []), f"/LOG={log}"],
                timeout=INSTALLER_TIMEOUT,
                check=False,
            )
        if result.returncode or not target.exists():
            raise RuntimeError(
                f"{entry['bundle']} installer exited {result.returncode} without "
                f"installing {target} (cancelled UAC prompt?); log: {log}"
            )
        return target
    finally:
        lock.unlink(missing_ok=True)


def install(entry: dict, force: bool = False) -> Path:
    """Download, verify and atomically place one bundle; reuse a verified install.

    Parallel render workers may race: the first rename wins and the others keep it.
    An existing bundle is only removed with `force`, never while others may load it.
    """
    if "installer" in entry:
        return _run_installer(entry, force)
    root = assets_dir()
    bundle, marker = root / entry["bundle"], root / f".{entry['bundle']}.sha256"
    verified = marker.is_file() and marker.read_text().strip() == entry["sha256"]
    if verified and bundle.exists() and not force:
        return bundle
    if force:
        _remove(bundle)
        marker.unlink(missing_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        archive = _download(entry, Path(temporary) / "bundle.zip")
        unpacked = Path(temporary) / "out"
        _extract(archive, unpacked)
        try:
            os.rename(unpacked / entry["bundle"], bundle)
        except OSError:
            if not bundle.exists():
                raise  # not a lost race: a real failure
    staged = root / f".{entry['bundle']}.{os.getpid()}.tmp"
    staged.write_text(entry["sha256"] + "\n")
    os.replace(staged, marker)
    return bundle


def bundled_plugin(name: str) -> Path | None:
    """Path of the bundled plugin named `name` (e.g. `pp-track.vst3`), fetched if needed."""
    for entry in available():
        if entry["bundle"] == name:
            return install(entry)
    return None


def fetch(force: bool = False) -> list[str]:
    """Download every bundled free plugin for this platform (`vexy-speakup assets fetch`)."""
    if platform_key() is None:
        raise RuntimeError("Bundled plugins exist only for macOS and Windows x64")
    return [str(install(entry, force)) for entry in available()]


def location(entry: dict) -> Path:
    """Where this entry's bundle lives once installed."""
    folder = common_vst3() if "installer" in entry else assets_dir()
    return folder / entry["bundle"]


def listing() -> list[dict]:
    """Bundled free plugins for this platform and whether each is installed."""
    return [
        {"bundle": e["bundle"], "plugin": e["name"], "version": e["version"],
         "license": e["license"], "installed": location(e).exists(),
         "method": "installer (admin)" if "installer" in e else "download"}
        for e in available()
    ]
