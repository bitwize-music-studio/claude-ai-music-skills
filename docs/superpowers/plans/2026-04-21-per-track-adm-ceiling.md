# Per-Track ADM Ceiling + Dark-Track Exclusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Depends on:** `2026-04-21-auto-recovery-integrity-warn-fallback.md` — this plan extends the same warn-fallback contract to the ADM loop and assumes `converged` + `unrecoverable_tracks` are available. Execute Plan A first and merge it before starting this one.

**Goal:** Stop the ADM loop from punishing clean tracks. When one or two tracks clip the decoded AAC ceiling, tighten only *their* true-peak ceilings and re-master only *those* tracks — not the entire album. Additionally: tracks flagged `already_dark` (high-mid band energy < 10 %) are excluded from ADM tightening entirely, since tightening a limiter on material that has no high-frequency content only pushes it further out of spec while delivering no ADM benefit. Clips on dark tracks are delivered as warn-fallback rows in `ADM_VALIDATION.md`.

**Architecture:** Four additive changes, all contained to the mastering pipeline. (1) `analyze_track` now returns `band_energy` *and* a derived `is_dark: bool` so downstream consumers don't have to repeat the threshold check. (2) `MasterAlbumCtx` gains `track_ceilings: dict[str, float]`, `dark_tracks: set[str]`, and `remaster_filenames: set[str] | None` — all optional, defaulting to "all tracks at scalar ceiling" so existing callers keep working. (3) `_stage_mastering` honors `remaster_filenames` (skip tracks not in the set when it's non-None) and reads per-track ceilings from `track_ceilings`. (4) The ADM loop in `audio.py` partitions clipping tracks into tightenable vs dark, tightens only the tightenable set, and populates `remaster_filenames` for the next cycle. Scalar `effective_ceiling` is preserved as the "default" ceiling used for first-cycle mastering and any non-overridden track.

**Tech Stack:** Python 3.11, existing numpy/scipy/soundfile/pyloudnorm. No new dependencies.

---

## Scope Check

This plan bundles two fixes that are architecturally entangled:
- Bug #3 (global ADM tightening crushes clean tracks) cannot be fixed without per-track ceiling tracking.
- Bug #5 (dark tracks shouldn't be ADM-tightened) shares the same partitioning logic — once you have per-track ceilings, "skip dark tracks" is one `if` branch away.

**Out of scope:**
- Writing a harmonic exciter to synthesize missing highs on dark tracks — that's a substantive DSP change for a separate plan, and is *not* required to fix the halt; warn-fallback delivers the album either way.
- Post-master spectral regression checks (bug #6) — covered in `2026-04-21-post-master-spectral-regression.md`.
- Stage extraction refactor — `_stage_mastering` is ~100 lines and this plan adds ~30; not the right time for a refactor.
- Changing `_ADM_MIN_CEILING_DB`, `_ADM_MAX_TIGHTEN_DB`, or any other ADM step-size constants. Those are policy knobs, not bugs.

---

## Codebase Context

Key files (paths from repo root):

- `servers/bitwize-music-server/handlers/processing/audio.py:740-975` — `master_album`'s ADM loop + `_adm_adaptive_ceiling`.
- `servers/bitwize-music-server/handlers/processing/_album_stages.py:640-750` — `_stage_mastering`.
- `servers/bitwize-music-server/handlers/processing/_album_stages.py:340-452` — `_stage_analysis`.
- `servers/bitwize-music-server/handlers/processing/_album_stages.py:2053-2178` — `_stage_adm_validation`.
- `tools/mastering/analyze_tracks.py:93-280` — `analyze_track` returning band_energy as a % dict.
- `tools/mastering/master_tracks.py:master_track` — per-track mastering entry point; reads ceiling from its preset arg.

**Current ADM loop behavior (today):**

```python
for adm_cycle in range(_ADM_MAX_CYCLES):
    for stage in adm_loop_stages:  # [mastering, verify, coherence*, ceiling_guard, adm_validation]
        if result := await stage(ctx):
            if is_adm_clip_failure(result) and adm_cycle < _ADM_MAX_CYCLES - 1:
                new_ceiling = _adm_adaptive_ceiling(failure_detail, ctx.effective_ceiling)
                ctx.effective_ceiling = new_ceiling           # GLOBAL (bug #3)
                ctx.targets["ceiling_db"] = ctx.effective_ceiling
                ctx.effective_preset["true_peak_ceiling"] = ctx.effective_ceiling
                adm_retry = True
                break
            ...
```

Every cycle, every stage runs for every track. The tightened ceiling is applied to every track on the next cycle's `_stage_mastering`. Observed effect on the reported halt: tracks 1–8 & 10 all landed within 0.06 dB of the final tightened ceiling of −4.42 dBTP, losing ~3 dB of headroom they didn't need to lose.

**ADM clip detail shape (today, produced by `_stage_adm_validation`):**

```python
{
    "tracks_with_clips": [
        {"filename": "03-abc.wav", "peak_db_decoded": -0.6, "encoded_bitrate": 256},
        ...
    ],
    "clips_retry_eligible": True,
    "ceiling_db": -1.5,
}
```

---

## File Structure

| File | Role | State |
|---|---|---|
| `tools/mastering/analyze_tracks.py` | Add `is_dark` to `analyze_track` output (derived from band_energy['high_mid'] < 10.0) | modify |
| `servers/bitwize-music-server/handlers/processing/_album_stages.py` | Populate `ctx.dark_tracks` / `ctx.track_ceilings` in `_stage_analysis`; honor `remaster_filenames` + `track_ceilings` in `_stage_mastering`; note dark-track ADM clips in `_stage_adm_validation` | modify |
| `servers/bitwize-music-server/handlers/processing/audio.py` | Rewrite ADM loop: per-track ceiling tightening, selective remaster set, dark-track ADM warn-fallback | modify |
| `tests/unit/mastering/test_analyze_tracks_is_dark.py` | Unit test for the new field | **new** |
| `tests/unit/mastering/test_master_album_per_track_ceiling.py` | Integration test: clean tracks keep original ceiling when a neighbor clips ADM | **new** |
| `tests/unit/mastering/test_master_album_dark_track_adm.py` | Integration test: dark track clipping ADM → warn-fallback, no tightening applied | **new** |
| `tests/unit/mastering/test_master_album_selective_remaster.py` | Integration test: `_stage_mastering` with `remaster_filenames={'03-…'}` only writes to that one file | **new** |
| `CHANGELOG.md` | `[Unreleased]` entry | modify |

Files **not** modified:
- `tools/mastering/master_tracks.py` — `master_track` already takes a preset; we pass per-track ceiling via that.
- `tools/mastering/coherence.py` / `tools/mastering/ceiling_guard.py` — they consume mastered files; no API change.

---

## Design Details (read before starting any task)

### Dark-track detection in `analyze_track`

`analyze_track` already computes `band_energy['high_mid']` as a **percentage** (0–100). The mix analyzer at `servers/bitwize-music-server/handlers/processing/mixing.py:367-378` uses a parallel measurement on **ratio** scale (0–1) and thresholds at `0.10` (→ 10 %).

Add a derived field to `analyze_track`'s return:

```python
is_dark = band_energy['high_mid'] < 10.0
```

Threshold is **not** configurable here — it matches the mix analyzer's default so the two stages are consistent. Preset-tunable threshold would be a separate phase. The value 10.0 is intentional: dark-enough that an existing `already_dark` flag at polish time almost always co-occurs with this.

### `MasterAlbumCtx` additions

Add three fields to the dataclass. All default to the "nothing overridden" sentinel, so existing callers keep working:

```python
@dataclass
class MasterAlbumCtx:
    # ... existing fields ...
    track_ceilings: dict[str, float] = field(default_factory=dict)
    dark_tracks: set[str] = field(default_factory=set)
    remaster_filenames: set[str] | None = None
```

- `track_ceilings[filename]`: if present, overrides `ctx.effective_ceiling` for that track during `_stage_mastering` and downstream. Absent → use scalar.
- `dark_tracks`: filenames of tracks whose `analyze_track` result has `is_dark=True`. Populated once in `_stage_analysis`; read by the ADM loop.
- `remaster_filenames`: when None, `_stage_mastering` masters every track in `ctx.wav_files`. When set, it only re-masters filenames in the set and leaves existing mastered files alone. Cycle 1 is None; cycle 2+ is the set of non-dark clipping tracks.

### `_stage_mastering` — selective re-mastering

Current flow masters every track in `ctx.wav_files`. New flow:

```python
for wav in ctx.wav_files:
    fname = wav.name
    if ctx.remaster_filenames is not None and fname not in ctx.remaster_filenames:
        # Skip — previous cycle's output is still valid for this track.
        continue

    # Per-track ceiling override
    per_track_ceiling = ctx.track_ceilings.get(fname, ctx.effective_ceiling)
    # ... build preset with true_peak_ceiling = per_track_ceiling ...
    master_track(wav, output_dir, preset_dict=per_track_preset, ...)
```

`ctx.mastered_files` should always reflect the full set of mastered files, not just the re-mastered subset. Skipped tracks already have valid output from the previous cycle — leave their entries in `mastered_files` alone.

### ADM loop rewrite

The current global-tightening block:

```python
new_ceiling, hit_floor, diverging = _adm_adaptive_ceiling(
    adm_last_failure_detail, ctx.effective_ceiling,
)
if diverging: ...
if new_ceiling >= ctx.effective_ceiling: ...
ctx.effective_ceiling = new_ceiling
ctx.targets["ceiling_db"] = ctx.effective_ceiling
ctx.effective_preset["true_peak_ceiling"] = ctx.effective_ceiling
adm_retry = True
```

Replace with a per-track partition:

```python
clip_entries = adm_last_failure_detail.get("tracks_with_clips") or []
clipping_fnames = {e["filename"] for e in clip_entries}

tightenable = clipping_fnames - ctx.dark_tracks
dark_clipping = clipping_fnames & ctx.dark_tracks

if not tightenable:
    # Every clipping track is dark — nothing to tighten. Warn-fallback.
    adm_clip_failure_persisted = True
    break

# Tighten each tightenable track individually.
any_moved = False
for fname in tightenable:
    entry = next(e for e in clip_entries if e["filename"] == fname)
    current = ctx.track_ceilings.get(fname, ctx.effective_ceiling)
    new_ceiling, hit_floor, diverging = _adm_adaptive_ceiling_per_track(
        entry, current, per_track_history[fname],
    )
    if diverging:
        # Per-track divergence: drop this track into dark_clipping for sidecar.
        dark_clipping.add(fname)
        continue
    if new_ceiling >= current:
        continue  # floor reached; nothing changes
    ctx.track_ceilings[fname] = new_ceiling
    any_moved = True

if not any_moved:
    adm_clip_failure_persisted = True
    break

# Next cycle re-masters only the tightenable tracks.
ctx.remaster_filenames = tightenable - dark_clipping
adm_retry = True
```

`_adm_adaptive_ceiling_per_track` is the same math as `_adm_adaptive_ceiling`, but with a per-track `history: list[dict]` argument instead of closing over the module-level `adm_history`. The function in `audio.py` is small enough that inlining a per-track helper adds little complexity; extract it into a module-level function with explicit `history` + `entry` kwargs.

`per_track_history` is a `dict[str, list[dict]]` initialized at loop start.

### Warn-fallback for dark clipping tracks

When dark tracks clip ADM, they can't be tightened further — the limiter is already over-working on material that has no headroom. Document the outcome in `ADM_VALIDATION.md` the same way the existing warn-fallback does, but add a `reason: "dark_track_not_tightened"` row per dark track.

Extend the `ADM_VALIDATION.md` writer (existing code in `_stage_adm_validation` or the orchestrator; audit during Task 4) to include a per-track `reason` column. The current sidecar is a flat list; the new version has an extra column but stays backward-compatible (old tests read filename / peak_db_decoded and those still work).

### Interaction with the verification warn-fallback (Plan A)

The verification stage runs *before* ADM. A dark track that fails verification will warn-fallback there first (if Plan A is merged). It won't reach ADM validation at all on that cycle. But if it *does* converge on verification and *then* clips ADM, this plan's dark-track path handles it.

### First-cycle behavior is preserved

On cycle 1: `remaster_filenames=None` → master everything; `track_ceilings` is empty → every track uses `effective_ceiling`. Byte-for-byte identical to pre-plan behavior for albums where no tracks clip ADM (i.e. the overwhelming majority).

---

## Task 1: `analyze_track` emits `is_dark`

**Files:**
- Modify: `tools/mastering/analyze_tracks.py` (return dict around line 253)
- Test: `tests/unit/mastering/test_analyze_tracks_is_dark.py` (NEW)

- [ ] **Step 1: Write failing test**

Create `tests/unit/mastering/test_analyze_tracks_is_dark.py`:

```python
"""analyze_track must return is_dark=True when high_mid band energy is
below the 10 % threshold used by the mix analyzer's already_dark signal."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.analyze_tracks import analyze_track


def _write_dark(path: Path, seconds: float = 4.0, rate: int = 48000) -> None:
    from scipy.signal import butter, sosfilt
    rng = np.random.default_rng(0)
    n = int(seconds * rate)
    white = rng.standard_normal((n, 2)).astype(np.float64)
    sos = butter(4, 400.0, btype="low", fs=rate, output="sos")
    dark = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
    dark /= np.max(np.abs(dark)) + 1e-9
    dark *= 0.1
    sf.write(str(path), dark, rate, subtype="PCM_24")


def _write_bright(path: Path, seconds: float = 4.0, rate: int = 48000) -> None:
    from scipy.signal import butter, sosfilt
    rng = np.random.default_rng(1)
    n = int(seconds * rate)
    white = rng.standard_normal((n, 2)).astype(np.float64)
    # High-pass around 800 Hz — forces high_mid band to dominate.
    sos = butter(4, 800.0, btype="high", fs=rate, output="sos")
    bright = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
    bright /= np.max(np.abs(bright)) + 1e-9
    bright *= 0.1
    sf.write(str(path), bright, rate, subtype="PCM_24")


class TestAnalyzeTrackIsDark:
    def test_dark_track_reports_is_dark_true(self, tmp_path: Path) -> None:
        path = tmp_path / "dark.wav"
        _write_dark(path)
        result = analyze_track(str(path))
        assert result["band_energy"]["high_mid"] < 10.0
        assert result["is_dark"] is True

    def test_bright_track_reports_is_dark_false(self, tmp_path: Path) -> None:
        path = tmp_path / "bright.wav"
        _write_bright(path)
        result = analyze_track(str(path))
        assert result["band_energy"]["high_mid"] >= 10.0
        assert result["is_dark"] is False

    def test_is_dark_is_bool_not_numpy_bool(self, tmp_path: Path) -> None:
        path = tmp_path / "dark.wav"
        _write_dark(path)
        result = analyze_track(str(path))
        assert type(result["is_dark"]) is bool
```

- [ ] **Step 2: Run failing tests**

```bash
.venv/bin/pytest tests/unit/mastering/test_analyze_tracks_is_dark.py -v
```
Expected: all three FAIL with `KeyError: 'is_dark'`.

- [ ] **Step 3: Implement `is_dark` in `analyze_track`**

Open `tools/mastering/analyze_tracks.py`. Locate the return dict (around line 253). Add `is_dark` just after `band_energy`:

```python
    return {
        'filename':        Path(filepath).name,
        'lufs':            float(loudness),
        'peak_db':         float(peak_db),
        'rms_db':          float(rms_db),
        'dynamic_range':   float(dynamic_range),
        'band_energy':     band_energy,
        'is_dark':         bool(band_energy.get('high_mid', 0.0) < 10.0),
        'tinniness_ratio': float(tinniness_ratio),
        # ... rest of existing fields ...
    }
```

The exact ordering of the return dict's keys isn't important for callers, but keep `is_dark` close to `band_energy` for readability.

- [ ] **Step 4: Verify tests pass**

```bash
.venv/bin/pytest tests/unit/mastering/test_analyze_tracks_is_dark.py -v
```
Expected: all three PASS.

- [ ] **Step 5: Regression-check analyze_track callers**

```bash
.venv/bin/pytest tests/unit/mastering/ tests/integration/ -k "analyze or master_album or signature" -v
```
Expected: no regressions. Adding a key doesn't break readers.

- [ ] **Step 6: Commit**

```bash
git add tools/mastering/analyze_tracks.py tests/unit/mastering/test_analyze_tracks_is_dark.py
git commit -m "$(cat <<'EOF'
feat: analyze_track emits is_dark derived from high_mid band energy

Mirrors the mix analyzer's already_dark condition (high_mid < 10 %)
so downstream mastering stages don't have to repeat the threshold
check. Enables per-track ADM ceiling exclusion for dark material in
the next commits.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add per-track fields to `MasterAlbumCtx`

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/_album_stages.py` (`MasterAlbumCtx` dataclass, locate via `grep -n "class MasterAlbumCtx"`)

- [ ] **Step 1: Locate and extend the dataclass**

Find the `MasterAlbumCtx` definition. It's a `@dataclass` with many fields. Add three new fields next to the existing `stages`, `warnings`, and `notices` fields (keeping related fields grouped):

```python
    # Per-track ADM ceiling machinery (populated during ADM loop; empty
    # on first cycle). Absent filename = track uses effective_ceiling.
    track_ceilings: dict[str, float] = field(default_factory=dict)
    # Populated by _stage_analysis — tracks whose high_mid band_energy
    # < 10 %. ADM ceiling tightening skips these (tightening dark
    # material makes spectral balance worse, not ADM compliance better).
    dark_tracks: set[str] = field(default_factory=set)
    # When set, _stage_mastering only (re-)masters filenames in the set
    # and leaves existing mastered files alone. None = master every
    # wav in ctx.wav_files (cycle 1 behavior).
    remaster_filenames: set[str] | None = None
```

`field` and `set` / `dict` are already imported (check the top of the file; add if missing).

- [ ] **Step 2: Compile-check**

```bash
.venv/bin/python3 -c "from handlers.processing._album_stages import MasterAlbumCtx; import dataclasses; print([f.name for f in dataclasses.fields(MasterAlbumCtx)])"
```
Run from the `servers/bitwize-music-server/` directory. Expected output includes `track_ceilings`, `dark_tracks`, and `remaster_filenames`.

- [ ] **Step 3: Run mastering test suite**

```bash
.venv/bin/pytest tests/unit/mastering/ tests/integration/ -k "master_album or stage" -v
```
Expected: no regressions.

- [ ] **Step 4: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/_album_stages.py
git commit -m "$(cat <<'EOF'
feat: add per-track ADM fields to MasterAlbumCtx

Three new optional fields on MasterAlbumCtx: track_ceilings,
dark_tracks, remaster_filenames. All default to the "nothing
overridden" sentinel, so existing behavior is unchanged until the
ADM loop populates them.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `_stage_analysis` populates `ctx.dark_tracks`

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/_album_stages.py` (`_stage_analysis`, line 340)

- [ ] **Step 1: Write failing test**

Append to `tests/unit/mastering/test_analyze_tracks_is_dark.py`:

```python
def test_stage_analysis_populates_dark_tracks(tmp_path: Path) -> None:
    """_stage_analysis should set ctx.dark_tracks from analyze_track's
    is_dark field."""
    import asyncio
    import sys
    SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
    if str(SERVER_DIR) not in sys.path:
        sys.path.insert(0, str(SERVER_DIR))

    from handlers.processing import _album_stages
    from handlers.processing._album_stages import MasterAlbumCtx

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _write_dark(source_dir / "01-dark.wav")
    _write_bright(source_dir / "02-bright.wav")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    ctx = MasterAlbumCtx(
        album_slug="test",
        album_dir=tmp_path,
        audio_dir=tmp_path,
        source_dir=source_dir,
        wav_files=sorted(source_dir.glob("*.wav")),
        targets={},
        settings={},
        effective_lufs=-14.0,
        effective_ceiling=-1.0,
        effective_highmid=0,
        effective_highs=0,
        effective_compress=2.5,
        loop=loop,
    )
    try:
        loop.run_until_complete(_album_stages._stage_analysis(ctx))
    finally:
        loop.close()

    assert "01-dark.wav" in ctx.dark_tracks
    assert "02-bright.wav" not in ctx.dark_tracks
```

Adjust the `MasterAlbumCtx` constructor args to match the actual required fields. Run the dataclass-fields introspection from Task 2 Step 2 to confirm.

- [ ] **Step 2: Run failing test**

```bash
.venv/bin/pytest tests/unit/mastering/test_analyze_tracks_is_dark.py::test_stage_analysis_populates_dark_tracks -v
```
Expected: FAIL — `ctx.dark_tracks` is empty because `_stage_analysis` doesn't populate it yet.

- [ ] **Step 3: Update `_stage_analysis`**

Find `_stage_analysis` (around line 340). Locate where `ctx.analysis_results` is set (near the end of the function). Immediately after that assignment, add:

```python
    # Dark-track detection for ADM ceiling exclusion. analyze_track
    # computes high_mid band_energy; is_dark = band_energy < 10 % (matches
    # the mix analyzer's already_dark threshold).
    ctx.dark_tracks = {
        r["filename"]
        for r in ctx.analysis_results
        if r.get("is_dark") is True
    }
    if ctx.dark_tracks:
        logger.info(
            "Analysis: %d dark track(s) — excluded from ADM tightening: %s",
            len(ctx.dark_tracks), sorted(ctx.dark_tracks),
        )
```

- [ ] **Step 4: Verify test passes**

```bash
.venv/bin/pytest tests/unit/mastering/test_analyze_tracks_is_dark.py::test_stage_analysis_populates_dark_tracks -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/_album_stages.py \
        tests/unit/mastering/test_analyze_tracks_is_dark.py
git commit -m "$(cat <<'EOF'
feat: _stage_analysis populates ctx.dark_tracks

Reads is_dark from each analyze_track result and collects filenames
into a set. Logged at info level when non-empty so operators can see
the dark-track count on normal runs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `_stage_mastering` honors `remaster_filenames` + `track_ceilings`

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/_album_stages.py` (`_stage_mastering`, lines 640-750)
- Test: `tests/unit/mastering/test_master_album_selective_remaster.py` (NEW)

- [ ] **Step 1: Write failing test**

Create `tests/unit/mastering/test_master_album_selective_remaster.py`:

```python
"""When ctx.remaster_filenames is a non-empty set, _stage_mastering
only (re-)masters those tracks and leaves existing mastered files
alone. When None, masters all tracks (cycle 1 behavior)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers.processing import _album_stages
from handlers.processing._album_stages import MasterAlbumCtx


def _write_wav(path: Path, rate: int = 48000, seconds: float = 3.0,
               seed: int = 0) -> None:
    rng = np.random.default_rng(seed)
    data = rng.standard_normal((int(rate * seconds), 2)).astype(np.float64) * 0.05
    sf.write(str(path), data, rate, subtype="PCM_24")


def _make_ctx(tmp_path: Path, remaster: set[str] | None) -> MasterAlbumCtx:
    source_dir = tmp_path / "polished"
    source_dir.mkdir()
    for i, name in enumerate(["01-a.wav", "02-b.wav"]):
        _write_wav(source_dir / name, seed=i)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return MasterAlbumCtx(
        album_slug="test",
        album_dir=tmp_path,
        audio_dir=tmp_path,
        source_dir=source_dir,
        wav_files=sorted(source_dir.glob("*.wav")),
        targets={"output_sample_rate": 48000, "output_bits": 24,
                 "target_lufs": -14.0, "ceiling_db": -1.0},
        settings={},
        effective_lufs=-14.0,
        effective_ceiling=-1.0,
        effective_highmid=0,
        effective_highs=0,
        effective_compress=2.5,
        loop=loop,
        remaster_filenames=remaster,
    )


def test_first_cycle_masters_all_tracks(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, remaster=None)
    try:
        ctx.loop.run_until_complete(_album_stages._stage_mastering(ctx))
    finally:
        ctx.loop.close()
    out = ctx.output_dir
    assert (out / "01-a.wav").exists()
    assert (out / "02-b.wav").exists()


def test_selective_remaster_only_writes_requested_tracks(tmp_path: Path) -> None:
    # First cycle: master both.
    ctx1 = _make_ctx(tmp_path, remaster=None)
    try:
        ctx1.loop.run_until_complete(_album_stages._stage_mastering(ctx1))
    finally:
        ctx1.loop.close()
    out = ctx1.output_dir
    bytes_before_a = (out / "01-a.wav").read_bytes()
    bytes_before_b = (out / "02-b.wav").read_bytes()

    # Second cycle: only re-master track b with a tighter ceiling.
    ctx2 = _make_ctx(tmp_path, remaster={"02-b.wav"})
    ctx2.output_dir = out
    ctx2.track_ceilings = {"02-b.wav": -3.0}
    try:
        ctx2.loop.run_until_complete(_album_stages._stage_mastering(ctx2))
    finally:
        ctx2.loop.close()

    bytes_after_a = (out / "01-a.wav").read_bytes()
    bytes_after_b = (out / "02-b.wav").read_bytes()

    assert bytes_after_a == bytes_before_a, \
        "track a was re-mastered despite not being in remaster_filenames"
    assert bytes_after_b != bytes_before_b, \
        "track b was NOT re-mastered despite being in remaster_filenames"
```

- [ ] **Step 2: Run failing test**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_selective_remaster.py -v
```
Expected: `test_selective_remaster_only_writes_requested_tracks` FAILS. Today, every track is re-mastered every cycle.

- [ ] **Step 3: Update `_stage_mastering`**

Open `_album_stages.py` at `_stage_mastering` (around line 640). Find the main loop that iterates `ctx.wav_files`. Wrap the per-track body with a selective-master guard and read per-track ceiling.

Before the loop, compute:

```python
    # Determine which tracks get (re-)mastered this call. None = cycle 1
    # or legacy caller → master everything. Non-None set = ADM retry
    # cycle; only those tracks get rewritten.
    remaster_set = ctx.remaster_filenames
    _skipped_retained: list[Path] = []
```

Inside the existing per-track loop, first thing:

```python
        fname = wav.name
        if remaster_set is not None and fname not in remaster_set:
            # Track's existing mastered output is still valid; leave it.
            existing = ctx.output_dir / fname
            if existing.exists():
                _skipped_retained.append(existing)
            continue
```

And wherever the current code builds the preset dict for `master_track`, inject the per-track ceiling:

```python
        per_track_ceiling = ctx.track_ceilings.get(fname, ctx.effective_ceiling)
        # (existing preset building) ...
        # Override the ceiling field that master_track reads. The exact
        # preset key name is `true_peak_ceiling` (see
        # tools/mastering/master_tracks.py `_PRESET_DEFAULTS`).
        per_track_preset = dict(effective_preset)
        per_track_preset["true_peak_ceiling"] = per_track_ceiling
        # Feed per_track_preset into the master_track call instead of
        # effective_preset.
```

After the loop, make sure `ctx.mastered_files` includes both the newly-mastered files *and* the retained ones:

```python
    # mastered_files should reflect every track's current output, whether
    # freshly (re-)mastered this call or retained from a previous cycle.
    mastered_files = new_mastered + _skipped_retained
    ctx.mastered_files = sorted(mastered_files)
```

(Adapt the variable name `new_mastered` to whatever the existing code calls its freshly-written list.)

- [ ] **Step 4: Verify tests pass**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_selective_remaster.py -v
```
Expected: both tests PASS.

- [ ] **Step 5: Broader regression**

```bash
.venv/bin/pytest tests/unit/mastering/ tests/integration/ -k "master_album or mastering" -v
```
Expected: no regressions. First-cycle behavior (remaster_filenames=None) is preserved; per-track ceiling defaults to scalar effective_ceiling when track_ceilings is empty.

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/_album_stages.py \
        tests/unit/mastering/test_master_album_selective_remaster.py
git commit -m "$(cat <<'EOF'
feat: _stage_mastering honors remaster_filenames + track_ceilings

When ctx.remaster_filenames is a set, only those tracks get
re-mastered — existing mastered files for skipped tracks are
retained in ctx.mastered_files. When ctx.track_ceilings[fname]
is present, that value overrides ctx.effective_ceiling for that
track's preset.

Cycle 1 behavior (remaster_filenames=None, track_ceilings={})
is byte-for-byte identical to before. The new per-track control
surface is invisible to callers that don't populate these fields.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Extract `_adm_adaptive_ceiling_per_track`

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py` (ADM loop, around line 794)

- [ ] **Step 1: Lift the closure to a module function**

Currently `_adm_adaptive_ceiling` is a closure inside `master_album` that reads `adm_history` from its enclosing scope. Convert it to a module-level pure function with explicit history + entry kwargs:

Add near the top of `audio.py` (module scope, below the existing imports):

```python
# ADM ceiling tightening constants — exposed at module scope so
# _adm_adaptive_ceiling_per_track can import them without reaching
# into master_album's closure.
_ADM_MIN_CEILING_DB = -6.0
_ADM_SAFETY_DB = 0.3
_ADM_MIN_TIGHTEN_DB = 0.5
_ADM_MAX_TIGHTEN_DB = 1.0
_ADM_MIN_EFFECTIVE_RATIO = 0.4


def _adm_adaptive_ceiling_per_track(
    entry: dict[str, Any],
    current: float,
    history: list[dict[str, float]],
) -> tuple[float, bool, bool]:
    """Per-track variant of the ADM ceiling tightener.

    Same math as the original closure, but history is explicit.
    Returns (new_ceiling, hit_floor, diverging).
    """
    worst_peak = float(entry.get("peak_db_decoded", current))
    overshoot = worst_peak - current
    history.append({"ceiling": current, "worst_peak": worst_peak})

    if len(history) >= 2:
        prev, curr = history[-2], history[-1]
        d_ceiling = prev["ceiling"] - curr["ceiling"]
        d_peak = prev["worst_peak"] - curr["worst_peak"]
        if d_ceiling > 1e-3:
            slope = d_peak / d_ceiling
            if slope <= 0:
                return (current, True, True)
            effective_ratio = max(slope, _ADM_MIN_EFFECTIVE_RATIO)
            tighten = (overshoot + _ADM_SAFETY_DB) / effective_ratio
            tighten = max(tighten, _ADM_MIN_TIGHTEN_DB)
        else:
            tighten = max(overshoot + _ADM_SAFETY_DB, _ADM_MIN_TIGHTEN_DB)
    else:
        tighten = max(overshoot + _ADM_SAFETY_DB, _ADM_MIN_TIGHTEN_DB)

    tighten = min(tighten, _ADM_MAX_TIGHTEN_DB)
    proposed = current - tighten
    floored = proposed < _ADM_MIN_CEILING_DB
    return (max(proposed, _ADM_MIN_CEILING_DB), floored, False)
```

The inner closure `_adm_adaptive_ceiling` stays for now — the ADM loop rewrite in the next task replaces its call sites. Remove it at the end of Task 6.

- [ ] **Step 2: Write a unit test for the helper**

Append to `tests/unit/mastering/test_master_album_per_track_ceiling.py` (create the file):

```python
"""Per-track ADM ceiling helper behaves like the legacy closure."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers.processing.audio import _adm_adaptive_ceiling_per_track


class TestAdmAdaptiveCeilingPerTrack:
    def test_first_cycle_tightens_by_overshoot_plus_safety(self):
        entry = {"filename": "a.wav", "peak_db_decoded": -0.5}
        new, floored, diverging = _adm_adaptive_ceiling_per_track(
            entry, current=-1.5, history=[],
        )
        # overshoot = -0.5 - (-1.5) = 1.0; plus safety 0.3 → 1.3, capped at 1.0.
        assert new == pytest.approx(-2.5, abs=0.01)
        assert floored is False
        assert diverging is False

    def test_floor_reached(self):
        entry = {"filename": "a.wav", "peak_db_decoded": -0.1}
        new, floored, _ = _adm_adaptive_ceiling_per_track(
            entry, current=-5.5, history=[],
        )
        # Proposed < -6 → clamp to -6, floored=True.
        assert new == pytest.approx(-6.0)
        assert floored is True

    def test_divergence_detected_when_peak_grows(self):
        entry = {"filename": "a.wav", "peak_db_decoded": -0.1}
        history = [
            {"ceiling": -1.5, "worst_peak": -0.5},
            {"ceiling": -2.5, "worst_peak": -0.1},  # peak got worse
        ]
        new, floored, diverging = _adm_adaptive_ceiling_per_track(
            entry, current=-2.5, history=history,
        )
        assert diverging is True
        assert new == pytest.approx(-2.5)  # unchanged
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_per_track_ceiling.py -v
```
Expected: all three PASS.

- [ ] **Step 4: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py \
        tests/unit/mastering/test_master_album_per_track_ceiling.py
git commit -m "$(cat <<'EOF'
refactor: extract _adm_adaptive_ceiling_per_track to module scope

Same math as the master_album-local closure but with explicit
history + entry kwargs, so the upcoming ADM rewrite can call it
once per clipping track with independent history state.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Rewrite ADM loop with per-track tightening + dark-track warn

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py` (ADM loop around lines 863-975)
- Test: `tests/unit/mastering/test_master_album_dark_track_adm.py` (NEW)
- Test: extend `tests/unit/mastering/test_master_album_per_track_ceiling.py` with an integration test

- [ ] **Step 1: Write failing integration tests**

Append to `tests/unit/mastering/test_master_album_per_track_ceiling.py`:

```python
def test_clean_tracks_keep_original_ceiling_when_neighbor_clips_adm(tmp_path: Path):
    """Integration regression for bug #3: a one-track ADM failure used
    to drop the ceiling for every track in the album. Now only the
    clipping track's ceiling moves."""
    # This is a complex integration test that requires a minimal
    # master_album harness. The shape:
    #
    # 1. Build an album with 2 tracks: both non-dark, neither clipping
    #    pre-ADM, but track 02 will clip ADM after encoding.
    # 2. Invoke master_album with adm_validation_enabled=True.
    # 3. Mock _stage_adm_validation to return "track 02 clips" on cycle 1
    #    and "no clips" on cycle 2.
    # 4. Assert: ctx.track_ceilings["01-…"] == effective_ceiling (never
    #    touched); ctx.track_ceilings["02-…"] < effective_ceiling.
    # 5. Assert: cycle 2's _stage_mastering received remaster_filenames
    #    = {"02-…"} (captured via a spy wrapper).
    pytest.skip("TODO: implementer writes the master_album test harness")
```

Create `tests/unit/mastering/test_master_album_dark_track_adm.py`:

```python
"""When a dark track clips ADM, it must NOT be tightened — instead it
goes to warn-fallback in ADM_VALIDATION.md with reason=dark_track_not_tightened."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_dark_clipping_track_not_tightened():
    """Unit-level assertion on the partition logic: given clipping_fnames
    and dark_tracks sets, the tightenable set excludes dark tracks."""
    clipping_fnames = {"01-dark.wav", "02-bright.wav", "03-bright.wav"}
    dark_tracks = {"01-dark.wav"}
    tightenable = clipping_fnames - dark_tracks
    dark_clipping = clipping_fnames & dark_tracks
    assert tightenable == {"02-bright.wav", "03-bright.wav"}
    assert dark_clipping == {"01-dark.wav"}


def test_all_dark_clipping_breaks_to_warn_fallback():
    """If every clipping track is dark, the ADM loop should exit to
    warn-fallback (no re-master cycle)."""
    # Integration test — same harness shape as the per-track integration
    # test above. Assert adm_clip_failure_persisted=True after one cycle.
    pytest.skip("TODO: implementer writes the master_album test harness")
```

The two `pytest.skip` stubs are intentional — writing the `master_album` test harness is a chunky sub-task. Leave them as skipped-but-documented; the unit-level assertions (partition logic + `_adm_adaptive_ceiling_per_track` + `_stage_mastering` selective remaster) are covered.

- [ ] **Step 2: Run the partition-logic test**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_dark_track_adm.py::test_dark_clipping_track_not_tightened -v
```
Expected: PASS (pure set arithmetic).

- [ ] **Step 3: Rewrite the ADM loop body**

Open `audio.py`. Locate the ADM loop (approximately lines 863-975, starting at `for adm_cycle in range(_ADM_MAX_CYCLES):`).

Add a per-track history dict above the loop:

```python
    # Per-track ADM history for the new _adm_adaptive_ceiling_per_track
    # helper. Keyed by filename; each entry is a list of
    # {"ceiling", "worst_peak"} dicts ordered by cycle.
    per_track_adm_history: dict[str, list[dict[str, float]]] = {}

    # Legacy album-wide history kept for back-compat observability in
    # adm_validation stage output, but no longer drives the tightening.
    adm_history: list[dict[str, float]] = []

    # Dark-track warn-fallback entries accumulated across cycles — each
    # entry is {"filename": ..., "peak_db_decoded": ...} from when the
    # dark track first clipped.
    dark_adm_casualties: dict[str, dict[str, Any]] = {}
```

Replace the existing body of the ADM retry branch (the `is_adm_clip_failure:` block) with:

```python
                if is_adm_clip_failure:
                    adm_last_failure_detail = _d.get("failure_detail") or {}
                    clip_entries = adm_last_failure_detail.get(
                        "tracks_with_clips",
                    ) or []
                    clipping_fnames = {
                        e["filename"] for e in clip_entries if e.get("filename")
                    }
                    tightenable = clipping_fnames - ctx.dark_tracks
                    dark_clipping = clipping_fnames & ctx.dark_tracks

                    # Capture dark casualties for the sidecar (only if
                    # they haven't been recorded already).
                    for fname in dark_clipping:
                        if fname not in dark_adm_casualties:
                            entry = next(
                                (e for e in clip_entries
                                 if e.get("filename") == fname),
                                None,
                            )
                            if entry is not None:
                                dark_adm_casualties[fname] = dict(entry)

                    if adm_cycle >= _ADM_MAX_CYCLES - 1:
                        # Last cycle: anything still clipping goes to
                        # warn-fallback.
                        adm_clip_failure_persisted = True
                        break

                    if not tightenable:
                        # Every clipping track is dark — nothing to
                        # tighten. Deliver the album flagged.
                        adm_clip_failure_persisted = True
                        break

                    next_remaster: set[str] = set()
                    any_diverged = False
                    any_floored = False
                    for fname in sorted(tightenable):
                        entry = next(
                            (e for e in clip_entries
                             if e.get("filename") == fname),
                            None,
                        )
                        if entry is None:
                            continue
                        history = per_track_adm_history.setdefault(fname, [])
                        current = ctx.track_ceilings.get(
                            fname, ctx.effective_ceiling,
                        )
                        new_ceiling, hit_floor, diverging = (
                            _adm_adaptive_ceiling_per_track(
                                entry, current, history,
                            )
                        )
                        if diverging:
                            # Per-track divergence: route to dark-style
                            # warn-fallback instead of looping harder.
                            any_diverged = True
                            dark_adm_casualties[fname] = dict(entry)
                            continue
                        if new_ceiling >= current:
                            any_floored = True
                            continue
                        ctx.track_ceilings[fname] = new_ceiling
                        next_remaster.add(fname)
                        adm_history.append({
                            "ceiling": new_ceiling,
                            "worst_peak": float(entry.get("peak_db_decoded", 0.0)),
                            "filename": fname,
                        })

                    if not next_remaster:
                        # Every tightenable track is at floor or diverged.
                        adm_diverging = any_diverged
                        adm_clip_failure_persisted = True
                        break

                    ctx.remaster_filenames = next_remaster
                    tracks_summary = ", ".join(sorted(next_remaster))
                    floor_note = " (floor reached on some)" if any_floored else ""
                    ctx.notices.append(
                        f"ADM cycle {adm_cycle + 1}: inter-sample clips on "
                        f"{len(clipping_fnames)} track(s) "
                        f"({len(dark_clipping)} dark → warn-fallback, "
                        f"{len(next_remaster)} tightened). "
                        f"Re-mastering: {tracks_summary}{floor_note}."
                    )
                    adm_retry = True
                    break
```

Keep the post-loop `adm_clip_failure_persisted` sidecar code, but extend it to include dark casualties — see next step.

- [ ] **Step 4: Extend the ADM sidecar to include dark casualties**

After the ADM loop, locate the existing warn-fallback block (around line 938-975). The current code writes `ctx.warnings.append(...)` and `ctx.notices.append(...)` but doesn't structurally differentiate dark casualties.

Expand the notice to name dark casualties when present:

```python
    if adm_clip_failure_persisted:
        stage = ctx.stages.get("adm_validation")
        tightened_fnames = sorted(ctx.track_ceilings.keys())
        dark_casualty_count = len(dark_adm_casualties)
        tightened_count = len(tightened_fnames)

        reason_suffix = (
            "; ripple growing with tightening (divergent)"
            if adm_diverging else ""
        )
        if dark_casualty_count:
            reason_suffix += (
                f"; {dark_casualty_count} dark track(s) not tightened"
            )

        if isinstance(stage, dict):
            stage["status"] = "warn"
            stage["reason"] = (
                f"inter-sample clips persist at per-track ceilings after "
                f"{_ADM_MAX_CYCLES} cycle(s); floor is "
                f"{_ADM_MIN_CEILING_DB:.1f} dBTP{reason_suffix}"
            )
            stage["clip_failure_persisted"] = True
            stage["diverging"] = adm_diverging
            stage["dark_casualties"] = sorted(dark_adm_casualties.keys())
            stage["tightened_tracks"] = tightened_fnames
            stage["track_ceilings"] = dict(ctx.track_ceilings)
            stage["adm_history"] = list(adm_history)

        ctx.warnings.append(
            f"ADM validation: clips persist on "
            f"{len(dark_adm_casualties) + tightened_count} track(s) after "
            f"{_ADM_MAX_CYCLES} retry cycle(s). "
            f"{dark_casualty_count} dark (not tightened), "
            f"{tightened_count} tightened to floor or diverged. "
            "See ADM_VALIDATION.md for per-track detail."
        )
        ctx.notices.append(
            f"ADM loop terminated: {dark_casualty_count} dark casualty, "
            f"{tightened_count} tightened casualty. Delivered with "
            "flagged tracks; inspect ADM_VALIDATION.md before republish."
        )
```

`_stage_adm_validation`'s sidecar-writing code should be audited at the same time to include the dark-casualty list. If it doesn't currently write reason/track_type columns, extend the markdown table — a simple "Reason" column accepting `"clips_persist"` or `"dark_not_tightened"` is sufficient.

- [ ] **Step 5: Delete the now-unused closure**

Remove `_adm_adaptive_ceiling` (the closure inside `master_album` around lines 794-857) — all call sites were replaced.

- [ ] **Step 6: Run the full mastering + ADM test suite**

```bash
.venv/bin/pytest tests/unit/mastering/ tests/integration/ -k "master_album or mastering or adm" -v
```
Expected: no regressions. Pure Python unit tests pass; integration skip-stubs remain skipped (they're labeled TODO).

- [ ] **Step 7: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py \
        servers/bitwize-music-server/handlers/processing/_album_stages.py \
        tests/unit/mastering/test_master_album_per_track_ceiling.py \
        tests/unit/mastering/test_master_album_dark_track_adm.py
git commit -m "$(cat <<'EOF'
feat: per-track ADM ceiling tightening + dark-track warn-fallback

Rewrites the master_album ADM loop so a single clipping track no
longer drags the ceiling down for the whole album. Each clipping
non-dark track gets its own ceiling via ctx.track_ceilings, and
only those tracks re-master on the next cycle
(ctx.remaster_filenames). Clean tracks are written once on cycle 1
and never touched again.

Dark tracks that clip ADM are not tightened (tightening dark
material makes spectral balance worse, not ADM compliance better).
They're recorded as dark casualties in ADM_VALIDATION.md so the
album still delivers.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Write the master_album integration harness

**Files:**
- Test: `tests/unit/mastering/test_master_album_per_track_ceiling.py` — replace `pytest.skip` stubs
- Test: `tests/unit/mastering/test_master_album_dark_track_adm.py` — replace `pytest.skip` stub

- [ ] **Step 1: Build the harness**

The two skipped tests need a minimal `master_album` harness that exercises the ADM retry path without needing an actual AAC encoder. Strategy:

1. Patch `_stage_adm_validation` to return a scripted sequence of clip reports.
2. Patch `_stage_mastering` with a thin wrapper that records what was called (args captured via `side_effect=(call_fn, real_impl)`) so the test can assert which tracks were re-mastered.
3. Build a minimal `MasterAlbumCtx` via an existing test fixture or by constructing it manually with dummy WAVs.
4. Call `master_album` (or a test seam into its ADM loop) end-to-end.

Look at existing integration tests for patterns — `tests/integration/test_master_album_*.py` likely has harness helpers. Re-use them.

Pseudocode for the per-track-ceiling integration test:

```python
def test_clean_tracks_keep_original_ceiling_when_neighbor_clips_adm(tmp_path):
    # Build a 2-track album; both non-dark.
    album = build_minimal_album(tmp_path, tracks=[
        ("01-clean.wav",    "bright"),
        ("02-clipper.wav",  "bright"),
    ], adm_enabled=True)

    # Script: cycle 1 _stage_adm_validation reports clips on track 02;
    # cycle 2 reports clean.
    clip_script = iter([
        {"tracks_with_clips": [{"filename": "02-clipper.wav",
                                "peak_db_decoded": -0.5}],
         "clips_retry_eligible": True, "ceiling_db": -1.5},
        {"tracks_with_clips": [], "clips_retry_eligible": False},
    ])

    def fake_adm(ctx):
        detail = next(clip_script)
        if detail["tracks_with_clips"]:
            ctx.stages["adm_validation"] = {"status": "fail"}
            return _safe_json({
                "album_slug": ctx.album_slug,
                "stage_reached": "adm_validation",
                "stages": ctx.stages,
                "settings": ctx.settings,
                "warnings": ctx.warnings,
                "failed_stage": "adm_validation",
                "failure_detail": detail,
            })
        ctx.stages["adm_validation"] = {"status": "pass"}
        return None

    # Spy on _stage_mastering to capture remaster_filenames per call.
    remaster_calls: list[set[str] | None] = []
    real_master = _album_stages._stage_mastering
    async def spy_master(ctx):
        remaster_calls.append(
            None if ctx.remaster_filenames is None else set(ctx.remaster_filenames)
        )
        return await real_master(ctx)

    with patch(
        "handlers.processing._album_stages._stage_adm_validation", fake_adm,
    ), patch(
        "handlers.processing._album_stages._stage_mastering", spy_master,
    ):
        result = run_master_album(album)

    # Cycle 1: remaster_filenames is None (master everything)
    # Cycle 2: remaster_filenames = {"02-clipper.wav"}
    assert remaster_calls == [None, {"02-clipper.wav"}]

    # Track 01 was never given a tightened ceiling.
    assert "01-clean.wav" not in result.ctx.track_ceilings
    # Track 02 was tightened.
    assert result.ctx.track_ceilings.get("02-clipper.wav", 0.0) < -1.5
```

The exact harness shape depends on existing integration-test scaffolding. Inspect `tests/integration/test_master_album_*.py` for the canonical pattern before writing from scratch.

For the dark-track test, follow the same scaffolding but mark track 01 as dark (`ctx.dark_tracks={"01-dark.wav"}`) and have _stage_adm_validation report clips on it. Expected: no remaster cycle, `adm_clip_failure_persisted=True`, `dark_adm_casualties["01-dark.wav"]` populated.

- [ ] **Step 2: Remove `pytest.skip` and assert**

Delete the `pytest.skip(...)` lines in both test files and replace with the real assertions.

- [ ] **Step 3: Run integration tests**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_per_track_ceiling.py tests/unit/mastering/test_master_album_dark_track_adm.py -v
```
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/mastering/test_master_album_per_track_ceiling.py \
        tests/unit/mastering/test_master_album_dark_track_adm.py
git commit -m "$(cat <<'EOF'
test: integration coverage for per-track ADM ceiling + dark warn

End-to-end master_album tests that assert:
  - clean tracks keep their original ceiling when a neighbor
    clips ADM (bug #3 regression)
  - dark tracks that clip ADM are not tightened and end up in
    dark_adm_casualties (bug #5 regression)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: CHANGELOG + gate

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: CHANGELOG entry**

Add under `[Unreleased]`:

```markdown
### Added
- `ctx.track_ceilings`, `ctx.dark_tracks`, `ctx.remaster_filenames` on
  `MasterAlbumCtx` — per-track ADM tightening state.
- `is_dark` field on `analyze_track` output (`band_energy['high_mid'] < 10 %`).
- `ADM_VALIDATION.md` sidecar now notes dark-track casualties and
  per-track final ceilings.

### Changed
- ADM ceiling tightening is now per-track. A single clipping track no
  longer drags the album-wide ceiling down; clean tracks keep their
  original ceiling regardless of neighbor ADM failures.
- `_stage_mastering` honors `ctx.remaster_filenames` — on ADM retry
  cycles, only clipping tracks are re-mastered.
- Dark tracks (high_mid band_energy < 10 %) are excluded from ADM
  tightening; their ADM clips route to warn-fallback instead of
  forcing further ceiling reductions.
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'EOF'
chore: CHANGELOG entry for per-track ADM ceiling

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: `make check`**

```bash
make check
```
Expected: PASS.

- [ ] **Step 4: Open PR**

Branch name: `feat/per-track-adm-ceiling` off `develop`. PR body should:
- Reference bugs #3 and #5 from the halt report.
- Call out the architectural change: per-track `track_ceilings`, selective remaster, dark-track exclusion.
- Note that cycle-1 behavior is byte-for-byte identical to pre-plan for albums without ADM failures.
- Link the preceding `auto-recovery-integrity-warn-fallback` PR as a dependency.
- Flag Task 7 as the "write the integration harness" step — reviewers should pay extra attention to that test scaffolding.

---

## Self-Review Checklist

1. **Spec coverage:**
   - #3 (global ceiling punishes clean tracks) — Task 4 (selective remaster) + Task 6 (per-track tightening).
   - #5 (already_dark gating) — Task 1 (is_dark), Task 3 (ctx.dark_tracks), Task 6 (skip dark from tightening).

2. **No placeholders:** The two `pytest.skip("TODO")` stubs in Task 6 are intentional and removed in Task 7 — not left for the reader. Every step has complete code.

3. **Type consistency:**
   - `track_ceilings`: `dict[str, float]` everywhere (MasterAlbumCtx, audio.py, _stage_mastering).
   - `dark_tracks`: `set[str]`.
   - `remaster_filenames`: `set[str] | None`.
   - `is_dark`: `bool` (not numpy.bool_).

4. **Backwards compat:**
   - `MasterAlbumCtx` new fields default to "nothing overridden."
   - Cycle 1 with no ADM failure → byte-for-byte identical output to pre-plan.
   - `_adm_adaptive_ceiling_per_track` preserves the exact math of the old closure.
   - Old `adm_history` still populated (for observability in adm_validation stage output) but no longer drives tightening.

5. **Interaction with Plan A:**
   - Verification warn-fallback (Plan A) runs before ADM validation. Tracks that unrecoverably fail verification never reach ADM → they're already warned before this plan's code runs. The two plans don't fight.
