# this_file: src/vexy_speakup/job_schema.py
"""Versioned batch job boundary types; choices and source hashes travel with the job."""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .settings import validate_chain


class JobModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class InputFile(JobModel):
    source: Path
    relative: Path
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    turns: list[dict] | dict | None = None


class Variant(JobModel):
    name: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    suffix: str = Field(pattern=r"^_[A-Za-z0-9_-]+$")
    config: dict
    file_speakers: dict[str, dict[str, list[dict]]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_chains(self) -> Self:
        validate_chain(self.config)
        for overrides in self.file_speakers.values():
            validate_chain({"speech": [], "master": [], "speakers": overrides})
        return self


class Processing(JobModel):
    workers: int = Field(default=4, ge=1, le=128, strict=True)
    max_chunk: float = Field(default=30, gt=0, le=3600, allow_inf_nan=False)
    target_lufs: float = Field(default=-16, ge=-70, le=-5, allow_inf_nan=False)
    true_peak: float = Field(default=-2, ge=-9, le=0, allow_inf_nan=False)
    diarizer: Literal["none", "mlx", "sortformer"] = "none"
    evaluate: bool = False


class Task(JobModel):
    file: int = Field(ge=0)
    variant: int = Field(ge=0)
    output: Path
    status: Literal["pending", "running", "complete", "failed", "cancelled"] = "pending"
    output_sha256: str = ""
    report: str = ""
    error: str = ""


class Job(JobModel):
    version: Literal[1] = 1
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    created_at: str
    output_directory: Path
    files: list[InputFile] = Field(min_length=1)
    variants: list[Variant] = Field(min_length=1)
    processing: Processing
    status: Literal["scheduled", "running", "complete", "failed", "cancelled"] = "scheduled"
    tasks: list[Task]

    @model_validator(mode="after")
    def valid_destinations(self) -> Self:
        expected = {
            (f, v) for f in range(len(self.files)) for v in range(len(self.variants))
        }
        if (
            len(self.tasks) != len(expected)
            or {(t.file, t.variant) for t in self.tasks} != expected
        ):
            raise ValueError("Tasks must cover every input/variant pair exactly once")
        if len({v.suffix for v in self.variants}) != len(self.variants):
            raise ValueError("Variant suffixes must be distinct")
        sources = {f.source.resolve() for f in self.files}
        destinations = set()
        for file in self.files:
            if file.relative.is_absolute() or ".." in file.relative.parts:
                raise ValueError(
                    "Input relative paths must stay inside the selected folder"
                )
        for task in self.tasks:
            relative = self.files[task.file].relative
            variant = self.variants[task.variant]
            destination = self.output_directory / relative.with_name(
                relative.stem + variant.suffix + relative.suffix
            )
            if (
                task.output.resolve() != destination.resolve()
                or task.output.resolve() in sources | destinations
            ):
                raise ValueError(
                    "Task output must match its suffix and never overwrite an input or another task"
                )
            destinations.add(task.output.resolve())
        for variant in self.variants:
            if variant.file_speakers.keys() - {str(f.source) for f in self.files}:
                raise ValueError(
                    "Speaker overrides must identify an input file explicitly"
                )
        return self
