#!/usr/bin/env python3
"""Unit tests for fix_dynamic() helper function."""

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.fix_dynamic_track import fix_dynamic


def _make_stereo_signal(duration=2.0, rate=44100, freq=440, amplitude=0.8):
    """Generate a stereo sine wave for testing."""
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    mono = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float64)
    return np.column_stack([mono, mono]), rate


def _make_dynamic_signal(rate=44100, duration=5.0):
    """Generate a signal with high dynamic range — loud sections over quiet base.

    This mimics the real-world problem: peak near 0 dBFS but LUFS far below
    target, so normal mastering hits the ceiling before reaching target loudness.
    """
    samples = int(rate * duration)
    t = np.linspace(0, duration, samples, endpoint=False)
    # Quiet base signal (most of the content)
    signal = 0.05 * np.sin(2 * np.pi * 440 * t)
    # Loud 100ms bursts every second — long enough for compressor to engage
    for burst_start in np.arange(0.1, duration, 1.0):
        start = int(burst_start * rate)
        end = min(start + int(0.1 * rate), samples)
        signal[start:end] = 0.9 * np.sin(2 * np.pi * 1000 * t[start:end])
    return np.column_stack([signal, signal]), rate


class TestFixDynamic:
    """Tests for the fix_dynamic() core function."""

    def test_reduces_dynamic_range(self):
        """fix_dynamic should bring a dynamic signal closer to target LUFS
        than simple peak-limited normalization would."""
        import pyloudnorm as pyln
        from tools.mastering.master_tracks import limit_peaks

        data, rate = _make_dynamic_signal()
        meter = pyln.Meter(rate)
        target = -14.0

        # Simple normalization + limiting (what master_track does)
        simple = data.copy()
        current_lufs = meter.integrated_loudness(simple)
        gain = 10 ** ((target - current_lufs) / 20)
        simple = simple * gain
        simple = limit_peaks(simple, ceiling_db=-1.0)
        simple_lufs = meter.integrated_loudness(simple)
        simple_err = abs(simple_lufs - target)

        # fix_dynamic (compression before normalization)
        processed, metrics = fix_dynamic(data.copy(), rate, target_lufs=target)
        proc_err = abs(metrics["final_lufs"] - target)

        assert proc_err <= simple_err, (
            f"fix_dynamic ({proc_err:.2f} dB error) should be at least as good as "
            f"simple normalization ({simple_err:.2f} dB error)"
        )

    def test_reaches_target_lufs(self):
        """Output LUFS should be within ±0.5 dB of target."""
        import pyloudnorm as pyln

        data, rate = _make_stereo_signal(duration=3.0, amplitude=0.3)
        target = -14.0

        processed, metrics = fix_dynamic(data.copy(), rate, target_lufs=target)

        meter = pyln.Meter(rate)
        actual_lufs = meter.integrated_loudness(processed)

        assert abs(actual_lufs - target) <= 0.5, (
            f"LUFS {actual_lufs:.1f} not within ±0.5 of target {target}"
        )
        assert abs(metrics["final_lufs"] - actual_lufs) < 0.1

    def test_respects_ceiling(self):
        """Peak should not exceed the specified ceiling."""
        data, rate = _make_stereo_signal(amplitude=0.9)
        ceiling = -1.0
        ceiling_linear = 10 ** (ceiling / 20)

        processed, metrics = fix_dynamic(data.copy(), rate, ceiling_db=ceiling)

        peak = np.max(np.abs(processed))
        assert peak <= ceiling_linear + 1e-6, (
            f"Peak {peak:.6f} exceeds ceiling {ceiling_linear:.6f}"
        )
        assert metrics["final_peak_db"] <= ceiling + 0.01

    def test_custom_eq(self):
        """Custom EQ settings should be applied instead of defaults."""
        data, rate = _make_stereo_signal(duration=3.0)

        # Default EQ: 3500 Hz cut
        processed_default, _ = fix_dynamic(data.copy(), rate)

        # Custom EQ: different frequency and gain
        custom_eq = [(1000, -4.0, 2.0)]
        processed_custom, _ = fix_dynamic(data.copy(), rate, eq_settings=custom_eq)

        # Results should differ since different EQ was applied
        assert not np.allclose(processed_default, processed_custom, atol=1e-4)

    def test_silent_audio(self):
        """Silent input should return gracefully without errors."""
        data = np.zeros((44100 * 2, 2))
        rate = 44100

        processed, metrics = fix_dynamic(data, rate)

        # Should not crash; metrics should reflect silence
        assert processed.shape == data.shape
        assert np.isfinite(metrics["final_peak_db"]) or metrics["final_peak_db"] == float("-inf")

    def test_returns_metrics(self):
        """Metrics dict should contain required keys."""
        data, rate = _make_stereo_signal(duration=3.0)
        _, metrics = fix_dynamic(data.copy(), rate)

        assert "original_lufs" in metrics
        assert "final_lufs" in metrics
        assert "final_peak_db" in metrics
        assert isinstance(metrics["original_lufs"], float)
        assert isinstance(metrics["final_lufs"], float)
        assert isinstance(metrics["final_peak_db"], float)

    def test_custom_target_lufs(self):
        """Should respect a non-default target LUFS value."""
        import pyloudnorm as pyln

        data, rate = _make_stereo_signal(duration=3.0, amplitude=0.3)
        target = -11.0

        processed, metrics = fix_dynamic(data.copy(), rate, target_lufs=target)

        meter = pyln.Meter(rate)
        actual_lufs = meter.integrated_loudness(processed)

        assert abs(actual_lufs - target) <= 0.5, (
            f"LUFS {actual_lufs:.1f} not within ±0.5 of target {target}"
        )
