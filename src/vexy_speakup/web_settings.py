# this_file: src/vexy_speakup/web_settings.py
"""Browser-editable installation paths, retaining custom candidate definitions."""

import os
import tempfile
from pathlib import Path

import tomli_w
from pydantic import BaseModel, ConfigDict, Field

from .settings import _validate, config_file, read_settings


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plugin_root: str
    workers: int = Field(ge=1, le=128)


def add_settings(app, session):
    @app.get("/api/settings")
    def get_settings():
        values = read_settings()
        return {
            "values": values,
            "path": str(config_file()),
            "overrides": {
                key: os.environ.get(env, "")
                for key, env in (
                    ("plugin_root", "VEXY_SPEAKUP_PLUGIN_ROOT"),
                )
            },
        }

    @app.post("/api/settings")
    def save_settings(request: Settings):
        with session.lock:
            if session.state["busy"]:
                raise ValueError("Wait for the current operation to finish")
            values = read_settings()
            if not os.environ.get("VEXY_SPEAKUP_PLUGIN_ROOT"):
                values["paths"]["plugin_root"] = request.plugin_root
            values["processing"]["workers"] = request.workers
            _validate(values)
            path = config_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                backup = path.with_suffix(".toml.bak")
                if not backup.exists():
                    with backup.open("xb") as writer:
                        writer.write(path.read_bytes())
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    "w", dir=path.parent, delete=False
                ) as writer:
                    temporary = Path(writer.name)
                    writer.write(tomli_w.dumps(values))
                    writer.flush()
                    os.fsync(writer.fileno())
                os.replace(temporary, path)
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
            session.manifest = None
        return {"saved": True}
