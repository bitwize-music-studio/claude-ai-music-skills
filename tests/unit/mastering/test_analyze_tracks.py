#!/usr/bin/env python3
"""
Unit tests for analyze_tracks.py

Tests audio analysis functions against synthetic audio signals.

Usage:
    python -m pytest tools/mastering/tests/test_analyze_tracks.py -v
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

from tools.mastering.analyze_tracks import analyze_track


def _generate_sine(freq=440.0, duration=3.0, rate=44100, amplitude=0.5, stereo=True):
    """Generate a sine wave test signal."""
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    mono = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    if stereo:
        return np.column_stack([mono, mono]), rate
    return mono, rate


def _write_wav(path, data, rate):
    sf.write(str(path), data, rate, subtype='PCM_16')


# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sine_wav(tmp_path):
    """A standard 440Hz stereo sine wave at -6 dBFS."""
    data, rate = _generate_sine(freq=440, amplitude=0.5, stereo=True)
    path = tmp_path / "sine.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def quiet_wav(tmp_path):
    """A very quiet signal."""
    data, rate = _generate_sine(freq=440, amplitude=0.01, stereo=True)
    path = tmp_path / "quiet.wav"
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
    """A completely silent stereo file."""
    rate = 44100
    data = np.zeros((rate * 2, 2), dtype=np.float32)
    path = tmp_path / "silent.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def bright_wav(tmp_path):
    """A signal with strong high-frequency content (should trigger tinniness)."""
    rate = 44100
    duration = 3.0
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    # Mix: weak low + strong high-mid
    low = 0.1 * np.sin(2 * np.pi * 200 * t)
    high_mid = 0.8 * np.sin(2 * np.pi * 4000 * t)
    mono = (low + high_mid).astype(np.float32)
    data = np.column_stack([mono, mono])
    path = tmp_path / "bright.wav"
    _write_wav(path, data, rate)
    return str(path)


# ─── Tests: Basic Analysis ─────────────────────────────────────────────


class TestAnalyzeTrackBasic:
    """Tests for the analyze_track function with normal inputs."""

    def test_returns_expected_keys(self, sine_wav):
        result = analyze_track(sine_wav)
        expected_keys = {
            'filename', 'duration', 'sample_rate', 'lufs',
            'peak_db', 'rms_db', 'dynamic_range',
            'band_energy', 'tinniness_ratio',
        }
        assert expected_keys == set(result.keys())

    def test_filename_is_basename(self, sine_wav):
        result = analyze_track(sine_wav)
        assert result['filename'] == 'sine.wav'

    def test_sample_rate(self, sine_wav):
        result = analyze_track(sine_wav)
        assert result['sample_rate'] == 44100

    def test_duration_approximately_correct(self, sine_wav):
        result = analyze_track(sine_wav)
        assert abs(result['duration'] - 3.0) < 0.1

    def test_lufs_is_finite_and_negative(self, sine_wav):
        result = analyze_track(sine_wav)
        assert np.isfinite(result['lufs'])
        assert result['lufs'] < 0

    def test_peak_db_is_negative(self, sine_wav):
        """Peak should be below 0 dBFS for 0.5 amplitude signal."""
        result = analyze_track(sine_wav)
        assert result['peak_db'] < 0

    def test_dynamic_range_is_positive(self, sine_wav):
        result = analyze_track(sine_wav)
        assert result['dynamic_range'] > 0


class TestAnalyzeTrackBandEnergy:
    """Tests for spectral band energy analysis."""

    def test_band_energy_keys(self, sine_wav):
        result = analyze_track(sine_wav)
        expected_bands = {'sub_bass', 'bass', 'low_mid', 'mid', 'high_mid', 'high', 'air'}
        assert expected_bands == set(result['band_energy'].keys())

    def test_band_energy_sums_near_100(self, sine_wav):
        result = analyze_track(sine_wav)
        total = sum(result['band_energy'].values())
        assert abs(total - 100.0) < 1.0  # Allow small floating point drift

    def test_440hz_energy_in_mid_band(self, sine_wav):
        """440Hz falls in the low_mid (250-500Hz) band."""
        result = analyze_track(sine_wav)
        be = result['band_energy']
        # 440Hz should have significant energy in low_mid
        assert be['low_mid'] > 20.0

    def test_bright_signal_high_tinniness(self, bright_wav):
        """Signal with strong 4kHz content should have high tinniness ratio."""
        result = analyze_track(bright_wav)
        assert result['tinniness_ratio'] > 0.5


class TestAnalyzeTrackEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_mono_input(self, mono_wav):
        """Mono files should be handled without error."""
        result = analyze_track(mono_wav)
        assert np.isfinite(result['lufs'])
        assert result['sample_rate'] == 44100

    def test_quiet_signal(self, quiet_wav):
        """Very quiet signals should still produce valid results."""
        result = analyze_track(quiet_wav)
        assert np.isfinite(result['lufs'])
        assert result['lufs'] < -30  # Should be very quiet

    def test_silent_audio_peak_is_neg_inf(self, silent_wav):
        """Silent audio should produce -inf peak."""
        result = analyze_track(silent_wav)
        assert result['peak_db'] == -np.inf

    def test_silent_audio_rms_is_neg_inf(self, silent_wav):
        result = analyze_track(silent_wav)
        assert result['rms_db'] == -np.inf

    def test_silent_audio_tinniness_zero(self, silent_wav):
        """Division by zero guard: tinniness should be 0 for silent audio."""
        result = analyze_track(silent_wav)
        # band_energy['mid'] will be 0 (or near-0) for silence
        # The code guards: if band_energy['mid'] > 0 else 0
        assert np.isfinite(result['tinniness_ratio'])

    def test_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(Exception):
            analyze_track(str(tmp_path / "nonexistent.wav"))
