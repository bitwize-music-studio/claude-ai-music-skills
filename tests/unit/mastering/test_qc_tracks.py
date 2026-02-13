#!/usr/bin/env python3
"""
Unit tests for qc_tracks.py

Tests all 7 QC checks against synthetic audio signals that are
specifically crafted to trigger pass, warn, and fail conditions.

Usage:
    python -m pytest tests/unit/mastering/test_qc_tracks.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.qc_tracks import (
    ALL_CHECKS,
    _check_clipping,
    _check_clicks,
    _check_format,
    _check_mono_compat,
    _check_phase,
    _check_silence,
    _check_spectral,
    qc_track,
)


# ─── Helpers ──────────────────────────────────────────────────────────


def _generate_sine(freq=440.0, duration=3.0, rate=44100, amplitude=0.5, stereo=True):
    """Generate a sine wave test signal."""
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    mono = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float64)
    if stereo:
        return np.column_stack([mono, mono]), rate
    return mono, rate


def _write_wav(path, data, rate, subtype="PCM_16"):
    sf.write(str(path), data, rate, subtype=subtype)


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def normal_wav(tmp_path):
    """Multi-band stereo signal designed to pass all QC checks.

    Mixes tones across all spectral bands so the spectral check sees
    balanced energy, while keeping amplitude moderate to avoid clipping.
    """
    rate = 44100
    duration = 3.0
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    # Mix tones across key bands: sub-bass, bass, mid, high-mid, high
    mono = (
        0.20 * np.sin(2 * np.pi * 40 * t)     # sub-bass
        + 0.20 * np.sin(2 * np.pi * 150 * t)   # bass
        + 0.20 * np.sin(2 * np.pi * 1000 * t)  # mid
        + 0.10 * np.sin(2 * np.pi * 4000 * t)  # high-mid (lower amp to avoid tinniness)
        + 0.08 * np.sin(2 * np.pi * 9000 * t)  # high
    ).astype(np.float64)
    data = np.column_stack([mono, mono])
    path = tmp_path / "normal.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def mono_wav(tmp_path):
    """A mono sine wave."""
    data, rate = _generate_sine(freq=440, amplitude=0.5, stereo=False)
    path = tmp_path / "mono.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def silent_wav(tmp_path):
    """Completely silent stereo file."""
    rate = 44100
    data = np.zeros((rate * 3, 2), dtype=np.float64)
    path = tmp_path / "silent.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def clipping_wav(tmp_path):
    """Signal with multiple clipping regions (amplitude at 0.999+)."""
    rate = 44100
    t = np.linspace(0, 3.0, rate * 3, endpoint=False)
    mono = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
    # Insert 5 clipping regions of 10 consecutive samples each
    for i in range(5):
        start = 5000 + i * 10000
        mono[start:start + 10] = 0.999
    data = np.column_stack([mono, mono])
    path = tmp_path / "clipping.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def out_of_phase_wav(tmp_path):
    """Stereo signal where R channel is inverted L — out of phase."""
    rate = 44100
    t = np.linspace(0, 3.0, rate * 3, endpoint=False)
    left = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
    right = -left  # Perfect phase inversion
    data = np.column_stack([left, right])
    path = tmp_path / "out_of_phase.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def leading_silence_wav(tmp_path):
    """Signal with 1 second of leading silence."""
    rate = 44100
    silence = np.zeros((rate, 2), dtype=np.float64)
    t = np.linspace(0, 2.0, rate * 2, endpoint=False)
    signal = 0.5 * np.sin(2 * np.pi * 440 * t)
    audio = np.column_stack([signal, signal])
    data = np.vstack([silence, audio])
    path = tmp_path / "leading_silence.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def internal_gap_wav(tmp_path):
    """Signal with a 1-second silent gap in the middle."""
    rate = 44100
    t1 = np.linspace(0, 1.0, rate, endpoint=False)
    sig1 = 0.5 * np.sin(2 * np.pi * 440 * t1)
    gap = np.zeros(rate, dtype=np.float64)
    t2 = np.linspace(0, 1.0, rate, endpoint=False)
    sig2 = 0.5 * np.sin(2 * np.pi * 440 * t2)
    mono = np.concatenate([sig1, gap, sig2])
    data = np.column_stack([mono, mono])
    path = tmp_path / "internal_gap.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def clicks_wav(tmp_path):
    """Signal with sharp transient spikes (clicks)."""
    rate = 44100
    duration = 3.0
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    mono = (0.05 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
    # Insert 5 strong clicks: single-sample spikes at 10x the local RMS
    for i in range(5):
        idx = 10000 + i * 20000
        mono[idx] = 0.95
    data = np.column_stack([mono, mono])
    path = tmp_path / "clicks.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def tinny_wav(tmp_path):
    """Signal with extreme high-mid energy and very little mid energy."""
    rate = 44100
    duration = 3.0
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    low = 0.05 * np.sin(2 * np.pi * 200 * t)
    high_mid = 0.9 * np.sin(2 * np.pi * 4000 * t)
    mono = (low + high_mid).astype(np.float64)
    data = np.column_stack([mono, mono])
    path = tmp_path / "tinny.wav"
    _write_wav(path, data, rate)
    return str(path)


# ─── Tests: Individual Check Functions ────────────────────────────────


class TestCheckFormat:
    """Tests for the format validation check."""

    def test_standard_stereo_wav_passes(self, normal_wav):
        info = sf.info(normal_wav)
        result = _check_format(info)
        assert result["status"] == "PASS"

    def test_mono_file_warns(self, mono_wav):
        info = sf.info(mono_wav)
        result = _check_format(info)
        assert result["status"] == "WARN"
        assert "Mono" in result["detail"]


class TestCheckMonoCompat:
    """Tests for the mono compatibility check."""

    def test_correlated_stereo_passes(self):
        """Identical L/R channels should have near-zero loss."""
        data, rate = _generate_sine(stereo=True)
        result = _check_mono_compat(data)
        assert result["status"] == "PASS"

    def test_inverted_channels_fail(self):
        """L and -L channels cancel completely in mono."""
        rate = 44100
        t = np.linspace(0, 1.0, rate, endpoint=False)
        left = 0.5 * np.sin(2 * np.pi * 440 * t)
        right = -left
        data = np.column_stack([left, right])
        result = _check_mono_compat(data)
        assert result["status"] == "FAIL"


class TestCheckPhase:
    """Tests for the phase correlation check."""

    def test_identical_channels_pass(self):
        """Identical channels should have correlation ~1.0."""
        data, rate = _generate_sine(stereo=True)
        result = _check_phase(data, rate)
        assert result["status"] == "PASS"
        assert float(result["value"]) > 0.9

    def test_inverted_channels_fail(self, out_of_phase_wav):
        """Inverted R channel should produce negative correlation."""
        data, rate = sf.read(out_of_phase_wav)
        result = _check_phase(data, rate)
        assert result["status"] == "FAIL"
        assert float(result["value"]) < 0

    def test_uncorrelated_channels_warn(self):
        """Random L and R should produce weak correlation."""
        rate = 44100
        rng = np.random.default_rng(42)
        left = 0.3 * rng.standard_normal(rate * 3)
        right = 0.3 * rng.standard_normal(rate * 3)
        data = np.column_stack([left, right])
        result = _check_phase(data, rate)
        # Random noise typically gives correlation near 0
        assert result["status"] in ("WARN", "FAIL")


class TestCheckClipping:
    """Tests for the clipping detection check."""

    def test_clean_signal_passes(self):
        """Normal amplitude signal should not trigger clipping."""
        data, _ = _generate_sine(amplitude=0.5)
        result = _check_clipping(data)
        assert result["status"] == "PASS"
        assert "0 regions" in result["value"]

    def test_clipped_signal_fails(self, clipping_wav):
        """Signal with multiple clipping regions should fail."""
        data, _ = sf.read(clipping_wav)
        result = _check_clipping(data)
        assert result["status"] in ("WARN", "FAIL")
        # We inserted 5 clipping regions
        assert "0 regions" not in result["value"]


class TestCheckClicks:
    """Tests for the click/pop detection check."""

    def test_clean_signal_passes(self):
        """Smooth sine wave should have no clicks."""
        data, rate = _generate_sine(amplitude=0.5)
        result = _check_clicks(data, rate)
        assert result["status"] == "PASS"
        assert "0 found" in result["value"]

    def test_signal_with_clicks_detected(self, clicks_wav):
        """Sharp transient spikes should be detected as clicks."""
        data, rate = sf.read(clicks_wav)
        result = _check_clicks(data, rate)
        assert result["status"] in ("WARN", "FAIL")
        assert "0 found" not in result["value"]


class TestCheckSilence:
    """Tests for the silence detection check."""

    def test_normal_signal_passes(self):
        """Signal with minimal leading/trailing silence should pass."""
        data, rate = _generate_sine(amplitude=0.5)
        result = _check_silence(data, rate)
        assert result["status"] == "PASS"

    def test_leading_silence_detected(self, leading_silence_wav):
        """1 second of leading silence should be flagged."""
        data, rate = sf.read(leading_silence_wav)
        result = _check_silence(data, rate)
        assert result["status"] == "FAIL"
        assert "Leading silence" in result["detail"]

    def test_internal_gap_detected(self, internal_gap_wav):
        """1-second gap in the middle should be flagged."""
        data, rate = sf.read(internal_gap_wav)
        result = _check_silence(data, rate)
        assert result["status"] == "FAIL"
        assert "internal gap" in result["detail"]


class TestCheckSpectral:
    """Tests for the spectral balance check."""

    def test_multiband_signal_passes(self):
        """Signal with energy across all bands should pass spectral check."""
        rate = 44100
        t = np.linspace(0, 3.0, rate * 3, endpoint=False)
        mono = (
            0.20 * np.sin(2 * np.pi * 40 * t)
            + 0.20 * np.sin(2 * np.pi * 150 * t)
            + 0.20 * np.sin(2 * np.pi * 1000 * t)
            + 0.10 * np.sin(2 * np.pi * 4000 * t)
            + 0.08 * np.sin(2 * np.pi * 9000 * t)
        )
        data = np.column_stack([mono, mono])
        result = _check_spectral(data, rate)
        assert result["status"] == "PASS"

    def test_tinny_signal_detected(self, tinny_wav):
        """Signal with extreme high-mid should trigger tinniness warning."""
        data, rate = sf.read(tinny_wav)
        result = _check_spectral(data, rate)
        assert result["status"] in ("WARN", "FAIL")
        assert "tinniness" in result["detail"].lower() or "High-mid" in result["detail"]


# ─── Tests: Full qc_track Integration ────────────────────────────────


class TestQcTrackIntegration:
    """Integration tests for the full qc_track() function."""

    def test_returns_expected_keys(self, normal_wav):
        result = qc_track(normal_wav)
        assert "filename" in result
        assert "checks" in result
        assert "verdict" in result

    def test_filename_is_basename(self, normal_wav):
        result = qc_track(normal_wav)
        assert result["filename"] == "normal.wav"

    def test_all_checks_run_by_default(self, normal_wav):
        result = qc_track(normal_wav)
        for check in ALL_CHECKS:
            assert check in result["checks"], f"Check '{check}' missing from results"

    def test_clean_signal_passes_all(self, normal_wav):
        """A clean stereo sine wave should pass all QC checks."""
        result = qc_track(normal_wav)
        assert result["verdict"] == "PASS"
        for check_name, check_result in result["checks"].items():
            assert check_result["status"] in ("PASS",), (
                f"Check '{check_name}' was {check_result['status']}: {check_result['detail']}"
            )

    def test_out_of_phase_fails(self, out_of_phase_wav):
        """Out-of-phase signal should get FAIL verdict."""
        result = qc_track(out_of_phase_wav)
        assert result["verdict"] == "FAIL"
        assert result["checks"]["phase"]["status"] == "FAIL"
        assert result["checks"]["mono"]["status"] == "FAIL"

    def test_leading_silence_fails(self, leading_silence_wav):
        """Leading silence should cause FAIL verdict."""
        result = qc_track(leading_silence_wav)
        assert result["checks"]["silence"]["status"] == "FAIL"
        assert result["verdict"] == "FAIL"

    def test_verdict_is_worst_status(self, normal_wav):
        """Verdict should reflect the worst individual check status."""
        result = qc_track(normal_wav)
        statuses = [r["status"] for r in result["checks"].values()]
        if "FAIL" in statuses:
            assert result["verdict"] == "FAIL"
        elif "WARN" in statuses:
            assert result["verdict"] == "WARN"
        else:
            assert result["verdict"] == "PASS"

    def test_selective_checks(self, normal_wav):
        """Only requested checks should run."""
        result = qc_track(normal_wav, checks=["format", "phase"])
        assert "format" in result["checks"]
        assert "phase" in result["checks"]
        assert "clipping" not in result["checks"]
        assert "spectral" not in result["checks"]

    def test_mono_file_handled(self, mono_wav):
        """Mono input should not crash any check."""
        result = qc_track(mono_wav)
        assert "verdict" in result
        # Mono files should pass phase/mono checks (or warn for format)
        assert result["verdict"] in ("PASS", "WARN")

    def test_nonexistent_file_raises(self, tmp_path):
        """Missing file should raise an exception."""
        with pytest.raises(Exception):
            qc_track(str(tmp_path / "nonexistent.wav"))

    def test_each_check_has_required_fields(self, normal_wav):
        """Every check result should have status, value, and detail."""
        result = qc_track(normal_wav)
        for check_name, check_result in result["checks"].items():
            assert "status" in check_result, f"'{check_name}' missing 'status'"
            assert "value" in check_result, f"'{check_name}' missing 'value'"
            assert "detail" in check_result, f"'{check_name}' missing 'detail'"
            assert check_result["status"] in ("PASS", "WARN", "FAIL"), (
                f"'{check_name}' has invalid status: {check_result['status']}"
            )
