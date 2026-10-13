# this_file: src/vexy_speakup/web_requests.py
"""Validated local browser request bodies."""

from pydantic import BaseModel, ConfigDict, Field


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Preview(Request):
    input_dir: str
    speaker_mode: bool = False
    diarizer: str = "mlx"
    diarization_dir: str = ""
    workers: int = Field(default=4, ge=1, le=128)
    chains: list[str] = Field(default_factory=list)


class Choices(Request):
    global_choices: dict[str, int] = Field(default_factory=dict)
    speaker_choices: dict[str, dict] = Field(default_factory=dict)
    output_dir: str = ""
    master_name: str = ""


class Location(Request):
    path: str


class Run(Request):
    workers: int = Field(default=4, ge=1, le=128)
    force: bool = False
