"""Per-track ADM ceiling helper behaves like the legacy closure."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers.processing.audio import _adm_adaptive_ceiling_per_track


class TestAdmAdaptiveCeilingPerTrack:
    def test_first_cycle_tightens_by_overshoot_plus_safety(self):
        entry = {"filename": "a.wav", "peak_db_decoded": -0.5}
        new, floored, diverging = _adm_adaptive_ceiling_per_track(
            entry, current=-1.5, history=[],
        )
        # overshoot = -0.5 - (-1.5) = 1.0; plus safety 0.3 → 1.3, capped at 1.0.
        assert new == pytest.approx(-2.5, abs=0.01)
        assert floored is False
        assert diverging is False

    def test_floor_reached(self):
        entry = {"filename": "a.wav", "peak_db_decoded": -0.1}
        new, floored, _ = _adm_adaptive_ceiling_per_track(
            entry, current=-5.5, history=[],
        )
        # Proposed < -6 → clamp to -6, floored=True.
        assert new == pytest.approx(-6.0)
        assert floored is True

    def test_divergence_detected_when_peak_grows(self):
        # After appending {ceiling=-2.5, worst_peak=-0.1}, history becomes:
        #   [-2] = {ceiling=-2.0, worst_peak=-0.3}  (pre-existing last entry)
        #   [-1] = {ceiling=-2.5, worst_peak=-0.1}  (newly appended)
        # d_ceiling = -2.0 - (-2.5) = 0.5 > 1e-3
        # d_peak    = -0.3 - (-0.1) = -0.2  (peak got WORSE as we tightened)
        # slope = -0.2 / 0.5 = -0.4 <= 0  → diverging
        entry = {"filename": "a.wav", "peak_db_decoded": -0.1}
        history = [
            {"ceiling": -1.5, "worst_peak": -0.5},
            {"ceiling": -2.0, "worst_peak": -0.3},  # last pre-existing entry
        ]
        new, floored, diverging = _adm_adaptive_ceiling_per_track(
            entry, current=-2.5, history=history,
        )
        assert diverging is True
        assert new == pytest.approx(-2.5)  # unchanged
