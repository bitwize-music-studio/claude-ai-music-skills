#!/usr/bin/env python3
"""Unit tests for Phase 1b signature metrics (STL-95, low-RMS, vocal-RMS)."""

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.analyze_tracks import analyze_track


def _write_wav(path, data, rate):
    sf.write(str(path), data, rate, subtype='PCM_16')


def _sine(freq, duration, rate, amplitude):
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


@pytest.fixture
def long_constant_wav(tmp_path):
    """60 s constant-level stereo sine at ~-14 LUFS."""
    rate = 48000
    mono = _sine(440, duration=60.0, rate=rate, amplitude=0.3)
    stereo = np.column_stack([mono, mono])
    path = tmp_path / "constant.wav"
    _write_wav(path, stereo, rate)
    return str(path)


@pytest.fixture
def chorus_verse_wav(tmp_path):
    """90 s pattern: 2 s loud chorus, 7 s medium verse — verse stays in EBU
    relative gate so integrated LUFS trends toward verse level while STL-95
    peaks on the chorus windows."""
    rate = 48000
    duration = 90.0
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    base = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    envelope = np.zeros_like(t, dtype=np.float32)
    period = 9.0
    for i in range(int(duration / period) + 1):
        loud_start = i * period
        loud_end = loud_start + 2.0
        mask = (t >= loud_start) & (t < loud_end)
        envelope[mask] = 0.7
        quiet_mask = (t >= loud_end) & (t < loud_start + period)
        envelope[quiet_mask] = 0.2
    mono = (base * envelope).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    path = tmp_path / "chorus_verse.wav"
    _write_wav(path, stereo, rate)
    return str(path)


@pytest.fixture
def short_wav(tmp_path):
    """10 s sine — too short for STL-95 (< 20 ST windows)."""
    rate = 48000
    mono = _sine(440, duration=10.0, rate=rate, amplitude=0.3)
    stereo = np.column_stack([mono, mono])
    path = tmp_path / "short.wav"
    _write_wav(path, stereo, rate)
    return str(path)


@pytest.fixture
def silent_60_wav(tmp_path):
    """60 s of silence."""
    rate = 48000
    stereo = np.zeros((int(rate * 60.0), 2), dtype=np.float32)
    path = tmp_path / "silent_60.wav"
    _write_wav(path, stereo, rate)
    return str(path)


@pytest.fixture
def bass_chorus_verse_wav(tmp_path):
    """60 s: loud bass chorus (3s, 80 Hz at -6 dBFS) + near-silent verse (5s)."""
    rate = 48000
    duration = 60.0
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    bass = np.sin(2 * np.pi * 80 * t).astype(np.float32)
    envelope = np.zeros_like(t, dtype=np.float32)
    period = 8.0
    for i in range(int(duration / period) + 1):
        loud_start = i * period
        loud_end = loud_start + 3.0
        mask = (t >= loud_start) & (t < loud_end)
        envelope[mask] = 0.5
        quiet_mask = (t >= loud_end) & (t < loud_start + period)
        envelope[quiet_mask] = 0.001
    mono = (bass * envelope).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    path = tmp_path / "bass_chorus_verse.wav"
    _write_wav(path, stereo, rate)
    return str(path)


class TestShortTerm95:
    def test_constant_level_stl_95_close_to_lufs(self, long_constant_wav):
        result = analyze_track(long_constant_wav)
        assert result['stl_95'] is not None
        assert abs(result['stl_95'] - result['lufs']) < 1.5

    def test_chorus_verse_stl_95_above_integrated(self, chorus_verse_wav):
        result = analyze_track(chorus_verse_wav)
        assert result['stl_95'] is not None
        assert result['stl_95'] > result['lufs'] + 2.0

    def test_short_track_stl_95_is_none(self, short_wav):
        result = analyze_track(short_wav)
        assert result['stl_95'] is None

    def test_silent_track_stl_95_is_none(self, silent_60_wav):
        result = analyze_track(silent_60_wav)
        assert result['stl_95'] is None


class TestLowRms:
    def test_bass_chorus_low_rms_reflects_loud_windows(self, bass_chorus_verse_wav):
        result = analyze_track(bass_chorus_verse_wav)
        assert result['low_rms'] is not None
        # Chorus at 0.5 amplitude for 80 Hz → RMS ≈ -9 dB; windowed on loud
        # choruses should report much louder than if whole-track averaged
        # with the near-silent verses.
        assert result['low_rms'] > -20.0

    def test_short_track_low_rms_is_none(self, short_wav):
        result = analyze_track(short_wav)
        assert result['low_rms'] is None

    def test_silent_track_low_rms_is_none(self, silent_60_wav):
        result = analyze_track(silent_60_wav)
        assert result['low_rms'] is None


@pytest.fixture
def full_mix_and_stem(tmp_path):
    """Full mix at -6 dBFS and a quieter vocal stem at -12 dBFS."""
    rate = 48000
    duration = 30.0
    full_mono = _sine(220, duration=duration, rate=rate, amplitude=0.5)
    stem_mono = _sine(1000, duration=duration, rate=rate, amplitude=0.25)
    full_stereo = np.column_stack([full_mono, full_mono])
    stem_stereo = np.column_stack([stem_mono, stem_mono])
    full_path = tmp_path / "track.wav"
    stem_path = tmp_path / "vocals.wav"
    _write_wav(full_path, full_stereo, rate)
    _write_wav(stem_path, stem_stereo, rate)
    return str(full_path), str(stem_path)


class TestVocalRmsStem:
    def test_explicit_stem_path_uses_stem(self, full_mix_and_stem):
        full, stem = full_mix_and_stem
        result = analyze_track(full, vocal_stem_path=stem)
        assert result['vocal_rms'] is not None
        # Stem at amplitude 0.25 → RMS = 0.25/sqrt(2) ≈ 0.177 → ~ -15 dB
        assert abs(result['vocal_rms'] - (-15.0)) < 2.0

    def test_stem_different_sample_rate_resamples(self, tmp_path):
        full_mono = _sine(220, duration=30.0, rate=48000, amplitude=0.5)
        full_stereo = np.column_stack([full_mono, full_mono])
        stem_mono = _sine(1000, duration=30.0, rate=44100, amplitude=0.25)
        stem_stereo = np.column_stack([stem_mono, stem_mono])
        full_path = tmp_path / "track.wav"
        stem_path = tmp_path / "vocals.wav"
        _write_wav(full_path, full_stereo, 48000)
        _write_wav(stem_path, stem_stereo, 44100)
        result = analyze_track(str(full_path), vocal_stem_path=str(stem_path))
        assert result['vocal_rms'] is not None
        assert abs(result['vocal_rms'] - (-15.0)) < 2.0

    def test_unreadable_stem_falls_back(self, tmp_path):
        full_mono = _sine(220, duration=30.0, rate=48000, amplitude=0.5)
        full_stereo = np.column_stack([full_mono, full_mono])
        full_path = tmp_path / "track.wav"
        _write_wav(full_path, full_stereo, 48000)
        bad_stem = tmp_path / "vocals.wav"
        bad_stem.write_bytes(b"not a wav file")
        # Unreadable stem → logged warning → band fallback applies.
        result = analyze_track(str(full_path), vocal_stem_path=str(bad_stem))
        assert result['vocal_rms'] is not None


class TestVocalRmsFallback:
    def test_no_stem_falls_back_to_band(self, tmp_path):
        rate = 48000
        duration = 30.0
        # Mid-range-heavy mix: 2 kHz sine dominates 1-4 kHz band.
        mono = _sine(2000, duration=duration, rate=rate, amplitude=0.5)
        stereo = np.column_stack([mono, mono])
        path = tmp_path / "midrange.wav"
        _write_wav(path, stereo, rate)
        result = analyze_track(str(path))
        assert result['vocal_rms'] is not None
        # 2 kHz at 0.5 amplitude → passes bandpass intact → RMS ≈ -9 dB.
        assert result['vocal_rms'] > -15.0

    def test_silent_track_vocal_rms_is_none(self, silent_60_wav):
        result = analyze_track(silent_60_wav)
        assert result['vocal_rms'] is None


class TestSignatureMeta:
    def test_meta_keys_on_full_length_track(self, long_constant_wav):
        result = analyze_track(long_constant_wav)
        assert 'signature_meta' in result
        meta = result['signature_meta']
        assert meta['stl_window_count'] >= 20
        assert meta['stl_top_5pct_count'] == max(1, int(round(0.05 * meta['stl_window_count'])))
        assert meta['vocal_rms_source'] == 'band_fallback'

    def test_meta_source_stem_when_stem_provided(self, full_mix_and_stem):
        full, stem = full_mix_and_stem
        result = analyze_track(full, vocal_stem_path=stem)
        assert result['signature_meta']['vocal_rms_source'] == 'stem'

    def test_meta_source_unavailable_on_silence(self, silent_60_wav):
        result = analyze_track(silent_60_wav)
        assert result['signature_meta']['vocal_rms_source'] == 'unavailable'
        assert result['signature_meta']['stl_top_5pct_count'] == 0


class TestAutoResolveStem:
    def _make_mix(self, path, rate=48000, duration=30.0, amplitude=0.5, freq=220):
        mono = _sine(freq, duration=duration, rate=rate, amplitude=amplitude)
        stereo = np.column_stack([mono, mono])
        _write_wav(path, stereo, rate)

    def _make_stem(self, path, rate=48000, duration=30.0, amplitude=0.25, freq=1000):
        mono = _sine(freq, duration=duration, rate=rate, amplitude=amplitude)
        stereo = np.column_stack([mono, mono])
        _write_wav(path, stereo, rate)

    def test_auto_resolve_album_root_layout(self, tmp_path):
        mix = tmp_path / "01-song.wav"
        self._make_mix(mix)
        stem_dir = tmp_path / "polished" / "01-song"
        stem_dir.mkdir(parents=True)
        stem = stem_dir / "vocals.wav"
        self._make_stem(stem)
        result = analyze_track(str(mix))
        assert result['signature_meta']['vocal_rms_source'] == 'stem'

    def test_auto_resolve_mastered_subfolder_layout(self, tmp_path):
        mastered_dir = tmp_path / "mastered"
        mastered_dir.mkdir()
        mix = mastered_dir / "01-song.wav"
        self._make_mix(mix)
        stem_dir = tmp_path / "polished" / "01-song"
        stem_dir.mkdir(parents=True)
        stem = stem_dir / "vocals.wav"
        self._make_stem(stem)
        result = analyze_track(str(mix))
        assert result['signature_meta']['vocal_rms_source'] == 'stem'

    def test_auto_resolve_miss_falls_back(self, tmp_path):
        mix = tmp_path / "01-song.wav"
        self._make_mix(mix)
        result = analyze_track(str(mix))
        assert result['signature_meta']['vocal_rms_source'] == 'band_fallback'

    def test_explicit_kwarg_overrides_auto_resolve(self, tmp_path):
        mix = tmp_path / "01-song.wav"
        self._make_mix(mix)
        auto_dir = tmp_path / "polished" / "01-song"
        auto_dir.mkdir(parents=True)
        auto_stem = auto_dir / "vocals.wav"
        self._make_stem(auto_stem, freq=500, amplitude=0.25)
        explicit_stem = tmp_path / "explicit.wav"
        self._make_stem(explicit_stem, amplitude=0.1, freq=1500)
        result = analyze_track(str(mix), vocal_stem_path=str(explicit_stem))
        assert result['signature_meta']['vocal_rms_source'] == 'stem'
        # Explicit is at amplitude 0.1 → RMS ≈ -23 dB; auto would give ≈ -15 dB.
        assert result['vocal_rms'] < -18.0
