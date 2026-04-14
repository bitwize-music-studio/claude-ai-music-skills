#!/usr/bin/env python3
"""Unit tests for album signature aggregation (#290 phase 3a)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.album_signature import (
    build_signature,
    compute_anchor_deltas,
)


def _analysis(**overrides) -> dict:
    """Minimal analyze_track()-shaped dict for tests."""
    base = {
        "filename": "01.wav",
        "duration": 180.0,
        "sample_rate": 96000,
        "lufs": -14.0,
        "peak_db": -1.0,
        "rms_db": -20.0,
        "dynamic_range": 8.0,
        "band_energy": {
            "sub_bass": 8.0, "bass": 18.0, "low_mid": 20.0,
            "mid": 25.0, "high_mid": 14.0, "high": 10.0, "air": 5.0,
        },
        "tinniness_ratio": 0.3,
        "max_short_term_lufs": -10.0,
        "max_momentary_lufs": -8.0,
        "short_term_range": 6.5,
        "stl_95": -10.5,
        "low_rms": -18.0,
        "vocal_rms": -16.0,
        "signature_meta": {
            "stl_window_count": 60,
            "stl_top_5pct_count": 3,
            "vocal_rms_source": "band_fallback",
        },
    }
    base.update(overrides)
    return base


class TestBuildSignatureHappyPath:
    def test_three_track_album_returns_tracks_and_album_blocks(self):
        results = [
            _analysis(filename="01.wav", lufs=-14.0, stl_95=-10.0, peak_db=-1.0),
            _analysis(filename="02.wav", lufs=-13.8, stl_95=-10.2, peak_db=-1.1),
            _analysis(filename="03.wav", lufs=-14.2, stl_95=-10.4, peak_db=-0.9),
        ]
        sig = build_signature(results)

        assert sig["album"]["track_count"] == 3
        assert len(sig["tracks"]) == 3
        assert sig["tracks"][0]["index"] == 1
        assert sig["tracks"][2]["index"] == 3
        assert sig["tracks"][0]["filename"] == "01.wav"

        # Median of {-14.0, -13.8, -14.2} is -14.0
        assert sig["album"]["median"]["lufs"] == pytest.approx(-14.0)
        # Median of {-10.0, -10.2, -10.4} is -10.2
        assert sig["album"]["median"]["stl_95"] == pytest.approx(-10.2)
        # Range: max(-13.8) - min(-14.2) = 0.4
        assert sig["album"]["range"]["lufs"] == pytest.approx(0.4)
