# this_file: tests/test_web.py
"""Browser API renders real audio, saves choices, runs and resumes a durable job."""

import time

import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from vexy_speakup.batch import read_job
from vexy_speakup.web import create_app


def wait(client):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        state = client.get("/api/state").json()
        if not state["busy"]:
            assert not state["error"], state["error"]
            return state
        time.sleep(0.05)
    pytest.fail("Local operation did not finish within 45 seconds")


def test_browser_when_listening_then_save_run_resume_and_serve_ranges(
    tmp_path, monkeypatch
):
    folder = tmp_path / "input"
    folder.mkdir()
    sf.write(folder / "voice.wav", np.sin(np.arange(48000) * 0.1) * 0.1, 48000)
    config = tmp_path / "config.toml"
    config.write_text(
        "\n".join(
            f'[candidates.{name}]\nprofile="bypass"\nsuffix="_{name}"'
            for name in ["podcast", "dx35", "dx35-bright", "clear"]
        )
    )
    monkeypatch.setenv("VEXY_SPEAKUP_CONFIG", str(config))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    with TestClient(create_app(str(folder))) as client:
        assert "Listen. Choose." in client.get("/").text
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/api/folders", params={"path": str(tmp_path)}).json()[
            "folders"
        ] == ["input"]
        assert client.get("/api/audio/0/-1").status_code == 404
        assert client.post("/api/run", json={}).status_code == 400
        assert (
            client.post(
                "/api/preview", json={"input_dir": str(folder), "workers": 2}
            ).status_code
            == 200
        )
        state = wait(client)
        assert len(state["manifest"]["groups"][0]["variants"]) == 12
        clip = client.get("/api/audio/0/0", headers={"Range": "bytes=0-31"})
        assert clip.status_code == 206 and len(clip.content) == 32, (
            "Browser playback supports range requests"
        )
        assert client.get("/api/audio/0/500").status_code == 404
        assert (
            client.post(
                "/api/schedule", json={"global_choices": {"dx35": 3}}
            ).status_code
            == 200
        )
        state = wait(client)
        job = read_job(state["job_path"])
        assert job.variants[0].config["speech"][-1]["parameters"]["gain_db"] == 3
        assert client.post("/api/run", json={"workers": 2}).status_code == 200
        wait(client)
        assert client.get("/api/job").json()["status"] == "complete"
        assert client.post("/api/run", json={}).status_code == 200
        wait(client)
        settings = {"plugin_root": "/tmp/plugins", "workers": 2}
        assert client.post("/api/settings", json=settings).status_code == 200
        assert (
            client.get("/api/settings").json()["values"]["candidates"]["dx35"][
                "profile"
            ]
            == "bypass"
        )
        assert config.with_suffix(".toml.bak").exists()
        backup = config.with_suffix(".toml.bak").read_bytes()
        monkeypatch.setenv("VEXY_SPEAKUP_PLUGIN_ROOT", "/environment/plugins")
        settings["plugin_root"] = "/environment/plugins"
        assert client.post("/api/settings", json=settings).status_code == 200
        assert (
            client.get("/api/settings").json()["values"]["paths"]["plugin_root"]
            == "/tmp/plugins"
        ), "Environment overrides must not overwrite saved installation paths"
        assert config.with_suffix(".toml.bak").read_bytes() == backup
        assert (
            client.post("/api/job/load", json={"path": state["job_path"]}).status_code
            == 200
        )
        assert (
            client.post(
                "/api/preview/load", json={"path": state["manifest"]["manifest_path"]}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/preview", json={"input_dir": str(folder), "workers": 0}
            ).status_code
            == 422
        )


def test_browser_when_busy_then_cancel_stops_worker_and_rejects_mutations(
    tmp_path, monkeypatch
):
    from vexy_speakup.cancel import check

    def blocked(**kwargs):
        while True:
            check()
            time.sleep(0.01)

    monkeypatch.setattr("vexy_speakup.web.prepare_preview", blocked)
    with TestClient(create_app()) as client:
        assert (
            client.post("/api/preview", json={"input_dir": str(tmp_path)}).status_code
            == 200
        )
        assert (
            client.post("/api/preview", json={"input_dir": str(tmp_path)}).status_code
            == 400
        )
        assert client.post("/api/job/load", json={"path": "absent"}).status_code == 400
        client.post("/api/cancel", json={})
        deadline = time.monotonic() + 5
        while client.get("/api/state").json()["busy"] and time.monotonic() < deadline:
            time.sleep(0.01)
        state = client.get("/api/state").json()
        assert not state["busy"] and state["message"] == "Stopped"
