"""Unit tests for apply_tilt_eq (#290 step 6 tilt-EQ coherence correction)."""
from __future__ import annotations

import numpy as np

from tools.mastering.master_tracks import apply_tilt_eq


def _band_rms(data: np.ndarray, rate: int, low_hz: float, high_hz: float) -> float:
    """Return RMS in a frequency band via FFT magnitude integration."""
    mono = data.mean(axis=1) if data.ndim == 2 else data
    spec = np.fft.rfft(mono)
    freqs = np.fft.rfftfreq(len(mono), d=1.0 / rate)
    mask = (freqs >= low_hz) & (freqs < high_hz)
    band = spec[mask]
    if band.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.abs(band) ** 2)))


def _make_pink_noise(rate: int = 44100, duration: float = 1.0) -> np.ndarray:
    rng = np.random.default_rng(42)
    n = int(rate * duration)
    white = rng.standard_normal(n).astype(np.float32) * 0.2
    stereo = np.column_stack([white, white])
    return stereo


def test_zero_tilt_is_passthrough() -> None:
    """tilt_db == 0 returns the input unchanged (short-circuit path)."""
    rate = 44100
    data = _make_pink_noise(rate)
    out = apply_tilt_eq(data, rate, tilt_db=0.0)
    assert out is data  # identity: short-circuit returns same object


def test_near_zero_tilt_short_circuits() -> None:
    """|tilt_db| < 0.01 short-circuits without filtering."""
    rate = 44100
    data = _make_pink_noise(rate)
    out = apply_tilt_eq(data, rate, tilt_db=0.005)
    assert out is data


def test_positive_tilt_boosts_highs_cuts_lows() -> None:
    """Positive tilt_db raises high-band energy and lowers low-band energy."""
    rate = 44100
    data = _make_pink_noise(rate)
    orig_low = _band_rms(data, rate, 20, 200)
    orig_high = _band_rms(data, rate, 4000, 16000)

    out = apply_tilt_eq(data, rate, tilt_db=0.5, pivot_hz=650.0)
    new_low = _band_rms(out, rate, 20, 200)
    new_high = _band_rms(out, rate, 4000, 16000)

    assert new_low < orig_low, "positive tilt should cut low band"
    assert new_high > orig_high, "positive tilt should boost high band"


def test_negative_tilt_inverse() -> None:
    """Negative tilt_db raises low-band energy and lowers high-band energy."""
    rate = 44100
    data = _make_pink_noise(rate)
    orig_low = _band_rms(data, rate, 20, 200)
    orig_high = _band_rms(data, rate, 4000, 16000)

    out = apply_tilt_eq(data, rate, tilt_db=-0.5, pivot_hz=650.0)
    new_low = _band_rms(out, rate, 20, 200)
    new_high = _band_rms(out, rate, 4000, 16000)

    assert new_low > orig_low, "negative tilt should boost low band"
    assert new_high < orig_high, "negative tilt should cut high band"


def test_tilt_preserves_shape() -> None:
    """Output has same shape and dtype-class as input for both mono and stereo."""
    rate = 44100
    stereo = _make_pink_noise(rate)
    mono = stereo.mean(axis=1)

    out_stereo = apply_tilt_eq(stereo, rate, tilt_db=0.3)
    out_mono = apply_tilt_eq(mono, rate, tilt_db=0.3)

    assert out_stereo.shape == stereo.shape
    assert out_mono.shape == mono.shape
