# this_file: tests/test_parallel.py
"""Parallel shards cover every fragment once and propagate worker failures."""

import json
import threading
import time

import pytest

from vexy_speakup.pipeline import render_speakers


def test_render_speakers_when_parallel_then_bound_concurrency_and_cover_jobs(
    monkeypatch, tmp_path
):
    lock = threading.Lock()
    active, maximum = 0, 0
    seen, chains = [], {}

    def worker(args, timeout, log):
        nonlocal active, maximum
        path = args[-1].split("=", 1)[1]
        with open(path) as reader:
            task = json.load(reader)
        with lock:
            active += 1
            maximum = max(maximum, active)
            seen.extend(task["jobs"])
            for job in task["jobs"]:
                chains[job] = task["specs"]
        time.sleep(0.02)
        with lock:
            active -= 1

    monkeypatch.setattr("vexy_speakup.pipeline.command", worker)
    config = {"speech": [], "speakers": {"a": [{"path": "A.vst3"}]}}
    render_speakers(
        {"a": list(range(7)), "b": list(range(7, 12))},
        tmp_path,
        config,
        10,
        False,
        workers=3,
    )
    assert sorted(seen) == list(range(12)), "Every fragment dispatched exactly once"
    assert 1 < maximum <= 3, "Workers execute concurrently within the limit"
    assert chains[0] == config["speakers"]["a"] and chains[7] == [], (
        "Speaker overrides survive sharding"
    )


def test_render_speakers_when_worker_fails_then_raise(monkeypatch, tmp_path):
    def fail(*args):
        raise RuntimeError("native worker crashed")

    monkeypatch.setattr("vexy_speakup.pipeline.command", fail)
    with pytest.raises(RuntimeError, match="crashed"):
        render_speakers({"a": [1, 2]}, tmp_path, {"speech": []}, 10, False, workers=2)


@pytest.mark.parametrize("workers", [0, -1, True, 129])
def test_render_speakers_when_bad_worker_count_then_reject(tmp_path, workers):
    with pytest.raises(ValueError):
        render_speakers({}, tmp_path, {"speech": []}, 10, False, workers=workers)
