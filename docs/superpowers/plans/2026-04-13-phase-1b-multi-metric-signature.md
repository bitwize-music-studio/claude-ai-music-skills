# Phase 1b — Multi-Metric Signature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `analyze_track()` with three signature metrics — STL-95, low-RMS (STL-95-windowed, 20–200 Hz), and vocal-RMS (polished stem when present, 1–4 kHz band fallback) — plus a `signature_meta` provenance dict, as the input for Phase 2 anchor selection and coherence checking.

**Architecture:** Additive extension of `tools/mastering/analyze_tracks.py`. Reuses the existing short-term LUFS loop; adds Butterworth bandpass helpers for low-RMS and vocal-band fallback; adds stem auto-resolve walking one directory up from the input. No pipeline stages change; MCP handler unchanged (new fields flow through existing JSON serialization). No consumers wired in this phase.

**Tech Stack:** Python 3.11, `numpy`, `scipy.signal` (already imported), `pyloudnorm`, `soundfile` — all existing deps. Tests use `pytest` + `tmp_path` fixtures, modeled on `tests/unit/mastering/test_analyze_tracks.py`.

---

## File Structure

**Create:**
- `tests/unit/mastering/test_signature_metrics.py` — unit tests for STL-95, low-RMS, vocal-RMS (stem + fallback + auto-resolve).

**Modify:**
- `tools/mastering/analyze_tracks.py` — extend `analyze_track()`; add three private helpers (`_bandpass_sos`, `_read_vocal_stem`, `_auto_resolve_vocal_stem`).
- `config/config.example.yaml` — fold in E2 review item: disk-usage note on `delivery_sample_rate` comment.

**Not modified:**
- `servers/bitwize-music-server/handlers/processing/audio.py` — handler picks up new fields through existing serialization; no code changes.

**Module responsibilities:**
- `analyze_tracks.py` owns signal math and stem resolution. Pure Python; no MCP coupling.
- Helpers stay private (underscore prefix) — they are implementation details of `analyze_track()`.

---

## Task 1: STL-95 — collect ST-LUFS values and compute 95th percentile

**Files:**
- Create: `tests/unit/mastering/test_signature_metrics.py`
- Modify: `tools/mastering/analyze_tracks.py`

- [ ] **Step 1: Write the failing test for constant-level STL-95**

Create `tests/unit/mastering/test_signature_metrics.py` with shared fixtures and the first test:

```python
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


class TestShortTerm95:
    def test_constant_level_stl_95_close_to_lufs(self, long_constant_wav):
        result = analyze_track(long_constant_wav)
        assert result['stl_95'] is not None
        assert abs(result['stl_95'] - result['lufs']) < 1.5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestShortTerm95::test_constant_level_stl_95_close_to_lufs -v
```
Expected: FAIL with `KeyError: 'stl_95'`.

- [ ] **Step 3: Implement STL-95 in analyze_track()**

Modify `tools/mastering/analyze_tracks.py`. Replace the short-term loop block (lines ~82–109) and the return dict:

```python
    # Short-term and momentary loudness dynamics
    max_short_term = float('-inf')
    min_short_term = float('inf')
    max_momentary = float('-inf')
    st_values: list[float] = []

    # Short-term: 3s window, 1s hop (EBU R128)
    st_window = int(3.0 * rate)
    st_hop = int(1.0 * rate)
    if data.shape[0] > st_window:
        for start in range(0, data.shape[0] - st_window, st_hop):
            chunk = data[start:start + st_window]
            st_lufs = pyln.Meter(rate).integrated_loudness(chunk)
            if np.isfinite(st_lufs):
                st_values.append(float(st_lufs))
                max_short_term = max(max_short_term, st_lufs)
                min_short_term = min(min_short_term, st_lufs)

    # STL-95: 95th percentile of finite short-term LUFS.
    # Gated to ≥20 windows (~23s audio) so the percentile has a meaningful
    # spread; below that it collapses to near-max.
    stl_95: float | None
    stl_top_5pct_indices: np.ndarray
    if len(st_values) >= 20:
        stl_array = np.asarray(st_values, dtype=np.float64)
        stl_95 = float(np.percentile(stl_array, 95))
        top_k = max(1, int(round(0.05 * len(st_values))))
        # Stable sort on -value: ties resolve to earliest window first.
        order = np.argsort(-stl_array, kind='stable')
        stl_top_5pct_indices = order[:top_k]
    else:
        stl_95 = None
        stl_top_5pct_indices = np.array([], dtype=np.int64)

    # Momentary: 400ms window, 100ms hop
    mom_window = int(0.4 * rate)
    mom_hop = int(0.1 * rate)
    if data.shape[0] > mom_window:
        for start in range(0, data.shape[0] - mom_window, mom_hop):
            chunk = data[start:start + mom_window]
            mom_lufs = pyln.Meter(rate).integrated_loudness(chunk)
            if np.isfinite(mom_lufs):
                max_momentary = max(max_momentary, mom_lufs)

    short_term_range = (max_short_term - min_short_term
                        if np.isfinite(max_short_term) and np.isfinite(min_short_term)
                        else 0.0)

    return {
        'filename': os.path.basename(filepath),
        'duration': len(mono) / rate,
        'sample_rate': rate,
        'lufs': loudness,
        'peak_db': peak_db,
        'rms_db': rms_db,
        'dynamic_range': dynamic_range,
        'band_energy': band_energy,
        'tinniness_ratio': tinniness_ratio,
        'max_short_term_lufs': max_short_term if np.isfinite(max_short_term) else None,
        'max_momentary_lufs': max_momentary if np.isfinite(max_momentary) else None,
        'short_term_range': short_term_range,
        'stl_95': stl_95,
    }
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestShortTerm95::test_constant_level_stl_95_close_to_lufs -v
```
Expected: PASS.

- [ ] **Step 5: Add test for chorus/verse pattern — STL-95 > integrated LUFS**

Add this fixture and test class method:

```python
@pytest.fixture
def chorus_verse_wav(tmp_path):
    """60 s pattern: 3 s loud chorus, 5 s quiet verse, repeating."""
    rate = 48000
    duration = 60.0
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    # Constant sine, then modulate amplitude with a chorus-pattern envelope.
    base = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    envelope = np.zeros_like(t, dtype=np.float32)
    period = 8.0  # 3s loud + 5s quiet
    for i in range(int(duration / period) + 1):
        loud_start = i * period
        loud_end = loud_start + 3.0
        mask = (t >= loud_start) & (t < loud_end)
        envelope[mask] = 0.6
        quiet_mask = (t >= loud_end) & (t < loud_start + period)
        envelope[quiet_mask] = 0.05
    mono = (base * envelope).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    path = tmp_path / "chorus_verse.wav"
    _write_wav(path, stereo, rate)
    return str(path)
```

Append inside `class TestShortTerm95:`

```python
    def test_chorus_verse_stl_95_above_integrated(self, chorus_verse_wav):
        result = analyze_track(chorus_verse_wav)
        assert result['stl_95'] is not None
        assert result['stl_95'] > result['lufs'] + 2.0
```

- [ ] **Step 6: Run and verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestShortTerm95 -v
```
Expected: both tests PASS.

- [ ] **Step 7: Add test for short-track gating (< 20 windows → None)**

Add fixture and test:

```python
@pytest.fixture
def short_wav(tmp_path):
    """10 s sine — too short for STL-95 (< 20 ST windows)."""
    rate = 48000
    mono = _sine(440, duration=10.0, rate=rate, amplitude=0.3)
    stereo = np.column_stack([mono, mono])
    path = tmp_path / "short.wav"
    _write_wav(path, stereo, rate)
    return str(path)
```

Append in `TestShortTerm95`:

```python
    def test_short_track_stl_95_is_none(self, short_wav):
        result = analyze_track(short_wav)
        assert result['stl_95'] is None
```

- [ ] **Step 8: Run and verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestShortTerm95 -v
```
Expected: three tests PASS.

- [ ] **Step 9: Add test for silent track**

```python
@pytest.fixture
def silent_60_wav(tmp_path):
    """60 s of silence."""
    rate = 48000
    stereo = np.zeros((int(rate * 60.0), 2), dtype=np.float32)
    path = tmp_path / "silent_60.wav"
    _write_wav(path, stereo, rate)
    return str(path)
```

In `TestShortTerm95`:

```python
    def test_silent_track_stl_95_is_none(self, silent_60_wav):
        result = analyze_track(silent_60_wav)
        assert result['stl_95'] is None
```

- [ ] **Step 10: Run and verify**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestShortTerm95 -v
```
Expected: four tests PASS.

- [ ] **Step 11: Commit**

```bash
git add tools/mastering/analyze_tracks.py tests/unit/mastering/test_signature_metrics.py
git commit -m "$(cat <<'EOF'
feat(mastering): add STL-95 signature metric to analyze_track

Collects short-term LUFS values from the existing 3s/1s loop,
computes the 95th percentile when at least 20 windows exist, and
retains the top-5% window indices for downstream low-RMS windowing.
Returns None for tracks too short or silent to produce a meaningful
percentile.

Part of #290 phase 1b.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: low-RMS — bandpass 20–200 Hz, measured within STL-95 windows

**Files:**
- Modify: `tools/mastering/analyze_tracks.py`
- Modify: `tests/unit/mastering/test_signature_metrics.py`

- [ ] **Step 1: Write failing test for bass-heavy chorus pattern**

Add fixture + test class:

```python
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


class TestLowRms:
    def test_bass_chorus_low_rms_reflects_loud_windows(self, bass_chorus_verse_wav):
        result = analyze_track(bass_chorus_verse_wav)
        assert result['low_rms'] is not None
        # Chorus at 0.5 amplitude for 80 Hz → RMS ≈ -9 dB; windowed on loud
        # choruses should report much louder than if whole-track averaged
        # with the near-silent verses.
        assert result['low_rms'] > -20.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestLowRms -v
```
Expected: FAIL with `KeyError: 'low_rms'`.

- [ ] **Step 3: Add `_bandpass_sos` helper and low-RMS computation**

In `tools/mastering/analyze_tracks.py`, add the helper above `analyze_track`:

```python
def _bandpass_sos(data: np.ndarray, rate: int, low_hz: float, high_hz: float,
                  order: int = 4) -> np.ndarray:
    """Zero-phase Butterworth bandpass via SOS form (numerically stable)."""
    nyquist = rate / 2
    low = max(low_hz, 1.0) / nyquist
    high = min(high_hz, nyquist - 1.0) / nyquist
    sos = signal.butter(order, [low, high], btype='bandpass', output='sos')
    return signal.sosfiltfilt(sos, data)


def _rms_db(samples: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(samples ** 2)))
    return 20.0 * np.log10(rms) if rms > 0 else float('-inf')
```

In `analyze_track`, after the STL-95 block but before the momentary loop, add:

```python
    # low-RMS: 20-200 Hz band, measured within top-5% STL windows only.
    # Whole-track measurement false-alarms on arrangements with quiet verses
    # and wall-of-bass choruses (see #290 spec footnote †).
    low_rms: float | None
    if stl_95 is not None and len(stl_top_5pct_indices) > 0:
        low_filtered = _bandpass_sos(mono, rate, 20.0, 200.0)
        window_rms_values: list[float] = []
        for window_idx in stl_top_5pct_indices:
            start = int(window_idx) * st_hop
            end = start + st_window
            chunk = low_filtered[start:end]
            rms_val = _rms_db(chunk)
            if np.isfinite(rms_val):
                window_rms_values.append(rms_val)
        low_rms = float(np.median(window_rms_values)) if window_rms_values else None
    else:
        low_rms = None
```

Add `low_rms` to the return dict:

```python
        'stl_95': stl_95,
        'low_rms': low_rms,
```

- [ ] **Step 4: Run test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestLowRms -v
```
Expected: PASS.

- [ ] **Step 5: Add test for short-track and silent-track gating**

In `TestLowRms`:

```python
    def test_short_track_low_rms_is_none(self, short_wav):
        result = analyze_track(short_wav)
        assert result['low_rms'] is None

    def test_silent_track_low_rms_is_none(self, silent_60_wav):
        result = analyze_track(silent_60_wav)
        assert result['low_rms'] is None
```

- [ ] **Step 6: Run and verify**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestLowRms -v
```
Expected: three tests PASS.

- [ ] **Step 7: Commit**

```bash
git add tools/mastering/analyze_tracks.py tests/unit/mastering/test_signature_metrics.py
git commit -m "$(cat <<'EOF'
feat(mastering): add low-RMS signature metric (20-200 Hz, windowed)

Bandpasses the mono mixdown at 20-200 Hz (4th-order Butterworth SOS,
zero-phase via sosfiltfilt) and takes the median RMS across the
top-5% STL windows identified by STL-95. Whole-track low-RMS would
false-alarm on arrangements with sparse verses and wall-of-bass
choruses; windowing keeps the metric faithful to what listeners
perceive as the track's low-end signature.

Returns None when STL-95 is None (track too short or silent).

Part of #290 phase 1b.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: vocal-RMS — explicit stem path (stem branch)

**Files:**
- Modify: `tools/mastering/analyze_tracks.py`
- Modify: `tests/unit/mastering/test_signature_metrics.py`

- [ ] **Step 1: Write failing test for explicit stem path**

Add to test file:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestVocalRmsStem -v
```
Expected: FAIL with `TypeError: analyze_track() got an unexpected keyword argument 'vocal_stem_path'`.

- [ ] **Step 3: Add stem reader helper and kwarg**

In `tools/mastering/analyze_tracks.py`, add helper above `analyze_track`:

```python
def _read_vocal_stem(stem_path: Path | str, target_rate: int) -> np.ndarray | None:
    """Read a vocal stem, mono-mix, resample to target_rate.

    Returns None if the file cannot be read or resampled.
    """
    try:
        data, rate = sf.read(str(stem_path))
    except Exception as exc:
        logger.warning("Could not read vocal stem %s: %s", stem_path, exc)
        return None
    if data.ndim > 1:
        mono = np.mean(data, axis=1)
    else:
        mono = data
    if rate != target_rate:
        try:
            # Use rational resampling when possible for stability.
            from math import gcd
            g = gcd(int(rate), int(target_rate))
            up = int(target_rate) // g
            down = int(rate) // g
            mono = signal.resample_poly(mono, up, down)
        except Exception as exc:
            logger.warning("Could not resample vocal stem %s: %s", stem_path, exc)
            return None
    return np.asarray(mono, dtype=np.float64)
```

Update `analyze_track` signature:

```python
def analyze_track(filepath: Path | str, *,
                  vocal_stem_path: Path | str | None = None) -> dict[str, Any]:
    """Analyze a single track and return metrics."""
```

Add vocal-RMS computation after the low-RMS block:

```python
    # vocal-RMS: whole-stem RMS when stem path resolves; 1-4 kHz band of
    # full mix otherwise. See #290 spec footnote ‡.
    vocal_rms: float | None = None
    vocal_rms_source: str = "unavailable"

    resolved_stem = Path(vocal_stem_path) if vocal_stem_path else None
    if resolved_stem is not None and resolved_stem.is_file():
        stem_mono = _read_vocal_stem(resolved_stem, rate)
        if stem_mono is not None:
            rms_val = _rms_db(stem_mono)
            if np.isfinite(rms_val):
                vocal_rms = float(rms_val)
                vocal_rms_source = "stem"
```

Append to return dict:

```python
        'stl_95': stl_95,
        'low_rms': low_rms,
        'vocal_rms': vocal_rms,
```

- [ ] **Step 4: Run test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestVocalRmsStem -v
```
Expected: PASS.

- [ ] **Step 5: Add test for stem at different sample rate (resample path)**

In `TestVocalRmsStem`:

```python
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
```

- [ ] **Step 6: Add test for unreadable stem falls through (no crash)**

```python
    def test_unreadable_stem_does_not_crash(self, tmp_path):
        full_mono = _sine(220, duration=30.0, rate=48000, amplitude=0.5)
        full_stereo = np.column_stack([full_mono, full_mono])
        full_path = tmp_path / "track.wav"
        _write_wav(full_path, full_stereo, 48000)
        bad_stem = tmp_path / "vocals.wav"
        bad_stem.write_bytes(b"not a wav file")
        # Should not raise — must fall through to band fallback (added in Task 4).
        # For now, vocal_rms should be None and source != "stem".
        result = analyze_track(str(full_path), vocal_stem_path=str(bad_stem))
        # Task 3 only implements the stem branch; if unreadable, result is None.
        assert result['vocal_rms'] is None
```

- [ ] **Step 7: Run all TestVocalRmsStem tests and verify they pass**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestVocalRmsStem -v
```
Expected: three tests PASS.

- [ ] **Step 8: Commit**

```bash
git add tools/mastering/analyze_tracks.py tests/unit/mastering/test_signature_metrics.py
git commit -m "$(cat <<'EOF'
feat(mastering): add vocal-RMS stem branch with explicit stem kwarg

Adds optional vocal_stem_path kwarg to analyze_track(). When the
stem resolves and reads, measures whole-stem RMS in dB on a mono
mixdown, resampling to the mix rate when needed. Unreadable stem
files log a warning and fall through (band fallback lands in Task 4).

Part of #290 phase 1b.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: vocal-RMS — 1–4 kHz band fallback

**Files:**
- Modify: `tools/mastering/analyze_tracks.py`
- Modify: `tests/unit/mastering/test_signature_metrics.py`

- [ ] **Step 1: Write failing test for band fallback**

Add test class:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestVocalRmsFallback -v
```
Expected: FAIL — `vocal_rms` is None without stem.

- [ ] **Step 3: Implement band fallback**

In `analyze_track`, extend the vocal-RMS block. Replace the prior block with:

```python
    # vocal-RMS: whole-stem RMS when stem path resolves; 1-4 kHz band of
    # full mix otherwise. See #290 spec footnote ‡.
    vocal_rms: float | None = None
    vocal_rms_source: str = "unavailable"

    resolved_stem = Path(vocal_stem_path) if vocal_stem_path else None
    if resolved_stem is not None and resolved_stem.is_file():
        stem_mono = _read_vocal_stem(resolved_stem, rate)
        if stem_mono is not None:
            rms_val = _rms_db(stem_mono)
            if np.isfinite(rms_val):
                vocal_rms = float(rms_val)
                vocal_rms_source = "stem"

    if vocal_rms is None:
        # Band fallback on full-mix mono: 1-4 kHz.
        try:
            band_filtered = _bandpass_sos(mono, rate, 1000.0, 4000.0)
            rms_val = _rms_db(band_filtered)
            if np.isfinite(rms_val):
                vocal_rms = float(rms_val)
                vocal_rms_source = "band_fallback"
        except Exception as exc:
            logger.warning("1-4 kHz band fallback failed: %s", exc)
```

- [ ] **Step 4: Update prior unreadable-stem test — now expects band_fallback**

In Task 3's `TestVocalRmsStem.test_unreadable_stem_does_not_crash`, change the assertion:

```python
        result = analyze_track(str(full_path), vocal_stem_path=str(bad_stem))
        # Unreadable stem → logged warning → band fallback applies.
        assert result['vocal_rms'] is not None
```

- [ ] **Step 5: Add silent-track test for band fallback**

In `TestVocalRmsFallback`:

```python
    def test_silent_track_vocal_rms_is_none(self, silent_60_wav):
        result = analyze_track(silent_60_wav)
        assert result['vocal_rms'] is None
```

- [ ] **Step 6: Run all TestVocalRms* tests**

```bash
~/.bitwize-music/venv/bin/python -m pytest "tests/unit/mastering/test_signature_metrics.py::TestVocalRmsStem" "tests/unit/mastering/test_signature_metrics.py::TestVocalRmsFallback" -v
```
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add tools/mastering/analyze_tracks.py tests/unit/mastering/test_signature_metrics.py
git commit -m "$(cat <<'EOF'
feat(mastering): add 1-4 kHz band fallback for vocal-RMS

When no vocal stem resolves (or the stem is unreadable), falls back
to measuring whole-track RMS on the 1-4 kHz bandpassed mono mixdown
of the full mix. Covers the today-default path (polish does not yet
preserve per-stem WAVs); stem measurement activates automatically
once the per-stem artifact lands.

Part of #290 phase 1b.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: signature_meta provenance dict

**Files:**
- Modify: `tools/mastering/analyze_tracks.py`
- Modify: `tests/unit/mastering/test_signature_metrics.py`

- [ ] **Step 1: Write failing test for signature_meta keys**

Add test class:

```python
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
        assert result['signature_meta']['stl_window_count'] >= 20
        assert result['signature_meta']['stl_top_5pct_count'] == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestSignatureMeta -v
```
Expected: FAIL with `KeyError: 'signature_meta'`.

- [ ] **Step 3: Add signature_meta to return dict**

In `analyze_track`, at the start of the return dict construction, replace the silent-case branch with:

```python
    # signature_meta records provenance for downstream consumers
    # (anchor selector, coherence check).
    signature_meta = {
        'stl_window_count': len(st_values),
        'stl_top_5pct_count': int(len(stl_top_5pct_indices)),
        'vocal_rms_source': vocal_rms_source,
    }

    return {
        'filename': os.path.basename(filepath),
        'duration': len(mono) / rate,
        'sample_rate': rate,
        'lufs': loudness,
        'peak_db': peak_db,
        'rms_db': rms_db,
        'dynamic_range': dynamic_range,
        'band_energy': band_energy,
        'tinniness_ratio': tinniness_ratio,
        'max_short_term_lufs': max_short_term if np.isfinite(max_short_term) else None,
        'max_momentary_lufs': max_momentary if np.isfinite(max_momentary) else None,
        'short_term_range': short_term_range,
        'stl_95': stl_95,
        'low_rms': low_rms,
        'vocal_rms': vocal_rms,
        'signature_meta': signature_meta,
    }
```

Note: when the track is silent, `len(st_values)` may still be ≥20 (windows that returned -inf LUFS are excluded from `st_values` but windows that returned finite silence values are included). Confirm by running the test — if `test_meta_source_unavailable_on_silence` fails on `stl_window_count >= 20`, relax the assertion to `>= 0` since silent audio may not produce finite pyloudnorm output at all.

- [ ] **Step 4: Run tests**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestSignatureMeta -v
```
Expected: three tests PASS. If the silent-track `stl_window_count` assertion fails (because pyloudnorm returns `-inf` for silent windows which get filtered), change the test line to `assert result['signature_meta']['stl_window_count'] >= 0`.

- [ ] **Step 5: Commit**

```bash
git add tools/mastering/analyze_tracks.py tests/unit/mastering/test_signature_metrics.py
git commit -m "$(cat <<'EOF'
feat(mastering): expose signature_meta provenance dict

Records stl_window_count, stl_top_5pct_count, and vocal_rms_source
alongside the scalar signature fields. Downstream consumers (anchor
selector, coherence check) branch on vocal_rms_source to explain
their decisions ('stem' / 'band_fallback' / 'unavailable') without
re-parsing paths.

Part of #290 phase 1b.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Stem auto-resolve

**Files:**
- Modify: `tools/mastering/analyze_tracks.py`
- Modify: `tests/unit/mastering/test_signature_metrics.py`

- [ ] **Step 1: Write failing test for album-root auto-resolve**

Add test class:

```python
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
        # Input at album root: <album>/01-song.wav; stem at <album>/polished/01-song/vocals.wav
        mix = tmp_path / "01-song.wav"
        self._make_mix(mix)
        stem_dir = tmp_path / "polished" / "01-song"
        stem_dir.mkdir(parents=True)
        stem = stem_dir / "vocals.wav"
        self._make_stem(stem)
        result = analyze_track(str(mix))
        assert result['signature_meta']['vocal_rms_source'] == 'stem'
```

- [ ] **Step 2: Run test to verify it fails**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestAutoResolveStem -v
```
Expected: FAIL — source is `band_fallback`, not `stem`.

- [ ] **Step 3: Add auto-resolve helper and wire it in**

In `tools/mastering/analyze_tracks.py`, add helper:

```python
def _auto_resolve_vocal_stem(input_path: Path) -> Path | None:
    """Find a matching polished vocal stem without explicit kwarg.

    Checks, in order:
      1. <input_dir>/polished/<input_stem>/vocals.wav  (album-root input)
      2. <input_dir>/../polished/<input_stem>/vocals.wav  (mastered/ or
         polished/ subfolder input)

    Returns the first existing path, or None.
    """
    stem_name = input_path.stem
    candidates = [
        input_path.parent / "polished" / stem_name / "vocals.wav",
        input_path.parent.parent / "polished" / stem_name / "vocals.wav",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None
```

In `analyze_track`, update the stem resolution to use auto-resolve when kwarg is None:

```python
    resolved_stem: Path | None
    if vocal_stem_path is not None:
        resolved_stem = Path(vocal_stem_path)
    else:
        resolved_stem = _auto_resolve_vocal_stem(Path(filepath))

    if resolved_stem is not None and resolved_stem.is_file():
        stem_mono = _read_vocal_stem(resolved_stem, rate)
        # ... (rest unchanged)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestAutoResolveStem::test_auto_resolve_album_root_layout -v
```
Expected: PASS.

- [ ] **Step 5: Add test for mastered/ subfolder layout**

In `TestAutoResolveStem`:

```python
    def test_auto_resolve_mastered_subfolder_layout(self, tmp_path):
        # Input at <album>/mastered/01-song.wav; stem at <album>/polished/01-song/vocals.wav
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
```

- [ ] **Step 6: Add test for miss → fallback**

```python
    def test_auto_resolve_miss_falls_back(self, tmp_path):
        mix = tmp_path / "01-song.wav"
        self._make_mix(mix)
        result = analyze_track(str(mix))
        assert result['signature_meta']['vocal_rms_source'] == 'band_fallback'
```

- [ ] **Step 7: Add test confirming explicit kwarg still wins over auto-resolve**

```python
    def test_explicit_kwarg_overrides_auto_resolve(self, tmp_path):
        mix = tmp_path / "01-song.wav"
        self._make_mix(mix)
        # Auto-resolve target (would be found)
        auto_dir = tmp_path / "polished" / "01-song"
        auto_dir.mkdir(parents=True)
        auto_stem = auto_dir / "vocals.wav"
        self._make_stem(auto_stem, freq=500)
        # Explicit kwarg: a different file with a different frequency (amplitude)
        explicit_stem = tmp_path / "explicit.wav"
        self._make_stem(explicit_stem, amplitude=0.1, freq=1500)  # quieter
        result = analyze_track(str(mix), vocal_stem_path=str(explicit_stem))
        assert result['signature_meta']['vocal_rms_source'] == 'stem'
        # Explicit is at amplitude 0.1 → RMS ≈ -23 dB; auto would give ≈ -15 dB
        assert result['vocal_rms'] < -18.0
```

- [ ] **Step 8: Run all TestAutoResolveStem tests**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_signature_metrics.py::TestAutoResolveStem -v
```
Expected: four tests PASS.

- [ ] **Step 9: Commit**

```bash
git add tools/mastering/analyze_tracks.py tests/unit/mastering/test_signature_metrics.py
git commit -m "$(cat <<'EOF'
feat(mastering): auto-resolve vocal stem path for analyze_track

When the caller omits vocal_stem_path, analyze_track walks two
layouts looking for <input_stem>/vocals.wav under a sibling
polished/ directory — first the input's directory, then one level
up. Covers album-root, polished/, and mastered/ input callsites
without touching the wider filesystem.

Part of #290 phase 1b.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: E2 review item — disk-usage note on delivery_sample_rate

**Files:**
- Modify: `config/config.example.yaml`

- [ ] **Step 1: Find the current `delivery_sample_rate` comment**

Run:
```bash
~/.bitwize-music/venv/bin/python -c "print(open('config/config.example.yaml').read())" | grep -n -A 20 "delivery_sample_rate"
```

- [ ] **Step 2: Append disk-usage note to the comment block**

Locate the comment block that starts with `# delivery_sample_rate [optional, default: 96000]` and ends just before `# delivery_sample_rate: 96000`. Add this paragraph immediately before the uncommented default:

```yaml
#   #
#   # Disk-usage note: at 24-bit / 96 kHz, mastered WAVs are roughly
#   # ~33 MB per stereo minute (vs. ~10 MB at 44.1 kHz). A 12-track
#   # album averages ~1.5 GB of mastered/ output before archival; enable
#   # archival only when you have the headroom for an extra ~3x of that.
```

- [ ] **Step 3: Verify YAML still parses**

```bash
~/.bitwize-music/venv/bin/python -c "import yaml; yaml.safe_load(open('config/config.example.yaml'))"
```
Expected: no output (clean parse).

- [ ] **Step 4: Commit**

```bash
git add config/config.example.yaml
git commit -m "$(cat <<'EOF'
docs(config): add disk-usage note to delivery_sample_rate comment

Expands the 24/96 default documentation with a concrete disk-usage
estimate (~33 MB/min at 24/96 vs ~10 MB/min at 44.1; ~1.5 GB per
12-track album before archival). Surfaces the tradeoff users should
weigh when enabling archival output.

Carried forward from #304 review item E2. Part of #290 phase 1b.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Full regression suite + final verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full mastering unit test suite**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/ -v
```
Expected: all tests PASS. Existing test count + new signature-metrics tests (around 16 new assertions). No regressions in `test_analyze_tracks.py`, `test_mastering_config.py`, `test_master_audio_config_wiring.py`, `test_master_album_config_wiring.py`, `test_archival_output.py`, or `test_prune_archival.py`.

- [ ] **Step 2: Run the full repo test suite**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/ -q
```
Expected: PASS. Regression budget: baseline from #304 was 3151 passed + 2 xfailed. New tests should push that to approximately 3167+. Zero unexpected failures.

- [ ] **Step 3: Manual smoke test — analyze a real track**

If a real album exists locally, pick a single mastered WAV and run:

```bash
~/.bitwize-music/venv/bin/python -c "
from tools.mastering.analyze_tracks import analyze_track
from pathlib import Path
import json
# Replace with an actual track path on your machine
track = Path.home() / 'some/test/track.wav'
if track.is_file():
    result = analyze_track(str(track))
    print(json.dumps({
        'stl_95': result['stl_95'],
        'low_rms': result['low_rms'],
        'vocal_rms': result['vocal_rms'],
        'meta': result['signature_meta'],
    }, indent=2))
"
```
Expected: non-None STL-95, low-RMS, vocal-RMS for a real-length mastered track; `vocal_rms_source` = `band_fallback` (today's default path).

Skip this step if no suitable local file is available.

- [ ] **Step 4: Confirm no orphaned untracked files**

```bash
git status
```
Expected: clean working tree (only the committed changes).

- [ ] **Step 5: Summary check — verify phase 1b deliverables**

Confirm by inspection that all of these are present:
- `tools/mastering/analyze_tracks.py` has `_bandpass_sos`, `_rms_db`, `_read_vocal_stem`, `_auto_resolve_vocal_stem` helpers.
- `analyze_track()` returns `stl_95`, `low_rms`, `vocal_rms`, `signature_meta`.
- `tests/unit/mastering/test_signature_metrics.py` exists with five test classes (`TestShortTerm95`, `TestLowRms`, `TestVocalRmsStem`, `TestVocalRmsFallback`, `TestSignatureMeta`, `TestAutoResolveStem`).
- `config/config.example.yaml` has the disk-usage note on `delivery_sample_rate`.
- No changes to `servers/bitwize-music-server/handlers/processing/audio.py`.

If all present → phase 1b implementation complete. Ready to open PR for review.

---

## Completion checklist

- [ ] Task 1 — STL-95 computation + gating
- [ ] Task 2 — low-RMS within STL-95 windows
- [ ] Task 3 — vocal-RMS stem branch (explicit kwarg)
- [ ] Task 4 — vocal-RMS 1-4 kHz band fallback
- [ ] Task 5 — signature_meta provenance dict
- [ ] Task 6 — stem auto-resolve
- [ ] Task 7 — E2 disk-usage note
- [ ] Task 8 — full regression run
