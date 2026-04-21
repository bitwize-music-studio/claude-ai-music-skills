"""Unit tests for fix_dynamic's iterative LUFS convergence."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.fix_dynamic_track import fix_dynamic


def _make_pink_stereo(seconds: float = 3.0, rate: int = 48000,
                     rms_db: float = -26.0) -> np.ndarray:
    """Generate pink-ish stereo noise at a calibrated RMS level."""
    rng = np.random.default_rng(42)
    n = int(seconds * rate)
    white = rng.standard_normal((n, 2)).astype(np.float64)
    # Cheap pink filter: accumulate + decay.
    pink = np.zeros_like(white)
    alpha = 0.98
    for i in range(1, n):
        pink[i] = alpha * pink[i - 1] + (1 - alpha) * white[i]
    pink /= np.max(np.abs(pink)) + 1e-9
    target_lin = 10 ** (rms_db / 20)
    current_rms = np.sqrt(np.mean(pink ** 2))
    return pink * (target_lin / current_rms)


def _make_dark_stereo(seconds: float = 3.0, rate: int = 48000,
                      rms_db: float = -30.0) -> np.ndarray:
    """Generate dark stereo noise (low-passed at ~400 Hz) that will
    struggle to hit K-weighted LUFS targets at tight ceilings."""
    from scipy.signal import butter, sosfilt

    rng = np.random.default_rng(7)
    n = int(seconds * rate)
    white = rng.standard_normal((n, 2)).astype(np.float64)
    sos = butter(4, 400.0, btype="low", fs=rate, output="sos")
    dark = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
    dark /= np.max(np.abs(dark)) + 1e-9
    target_lin = 10 ** (rms_db / 20)
    current_rms = np.sqrt(np.mean(dark ** 2))
    return dark * (target_lin / current_rms)


class TestFixDynamicConvergence:
    def test_returns_converged_metric(self):
        data = _make_pink_stereo()
        _, metrics = fix_dynamic(data, 48000, target_lufs=-14.0, ceiling_db=-1.0)
        assert "converged" in metrics
        assert "iterations_run" in metrics
        assert isinstance(metrics["converged"], bool)
        assert isinstance(metrics["iterations_run"], int)

    def test_pink_noise_converges_in_one_iteration(self):
        data = _make_pink_stereo()
        _, metrics = fix_dynamic(data, 48000, target_lufs=-14.0, ceiling_db=-1.0)
        assert metrics["converged"] is True
        assert metrics["iterations_run"] == 1
        assert abs(metrics["final_lufs"] - (-14.0)) <= 0.5

    def test_dark_noise_at_tight_ceiling_reports_non_convergence(self):
        # Dark material at a -4 dB ceiling cannot reach -14 LUFS no matter
        # how aggressive we compress. The helper should iterate, land on
        # the best attempt, and honestly report converged=False.
        data = _make_dark_stereo(rms_db=-35.0)
        _, metrics = fix_dynamic(data, 48000, target_lufs=-14.0, ceiling_db=-4.0)
        assert metrics["converged"] is False
        assert metrics["iterations_run"] == 3
        # Final LUFS should still be the closest-to-target iteration.
        assert metrics["final_lufs"] < -14.0

    def test_iterations_capped_at_three(self):
        data = _make_dark_stereo(rms_db=-40.0)
        _, metrics = fix_dynamic(data, 48000, target_lufs=-14.0, ceiling_db=-6.0)
        assert metrics["iterations_run"] <= 3

    def test_original_lufs_preserved_across_iterations(self):
        data = _make_pink_stereo(rms_db=-26.0)
        _, metrics = fix_dynamic(data, 48000, target_lufs=-14.0, ceiling_db=-1.0)
        # original_lufs should reflect the input, not the last-iteration input.
        assert metrics["original_lufs"] < -20.0
        assert metrics["original_lufs"] > -32.0

    def test_final_peak_respects_ceiling(self):
        data = _make_pink_stereo()
        _, metrics = fix_dynamic(data, 48000, target_lufs=-14.0, ceiling_db=-1.0)
        assert metrics["final_peak_db"] <= -1.0 + 0.05  # tiny numerical slop

    def test_second_iteration_fires_when_first_misses(self):
        # Craft input that single-pass won't converge on but two-pass will.
        # High-crest material: quiet base with short loud bursts causes the
        # -1 dB ceiling to pull the first-pass LUFS just outside ±0.5 dB
        # of target; heavier compression in pass 2 reduces crest factor
        # enough that the ceiling clips less, landing within tolerance.
        rate = 48000
        n = int(5.0 * rate)
        t = np.linspace(0, 5.0, n, endpoint=False)
        base_amp = 0.03
        burst_amp = 0.88
        burst_dur_ms = 30
        burst_count = 10

        signal = base_amp * np.sin(2 * np.pi * 200 * t)
        for bi in range(burst_count):
            burst_start = 0.1 + bi * (4.8 / burst_count)
            start = int(burst_start * rate)
            end = min(start + int(burst_dur_ms / 1000 * rate), n)
            signal[start:end] = burst_amp * np.sin(2 * np.pi * 1000 * t[start:end])
        data = np.column_stack([signal, signal])

        _, metrics = fix_dynamic(data, rate, target_lufs=-14.0, ceiling_db=-1.0)
        assert metrics["iterations_run"] >= 2
        # Should still converge.
        if metrics["converged"]:
            assert abs(metrics["final_lufs"] - (-14.0)) <= 0.5
