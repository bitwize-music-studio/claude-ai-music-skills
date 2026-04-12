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
    apply_sub_bass_exciter,
    apply_transient_shaper,
    gentle_compress,
    remove_clicks,
    reduce_noise,
    enhance_stereo,
    _apply_character_effects,
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
    _resolve_master_click_thresholds,
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
    # Background kept quiet (0.1x) so a 10 ms window containing the click
    # has peak/rms > 6.0 — required by TestRemoveClicksPeakRatio tests.
    data = (amplitude * 0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
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
        result, n_clicks = remove_clicks(data, rate, threshold=4.0)
        # The click sample should be reduced
        click_idx = int(0.5 * rate)
        assert np.abs(result[click_idx, 0]) < np.abs(data[click_idx, 0])
        assert n_clicks > 0

    def test_clean_signal_unchanged(self):
        """Clean signal without clicks should be mostly unchanged."""
        data, rate = _generate_sine(amplitude=0.3)
        result, n_clicks = remove_clicks(data, rate, threshold=6.0)
        # Most samples should be identical
        diff = np.max(np.abs(result - data))
        assert diff < 0.1
        assert n_clicks == 0

    def test_zero_threshold_is_passthrough(self):
        data, rate = _generate_sine()
        result, n_clicks = remove_clicks(data, rate, threshold=0)
        assert np.array_equal(result, data)
        assert n_clicks == 0

    def test_mono_input(self):
        data, rate = _generate_sine(stereo=False)
        result, n_clicks = remove_clicks(data, rate)
        assert result.shape == data.shape

    def test_output_is_finite(self):
        data, rate = _generate_click()
        result, n_clicks = remove_clicks(data, rate)
        assert np.all(np.isfinite(result))


class TestRemoveClicksPeakRatio:
    """Tests for the windowed peak/rms detection path (#289)."""

    def test_peak_ratio_detects_high_peak_rms_window(self):
        """A lone spike in an otherwise-quiet sine should register as a click."""
        data, rate = _generate_click(amplitude=0.5)
        # Default peak_ratio=6.0 matches QC's hard-coded default
        result, n_clicks = remove_clicks(data, rate, peak_ratio=6.0)
        assert n_clicks >= 1
        # Click sample reduced in both channels
        click_idx = int(0.5 * rate)
        assert np.abs(result[click_idx, 0]) < np.abs(data[click_idx, 0])

    def test_strict_peak_ratio_skips_moderate_click(self):
        """A strict peak_ratio (50.0) should not flag a modest transient —
        higher ratios demand bigger peak/rms separation before flagging."""
        data, rate = _generate_click(amplitude=0.5)
        # peak/rms of this click in a 10 ms window is ~10.2; a strict 50.0
        # ratio requires ~5× higher separation, so no click should fire.
        result, n_clicks = remove_clicks(data, rate, peak_ratio=50.0)
        assert n_clicks == 0
        assert np.array_equal(result, data)

    def test_peak_ratio_takes_precedence_over_threshold(self):
        """When both `threshold` and `peak_ratio` are set, peak_ratio wins."""
        data, rate = _generate_click(amplitude=0.5)
        # threshold=0 would passthrough in std path; peak_ratio path must
        # still detect the click.
        result, n_clicks = remove_clicks(data, rate, threshold=0, peak_ratio=6.0)
        assert n_clicks >= 1

    def test_peak_ratio_on_mono(self):
        data, rate = _generate_click(amplitude=0.5)
        mono = data[:, 0]
        result, n_clicks = remove_clicks(mono, rate, peak_ratio=6.0)
        assert result.shape == mono.shape
        assert n_clicks >= 1


class TestRemoveClicksCubicRepair:
    """Tests for the cubic-spline stem-tier repair path (#289)."""

    def test_cubic_repair_differs_from_linear_on_stem(self):
        """Cubic repair should produce a different signal than linear on
        an isolated stem with a click — this is the whole point of the
        stem-tier upgrade."""
        data, rate = _generate_click(amplitude=0.5)
        linear_result, _ = remove_clicks(data, rate, peak_ratio=6.0, repair="linear")
        cubic_result, _ = remove_clicks(data, rate, peak_ratio=6.0, repair="cubic")
        # Same detections, different repair — the repaired samples must differ.
        click_idx = int(0.5 * rate)
        assert not np.allclose(
            linear_result[click_idx - 1:click_idx + 2, 0],
            cubic_result[click_idx - 1:click_idx + 2, 0],
        )

    def test_cubic_repair_is_finite(self):
        """Spline repair must never produce NaN or Inf."""
        data, rate = _generate_click(amplitude=0.5)
        result, _ = remove_clicks(data, rate, peak_ratio=6.0, repair="cubic")
        assert np.all(np.isfinite(result))

    def test_cubic_repair_reduces_click_amplitude(self):
        """Repaired click sample should be closer to the local sine value
        than the original spike."""
        data, rate = _generate_click(amplitude=0.5)
        result, _ = remove_clicks(data, rate, peak_ratio=6.0, repair="cubic")
        click_idx = int(0.5 * rate)
        # Original click is |~0.495|; local sine at 440 Hz amp 0.05 is
        # near zero at t=0.5s. Repaired sample should be near zero — 0.05
        # is a generous upper bound that would still catch a regression
        # leaving a partially-repaired click.
        assert np.abs(result[click_idx, 0]) < 0.05

    def test_cubic_repair_near_buffer_edge_falls_back_to_linear(self):
        """A click within window_ms of the start should not crash; it
        should fall back to linear repair."""
        rate = 44100
        t = np.linspace(0, 1.0, rate, endpoint=False)
        mono = (0.15 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
        # Inject a click at sample 5 (well inside the default 1.5 ms window
        # which is ~66 samples at 44.1 kHz).
        mono[5] = 0.95
        data = np.column_stack([mono, mono])
        result, n_clicks = remove_clicks(data, rate, peak_ratio=6.0, repair="cubic")
        assert np.all(np.isfinite(result))
        assert n_clicks >= 1

    def test_invalid_repair_raises(self):
        data, rate = _generate_click()
        with pytest.raises(ValueError, match="repair must be"):
            remove_clicks(data, rate, peak_ratio=6.0, repair="nearest")

    def test_stem_repair_differs_from_full_mix_repair_on_isolated_stem(self):
        """Per #289 acceptance: 'stem repair differs from full-mix repair
        on an isolated stem with a click.' Same signal, same detection,
        two repair strategies — they must produce distinguishable output."""
        data, rate = _generate_click(amplitude=0.5)
        stem_repaired, _ = remove_clicks(data, rate, peak_ratio=6.0, repair="cubic")
        full_repaired, _ = remove_clicks(data, rate, peak_ratio=6.0, repair="linear")
        click_idx = int(0.5 * rate)
        # Nontrivial difference in the repaired neighborhood
        assert np.max(np.abs(
            stem_repaired[click_idx - 1:click_idx + 2, 0]
            - full_repaired[click_idx - 1:click_idx + 2, 0]
        )) > 1e-6


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

    def test_reports_clicks_removed_when_given_report_dict(self):
        """`process_drums` should record how many clicks it repaired when
        a report dict is passed in."""
        data, rate = _generate_click(amplitude=0.5)
        report: dict[str, int] = {}
        settings = _get_stem_settings('drums', genre='electronic')
        result = process_drums(data, rate, settings=settings, report=report)
        assert np.all(np.isfinite(result))
        # Synthetic click with a high amplitude should always get flagged
        # by the peak_ratio=8.0 detector on the electronic preset.
        assert report.get('clicks_removed', 0) >= 1

    def test_uses_cubic_repair_when_peak_ratio_is_set(self):
        """With a `click_peak_ratio` setting, the drum processor should
        use the cubic (stem-tier) repair, not the legacy std+linear path."""
        data, rate = _generate_click(amplitude=0.5)
        # Force the ratio path by passing click_peak_ratio directly.
        settings = {
            'click_removal': True,
            'click_peak_ratio': 6.0,
            'compress_threshold_db': -12.0,
            'compress_ratio': 2.0,
            'compress_attack_ms': 5.0,
        }
        # And a sibling baseline using the legacy std path.
        baseline_settings = {
            'click_removal': True,
            'click_threshold': 6.0,
            'compress_threshold_db': -12.0,
            'compress_ratio': 2.0,
            'compress_attack_ms': 5.0,
        }
        cubic = process_drums(data.copy(), rate, settings=settings)
        linear = process_drums(data.copy(), rate, settings=baseline_settings)
        # The *full* processor chain (compressor, saturator) runs on both,
        # so we compare the early-pipeline sample neighborhood around the
        # click index — must be different because repair differs.
        click_idx = int(0.5 * rate)
        assert not np.allclose(
            cubic[click_idx - 1:click_idx + 2, 0],
            linear[click_idx - 1:click_idx + 2, 0],
            atol=1e-6,
        )


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

    def test_reports_clicks_removed_when_given_report_dict(self):
        data, rate = _generate_click(amplitude=0.5)
        report: dict[str, int] = {}
        settings = _get_stem_settings('percussion', genre='electronic')
        result = process_percussion(data, rate, settings=settings, report=report)
        assert np.all(np.isfinite(result))
        assert report.get('clicks_removed', 0) >= 1


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

    def test_result_reports_clicks_removed_per_stem(self, tmp_path):
        """mix_track_stems should surface clicks_removed on each stem that
        ran the declicker."""
        rate = 44100
        # Build a drums-stem wav with a click at t≈0.5s.
        # Offset by 50 samples so the click falls mid-window (not on a
        # 10 ms window boundary) — this prevents the click's energy from
        # being diluted across two windows, keeping peak/RMS well above 8.0.
        # Sine amplitude of 0.10 gives peak/RMS ≈ 9.9 > electronic threshold 8.0.
        t = np.linspace(0, 1.0, rate, endpoint=False)
        mono = (0.10 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
        click_idx = int(0.5 * rate) + 50  # 22100 — not on a 441-sample boundary
        mono[click_idx] = 0.95
        mono[click_idx + 1] = -0.95
        drums = np.column_stack([mono, mono])

        # And a clean vocal stem for completeness
        vocal_mono = (0.1 * np.sin(2 * np.pi * 330 * t)).astype(np.float64)
        vocals = np.column_stack([vocal_mono, vocal_mono])

        drums_path = tmp_path / "drums.wav"
        vocals_path = tmp_path / "vocals.wav"
        sf.write(str(drums_path), drums, rate, subtype='PCM_16')
        sf.write(str(vocals_path), vocals, rate, subtype='PCM_16')
        out_path = tmp_path / "out.wav"

        result = mix_track_stems(
            {'drums': str(drums_path), 'vocals': str(vocals_path)},
            out_path,
            genre='electronic',
        )

        # Each stem entry should carry clicks_removed; drums must be > 0.
        by_stem = {s['stem']: s for s in result['stems_processed']}
        assert 'clicks_removed' in by_stem['drums']
        assert by_stem['drums']['clicks_removed'] >= 1
        # Vocals don't run the declicker, so clicks_removed should be 0
        # or absent; assert the presence contract only for declicking stems.
        assert by_stem['vocals'].get('clicks_removed', 0) == 0


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
        mix_track_full(noise_wav, output_path, genre='hip-hop')
        assert Path(output_path).exists()

    def test_mono_input(self, mono_wav, output_path):
        """Mono input should produce mono output."""
        mix_track_full(mono_wav, output_path)
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

    def test_full_mix_reports_clicks_removed(self, tmp_path):
        """mix_track_full's result should include clicks_removed."""
        rate = 44100
        t = np.linspace(0, 1.0, rate, endpoint=False)
        # Quiet sine background (0.10) so the click dominates a 10ms window.
        mono = (0.10 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
        # Click mid-window (not on window boundary) at t≈0.5s + 50 samples.
        click_idx = int(0.5 * rate) + 50
        mono[click_idx] = 0.95
        mono[click_idx + 1] = -0.95
        data = np.column_stack([mono, mono])

        in_path = tmp_path / "in.wav"
        out_path = tmp_path / "out.wav"
        sf.write(str(in_path), data, rate, subtype='PCM_16')

        result = mix_track_full(in_path, out_path, genre='electronic')
        assert 'clicks_removed' in result
        # Electronic preset peak_ratio=8.0. With 0.10 background + mid-window
        # 0.95 click, ratio is ~9.9, above the threshold.
        assert isinstance(result['clicks_removed'], int)
        assert result['clicks_removed'] >= 1

    def test_full_mix_linear_repair_catches_obvious_click(self, tmp_path):
        """A big click against a quiet sine should register clicks_removed>0
        even on the legacy std-path (no genre → no peak_ratio → std default)."""
        rate = 44100
        t = np.linspace(0, 1.0, rate, endpoint=False)
        mono = (0.05 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
        click_idx = int(0.5 * rate) + 50
        mono[click_idx] = 0.9
        mono[click_idx + 1] = -0.9
        data = np.column_stack([mono, mono])

        in_path = tmp_path / "in.wav"
        out_path = tmp_path / "out.wav"
        sf.write(str(in_path), data, rate, subtype='PCM_16')

        # No genre → std path with default threshold=6.0.
        result = mix_track_full(in_path, out_path)
        assert result['clicks_removed'] >= 1


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


class TestMasterClickThresholdsThreaded:
    """Verify polish pipeline picks up click_peak_ratio / click_fail_count
    from the mastering genre preset so polish and QC stay aligned (#289)."""

    def test_stem_settings_inherit_master_click_thresholds(self):
        # 'electronic' is one of the mastering-tuned genres (ratio 8.0, fail 15)
        settings = _get_stem_settings('drums', genre='electronic')
        assert settings.get('click_peak_ratio') == 8.0
        assert settings.get('click_fail_count') == 15

    def test_full_mix_settings_inherit_master_click_thresholds(self):
        settings = _get_full_mix_settings(genre='electronic')
        assert settings.get('click_peak_ratio') == 8.0
        assert settings.get('click_fail_count') == 15

    def test_no_genre_leaves_click_thresholds_unset(self):
        settings = _get_stem_settings('drums')
        assert 'click_peak_ratio' not in settings
        assert 'click_fail_count' not in settings

    def test_unknown_genre_does_not_raise(self):
        # mix-only / user-added genre — helper must fail soft and inject
        # nothing rather than defaulting to 6.0/3.
        settings = _get_full_mix_settings(genre='totally-invented-genre')
        assert 'click_peak_ratio' not in settings
        assert 'click_fail_count' not in settings


# ─── Character Effects Tests ─────────────────────────────────────────


class TestApplySaturation:
    """Tests for apply_saturation()."""

    def test_zero_drive_passthrough(self):
        """Drive=0 returns data unchanged."""
        data, rate = _generate_sine(amplitude=0.5)
        result = apply_saturation(data, rate, drive=0.0)
        np.testing.assert_array_equal(result, data)

    def test_negative_drive_passthrough(self):
        """Negative drive returns data unchanged."""
        data, rate = _generate_sine(amplitude=0.5)
        result = apply_saturation(data, rate, drive=-0.5)
        np.testing.assert_array_equal(result, data)

    def test_saturation_changes_signal(self):
        """Non-zero drive produces a different signal."""
        data, rate = _generate_sine(amplitude=0.5)
        result = apply_saturation(data, rate, drive=0.2)
        assert not np.allclose(result, data)

    def test_saturation_preserves_shape(self):
        """Output shape matches input shape."""
        data, rate = _generate_sine(amplitude=0.5)
        result = apply_saturation(data, rate, drive=0.3)
        assert result.shape == data.shape

    def test_saturation_mono(self):
        """Saturation works on mono signals."""
        data, rate = _generate_sine(amplitude=0.5, stereo=False)
        result = apply_saturation(data, rate, drive=0.2)
        assert result.shape == data.shape
        assert not np.allclose(result, data)

    def test_saturation_adds_harmonics(self):
        """Saturation adds harmonic content (broadens spectrum)."""
        data, rate = _generate_sine(freq=440, amplitude=0.5)
        result = apply_saturation(data, rate, drive=0.3)
        # Check that spectral energy outside the fundamental increases
        fft_orig = np.abs(np.fft.rfft(data[:, 0]))
        fft_sat = np.abs(np.fft.rfft(result[:, 0]))
        # Fundamental bin
        fund_bin = int(440 * len(data) / rate)
        # Sum energy outside ±5 bins of fundamental
        mask = np.ones(len(fft_orig), dtype=bool)
        mask[max(0, fund_bin - 5):fund_bin + 6] = False
        orig_sideband = np.sum(fft_orig[mask])
        sat_sideband = np.sum(fft_sat[mask])
        assert sat_sideband > orig_sideband

    def test_saturation_drive_clamped(self):
        """Drive > 1.0 is clamped to 1.0 (no explosion)."""
        data, rate = _generate_sine(amplitude=0.8)
        result = apply_saturation(data, rate, drive=5.0)
        assert np.all(np.abs(result) <= 1.0)

    def test_higher_drive_more_effect(self):
        """Higher drive produces more deviation from original."""
        data, rate = _generate_sine(amplitude=0.5)
        low = apply_saturation(data, rate, drive=0.1)
        high = apply_saturation(data, rate, drive=0.5)
        diff_low = np.mean(np.abs(low - data))
        diff_high = np.mean(np.abs(high - data))
        assert diff_high > diff_low


class TestApplyLowpass:
    """Tests for apply_lowpass()."""

    def test_high_cutoff_passthrough(self):
        """Cutoff >= Nyquist returns data unchanged."""
        data, rate = _generate_sine(freq=440, amplitude=0.5)
        result = apply_lowpass(data, rate, cutoff=rate // 2)
        np.testing.assert_array_equal(result, data)

    def test_zero_cutoff_passthrough(self):
        """Cutoff=0 returns data unchanged (invalid, skip)."""
        data, rate = _generate_sine(freq=440, amplitude=0.5)
        result = apply_lowpass(data, rate, cutoff=0)
        np.testing.assert_array_equal(result, data)

    def test_lowpass_attenuates_highs(self):
        """Lowpass at 1000 Hz attenuates a 5000 Hz signal."""
        data, rate = _generate_sine(freq=5000, amplitude=0.5)
        result = apply_lowpass(data, rate, cutoff=1000)
        # RMS should drop significantly
        orig_rms = np.sqrt(np.mean(data ** 2))
        result_rms = np.sqrt(np.mean(result ** 2))
        assert result_rms < orig_rms * 0.5

    def test_lowpass_preserves_lows(self):
        """Lowpass at 5000 Hz preserves a 200 Hz signal."""
        data, rate = _generate_sine(freq=200, amplitude=0.5)
        result = apply_lowpass(data, rate, cutoff=5000)
        # Signal should be mostly unchanged (small filter ripple OK)
        correlation = np.corrcoef(data[:, 0], result[:, 0])[0, 1]
        assert correlation > 0.95

    def test_lowpass_preserves_shape(self):
        """Output shape matches input shape."""
        data, rate = _generate_sine(amplitude=0.5)
        result = apply_lowpass(data, rate, cutoff=8000)
        assert result.shape == data.shape

    def test_lowpass_mono(self):
        """Lowpass works on mono signals."""
        data, rate = _generate_sine(freq=5000, amplitude=0.5, stereo=False)
        result = apply_lowpass(data, rate, cutoff=1000)
        assert result.shape == data.shape
        assert np.sqrt(np.mean(result ** 2)) < np.sqrt(np.mean(data ** 2)) * 0.5


class TestApplyCharacterEffects:
    """Tests for _apply_character_effects() helper."""

    def test_no_effects_passthrough(self):
        """All effects disabled returns data unchanged."""
        data, rate = _generate_sine(amplitude=0.5)
        settings = {'saturation_drive': 0, 'lowpass_cutoff': 20000, 'stereo_width': 1.0}
        result = _apply_character_effects(data, rate, settings)
        np.testing.assert_array_equal(result, data)

    def test_saturation_flag(self):
        """saturation=True applies saturation when drive > 0."""
        data, rate = _generate_sine(amplitude=0.5)
        settings = {'saturation_drive': 0.2}
        result = _apply_character_effects(data, rate, settings, saturation=True)
        assert not np.allclose(result, data)

    def test_saturation_flag_off(self):
        """saturation=False skips saturation even with drive > 0."""
        data, rate = _generate_sine(amplitude=0.5)
        settings = {'saturation_drive': 0.2}
        result = _apply_character_effects(data, rate, settings, saturation=False)
        np.testing.assert_array_equal(result, data)

    def test_lowpass_flag(self):
        """lowpass=True applies lowpass when cutoff < 20000."""
        data, rate = _generate_sine(freq=5000, amplitude=0.5)
        settings = {'lowpass_cutoff': 1000}
        result = _apply_character_effects(data, rate, settings, lowpass=True)
        assert not np.allclose(result, data)

    def test_stereo_flag(self):
        """stereo=True applies width when stereo_width != 1.0."""
        data, rate = _generate_sine(amplitude=0.5)
        # Make left and right slightly different for stereo effect
        data[:, 1] *= 0.8
        settings = {'stereo_width': 1.3}
        result = _apply_character_effects(data, rate, settings, stereo=True)
        assert not np.allclose(result, data)

    def test_stereo_width_narrowing(self):
        """stereo_width < 1.0 narrows the stereo field."""
        data, rate = _generate_sine(amplitude=0.5)
        data[:, 1] *= 0.7  # Create stereo difference
        settings = {'stereo_width': 0.9}
        result = _apply_character_effects(data, rate, settings, stereo=True)
        # Side signal should be reduced
        orig_side = np.mean(np.abs(data[:, 0] - data[:, 1]))
        result_side = np.mean(np.abs(result[:, 0] - result[:, 1]))
        assert result_side < orig_side


class TestProcessorCharacterEffectsWiring:
    """Verify that processors apply character effects when settings are non-default."""

    def test_vocals_saturation(self):
        """Vocals applies saturation when drive > 0."""
        data, rate = _generate_sine(amplitude=0.5)
        settings_off = _get_stem_settings('vocals')
        settings_on = {**settings_off, 'saturation_drive': 0.2}
        result_off = process_vocals(data.copy(), rate, settings_off)
        result_on = process_vocals(data.copy(), rate, settings_on)
        assert not np.allclose(result_off, result_on)

    def test_vocals_lowpass(self):
        """Vocals applies lowpass when cutoff < 20000."""
        data, rate = _generate_sine(freq=5000, amplitude=0.5)
        settings_off = _get_stem_settings('vocals')
        settings_on = {**settings_off, 'lowpass_cutoff': 2000}
        result_off = process_vocals(data.copy(), rate, settings_off)
        result_on = process_vocals(data.copy(), rate, settings_on)
        assert not np.allclose(result_off, result_on)

    def test_backing_vocals_stereo_width(self):
        """Backing vocals applies stereo width."""
        data, rate = _generate_sine(amplitude=0.5)
        data[:, 1] *= 0.8
        settings = {**_get_stem_settings('backing_vocals'), 'stereo_width': 1.5}
        result_wide = process_backing_vocals(data.copy(), rate, settings)
        settings_narrow = {**settings, 'stereo_width': 1.0}
        result_narrow = process_backing_vocals(data.copy(), rate, settings_narrow)
        assert not np.allclose(result_wide, result_narrow)

    def test_drums_saturation(self):
        """Drums applies saturation when drive > 0."""
        data, rate = _generate_noise(amplitude=0.5)
        settings_off = _get_stem_settings('drums')
        settings_on = {**settings_off, 'saturation_drive': 0.15}
        result_off = process_drums(data.copy(), rate, settings_off)
        result_on = process_drums(data.copy(), rate, settings_on)
        assert not np.allclose(result_off, result_on)

    def test_guitar_all_character_effects(self):
        """Guitar applies stereo, saturation, and lowpass."""
        data, rate = _generate_sine(freq=1200, amplitude=0.5)
        data[:, 1] *= 0.9
        settings = {
            **_get_stem_settings('guitar'),
            'stereo_width': 1.2,
            'saturation_drive': 0.15,
            'lowpass_cutoff': 8000,
        }
        settings_off = {
            **_get_stem_settings('guitar'),
            'stereo_width': 1.0,
            'saturation_drive': 0,
            'lowpass_cutoff': 20000,
        }
        result_on = process_guitar(data.copy(), rate, settings)
        result_off = process_guitar(data.copy(), rate, settings_off)
        assert not np.allclose(result_on, result_off)

    def test_strings_no_saturation(self):
        """Strings does NOT apply saturation (per YAML chain)."""
        data, rate = _generate_sine(amplitude=0.5)
        settings = {**_get_stem_settings('strings'), 'saturation_drive': 0.3}
        # Both should be the same because strings doesn't wire saturation
        result = process_strings(data.copy(), rate, settings)
        settings_zero = {**settings, 'saturation_drive': 0}
        result_zero = process_strings(data.copy(), rate, settings_zero)
        np.testing.assert_array_equal(result, result_zero)

    def test_percussion_stereo_and_saturation(self):
        """Percussion applies stereo width and saturation but not lowpass."""
        data, rate = _generate_noise(amplitude=0.3)
        settings = {
            **_get_stem_settings('percussion'),
            'stereo_width': 1.2,
            'saturation_drive': 0.1,
            'lowpass_cutoff': 5000,  # should be ignored
        }
        settings_off = {
            **settings,
            'stereo_width': 1.0,
            'saturation_drive': 0,
        }
        result_on = process_percussion(data.copy(), rate, settings)
        result_off = process_percussion(data.copy(), rate, settings_off)
        assert not np.allclose(result_on, result_off)

    def test_other_lowpass_only(self):
        """Other stem applies lowpass but not saturation or stereo."""
        data, rate = _generate_sine(freq=5000, amplitude=0.3)
        settings = {**_get_stem_settings('other'), 'lowpass_cutoff': 2000}
        settings_off = {**settings, 'lowpass_cutoff': 20000}
        result_on = process_other(data.copy(), rate, settings)
        result_off = process_other(data.copy(), rate, settings_off)
        assert not np.allclose(result_on, result_off)

    def test_default_settings_unchanged_behavior(self):
        """With default settings (drive=0, cutoff=20000, width=1.0), processors behave as before."""
        data, rate = _generate_sine(amplitude=0.5)
        # Default settings have all character effects off
        settings = _get_stem_settings('vocals')
        assert settings.get('saturation_drive', 0) == 0
        assert settings.get('lowpass_cutoff', 20000) == 20000
        # Just verify it runs without error
        result = process_vocals(data.copy(), rate, settings)
        assert result.shape == data.shape


# ─── Sub-Bass Exciter Tests ──────────────────────────────────────────


class TestSubBassExciter:
    """Tests for apply_sub_bass_exciter()."""

    def test_zero_amount_passthrough(self):
        """Amount=0 returns data unchanged."""
        data, rate = _generate_sine(freq=60, amplitude=0.5)
        result = apply_sub_bass_exciter(data, rate, amount=0.0)
        np.testing.assert_array_equal(result, data)

    def test_exciter_adds_harmonics(self):
        """Exciter should add harmonic content above the crossover."""
        data, rate = _generate_sine(freq=40, amplitude=0.5)
        result = apply_sub_bass_exciter(data, rate, amount=0.5, freq=80)
        # Check for new spectral energy above 80Hz
        fft_orig = np.abs(np.fft.rfft(data[:, 0]))
        fft_exc = np.abs(np.fft.rfft(result[:, 0]))
        # Energy above crossover should increase
        crossover_bin = int(80 * len(data) / rate)
        orig_above = np.sum(fft_orig[crossover_bin:])
        exc_above = np.sum(fft_exc[crossover_bin:])
        assert exc_above > orig_above

    def test_preserves_shape(self):
        """Output shape matches input."""
        data, rate = _generate_sine(freq=60, amplitude=0.5)
        result = apply_sub_bass_exciter(data, rate, amount=0.3)
        assert result.shape == data.shape

    def test_mono_support(self):
        """Works on mono signals."""
        data, rate = _generate_sine(freq=60, amplitude=0.5, stereo=False)
        result = apply_sub_bass_exciter(data, rate, amount=0.3)
        assert result.shape == data.shape

    def test_high_freq_signal_unaffected(self):
        """Signal above crossover should be mostly unaffected."""
        data, rate = _generate_sine(freq=1000, amplitude=0.5)
        result = apply_sub_bass_exciter(data, rate, amount=0.5, freq=80)
        correlation = np.corrcoef(data[:, 0], result[:, 0])[0, 1]
        assert correlation > 0.95


class TestTransientShaper:
    """Tests for apply_transient_shaper()."""

    def test_zero_gains_passthrough(self):
        """Both gains=0 returns data unchanged."""
        data, rate = _generate_noise(amplitude=0.5)
        result = apply_transient_shaper(data, rate, attack_gain=0, sustain_gain=0)
        np.testing.assert_array_equal(result, data)

    def test_attack_boost_changes_signal(self):
        """Positive attack gain should change the signal."""
        data, rate = _generate_noise(amplitude=0.5)
        result = apply_transient_shaper(data, rate, attack_gain=6.0)
        assert not np.allclose(result, data)

    def test_sustain_boost_changes_signal(self):
        """Positive sustain gain should change the signal."""
        data, rate = _generate_noise(amplitude=0.5)
        result = apply_transient_shaper(data, rate, sustain_gain=3.0)
        assert not np.allclose(result, data)

    def test_preserves_shape(self):
        """Output shape matches input."""
        data, rate = _generate_noise(amplitude=0.5)
        result = apply_transient_shaper(data, rate, attack_gain=3.0)
        assert result.shape == data.shape

    def test_mono_support(self):
        """Works on mono signals."""
        data, rate = _generate_noise(amplitude=0.5, stereo=False)
        result = apply_transient_shaper(data, rate, attack_gain=3.0)
        assert result.shape == data.shape


class TestPhase2ProcessorWiring:
    """Verify Phase 2 effects are wired into processors."""

    def test_drums_transient_shaping(self):
        """Drums applies transient shaping when attack_db != 0."""
        data, rate = _generate_noise(amplitude=0.5)
        settings_off = {**_get_stem_settings('drums'), 'transient_attack_db': 0}
        settings_on = {**_get_stem_settings('drums'), 'transient_attack_db': 6.0}
        result_off = process_drums(data.copy(), rate, settings_off)
        result_on = process_drums(data.copy(), rate, settings_on)
        assert not np.allclose(result_off, result_on)

    def test_bass_sub_bass_exciter(self):
        """Bass applies sub-bass exciter when amount > 0."""
        data, rate = _generate_sine(freq=60, amplitude=0.5)
        settings_off = {**_get_stem_settings('bass'), 'sub_bass_exciter': 0}
        settings_on = {**_get_stem_settings('bass'), 'sub_bass_exciter': 0.3}
        result_off = process_bass(data.copy(), rate, settings_off)
        result_on = process_bass(data.copy(), rate, settings_on)
        assert not np.allclose(result_off, result_on)

    def test_percussion_transient_shaping(self):
        """Percussion applies transient shaping when attack_db != 0."""
        data, rate = _generate_noise(amplitude=0.3)
        settings_off = {**_get_stem_settings('percussion'), 'transient_attack_db': 0}
        settings_on = {**_get_stem_settings('percussion'), 'transient_attack_db': 4.0}
        result_off = process_percussion(data.copy(), rate, settings_off)
        result_on = process_percussion(data.copy(), rate, settings_on)
        assert not np.allclose(result_off, result_on)
