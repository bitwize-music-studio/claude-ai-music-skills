#!/usr/bin/env python3
"""
Regression tests for issue #410.

gentle_compress / apply_transient_shaper computed time-constant coefficients
via ``np.exp(-1.0 / (rate * ms / 1000.0))``. When an attack/release time is
0 ms (reachable through user-override mix presets), the inner
``rate * ms / 1000.0`` collapses to 0.0 and the Python scalar division
``-1.0 / 0.0`` raises ZeroDivisionError, aborting the whole polish run.

These tests pin the fix: a 0 ms (or negative) attack/release time must be
clamped to a tiny positive floor so no exception is raised and output stays
finite, while a normal positive time still behaves as before.

Usage:
    python -m pytest tests/unit/mixing/test_mix_tracks_zerodiv_410.py -v
"""

import sys
from pathlib import Path

import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mixing.mix_tracks import (
    _MIN_TIME_CONSTANT_MS,
    apply_transient_shaper,
    gentle_compress,
)


def _signal(rate: int = 44100, seconds: float = 0.1) -> np.ndarray:
    """A stereo sine with a transient burst so both code paths do real work."""
    t = np.arange(int(rate * seconds)) / rate
    tone = 0.8 * np.sin(2 * np.pi * 440 * t)
    # Add a sharp transient so the transient shaper has something to detect.
    tone[len(tone) // 2] += 0.15
    return np.column_stack([tone, tone]).astype(np.float64)


class TestGentleCompressZeroTimes:
    def test_zero_attack_does_not_raise(self):
        data = _signal()
        result = gentle_compress(data, 44100, ratio=4.0, attack_ms=0)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_zero_release_does_not_raise(self):
        data = _signal()
        result = gentle_compress(data, 44100, ratio=4.0, release_ms=0)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_both_zero_does_not_raise(self):
        data = _signal()
        result = gentle_compress(data, 44100, ratio=4.0, attack_ms=0, release_ms=0)
        assert np.all(np.isfinite(result))

    def test_negative_time_clamps_to_floor(self):
        """A negative attack time must clamp to the floor, not become a
        coeff>1 runaway envelope. Output byte-identical to the floor-value
        run pins the clamp; on unfixed code the negative time diverged (it
        stayed finite on this short signal, so a bare finiteness check did
        not catch the regression)."""
        data = _signal()
        result = gentle_compress(data, 44100, ratio=4.0, attack_ms=-5.0)
        clamped = gentle_compress(data, 44100, ratio=4.0,
                                  attack_ms=_MIN_TIME_CONSTANT_MS)
        assert np.all(np.isfinite(result))
        assert np.array_equal(result, clamped)

    def test_normal_attack_still_compresses(self):
        """A normal positive attack must still reduce peaks above threshold."""
        data = _signal()
        result = gentle_compress(data, 44100, threshold_db=-12.0, ratio=4.0,
                                 attack_ms=10.0, release_ms=100.0)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))
        assert np.max(np.abs(result)) < np.max(np.abs(data))


class TestTransientShaperZeroTimes:
    def test_zero_fast_attack_does_not_raise(self):
        data = _signal()
        result = apply_transient_shaper(data, 44100, attack_gain=6.0,
                                        fast_attack_ms=0)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_zero_slow_attack_does_not_raise(self):
        data = _signal()
        result = apply_transient_shaper(data, 44100, attack_gain=6.0,
                                        slow_attack_ms=0)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_negative_fast_attack_clamps_to_floor(self):
        """A negative transient fast-attack time must clamp to the floor,
        producing output byte-identical to the floor-value run (see #410)."""
        data = _signal()
        result = apply_transient_shaper(data, 44100, sustain_gain=3.0,
                                        fast_attack_ms=-1.0)
        clamped = apply_transient_shaper(data, 44100, sustain_gain=3.0,
                                         fast_attack_ms=_MIN_TIME_CONSTANT_MS)
        assert np.all(np.isfinite(result))
        assert np.array_equal(result, clamped)

    def test_normal_attack_still_shapes(self):
        """A normal positive attack must still alter the signal."""
        data = _signal()
        result = apply_transient_shaper(data, 44100, attack_gain=6.0,
                                        fast_attack_ms=0.5, slow_attack_ms=20.0)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))
        assert not np.allclose(result, data)
