#!/usr/bin/env python3
"""
Unit tests for master_tracks.py

Tests mastering functions: EQ, limiting, loudness normalization, and edge cases.

Usage:
    python -m pytest tools/mastering/tests/test_master_tracks.py -v
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

from tools.mastering.master_tracks import (
    GENRE_PRESETS,
    _BUILTIN_PRESETS_FILE,
    _PRESET_DEFAULTS,
    _load_yaml_file,
    _process_one_track,
    apply_eq,
    apply_fade_out,
    apply_high_shelf,
    apply_tpdf_dither,
    limit_peaks,
    load_genre_presets,
    master_track,
    measure_true_peak,
    soft_clip,
)


def _generate_sine(freq=440.0, duration=3.0, rate=44100, amplitude=0.5, stereo=True):
    """Generate a sine wave test signal."""
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    mono = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float64)
    if stereo:
        return np.column_stack([mono, mono]), rate
    return mono, rate


def _generate_noise(duration=3.0, rate=44100, amplitude=0.3, stereo=True):
    """Generate white noise test signal."""
    rng = np.random.default_rng(42)
    samples = int(rate * duration)
    mono = (amplitude * rng.standard_normal(samples)).astype(np.float64)
    if stereo:
        return np.column_stack([mono, mono.copy()]), rate
    return mono, rate


def _write_wav(path, data, rate):
    sf.write(str(path), data, rate, subtype='PCM_16')


# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sine_wav(tmp_path):
    data, rate = _generate_sine(freq=440, amplitude=0.5, stereo=True)
    path = tmp_path / "sine.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def mono_wav(tmp_path):
    data, rate = _generate_sine(freq=440, amplitude=0.5, stereo=False)
    path = tmp_path / "mono.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def silent_wav(tmp_path):
    rate = 44100
    data = np.zeros((rate * 3, 2), dtype=np.float64)
    path = tmp_path / "silent.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def hot_wav(tmp_path):
    """A near-clipping signal (amplitude ~0.99)."""
    data, rate = _generate_sine(freq=440, amplitude=0.99, stereo=True)
    path = tmp_path / "hot.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def noise_wav(tmp_path):
    """White noise — broadband signal for EQ testing."""
    data, rate = _generate_noise(amplitude=0.3, stereo=True)
    path = tmp_path / "noise.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def output_path(tmp_path):
    return str(tmp_path / "output.wav")


# ─── Tests: apply_eq ───────────────────────────────────────────────────


class TestApplyEq:
    """Tests for the parametric EQ function."""

    def test_zero_gain_is_passthrough(self):
        """0 dB gain should not alter the signal."""
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=1000, gain_db=0.0)
        # With 0 dB gain, output should be nearly identical
        assert np.allclose(result, data, atol=1e-6)

    def test_negative_gain_reduces_energy(self):
        """Cutting at the signal frequency should reduce energy."""
        data, rate = _generate_sine(freq=1000, amplitude=0.5)
        result = apply_eq(data, rate, freq=1000, gain_db=-6.0, q=1.0)
        assert np.max(np.abs(result)) < np.max(np.abs(data))

    def test_positive_gain_increases_energy(self):
        """Boosting at the signal frequency should increase energy."""
        data, rate = _generate_sine(freq=1000, amplitude=0.3)
        result = apply_eq(data, rate, freq=1000, gain_db=6.0, q=1.0)
        assert np.max(np.abs(result)) > np.max(np.abs(data))

    def test_freq_above_nyquist_skips(self):
        """Frequency above Nyquist should return data unchanged."""
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=25000, gain_db=-6.0)
        assert np.array_equal(result, data)

    def test_freq_below_20hz_skips(self):
        """Frequency below 20Hz should return data unchanged."""
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=10, gain_db=-6.0)
        assert np.array_equal(result, data)

    def test_negative_q_skips(self):
        """Negative Q should return data unchanged."""
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=1000, gain_db=-6.0, q=-1.0)
        assert np.array_equal(result, data)

    def test_zero_q_skips(self):
        """Zero Q should return data unchanged."""
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=1000, gain_db=-6.0, q=0.0)
        assert np.array_equal(result, data)

    def test_mono_input(self):
        """EQ should work on mono (1D) arrays."""
        data, rate = _generate_sine(stereo=False)
        result = apply_eq(data, rate, freq=1000, gain_db=-3.0)
        assert result.shape == data.shape

    def test_stereo_preserves_shape(self):
        """EQ should preserve the (samples, channels) shape."""
        data, rate = _generate_sine(stereo=True)
        result = apply_eq(data, rate, freq=1000, gain_db=-3.0)
        assert result.shape == data.shape

    def test_output_is_finite(self):
        """EQ output should never contain NaN or inf."""
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=3500, gain_db=-6.0, q=1.5)
        assert np.all(np.isfinite(result))


class TestApplyHighShelf:
    """Tests for the high shelf EQ function."""

    def test_negative_gain_reduces_highs(self):
        """High shelf cut should reduce high-frequency energy."""
        data, rate = _generate_sine(freq=10000, amplitude=0.5)
        result = apply_high_shelf(data, rate, freq=8000, gain_db=-6.0)
        assert np.max(np.abs(result)) < np.max(np.abs(data))

    def test_freq_above_nyquist_skips(self):
        data, rate = _generate_sine()
        result = apply_high_shelf(data, rate, freq=25000, gain_db=-6.0)
        assert np.array_equal(result, data)

    def test_mono_input(self):
        data, rate = _generate_sine(freq=10000, stereo=False)
        result = apply_high_shelf(data, rate, freq=8000, gain_db=-3.0)
        assert result.shape == data.shape

    def test_output_is_finite(self):
        data, rate = _generate_sine()
        result = apply_high_shelf(data, rate, freq=8000, gain_db=-6.0)
        assert np.all(np.isfinite(result))


# ─── Tests: soft_clip and limit_peaks ──────────────────────────────────


class TestSoftClip:
    """Tests for the soft clipping limiter."""

    def test_below_threshold_is_passthrough(self):
        """Signal below threshold should pass through unchanged."""
        data = np.array([0.1, 0.5, -0.3, 0.0])
        result = soft_clip(data, threshold=0.95)
        assert np.array_equal(result, data)

    def test_above_threshold_is_reduced(self):
        """Signal above threshold should be attenuated."""
        data = np.array([1.5, -1.5])
        result = soft_clip(data, threshold=0.95)
        assert np.all(np.abs(result) < np.abs(data))

    def test_preserves_sign(self):
        """Soft clip should preserve signal polarity."""
        data = np.array([1.5, -1.5, 0.5, -0.5])
        result = soft_clip(data, threshold=0.9)
        assert np.all(np.sign(result) == np.sign(data))

    def test_output_is_finite(self):
        data = np.array([10.0, -10.0, 0.0, 1.0])
        result = soft_clip(data, threshold=0.95)
        assert np.all(np.isfinite(result))


class TestLimitPeaks:
    """Tests for the peak limiter."""

    def test_peaks_below_ceiling(self):
        """After limiting, peaks should not exceed the ceiling."""
        data = np.array([[1.5, -1.5], [0.5, 0.5]])
        result = limit_peaks(data, ceiling_db=-1.0)
        ceiling_linear = 10 ** (-1.0 / 20)
        assert np.max(np.abs(result)) <= ceiling_linear + 1e-6

    def test_quiet_signal_unchanged(self):
        """Signal well below ceiling should be essentially unchanged."""
        data = np.array([[0.01, -0.01], [0.02, 0.02]])
        result = limit_peaks(data, ceiling_db=-1.0)
        assert np.allclose(result, data, atol=1e-6)

    def test_zero_db_ceiling(self):
        """0 dBFS ceiling should limit peaks to 1.0."""
        data = np.array([[1.5, -1.5]])
        result = limit_peaks(data, ceiling_db=0.0)
        assert np.max(np.abs(result)) <= 1.0 + 1e-6

    def test_true_peak_detection(self):
        """Limiter should catch inter-sample peaks that exceed the ceiling."""
        # Two samples that create a large inter-sample peak when interpolated
        # e.g., [0.8, -0.8] has inter-sample peaks above 0.8 due to sinc overshoot
        rate = 44100
        t = np.linspace(0, 0.01, int(rate * 0.01), endpoint=False)
        # A high-frequency sine near Nyquist creates large inter-sample peaks
        data = 0.7 * np.sin(2 * np.pi * 20000 * t)
        data = np.column_stack([data, data])
        result = limit_peaks(data, ceiling_db=-1.0)
        ceiling_linear = 10 ** (-1.0 / 20)
        # True peak of result must be below ceiling
        from scipy.signal import resample_poly
        upsampled = resample_poly(result[:, 0], up=4, down=1)
        assert np.max(np.abs(upsampled)) <= ceiling_linear + 1e-3


# ─── Tests: measure_true_peak ─────────────────────────────────────────


class TestMeasureTruePeak:
    """Tests for ITU-R BS.1770-4 true peak measurement."""

    def test_sine_true_peak_exceeds_sample_peak(self):
        """A near-Nyquist sine should have true peak > sample peak."""
        rate = 44100
        t = np.linspace(0, 0.1, int(rate * 0.1), endpoint=False)
        data = 0.9 * np.sin(2 * np.pi * 20000 * t)
        sample_peak = np.max(np.abs(data))
        true_peak = measure_true_peak(data)
        assert true_peak >= sample_peak

    def test_low_freq_true_peak_close_to_sample_peak(self):
        """A low-frequency sine has negligible inter-sample overshoot."""
        rate = 44100
        t = np.linspace(0, 0.1, int(rate * 0.1), endpoint=False)
        data = 0.5 * np.sin(2 * np.pi * 100 * t)
        sample_peak = np.max(np.abs(data))
        true_peak = measure_true_peak(data)
        assert abs(true_peak - sample_peak) < 0.01

    def test_stereo_returns_worst_channel(self):
        """True peak of stereo should be the max across both channels."""
        rate = 44100
        t = np.linspace(0, 0.01, int(rate * 0.01), endpoint=False)
        left = 0.3 * np.sin(2 * np.pi * 440 * t)
        right = 0.9 * np.sin(2 * np.pi * 440 * t)
        data = np.column_stack([left, right])
        true_peak = measure_true_peak(data)
        assert true_peak >= 0.89  # Right channel dominates

    def test_empty_data(self):
        """Empty array should return 0."""
        assert measure_true_peak(np.array([])) == 0.0

    def test_silence(self):
        """Silent data should return 0."""
        data = np.zeros(1000)
        assert measure_true_peak(data) == 0.0


# ─── Tests: apply_tpdf_dither ─────────────────────────────────────────


class TestApplyTpdfDither:
    """Tests for TPDF dithering before quantization."""

    def test_dither_adds_noise(self):
        """Dithered signal should differ from original."""
        data = np.zeros((1000, 2))
        result = apply_tpdf_dither(data, target_bits=16, seed=42)
        assert not np.allclose(result, data)

    def test_dither_amplitude_within_bounds(self):
        """Dither noise should be within ±1 LSB of the target bit depth."""
        data = np.zeros(10000)
        result = apply_tpdf_dither(data, target_bits=16, seed=42)
        one_lsb = 1.0 / 32768
        # TPDF range is ±1 LSB; allow small statistical overshoot
        assert np.max(np.abs(result)) < 1.5 * one_lsb

    def test_dither_is_triangular_distribution(self):
        """Dither noise should approximate a triangular PDF."""
        data = np.zeros(100000)
        result = apply_tpdf_dither(data, target_bits=16, seed=42)
        # Triangular distribution: mean ≈ 0, lower kurtosis than uniform
        assert abs(np.mean(result)) < 1e-7
        # Standard deviation for TPDF = LSB / sqrt(6)
        one_lsb = 1.0 / 32768
        expected_std = one_lsb / np.sqrt(6)
        assert abs(np.std(result) - expected_std) < expected_std * 0.1

    def test_dither_seed_reproducibility(self):
        """Same seed should produce identical dither."""
        data = np.zeros(1000)
        r1 = apply_tpdf_dither(data, seed=123)
        r2 = apply_tpdf_dither(data, seed=123)
        assert np.array_equal(r1, r2)

    def test_dither_different_seeds_differ(self):
        """Different seeds should produce different dither."""
        data = np.zeros(1000)
        r1 = apply_tpdf_dither(data, seed=1)
        r2 = apply_tpdf_dither(data, seed=2)
        assert not np.array_equal(r1, r2)

    def test_dither_preserves_shape(self):
        """Output shape should match input."""
        for shape in [(1000,), (1000, 2)]:
            data = np.zeros(shape)
            result = apply_tpdf_dither(data, seed=42)
            assert result.shape == data.shape


# ─── Tests: master_track (integration) ────────────────────────────────


class TestMasterTrack:
    """Integration tests for the full mastering chain."""

    def test_basic_mastering(self, sine_wav, output_path):
        """Master a normal stereo file to -14 LUFS."""
        result = master_track(sine_wav, output_path, target_lufs=-14.0)
        assert 'original_lufs' in result
        assert 'final_lufs' in result
        assert 'gain_applied' in result
        assert 'final_peak' in result
        assert not result.get('skipped', False)
        assert Path(output_path).exists()

    def test_output_loudness_near_target(self, sine_wav, output_path):
        """Final LUFS should be close to target."""
        result = master_track(sine_wav, output_path, target_lufs=-14.0)
        # Allow 1.5 dB tolerance due to limiting
        assert abs(result['final_lufs'] - (-14.0)) < 1.5

    def test_output_peak_below_ceiling(self, sine_wav, output_path):
        """Final peak should not exceed the ceiling."""
        result = master_track(sine_wav, output_path, ceiling_db=-1.0)
        assert result['final_peak'] <= -0.9  # Small tolerance

    def test_mono_input_produces_mono_output(self, mono_wav, output_path):
        """Mono input should produce mono output."""
        result = master_track(mono_wav, output_path, target_lufs=-14.0)
        assert not result.get('skipped', False)
        data, _ = sf.read(output_path)
        assert len(data.shape) == 1  # Mono

    def test_stereo_input_produces_stereo_output(self, sine_wav, output_path):
        """Stereo input should produce stereo output."""
        master_track(sine_wav, output_path, target_lufs=-14.0)
        data, _ = sf.read(output_path)
        assert len(data.shape) == 2
        assert data.shape[1] == 2

    def test_silent_audio_is_skipped(self, silent_wav, output_path):
        """Silent audio should be skipped gracefully."""
        result = master_track(silent_wav, output_path, target_lufs=-14.0)
        assert result.get('skipped', False) is True
        assert result['original_lufs'] == float('-inf')

    def test_with_eq_settings(self, noise_wav, output_path):
        """Mastering with EQ settings should complete without error."""
        eq = [(3500, -2.0, 1.5)]
        result = master_track(noise_wav, output_path, target_lufs=-14.0, eq_settings=eq)
        assert not result.get('skipped', False)
        assert Path(output_path).exists()

    def test_with_multiple_eq_bands(self, noise_wav, output_path):
        """Multiple EQ bands should all be applied."""
        eq = [(3500, -2.0, 1.5), (8000, -1.5, 0.7)]
        result = master_track(noise_wav, output_path, target_lufs=-14.0, eq_settings=eq)
        assert not result.get('skipped', False)

    def test_hot_signal_is_limited(self, hot_wav, output_path):
        """Near-clipping input should be properly limited."""
        result = master_track(hot_wav, output_path, target_lufs=-14.0, ceiling_db=-1.0)
        assert result['final_peak'] <= -0.9

    def test_gain_applied_is_correct_sign(self, sine_wav, output_path):
        """If input is quieter than target, gain should be positive."""
        result = master_track(sine_wav, output_path, target_lufs=-14.0)
        if result['original_lufs'] < -14.0:
            assert result['gain_applied'] > 0
        elif result['original_lufs'] > -14.0:
            assert result['gain_applied'] < 0

    def test_output_file_is_valid_wav(self, sine_wav, output_path):
        """Output should be a readable WAV file."""
        master_track(sine_wav, output_path, target_lufs=-14.0)
        data, rate = sf.read(output_path)
        assert rate == 44100
        assert len(data) > 0
        assert np.all(np.isfinite(data))

    def test_mastering_with_preset_dict(self, noise_wav, output_path):
        """master_track should accept a preset dict for all parameters."""
        preset = {
            'target_lufs': -16.0,
            'cut_highmid': -2.0,
            'cut_highs': -1.0,
            'compress_ratio': 2.0,
            'compress_threshold': -15.0,
            'compress_attack': 20.0,
            'compress_release': 150.0,
            'eq_highmid_freq': 4000.0,
            'eq_highmid_q': 2.0,
            'eq_highs_freq': 9000.0,
            'eq_highs_q': 0.5,
            'dither_bits': 16,
        }
        result = master_track(noise_wav, output_path, preset=preset)
        assert not result.get('skipped', False)
        assert Path(output_path).exists()
        assert abs(result['final_lufs'] - (-16.0)) < 2.0

    def test_preset_dict_overrides_defaults(self, noise_wav, output_path):
        """Partial preset dict should merge with defaults."""
        preset = {'target_lufs': -18.0}
        result = master_track(noise_wav, output_path, preset=preset)
        assert not result.get('skipped', False)
        assert abs(result['final_lufs'] - (-18.0)) < 2.0


# ─── Tests: Genre Presets ──────────────────────────────────────────────


class TestGenrePresets:
    """Tests for genre preset configuration."""

    def test_all_presets_are_dicts(self):
        for genre, preset in GENRE_PRESETS.items():
            assert isinstance(preset, dict), f"Genre '{genre}' preset should be a dict"
            assert 'target_lufs' in preset, f"Genre '{genre}' missing target_lufs"
            assert 'cut_highmid' in preset, f"Genre '{genre}' missing cut_highmid"
            assert 'cut_highs' in preset, f"Genre '{genre}' missing cut_highs"
            assert 'compress_ratio' in preset, f"Genre '{genre}' missing compress_ratio"

    def test_all_presets_have_negative_lufs(self):
        for genre, preset in GENRE_PRESETS.items():
            assert preset['target_lufs'] < 0, f"Genre '{genre}' LUFS should be negative"

    def test_all_presets_have_nonpositive_eq(self):
        """EQ values should be cuts (negative) or zero."""
        for genre, preset in GENRE_PRESETS.items():
            assert preset['cut_highmid'] <= 0, f"Genre '{genre}' high-mid should be <= 0"
            assert preset['cut_highs'] <= 0, f"Genre '{genre}' highs should be <= 0"

    def test_common_genres_exist(self):
        for genre in ['pop', 'rock', 'hip-hop', 'electronic', 'jazz', 'classical', 'folk', 'country', 'metal']:
            assert genre in GENRE_PRESETS, f"Expected genre '{genre}' in presets"

    def test_preset_with_mastering(self, noise_wav, output_path):
        """Apply a genre preset through the full mastering chain."""
        preset = GENRE_PRESETS['rock']
        eq = []
        if preset['cut_highmid'] != 0:
            eq.append((preset['eq_highmid_freq'], preset['cut_highmid'], preset['eq_highmid_q']))
        if preset['cut_highs'] != 0:
            eq.append((preset['eq_highs_freq'], preset['cut_highs'], preset['eq_highs_q']))
        result = master_track(noise_wav, output_path, target_lufs=preset['target_lufs'], eq_settings=eq)
        assert not result.get('skipped', False)


# ─── Tests: Numerical Stability ───────────────────────────────────────


class TestNumericalStability:
    """Tests for numerical edge cases that could cause crashes or corruption."""

    def test_eq_extreme_gain(self):
        """Extreme EQ gain should not produce NaN/inf."""
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=1000, gain_db=-24.0, q=1.0)
        assert np.all(np.isfinite(result))

    def test_eq_extreme_boost(self):
        """Large boost should not produce NaN/inf."""
        data, rate = _generate_sine(amplitude=0.1)
        result = apply_eq(data, rate, freq=1000, gain_db=24.0, q=1.0)
        assert np.all(np.isfinite(result))

    def test_eq_very_narrow_q(self):
        """Very narrow Q should still produce finite output."""
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=1000, gain_db=-3.0, q=20.0)
        assert np.all(np.isfinite(result))

    def test_eq_very_wide_q(self):
        """Very wide Q should still produce finite output."""
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=1000, gain_db=-3.0, q=0.1)
        assert np.all(np.isfinite(result))

    def test_soft_clip_extreme_values(self):
        """Extreme input values should not produce NaN/inf."""
        data = np.array([100.0, -100.0, 0.0])
        result = soft_clip(data, threshold=0.95)
        assert np.all(np.isfinite(result))

    def test_limit_peaks_very_hot_signal(self):
        """Very loud signal should be limited without NaN/inf."""
        data = np.array([[50.0, -50.0], [30.0, -30.0]])
        result = limit_peaks(data, ceiling_db=-1.0)
        assert np.all(np.isfinite(result))
        ceiling_linear = 10 ** (-1.0 / 20)
        assert np.max(np.abs(result)) <= ceiling_linear + 1e-6

    def test_master_very_quiet_nonsilent(self, tmp_path):
        """Very quiet but non-silent audio should master without error."""
        data, rate = _generate_sine(amplitude=0.0001, duration=3.0)
        in_path = tmp_path / "vquiet.wav"
        out_path = tmp_path / "vquiet_out.wav"
        _write_wav(in_path, data, rate)
        result = master_track(str(in_path), str(out_path), target_lufs=-14.0)
        # Should either complete or skip, but not crash
        assert 'original_lufs' in result


# ─── Tests: YAML Preset Loading ───────────────────────────────────────


class TestYamlPresetLoading:
    """Tests for YAML-based genre preset loading and override merging."""

    def test_builtin_yaml_exists(self):
        """The built-in genre-presets.yaml should ship with the plugin."""
        assert _BUILTIN_PRESETS_FILE.exists(), f"Missing {_BUILTIN_PRESETS_FILE}"

    def test_builtin_yaml_is_valid(self):
        """Built-in YAML should parse without error."""
        data = _load_yaml_file(_BUILTIN_PRESETS_FILE)
        assert 'genres' in data
        assert 'defaults' in data
        assert len(data['genres']) > 50  # We have 60+ genres

    def test_builtin_yaml_has_required_fields(self):
        """Each genre entry should have target_lufs, cut_highmid, cut_highs."""
        data = _load_yaml_file(_BUILTIN_PRESETS_FILE)
        for genre, settings in data['genres'].items():
            assert 'target_lufs' in settings, f"Genre '{genre}' missing target_lufs"
            assert 'cut_highmid' in settings, f"Genre '{genre}' missing cut_highmid"
            assert 'cut_highs' in settings, f"Genre '{genre}' missing cut_highs"

    def test_builtin_yaml_has_all_default_keys(self):
        """Built-in YAML defaults should include all preset keys."""
        data = _load_yaml_file(_BUILTIN_PRESETS_FILE)
        defaults = data['defaults']
        expected_keys = [
            'target_lufs', 'cut_highmid', 'cut_highs', 'compress_ratio',
            'compress_threshold', 'compress_attack', 'compress_release',
            'eq_highmid_freq', 'eq_highmid_q', 'eq_highs_freq', 'eq_highs_q',
            'dither_bits',
        ]
        for key in expected_keys:
            assert key in defaults, f"Default key '{key}' missing from genre-presets.yaml"

    def test_loaded_presets_match_yaml(self):
        """GENRE_PRESETS dict should match what's in the YAML file."""
        data = _load_yaml_file(_BUILTIN_PRESETS_FILE)
        for genre, settings in data['genres'].items():
            assert genre in GENRE_PRESETS, f"Genre '{genre}' in YAML but not in GENRE_PRESETS"
            preset = GENRE_PRESETS[genre]
            assert preset['target_lufs'] == float(settings['target_lufs']), (
                f"Genre '{genre}' target_lufs mismatch"
            )
            assert preset['cut_highmid'] == float(settings['cut_highmid']), (
                f"Genre '{genre}' cut_highmid mismatch"
            )
            assert preset['cut_highs'] == float(settings['cut_highs']), (
                f"Genre '{genre}' cut_highs mismatch"
            )

    def test_load_yaml_file_missing(self, tmp_path):
        """Loading a nonexistent YAML file should return empty dict."""
        result = _load_yaml_file(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_load_yaml_file_invalid(self, tmp_path):
        """Loading an invalid YAML file should return empty dict."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text(": : : not valid yaml [[[")
        result = _load_yaml_file(bad_file)
        assert result == {}

    def test_load_yaml_file_empty(self, tmp_path):
        """Loading an empty YAML file should return empty dict."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        result = _load_yaml_file(empty_file)
        assert result == {}

    def test_override_merges_genre(self, tmp_path, monkeypatch):
        """User override should merge on top of built-in for a specific genre."""
        # Create a minimal override file
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        override_file = override_dir / "mastering-presets.yaml"
        override_file.write_text(
            "genres:\n"
            "  rock:\n"
            "    cut_highmid: -1.0\n"  # Override rock's -2.5 to -1.0
        )

        # Patch _get_overrides_path to return our test dir
        import tools.mastering.master_tracks as mt
        monkeypatch.setattr(mt, '_get_overrides_path', lambda: override_dir)

        presets = load_genre_presets()
        # Rock should have overridden cut_highmid but keep other fields
        preset = presets['rock']
        assert preset['cut_highmid'] == -1.0  # Overridden
        assert preset['target_lufs'] == -14.0  # Inherited from built-in
        assert preset['cut_highs'] == 0        # Inherited from built-in
        assert preset['compress_ratio'] == 1.5  # Default

    def test_override_adds_new_genre(self, tmp_path, monkeypatch):
        """User override can add entirely new genres."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        override_file = override_dir / "mastering-presets.yaml"
        override_file.write_text(
            "genres:\n"
            "  dark-electronic:\n"
            "    target_lufs: -12.0\n"
            "    cut_highmid: -3.0\n"
            "    cut_highs: -1.0\n"
        )

        import tools.mastering.master_tracks as mt
        monkeypatch.setattr(mt, '_get_overrides_path', lambda: override_dir)

        presets = load_genre_presets()
        assert 'dark-electronic' in presets
        preset = presets['dark-electronic']
        assert preset['target_lufs'] == -12.0
        assert preset['cut_highmid'] == -3.0
        assert preset['cut_highs'] == -1.0
        assert preset['compress_ratio'] == 1.5

    def test_override_defaults(self, tmp_path, monkeypatch):
        """User can override default settings."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        override_file = override_dir / "mastering-presets.yaml"
        override_file.write_text(
            "defaults:\n"
            "  target_lufs: -12.0\n"
            "genres:\n"
            "  custom-genre:\n"
            "    cut_highmid: -2.0\n"  # No target_lufs, should use overridden default
        )

        import tools.mastering.master_tracks as mt
        monkeypatch.setattr(mt, '_get_overrides_path', lambda: override_dir)

        presets = load_genre_presets()
        preset = presets['custom-genre']
        assert preset['target_lufs'] == -12.0    # From overridden defaults
        assert preset['cut_highmid'] == -2.0     # From genre entry
        assert preset['compress_ratio'] == 1.5   # Default

    def test_no_override_dir_works(self, monkeypatch):
        """When no override directory exists, built-in presets load fine."""
        import tools.mastering.master_tracks as mt
        monkeypatch.setattr(mt, '_get_overrides_path', lambda: None)

        presets = load_genre_presets()
        assert 'rock' in presets
        assert 'pop' in presets
        assert len(presets) > 50


# ─── Tests: Fade Out ─────────────────────────────────────────────────


class TestApplyFadeOut:
    """Tests for apply_fade_out function."""

    def test_zero_duration_passthrough(self):
        data, rate = _generate_sine(duration=1.0)
        result = apply_fade_out(data, rate, duration=0)
        assert np.array_equal(result, data)

    def test_negative_duration_passthrough(self):
        data, rate = _generate_sine(duration=1.0)
        result = apply_fade_out(data, rate, duration=-1.0)
        assert np.array_equal(result, data)

    def test_end_is_silent(self):
        data, rate = _generate_sine(duration=3.0, amplitude=0.5)
        result = apply_fade_out(data, rate, duration=2.0)
        # Last sample should be near zero
        assert np.max(np.abs(result[-1])) < 0.01

    def test_beginning_unchanged(self):
        data, rate = _generate_sine(duration=3.0, amplitude=0.5)
        result = apply_fade_out(data, rate, duration=1.0)
        # First half should be unchanged
        midpoint = data.shape[0] // 2
        assert np.array_equal(result[:midpoint], data[:midpoint])

    def test_fade_longer_than_audio(self):
        data, rate = _generate_sine(duration=1.0, amplitude=0.5)
        result = apply_fade_out(data, rate, duration=5.0)
        # Should not crash, end should be silent
        assert np.max(np.abs(result[-1])) < 0.01

    def test_mono_input(self):
        data, rate = _generate_sine(duration=2.0, stereo=False)
        result = apply_fade_out(data, rate, duration=1.0)
        assert len(result.shape) == 1
        assert np.max(np.abs(result[-1])) < 0.01

    def test_linear_curve(self):
        data, rate = _generate_sine(duration=2.0)
        result = apply_fade_out(data, rate, duration=1.0, curve='linear')
        assert np.max(np.abs(result[-1])) < 0.01

    def test_does_not_mutate_input(self):
        data, rate = _generate_sine(duration=2.0)
        original = data.copy()
        apply_fade_out(data, rate, duration=1.0)
        assert np.array_equal(data, original)


# ─── Tests: Process One Track ─────────────────────────────────────────


class TestProcessOneTrack:
    """Tests for _process_one_track helper."""

    def test_dry_run_returns_estimate(self, sine_wav, output_path):
        name, result = _process_one_track(
            Path(sine_wav), Path(output_path),
            target_lufs=-14.0, eq_settings=None,
            ceiling_db=-1.0, dry_run=True,
        )
        assert result is not None
        assert result['final_lufs'] == -14.0
        assert not Path(output_path).exists()

    def test_real_run_creates_output(self, sine_wav, output_path):
        name, result = _process_one_track(
            Path(sine_wav), Path(output_path),
            target_lufs=-14.0, eq_settings=None,
            ceiling_db=-1.0, dry_run=False,
        )
        assert result is not None
        assert Path(output_path).exists()

    def test_silent_returns_none(self, silent_wav, output_path):
        name, result = _process_one_track(
            Path(silent_wav), Path(output_path),
            target_lufs=-14.0, eq_settings=None,
            ceiling_db=-1.0, dry_run=False,
        )
        assert result is None

    def test_dry_run_silent_returns_none(self, silent_wav, output_path):
        name, result = _process_one_track(
            Path(silent_wav), Path(output_path),
            target_lufs=-14.0, eq_settings=None,
            ceiling_db=-1.0, dry_run=True,
        )
        assert result is None

    def test_preset_dict_passthrough(self, sine_wav, output_path):
        """_process_one_track should accept and pass through a preset dict."""
        preset = {'target_lufs': -16.0, 'compress_ratio': 1.0}
        name, result = _process_one_track(
            Path(sine_wav), Path(output_path),
            preset=preset, ceiling_db=-1.0, dry_run=False,
        )
        assert result is not None
        assert Path(output_path).exists()


# ─── Tests: Preset Resolution ───────────────────────────────────────────


class TestPresetResolution:
    """Tests for preset dict construction from genre presets and CLI overrides."""

    def test_genre_preset_is_complete_dict(self):
        """Each genre preset should have all keys from _PRESET_DEFAULTS."""
        for genre, preset in GENRE_PRESETS.items():
            for key in _PRESET_DEFAULTS:
                assert key in preset, f"Genre '{genre}' missing key '{key}'"

    def test_genre_preset_values_are_floats(self):
        """All preset values should be floats."""
        for genre, preset in GENRE_PRESETS.items():
            for key, value in preset.items():
                assert isinstance(value, float), (
                    f"Genre '{genre}' key '{key}' is {type(value).__name__}, expected float"
                )

    def test_default_preset_matches_hardcoded_defaults(self):
        """_PRESET_DEFAULTS should match the previously hardcoded values."""
        assert _PRESET_DEFAULTS['compress_threshold'] == -18.0
        assert _PRESET_DEFAULTS['compress_attack'] == 30.0
        assert _PRESET_DEFAULTS['compress_release'] == 200.0
        assert _PRESET_DEFAULTS['eq_highmid_freq'] == 3500.0
        assert _PRESET_DEFAULTS['eq_highmid_q'] == 1.5
        assert _PRESET_DEFAULTS['eq_highs_freq'] == 8000.0
        assert _PRESET_DEFAULTS['eq_highs_q'] == 0.7
        assert _PRESET_DEFAULTS['dither_bits'] == 16
