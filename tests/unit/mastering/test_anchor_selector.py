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
