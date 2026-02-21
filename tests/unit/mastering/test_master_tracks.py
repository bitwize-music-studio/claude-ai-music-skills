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
    _load_yaml_file,
    apply_eq,
    apply_fade_out,
    apply_high_shelf,
    limit_peaks,
    load_genre_presets,
    master_track,
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


# ─── Tests: apply_fade_out ─────────────────────────────────────────────


class TestApplyFadeOut:
    """Tests for the fade-out envelope function."""

    def test_fade_out_reduces_end_amplitude(self):
        """Last samples should be near zero after fade."""
        data, rate = _generate_sine(freq=440, duration=3.0, amplitude=0.5)
        result = apply_fade_out(data, rate, duration=2.0)
        # Last few samples should be nearly silent
        end_rms = np.sqrt(np.mean(result[-100:] ** 2))
        assert end_rms < 0.01

    def test_fade_out_preserves_beginning(self):
        """Samples before fade region should be unchanged."""
        data, rate = _generate_sine(freq=440, duration=3.0, amplitude=0.5)
        result = apply_fade_out(data, rate, duration=1.0)
        # First 2 seconds (before fade region) should be identical
        pre_fade_samples = int(2.0 * rate)
        assert np.array_equal(result[:pre_fade_samples], data[:pre_fade_samples])

    def test_fade_out_none_is_passthrough(self):
        """fade_out=None via master_track should not modify audio."""
        data, rate = _generate_sine(freq=440, duration=3.0, amplitude=0.5)
        # apply_fade_out with duration <= 0 should passthrough
        result = apply_fade_out(data, rate, duration=0.0)
        assert np.array_equal(result, data)

    def test_fade_out_longer_than_audio(self):
        """Fade longer than audio should gracefully fade the entire track."""
        data, rate = _generate_sine(freq=440, duration=1.0, amplitude=0.5)
        result = apply_fade_out(data, rate, duration=5.0)
        # Should not crash; last samples should be near zero
        end_rms = np.sqrt(np.mean(result[-100:] ** 2))
        assert end_rms < 0.01
        # Shape should be preserved
        assert result.shape == data.shape

    def test_fade_out_exponential_curve(self):
        """Middle of fade region should be below 0.5 (not linear)."""
        rate = 44100
        duration = 2.0
        # Create constant signal for easy envelope checking
        data = np.ones((int(rate * duration), 2)) * 0.5
        result = apply_fade_out(data, rate, duration=2.0, curve='exponential')
        # Midpoint of fade (t=0.5): gain = (1 - 0.5)^3 = 0.125
        mid_idx = len(data) // 2
        # At midpoint, amplitude should be well below 0.5 * 0.5 = 0.25 (linear midpoint)
        assert result[mid_idx, 0] < 0.25

    def test_fade_out_mono(self):
        """Fade-out should work on mono (1D) arrays."""
        data, rate = _generate_sine(freq=440, duration=2.0, amplitude=0.5, stereo=False)
        result = apply_fade_out(data, rate, duration=1.0)
        assert result.shape == data.shape
        end_rms = np.sqrt(np.mean(result[-100:] ** 2))
        assert end_rms < 0.01


# ─── Tests: Genre Presets ──────────────────────────────────────────────


class TestGenrePresets:
    """Tests for genre preset configuration."""

    def test_all_presets_are_3_tuples(self):
        for genre, preset in GENRE_PRESETS.items():
            assert len(preset) == 3, f"Genre '{genre}' preset should be a 3-tuple"

    def test_all_presets_have_negative_lufs(self):
        for genre, (lufs, _, _) in GENRE_PRESETS.items():
            assert lufs < 0, f"Genre '{genre}' LUFS should be negative"

    def test_all_presets_have_nonpositive_eq(self):
        """EQ values should be cuts (negative) or zero."""
        for genre, (_, highmid, highs) in GENRE_PRESETS.items():
            assert highmid <= 0, f"Genre '{genre}' high-mid should be <= 0"
            assert highs <= 0, f"Genre '{genre}' highs should be <= 0"

    def test_common_genres_exist(self):
        for genre in ['pop', 'rock', 'hip-hop', 'electronic', 'jazz', 'classical', 'folk', 'country', 'metal']:
            assert genre in GENRE_PRESETS, f"Expected genre '{genre}' in presets"

    def test_preset_with_mastering(self, noise_wav, output_path):
        """Apply a genre preset through the full mastering chain."""
        lufs, highmid, highs = GENRE_PRESETS['rock']
        eq = []
        if highmid != 0:
            eq.append((3500, highmid, 1.5))
        if highs != 0:
            eq.append((8000, highs, 0.7))
        result = master_track(noise_wav, output_path, target_lufs=lufs, eq_settings=eq)
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

    def test_loaded_presets_match_yaml(self):
        """GENRE_PRESETS dict should match what's in the YAML file."""
        data = _load_yaml_file(_BUILTIN_PRESETS_FILE)
        for genre, settings in data['genres'].items():
            assert genre in GENRE_PRESETS, f"Genre '{genre}' in YAML but not in GENRE_PRESETS"
            expected = (
                float(settings['target_lufs']),
                float(settings['cut_highmid']),
                float(settings['cut_highs']),
            )
            assert GENRE_PRESETS[genre] == expected, (
                f"Genre '{genre}': YAML={expected}, loaded={GENRE_PRESETS[genre]}"
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
        lufs, highmid, highs = presets['rock']
        assert highmid == -1.0  # Overridden
        assert lufs == -14.0    # Inherited from built-in
        assert highs == 0       # Inherited from built-in

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
        assert presets['dark-electronic'] == (-12.0, -3.0, -1.0)

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
        lufs, highmid, highs = presets['custom-genre']
        assert lufs == -12.0    # From overridden defaults
        assert highmid == -2.0  # From genre entry

    def test_no_override_dir_works(self, monkeypatch):
        """When no override directory exists, built-in presets load fine."""
        import tools.mastering.master_tracks as mt
        monkeypatch.setattr(mt, '_get_overrides_path', lambda: None)

        presets = load_genre_presets()
        assert 'rock' in presets
        assert 'pop' in presets
        assert len(presets) > 50
