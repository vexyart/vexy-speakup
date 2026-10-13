# this_file: src/vexy_speakup/web.py
"""Local browser interface for listening choices and durable batch jobs."""

import json
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Timer

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .batch import read_job
from .listening import schedule_choices
from .preview import prepare_preview
from .profiles import chain_options
from .queue import run_job
from .web_requests import Choices, Location, Preview, Run
from .web_state import Session

ASSETS = Path(__file__).with_name("web_assets")


def create_app(input_dir: str = "") -> FastAPI:
    session = Session(input_dir)

    @asynccontextmanager
    async def lifespan(app):
        yield
        session.close()

    app = FastAPI(lifespan=lifespan)
    app.state.session = session
    app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")

    @app.exception_handler(ValueError)
    @app.exception_handler(OSError)
    async def invalid(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/")
    def index():
        return FileResponse(ASSETS / "index.html")

    @app.get("/api/state")
    def state():
        with session.lock:
            return {
                **session.state,
                "input_dir": session.input_dir,
                "manifest": session.manifest,
                "job_path": session.job_path,
            }

    @app.get("/api/folders")
    def folders(path: str = ""):
        folder = Path(path or session.input_dir or Path.home()).expanduser().resolve()
        if not folder.is_dir():
            raise ValueError("Choose an existing folder")
        return {
            "path": str(folder),
            "parent": str(folder.parent),
            "folders": sorted(
                p.name
                for p in folder.iterdir()
                if p.is_dir() and not p.name.startswith(".")
            ),
        }

    @app.get("/api/chains")
    def chains():
        return chain_options()

    @app.post("/api/preview")
    def preview(request: Preview):
        def done(manifest):
            session.manifest = manifest
            session.input_dir = request.input_dir
            session.progress("Clips ready. Listen, choose, then save your batch job.")

        session.launch(
            "Preparing listening clips…",
            lambda: prepare_preview(**request.model_dump(), progress=session.progress),
            done,
        )
        return {"accepted": True}

    @app.post("/api/preview/load")
    def load_preview(request: Location):
        with session.lock:
            if session.state["busy"]:
                raise ValueError("Wait for the current operation to finish")
            manifest = json.loads(Path(request.path).expanduser().read_text())
            if manifest.get("version") != 1 or not manifest.get("groups"):
                raise ValueError("Unsupported or empty listening session")
            base = read_job(manifest["base_job"])
            first = base.files[0]
            session.input_dir = str(first.source.parents[len(first.relative.parts) - 1])
            session.manifest = manifest
        return {"loaded": True}

    @app.get("/api/audio/{group}/{variant}")
    def audio(group: int, variant: int):
        try:
            row = session.manifest["groups"][group]
            if group < 0 or variant < -1:
                raise IndexError
            path = (
                row["original"] if variant == -1 else row["variants"][variant]["output"]
            )
        except (TypeError, IndexError, KeyError):
            raise HTTPException(404, "Listening clip unavailable") from None
        if not Path(path).is_file():
            raise HTTPException(404, "Listening clip is missing; prepare it again")
        return FileResponse(path, media_type="audio/wav")

    @app.post("/api/schedule")
    def schedule(request: Choices):
        if session.manifest is None:
            raise ValueError("Prepare listening clips first")

        def done(path):
            session.job_path = str(path)
            session.progress("Job saved. Run now or resume it later.")

        session.launch(
            "Saving selected variants…",
            lambda: schedule_choices(session.manifest, **request.model_dump()),
            done,
        )
        return {"accepted": True}

    @app.post("/api/job/load")
    def load_job(request: Location):
        with session.lock:
            if session.state["busy"]:
                raise ValueError("Wait for the current operation to finish")
            path = Path(request.path).expanduser().resolve()
            read_job(path)
            session.job_path = str(path)
        return {"loaded": True}

    @app.get("/api/job")
    def job():
        if not session.job_path:
            return None
        return read_job(session.job_path).model_dump(mode="json")

    @app.post("/api/run")
    def run(request: Run):
        if not session.job_path:
            raise ValueError("Save or open a batch job first")

        def done(result):
            session.progress(
                f"{result['status']}: {result['completed']} of {result['total']} outputs complete; {result['failed']} failures."
            )

        session.launch(
            "Processing saved job…",
            lambda: run_job(session.job_path, **request.model_dump(), verbose=False),
            done,
        )
        return {"accepted": True}

    @app.post("/api/cancel")
    def cancel():
        session.cancelled.set()
        session.progress("Stopping; completed outputs remain available.")
        return {"accepted": True}

    from .web_settings import add_settings

    add_settings(app, session)
    return app


def gui(input_dir: str = "", port: int = 8765, open_browser: bool = True) -> None:
    """Serve the listening UI on localhost; Ctrl-C stops its native workers."""
    import uvicorn

    if open_browser:
        Timer(1, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run(create_app(input_dir), host="127.0.0.1", port=port)
