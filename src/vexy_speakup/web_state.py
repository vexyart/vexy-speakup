# this_file: src/vexy_speakup/web_state.py
"""One cancellable UI operation at a time, with backend worker concurrency."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event, RLock

from .cancel import scope


class Session:
    def __init__(self, input_dir: str):
        self.input_dir = input_dir
        self.manifest = None
        self.job_path = ""
        self.lock = RLock()
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.cancelled = Event()
        self.state = {
            "busy": False,
            "message": "Choose a folder to begin.",
            "error": "",
        }

    def progress(self, message):
        with self.lock:
            self.state["message"] = str(message)

    def launch(self, message, function, done):
        with self.lock:
            if self.state["busy"]:
                raise ValueError("An operation is already running")
            self.cancelled = Event()
            self.state = {"busy": True, "message": message, "error": ""}
            self.pool.submit(self.execute, function, done)

    def execute(self, function, done):
        try:
            with scope(self.cancelled):
                result = function()
            with self.lock:
                done(result)
        except Exception as exc:  # noqa: BLE001 -- UI operation boundary reports backend failures
            with self.lock:
                self.state.update(
                    message="Stopped"
                    if self.cancelled.is_set()
                    else "Operation failed",
                    error=str(exc),
                )
        finally:
            with self.lock:
                self.state["busy"] = False

    def close(self):
        self.cancelled.set()
        self.pool.shutdown(wait=True, cancel_futures=True)
