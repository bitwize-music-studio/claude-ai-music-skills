#!/usr/bin/env python3
"""Unit tests for the album-mastering anchor selector (#290 phase 2)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.anchor_selector import (
    _spectral_match_score,
)

from tools.mastering.anchor_selector import (
    _mix_quality_score,
    _representativeness_score,
    _ceiling_penalty_score,
    _album_medians,
)


REF = {
    "sub_bass": 8.0,
    "bass":     18.0,
    "low_mid":  20.0,
    "mid":      25.0,
    "high_mid": 14.0,
    "high":     10.0,
    "air":       5.0,
}


class TestSpectralMatchScore:
    def test_exact_match_scores_one(self):
        assert _spectral_match_score(REF, REF) == pytest.approx(1.0)

    def test_mismatched_curve_scores_below_match(self):
        off = {**REF, "mid": 5.0, "high": 30.0}  # large distance
        score_match = _spectral_match_score(REF, REF)
        score_off = _spectral_match_score(off, REF)
        assert score_off < score_match
        assert 0.0 < score_off < 1.0


def _track(**overrides) -> dict:
    base = {
        "filename": "01.wav",
        "stl_95": -14.0,
        "short_term_range": 8.0,
        "low_rms": -20.0,
        "vocal_rms": -18.0,
        "peak_db": -4.0,
        "band_energy": dict(REF),
    }
    base.update(overrides)
    return base


class TestMixQuality:
    def test_on_target_lra_and_spectral_match_scores_near_one(self):
        track = _track(short_term_range=8.0, band_energy=dict(REF))
        score = _mix_quality_score(track, REF, genre_ideal_lra=8.0)
        # LRA difference 0 → 1/(1+0)=1; spectral exact → 1; product = 1
        assert score == pytest.approx(1.0)

    def test_off_target_lra_drops_score(self):
        track = _track(short_term_range=14.0, band_energy=dict(REF))
        score = _mix_quality_score(track, REF, genre_ideal_lra=8.0)
        # |14 − 8| = 6 → 1/7 ≈ 0.143; spectral match = 1 → score ≈ 0.143
        assert score == pytest.approx(1.0 / 7.0, rel=1e-3)


class TestRepresentativeness:
    def test_track_at_median_scores_one(self):
        tracks = [
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
        ]
        medians = _album_medians(tracks)
        score = _representativeness_score(tracks[0], medians)
        assert score == pytest.approx(1.0)

    def test_distant_track_scores_below(self):
        tracks = [
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
            _track(stl_95=-10.0, short_term_range=3.0, low_rms=-12.0, vocal_rms=-10.0),
        ]
        medians = _album_medians(tracks)
        score_close = _representativeness_score(tracks[0], medians)
        score_far = _representativeness_score(tracks[2], medians)
        assert score_close > score_far
        assert 0.0 < score_far < 1.0


class TestCeilingPenalty:
    def test_peak_below_minus3_no_penalty(self):
        assert _ceiling_penalty_score(-6.0) == 0.0
        assert _ceiling_penalty_score(-3.0) == 0.0

    def test_peak_at_0dbfs_max_penalty(self):
        assert _ceiling_penalty_score(0.0) == pytest.approx(1.0)

    def test_peak_midway_scaled(self):
        assert _ceiling_penalty_score(-1.5) == pytest.approx(0.5)
