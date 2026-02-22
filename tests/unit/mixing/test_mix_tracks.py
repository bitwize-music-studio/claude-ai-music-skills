#!/usr/bin/env python3
"""
Unit tests for mix_tracks.py

Tests per-stem processing functions, full pipeline, and preset loading.

Usage:
    python -m pytest tests/unit/mixing/test_mix_tracks.py -v
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

from tools.mixing.mix_tracks import (
    MIX_PRESETS,
    _BUILTIN_PRESETS_FILE,
    _load_yaml_file,
    _deep_merge,
    apply_eq,
    apply_high_shelf,
    apply_highpass,
    apply_lowpass,
    apply_saturation,
    apply_stereo_width,
    gentle_compress,
    remove_clicks,
    reduce_noise,
    enhance_stereo,
    remix_stems,
    process_vocals,
    process_backing_vocals,
    process_drums,
    process_bass,
    process_guitar,
    process_keyboard,
    process_strings,
    process_brass,
    process_woodwinds,
    process_percussion,
    process_synth,
    process_other,
    mix_track_stems,
    mix_track_full,
    load_mix_presets,
    discover_stems,
    _get_stem_settings,
    _get_full_mix_settings,
    _get_bus_settings,
)


# ─── Test Helpers ─────────────────────────────────────────────────────


def _generate_sine(freq=440.0, duration=1.0, rate=44100, amplitude=0.5, stereo=True):
    """Generate a sine wave test signal."""
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    mono = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float64)
    if stereo:
        return np.column_stack([mono, mono]), rate
    return mono, rate


def _generate_noise(duration=1.0, rate=44100, amplitude=0.3, stereo=True):
    """Generate white noise test signal."""
    rng = np.random.default_rng(42)
    samples = int(rate * duration)
    mono = (amplitude * rng.standard_normal(samples)).astype(np.float64)
    if stereo:
        return np.column_stack([mono, mono.copy()]), rate
    return mono, rate


def _generate_click(duration=1.0, rate=44100, click_pos=0.5, amplitude=0.5):
    """Generate a signal with an artificial click/pop."""
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    data = (amplitude * 0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
    # Insert a sharp click
    click_idx = int(click_pos * rate)
    if click_idx < len(data):
        data[click_idx] = amplitude * 0.99
        if click_idx + 1 < len(data):
            data[click_idx + 1] = -amplitude * 0.99
    return np.column_stack([data, data]), rate


def _write_wav(path, data, rate):
    sf.write(str(path), data, rate, subtype='PCM_16')


# ─── Fixtures ─────────────────────────────────────────────────────────


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
def noise_wav(tmp_path):
    data, rate = _generate_noise(amplitude=0.3, stereo=True)
    path = tmp_path / "noise.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def click_wav(tmp_path):
    data, rate = _generate_click()
    path = tmp_path / "click.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def silent_wav(tmp_path):
    rate = 44100
    data = np.zeros((rate, 2), dtype=np.float64)
    path = tmp_path / "silent.wav"
    _write_wav(path, data, rate)
    return str(path)


@pytest.fixture
def stem_dir(tmp_path):
    """Create a directory with stem WAV files."""
    stems = tmp_path / "stems" / "01-test-track"
    stems.mkdir(parents=True)

    rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)

    # Vocals: mid-frequency sine
    vocals = 0.4 * np.sin(2 * np.pi * 800 * t)
    _write_wav(stems / "vocals.wav", np.column_stack([vocals, vocals]), rate)

    # Drums: noise bursts
    rng = np.random.default_rng(42)
    drums = 0.5 * rng.standard_normal(len(t))
    _write_wav(stems / "drums.wav", np.column_stack([drums, drums]), rate)

    # Bass: low sine
    bass = 0.5 * np.sin(2 * np.pi * 80 * t)
    _write_wav(stems / "bass.wav", np.column_stack([bass, bass]), rate)

    # Other: mid-high sine
    other = 0.3 * np.sin(2 * np.pi * 2000 * t)
    _write_wav(stems / "other.wav", np.column_stack([other, other]), rate)

    return stems


@pytest.fixture
def stem_dir_6(tmp_path):
    """Create a directory with 6 Suno-named stem WAV files."""
    stems = tmp_path / "stems" / "01-test-track-6"
    stems.mkdir(parents=True)

    rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)

    # Lead Vocals: mid-frequency sine
    lead = 0.4 * np.sin(2 * np.pi * 800 * t)
    _write_wav(stems / "0 Lead Vocals.wav", np.column_stack([lead, lead]), rate)

    # Backing Vocals: slightly different frequency
    backing = 0.3 * np.sin(2 * np.pi * 900 * t)
    _write_wav(stems / "1 Backing Vocals.wav", np.column_stack([backing, backing]), rate)

    # Drums: noise bursts
    rng = np.random.default_rng(42)
    drums = 0.5 * rng.standard_normal(len(t))
    _write_wav(stems / "2 Drums.wav", np.column_stack([drums, drums]), rate)

    # Bass: low sine
    bass = 0.5 * np.sin(2 * np.pi * 80 * t)
    _write_wav(stems / "3 Bass.wav", np.column_stack([bass, bass]), rate)

    # Synth: mid-high sine
    synth = 0.3 * np.sin(2 * np.pi * 2000 * t)
    _write_wav(stems / "4 Synth.wav", np.column_stack([synth, synth]), rate)

    # Other: different frequency
    other = 0.25 * np.sin(2 * np.pi * 3000 * t)
    _write_wav(stems / "5 Other.wav", np.column_stack([other, other]), rate)

    return stems


@pytest.fixture
def stem_dir_12(tmp_path):
    """Create a directory with 12 Suno-named stem WAV files."""
    stems = tmp_path / "stems" / "01-test-track-12"
    stems.mkdir(parents=True)

    rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)

    files = [
        ("0 Lead Vocals.wav",    0.4, 800),
        ("1 Backing Vocals.wav", 0.3, 900),
        ("2 Drums.wav",          0.5, None),   # noise
        ("3 Bass.wav",           0.5, 80),
        ("4 Guitar.wav",         0.35, 1200),
        ("5 Keyboard.wav",       0.3, 1500),
        ("6 Strings.wav",        0.25, 600),
        ("7 Brass.wav",          0.3, 1000),
        ("8 Woodwinds.wav",      0.25, 2200),
        ("9 Percussion.wav",     0.35, None),  # noise
        ("10 Synth.wav",         0.3, 2000),
        ("11 FX.wav",            0.2, 3000),
    ]

    rng = np.random.default_rng(42)
    for name, amp, freq in files:
        if freq is None:
            # noise-based stem (drums, percussion)
            data = amp * rng.standard_normal(len(t))
        else:
            data = amp * np.sin(2 * np.pi * freq * t)
        _write_wav(stems / name, np.column_stack([data, data]), rate)

    return stems


@pytest.fixture
def output_path(tmp_path):
    return str(tmp_path / "output.wav")


# ─── Tests: apply_highpass ────────────────────────────────────────────


class TestApplyHighpass:
    """Tests for the Butterworth highpass filter."""

    def test_removes_low_frequencies(self):
        """Highpass should reduce low-frequency energy."""
        data, rate = _generate_sine(freq=20, amplitude=0.5)
        result = apply_highpass(data, rate, cutoff=100)
        assert np.max(np.abs(result)) < np.max(np.abs(data))

    def test_passes_high_frequencies(self):
        """Highpass should pass frequencies above cutoff."""
        data, rate = _generate_sine(freq=1000, amplitude=0.5)
        result = apply_highpass(data, rate, cutoff=30)
        # High-freq signal should be mostly unchanged
        # Allow some attenuation from filter rolloff
        assert np.max(np.abs(result)) > 0.3

    def test_zero_cutoff_is_passthrough(self):
        """Cutoff of 0 should return unchanged data."""
        data, rate = _generate_sine()
        result = apply_highpass(data, rate, cutoff=0)
        assert np.array_equal(result, data)

    def test_cutoff_above_nyquist_is_passthrough(self):
        """Cutoff above Nyquist should return unchanged data."""
        data, rate = _generate_sine()
        result = apply_highpass(data, rate, cutoff=rate)
        assert np.array_equal(result, data)

    def test_mono_input(self):
        """Should work with mono (1D) arrays."""
        data, rate = _generate_sine(stereo=False)
        result = apply_highpass(data, rate, cutoff=100)
        assert result.shape == data.shape

    def test_output_is_finite(self):
        data, rate = _generate_sine()
        result = apply_highpass(data, rate, cutoff=30)
        assert np.all(np.isfinite(result))


# ─── Tests: apply_eq ─────────────────────────────────────────────────


class TestApplyEq:
    """Tests for the parametric EQ function."""

    def test_zero_gain_is_passthrough(self):
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=1000, gain_db=0.0)
        assert np.array_equal(result, data)

    def test_negative_gain_reduces_energy(self):
        data, rate = _generate_sine(freq=1000, amplitude=0.5)
        result = apply_eq(data, rate, freq=1000, gain_db=-6.0, q=1.0)
        assert np.max(np.abs(result)) < np.max(np.abs(data))

    def test_positive_gain_increases_energy(self):
        data, rate = _generate_sine(freq=1000, amplitude=0.3)
        result = apply_eq(data, rate, freq=1000, gain_db=6.0, q=1.0)
        assert np.max(np.abs(result)) > np.max(np.abs(data))

    def test_freq_out_of_range_skips(self):
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=25000, gain_db=-6.0)
        assert np.array_equal(result, data)

    def test_negative_q_skips(self):
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=1000, gain_db=-6.0, q=-1.0)
        assert np.array_equal(result, data)

    def test_mono_input(self):
        data, rate = _generate_sine(stereo=False)
        result = apply_eq(data, rate, freq=1000, gain_db=-3.0)
        assert result.shape == data.shape

    def test_output_is_finite(self):
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=3000, gain_db=6.0, q=1.5)
        assert np.all(np.isfinite(result))


# ─── Tests: apply_high_shelf ─────────────────────────────────────────


class TestApplyHighShelf:
    """Tests for the high shelf EQ function."""

    def test_negative_gain_reduces_highs(self):
        data, rate = _generate_sine(freq=10000, amplitude=0.5)
        result = apply_high_shelf(data, rate, freq=8000, gain_db=-6.0)
        assert np.max(np.abs(result)) < np.max(np.abs(data))

    def test_zero_gain_is_passthrough(self):
        data, rate = _generate_sine()
        result = apply_high_shelf(data, rate, freq=8000, gain_db=0.0)
        assert np.array_equal(result, data)

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


# ─── Tests: gentle_compress ──────────────────────────────────────────


class TestGentleCompress:
    """Tests for the envelope-following compressor."""

    def test_reduces_peaks_above_threshold(self):
        """Compression should reduce peaks above threshold."""
        data, rate = _generate_sine(freq=440, amplitude=0.8)
        result = gentle_compress(data, rate, threshold_db=-6.0, ratio=4.0)
        assert np.max(np.abs(result)) < np.max(np.abs(data))

    def test_unity_ratio_is_passthrough(self):
        """Ratio of 1:1 should not compress."""
        data, rate = _generate_sine()
        result = gentle_compress(data, rate, threshold_db=-6.0, ratio=1.0)
        assert np.array_equal(result, data)

    def test_below_ratio_is_passthrough(self):
        """Ratio below 1:1 should return unchanged data."""
        data, rate = _generate_sine()
        result = gentle_compress(data, rate, threshold_db=-6.0, ratio=0.5)
        assert np.array_equal(result, data)

    def test_mono_input(self):
        data, rate = _generate_sine(stereo=False, amplitude=0.8)
        result = gentle_compress(data, rate, threshold_db=-6.0, ratio=2.0)
        assert result.shape == data.shape

    def test_output_is_finite(self):
        data, rate = _generate_sine(amplitude=0.9)
        result = gentle_compress(data, rate, threshold_db=-10.0, ratio=4.0)
        assert np.all(np.isfinite(result))

    def test_preserves_sign(self):
        """Compression should not invert signal polarity."""
        data, rate = _generate_sine(amplitude=0.8)
        result = gentle_compress(data, rate, threshold_db=-6.0, ratio=3.0)
        # Check that signs are preserved where non-zero
        nonzero = np.abs(data) > 0.01
        assert np.all(np.sign(result[nonzero]) == np.sign(data[nonzero]))


# ─── Tests: remove_clicks ────────────────────────────────────────────


class TestRemoveClicks:
    """Tests for click/pop detection and removal."""

    def test_removes_artificial_click(self):
        """Should detect and reduce artificial clicks."""
        data, rate = _generate_click(amplitude=0.5)
        result = remove_clicks(data, rate, threshold=4.0)
        # The click sample should be reduced
        click_idx = int(0.5 * rate)
        assert np.abs(result[click_idx, 0]) < np.abs(data[click_idx, 0])

    def test_clean_signal_unchanged(self):
        """Clean signal without clicks should be mostly unchanged."""
        data, rate = _generate_sine(amplitude=0.3)
        result = remove_clicks(data, rate, threshold=6.0)
        # Most samples should be identical
        diff = np.max(np.abs(result - data))
        assert diff < 0.1

    def test_zero_threshold_is_passthrough(self):
        data, rate = _generate_sine()
        result = remove_clicks(data, rate, threshold=0)
        assert np.array_equal(result, data)

    def test_mono_input(self):
        data, rate = _generate_sine(stereo=False)
        result = remove_clicks(data, rate)
        assert result.shape == data.shape

    def test_output_is_finite(self):
        data, rate = _generate_click()
        result = remove_clicks(data, rate)
        assert np.all(np.isfinite(result))


# ─── Tests: reduce_noise ─────────────────────────────────────────────


class TestReduceNoise:
    """Tests for spectral gating noise reduction."""

    def test_reduces_noise_floor(self):
        """Noise reduction should reduce low-level noise."""
        pytest.importorskip("noisereduce")
        data, rate = _generate_noise(amplitude=0.1, stereo=True)
        result = reduce_noise(data, rate, strength=0.8)
        assert np.std(result) < np.std(data)

    def test_zero_strength_is_passthrough(self):
        """Zero strength should return unchanged data."""
        data, rate = _generate_noise()
        result = reduce_noise(data, rate, strength=0.0)
        assert np.array_equal(result, data)

    def test_mono_input(self):
        pytest.importorskip("noisereduce")
        data, rate = _generate_noise(stereo=False)
        result = reduce_noise(data, rate, strength=0.3)
        assert result.shape == data.shape

    def test_output_is_finite(self):
        pytest.importorskip("noisereduce")
        data, rate = _generate_noise()
        result = reduce_noise(data, rate, strength=0.5)
        assert np.all(np.isfinite(result))


# ─── Tests: enhance_stereo ───────────────────────────────────────────


class TestEnhanceStereo:
    """Tests for mid-side stereo width enhancement."""

    def test_increases_side_energy(self):
        """Enhancement should increase difference between L and R."""
        # Create a signal with slight stereo difference
        rate = 44100
        t = np.linspace(0, 1.0, rate, endpoint=False)
        left = 0.5 * np.sin(2 * np.pi * 440 * t)
        right = 0.5 * np.sin(2 * np.pi * 440 * t + 0.3)  # Phase offset
        data = np.column_stack([left, right])

        result = enhance_stereo(data, rate, amount=0.5)
        # Side signal (L-R) should be stronger
        orig_side = np.std(data[:, 0] - data[:, 1])
        enhanced_side = np.std(result[:, 0] - result[:, 1])
        assert enhanced_side > orig_side

    def test_zero_amount_is_passthrough(self):
        data, rate = _generate_sine()
        result = enhance_stereo(data, rate, amount=0.0)
        assert np.array_equal(result, data)

    def test_mono_input_returns_unchanged(self):
        data, rate = _generate_sine(stereo=False)
        result = enhance_stereo(data, rate, amount=0.5)
        assert np.array_equal(result, data)

    def test_output_is_finite(self):
        data, rate = _generate_sine()
        result = enhance_stereo(data, rate, amount=0.5)
        assert np.all(np.isfinite(result))


# ─── Tests: apply_saturation ─────────────────────────────────────────


class TestApplySaturation:
    """Tests for the tanh waveshaping saturation function."""

    def test_saturation_increases_harmonics(self):
        """Output RMS should increase with drive > 0."""
        data, rate = _generate_sine(freq=440, amplitude=0.3)
        result = apply_saturation(data, rate, drive=0.5)
        # Saturation adds harmonics which increases RMS
        orig_rms = np.sqrt(np.mean(data ** 2))
        sat_rms = np.sqrt(np.mean(result ** 2))
        assert sat_rms > orig_rms * 0.9  # At least comparable (gain normalization)

    def test_saturation_zero_drive_passthrough(self):
        """drive=0 should return identical audio."""
        data, rate = _generate_sine()
        result = apply_saturation(data, rate, drive=0.0)
        assert np.array_equal(result, data)

    def test_saturation_warm_vs_neutral(self):
        """'warm' tone should have less high-frequency energy than 'neutral'."""
        data, rate = _generate_noise(amplitude=0.3)
        warm = apply_saturation(data, rate, drive=0.5, tone='warm')
        neutral = apply_saturation(data, rate, drive=0.5, tone='neutral')
        # Compare high-frequency energy (last quarter of spectrum)
        from scipy import fft
        warm_spectrum = np.abs(fft.rfft(warm[:, 0]))
        neutral_spectrum = np.abs(fft.rfft(neutral[:, 0]))
        high_start = len(warm_spectrum) * 3 // 4
        warm_highs = np.sum(warm_spectrum[high_start:])
        neutral_highs = np.sum(neutral_spectrum[high_start:])
        assert warm_highs < neutral_highs

    def test_saturation_output_is_finite(self):
        """Saturation should never produce NaN/inf."""
        data, rate = _generate_sine(amplitude=0.9)
        result = apply_saturation(data, rate, drive=1.0)
        assert np.all(np.isfinite(result))

    def test_saturation_mono_input(self):
        """Saturation should work on mono (1D) arrays."""
        data, rate = _generate_sine(stereo=False)
        result = apply_saturation(data, rate, drive=0.3)
        assert result.shape == data.shape


# ─── Tests: apply_lowpass ────────────────────────────────────────────


class TestApplyLowpass:
    """Tests for the Butterworth lowpass filter."""

    def test_lowpass_removes_highs(self):
        """Energy above cutoff should be reduced."""
        data, rate = _generate_sine(freq=10000, amplitude=0.5)
        result = apply_lowpass(data, rate, cutoff=5000)
        assert np.max(np.abs(result)) < np.max(np.abs(data))

    def test_lowpass_high_cutoff_passthrough(self):
        """Cutoff at or above Nyquist should return unchanged data."""
        data, rate = _generate_sine(freq=440, amplitude=0.5)
        # Cutoff >= Nyquist (22050) returns unchanged
        result = apply_lowpass(data, rate, cutoff=22050)
        assert np.array_equal(result, data)

    def test_lowpass_passes_low_frequencies(self):
        """Lowpass should pass frequencies below cutoff."""
        data, rate = _generate_sine(freq=100, amplitude=0.5)
        result = apply_lowpass(data, rate, cutoff=5000)
        # Low-freq signal should be mostly unchanged
        assert np.max(np.abs(result)) > 0.3

    def test_lowpass_mono_input(self):
        """Should work with mono (1D) arrays."""
        data, rate = _generate_sine(freq=10000, stereo=False)
        result = apply_lowpass(data, rate, cutoff=5000)
        assert result.shape == data.shape

    def test_lowpass_output_is_finite(self):
        data, rate = _generate_sine()
        result = apply_lowpass(data, rate, cutoff=8000)
        assert np.all(np.isfinite(result))


# ─── Tests: apply_stereo_width ───────────────────────────────────────


class TestApplyStereoWidth:
    """Tests for the mid-side stereo width adjustment function."""

    def test_stereo_width_narrow(self):
        """width < 1.0 should reduce L-R difference."""
        rate = 44100
        t = np.linspace(0, 1.0, rate, endpoint=False)
        left = 0.5 * np.sin(2 * np.pi * 440 * t)
        right = 0.5 * np.sin(2 * np.pi * 440 * t + 0.3)
        data = np.column_stack([left, right])

        result = apply_stereo_width(data, rate, width=0.5)
        orig_diff = np.std(data[:, 0] - data[:, 1])
        narrow_diff = np.std(result[:, 0] - result[:, 1])
        assert narrow_diff < orig_diff

    def test_stereo_width_wide(self):
        """width > 1.0 should increase L-R difference."""
        rate = 44100
        t = np.linspace(0, 1.0, rate, endpoint=False)
        left = 0.5 * np.sin(2 * np.pi * 440 * t)
        right = 0.5 * np.sin(2 * np.pi * 440 * t + 0.3)
        data = np.column_stack([left, right])

        result = apply_stereo_width(data, rate, width=1.5)
        orig_diff = np.std(data[:, 0] - data[:, 1])
        wide_diff = np.std(result[:, 0] - result[:, 1])
        assert wide_diff > orig_diff

    def test_stereo_width_unity_passthrough(self):
        """width=1.0 should return identical audio."""
        data, rate = _generate_sine()
        result = apply_stereo_width(data, rate, width=1.0)
        assert np.array_equal(result, data)

    def test_stereo_width_mono_returns_unchanged(self):
        """Mono input should be returned unchanged."""
        data, rate = _generate_sine(stereo=False)
        result = apply_stereo_width(data, rate, width=1.5)
        assert np.array_equal(result, data)

    def test_stereo_width_output_is_finite(self):
        data, rate = _generate_sine()
        result = apply_stereo_width(data, rate, width=2.0)
        assert np.all(np.isfinite(result))


# ─── Tests: lo-fi preset integration ────────────────────────────────


class TestLofiPresetIntegration:
    """Integration test: lo-fi preset should activate saturation in full_mix chain."""

    def test_lofi_preset_applies_saturation(self, noise_wav, output_path):
        """lo-fi genre preset should activate saturation in full_mix chain."""
        settings = _get_full_mix_settings(genre='lo-fi')
        assert settings.get('saturation_drive', 0) > 0, \
            "lo-fi preset should set saturation_drive > 0 for full_mix"
        assert settings.get('lowpass_cutoff', 20000) < 20000, \
            "lo-fi preset should set lowpass_cutoff < 20000 for full_mix"

        # Run full pipeline to ensure it doesn't crash
        result = mix_track_full(noise_wav, output_path, genre='lo-fi')
        assert Path(output_path).exists()
        assert not result.get('error')


# ─── Tests: remix_stems ──────────────────────────────────────────────


class TestRemixStems:
    """Tests for stem remixing."""

    def test_basic_remix(self):
        """Should combine stems into a single stereo output."""
        rate = 44100
        t = np.linspace(0, 1.0, rate, endpoint=False)

        stems = {
            'vocals': (np.column_stack([
                0.3 * np.sin(2 * np.pi * 440 * t),
                0.3 * np.sin(2 * np.pi * 440 * t),
            ]), rate),
            'drums': (np.column_stack([
                0.3 * np.sin(2 * np.pi * 200 * t),
                0.3 * np.sin(2 * np.pi * 200 * t),
            ]), rate),
        }

        mixed, out_rate = remix_stems(stems)
        assert out_rate == rate
        assert mixed.shape == (rate, 2)
        assert np.max(np.abs(mixed)) > 0

    def test_gain_adjustment(self):
        """Positive gain should increase stem level in mix."""
        rate = 44100
        data = np.zeros((rate, 2))
        data[:, 0] = 0.3
        data[:, 1] = 0.3
        stems = {'vocals': (data.copy(), rate)}

        # Mix with unity gain
        mixed_unity, _ = remix_stems(stems, gains_dict={'vocals': 0.0})
        # Mix with +6 dB gain
        mixed_boosted, _ = remix_stems(stems, gains_dict={'vocals': 6.0})

        assert np.max(np.abs(mixed_boosted)) > np.max(np.abs(mixed_unity))

    def test_mono_stem_to_stereo(self):
        """Mono stems should be expanded to stereo in the mix."""
        rate = 44100
        mono = np.ones(rate) * 0.3
        stems = {'bass': (mono, rate)}

        mixed, _ = remix_stems(stems)
        assert mixed.shape == (rate, 2)
        # Both channels should have the mono content
        assert np.allclose(mixed[:, 0], mixed[:, 1], atol=1e-6)

    def test_different_lengths_padded(self):
        """Stems of different lengths should be zero-padded."""
        rate = 44100
        short = np.column_stack([np.ones(rate), np.ones(rate)]) * 0.3
        long = np.column_stack([np.ones(rate * 2), np.ones(rate * 2)]) * 0.3

        stems = {
            'vocals': (short, rate),
            'bass': (long, rate),
        }

        mixed, _ = remix_stems(stems)
        assert mixed.shape[0] == rate * 2

    def test_empty_stems_raises(self):
        """Empty stems dict should raise ValueError."""
        with pytest.raises(ValueError):
            remix_stems({})

    def test_prevents_clipping(self):
        """Output should not exceed 0.95 peak."""
        rate = 44100
        loud = np.column_stack([np.ones(rate), np.ones(rate)]) * 0.8
        stems = {
            'vocals': (loud.copy(), rate),
            'drums': (loud.copy(), rate),
            'bass': (loud.copy(), rate),
            'other': (loud.copy(), rate),
        }

        mixed, _ = remix_stems(stems)
        assert np.max(np.abs(mixed)) <= 0.95 + 1e-6


# ─── Tests: Per-Stem Processors ──────────────────────────────────────


class TestProcessVocals:
    """Tests for the vocal processing chain."""

    def test_produces_output(self):
        data, rate = _generate_sine(freq=800, amplitude=0.5)
        result = process_vocals(data, rate)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_with_custom_settings(self):
        data, rate = _generate_sine(freq=800, amplitude=0.5)
        settings = {
            'noise_reduction': 0.0,
            'presence_boost_db': 3.0,
            'presence_freq': 3000,
            'high_tame_db': -3.0,
            'high_tame_freq': 7000,
            'compress_threshold_db': -12.0,
            'compress_ratio': 3.0,
            'compress_attack_ms': 10.0,
        }
        result = process_vocals(data, rate, settings=settings)
        assert np.all(np.isfinite(result))


class TestProcessDrums:
    """Tests for the drum processing chain."""

    def test_produces_output(self):
        data, rate = _generate_noise(amplitude=0.5)
        result = process_drums(data, rate)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_with_click_removal_disabled(self):
        data, rate = _generate_noise(amplitude=0.5)
        settings = {
            'click_removal': False,
            'compress_threshold_db': -12.0,
            'compress_ratio': 2.0,
            'compress_attack_ms': 5.0,
        }
        result = process_drums(data, rate, settings=settings)
        assert np.all(np.isfinite(result))


class TestProcessBass:
    """Tests for the bass processing chain."""

    def test_produces_output(self):
        data, rate = _generate_sine(freq=80, amplitude=0.5)
        result = process_bass(data, rate)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_highpass_removes_sub_rumble(self):
        """Bass processor should remove sub-bass rumble."""
        data, rate = _generate_sine(freq=15, amplitude=0.5)
        result = process_bass(data, rate)
        # Very low frequency should be reduced
        assert np.max(np.abs(result)) < np.max(np.abs(data))


class TestProcessOther:
    """Tests for the 'other' stem processing chain."""

    def test_produces_output(self):
        data, rate = _generate_sine(freq=2000, amplitude=0.4)
        result = process_other(data, rate)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))


class TestProcessBackingVocals:
    """Tests for the backing vocal processing chain."""

    def test_produces_output(self):
        data, rate = _generate_sine(freq=800, amplitude=0.5)
        result = process_backing_vocals(data, rate)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_less_presence_than_lead(self):
        """Backing vocals should have less presence boost than lead vocals."""
        bv_settings = _get_stem_settings('backing_vocals')
        lead_settings = _get_stem_settings('vocals')
        assert bv_settings['presence_boost_db'] < lead_settings['presence_boost_db']

    def test_with_custom_settings(self):
        data, rate = _generate_sine(freq=800, amplitude=0.5)
        settings = {
            'noise_reduction': 0.0,
            'presence_boost_db': 0.5,
            'presence_freq': 3000,
            'high_tame_db': -3.0,
            'high_tame_freq': 7000,
            'stereo_width': 1.0,
            'compress_threshold_db': -14.0,
            'compress_ratio': 3.0,
            'compress_attack_ms': 8.0,
        }
        result = process_backing_vocals(data, rate, settings=settings)
        assert np.all(np.isfinite(result))

    def test_default_gain_is_negative(self):
        """Backing vocals default gain should be negative (sit behind lead)."""
        settings = _get_stem_settings('backing_vocals')
        assert settings['gain_db'] < 0


class TestProcessSynth:
    """Tests for the synth processing chain."""

    def test_produces_output(self):
        data, rate = _generate_sine(freq=2000, amplitude=0.4)
        result = process_synth(data, rate)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_highpass_removes_sub_bass(self):
        """Synth processor should remove sub-bass via highpass."""
        data, rate = _generate_sine(freq=30, amplitude=0.5)
        result = process_synth(data, rate)
        assert np.max(np.abs(result)) < np.max(np.abs(data))

    def test_with_custom_settings(self):
        data, rate = _generate_sine(freq=2000, amplitude=0.4)
        settings = {
            'highpass_cutoff': 100,
            'mid_boost_db': 2.0,
            'mid_freq': 2000,
            'high_tame_db': -2.0,
            'high_tame_freq': 9000,
            'stereo_width': 1.0,
            'compress_threshold_db': -16.0,
            'compress_ratio': 2.0,
            'compress_attack_ms': 15.0,
        }
        result = process_synth(data, rate, settings=settings)
        assert np.all(np.isfinite(result))


class TestProcessGuitar:
    """Tests for the guitar processing chain."""

    def test_produces_output(self):
        data, rate = _generate_sine(freq=1200, amplitude=0.4)
        result = process_guitar(data, rate)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_highpass_removes_sub_bass(self):
        """Guitar processor should remove sub-bass via highpass."""
        data, rate = _generate_sine(freq=30, amplitude=0.5)
        result = process_guitar(data, rate)
        assert np.max(np.abs(result)) < np.max(np.abs(data))

    def test_with_custom_settings(self):
        data, rate = _generate_sine(freq=1200, amplitude=0.4)
        settings = {
            'highpass_cutoff': 100,
            'mud_cut_db': -3.0,
            'mud_freq': 250,
            'presence_boost_db': 2.0,
            'presence_freq': 3000,
            'high_tame_db': -2.0,
            'high_tame_freq': 8000,
            'stereo_width': 1.0,
            'compress_threshold_db': -14.0,
            'compress_ratio': 2.5,
            'compress_attack_ms': 12.0,
        }
        result = process_guitar(data, rate, settings=settings)
        assert np.all(np.isfinite(result))


class TestProcessKeyboard:
    """Tests for the keyboard processing chain."""

    def test_produces_output(self):
        data, rate = _generate_sine(freq=1500, amplitude=0.4)
        result = process_keyboard(data, rate)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_preserves_low_piano_notes(self):
        """Low highpass (40 Hz) should preserve piano bass notes."""
        # A note at 55 Hz (A1 on piano) should mostly pass
        data, rate = _generate_sine(freq=55, amplitude=0.5)
        result = process_keyboard(data, rate)
        # Should retain significant energy (highpass at 40 Hz, signal at 55 Hz)
        assert np.max(np.abs(result)) > 0.1

    def test_with_custom_settings(self):
        data, rate = _generate_sine(freq=1500, amplitude=0.4)
        settings = {
            'highpass_cutoff': 50,
            'mud_cut_db': -2.0,
            'mud_freq': 300,
            'presence_boost_db': 1.5,
            'presence_freq': 2500,
            'high_tame_db': -2.0,
            'high_tame_freq': 9000,
            'stereo_width': 1.0,
            'compress_threshold_db': -16.0,
            'compress_ratio': 2.0,
            'compress_attack_ms': 15.0,
        }
        result = process_keyboard(data, rate, settings=settings)
        assert np.all(np.isfinite(result))


class TestProcessStrings:
    """Tests for the strings processing chain."""

    def test_produces_output(self):
        data, rate = _generate_sine(freq=600, amplitude=0.4)
        result = process_strings(data, rate)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_very_light_compression(self):
        """Strings should use lightest compression (1.5:1 default)."""
        settings = _get_stem_settings('strings')
        assert settings['compress_ratio'] == 1.5

    def test_with_custom_settings(self):
        data, rate = _generate_sine(freq=600, amplitude=0.4)
        settings = {
            'highpass_cutoff': 40,
            'mud_cut_db': -1.0,
            'mud_freq': 250,
            'presence_boost_db': 1.5,
            'presence_freq': 3500,
            'high_tame_db': -1.0,
            'high_tame_freq': 9000,
            'stereo_width': 1.0,
            'compress_threshold_db': -18.0,
            'compress_ratio': 1.5,
            'compress_attack_ms': 20.0,
        }
        result = process_strings(data, rate, settings=settings)
        assert np.all(np.isfinite(result))


class TestProcessBrass:
    """Tests for the brass processing chain."""

    def test_produces_output(self):
        data, rate = _generate_sine(freq=1000, amplitude=0.4)
        result = process_brass(data, rate)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_high_tame_controls_harshness(self):
        """Brass high tame should be aggressive (-2 dB at 7 kHz)."""
        settings = _get_stem_settings('brass')
        assert settings['high_tame_db'] == -2.0
        assert settings['high_tame_freq'] == 7000

    def test_with_custom_settings(self):
        data, rate = _generate_sine(freq=1000, amplitude=0.4)
        settings = {
            'highpass_cutoff': 80,
            'mud_cut_db': -2.0,
            'mud_freq': 300,
            'presence_boost_db': 2.0,
            'presence_freq': 2000,
            'high_tame_db': -3.0,
            'high_tame_freq': 7000,
            'compress_threshold_db': -14.0,
            'compress_ratio': 2.5,
            'compress_attack_ms': 10.0,
        }
        result = process_brass(data, rate, settings=settings)
        assert np.all(np.isfinite(result))


class TestProcessWoodwinds:
    """Tests for the woodwinds processing chain."""

    def test_produces_output(self):
        data, rate = _generate_sine(freq=2200, amplitude=0.4)
        result = process_woodwinds(data, rate)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_preserves_breathiness(self):
        """Woodwinds high tame should be gentle (-1 dB) to preserve breathiness."""
        settings = _get_stem_settings('woodwinds')
        assert settings['high_tame_db'] == -1.0

    def test_with_custom_settings(self):
        data, rate = _generate_sine(freq=2200, amplitude=0.4)
        settings = {
            'highpass_cutoff': 60,
            'mud_cut_db': -1.5,
            'mud_freq': 250,
            'presence_boost_db': 1.5,
            'presence_freq': 2500,
            'high_tame_db': -1.5,
            'high_tame_freq': 8000,
            'compress_threshold_db': -16.0,
            'compress_ratio': 2.0,
            'compress_attack_ms': 15.0,
        }
        result = process_woodwinds(data, rate, settings=settings)
        assert np.all(np.isfinite(result))


class TestProcessPercussion:
    """Tests for the percussion processing chain."""

    def test_produces_output(self):
        data, rate = _generate_noise(amplitude=0.4)
        result = process_percussion(data, rate)
        assert result.shape == data.shape
        assert np.all(np.isfinite(result))

    def test_click_removal_works(self):
        """Percussion should apply click removal by default."""
        data, rate = _generate_click(amplitude=0.5)
        result = process_percussion(data, rate)
        click_idx = int(0.5 * rate)
        assert np.abs(result[click_idx, 0]) < np.abs(data[click_idx, 0])

    def test_with_custom_settings(self):
        data, rate = _generate_noise(amplitude=0.4)
        settings = {
            'highpass_cutoff': 80,
            'click_removal': False,
            'presence_boost_db': 1.5,
            'presence_freq': 4000,
            'high_tame_db': -1.5,
            'high_tame_freq': 10000,
            'stereo_width': 1.0,
            'compress_threshold_db': -15.0,
            'compress_ratio': 2.0,
            'compress_attack_ms': 8.0,
        }
        result = process_percussion(data, rate, settings=settings)
        assert np.all(np.isfinite(result))


# ─── Tests: Full Pipeline (Stems) ────────────────────────────────────


class TestMixTrackStems:
    """Integration tests for the stems processing pipeline."""

    def test_basic_stems_processing(self, stem_dir, output_path):
        """Process stems directory and produce output WAV."""
        stem_paths = {
            name: str(stem_dir / f"{name}.wav")
            for name in ('vocals', 'drums', 'bass', 'other')
        }
        result = mix_track_stems(stem_paths, output_path)

        assert result['mode'] == 'stems'
        assert len(result['stems_processed']) == 4
        assert Path(output_path).exists()
        assert not result.get('error')

    def test_dry_run_no_output(self, stem_dir, output_path):
        """Dry run should analyze but not write files."""
        stem_paths = {
            name: str(stem_dir / f"{name}.wav")
            for name in ('vocals', 'drums', 'bass', 'other')
        }
        result = mix_track_stems(stem_paths, output_path, dry_run=True)

        assert result['dry_run'] is True
        assert len(result['stems_processed']) == 4
        assert not Path(output_path).exists()

    def test_partial_stems(self, stem_dir, output_path):
        """Should work with only some stems available."""
        stem_paths = {
            'vocals': str(stem_dir / "vocals.wav"),
            'drums': str(stem_dir / "drums.wav"),
        }
        result = mix_track_stems(stem_paths, output_path)

        assert len(result['stems_processed']) == 2
        assert Path(output_path).exists()

    def test_with_genre_preset(self, stem_dir, output_path):
        """Genre preset should be applied."""
        stem_paths = {
            name: str(stem_dir / f"{name}.wav")
            for name in ('vocals', 'drums', 'bass', 'other')
        }
        result = mix_track_stems(stem_paths, output_path, genre='rock')

        assert len(result['stems_processed']) == 4
        assert Path(output_path).exists()

    def test_output_is_valid_wav(self, stem_dir, output_path):
        """Output should be a readable stereo WAV."""
        stem_paths = {
            name: str(stem_dir / f"{name}.wav")
            for name in ('vocals', 'drums', 'bass', 'other')
        }
        mix_track_stems(stem_paths, output_path)

        data, rate = sf.read(output_path)
        assert rate == 44100
        assert len(data.shape) == 2
        assert data.shape[1] == 2
        assert np.all(np.isfinite(data))

    def test_missing_stem_file_skipped(self, stem_dir, output_path):
        """Missing stem files should be skipped gracefully."""
        stem_paths = {
            'vocals': str(stem_dir / "vocals.wav"),
            'drums': str(stem_dir / "nonexistent.wav"),
        }
        result = mix_track_stems(stem_paths, output_path)

        assert len(result['stems_processed']) == 1
        assert Path(output_path).exists()

    def test_stems_applies_stereo_width(self, stem_dir, output_path):
        """Stems pipeline should apply stereo width for genres that define it."""
        stem_paths = {
            name: str(stem_dir / f"{name}.wav")
            for name in ('vocals', 'drums', 'bass', 'other')
        }
        # Shoegaze has stereo_width: 1.4 in full_mix settings
        result = mix_track_stems(stem_paths, output_path, genre='shoegaze')

        assert Path(output_path).exists()
        assert 'stereo_width' in result, "Result should include stereo_width for shoegaze"
        assert result['stereo_width'] == 1.4

    def test_stems_no_stereo_width_for_default(self, stem_dir, output_path):
        """Stems pipeline should skip stereo width when default (1.0)."""
        stem_paths = {
            name: str(stem_dir / f"{name}.wav")
            for name in ('vocals', 'drums', 'bass', 'other')
        }
        result = mix_track_stems(stem_paths, output_path)

        assert Path(output_path).exists()
        assert 'stereo_width' not in result, \
            "Result should not include stereo_width when default (1.0)"

    def test_no_valid_stems_returns_error(self, tmp_path, output_path):
        """All missing stems should return error."""
        stem_paths = {
            'vocals': str(tmp_path / "missing.wav"),
        }
        result = mix_track_stems(stem_paths, output_path)
        assert result.get('error')

    def test_empty_stem_wav_skipped(self, stem_dir, output_path):
        """Empty (zero-sample) stem WAV should be skipped, not crash."""
        # Overwrite vocals with an empty WAV
        empty_path = stem_dir / "vocals.wav"
        sf.write(str(empty_path), np.array([]).reshape(0, 2), 44100)

        stem_paths = {
            'vocals': str(empty_path),
            'drums': str(stem_dir / "drums.wav"),
        }
        result = mix_track_stems(stem_paths, output_path)

        # Only drums should be processed; vocals skipped
        assert len(result['stems_processed']) == 1
        assert result['stems_processed'][0]['stem'] == 'drums'
        assert Path(output_path).exists()


# ─── Tests: Stem Discovery ───────────────────────────────────────────


class TestDiscoverStems:
    """Test discover_stems with standard and Suno naming conventions."""

    def test_standard_naming(self, stem_dir):
        """Standard names (vocals.wav, drums.wav, etc.) are found."""
        result = discover_stems(stem_dir)
        assert 'vocals' in result
        assert 'drums' in result
        assert 'bass' in result
        assert 'other' in result
        assert result['vocals'].endswith('vocals.wav')

    def test_suno_naming_all_included(self, tmp_path):
        """All Suno-style files are included — nothing dropped, 6 distinct categories."""
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(tmp_path / "0 Lead Vocals.wav"), tone, rate)
        sf.write(str(tmp_path / "1 Backing Vocals.wav"), tone, rate)
        sf.write(str(tmp_path / "2 Drums.wav"), tone, rate)
        sf.write(str(tmp_path / "3 Bass.wav"), tone, rate)
        sf.write(str(tmp_path / "4 Synth.wav"), tone, rate)
        sf.write(str(tmp_path / "5 Other.wav"), tone, rate)

        result = discover_stems(tmp_path)
        # Each Suno stem routes to its own category
        assert 'vocals' in result           # "0 Lead Vocals"
        assert isinstance(result['vocals'], str)  # single file
        assert 'backing_vocals' in result   # "1 Backing Vocals"
        assert isinstance(result['backing_vocals'], str)
        assert 'drums' in result            # "2 Drums"
        assert 'bass' in result             # "3 Bass"
        assert 'synth' in result            # "4 Synth"
        assert 'other' in result            # "5 Other"
        # Total: 6 files in 6 categories — nothing dropped
        total = sum(
            len(v) if isinstance(v, list) else 1
            for v in result.values()
        )
        assert total == 6

    def test_suno_vocals_keyword_matched(self, tmp_path):
        """Lead and backing vocal files are routed to separate categories."""
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(tmp_path / "0 Lead Vocals.wav"), tone, rate)
        sf.write(str(tmp_path / "1 Backing Vocals.wav"), tone, rate)

        result = discover_stems(tmp_path)
        # Lead → vocals, Backing → backing_vocals
        assert 'vocals' in result
        assert isinstance(result['vocals'], str)
        assert 'backing_vocals' in result
        assert isinstance(result['backing_vocals'], str)

    def test_single_nonstandard_stem_returns_string(self, tmp_path):
        """Single file per category returns a string, not a list."""
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(tmp_path / "2 Drums.wav"), tone, rate)

        result = discover_stems(tmp_path)
        # "2 drums" contains "drum" keyword → drums category
        assert isinstance(result['drums'], str)

    def test_suno_synth_maps_to_synth(self, tmp_path):
        """Synth stem maps to 'synth' category."""
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(tmp_path / "4 Synth.wav"), tone, rate)

        result = discover_stems(tmp_path)
        assert 'synth' in result

    def test_suno_multiple_other_returns_list(self, tmp_path):
        """Multiple non-matching stems are combined as 'other'."""
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(tmp_path / "4 FX.wav"), tone, rate)
        sf.write(str(tmp_path / "5 Other.wav"), tone, rate)

        result = discover_stems(tmp_path)
        assert isinstance(result['other'], list)
        assert len(result['other']) == 2

    def test_standard_plus_extra_stems_all_included(self, stem_dir, tmp_path):
        """Standard + Suno names all included, routed by keyword."""
        # stem_dir already has standard names (vocals.wav, drums.wav, bass.wav, other.wav)
        # Add extra Suno-named files
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(stem_dir / "0 Lead Vocals.wav"), tone, rate)
        sf.write(str(stem_dir / "synth.wav"), tone, rate)

        result = discover_stems(stem_dir)
        # vocals.wav + "0 Lead Vocals.wav" both match "vocal" keyword → list
        assert 'vocals' in result
        assert isinstance(result['vocals'], list)
        assert len(result['vocals']) == 2
        # drums.wav → drums, bass.wav → bass
        assert 'drums' in result
        assert 'bass' in result
        # synth.wav → synth (keyword match)
        assert 'synth' in result
        assert Path(result['synth']).name == "synth.wav"
        # other.wav → other (no keyword match)
        assert 'other' in result
        assert Path(result['other']).name == "other.wav"
        # Total: 6 files — nothing dropped
        total = sum(
            len(v) if isinstance(v, list) else 1
            for v in result.values()
        )
        assert total == 6

    def test_empty_directory(self, tmp_path):
        """Empty directory returns empty dict."""
        result = discover_stems(tmp_path)
        assert result == {}

    def test_uppercase_names_keyword_matched(self, tmp_path):
        """Uppercase names are matched via case-insensitive keywords."""
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(tmp_path / "LEAD VOCALS.wav"), tone, rate)
        sf.write(str(tmp_path / "DRUMS.wav"), tone, rate)

        result = discover_stems(tmp_path)
        # "lead vocals" contains "vocal" → vocals
        assert 'vocals' in result
        # "drums" contains "drum" → drums
        assert 'drums' in result

    def test_backing_vocals_not_confused_with_vocals(self, tmp_path):
        """Keyword ordering regression: backing_vocal must match before vocal."""
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(tmp_path / "1 Backing Vocals.wav"), tone, rate)

        result = discover_stems(tmp_path)
        # Must route to backing_vocals, NOT vocals
        assert 'backing_vocals' in result
        assert 'vocals' not in result


class TestMixTrackStems6Stem:
    """Integration test: all 6 Suno stems discovered + processed end-to-end."""

    def test_6_stem_end_to_end(self, stem_dir_6, output_path):
        """All 6 Suno stems are discovered, processed, and remixed."""
        stem_paths = discover_stems(stem_dir_6)

        # Should have all 6 categories
        assert len(stem_paths) == 6
        for cat in ('vocals', 'backing_vocals', 'drums', 'bass', 'synth', 'other'):
            assert cat in stem_paths, f"Missing category: {cat}"

        result = mix_track_stems(stem_paths, output_path)

        assert Path(output_path).exists()
        assert not result.get('error')
        assert len(result['stems_processed']) == 6
        processed_names = {s['stem'] for s in result['stems_processed']}
        assert processed_names == {'vocals', 'backing_vocals', 'drums', 'bass', 'synth', 'other'}


class TestMixTrackStems12Stem:
    """Integration test: all 12 Suno stems discovered + processed end-to-end."""

    def test_12_stem_end_to_end(self, stem_dir_12, output_path):
        """All 12 Suno stems are discovered, processed, and remixed."""
        stem_paths = discover_stems(stem_dir_12)

        # Should have all 12 categories
        assert len(stem_paths) == 12
        expected = {
            'vocals', 'backing_vocals', 'drums', 'bass',
            'guitar', 'keyboard', 'strings', 'brass',
            'woodwinds', 'percussion', 'synth', 'other',
        }
        for cat in expected:
            assert cat in stem_paths, f"Missing category: {cat}"

        result = mix_track_stems(stem_paths, output_path)

        assert Path(output_path).exists()
        assert not result.get('error')
        assert len(result['stems_processed']) == 12
        processed_names = {s['stem'] for s in result['stems_processed']}
        assert processed_names == expected


class TestStemDiscoveryRegression:
    """Regression tests for keyword routing edge cases."""

    def test_percussion_not_confused_with_drums(self, tmp_path):
        """'9 Percussion.wav' must route to percussion, NOT drums."""
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(tmp_path / "2 Drums.wav"), tone, rate)
        sf.write(str(tmp_path / "9 Percussion.wav"), tone, rate)

        result = discover_stems(tmp_path)
        assert 'drums' in result
        assert 'percussion' in result
        assert Path(result['drums']).name == "2 Drums.wav"
        assert Path(result['percussion']).name == "9 Percussion.wav"

    def test_keyboard_matches_piano(self, tmp_path):
        """'Piano.wav' should route to keyboard category."""
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(tmp_path / "Piano.wav"), tone, rate)

        result = discover_stems(tmp_path)
        assert 'keyboard' in result
        assert Path(result['keyboard']).name == "Piano.wav"

    def test_saxophone_matches_woodwinds(self, tmp_path):
        """'Saxophone.wav' should route to woodwinds category."""
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(tmp_path / "Saxophone.wav"), tone, rate)

        result = discover_stems(tmp_path)
        assert 'woodwinds' in result
        assert Path(result['woodwinds']).name == "Saxophone.wav"

    def test_trumpet_matches_brass(self, tmp_path):
        """'Trumpet.wav' should route to brass category."""
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(tmp_path / "Trumpet.wav"), tone, rate)

        result = discover_stems(tmp_path)
        assert 'brass' in result
        assert Path(result['brass']).name == "Trumpet.wav"

    def test_violin_matches_strings(self, tmp_path):
        """'Violin.wav' should route to strings category."""
        rate = 44100
        tone = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        sf.write(str(tmp_path / "Violin.wav"), tone, rate)

        result = discover_stems(tmp_path)
        assert 'strings' in result
        assert Path(result['strings']).name == "Violin.wav"

    def test_old_4_stem_still_works(self, stem_dir):
        """Old 4-stem directories (vocals, drums, bass, other) still work."""
        result = discover_stems(stem_dir)
        assert 'vocals' in result
        assert 'drums' in result
        assert 'bass' in result
        assert 'other' in result


class TestMixTrackStemsMultiFile:
    """Test mix_track_stems with multi-file stem categories."""

    def test_list_paths_combined(self, tmp_path):
        """Multiple paths for one category are combined."""
        rate = 44100
        t = np.arange(rate) / rate
        lead = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        backing = np.sin(2 * np.pi * 880 * t).astype(np.float32) * 0.5

        lead_path = tmp_path / "lead.wav"
        backing_path = tmp_path / "backing.wav"
        sf.write(str(lead_path), lead, rate)
        sf.write(str(backing_path), backing, rate)

        output = str(tmp_path / "output.wav")
        result = mix_track_stems(
            {'vocals': [str(lead_path), str(backing_path)]},
            output,
        )

        assert len(result['stems_processed']) == 1
        assert result['stems_processed'][0]['stem'] == 'vocals'
        assert Path(output).exists()

    def test_suno_naming_end_to_end(self, tmp_path):
        """Full pipeline with Suno-named stems — keyword-routed to correct categories."""
        rate = 44100
        t = np.arange(rate) / rate
        tone = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        sf.write(str(tmp_path / "0 Lead Vocals.wav"), tone, rate)
        sf.write(str(tmp_path / "2 Drums.wav"), tone * 0.8, rate)
        sf.write(str(tmp_path / "3 Bass.wav"), tone * 0.6, rate)
        sf.write(str(tmp_path / "5 Other.wav"), tone * 0.4, rate)

        stem_paths = discover_stems(tmp_path)
        # Keywords route each file to the right category
        assert 'vocals' in stem_paths  # "Lead Vocals" → vocal keyword
        assert 'drums' in stem_paths   # "Drums" → drum keyword
        assert 'bass' in stem_paths    # "Bass" → bass keyword
        assert 'other' in stem_paths   # "Other" → no keyword match
        # Each file in its own category — 4 distinct categories
        assert len(stem_paths) == 4
        total = sum(
            len(v) if isinstance(v, list) else 1
            for v in stem_paths.values()
        )
        assert total == 4

        output = str(tmp_path / "polished.wav")
        result = mix_track_stems(stem_paths, output)

        assert Path(output).exists()
        assert not result.get('error')


# ─── Tests: Full Pipeline (Full Mix) ─────────────────────────────────


class TestMixTrackFull:
    """Integration tests for the full-mix fallback pipeline."""

    def test_basic_full_mix(self, noise_wav, output_path):
        """Process a full mix WAV file."""
        result = mix_track_full(noise_wav, output_path)

        assert result['mode'] == 'full_mix'
        assert Path(output_path).exists()
        assert not result.get('error')

    def test_dry_run_no_output(self, noise_wav, output_path):
        """Dry run should analyze but not write files."""
        result = mix_track_full(noise_wav, output_path, dry_run=True)

        assert result['dry_run'] is True
        assert not Path(output_path).exists()

    def test_with_genre_preset(self, noise_wav, output_path):
        """Genre preset should be applied."""
        result = mix_track_full(noise_wav, output_path, genre='hip-hop')
        assert Path(output_path).exists()

    def test_mono_input(self, mono_wav, output_path):
        """Mono input should produce mono output."""
        result = mix_track_full(mono_wav, output_path)
        data, _ = sf.read(output_path)
        assert len(data.shape) == 1  # Mono output for mono input

    def test_output_is_valid_wav(self, noise_wav, output_path):
        """Output should be a valid readable WAV."""
        mix_track_full(noise_wav, output_path)
        data, rate = sf.read(output_path)
        assert rate == 44100
        assert len(data) > 0
        assert np.all(np.isfinite(data))

    def test_has_metrics(self, noise_wav, output_path):
        """Result should include before/after metrics."""
        result = mix_track_full(noise_wav, output_path)
        assert 'pre_peak' in result
        assert 'pre_rms' in result
        assert 'post_peak' in result
        assert 'post_rms' in result


# ─── Tests: Preset Loading ───────────────────────────────────────────


class TestPresetLoading:
    """Tests for YAML preset loading and merging."""

    def test_builtin_yaml_exists(self):
        assert _BUILTIN_PRESETS_FILE.exists(), f"Missing {_BUILTIN_PRESETS_FILE}"

    def test_builtin_yaml_is_valid(self):
        data = _load_yaml_file(_BUILTIN_PRESETS_FILE)
        assert 'genres' in data
        assert 'defaults' in data

    def test_defaults_have_all_stem_types(self):
        data = _load_yaml_file(_BUILTIN_PRESETS_FILE)
        defaults = data['defaults']
        for stem in ('vocals', 'backing_vocals', 'drums', 'bass', 'guitar',
                      'keyboard', 'strings', 'brass', 'woodwinds', 'percussion',
                      'synth', 'other', 'bus', 'full_mix'):
            assert stem in defaults, f"Missing default settings for '{stem}'"

    def test_common_genres_exist(self):
        data = _load_yaml_file(_BUILTIN_PRESETS_FILE)
        genres = data['genres']
        for genre in ['pop', 'rock', 'hip-hop', 'electronic', 'jazz',
                       'classical', 'folk', 'country', 'metal', 'ambient']:
            assert genre in genres, f"Expected genre '{genre}' in mix presets"

    def test_loaded_presets_structure(self):
        presets = MIX_PRESETS
        assert 'defaults' in presets
        assert 'genres' in presets
        assert 'vocals' in presets['defaults']

    def test_get_stem_settings_defaults(self):
        """Should return defaults when no genre specified."""
        settings = _get_stem_settings('vocals')
        assert 'presence_boost_db' in settings
        assert 'compress_ratio' in settings

    def test_get_stem_settings_with_genre(self):
        """Genre should override defaults."""
        settings = _get_stem_settings('vocals', genre='hip-hop')
        # Hip-hop has vocals.presence_boost_db = 2.5
        assert settings['presence_boost_db'] == 2.5

    def test_get_full_mix_settings(self):
        settings = _get_full_mix_settings()
        assert 'noise_reduction' in settings
        assert 'highpass_cutoff' in settings

    def test_load_yaml_file_missing(self, tmp_path):
        result = _load_yaml_file(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_load_yaml_file_empty(self, tmp_path):
        empty = tmp_path / "empty.yaml"
        empty.write_text("")
        result = _load_yaml_file(empty)
        assert result == {}

    def test_load_yaml_file_invalid(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(": : : not valid [[[")
        result = _load_yaml_file(bad)
        assert result == {}


class TestDeepMerge:
    """Tests for the deep merge utility."""

    def test_shallow_merge(self):
        result = _deep_merge({'a': 1}, {'b': 2})
        assert result == {'a': 1, 'b': 2}

    def test_override_value(self):
        result = _deep_merge({'a': 1}, {'a': 2})
        assert result == {'a': 2}

    def test_nested_merge(self):
        base = {'vocals': {'gain_db': 0.0, 'presence_boost_db': 2.0}}
        override = {'vocals': {'gain_db': 1.0}}
        result = _deep_merge(base, override)
        assert result == {'vocals': {'gain_db': 1.0, 'presence_boost_db': 2.0}}

    def test_override_adds_new_nested_key(self):
        base = {'vocals': {'gain_db': 0.0}}
        override = {'vocals': {'noise_reduction': 0.5}}
        result = _deep_merge(base, override)
        assert result == {'vocals': {'gain_db': 0.0, 'noise_reduction': 0.5}}

    def test_base_unchanged(self):
        base = {'a': 1}
        _deep_merge(base, {'a': 2})
        assert base == {'a': 1}


# ─── Tests: Numerical Stability ──────────────────────────────────────


class TestNumericalStability:
    """Tests for edge cases that could cause crashes or corruption."""

    def test_eq_extreme_gain(self):
        data, rate = _generate_sine()
        result = apply_eq(data, rate, freq=1000, gain_db=-24.0, q=1.0)
        assert np.all(np.isfinite(result))

    def test_eq_extreme_boost(self):
        data, rate = _generate_sine(amplitude=0.1)
        result = apply_eq(data, rate, freq=1000, gain_db=24.0, q=1.0)
        assert np.all(np.isfinite(result))

    def test_compress_silent_signal(self):
        data = np.zeros((44100, 2))
        result = gentle_compress(data, 44100, threshold_db=-20.0, ratio=4.0)
        assert np.all(np.isfinite(result))

    def test_remix_silent_stems(self):
        rate = 44100
        silence = np.zeros((rate, 2))
        stems = {'vocals': (silence.copy(), rate), 'bass': (silence.copy(), rate)}
        mixed, _ = remix_stems(stems)
        assert np.all(np.isfinite(mixed))

    def test_highpass_near_nyquist(self):
        data, rate = _generate_sine()
        result = apply_highpass(data, rate, cutoff=rate // 2 - 1)
        # Should still produce finite output (even if filter is extreme)
        assert np.all(np.isfinite(result))

    def test_process_very_short_audio(self):
        """Very short audio (< 100 samples) should not crash."""
        data = np.random.randn(50, 2) * 0.3
        rate = 44100
        result = process_vocals(data, rate, settings={
            'noise_reduction': 0.0,
            'presence_boost_db': 2.0,
            'presence_freq': 3000,
            'high_tame_db': -2.0,
            'high_tame_freq': 7000,
            'compress_threshold_db': -15.0,
            'compress_ratio': 2.5,
            'compress_attack_ms': 10.0,
        })
        assert np.all(np.isfinite(result))


# ─── Tests: Override Merging ─────────────────────────────────────────


class TestOverrideMerging:
    """Tests for user override preset merging."""

    def test_override_merges_genre(self, tmp_path, monkeypatch):
        """User override should deep-merge into built-in genre."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        override_file = override_dir / "mix-presets.yaml"
        override_file.write_text(
            "genres:\n"
            "  rock:\n"
            "    vocals:\n"
            "      gain_db: 2.0\n"
        )

        import tools.mixing.mix_tracks as mt
        monkeypatch.setattr(mt, '_get_overrides_path', lambda: override_dir)

        presets = load_mix_presets()
        rock_vocals = presets['genres']['rock']['vocals']
        assert rock_vocals['gain_db'] == 2.0
        # Should keep other built-in rock vocal settings
        assert 'high_tame_db' in rock_vocals

    def test_override_adds_new_genre(self, tmp_path, monkeypatch):
        """User override can add entirely new genres."""
        override_dir = tmp_path / "overrides"
        override_dir.mkdir()
        override_file = override_dir / "mix-presets.yaml"
        override_file.write_text(
            "genres:\n"
            "  dark-ambient:\n"
            "    vocals:\n"
            "      noise_reduction: 0.8\n"
            "      gain_db: -1.0\n"
        )

        import tools.mixing.mix_tracks as mt
        monkeypatch.setattr(mt, '_get_overrides_path', lambda: override_dir)

        presets = load_mix_presets()
        assert 'dark-ambient' in presets['genres']
        assert presets['genres']['dark-ambient']['vocals']['noise_reduction'] == 0.8

    def test_no_override_dir_works(self, monkeypatch):
        """When no override directory exists, built-in presets load fine."""
        import tools.mixing.mix_tracks as mt
        monkeypatch.setattr(mt, '_get_overrides_path', lambda: None)

        presets = load_mix_presets()
        assert 'rock' in presets['genres']
        assert 'pop' in presets['genres']


# ─── Tests: Bus Compression ─────────────────────────────────────────


class TestBusCompression:
    """Tests for mix bus compression in the stems pipeline."""

    def test_bus_compression_reduces_peaks(self):
        """Bus compression should reduce peak level on sustained material."""
        # Sustained loud sine — represents post-remix combined signal
        data, rate = _generate_sine(freq=440, amplitude=0.8)

        pre_peak = float(np.max(np.abs(data)))

        result = gentle_compress(
            data, rate,
            threshold_db=-14.0, ratio=2.5,
            attack_ms=20.0, release_ms=150.0,
        )

        post_peak = float(np.max(np.abs(result)))

        assert post_peak < pre_peak, (
            f"Bus compression should reduce peaks: {pre_peak:.4f} → {post_peak:.4f}"
        )

    def test_bus_compression_settings_from_presets(self):
        """_get_bus_settings() should return correct defaults."""
        settings = _get_bus_settings()
        assert settings['compress_threshold_db'] == -14.0
        assert settings['compress_ratio'] == 2.5
        assert settings['compress_attack_ms'] == 20.0
        assert settings['compress_release_ms'] == 150.0

    def test_bus_compression_genre_override(self):
        """Genre overrides should apply to bus settings."""
        # Classical should bypass (ratio 1.0)
        classical = _get_bus_settings(genre='classical')
        assert classical['compress_ratio'] == 1.0

        # EDM should use tighter compression (ratio 3.0)
        edm = _get_bus_settings(genre='edm')
        assert edm['compress_ratio'] == 3.0

        # Jazz should bypass (ratio 1.0)
        jazz = _get_bus_settings(genre='jazz')
        assert jazz['compress_ratio'] == 1.0

    def test_bus_compression_bypass_when_ratio_unity(self):
        """Ratio 1.0 should effectively be a no-op (bypass)."""
        data, rate = _generate_sine(freq=440, amplitude=0.8)
        result = gentle_compress(
            data, rate,
            threshold_db=-14.0, ratio=1.0,
            attack_ms=20.0, release_ms=150.0,
        )
        assert np.array_equal(result, data)

    def test_mix_track_stems_applies_bus_compression(self, stem_dir, output_path):
        """Full stems pipeline should produce output with bus compression metrics."""
        stem_paths = {
            name: str(stem_dir / f"{name}.wav")
            for name in ('vocals', 'drums', 'bass', 'other')
        }
        result = mix_track_stems(stem_paths, output_path)

        assert Path(output_path).exists()
        assert 'bus_compression' in result, "Result should include bus_compression metrics"
        bus = result['bus_compression']
        assert bus['ratio'] == 2.5
        assert bus['post_peak'] <= 0.95 + 1e-6
