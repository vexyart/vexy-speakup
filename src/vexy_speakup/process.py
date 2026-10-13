# this_file: src/vexy_speakup/process.py
"""Capture one process with a deadline; cancellation kills only its own new session."""

import os
import signal
import subprocess
import time

from .cancel import check


def capture(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    check()
    with subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    ) as process:
        deadline = time.monotonic() + timeout
        try:
            while True:
                check()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(args, timeout)
                try:
                    out, err = process.communicate(timeout=min(0.1, remaining))
                    return subprocess.CompletedProcess(
                        args, process.returncode, out, err
                    )
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
