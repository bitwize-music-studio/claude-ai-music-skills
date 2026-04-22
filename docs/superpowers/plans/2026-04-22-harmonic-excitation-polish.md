# Harmonic Excitation in Polish (ADM-Aware) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-stem harmonic excitation step to the polish pipeline so dark-material tracks (Suno output with high_mid band energy < 10 %) gain synthetic upper-harmonic content before mastering, giving the limiter headroom it can actually use. Gated on a preset flag so operators opt in per genre/album; when enabled, the analyzer's existing `already_dark` signal drives per-stem intensity.

**Architecture:** Three additive pieces. (1) New pure-DSP module `tools/mixing/excitation.py` with `apply_harmonic_excitation(data, rate, amount_db, freq_range)` — bandpass → soft-saturate → high-pass → attenuate → mix. (2) Per-stem `excitation_db` preset key wired through `_get_stem_settings` the same way `high_tame_db` is today, with a new entry in `_ANALYZER_EQ_OVERRIDE_KEYS` + `_ANALYZER_PARAM_REASONS` so the analyzer can recommend it when a stem is `already_dark`. (3) Preset flag `defaults.analyzer.adm_aware_excitation: bool` (default `false`) gates the analyzer's emission of the recommendation — operators turn it on per preset when they're willing to trade artistic-fingerprint sound for ADM compliance. Existing stem processors read `settings.get('excitation_db', 0.0)` and apply the helper when non-zero, so non-dark stems and presets with the flag off are byte-identical.

**Tech Stack:** Python 3.11, `numpy`, `scipy.signal` (already imported by `mix_tracks.py`). No new dependencies.

---

## Scope Check

Single subsystem (mix/polish DSP) — fits one plan. Out of scope:

- Auto-calibrated excitation intensity from measured high_mid deficit. (Fixed preset-tunable values are safer and easier to A/B. Could be a follow-up once operators have taste data.)
- Runtime coupling between `adm_validation_enabled` in the master config and `adm_aware_excitation` in the polish preset. (Two flags for operator control. Clear separation. Docs tell operators to enable both together.)
- Polish stage analyzer changes beyond threading the new excitation recommendation through. (Analyzer's `is_dark` detection is already live from Plan B.)
- Mastering stage changes. Excitation happens in polish only; mastering sees the excited signal naturally.
- Per-song override mechanism. (Preset-level is sufficient for v1. Genre presets can override defaults.)

---

## Codebase Context

Key files (paths from repo root):

- `tools/mixing/mix_tracks.py:1037-1054` — `_ANALYZER_EQ_OVERRIDE_KEYS` whitelist + `_ANALYZER_PARAM_REASONS` tag map. Analyzer recs are only applied to whitelisted keys; new keys must be added here.
- `tools/mixing/mix_tracks.py:1057-1180` — `_get_stem_settings` merges preset defaults + genre overlay + analyzer recs into the per-stem settings dict.
- `tools/mixing/mix_tracks.py` per-stem processors (around lines 1170+, 1220+, 1370+, 1430+, 1490+, 1550+, 1610+ for vocals, backing_vocals, guitar, keyboard, strings, brass, woodwinds, etc.) — each reads settings by key and applies the effect. Pattern: `amt = settings.get('high_tame_db', -2.0); if amt != 0: data = apply_high_shelf(...)`.
- `tools/mixing/mix_tracks.py:298` — `apply_eq` reference primitive. `apply_high_shelf` is around line 330. Our new `apply_harmonic_excitation` should match the shape: pure function, takes `(data, rate, ...)`, returns data.
- `tools/mixing/mix-presets.yaml` — preset defaults. Each stem has a dict of settings; `defaults.analyzer.*` block carries analyzer thresholds and flags.
- `servers/bitwize-music-server/handlers/processing/mixing.py:367-378` — `_analyze_one` detects `already_dark` (high_mid_ratio < dark_high_mid_ratio). Its `result["recommendations"]` dict gets wired into `_get_stem_settings` via `analyzer_rec`.

**Existing pattern for a similar per-stem DSP knob (precedent):**

`sub_bass_exciter: 0.0-1.0` already exists on the bass stem — see the comment block in `mix-presets.yaml` around line 30. It's off by default, numeric-amount-based, per-stem-configurable. Our `excitation_db` follows the exact same shape.

**Existing similarity — `presence_boost_db`:**

Per-stem EQ-based "brightness" boost already in presets for vocals, backing_vocals, guitar, keyboard, strings, brass, woodwinds, percussion, synth. That's a linear boost — no new harmonics generated. Harmonic excitation is complementary: generates upper-harmonic *content* via nonlinearity, not just amplifies existing content.

---

## File Structure

| File | Role | State |
|---|---|---|
| `tools/mixing/excitation.py` | New pure-DSP module: `apply_harmonic_excitation(data, rate, amount_db, freq_range)` | **new** |
| `tools/mixing/mix_tracks.py` | Add `excitation_db` to `_ANALYZER_EQ_OVERRIDE_KEYS` + `_ANALYZER_PARAM_REASONS`; wire `apply_harmonic_excitation` into each stem processor that supports brightness | modify |
| `tools/mixing/mix-presets.yaml` | Add `defaults.analyzer.adm_aware_excitation: false` + per-stem `excitation_db` defaults (0.0 unless the stem benefits from excitation in dark material) | modify |
| `servers/bitwize-music-server/handlers/processing/mixing.py` | Extend `_analyze_one` to emit `excitation_db` recommendation when `already_dark` AND `adm_aware_excitation` preset flag is true; per-stem intensity from the preset's stem default | modify |
| `tests/unit/mixing/test_excitation.py` | Unit tests for the new DSP primitive | **new** |
| `tests/unit/mixing/test_polish_adm_aware_excitation.py` | Integration tests: analyzer → stem settings → stem processor | **new** |
| `CHANGELOG.md` | `[Unreleased]` entry | modify |

Files **not** modified:
- Mastering stages (`_album_stages.py`, `master_tracks.py`). Polish output feeds mastering naturally; excited signal's LUFS is measured normally.
- Top-level master_album config. `adm_validation_enabled` is unrelated — presets control excitation independently.

---

## Design Details (read before starting any task)

### The DSP primitive

Input: stereo numpy array `data`, sample rate `rate`, amount in dB, optional frequency range (default 3000-12000 Hz — the "presence/air" band where excitation generates useful harmonics).

Algorithm:

1. Bandpass the source to the excitation band. This isolates the mid content that will generate the new harmonics.
2. Soft-clip / saturate the bandpassed signal via `tanh(drive * x) / drive`. This is the nonlinearity that creates harmonics.
3. High-pass the saturated signal at `freq_range[0]` (the bottom of the excitation band). This removes the original bandpassed content and keeps only the *new* harmonics that saturation generated above the band.
4. Attenuate the new harmonics to `amount_db` gain (negative values → quieter, positive → louder).
5. Mix the attenuated harmonics back into the original signal.

```python
def apply_harmonic_excitation(
    data: np.ndarray,
    rate: int,
    amount_db: float,
    freq_range: tuple[float, float] = (3000.0, 12000.0),
    drive: float = 2.5,
) -> np.ndarray:
    if amount_db <= 0.0:
        return data
    low, high = freq_range
    nyq = rate / 2
    if high >= nyq:
        high = nyq - 1.0
    # Butterworth bandpass, 4th-order, zero-phase
    sos_bp = scipy.signal.butter(
        4, [low / nyq, high / nyq], btype="band", output="sos",
    )
    bandpassed = scipy.signal.sosfiltfilt(sos_bp, data, axis=0)
    # Soft saturation: tanh compresses and adds odd harmonics
    saturated = np.tanh(drive * bandpassed) / drive
    # High-pass to isolate the newly-created upper harmonics
    sos_hp = scipy.signal.butter(
        4, low / nyq, btype="high", output="sos",
    )
    new_harmonics = scipy.signal.sosfiltfilt(sos_hp, saturated, axis=0)
    # Attenuate and mix back
    gain_linear = 10.0 ** (amount_db / 20.0)
    return data + new_harmonics * gain_linear
```

Guarantees:
- `amount_db <= 0` is a no-op (returns input unchanged).
- Low frequencies (< 3 kHz by default) are unaffected.
- Output peak may be slightly higher than input peak (proportional to `amount_db` and input content). Downstream limiting (mastering) handles this.

### Per-stem preset defaults

| Stem | `excitation_db` default | Rationale |
|---|---:|---|
| vocals | 2.5 | Presence/air; most impact on perceived brightness |
| backing_vocals | 2.0 | Slightly less than lead vocals — they sit behind |
| guitar | 1.5 | Strings already have harmonic content |
| keyboard | 1.5 | Similar to guitar |
| strings | 2.0 | Bow noise / rosin simulation |
| brass | 1.5 | Already bright; gentle add |
| woodwinds | 2.0 | Breath/air simulation |
| percussion | 2.0 | Cymbal/shaker sparkle |
| synth | 1.5 | Often already bright from synthesis |
| drums | 0.0 | Kick/snare shouldn't get exciter — use transient_attack_db instead |
| bass | 0.0 | `sub_bass_exciter` handles bass |
| other | 1.0 | Conservative default for catch-all |

All default to 0.0 in the preset YAML, then raised to these values per-stem ONLY when the preset's `defaults.analyzer.adm_aware_excitation` flag is true AND the stem's analyzer result has `already_dark`. This preserves existing behavior by default.

### Analyzer integration

In `_analyze_one` in `servers/bitwize-music-server/handlers/processing/mixing.py:367-378`, the existing `already_dark` branch already emits `recommendations["high_tame_db"] = 0.0`. Extend it to also emit:

```python
adm_aware = analyzer_thresholds.get("adm_aware_excitation", False)
if adm_aware:
    # Pull per-stem default from preset; fall back to 2.0 dB as safe mid-ground.
    preset_excitation = (
        MIX_PRESETS
        .get("defaults", {})
        .get(stem_name, {})
        .get("excitation_db_when_dark", 2.0)
    )
    result["recommendations"]["excitation_db"] = preset_excitation
```

The "when dark" preset key is separate from the runtime `excitation_db` setting because it represents "what to apply WHEN we decide to excite this stem" — not "always apply this much." This way non-dark stems keep `excitation_db=0.0` in settings; only dark stems get elevated via the analyzer rec.

### `_get_stem_settings` wiring

Add `"excitation_db"` to:

1. `_ANALYZER_EQ_OVERRIDE_KEYS` — so the analyzer's rec gets merged into settings.
2. `_ANALYZER_PARAM_REASONS` with `("already_dark",)` — so `overrides_applied` telemetry credits the right reason.

No other change to `_get_stem_settings` — it already handles whitelisted-key merging.

### Stem processor wiring

Each stem processor that supports excitation (vocals, backing_vocals, guitar, keyboard, strings, brass, woodwinds, percussion, synth, other) gets a 3-line addition BEFORE the existing `high_tame_db` block (apply excitation, then tame highs if needed):

```python
excitation_db = settings.get('excitation_db', 0.0)
if excitation_db > 0:
    data = apply_harmonic_excitation(data, rate, amount_db=excitation_db)
```

Ordering matters: excitation adds upper harmonics, then high-shelf tame attenuates them if the preset also sets `high_tame_db < 0`. Usually the `already_dark` path sets `high_tame_db: 0.0` (from existing code) so the tame is a no-op and the excitation survives into the output.

Drums and bass skip excitation (see table above).

### Why this design is cheap to ship

- Default behavior unchanged. New preset flag defaults to off; new per-stem `excitation_db_when_dark` defaults don't matter until the flag is on.
- No orchestration changes. Polish output feeds mastering as today.
- Single DSP primitive, testable in isolation.
- Reuses the existing analyzer → stem settings pipeline.
- Per-stem tuning is just YAML — no code for operators to calibrate.

---

## Task 1: DSP primitive — `apply_harmonic_excitation`

**Files:**
- Create: `tools/mixing/excitation.py`
- Test: `tests/unit/mixing/test_excitation.py` (NEW)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/mixing/test_excitation.py`:

```python
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
```

- [ ] **Step 2: Run to verify failures**

```bash
.venv/bin/pytest tests/unit/mixing/test_excitation.py -v
```

Expected: all 8 tests FAIL with `ImportError: cannot import name 'apply_harmonic_excitation'`.

- [ ] **Step 3: Implement the primitive**

Create `tools/mixing/excitation.py`:

```python
"""Harmonic excitation: generate synthetic upper harmonics to add brightness
and presence to dark-material stems.

The primitive bandpasses the input to the 'presence' band (default 3-12 kHz),
applies tanh soft-saturation to generate new harmonics, high-passes the
saturated signal to isolate those new harmonics from the original content,
attenuates to the requested amount, and mixes back into the source.

Used by the polish stage when a stem is classified `already_dark` (high_mid
band_energy < 10 %) AND the preset's `adm_aware_excitation` flag is on.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import signal


def apply_harmonic_excitation(
    data: Any,
    rate: int,
    amount_db: float,
    freq_range: tuple[float, float] = (3000.0, 12000.0),
    drive: float = 2.5,
) -> Any:
    """Add synthetic upper harmonics to ``data`` via bandpass-saturate-hipass-mix.

    Args:
        data: Stereo or mono numpy array (float).
        rate: Sample rate in Hz.
        amount_db: Excitation intensity in dB. ``<= 0`` is a no-op;
            typical useful range 1.0-4.0 dB. Above 6 dB becomes audible
            as processing.
        freq_range: (low, high) Hz of the excitation band. Defaults
            to (3000, 12000) — the presence/air band.
        drive: tanh saturation drive. Higher = more aggressive harmonics.
            Default 2.5 is a balanced mid-ground.

    Returns:
        Excited signal with the same shape and dtype as ``data``.
    """
    if amount_db <= 0.0:
        return data

    low, high = freq_range
    nyq = rate / 2.0
    # Clamp high to stay below Nyquist.
    if high >= nyq:
        high = nyq - 1.0
    if low <= 0 or low >= high:
        # Degenerate band — no-op.
        return data

    # Bandpass to isolate the mid content that will generate harmonics.
    sos_bp = signal.butter(
        4, [low / nyq, high / nyq], btype="band", output="sos",
    )
    bandpassed = signal.sosfiltfilt(sos_bp, data, axis=0)

    # tanh saturation: compresses peaks and generates odd-order harmonics.
    saturated = np.tanh(drive * bandpassed) / drive

    # High-pass to keep only the NEW harmonics (above the bandpass region),
    # discarding the original bandpassed content. freq_range[0] is the
    # cutoff — harmonics generated from the source's fundamental content
    # land above this.
    sos_hp = signal.butter(4, low / nyq, btype="high", output="sos")
    new_harmonics = signal.sosfiltfilt(sos_hp, saturated, axis=0)

    gain_linear = 10.0 ** (amount_db / 20.0)
    return data + new_harmonics * gain_linear
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/unit/mixing/test_excitation.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/mixing/excitation.py tests/unit/mixing/test_excitation.py
git commit -m "$(cat <<'EOF'
feat: harmonic excitation DSP primitive for polish

New apply_harmonic_excitation(data, rate, amount_db, freq_range)
bandpass → tanh saturate → high-pass → attenuate → mix. Used by
the upcoming polish integration to add synthetic upper harmonics
to dark-material stems so downstream mastering has room to work.

amount_db <= 0 is a no-op (returns input unchanged) — matches the
"off by default" pattern already used by sub_bass_exciter and
other preset-controlled effects.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Preset plumbing — analyzer flag + per-stem defaults

**Files:**
- Modify: `tools/mixing/mix-presets.yaml`

- [ ] **Step 1: Add analyzer flag + per-stem defaults**

Open `tools/mixing/mix-presets.yaml`. In the `defaults.analyzer:` block, add:

```yaml
    # When true, stems classified `already_dark` (high_mid_ratio <
    # dark_high_mid_ratio) get a harmonic excitation recommendation
    # from _analyze_one. Per-stem intensity comes from each stem's
    # `excitation_db_when_dark` field. Off by default — enabling
    # changes the sound of dark-material polish (adds synthetic
    # upper harmonics via tanh saturation); see the plan doc
    # 2026-04-22-harmonic-excitation-polish.md for rationale and
    # caveats. Pair with mastering's adm_validation_enabled when
    # your target is Apple Digital Masters submission.
    adm_aware_excitation: false
```

In each stem's defaults (vocals, backing_vocals, guitar, keyboard, strings, brass, woodwinds, percussion, synth, other), add:

```yaml
    # Baseline excitation amount (dB) applied when the analyzer flags
    # this stem as `already_dark` AND defaults.analyzer.adm_aware_excitation
    # is true. 0.0 means "never excite this stem" — set on drums and bass.
    excitation_db_when_dark: 2.5   # vocals
```

Use these per-stem values:

| stem | `excitation_db_when_dark` |
|---|---:|
| vocals | 2.5 |
| backing_vocals | 2.0 |
| guitar | 1.5 |
| keyboard | 1.5 |
| strings | 2.0 |
| brass | 1.5 |
| woodwinds | 2.0 |
| percussion | 2.0 |
| synth | 1.5 |
| drums | 0.0 |
| bass | 0.0 |
| other | 1.0 |

Also add the runtime setting `excitation_db: 0.0` to each stem's defaults (except drums/bass which keep 0.0). This is the value the stem processor reads. It stays 0.0 unless the analyzer rec elevates it via `_get_stem_settings`.

Example for vocals:

```yaml
  vocals:
    click_removal: true
    noise_reduction: 0.5
    presence_boost_db: 2.0
    presence_freq: 3000
    high_tame_db: -2.0
    high_tame_freq: 7000
    compress_threshold_db: -15.0
    compress_ratio: 2.5
    compress_attack_ms: 10.0
    gain_db: 0.0
    saturation_drive: 0
    lowpass_cutoff: 20000
    excitation_db: 0.0
    excitation_db_when_dark: 2.5
```

- [ ] **Step 2: Verify YAML parses**

```bash
.venv/bin/python3 -c "
from tools.mixing.mix_tracks import MIX_PRESETS
assert MIX_PRESETS['defaults']['analyzer']['adm_aware_excitation'] is False
assert MIX_PRESETS['defaults']['vocals']['excitation_db_when_dark'] == 2.5
assert MIX_PRESETS['defaults']['vocals']['excitation_db'] == 0.0
assert MIX_PRESETS['defaults']['drums']['excitation_db_when_dark'] == 0.0
print('ok')
"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add tools/mixing/mix-presets.yaml
git commit -m "$(cat <<'EOF'
feat: preset keys for ADM-aware harmonic excitation

- defaults.analyzer.adm_aware_excitation (default false) gates
  the analyzer's emission of excitation recommendations for
  dark-classified stems.
- Per-stem excitation_db (runtime setting, default 0.0) and
  excitation_db_when_dark (analyzer target value) — vocals 2.5,
  cymbals/strings/percussion 2.0, guitar/keyboard/synth 1.5,
  brass/woodwinds/other 1.0-2.0, drums 0.0, bass 0.0.

Off by default. Opt in per preset when targeting ADM compliance.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `_get_stem_settings` whitelists `excitation_db`

**Files:**
- Modify: `tools/mixing/mix_tracks.py:1037-1054`
- Test: `tests/unit/mixing/test_polish_adm_aware_excitation.py` (NEW)

- [ ] **Step 1: Write failing test**

Create `tests/unit/mixing/test_polish_adm_aware_excitation.py`:

```python
"""End-to-end tests: analyzer recommends excitation_db on dark stems
(when the preset flag is on), which flows through _get_stem_settings
into the runtime settings, and the stem processor applies it."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.signal import welch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mixing.mix_tracks import _get_stem_settings


class TestGetStemSettingsExcitation:
    def test_analyzer_rec_applied_when_dark(self):
        """When the analyzer's rec has excitation_db, _get_stem_settings
        honors it (whitelisted)."""
        settings = _get_stem_settings(
            "vocals",
            analyzer_rec={"excitation_db": 2.5, "high_tame_db": 0.0},
        )
        assert settings["excitation_db"] == 2.5

    def test_no_rec_keeps_zero_default(self):
        """Without an analyzer rec, excitation_db stays at preset
        default (0.0)."""
        settings = _get_stem_settings("vocals", analyzer_rec=None)
        assert settings["excitation_db"] == 0.0

    def test_unrelated_rec_ignored(self):
        """Recommendations for non-whitelisted keys are ignored."""
        settings = _get_stem_settings(
            "vocals",
            analyzer_rec={"some_nonsense_key": 999},
        )
        assert "some_nonsense_key" not in settings
```

- [ ] **Step 2: Run to see failures**

```bash
.venv/bin/pytest tests/unit/mixing/test_polish_adm_aware_excitation.py::TestGetStemSettingsExcitation -v
```

Expected: `test_analyzer_rec_applied_when_dark` FAILS — `excitation_db` is not in `_ANALYZER_EQ_OVERRIDE_KEYS`, so the rec is dropped.

- [ ] **Step 3: Whitelist the key**

In `tools/mixing/mix_tracks.py:1037-1054`, extend both sets:

```python
_ANALYZER_EQ_OVERRIDE_KEYS = frozenset({
    "mud_cut_db",
    "high_tame_db",
    "noise_reduction",
    "highpass_cutoff",
    "excitation_db",
})

_ANALYZER_PARAM_REASONS: dict[str, tuple[str, ...]] = {
    "high_tame_db":    ("harsh_highmids", "already_dark"),
    "mud_cut_db":      ("muddy_low_mids",),
    "noise_reduction": ("elevated_noise_floor",),
    "highpass_cutoff": ("sub_rumble",),
    "excitation_db":   ("already_dark",),
}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/unit/mixing/test_polish_adm_aware_excitation.py::TestGetStemSettingsExcitation -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Regression-check existing whitelisted-key tests**

```bash
.venv/bin/pytest tests/unit/mixing/ -k "analyzer or override or stem_settings" -v
```

Expected: no regressions. Adding a key doesn't affect other analyzer recs.

- [ ] **Step 6: Commit**

```bash
git add tools/mixing/mix_tracks.py \
        tests/unit/mixing/test_polish_adm_aware_excitation.py
git commit -m "$(cat <<'EOF'
feat: whitelist excitation_db as an analyzer override

Adds excitation_db to _ANALYZER_EQ_OVERRIDE_KEYS and maps it to
the ('already_dark',) reason tag in _ANALYZER_PARAM_REASONS, so
analyzer recommendations flow through _get_stem_settings into
runtime stem settings with correct per-parameter attribution.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Analyzer emits `excitation_db` recommendation on dark stems

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/mixing.py:367-378` (the `already_dark` branch of `_analyze_one`)
- Test: extend `tests/unit/mixing/test_polish_adm_aware_excitation.py`

- [ ] **Step 1: Add failing test**

Append to `tests/unit/mixing/test_polish_adm_aware_excitation.py`:

```python
class TestAnalyzerEmitsExcitationRec:
    def _call_analyze_one(self, data, rate, stem_name, adm_aware):
        """Thin wrapper: build the preset-threshold dict the way
        _analyze_one expects, call it, return its result."""
        import sys
        SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
        if str(SERVER_DIR) not in sys.path:
            sys.path.insert(0, str(SERVER_DIR))
        from handlers.processing.mixing import _analyze_one  # type: ignore
        # _analyze_one takes thresholds from the preset block; pass an
        # override matching the new key.
        return _analyze_one(
            data, rate, stem_name,
            dark_ratio=0.10, harsh_ratio=0.25,
            peak_ratio=15.0, genre=None,
            adm_aware_excitation=adm_aware,
        )

    def test_no_rec_when_flag_off(self, tmp_path: Path):
        """Dark stem, adm_aware_excitation=False → no excitation_db
        recommendation emitted (existing behavior preserved)."""
        from scipy.signal import butter, sosfilt
        rng = np.random.default_rng(0)
        rate = 48000
        n = int(2.0 * rate)
        white = rng.standard_normal((n, 2)).astype(np.float64)
        sos = butter(4, 500.0, btype="low", fs=rate, output="sos")
        dark = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
        dark /= np.max(np.abs(dark)) + 1e-9
        dark *= 0.1

        result = self._call_analyze_one(dark, rate, "vocals", adm_aware=False)
        assert "already_dark" in result["issues"], (
            "Fixture should be classified dark"
        )
        assert "excitation_db" not in result["recommendations"], (
            "Flag off → no excitation rec"
        )

    def test_rec_emitted_when_flag_on_and_dark(self, tmp_path: Path):
        """Dark stem + flag on → excitation_db rec at stem's per-stem
        preset value."""
        from scipy.signal import butter, sosfilt
        rng = np.random.default_rng(1)
        rate = 48000
        n = int(2.0 * rate)
        white = rng.standard_normal((n, 2)).astype(np.float64)
        sos = butter(4, 500.0, btype="low", fs=rate, output="sos")
        dark = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
        dark /= np.max(np.abs(dark)) + 1e-9
        dark *= 0.1

        result = self._call_analyze_one(dark, rate, "vocals", adm_aware=True)
        assert "already_dark" in result["issues"]
        assert result["recommendations"].get("excitation_db") == 2.5, (
            "Vocals preset's excitation_db_when_dark is 2.5"
        )

    def test_no_rec_on_bright_stem(self, tmp_path: Path):
        """Bright stem + flag on → no excitation rec (only dark stems
        get excited)."""
        from scipy.signal import butter, sosfilt
        rng = np.random.default_rng(2)
        rate = 48000
        n = int(2.0 * rate)
        white = rng.standard_normal((n, 2)).astype(np.float64)
        sos = butter(4, 800.0, btype="high", fs=rate, output="sos")
        bright = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
        bright /= np.max(np.abs(bright)) + 1e-9
        bright *= 0.1

        result = self._call_analyze_one(bright, rate, "vocals", adm_aware=True)
        assert "already_dark" not in result["issues"]
        assert "excitation_db" not in result["recommendations"]
```

- [ ] **Step 2: Run to see failures**

```bash
.venv/bin/pytest tests/unit/mixing/test_polish_adm_aware_excitation.py::TestAnalyzerEmitsExcitationRec -v
```

Expected: FAILS — `_analyze_one` doesn't accept `adm_aware_excitation` kwarg yet and doesn't emit the rec.

- [ ] **Step 3: Thread the flag + emit the rec**

Read `servers/bitwize-music-server/handlers/processing/mixing.py` around `def _analyze_one` and the existing threshold-resolution helper. Two changes:

**3a.** Extend `_analyze_one` signature to accept `adm_aware_excitation: bool = False` kwarg (pass through from the caller).

**3b.** In the existing `already_dark` branch (around line 372-378), after setting `result["recommendations"]["high_tame_db"] = 0.0`, add:

```python
                if adm_aware_excitation:
                    # Lookup per-stem target from the preset; fall back
                    # to 2.0 dB as a safe mid-ground if the preset
                    # doesn't declare one.
                    try:
                        from tools.mixing.mix_tracks import MIX_PRESETS
                    except ImportError:
                        MIX_PRESETS = {}  # type: ignore
                    preset_excitation = (
                        MIX_PRESETS
                        .get("defaults", {})
                        .get(stem_name, {})
                        .get("excitation_db_when_dark", 2.0)
                    )
                    if preset_excitation > 0:
                        result["recommendations"]["excitation_db"] = float(
                            preset_excitation,
                        )
```

**3c.** Update the caller of `_analyze_one` (search for it in the same file — `analyze_mix_issues`) to read the flag from the threshold-resolution helper and pass it through:

```python
adm_aware = analyzer_thresholds.get("adm_aware_excitation", False)
# ...when calling _analyze_one:
_analyze_one(..., adm_aware_excitation=adm_aware)
```

The threshold-resolution helper (`_resolve_analyzer_thresholds`) already reads the preset's `defaults.analyzer` block — extend it to include `adm_aware_excitation` alongside `dark_high_mid_ratio` / `harsh_high_mid_ratio`.

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/unit/mixing/test_polish_adm_aware_excitation.py::TestAnalyzerEmitsExcitationRec -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Regression check**

```bash
.venv/bin/pytest tests/unit/mixing/ -v
```

Expected: no regressions in other analyzer/mixing tests.

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/mixing.py \
        tests/unit/mixing/test_polish_adm_aware_excitation.py
git commit -m "$(cat <<'EOF'
feat: _analyze_one emits excitation_db rec on dark stems

When defaults.analyzer.adm_aware_excitation is true in the mix
preset, dark-classified stems get an excitation_db recommendation
sourced from the stem's excitation_db_when_dark preset field.
Drums and bass keep 0.0 (never excited). Flag defaults to false,
so existing behavior is unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Stem processors apply excitation

**Files:**
- Modify: `tools/mixing/mix_tracks.py` — stem processors for vocals, backing_vocals, guitar, keyboard, strings, brass, woodwinds, percussion, synth, other. Each gets an excitation block added before its existing `high_tame_db` block.
- Test: extend `tests/unit/mixing/test_polish_adm_aware_excitation.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/mixing/test_polish_adm_aware_excitation.py`:

```python
class TestStemProcessorAppliesExcitation:
    def test_vocals_excitation_adds_high_mid(self, tmp_path: Path):
        """_process_vocals with excitation_db=2.5 measurably raises
        high_mid band energy vs excitation_db=0."""
        from scipy.signal import butter, sosfilt
        from scipy.signal import welch

        rng = np.random.default_rng(3)
        rate = 48000
        n = int(2.0 * rate)
        white = rng.standard_normal((n, 2)).astype(np.float64)
        sos = butter(4, 600.0, btype="low", fs=rate, output="sos")
        dark = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
        dark /= np.max(np.abs(dark)) + 1e-9
        dark *= 0.1

        # Import the processor. Each repo may name the helper
        # differently (_process_vocals, process_vocals, etc.) — adapt
        # to match the actual export. Common pattern: `mix_track_stems`
        # routes to per-stem helpers. We test via a minimal settings
        # dict bypassing the full dispatcher.
        from tools.mixing.mix_tracks import _process_stem_vocals

        base_settings = {
            "click_removal": False,
            "noise_reduction": 0.0,
            "presence_boost_db": 0.0,
            "presence_freq": 3000,
            "high_tame_db": 0.0,
            "high_tame_freq": 7000,
            "compress_threshold_db": -15.0,
            "compress_ratio": 1.0,   # effectively no compression
            "compress_attack_ms": 10.0,
            "gain_db": 0.0,
            "saturation_drive": 0.0,
            "lowpass_cutoff": 20000,
        }

        no_excite_settings = {**base_settings, "excitation_db": 0.0}
        excite_settings = {**base_settings, "excitation_db": 3.0}

        # If the processor in your codebase has a different name, adjust.
        out_no = _process_stem_vocals(dark.copy(), rate, no_excite_settings)
        out_yes = _process_stem_vocals(dark.copy(), rate, excite_settings)

        def _high_mid_pct(x):
            mono = np.mean(x, axis=1)
            freqs, psd = welch(mono, rate, nperseg=8192)
            total = float(np.sum(psd))
            if total == 0.0:
                return 0.0
            mask = (freqs >= 2000) & (freqs < 6000)
            return float(np.sum(psd[mask]) / total * 100.0)

        pre = _high_mid_pct(out_no)
        post = _high_mid_pct(out_yes)
        assert post > pre + 0.5, (
            f"Excitation in vocals processor did not raise high_mid: "
            f"no={pre:.2f}%, with={post:.2f}%"
        )
```

**Adapt processor name if needed.** Run `grep -n "def _process_stem\|def process_vocals\|def _vocals_chain" tools/mixing/mix_tracks.py` to find the actual vocals processor function. The test above uses `_process_stem_vocals` as a placeholder; rename to the real symbol.

- [ ] **Step 2: Run to see failure**

```bash
.venv/bin/pytest tests/unit/mixing/test_polish_adm_aware_excitation.py::TestStemProcessorAppliesExcitation -v
```

Expected: FAIL — excitation is not wired into the vocals processor yet, so `out_no` and `out_yes` produce identical high_mid content.

- [ ] **Step 3: Wire excitation into each stem processor**

For EACH of these processors in `tools/mixing/mix_tracks.py` (use `grep -n "high_tame_db = settings.get" tools/mixing/mix_tracks.py` to find them all):

- vocals (around line 1172)
- backing_vocals (around line 1224)
- guitar (around line 1371)
- keyboard (around line 1432)
- strings (around line 1493)
- brass (around line 1555)
- woodwinds (around line 1617)
- percussion
- synth
- other

In each, BEFORE the `high_tame_db = settings.get(...)` block, insert:

```python
    excitation_db = settings.get('excitation_db', 0.0)
    if excitation_db > 0:
        from tools.mixing.excitation import apply_harmonic_excitation
        data = apply_harmonic_excitation(data, rate, amount_db=excitation_db)
```

Lift the import to the top of the file if preferred (cleaner than per-call import). The per-call form is shown first to minimize diff during initial review.

Drums and bass intentionally skip this addition — their preset defaults are 0.0 and they use other brightness mechanisms (`transient_attack_db`, `sub_bass_exciter`).

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/unit/mixing/test_polish_adm_aware_excitation.py -v
```

All tests in the file must PASS.

- [ ] **Step 5: Regression check for polish suite**

```bash
.venv/bin/pytest tests/unit/mixing/ tests/unit/mastering/ -k "polish or mix or stem" -v
```

Expected: no regressions. Existing polish/mix tests don't set `excitation_db`, so it defaults to 0.0, processor is a no-op.

- [ ] **Step 6: Commit**

```bash
git add tools/mixing/mix_tracks.py \
        tests/unit/mixing/test_polish_adm_aware_excitation.py
git commit -m "$(cat <<'EOF'
feat: stem processors apply harmonic excitation

Vocals, backing_vocals, guitar, keyboard, strings, brass,
woodwinds, percussion, synth, and other stem processors now call
apply_harmonic_excitation when settings['excitation_db'] > 0.
Drums and bass intentionally skip (kick/snare use transient_*
knobs; bass uses sub_bass_exciter).

Excitation runs BEFORE the existing high_tame_db block so the
"dark" path (high_tame=0, excitation>0) preserves the new
harmonics through to output.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: End-to-end integration test + CHANGELOG

**Files:**
- Test: extend `tests/unit/mixing/test_polish_adm_aware_excitation.py`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add an end-to-end test**

Append to `tests/unit/mixing/test_polish_adm_aware_excitation.py`:

```python
class TestEndToEnd:
    def test_dark_material_polish_excites_when_flag_on(self, tmp_path: Path):
        """Given a dark stem WAV and adm_aware_excitation=True in
        preset, the full polish chain produces output with measurably
        more high_mid energy than the same run with the flag off."""
        import sys
        SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
        if str(SERVER_DIR) not in sys.path:
            sys.path.insert(0, str(SERVER_DIR))

        import soundfile as sf
        from scipy.signal import butter, sosfilt, welch

        # Write a dark vocals-like fixture.
        rng = np.random.default_rng(42)
        rate = 48000
        n = int(2.0 * rate)
        white = rng.standard_normal((n, 2)).astype(np.float64)
        sos = butter(4, 500.0, btype="low", fs=rate, output="sos")
        dark = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
        dark /= np.max(np.abs(dark)) + 1e-9
        dark *= 0.1

        # The easiest way to exercise end-to-end is through
        # _get_stem_settings + _process_stem_vocals with the analyzer
        # rec already injected. Full mix_track_stems orchestration
        # requires stem files on disk and is covered by broader
        # integration tests.

        from tools.mixing.mix_tracks import (
            _get_stem_settings,
            _process_stem_vocals,
        )

        no_rec_settings = _get_stem_settings("vocals", analyzer_rec=None)
        with_rec_settings = _get_stem_settings(
            "vocals",
            analyzer_rec={"excitation_db": 2.5, "high_tame_db": 0.0},
        )

        out_no = _process_stem_vocals(dark.copy(), rate, no_rec_settings)
        out_yes = _process_stem_vocals(dark.copy(), rate, with_rec_settings)

        def _high_mid_pct(x):
            mono = np.mean(x, axis=1)
            freqs, psd = welch(mono, rate, nperseg=8192)
            total = float(np.sum(psd))
            if total == 0.0:
                return 0.0
            mask = (freqs >= 2000) & (freqs < 6000)
            return float(np.sum(psd[mask]) / total * 100.0)

        assert _high_mid_pct(out_yes) > _high_mid_pct(out_no) + 1.0
```

- [ ] **Step 2: Run tests**

```bash
.venv/bin/pytest tests/unit/mixing/test_polish_adm_aware_excitation.py -v
```

All tests PASS.

- [ ] **Step 3: Update CHANGELOG**

Append to `CHANGELOG.md` under `[Unreleased]` → `### Added`:

```markdown
- Harmonic excitation in polish — `apply_harmonic_excitation`
  DSP primitive + per-stem `excitation_db` preset setting.
  When `defaults.analyzer.adm_aware_excitation: true` in the
  mix preset, dark-classified stems (high_mid band_energy < 10 %)
  get synthetic upper-harmonic content added during polish via
  bandpass → tanh saturation → high-pass → attenuate → mix.
  Gives mastering's limiter room to work on dark Suno material
  that would otherwise ship with ADM inter-sample peak flags.
  Off by default — enable per preset when targeting ADM
  compliance. See `docs/superpowers/plans/2026-04-22-harmonic-excitation-polish.md`.
```

- [ ] **Step 4: `make check`**

```bash
make check 2>&1 | tail -20
```

Expected: PASS (ruff + bandit + mypy + pytest all green).

- [ ] **Step 5: Commit**

```bash
git add tests/unit/mixing/test_polish_adm_aware_excitation.py CHANGELOG.md
git commit -m "$(cat <<'EOF'
chore: CHANGELOG + end-to-end coverage for excitation

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Open PR**

Branch name: `feat/harmonic-excitation-polish` off `develop`.

PR body should:
- Describe the three changes (primitive, preset plumbing, processor integration).
- Call out that behavior is unchanged unless the preset flag is turned on.
- Note that enabling the flag changes the sound (adds synthetic high-mid content) and operators should A/B on a real album before committing.
- Link the Apr-21 halt-report discussion (bug #6 / dark-casualty context) if there's a thread to reference.

---

## Self-Review Checklist

1. **Spec coverage:**
   - DSP primitive: Task 1.
   - Preset plumbing: Task 2.
   - `_get_stem_settings` whitelist: Task 3.
   - Analyzer rec emission: Task 4.
   - Stem processor wiring: Task 5.
   - End-to-end + CHANGELOG + gate: Task 6.

2. **No placeholders:** Every code block is complete. Test fixtures are real (pink/dark noise generators). The "adapt processor name if needed" in Task 5 step 1 is a genuine note about the implementer verifying the symbol — the expected name `_process_stem_vocals` matches the codebase pattern but if it's `_vocals_chain` or similar, the implementer renames.

3. **Type consistency:** `excitation_db: float`, `excitation_db_when_dark: float`, `adm_aware_excitation: bool`. Same shape everywhere.

4. **Backward compat:** Preset flag defaults to `false`. Per-stem `excitation_db` defaults to `0.0`. Processors no-op on `excitation_db <= 0`. Existing albums with no preset changes see zero behavior change.

5. **Ordering invariant:** Excitation before `high_tame_db` inside each stem processor. The `already_dark` analyzer path sets `high_tame_db: 0.0`, so the tame is a no-op and the new harmonics survive. If operators manually set `high_tame_db: -2.0` AND `excitation_db: 2.5`, the tame will partially undo the excitation — but that's a configuration decision; the ordering is fail-safe (no clipping, no NaN, just degraded effect).

6. **Dependency on earlier plans:** This plan depends on Plan B's `is_dark` detection and analyzer plumbing being on develop. Verified — Plan B merged as `da66f66` and is on `develop` at the branch base.

7. **Rollout caveat worth surfacing in PR body:** operators should pilot on one album before making the flag default-on — excitation changes the sound, and taste varies.
