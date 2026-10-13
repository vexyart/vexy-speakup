# this_file: src/vexy_speakup/queue.py
"""Execute durable batch jobs with bounded native concurrency and verified resume."""

import fcntl
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from pathlib import Path
from threading import Event

from .batch import create_job, read_job, save_job
from .batch_render import _completed, _execute, _prepare
from .cancel import TOKEN, scope
from .media import sha


def _run_job(
    job_path: str | Path,
    workers: int | None = None,
    file_workers: int = 1,
    force: bool = False,
    verbose: bool = True,
) -> dict:
    """Run/resume a saved job; split the total worker budget across concurrent variants.

    Successful outputs are hash-verified before skipping. Failed/pending work can
    be retried; existing outputs require force. A kernel lock prevents two runners
    from claiming the same job and releases automatically if a process dies.
    """
    path = Path(job_path).expanduser().resolve()
    with path.with_suffix(".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("This job is already running") from exc
        job = read_job(path)
        budget = job.processing.workers if workers is None else workers
        if (
            type(budget) is not int
            or not 1 <= budget <= 128
            or type(file_workers) is not int
            or not 1 <= file_workers <= budget
        ):
            raise ValueError("Require workers [1,128] and file_workers [1,workers]")
        job.status = "running"
        save_job(path, job)
        pending, prepared = [], {}
        work = path.parent / (job.id + "-work")
        for index, file in enumerate(job.files):
            tasks = [t for t in job.tasks if t.file == index]
            try:
                if not file.source.is_file() or sha(file.source) != file.sha256:
                    raise ValueError(f"Input changed or is missing: {file.source}")
                remaining = []
                for task in tasks:
                    try:
                        if not _completed(job, task, work):
                            remaining.append(task)
                    except (OSError, ValueError, KeyError) as exc:
                        task.status, task.error = "failed", str(exc)
                        if force:
                            remaining.append(task)
                if remaining:
                    prepared[index] = _prepare(job, index, work)
                    pending.extend(remaining)
            except (
                OSError,
                ValueError,
                RuntimeError,
                TypeError,
                subprocess.SubprocessError,
            ) as exc:
                for task in tasks:
                    if isinstance(exc, InterruptedError) and task.status == "complete":
                        continue
                    task.status, task.error = (
                        "cancelled" if isinstance(exc, InterruptedError) else "failed",
                        str(exc),
                    )
            save_job(path, job)
        concurrency = min(file_workers, max(1, len(pending)))
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {}
            for task in pending:
                task.status, task.error = "running", ""
                futures[
                    pool.submit(
                        copy_context().run,
                        _execute,
                        job,
                        task,
                        prepared[task.file],
                        work,
                        budget // concurrency,
                        force,
                        verbose,
                    )
                ] = task
            save_job(path, job)
            try:
                for future in as_completed(futures):
                    task = futures[future]
                    try:
                        result = future.result()
                        task.output_sha256, task.report = (
                            result["output_sha256"],
                            result["report"],
                        )
                        task.status = "complete"
                    except Exception as exc:  # noqa: BLE001 -- task boundary records failure and continues other tasks
                        task.status, task.error = (
                            "cancelled"
                            if isinstance(exc, InterruptedError)
                            else "failed",
                            str(exc),
                        )
                    save_job(path, job)
            except BaseException:
                TOKEN.get().set()
                for future, task in futures.items():
                    future.cancel()
                    if task.status != "complete":
                        task.status, task.error = "cancelled", "Runner interrupted"
                job.status = "cancelled"
                save_job(path, job)
                raise

        job.status = (
            "complete" if all(t.status == "complete" for t in job.tasks) else "failed"
        )
        if TOKEN.get() is not None and TOKEN.get().is_set():
            job.status = "cancelled"
        save_job(path, job)
        return {
            "job": str(path),
            "status": job.status,
            "completed": sum(t.status == "complete" for t in job.tasks),
            "failed": sum(t.status == "failed" for t in job.tasks),
            "cancelled": sum(t.status == "cancelled" for t in job.tasks),
            "total": len(job.tasks),
        }


def run_job(
    job_path: str | Path,
    workers: int | None = None,
    file_workers: int = 1,
    force: bool = False,
    verbose: bool = True,
) -> dict:
    """Run a saved job under one cancellation scope, shared with its native workers."""
    with scope(TOKEN.get() or Event()):
        return _run_job(job_path, workers, file_workers, force, verbose)


def batch(
    input_dir: str,
    candidates: str = "",
    output_dir: str = "",
    job_path: str = "",
    recursive: bool = False,
    diarization_dir: str = "",
    workers: int | None = None,
    file_workers: int = 1,
    verbose: bool = True,
    diarizer: str = "none",
    force: bool = False,
) -> dict:
    """Schedule and run a folder in one command; retain the job for inspection/resume."""
    path = create_job(
        input_dir,
        candidates,
        output_dir,
        job_path,
        recursive,
        diarization_dir,
        diarizer,
    )
    return run_job(path, workers, file_workers, force=force, verbose=verbose)
