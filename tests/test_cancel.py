# this_file: tests/test_cancel.py
"""Cancellation terminates only the subprocess group launched by this operation."""

import subprocess
import sys
import threading
import time

import pytest

from vexy_speakup.cancel import scope
from vexy_speakup.media import command


def test_command_when_cancelled_then_stop_silent_process_and_descendant(tmp_path):
    token = threading.Event()
    pid_file = tmp_path / "child.pid"
    script = (
        "import subprocess,time,pathlib; p=subprocess.Popen(['sleep','30']); pathlib.Path("
        + repr(str(pid_file))
        + ").write_text(str(p.pid)); time.sleep(30)"
    )
    thread = threading.Thread(target=lambda: (time.sleep(0.3), token.set()))
    thread.start()
    started = time.monotonic()
    with scope(token), pytest.raises(InterruptedError, match="cancelled"):
        command([sys.executable, "-c", script], timeout=20)
    thread.join()
    assert time.monotonic() - started < 3
    child = int(pid_file.read_text())
    result = subprocess.run(
        ["ps", "-p", str(child), "-o", "stat="],
        capture_output=True,
        text=True,
        check=False,
    )
    assert not result.stdout.strip() or result.stdout.strip().startswith("Z"), (
        "Descendant is no longer running"
    )


def test_command_when_deadline_expires_then_raise_without_restart():
    with pytest.raises(subprocess.TimeoutExpired):
        command([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.1)
