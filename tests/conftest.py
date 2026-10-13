# this_file: tests/conftest.py
"""Local user app settings must not change regression-test behaviour."""

import pytest


@pytest.fixture(autouse=True)
def app_config_isolation(monkeypatch, tmp_path):
    monkeypatch.setenv("VEXY_SPEAKUP_CONFIG", str(tmp_path / "app-config.toml"))
