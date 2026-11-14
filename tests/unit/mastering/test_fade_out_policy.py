"""Which fade-out mastering gives a track, from its cached state entry.

The track file's Fade Out row decides: a number of seconds is that fade, and
"no fade" (None in the state) is none. A track that never says, either with
no row or with no entry at all, gets the default.

Usage:
    python -m pytest tests/unit/mastering/test_fade_out_policy.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.master_tracks import DEFAULT_FADE_OUT_SECONDS, fade_out_for_track

pytestmark = pytest.mark.unit


def test_the_default_is_three_seconds():
    assert DEFAULT_FADE_OUT_SECONDS == 3.0


@pytest.mark.parametrize("entry, expected", [
    # Never said: no entry, or an entry without the row.
    (None, 3.0),
    ({}, 3.0),
    ({"title": "Paper Boats", "status": "Generated"}, 3.0),
    # Said a number of seconds.
    ({"fade_out": 8.0}, 8.0),
    ({"fade_out": 3}, 3.0),
    # Said no fade.
    ({"fade_out": None}, None),
    ({"fade_out": 0}, None),
    ({"fade_out": 0.0}, None),
    ({"fade_out": -2.0}, None),
    # Not a number of seconds: a hand-edited cache. No fade, never a guess.
    ({"fade_out": True}, None),
    ({"fade_out": "5s"}, None),
])
def test_fade_out_for_track(entry, expected):
    assert fade_out_for_track(entry) == expected
