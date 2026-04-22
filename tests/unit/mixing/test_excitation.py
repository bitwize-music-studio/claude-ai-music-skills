"""Unit tests for the harmonic excitation DSP primitive."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.signal import welch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mixing.excitation import apply_harmonic_excitation


def _pink_stereo(seconds: float = 2.0, rate: int = 48000,
                 rms_db: float = -18.0) -> np.ndarray:
    rng = np.random.default_rng(42)
    n = int(seconds * rate)
    white = rng.standard_normal((n, 2)).astype(np.float64)
    pink = np.zeros_like(white)
    alpha = 0.98
    for i in range(1, n):
        pink[i] = alpha * pink[i - 1] + (1 - alpha) * white[i]
    pink /= np.max(np.abs(pink)) + 1e-9
    target_lin = 10 ** (rms_db / 20)
    current_rms = np.sqrt(np.mean(pink ** 2))
    return pink * (target_lin / current_rms)


def _dark_stereo(seconds: float = 2.0, rate: int = 48000,
                 rms_db: float = -20.0) -> np.ndarray:
    """Low-passed noise — minimal high-frequency content. Excitation
    should measurably add high-mid energy here."""
    from scipy.signal import butter, sosfilt
    rng = np.random.default_rng(7)
    n = int(seconds * rate)
    white = rng.standard_normal((n, 2)).astype(np.float64)
    sos = butter(4, 800.0, btype="low", fs=rate, output="sos")
    dark = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
    dark /= np.max(np.abs(dark)) + 1e-9
    target_lin = 10 ** (rms_db / 20)
    current_rms = np.sqrt(np.mean(dark ** 2))
    return dark * (target_lin / current_rms)


def _high_mid_energy_pct(data: np.ndarray, rate: int,
                         band: tuple[float, float] = (2000.0, 6000.0)) -> float:
    """Return % of total PSD energy that falls in the given band."""
    mono = np.mean(data, axis=1) if data.ndim > 1 else data
    freqs, psd = welch(mono, rate, nperseg=8192)
    total = float(np.sum(psd))
    if total == 0.0:
        return 0.0
    band_mask = (freqs >= band[0]) & (freqs < band[1])
    return float(np.sum(psd[band_mask]) / total * 100.0)


class TestHarmonicExcitation:
    def test_zero_amount_is_noop(self):
        data = _pink_stereo()
        out = apply_harmonic_excitation(data, 48000, amount_db=0.0)
        # Byte-identical no-op for default / off case.
        assert np.array_equal(out, data)

    def test_negative_amount_is_noop(self):
        data = _pink_stereo()
        out = apply_harmonic_excitation(data, 48000, amount_db=-3.0)
        assert np.array_equal(out, data)

    def test_excitation_adds_high_mid_energy_on_dark_material(self):
        data = _dark_stereo()
        rate = 48000
        pre = _high_mid_energy_pct(data, rate)
        out = apply_harmonic_excitation(data, rate, amount_db=3.0)
        post = _high_mid_energy_pct(out, rate)
        # Excitation should measurably raise high-mid energy on dark input.
        assert post > pre + 0.5, (
            f"Excitation did not raise high_mid energy: "
            f"pre={pre:.2f}%, post={post:.2f}%"
        )

    def test_low_frequencies_unchanged(self):
        """Content below the excitation band should be untouched."""
        data = _pink_stereo()
        rate = 48000
        out = apply_harmonic_excitation(data, rate, amount_db=4.0)
        # Low-band (20-500 Hz) should be near-identical.
        freqs, psd_in = welch(np.mean(data, axis=1), rate, nperseg=8192)
        _, psd_out = welch(np.mean(out, axis=1), rate, nperseg=8192)
        low_mask = (freqs >= 20) & (freqs < 500)
        if np.sum(psd_in[low_mask]) > 0:
            ratio = np.sum(psd_out[low_mask]) / np.sum(psd_in[low_mask])
            assert 0.95 <= ratio <= 1.05, (
                f"Low-frequency energy ratio {ratio:.3f} should be ~1.0"
            )

    def test_shape_preserved(self):
        data = _pink_stereo()
        out = apply_harmonic_excitation(data, 48000, amount_db=3.0)
        assert out.shape == data.shape
        assert out.dtype == data.dtype

    def test_monotonic_in_amount(self):
        """Higher amount_db → more high-mid energy added."""
        data = _dark_stereo()
        rate = 48000
        pre = _high_mid_energy_pct(data, rate)
        post_small = _high_mid_energy_pct(
            apply_harmonic_excitation(data, rate, amount_db=1.0), rate,
        )
        post_large = _high_mid_energy_pct(
            apply_harmonic_excitation(data, rate, amount_db=6.0), rate,
        )
        assert post_small > pre
        assert post_large > post_small

    def test_no_nans_or_infs(self):
        data = _pink_stereo()
        out = apply_harmonic_excitation(data, 48000, amount_db=4.0)
        assert np.all(np.isfinite(out))

    def test_peak_bounded(self):
        """Excitation shouldn't cause wild peak growth. Sub-2x peak
        increase at 4 dB amount is a reasonable bound."""
        data = _pink_stereo()
        pre_peak = np.max(np.abs(data))
        out = apply_harmonic_excitation(data, 48000, amount_db=4.0)
        post_peak = np.max(np.abs(out))
        assert post_peak < pre_peak * 2.0, (
            f"Peak grew from {pre_peak:.3f} to {post_peak:.3f} — "
            "excitation should not double peaks at 4 dB amount"
        )
