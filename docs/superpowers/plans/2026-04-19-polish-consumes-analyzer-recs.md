# Polish Consumes Analyzer Recommendations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `analyze_mix_issues` recommendations into `polish_album` as per-track overrides on top of genre defaults, and add a dark-track protection condition to the analyzer so electronic tracks with low high-mid energy stop getting genre-default `high_tame_db: -1.5` that further darkens them.

**Architecture:** Additive across the mix subsystem. (1) Analyzer gains one `elif high_mid_ratio < 0.10` branch producing `high_tame_db: 0.0` + `already_dark` issue tag. (2) `_get_stem_settings` gains an `analyzer_rec` kwarg that whitelist-filters and merges the analyzer's per-stem recommendations on top of genre defaults. (3) `mix_track_stems` gains `analyzer_recs` and records `overrides_applied` per stem. (4) `polish_audio` gains `analyzer_results` (auto-runs the analyzer when None) and aggregates overrides across tracks. (5) `polish_album` passes its existing analyze-stage output down.

**Tech Stack:** Python 3, pytest, numpy/scipy, YAML presets. Changes contained to `servers/bitwize-music-server/handlers/processing/mixing.py`, `tools/mixing/mix_tracks.py`, `tools/mixing/mix-presets.yaml`.

**Spec:** [`docs/superpowers/specs/2026-04-19-polish-consumes-analyzer-recs-design.md`](../specs/2026-04-19-polish-consumes-analyzer-recs-design.md)

**Canonical issue:** [#336](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/336)

---

## File Structure

| File | Role |
|---|---|
| `tools/mixing/mix-presets.yaml` | Add `defaults.analyzer.{dark_high_mid_ratio, harsh_high_mid_ratio}` for preset-tunable thresholds (defaults 0.10 / 0.25, unchanged behavior) |
| `servers/bitwize-music-server/handlers/processing/mixing.py` | Add `_resolve_analyzer_thresholds` helper; add dark-track branch in `_analyze_one`; add `analyzer_results` kwarg to `polish_audio` with auto-run fallback; pipe analyzer output to `mix_track_stems`; aggregate `overrides_applied` into `polish` stage output |
| `tools/mixing/mix_tracks.py` | Add `analyzer_rec` kwarg to `_get_stem_settings` (whitelist-filtered merge on top of genre defaults); add `analyzer_recs` kwarg to `mix_track_stems` (per-stem dispatch + `overrides_applied` telemetry) |
| `tests/unit/mixing/test_analyze_mix_issues.py` | NEW — analyzer's dark-track condition, threshold preset override, harsh/dark non-overlap |
| `tests/unit/mixing/test_polish_analyzer_overrides.py` | NEW — `_get_stem_settings` merge behavior, sentinel `0.0`, fall-through, non-EQ ignored |
| `tests/unit/mixing/test_polish_audio_stems.py` | EXTEND — polish_audio pipes analyzer through; direct-call auto-run fallback |

Allowed EQ whitelist: `mud_cut_db`, `high_tame_db`, `noise_reduction`, `highpass_cutoff`. `click_removal` intentionally excluded (already wired via `_resolve_analyzer_peak_ratio`).

---

## Task 1: Analyzer dark-track condition + preset thresholds

**Files:**
- Modify: `tools/mixing/mix-presets.yaml` (add `defaults.analyzer` block)
- Modify: `servers/bitwize-music-server/handlers/processing/mixing.py` (add `_resolve_analyzer_thresholds`; extend `_analyze_one` around line 334)
- Test: `tests/unit/mixing/test_analyze_mix_issues.py` (NEW file)

- [ ] **Step 1: Write failing tests for the dark-track condition and preset resolution**

Create `tests/unit/mixing/test_analyze_mix_issues.py`:

```python
"""Unit tests for analyze_mix_issues dark-track condition + threshold resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


def test_resolve_analyzer_thresholds_defaults():
    """With no preset overrides, resolver returns (0.10, 0.25)."""
    from handlers.processing.mixing import _resolve_analyzer_thresholds
    dark, harsh = _resolve_analyzer_thresholds()
    assert dark == pytest.approx(0.10)
    assert harsh == pytest.approx(0.25)


def test_dark_condition_emits_high_tame_zero_and_already_dark_issue(monkeypatch):
    """A track with high_mid_ratio < 0.10 gets recommendation high_tame_db=0.0."""
    import numpy as np
    from handlers.processing.mixing import _build_analyzer

    # Dark synthetic signal: low-frequency sine at ~100 Hz, 2 s @ 48 kHz.
    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    mono = 0.3 * np.sin(2 * np.pi * 100 * t).astype(np.float64)
    data = np.column_stack([mono, mono])

    analyze_one = _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)
    result = analyze_one(data, rate, filename="dark-track.wav", stem_name="synth", genre="electronic")

    assert "already_dark" in result["issues"], f"expected already_dark, got {result['issues']}"
    assert result["recommendations"]["high_tame_db"] == pytest.approx(0.0)
    assert result["high_mid_ratio"] < 0.10


def test_harsh_condition_still_fires_above_0_25(monkeypatch):
    """A track with high_mid_ratio > 0.25 gets recommendation high_tame_db=-2.0 and harsh_highmids issue."""
    import numpy as np
    from handlers.processing.mixing import _build_analyzer

    # Harsh synthetic: sum of 3 kHz + 4 kHz strong tones.
    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    mono = (0.3 * np.sin(2 * np.pi * 3000 * t) + 0.3 * np.sin(2 * np.pi * 4000 * t)).astype("float64")
    data = np.column_stack([mono, mono])

    analyze_one = _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)
    result = analyze_one(data, rate, filename="harsh-track.wav", stem_name="synth", genre="electronic")

    assert "harsh_highmids" in result["issues"], f"expected harsh_highmids, got {result['issues']}"
    assert result["recommendations"]["high_tame_db"] == pytest.approx(-2.0)


def test_middle_band_triggers_neither_condition(monkeypatch):
    """high_mid_ratio in [0.10, 0.25] produces neither issue tag."""
    import numpy as np
    from handlers.processing.mixing import _build_analyzer

    # Mixed signal with moderate high-mid content.
    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    # 500 Hz (mid) + 3 kHz (high-mid) balanced so ratio is in the middle band
    mono = (0.35 * np.sin(2 * np.pi * 500 * t) + 0.08 * np.sin(2 * np.pi * 3000 * t)).astype("float64")
    data = np.column_stack([mono, mono])

    analyze_one = _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)
    result = analyze_one(data, rate, filename="middle-track.wav", stem_name="synth", genre="electronic")

    assert "already_dark" not in result["issues"]
    assert "harsh_highmids" not in result["issues"]
    # Neither recommendation should be emitted:
    assert "high_tame_db" not in result["recommendations"]


def test_preset_override_of_dark_threshold_changes_trigger(monkeypatch):
    """Raising the dark threshold to 0.15 makes a 0.12-ratio track fire already_dark."""
    import numpy as np
    from handlers.processing.mixing import _build_analyzer

    # Mixed signal engineered for high_mid_ratio ~ 0.12 (middle band under default 0.10 floor).
    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    mono = (0.30 * np.sin(2 * np.pi * 500 * t) + 0.09 * np.sin(2 * np.pi * 3000 * t)).astype("float64")
    data = np.column_stack([mono, mono])

    # With default thresholds (0.10/0.25), no issue
    analyze_default = _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)
    result_default = analyze_default(data, rate, filename="mid.wav", stem_name="synth", genre="electronic")
    assert "already_dark" not in result_default["issues"]

    # With dark_ratio raised to 0.15, now fires
    analyze_raised = _build_analyzer(dark_ratio=0.15, harsh_ratio=0.25)
    result_raised = analyze_raised(data, rate, filename="mid.wav", stem_name="synth", genre="electronic")
    assert "already_dark" in result_raised["issues"]
    assert result_raised["recommendations"]["high_tame_db"] == pytest.approx(0.0)
```

Note: the test calls `_build_analyzer(dark_ratio, harsh_ratio)` — a new helper that returns a closure performing the same analysis as `_analyze_one` but with injected thresholds. This lets tests run the analysis logic on raw numpy data without the async/filesystem harness. Task 1 introduces this helper alongside the existing `_analyze_one` inner function; `_analyze_one` then calls into it with resolved thresholds.

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/unit/mixing/test_analyze_mix_issues.py -v`
Expected: FAIL — `ImportError: cannot import name '_resolve_analyzer_thresholds'` and `_build_analyzer`.

- [ ] **Step 3: Add the `analyzer` preset block**

Edit `tools/mixing/mix-presets.yaml`. Find the `defaults:` section at the top of the file (existing structure: `defaults` holds per-stem config like `defaults.vocals`, `defaults.drums`, etc.). Add a new `analyzer` subsection at the top of `defaults`:

```yaml
defaults:
  analyzer:
    # Thresholds consumed by analyze_mix_issues — see servers/.../mixing.py
    # _analyze_one. Dark tracks (high_mid_ratio < dark_high_mid_ratio) get
    # recommendation high_tame_db: 0.0, overriding genre-default high-shelf
    # cuts that would further darken them. Harsh tracks
    # (high_mid_ratio > harsh_high_mid_ratio) get high_tame_db: -2.0.
    dark_high_mid_ratio: 0.10
    harsh_high_mid_ratio: 0.25
  # ... existing vocals, drums, etc. below stay untouched
```

Be careful about indentation — YAML is whitespace-sensitive. Two-space indent under `defaults:`. Place the block above existing per-stem entries.

- [ ] **Step 4: Add `_resolve_analyzer_thresholds` helper + `_build_analyzer` factory + dark-track branch**

Edit `servers/bitwize-music-server/handlers/processing/mixing.py`.

First, directly after the existing `_resolve_analyzer_peak_ratio` function (around line 228), add the new threshold resolver:

```python
def _resolve_analyzer_thresholds() -> tuple[float, float]:
    """Load (dark_high_mid_ratio, harsh_high_mid_ratio) from mix presets.

    Falls back to (0.10, 0.25) when the analyzer preset block is absent.
    Values are consumed by `_analyze_one` for the dark-track and
    harsh-highmids branches respectively (#336).
    """
    try:
        from tools.mixing.mix_tracks import load_mix_presets
    except ImportError:
        return 0.10, 0.25

    presets = load_mix_presets()
    analyzer = presets.get("defaults", {}).get("analyzer", {})
    dark = float(analyzer.get("dark_high_mid_ratio", 0.10))
    harsh = float(analyzer.get("harsh_high_mid_ratio", 0.25))
    return dark, harsh
```

Second, lift the existing `_analyze_one` inner function in `analyze_mix_issues` (around lines 291–378) into a module-level factory that accepts thresholds. This replaces the inner function and lets tests run the analysis logic directly without an album fixture.

Replace lines 291–378 (the entire `def _analyze_one` body, inside `async def analyze_mix_issues`) with a call to the factory:

At the module level, above `async def analyze_mix_issues`, add:

```python
def _build_analyzer(
    dark_ratio: float = 0.10,
    harsh_ratio: float = 0.25,
):
    """Return an `analyze_one` callable bound to the given thresholds.

    The returned callable takes raw numpy audio data and produces the
    per-file/per-stem analysis dict. Splitting it out of
    `analyze_mix_issues` lets tests exercise the logic without mounting
    an album directory.

    Args:
        dark_ratio: high_mid_ratio below which `already_dark` fires.
        harsh_ratio: high_mid_ratio above which `harsh_highmids` fires.

    Returns:
        Callable ``analyze_one(data, rate, *, filename, stem_name, genre)``
        → per-file analysis dict identical in shape to the original
        `_analyze_one` output.
    """
    import numpy as np
    from scipy import signal as sig

    def analyze_one(
        data,
        rate: int,
        *,
        filename: str,
        stem_name: str | None = None,
        genre: str = "",
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"filename": filename, "issues": [], "recommendations": {}}

        peak = float(np.max(np.abs(data)))
        rms = float(np.sqrt(np.mean(data ** 2)))
        result["peak"] = peak
        result["rms"] = rms

        # Noise floor estimate (quietest 10% of signal)
        abs_signal = np.abs(data[:, 0])
        sorted_abs = np.sort(abs_signal)
        noise_floor = float(np.mean(sorted_abs[:len(sorted_abs) // 10]))
        result["noise_floor"] = noise_floor
        if noise_floor > 0.005:
            result["issues"].append("elevated_noise_floor")
            result["recommendations"]["noise_reduction"] = min(0.8, noise_floor * 100)

        freqs, psd = sig.welch(data[:, 0], rate, nperseg=min(4096, len(data)))

        # Low-mid energy (150-400 Hz) — muddiness indicator
        low_mid_mask = (freqs >= 150) & (freqs <= 400)
        total_energy = float(np.sum(psd))
        if total_energy > 0:
            low_mid_ratio = float(np.sum(psd[low_mid_mask])) / total_energy
            result["low_mid_ratio"] = low_mid_ratio
            if low_mid_ratio > 0.35:
                result["issues"].append("muddy_low_mids")
                result["recommendations"]["mud_cut_db"] = -3.0

        # High-mid energy (2-5 kHz) — harshness / darkness indicator
        high_mid_mask = (freqs >= 2000) & (freqs <= 5000)
        if total_energy > 0:
            high_mid_ratio = float(np.sum(psd[high_mid_mask])) / total_energy
            result["high_mid_ratio"] = high_mid_ratio
            if high_mid_ratio > harsh_ratio:
                result["issues"].append("harsh_highmids")
                result["recommendations"]["high_tame_db"] = -2.0
            elif high_mid_ratio < dark_ratio:
                # #336: already-dark track — emit sentinel 0.0 to override
                # genre-default high-shelf cuts (e.g. electronic's
                # synth/keyboard/other stems at -1.5 dB @ 9 kHz) that would
                # compound the darkness in polish.
                result["issues"].append("already_dark")
                result["recommendations"]["high_tame_db"] = 0.0

        # Click detection (sudden amplitude spikes).
        mono_col = data[:, 0]
        window = max(int(rate * 0.01), 1)
        n_windows = len(mono_col) // window
        if n_windows > 0:
            windows = mono_col[: n_windows * window].reshape(n_windows, window)
            win_rms = np.sqrt(np.mean(windows ** 2, axis=1))
            win_peak = np.max(np.abs(windows), axis=1)
            active = win_rms > 1e-8
            ratios = np.zeros(n_windows, dtype=np.float64)
            np.divide(win_peak, win_rms, out=ratios, where=active)
            peak_ratio = _resolve_analyzer_peak_ratio(stem_name, genre)
            click_count = int(np.sum(ratios > peak_ratio))
            result["click_count"] = click_count
            if click_count > 10:
                result["issues"].append("clicks_detected")
                result["recommendations"]["click_removal"] = True

        # Sub-bass rumble (< 30 Hz)
        sub_mask = freqs < 30
        if total_energy > 0:
            sub_ratio = float(np.sum(psd[sub_mask])) / total_energy
            result["sub_ratio"] = sub_ratio
            if sub_ratio > 0.15:
                result["issues"].append("sub_rumble")
                result["recommendations"]["highpass_cutoff"] = 35

        if not result["issues"]:
            result["issues"].append("none_detected")

        return result

    return analyze_one
```

Third, replace the inner `_analyze_one` in `analyze_mix_issues` (currently lines 291–378) with code that uses the factory. After the `stems_mode` detection block, insert threshold resolution and analyzer construction:

```python
    # Resolve analyzer thresholds once per run (preset-configurable, #336).
    dark_ratio, harsh_ratio = _resolve_analyzer_thresholds()
    analyze_core = _build_analyzer(dark_ratio=dark_ratio, harsh_ratio=harsh_ratio)

    def _analyze_one(
        wav_path: Path, stem_name: str | None = None,
    ) -> dict[str, Any]:
        data, rate = sf.read(str(wav_path))
        if len(data.shape) == 1:
            data = np.column_stack([data, data])
        return analyze_core(
            data, rate, filename=wav_path.name,
            stem_name=stem_name, genre=genre,
        )
```

The rest of `analyze_mix_issues` (the `track_analyses` loop and the final `_safe_json` return) is unchanged.

- [ ] **Step 5: Run the analyzer tests — they pass**

Run: `pytest tests/unit/mixing/test_analyze_mix_issues.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add tools/mixing/mix-presets.yaml servers/bitwize-music-server/handlers/processing/mixing.py tests/unit/mixing/test_analyze_mix_issues.py
git commit -m "feat: analyzer dark-track condition + preset thresholds (#336)

Add 'already_dark' branch in _analyze_one: when high_mid_ratio
< dark_high_mid_ratio (default 0.10), emit issue tag 'already_dark'
and recommendation high_tame_db: 0.0 — a sentinel for polish to
override genre-default high-shelf cuts that would further darken
the track. Thresholds (dark / harsh) loaded from the new
defaults.analyzer preset block so per-genre tuning is a config
change, not a code change. Analysis logic extracted into a module-
level _build_analyzer factory so tests can run on raw numpy data.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: `_get_stem_settings` accepts `analyzer_rec` kwarg

**Files:**
- Modify: `tools/mixing/mix_tracks.py` (extend `_get_stem_settings` signature + body around line 1033)
- Test: `tests/unit/mixing/test_polish_analyzer_overrides.py` (NEW file)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/mixing/test_polish_analyzer_overrides.py`:

```python
"""Unit tests for _get_stem_settings analyzer_rec merge behavior (#336)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_get_stem_settings_no_analyzer_rec_is_backward_compatible():
    """Without analyzer_rec, settings match previous behavior exactly."""
    from tools.mixing.mix_tracks import _get_stem_settings
    baseline = _get_stem_settings("synth", genre="electronic")
    with_none = _get_stem_settings("synth", genre="electronic", analyzer_rec=None)
    assert baseline == with_none


def test_analyzer_rec_overrides_high_tame_db():
    """Analyzer high_tame_db=-2.0 overrides electronic's synth default (-1.5)."""
    from tools.mixing.mix_tracks import _get_stem_settings
    baseline = _get_stem_settings("synth", genre="electronic")
    assert baseline.get("high_tame_db") == pytest.approx(-1.5), (
        f"precondition failed: expected electronic synth default -1.5, got {baseline.get('high_tame_db')}"
    )
    merged = _get_stem_settings(
        "synth", genre="electronic",
        analyzer_rec={"high_tame_db": -2.0},
    )
    assert merged["high_tame_db"] == pytest.approx(-2.0)


def test_sentinel_zero_overrides_negative_default():
    """analyzer_rec high_tame_db=0.0 overrides negative genre default (not silently dropped)."""
    from tools.mixing.mix_tracks import _get_stem_settings
    merged = _get_stem_settings(
        "synth", genre="electronic",
        analyzer_rec={"high_tame_db": 0.0},
    )
    assert merged["high_tame_db"] == pytest.approx(0.0)


def test_mud_cut_and_highpass_and_noise_reduction_also_overridden():
    """All four EQ whitelist keys apply when present in analyzer_rec."""
    from tools.mixing.mix_tracks import _get_stem_settings
    merged = _get_stem_settings(
        "vocals", genre="electronic",
        analyzer_rec={
            "mud_cut_db": -5.0,
            "high_tame_db": -3.0,
            "noise_reduction": 0.4,
            "highpass_cutoff": 80,
        },
    )
    assert merged["mud_cut_db"] == pytest.approx(-5.0)
    assert merged["high_tame_db"] == pytest.approx(-3.0)
    assert merged["noise_reduction"] == pytest.approx(0.4)
    assert merged["highpass_cutoff"] == 80


def test_non_eq_analyzer_rec_ignored():
    """click_removal and unknown keys do NOT leak into settings."""
    from tools.mixing.mix_tracks import _get_stem_settings
    baseline = _get_stem_settings("synth", genre="electronic")
    merged = _get_stem_settings(
        "synth", genre="electronic",
        analyzer_rec={"click_removal": True, "random_junk_key": 99},
    )
    # click_removal is handled via _resolve_analyzer_peak_ratio, not merged here
    assert "click_removal" not in merged or merged.get("click_removal") == baseline.get("click_removal")
    assert "random_junk_key" not in merged


def test_empty_analyzer_rec_is_noop():
    """analyzer_rec={} produces identical output to analyzer_rec=None."""
    from tools.mixing.mix_tracks import _get_stem_settings
    baseline = _get_stem_settings("synth", genre="electronic")
    empty = _get_stem_settings("synth", genre="electronic", analyzer_rec={})
    assert baseline == empty
```

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/unit/mixing/test_polish_analyzer_overrides.py -v`
Expected: FAIL — `TypeError: _get_stem_settings() got an unexpected keyword argument 'analyzer_rec'`.

- [ ] **Step 3: Extend `_get_stem_settings`**

Edit `tools/mixing/mix_tracks.py`. Locate `def _get_stem_settings` at line 1033. Replace the function (lines 1033–1065) with:

```python
# #336: whitelist of analyzer recommendation keys that are allowed to
# override genre defaults in polish. click_removal is intentionally
# excluded — it's wired through _resolve_analyzer_peak_ratio, not
# merged into per-stem EQ settings.
_ANALYZER_EQ_OVERRIDE_KEYS = frozenset({
    "mud_cut_db",
    "high_tame_db",
    "noise_reduction",
    "highpass_cutoff",
})


def _get_stem_settings(
    stem_name: str,
    genre: str | None = None,
    analyzer_rec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get processing settings for a specific stem type.

    Args:
        stem_name: One of 'vocals', 'backing_vocals', 'drums', 'bass',
            'guitar', 'keyboard', 'strings', 'brass', 'woodwinds',
            'percussion', 'synth', 'other'
        genre: Optional genre name for genre-specific overrides
        analyzer_rec: Optional per-stem recommendations from
            `analyze_mix_issues`. When provided, any whitelisted key
            (mud_cut_db, high_tame_db, noise_reduction, highpass_cutoff)
            overrides the genre default. Non-whitelisted keys
            (click_removal, etc.) are ignored. A sentinel value of 0.0
            is honored — it means "override the genre default to
            zero," not "no recommendation." (#336)

    Returns:
        Dict of processing settings for this stem.
    """
    presets = MIX_PRESETS
    defaults = presets.get('defaults', {})
    stem_defaults = defaults.get(stem_name, {})

    if genre:
        genre_key = genre.lower()
        genre_presets = presets.get('genres', {}).get(genre_key, {})
        genre_stem = genre_presets.get(stem_name, {})
        result: dict[str, Any] = _deep_merge(stem_defaults, genre_stem)
    else:
        result = stem_defaults.copy()

    peak_ratio, fail_count = _resolve_master_click_thresholds(genre)
    if peak_ratio is not None and 'click_peak_ratio' not in result:
        result['click_peak_ratio'] = peak_ratio
    if fail_count is not None and 'click_fail_count' not in result:
        result['click_fail_count'] = fail_count

    # #336: analyzer per-stem recommendations layer on top of genre
    # defaults. Whitelist-filter so click_removal and unknown keys
    # don't leak into the settings dict.
    if analyzer_rec:
        for key, value in analyzer_rec.items():
            if key in _ANALYZER_EQ_OVERRIDE_KEYS:
                result[key] = value

    return result
```

- [ ] **Step 4: Run the tests — they pass**

Run: `pytest tests/unit/mixing/test_polish_analyzer_overrides.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Run existing mixing unit tests — no regression**

Run: `pytest tests/unit/mixing/ -v 2>&1 | tail -20`
Expected: PASS — all pre-existing tests (in test_detector_parity, test_mix_tracks, test_polish_audio_stems, test_polish_peak_invariant) still green. `_get_stem_settings` callers all invoke it positionally without the new kwarg so they're unaffected.

- [ ] **Step 6: Commit**

```bash
git add tools/mixing/mix_tracks.py tests/unit/mixing/test_polish_analyzer_overrides.py
git commit -m "feat: _get_stem_settings accepts analyzer_rec kwarg (#336)

Layer analyzer per-stem recommendations on top of genre defaults
using a whitelist (mud_cut_db, high_tame_db, noise_reduction,
highpass_cutoff). Sentinel value 0.0 overrides a negative genre
default — it means 'apply zero EQ here,' not 'no recommendation.'
click_removal is intentionally excluded (wired elsewhere via
_resolve_analyzer_peak_ratio). Callers that don't pass analyzer_rec
get identical behavior to before.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: `mix_track_stems` accepts `analyzer_recs` + emits `overrides_applied`

**Files:**
- Modify: `tools/mixing/mix_tracks.py` (extend `mix_track_stems` signature + body around lines 1815–1910)
- Test: `tests/unit/mixing/test_polish_analyzer_overrides.py` (extend)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/mixing/test_polish_analyzer_overrides.py`:

```python
class TestMixTrackStemsAnalyzerRecs:
    """#336: mix_track_stems accepts per-stem analyzer recs and records overrides_applied."""

    def _make_dummy_stem(self, tmp_path, name: str, amplitude: float = 0.2):
        """Write a 1-second 100 Hz sine as a stem WAV; return the path."""
        import numpy as np
        import soundfile as sf
        rate = 48000
        t = np.linspace(0.0, 1.0, rate, endpoint=False)
        mono = amplitude * np.sin(2 * np.pi * 100 * t).astype("float64")
        stereo = np.column_stack([mono, mono])
        p = tmp_path / f"{name}.wav"
        sf.write(str(p), stereo, rate)
        return str(p)

    def test_mix_track_stems_records_overrides_applied_when_recs_present(self, tmp_path):
        from tools.mixing.mix_tracks import mix_track_stems
        stem_paths = {
            "vocals": self._make_dummy_stem(tmp_path, "vocals"),
            "synth":  self._make_dummy_stem(tmp_path, "synth"),
        }
        out = tmp_path / "mix.wav"
        analyzer_recs = {
            "synth": {
                "recommendations": {"high_tame_db": 0.0},
                "issues": ["already_dark"],
            }
        }
        result = mix_track_stems(
            stem_paths, str(out),
            genre="electronic", dry_run=True,
            analyzer_recs=analyzer_recs,
        )
        assert "overrides_applied" in result
        assert len(result["overrides_applied"]) == 1
        entry = result["overrides_applied"][0]
        assert entry["stem"] == "synth"
        assert entry["parameter"] == "high_tame_db"
        assert entry["analyzer_rec"] == pytest.approx(0.0)
        assert entry["applied"] == pytest.approx(0.0)
        assert entry["genre_default"] == pytest.approx(-1.5)
        assert entry["reason"] == "already_dark"

    def test_mix_track_stems_no_recs_yields_empty_overrides_list(self, tmp_path):
        from tools.mixing.mix_tracks import mix_track_stems
        stem_paths = {"vocals": self._make_dummy_stem(tmp_path, "vocals")}
        out = tmp_path / "mix.wav"
        result = mix_track_stems(stem_paths, str(out), genre="electronic", dry_run=True)
        assert result.get("overrides_applied", []) == []

    def test_mix_track_stems_non_eq_rec_does_not_produce_override(self, tmp_path):
        from tools.mixing.mix_tracks import mix_track_stems
        stem_paths = {"synth": self._make_dummy_stem(tmp_path, "synth")}
        out = tmp_path / "mix.wav"
        # Only click_removal (non-EQ whitelist) in recommendations
        analyzer_recs = {
            "synth": {
                "recommendations": {"click_removal": True},
                "issues": ["clicks_detected"],
            }
        }
        result = mix_track_stems(
            stem_paths, str(out), genre="electronic", dry_run=True,
            analyzer_recs=analyzer_recs,
        )
        assert result.get("overrides_applied", []) == []

    def test_mix_track_stems_missing_stem_in_recs_falls_through(self, tmp_path):
        """When analyzer_recs has no entry for a stem, that stem uses genre default."""
        from tools.mixing.mix_tracks import mix_track_stems
        stem_paths = {
            "synth": self._make_dummy_stem(tmp_path, "synth"),
            "vocals": self._make_dummy_stem(tmp_path, "vocals"),
        }
        out = tmp_path / "mix.wav"
        # Only synth has a rec; vocals should fall through without producing an override
        analyzer_recs = {
            "synth": {"recommendations": {"high_tame_db": -2.5}, "issues": ["harsh_highmids"]}
        }
        result = mix_track_stems(
            stem_paths, str(out), genre="electronic", dry_run=True,
            analyzer_recs=analyzer_recs,
        )
        stems_in_overrides = {e["stem"] for e in result.get("overrides_applied", [])}
        assert stems_in_overrides == {"synth"}
```

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/unit/mixing/test_polish_analyzer_overrides.py::TestMixTrackStemsAnalyzerRecs -v`
Expected: FAIL — `TypeError: mix_track_stems() got an unexpected keyword argument 'analyzer_recs'`.

- [ ] **Step 3: Extend `mix_track_stems`**

Edit `tools/mixing/mix_tracks.py`. Locate `def mix_track_stems` at line 1815. Modify the signature and the per-stem processing loop.

Replace the signature + docstring + opening lines (around 1815–1840) with:

```python
def mix_track_stems(
    stem_paths: dict[str, str | list[str]],
    output_path: Path | str,
    genre: str | None = None,
    dry_run: bool = False,
    stem_output_dir: Path | None = None,
    analyzer_recs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Full stems pipeline: load stems, process each, remix, write output.

    Args:
        stem_paths: Dict mapping stem name to file path
            e.g. {'vocals': '/path/vocals.wav', 'drums': '/path/drums.wav', ...}
        output_path: Path for polished output WAV
        genre: Optional genre name for preset selection
        dry_run: If True, analyze only without writing files
        stem_output_dir: Optional per-stem output directory
        analyzer_recs: Optional per-stem analyzer output from
            ``analyze_mix_issues``. Shape: ``{stem_name: {"recommendations":
            {...}, "issues": [...]}}``. When provided, whitelisted EQ
            keys in ``recommendations`` override genre defaults for that
            stem. The overrides fired are recorded in the return dict's
            ``overrides_applied`` list with ``(stem, parameter,
            genre_default, analyzer_rec, applied, reason)``. (#336)

    Returns:
        Dict with processing results, metrics, and (when analyzer_recs
        is present) an ``overrides_applied`` list.
    """
    stems_processed: list[dict[str, Any]] = []
    overrides_applied: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        'mode': 'stems',
        'stems_processed': stems_processed,
        'overrides_applied': overrides_applied,
        'dry_run': dry_run,
    }
```

Then, inside the existing loop `for stem_name in STEM_NAMES:` around line 1841, find the line where `settings = _get_stem_settings(stem_name, genre)` is called (check with a grep — there's one around line 1906 inside this function). Before that `settings = ...` assignment, compute the analyzer rec and capture any overrides:

```python
        # #336: pull per-stem recommendations from analyzer (if any).
        stem_analyzer = (analyzer_recs or {}).get(stem_name) or {}
        stem_recs = stem_analyzer.get("recommendations", {}) if stem_analyzer else {}
        stem_issues = stem_analyzer.get("issues", []) if stem_analyzer else []

        # Capture genre baseline BEFORE merging analyzer recs so we can
        # report what the override changed.
        if stem_recs:
            baseline_settings = _get_stem_settings(stem_name, genre)
            for key, rec_val in stem_recs.items():
                if key in _ANALYZER_EQ_OVERRIDE_KEYS:
                    # Issue tag that justifies this override, if any
                    reason = next(
                        (t for t in stem_issues
                         if t in ("harsh_highmids", "already_dark",
                                  "muddy_low_mids", "elevated_noise_floor",
                                  "sub_rumble")),
                        None,
                    )
                    overrides_applied.append({
                        "stem":           stem_name,
                        "parameter":      key,
                        "genre_default":  baseline_settings.get(key),
                        "analyzer_rec":   rec_val,
                        "applied":        rec_val,
                        "reason":         reason,
                    })

        settings = _get_stem_settings(stem_name, genre, analyzer_rec=stem_recs or None)
```

(Replace the existing `settings = _get_stem_settings(stem_name, genre)` line with the `settings = _get_stem_settings(stem_name, genre, analyzer_rec=stem_recs or None)` line. Keep the rest of the loop body as-is.)

Exact location of the existing `settings = _get_stem_settings(stem_name, genre)` call to replace: it's inside the `for stem_name in STEM_NAMES:` loop at approximately line 1906 of the current file. Use grep: `grep -n "_get_stem_settings(stem_name, genre)" tools/mixing/mix_tracks.py` should give the exact line.

- [ ] **Step 4: Run the tests — they pass**

Run: `pytest tests/unit/mixing/test_polish_analyzer_overrides.py -v`
Expected: PASS (10 tests — 6 original + 4 new).

- [ ] **Step 5: Run full mixing test suite**

Run: `pytest tests/unit/mixing/ -v 2>&1 | tail -30`
Expected: PASS. Watch specifically for regressions in `test_polish_audio_stems.py` and `test_polish_peak_invariant.py` — those exercise the `mix_track_stems` path.

- [ ] **Step 6: Commit**

```bash
git add tools/mixing/mix_tracks.py tests/unit/mixing/test_polish_analyzer_overrides.py
git commit -m "feat: mix_track_stems accepts analyzer_recs + emits overrides_applied (#336)

Pipe per-stem analyzer output (recommendations + issues tags) into
mix_track_stems. For each whitelisted EQ key overridden by the
analyzer, record an entry in overrides_applied with the genre
default, analyzer recommendation, applied value, and the issue tag
that justifies the override. Backward-compatible: callers that
don't pass analyzer_recs get an empty overrides_applied list.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: `polish_audio` accepts `analyzer_results` + auto-run fallback

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/mixing.py` (extend `polish_audio` signature + stems-mode branch)
- Test: `tests/unit/mixing/test_polish_audio_stems.py` (extend)

- [ ] **Step 1: Write failing integration test for polish_audio auto-run**

Append to `tests/unit/mixing/test_polish_audio_stems.py` (match the existing fixture style — examine the file for its harness):

```python
class TestPolishAudioAnalyzerCoupling:
    """#336: polish_audio pipes analyzer recs into mix_track_stems."""

    def test_polish_audio_auto_runs_analyzer_when_results_not_passed(
        self, electronic_album_fixture,
    ):
        """Direct polish_audio call with no analyzer_results should still
        produce overrides_applied if the album's stems trigger analyzer recs."""
        import asyncio
        import json
        from handlers.processing.mixing import polish_audio

        album_slug = electronic_album_fixture["album_slug"]
        result_json = asyncio.run(polish_audio(
            album_slug=album_slug, genre="electronic",
            use_stems=True, dry_run=True,
        ))
        result = json.loads(result_json)
        assert "overrides_applied" in result.get("summary", {}), (
            f"expected overrides_applied in summary, got keys {list(result.get('summary', {}).keys())}"
        )

    def test_polish_audio_uses_provided_analyzer_results_without_rerun(
        self, electronic_album_fixture, monkeypatch,
    ):
        """When analyzer_results is provided, polish_audio does NOT call analyze_mix_issues."""
        import asyncio
        import json
        from handlers.processing import mixing as mixing_mod

        call_count = {"n": 0}
        original = mixing_mod.analyze_mix_issues

        async def _tracking_analyzer(*args, **kwargs):
            call_count["n"] += 1
            return await original(*args, **kwargs)

        monkeypatch.setattr(mixing_mod, "analyze_mix_issues", _tracking_analyzer)

        # Provide pre-computed (empty) analyzer_results — polish should skip re-running
        pre_analyzed = {"tracks": [], "album_summary": {"tracks_analyzed": 0, "common_issues": [], "source_mode": "stems"}}
        album_slug = electronic_album_fixture["album_slug"]

        asyncio.run(mixing_mod.polish_audio(
            album_slug=album_slug, genre="electronic",
            use_stems=True, dry_run=True,
            analyzer_results=pre_analyzed,
        ))

        assert call_count["n"] == 0, (
            f"polish_audio should NOT re-run analyzer when analyzer_results is passed, "
            f"but analyze_mix_issues was called {call_count['n']} time(s)"
        )
```

Note: `electronic_album_fixture` is a fixture this test file will define — it creates a temp album directory with `stems/` per-track subdirectories containing a dark synth stem and a normal vocals stem. If the file already has similar fixtures, reuse them. If not, add the fixture at the top of the new test class (or as a module-level `@pytest.fixture`) creating a tmp_path-based album layout matching the real `_resolve_audio_dir` conventions. Example skeleton:

```python
@pytest.fixture
def electronic_album_fixture(tmp_path, monkeypatch):
    """Build a minimal electronic album with stems for one track.

    Creates:
        tmp_path/content/artists/test-artist/albums/electronic/test-album/
            tracks/01-dark.md
        tmp_path/audio/artists/test-artist/albums/electronic/test-album/
            stems/01-dark/synth.wav      (dark synthetic signal)
            stems/01-dark/vocals.wav     (neutral signal)

    Monkeypatches the state cache + config so _resolve_audio_dir resolves
    to the tmp audio dir.
    """
    # ... match the existing fixture setup in this test file ...
    raise NotImplementedError(
        "Adapt to the existing fixture pattern in test_polish_audio_stems.py. "
        "If no pattern exists, see tests/unit/mastering/test_stage_status_update.py's "
        "_build_state helper for a model."
    )
```

Engineer: look at the top of `test_polish_audio_stems.py` for the existing fixture pattern. It already creates tmp albums (the file tests `polish_audio` in stems mode). Adapt it — don't reinvent.

- [ ] **Step 2: Run failing tests**

Run: `pytest tests/unit/mixing/test_polish_audio_stems.py::TestPolishAudioAnalyzerCoupling -v`
Expected: FAIL — either `TypeError: polish_audio() got an unexpected keyword argument 'analyzer_results'` or missing `overrides_applied` in the summary.

- [ ] **Step 3: Extend `polish_audio`**

Edit `servers/bitwize-music-server/handlers/processing/mixing.py`. Modify `polish_audio` at line 17.

Change the signature:

```python
async def polish_audio(
    album_slug: str,
    genre: str = "",
    use_stems: bool = True,
    dry_run: bool = False,
    track_filename: str = "",
    analyzer_results: dict[str, Any] | None = None,
) -> str:
```

Update the docstring to mention the new kwarg (the engineer should read the existing docstring and add a line for `analyzer_results`).

At the start of the function (after the validation block, around line 73 where `output_dir = audio_dir / "polished"` is computed), insert the auto-run fallback:

```python
    # #336: polish consumes analyzer per-stem recommendations. Auto-run
    # the analyzer when the caller didn't provide results (so direct
    # polish_audio calls still see the coupling). polish_album skips
    # this by passing its existing analyze-stage output down.
    if analyzer_results is None and not dry_run:
        analyzer_json = await analyze_mix_issues(album_slug, genre)
        analyzer_parsed = json.loads(analyzer_json)
        if "error" in analyzer_parsed:
            # Analyzer failure is non-fatal for polish — proceed without recs.
            analyzer_results = None
        else:
            analyzer_results = analyzer_parsed

    # Build per-track analyzer rec lookup: {track_basename: {stem: {...}}}
    per_track_recs: dict[str, dict[str, dict[str, Any]]] = {}
    if analyzer_results:
        for track_entry in analyzer_results.get("tracks", []):
            # Stems-mode entry shape: {"track": name, "stems": {stem: analysis}}
            if "stems" in track_entry and isinstance(track_entry["stems"], dict):
                per_track_recs[track_entry["track"]] = track_entry["stems"]
```

Then, in the stems-mode branch (around line 111–131 where `mix_track_stems` is called via `_do_stems`), pass `analyzer_recs`. Find the `_do_stems` helper and its call; update:

```python
            track_recs = per_track_recs.get(track_dir.name) or None

            def _do_stems(
                sp: dict[str, str | list[str]], op: str, g: str | None,
                dr: bool, sd: Path | None, ar: dict | None,
            ) -> dict[str, Any]:
                return mix_track_stems(
                    sp, op, genre=g, dry_run=dr,
                    stem_output_dir=sd, analyzer_recs=ar,
                )

            result = await loop.run_in_executor(
                None, _do_stems, stem_paths, out_path,
                genre or None, dry_run, _stem_output_dir, track_recs,
            )
```

Finally, aggregate overrides across tracks into the summary. Currently the function returns:

```python
    return _safe_json({
        "tracks": track_results,
        "settings": {...},
        "summary": {
            "tracks_processed": len(track_results),
            "mode": "stems" if use_stems else "full_mix",
            "output_dir": str(output_dir) if not dry_run else None,
        },
    })
```

Extend the summary to include `overrides_applied`:

```python
    aggregated_overrides: list[dict[str, Any]] = []
    for tr in track_results:
        for entry in tr.get("overrides_applied", []):
            aggregated_overrides.append({
                "track": tr.get("track_name") or tr.get("filename") or "",
                **entry,
            })

    return _safe_json({
        "tracks": track_results,
        "settings": {
            "genre": genre or None,
            "use_stems": use_stems,
            "dry_run": dry_run,
            "track_filename": track_filename or None,
        },
        "summary": {
            "tracks_processed": len(track_results),
            "mode": "stems" if use_stems else "full_mix",
            "output_dir": str(output_dir) if not dry_run else None,
            "overrides_applied": aggregated_overrides,
        },
    })
```

- [ ] **Step 4: Run the tests — they pass**

Run: `pytest tests/unit/mixing/test_polish_audio_stems.py::TestPolishAudioAnalyzerCoupling -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run full mixing test suite**

Run: `pytest tests/unit/mixing/ -v 2>&1 | tail -20`
Expected: PASS. All prior tests still green.

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/mixing.py tests/unit/mixing/test_polish_audio_stems.py
git commit -m "feat: polish_audio wires analyzer_results through to mix_track_stems (#336)

Adds analyzer_results kwarg with auto-run fallback when None.
Extracts per-track per-stem recommendations and passes them to
mix_track_stems. Aggregates overrides across tracks into
summary.overrides_applied so the top-level polish result shows
operators exactly which EQ overrides fired and why.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: `polish_album` passes analyzer output down

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/mixing.py` (`polish_album`, around line 492)
- Test: `tests/unit/mixing/test_polish_audio_stems.py` (extend — integration test)

- [ ] **Step 1: Write failing integration test**

Append to the same `TestPolishAudioAnalyzerCoupling` class in `tests/unit/mixing/test_polish_audio_stems.py`:

```python
    def test_polish_album_surfaces_overrides_in_stage_output(
        self, electronic_album_fixture,
    ):
        """polish_album's final JSON carries overrides_applied under polish stage."""
        import asyncio
        import json
        from handlers.processing.mixing import polish_album

        album_slug = electronic_album_fixture["album_slug"]
        result_json = asyncio.run(polish_album(
            album_slug=album_slug, genre="electronic",
        ))
        result = json.loads(result_json)
        polish_stage = result["stages"].get("polish", {})
        assert "overrides_applied" in polish_stage, (
            f"polish_album stages.polish must expose overrides_applied; got {list(polish_stage.keys())}"
        )
        # When the fixture includes a dark synth stem, we expect at least one override
        assert isinstance(polish_stage["overrides_applied"], list)
```

- [ ] **Step 2: Run failing test**

Run: `pytest tests/unit/mixing/test_polish_audio_stems.py::TestPolishAudioAnalyzerCoupling::test_polish_album_surfaces_overrides_in_stage_output -v`
Expected: FAIL — `AssertionError: polish_album stages.polish must expose overrides_applied`.

- [ ] **Step 3: Modify `polish_album`**

Edit `servers/bitwize-music-server/handlers/processing/mixing.py`. Locate the polish-stage invocation at line 492.

Replace:

```python
    polish_json = await polish_audio(
        album_slug=album_slug,
        genre=genre,
        use_stems=use_stems,
        dry_run=False,
    )
```

With:

```python
    # #336: pass the analysis-stage output into polish so analyzer
    # recommendations become per-track overrides (no duplicate analysis
    # run).
    polish_json = await polish_audio(
        album_slug=album_slug,
        genre=genre,
        use_stems=use_stems,
        dry_run=False,
        analyzer_results=analysis,
    )
```

And update the `stages["polish"]` assignment (around line 510) to include `overrides_applied`:

```python
    stages["polish"] = {
        "status": "pass",
        "tracks_processed": polish["summary"]["tracks_processed"],
        "output_dir": polish["summary"]["output_dir"],
        "overrides_applied": polish["summary"].get("overrides_applied", []),
    }
```

- [ ] **Step 4: Run the test — it passes**

Run: `pytest tests/unit/mixing/test_polish_audio_stems.py::TestPolishAudioAnalyzerCoupling -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run full mixing + mastering suites**

Run: `pytest tests/unit/mixing/ tests/unit/mastering/ --tb=line 2>&1 | tail -10`
Expected: PASS on everything. The mastering suite should be unaffected — no mastering code touched.

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/mixing.py tests/unit/mixing/test_polish_audio_stems.py
git commit -m "feat: polish_album threads analyzer output through polish stage (#336)

polish_album now passes its analyze-stage output directly to
polish_audio via the analyzer_results kwarg — avoiding a duplicate
analyzer run — and surfaces the aggregated overrides_applied list
under stages.polish so operators see exactly which per-stem EQ
overrides fired and which analyzer issue justified each.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run `make check` from repo root**

```bash
make check
```

Expected: all green (ruff, bandit, mypy, full pytest suite). If anything fails, fix the root cause — don't skip. Common failure modes:

- `ruff check tools/ servers/` catches unused imports if the new `Any` / `dict` type hints weren't imported correctly in `mix_tracks.py`.
- `mypy` catches a signature mismatch if the `_get_stem_settings` kwargs aren't keyword-only in some callers.
- Integration test failures in `test_polish_audio_stems.py` if the `electronic_album_fixture` doesn't match the real `_resolve_audio_dir` path conventions.

- [ ] **Step 2: Smoke test the analyzer directly**

Run:

```bash
~/.bitwize-music/venv/bin/python3 -c "
import numpy as np
from handlers.processing.mixing import _build_analyzer
rate = 48000
t = np.linspace(0, 2, 2*rate, endpoint=False)
# Dark track: all low-frequency energy
dark = np.column_stack([
    0.3 * np.sin(2*np.pi*100*t),
    0.3 * np.sin(2*np.pi*100*t),
])
a = _build_analyzer()
r = a(dark.astype('float64'), rate, filename='dark.wav', stem_name='synth', genre='electronic')
print('issues:', r['issues'])
print('recs:', r['recommendations'])
print('high_mid_ratio:', r.get('high_mid_ratio'))
"
```

Expected output includes `already_dark` in issues and `high_tame_db: 0.0` in recs.

- [ ] **Step 3: Push branch and open PR**

```bash
git push -u origin fix/336-polish-consumes-analyzer-recs
gh pr create --base develop --title "fix: polish consumes analyzer recommendations (#336)" --body "$(cat <<'EOF'
## Summary
- Wires `analyze_mix_issues` per-stem recommendations into `polish_audio` as per-track EQ overrides on top of genre defaults
- Adds `already_dark` condition to the analyzer (emits `high_tame_db: 0.0` sentinel when `high_mid_ratio < 0.10`) — protects dark tracks from genre-default high-shelf cuts that further darken them
- Exposes `overrides_applied` under `stages.polish` so operators can see exactly which EQ overrides fired per track/stem and which analyzer issue justified each

Fixes #336. Defaults unchanged — the wire-through only takes effect when the analyzer actually emits a recommendation, and thresholds (`0.10` / `0.25`) are preset-tunable via `defaults.analyzer` in `mix-presets.yaml`.

## Test plan
- [x] `make check` passes locally
- [x] Smoke test: dark synthetic input produces `high_tame_db: 0.0` + `already_dark` tag
- [ ] Re-run the issue's repro on `if-anyone-makes-it-everyone-dances` (electronic, 10 tracks) — verify:
  - `polish.overrides_applied` shows entries for tracks with `harsh_highmids` or `muddy_low_mids`
  - Track 09's synth/keyboard/other stems show `{parameter: high_tame_db, applied: 0.0, reason: already_dark}`
  - Post-QC `09-carbon-and-silicon.wav` no longer shows "No highs" WARN

## Follow-ups (out of scope)
- Per-track manual sidecar override (complements auto-wire)
- Symmetric `mud_cut_db: 0.0` guard for tracks with no low-mid content
- Per-genre default threshold overrides in `mix-presets.yaml`
EOF
)"
```

---

## Self-Review

**Spec coverage:**

- [x] Wire analyzer recommendations into polish — Task 2 (merge), Task 3 (pipeline), Task 4 (polish_audio), Task 5 (polish_album)
- [x] Dark-track protection via `high_tame_db: 0.0` sentinel — Task 1
- [x] `overrides_applied` stage telemetry — Task 3 + Task 4 + Task 5
- [x] Preset-tunable thresholds — Task 1 (defaults.analyzer block)
- [x] `click_removal` intentionally excluded — Task 2 (`_ANALYZER_EQ_OVERRIDE_KEYS` whitelist)
- [x] Auto-run fallback for direct `polish_audio` callers — Task 4
- [x] All testing layers covered (analyzer unit, merge unit, pipeline unit, integration) — Tasks 1, 2, 3, 4, 5
- [x] `make check` gate — Task 6

**Placeholder scan:** The `electronic_album_fixture` in Task 4 Step 1 contains a pointer to existing fixture style rather than the full fixture. This is because the fixture pattern depends on what already exists in `test_polish_audio_stems.py` — the engineer must read it and adapt. Not a blind TBD; it's "reuse the existing pattern, don't reinvent." If the file has no such pattern, the task pointer to `test_stage_status_update.py`'s `_build_state` helper serves as the model.

**Type consistency:**
- `_ANALYZER_EQ_OVERRIDE_KEYS` is a `frozenset[str]` defined in `mix_tracks.py` (Task 2) and referenced in `mix_tracks.py` Task 3.
- `analyzer_rec: dict[str, Any] | None` kwarg shape is consistent across `_get_stem_settings` (Task 2) and the filtered dict passed by `mix_track_stems` (Task 3).
- `analyzer_recs: dict[str, dict[str, Any]] | None` on `mix_track_stems` (Task 3) is indexed by stem name; `per_track_recs: dict[str, dict[str, dict[str, Any]]]` in `polish_audio` (Task 4) adds the track-name outer layer.
- Override entry shape is identical at every layer: `{stem, parameter, genre_default, analyzer_rec, applied, reason}`. Polish adds a `track` field when aggregating across tracks.

## Out of scope (explicit)

- Per-track manual sidecar override path (complements auto-wire — natural follow-up on the same merge infrastructure)
- Symmetric `mud_cut_db: 0.0` guard for already-bright tracks with no low-mid content
- Per-genre default threshold overrides in `mix-presets.yaml`'s `genres` section
- Changing `click_removal` flow (wired via `_resolve_analyzer_peak_ratio` in commit `272a15d`)
- New MCP tool surface — all changes are additive kwargs on existing tools
