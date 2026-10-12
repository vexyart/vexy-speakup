# this_file: tests/test_pipeline.py
"""Timeline, input-boundary and publication acceptance tests."""

import numpy as np
import pytest

from vexy_speakup.levels import level_gain
from vexy_speakup.media import destinations
from vexy_speakup.turns import parse_turns, partition


def test_partition_overlap_is_rendered_once_and_gaps_retained():
    turns = parse_turns(
        [
            {"start": 1, "end": 4, "speaker": "A"},
            {"start": 3, "end": 5, "speaker": "B"},
        ],
        6,
    )
    rows = partition(turns, 6, 2)
    assert [(r["start"], r["end"], r["speakers"]) for r in rows] == [
        (0, 1, []),
        (1, 3, ["A"]),
        (3, 4, ["A", "B"]),
        (4, 5, ["B"]),
        (5, 6, []),
    ]
    assert sum(r["end"] - r["start"] for r in rows) == 6, "No loss or duplication"


@pytest.mark.parametrize(
    "row",
    [
        {"start": -1, "end": 1, "speaker": "A"},
        {"start": 0, "end": float("nan"), "speaker": "A"},
        {"start": 0, "end": 9, "speaker": "A"},
        {"start": 0, "end": 1, "speaker": "../../escape"},
        {"start": True, "end": 1, "speaker": "A"},
    ],
)
def test_invalid_turns_fail_at_boundary(row):
    with pytest.raises(ValueError):
        parse_turns([row], 6)


def test_silent_turns_partition_to_background():
    assert partition([], 1, 30) == [{"start": 0.0, "end": 1, "speakers": []}], (
        "Silence preserved"
    )


def test_destinations_match_input_extension_and_reject_input_overwrite(tmp_path):
    source = tmp_path / "meeting.mp4"
    source.touch()
    work, output = destinations(source, "", "", "_improved")
    assert work == tmp_path / "meeting"
    assert output == tmp_path / "meeting_improved.mp4"
    with pytest.raises(ValueError):
        destinations(source, "", str(source), "_improved")


def test_level_gain_does_not_amplify_silence_and_caps_large_gain():
    assert level_gain(np.zeros((48000, 1), np.float32), 48000, -18) == 0
    x = np.sin(np.arange(48000) * 0.1)[:, None].astype(np.float32) * 0.003
    assert 0 < level_gain(x, 48000, -18) <= 12, "Quiet turns have bounded gain"


def test_short_turns_have_defined_loudness_gain():
    assert np.isfinite(level_gain(np.ones((48, 1), np.float32) * 0.1, 48000, -18))
