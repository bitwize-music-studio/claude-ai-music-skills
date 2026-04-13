#!/usr/bin/env python3
"""Unit tests for tools/mastering/mono_fold.py — mono fold-down QC analysis."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.mono_fold import (
    DEFAULT_THRESHOLDS,
    fold_to_mono,
    mono_fold_metrics,
)


def _stereo_sine(freq=1000.0, duration=3.0, rate=44100, amplitude=0.3,
                 right_scale=1.0, right_phase=0.0):
    """Generate a stereo sine with configurable right-channel scale/phase."""
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    left = amplitude * np.sin(2 * np.pi * freq * t)
    right = right_scale * amplitude * np.sin(2 * np.pi * freq * t + right_phase)
    return np.column_stack([left, right]).astype(np.float64), rate


class TestFoldToMono:
    def test_returns_1d_array_same_length(self):
        data, _ = _stereo_sine()
        mono = fold_to_mono(data)
        assert mono.ndim == 1
        assert len(mono) == len(data)

    def test_mean_downmix_convention(self):
        """Codebase uses np.mean(data, axis=1) for stereo→mono."""
        data = np.array([[1.0, 3.0], [2.0, 4.0]])
        mono = fold_to_mono(data)
        np.testing.assert_allclose(mono, [2.0, 3.0])

    def test_mono_input_passthrough(self):
        """1-D input should be returned unchanged."""
        data = np.array([0.1, 0.2, 0.3])
        mono = fold_to_mono(data)
        np.testing.assert_allclose(mono, data)


class TestMonoFoldMetrics:
    def test_in_phase_correlated_signal_passes(self):
        """Identical L/R channels fold perfectly — PASS."""
        data, rate = _stereo_sine(right_scale=1.0)
        metrics = mono_fold_metrics(data, rate)
        assert metrics["verdict"] == "PASS"
        assert metrics["band_drop_fail"] is False

    def test_inverted_channels_hard_fail_with_band_info(self):
        """L = -R cancels completely in mono — FAIL with offending band reported."""
        data, rate = _stereo_sine(right_scale=-1.0)
        metrics = mono_fold_metrics(data, rate)
        assert metrics["verdict"] == "FAIL"
        assert metrics["band_drop_fail"] is True
        # The signal is at 1000 Hz, which lives in the "mid" band (500-2000)
        assert metrics["worst_band"]["name"] == "mid"
        # Drop should exceed the 6 dB threshold
        assert metrics["worst_band"]["delta_db"] < -6.0

    def test_returned_mono_audio_is_sample_ready(self):
        """Metrics should return the mono audio data for writing as a .mono.wav sample."""
        data, rate = _stereo_sine()
        metrics = mono_fold_metrics(data, rate)
        mono_audio = metrics["mono_audio"]
        assert mono_audio.ndim == 1
        assert len(mono_audio) == len(data)

    def test_per_band_deltas_cover_all_bands(self):
        """Result should include delta_db for every band in DEFAULT_THRESHOLDS."""
        data, rate = _stereo_sine()
        metrics = mono_fold_metrics(data, rate)
        band_deltas = metrics["band_deltas"]
        for band in ("sub_bass", "bass", "low_mid", "mid", "high_mid", "high", "air"):
            assert band in band_deltas
            entry = band_deltas[band]
            assert "delta_db" in entry
            assert "hz_low" in entry
            assert "hz_high" in entry

    def test_lufs_delta_reported(self):
        """LUFS stereo/mono/delta should be present in the result."""
        data, rate = _stereo_sine()
        metrics = mono_fold_metrics(data, rate)
        assert "lufs" in metrics
        assert "stereo" in metrics["lufs"]
        assert "mono" in metrics["lufs"]
        assert "delta_db" in metrics["lufs"]

    def test_vocal_rms_delta_reported(self):
        """Vocal band (1-4 kHz) RMS delta should be present."""
        data, rate = _stereo_sine()
        metrics = mono_fold_metrics(data, rate)
        assert "vocal_rms" in metrics
        assert "delta_db" in metrics["vocal_rms"]

    def test_stereo_correlation_reported(self):
        """Stereo correlation coefficient should be present."""
        data, rate = _stereo_sine()
        metrics = mono_fold_metrics(data, rate)
        assert "stereo_correlation" in metrics
        corr = metrics["stereo_correlation"]
        # In-phase identical channels should correlate near 1.0
        assert corr > 0.9

    def test_inverted_channels_correlation_near_minus_one(self):
        data, rate = _stereo_sine(right_scale=-1.0)
        metrics = mono_fold_metrics(data, rate)
        assert metrics["stereo_correlation"] < -0.9

    def test_custom_thresholds_respected(self):
        """Thresholds gate the verdict — extreme ones suppress the fail."""
        data_inv, rate_inv = _stereo_sine(right_scale=-1.0)
        # 100 dB threshold is wider than the noise-floor cancellation bound,
        # so even a phase-inverted signal won't trip band_drop_fail.
        loose = dict(DEFAULT_THRESHOLDS)
        loose["band_drop_fail_db"] = 100.0
        loose_metrics = mono_fold_metrics(data_inv, rate_inv, thresholds=loose)
        assert loose_metrics["band_drop_fail"] is False

        # Default threshold (6 dB) catches the same cancellation as FAIL.
        default_metrics = mono_fold_metrics(data_inv, rate_inv)
        assert default_metrics["band_drop_fail"] is True

    def test_wide_stereo_low_correlation_warns(self):
        """Uncorrelated L/R (random noise) should WARN on correlation."""
        rate = 44100
        rng = np.random.default_rng(42)
        left = 0.3 * rng.standard_normal(rate * 3)
        right = 0.3 * rng.standard_normal(rate * 3)
        data = np.column_stack([left, right])
        metrics = mono_fold_metrics(data, rate)
        # Uncorrelated noise ≈ 0 correlation — below 0.3 threshold
        assert metrics["stereo_correlation"] < 0.3
        assert metrics["verdict"] in ("WARN", "FAIL")

    def test_verdict_is_worst_status(self):
        """If any sub-check is FAIL, overall verdict is FAIL."""
        data, rate = _stereo_sine(right_scale=-1.0)
        metrics = mono_fold_metrics(data, rate)
        assert metrics["verdict"] == "FAIL"

    def test_silent_signal_degrades_gracefully(self):
        """Silent stereo should not crash and should not claim a band-drop fail."""
        rate = 44100
        data = np.zeros((rate * 2, 2), dtype=np.float64)
        metrics = mono_fold_metrics(data, rate)
        # No signal = no drop to measure
        assert metrics["band_drop_fail"] is False
