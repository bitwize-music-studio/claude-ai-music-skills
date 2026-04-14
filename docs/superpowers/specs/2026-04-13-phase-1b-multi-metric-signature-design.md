# Phase 1b — Multi-Metric Signature Foundation (Design)

**Canonical spec**: [Issue #290](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/290)
**Parent design**: [`2026-04-13-album-mastering-pipeline-design.md`](2026-04-13-album-mastering-pipeline-design.md)
**Phase**: 1b (follows 1a in #304)
**Design date**: 2026-04-13

## Summary

Extend `analyze_track()` with three new signature metrics — STL-95, low-RMS (STL-95-windowed, 20–200 Hz), and vocal-RMS (polished vocal stem when present, else 1–4 kHz band of full mix) — and a small `signature_meta` dict recording provenance. Purely additive return schema; no new MCP tool; no pipeline stage changes. These fields are the inputs that Phase 2a (anchor selector) and Phase 2b (album coherence check/correct) consume.

## Architectural context

- Core metric computation lives in `tools/mastering/analyze_tracks.py` (pure Python, no MCP coupling).
- MCP boundary stays thin in `servers/bitwize-music-server/handlers/processing/audio.py`. The `analyze_audio` handler gains one optional kwarg (`vocal_stem_path`) and passes it through.
- No consumers in Phase 1b. Phase 2a and 2b read these fields.
- Fields are **additive**: existing tests and callers only assert on fields they care about, so adding keys cannot regress them.

## Design decisions

### Vocal-RMS source — honor spec path, graceful fallback

Spec (`#290` Multi-metric table footnote ‡) says measure the polished vocal stem at `polished/<track>/vocals.wav` when present, else the 1–4 kHz band of the full mix. Today, `polish_audio` writes only a single mixed stereo WAV at `polished/<track>.wav`; the per-stem subdirectory does not exist. That means the band fallback always fires today.

Phase 1b implements the spec as written. When `polished/<track>/vocals.wav` eventually exists (separate polish upgrade, tracked as a follow-up), stem measurement activates automatically with no further changes to this code path.

Alternatives rejected:

- **Read pre-polish stems** (`stems/<track>/vocals.wav`) — they exist today but are unpolished, so the measurement drifts from what the mastered track contains. Partially defeats the purpose.
- **Scope-creep polish** to preserve per-stem output — bundles a polish stage change into a metrics-only PR. Clean standalone follow-up instead.

### Return schema — additive flat scalars + `signature_meta`

Three new top-level scalar fields (`stl_95`, `low_rms`, `vocal_rms`) plus a `signature_meta` dict for provenance. Scalars follow existing flat-key convention in `analyze_track()`'s return dict. The meta dict keeps provenance separate so downstream consumers can branch on `vocal_rms_source` without parsing magic numbers.

### Metric algorithms

**STL-95**: reuse existing 3 s window / 1 s hop short-term LUFS loop at `analyze_tracks.py:86–95`. Collect all finite ST-LUFS values into a list. Return `np.percentile(values, 95)` (numpy default linear interpolation). Retain the indices of the top-K windows for reuse by low-RMS, where `K = max(1, round(0.05 * N))` (rounded to nearest, min 1). Sort descending by ST-LUFS; ties broken by window index ascending (earlier window wins) for determinism.

**Gating**: return `None` when fewer than 20 finite ST windows exist. Rationale: at 20 windows (≈23 s of audio) the 95th percentile spans exactly one sample; below that the percentile reports the maximum, which is the wrong statistic. The `stl_window_count` field in `signature_meta` makes the gate visible.

**low-RMS (20–200 Hz)**:
- Butterworth bandpass, 4th order, zero-phase via `scipy.signal.sosfiltfilt`, `sos` form for numeric stability.
- For each top-5% window (indices retained from STL-95), compute RMS in dB on the filtered mono mixdown of that window.
- Return the **median** across those windows. Robust to a single outlier chorus.
- Return `None` when `stl_95` is `None`.

**vocal-RMS**:
- **Stem path**: if `vocal_stem_path` resolves and reads successfully → mono mixdown of the stem, whole-stem RMS in dB. `vocal_rms_source = "stem"`.
- **Band fallback**: 1–4 kHz Butterworth bandpass (4th order, `sosfiltfilt`) on full-mix mono, whole-track RMS in dB. `vocal_rms_source = "band_fallback"`.
- **Unavailable**: silent / unreadable / unresolvable → `None`, `vocal_rms_source = "unavailable"`.

Whole-track (not windowed) is the spec wording: *"measured directly on the polished vocal stem"* and *"1–4 kHz band of the full mix"* — neither mentions STL-95 windowing. Window alignment can be added later if empirical tuning finds it necessary; the return schema is forward-compatible.

### Stem auto-resolve

`analyze_track()` gains an optional `vocal_stem_path` kwarg. When explicitly passed, it's used directly. When omitted, resolve by convention — check, in order:

1. `<input_dir>/polished/<input_stem>/vocals.wav` — input is at album root.
2. `<input_dir>/../polished/<input_stem>/vocals.wav` — input is in a `mastered/` or `polished/` subfolder.

First hit wins; no hit → fall back to band. Walking two levels covers every current layout (raw at album root, polished output, mastered output) without touching the wider filesystem.

The handler `analyze_audio` accepts the same optional kwarg and passes it through. This keeps analyze_audio usable without extra context while letting Phase 2 callers (anchor selector, coherence check) be explicit when they already know the stem path.

## Interface

### `tools/mastering/analyze_tracks.py`

```python
def analyze_track(
    filepath: Path | str,
    *,
    vocal_stem_path: Path | str | None = None,
) -> dict[str, Any]:
    ...
```

New return keys (all others unchanged):

```python
{
    # ... existing fields unchanged ...
    'stl_95': float | None,
    'low_rms': float | None,
    'vocal_rms': float | None,
    'signature_meta': {
        'stl_window_count': int,
        'stl_top_5pct_count': int,
        'vocal_rms_source': 'stem' | 'band_fallback' | 'unavailable',
    },
}
```

### `servers/bitwize-music-server/handlers/processing/audio.py`

```python
async def analyze_audio(
    audio_path: str,
    *,
    vocal_stem_path: str | None = None,
) -> str:
    ...
```

MCP schema is implicit from the Python signature; existing callers that don't pass `vocal_stem_path` get the auto-resolve behavior.

## Error handling

- **Track < ~23 s (20 ST windows)** → `stl_95 = None`, `low_rms = None`. Visible via `stl_window_count` in `signature_meta`.
- **Stem file exists but unreadable** → log warning, fall back to band. Do not crash.
- **Stem at a different sample rate** → resample to mix rate before RMS. If resample fails, fall back.
- **Stem is mono** → existing mono→stereo duplication in `analyze_track()` handles it when reading; whole-stem mono mixdown for RMS normalizes regardless.
- **Silent audio** → `rms = 0` → `rms_db` = `-inf` (matches existing behavior). All three new fields return `None` or `"unavailable"`.

## Testing

Model after `tests/unit/mastering/test_analyze_tracks.py`. Use existing `_generate_sine()` and `_write_wav()` helpers.

**New file `tests/unit/mastering/test_signature_metrics.py`:**

- `TestShortTerm95`
  - Constant-level sine → `stl_95` within 1 LU of integrated LUFS.
  - Chorus/verse pattern (loud 3 s burst every 8 s) → `stl_95 > lufs + 2`.
  - Track < 23 s → `stl_95 is None`, `stl_window_count < 20`.
  - Silent track → `stl_95 is None`.

- `TestLowRms`
  - Bass-heavy loud windows + quiet verses → median low-RMS reflects bass chorus level, not whole-track.
  - Full-track silence → `low_rms is None`.
  - `stl_95 is None` implies `low_rms is None`.

- `TestVocalRms`
  - Stem at known level adjacent to input → `vocal_rms_source == "stem"`, value within 1 dB of expected.
  - Explicit `vocal_stem_path` kwarg → honored over auto-resolve.
  - No stem, 1–4 kHz-rich mix → `vocal_rms_source == "band_fallback"`, finite value.
  - Stem at 48 kHz, input at 96 kHz → resample path produces finite value.
  - Stem is an invalid WAV → logged, falls back to band.

**New file `tests/unit/mastering/test_analyze_audio_vocal_stem.py`:**

- Auto-resolve hit: create temp `polished/<name>/vocals.wav` alongside input; confirm `vocal_rms_source == "stem"`.
- Auto-resolve miss: no stem dir; confirm `vocal_rms_source == "band_fallback"`.

## File structure

**Create:**
- `tests/unit/mastering/test_signature_metrics.py`
- `tests/unit/mastering/test_analyze_audio_vocal_stem.py`

**Modify:**
- `tools/mastering/analyze_tracks.py` — extend `analyze_track()` with STL-95, low-RMS, vocal-RMS, `signature_meta`; add `vocal_stem_path` kwarg.
- `servers/bitwize-music-server/handlers/processing/audio.py` — pass `vocal_stem_path` through `analyze_audio`.
- `config/config.example.yaml` — fold in E2 review item: disk-usage note on `delivery_sample_rate` comment.

## Out of scope / follow-ups

- **Polish preserves per-stem output** (new `polished/<track>/vocals.wav` artifact). Required before stem measurement activates in practice. Filed as a new #290 checklist item when this PR lands.
- **Anchor selector** (Phase 2a) — consumes `stl_95`, `low_rms`, `vocal_rms`.
- **Album coherence check/correct** (Phase 2b) — consumes signature across a track set.
- **Genre coherence tolerance fields** (`coherence_stl_95_lu`, `coherence_low_rms_db`, `coherence_vocal_rms_db`) — ship with Phase 2.
- **Whole-track windowing for vocal-RMS** — deferred; trigger is empirical drift, not currently observed.

## Non-goals

- No changes to polish stage.
- No new MCP tool.
- No album-level aggregation (signature persistence is Phase 2c).
- No genre-specific coherence semantics.
- No wiring into `master_album` or `master_audio` pipelines.
