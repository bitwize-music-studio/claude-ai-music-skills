# Phase 3b — `album_coherence_check` + `album_coherence_correct` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship two new MCP tools that operationalize the multi-metric signature foundation (phase 1b) and anchor selector (phase 2) into automated coherence correction. `album_coherence_check` is read-only: it measures the album, picks the anchor, and flags outlier tracks whose metrics sit outside per-genre tolerance bands. `album_coherence_correct` re-masters the LUFS-outlier tracks from the `polished/` source with a per-track adjusted `target_lufs` so every track's measured integrated loudness lands within tolerance of the anchor.

**Architecture:** Additive. A new pure-Python module (`tools/mastering/coherence.py`) owns the tolerance-classification math and the per-track correction-plan builder — no I/O, no MCP coupling. Two new async handlers in `handlers/processing/audio.py` orchestrate: `album_coherence_check` reuses `measure_album_signature`'s internals (analyze → `build_signature` → `select_anchor` → `compute_anchor_deltas`) then calls `classify_outliers`. `album_coherence_correct` extends that with a second `master_track` pass on LUFS outliers only, using the phase-2 anchor's measured LUFS as the new per-track target. Four new fields land in `tools/mastering/genre-presets.yaml` defaults: `coherence_stl_95_lu`, `coherence_lra_floor_lu`, `coherence_low_rms_db`, `coherence_vocal_rms_db`.

**Scope limits (MVP):**
- Correction handles **LUFS outliers only**. STL-95 / LRA / low-RMS / vocal-RMS violations are **reported in the response** but not auto-corrected in this phase. (Correcting compression ratio / band balance per-track needs more signal-processing work; deferred to a later phase.)
- **Single-pass correction**. The "ADM outer × coherence inner" iteration budget from issue #290 lands in a later phase — this ships one re-master pass plus a re-measurement.
- **No album-ceiling guard**. Bounded pull-down / halt-and-escalate logic is a separate checklist item.
- **No `ALBUM_SIGNATURE.yaml` persistence**. Phase 3c.

**Tech Stack:** Python 3.11, `numpy` (already imported), existing `master_track` / `analyze_track` / `build_signature` / `select_anchor` primitives. No new deps.

---

## File Structure

**Create:**
- `tools/mastering/coherence.py` — pure-Python classifier + correction-plan builder. Three public functions:
  - `load_tolerances(preset)` — pulls the four `coherence_*` fields with documented defaults.
  - `classify_outliers(deltas, tolerances, anchor_short_term_range)` — per-track violation list (LUFS, STL-95, LRA floor, low-RMS, vocal-RMS).
  - `build_correction_plan(classifications, analysis_results, anchor_index_1based)` — per-track preset-override dicts (LUFS-only in MVP).
- `tests/unit/mastering/test_coherence.py` — unit tests for the pure-Python module.
- `tests/unit/mastering/test_album_coherence_handlers.py` — integration tests for both handlers using `tmp_path` + synthetic WAVs.

**Modify:**
- `tools/mastering/genre-presets.yaml`:
  - Add four `coherence_*` fields to the `defaults:` block (after the existing `spectral_reference_energy` block at lines 145–153).
  - Extend the header-comment table (lines 1–82) to document the new fields.
- `servers/bitwize-music-server/handlers/processing/audio.py`:
  - Add `album_coherence_check` async handler (~120 lines) after `measure_album_signature`.
  - Add `album_coherence_correct` async handler (~180 lines) after `album_coherence_check`.
  - Add both to the `register(mcp)` block at the bottom.
- `servers/bitwize-music-server/handlers/processing/__init__.py` — re-export both new handlers (alphabetical).
- `servers/bitwize-music-server/server.py` — re-export both new handlers (alphabetical).
- `CHANGELOG.md` — add an `[Unreleased]` entry under `### Added` describing both tools.

**Not modified:**
- `tools/mastering/album_signature.py` — consumed as-is.
- `tools/mastering/anchor_selector.py` — consumed as-is.
- `tools/mastering/master_tracks.py` — `master_track(preset=...)` is called with a per-track modified preset dict; the signature stays untouched.
- `tools/mastering/config.py` — `build_effective_preset` is reused for the initial genre → preset resolution.

**Module responsibilities:**
- `coherence.py` — tolerance bands, outlier classification, correction planning. Pure math, pure dicts.
- `album_coherence_check` handler — glue: resolve audio dir → analyze WAVs → build signature → select anchor → classify → JSON.
- `album_coherence_correct` handler — glue: do the check, build a correction plan, re-master from `polished/` per plan, atomically promote staging → `mastered/`, re-measure.

---

## Design Details (read before starting any task)

### Tolerance field semantics

Four new preset fields. All land in `defaults:`; per-genre overrides are allowed but not shipped in this phase.

| Field | Default | Meaning |
|-------|---------|---------|
| `coherence_stl_95_lu` | `0.5` | Max `\|delta_stl_95\|` (LU) before a track is classified an STL-95 outlier. |
| `coherence_lra_floor_lu` | `1.0` | Minimum allowed `short_term_range` (LU) — tracks below this trip an LRA-floor violation regardless of anchor. |
| `coherence_low_rms_db` | `2.0` | Max `\|delta_low_rms\|` (dB) before low-RMS outlier. |
| `coherence_vocal_rms_db` | `2.0` | Max `\|delta_vocal_rms\|` (dB) before vocal-RMS outlier. |

LUFS tolerance isn't a preset field — we reuse the existing mastering verification spec (`±0.5 LU` around the resolved `target_lufs`, from `master_album`'s Stage 5 verify step) as the LUFS outlier threshold. That keeps the coherence check aligned with the mastering-loop's own pass/fail criterion.

**Why `lra_floor` is a floor, not a band:** STL-95 variance is already caught by `coherence_stl_95_lu`. LRA floor exists to catch over-compressed outliers that would cross the "no perceived dynamics" line for the album's genre — it's a hard minimum, not a ±band.

### `load_tolerances(preset)` contract

```python
DEFAULTS = {
    "coherence_stl_95_lu":    0.5,
    "coherence_lra_floor_lu": 1.0,
    "coherence_low_rms_db":   2.0,
    "coherence_vocal_rms_db": 2.0,
    "lufs_tolerance_lu":      0.5,   # hardcoded — matches master_album Stage 5
}

def load_tolerances(preset: dict[str, Any] | None) -> dict[str, float]:
    """Return the effective tolerance band dict.

    Falls back to built-in defaults key-by-key so a partial genre preset
    doesn't nuke fields it didn't override.
    """
```

`lufs_tolerance_lu` is intentionally **not** a preset field — it's a hardcoded constant derived from the existing mastering verification spec. Keeping it co-located with the other tolerances keeps `classify_outliers` signature clean.

### `classify_outliers` return shape

```python
[
    {
        "index": 1,                                  # 1-based
        "filename": "01-opening.wav",
        "is_anchor": False,
        "is_outlier": True,
        "violations": [
            {
                "metric":    "lufs",
                "delta":     1.3,                    # track - anchor
                "tolerance": 0.5,
                "severity":  "outlier",              # "ok" | "outlier" | "missing"
                "correctable": True,                 # LUFS is correctable in MVP
            },
            {
                "metric":    "stl_95",
                "delta":     -0.9,
                "tolerance": 0.5,
                "severity":  "outlier",
                "correctable": False,                # STL-95 not in MVP correction
            },
            {
                "metric":    "lra_floor",
                "value":     0.7,                    # no delta — it's a floor
                "floor":     1.0,
                "severity":  "outlier",
                "correctable": False,
            },
        ],
    },
    {
        "index": 2,
        "filename": "02-anchor.wav",
        "is_anchor": True,
        "is_outlier": False,
        "violations": [],
    },
    ...
]
```

**Rules:**
- A metric with `None` delta (missing analyzer output) emits a `{"metric": ..., "severity": "missing"}` violation. Not counted as `is_outlier: True` — the check can't classify what it can't measure.
- The anchor's own row always has `is_anchor: True`, `is_outlier: False`, and empty `violations`.
- `is_outlier` is True when **any** violation has `severity: "outlier"`.
- Five metrics are checked per track: `lufs`, `stl_95`, `lra_floor`, `low_rms`, `vocal_rms`. (`lra_floor` is a per-track check against `anchor.short_term_range` floor; the other four are delta-from-anchor checks.)

### `build_correction_plan` return shape

```python
{
    "anchor_index": 2,
    "anchor_lufs":  -14.1,        # measured LUFS of the anchor (ground truth)
    "corrections": [
        {
            "index":                1,
            "filename":             "01-opening.wav",
            "correctable":          True,
            "original_target_lufs": -14.0,         # from the preset (what was used first master)
            "corrected_target_lufs": -14.1,        # = anchor_lufs
            "reason":               "LUFS outlier: delta=+1.3, tolerance=±0.5",
        },
        {
            "index":                3,
            "filename":             "03-quiet.wav",
            "correctable":          False,
            "reason":               "Only non-LUFS violations (stl_95, lra_floor) — MVP scope skips.",
        },
    ],
    "skipped": [
        # Tracks with no violations OR anchor itself.
        {"index": 2, "filename": "02-anchor.wav", "reason": "is_anchor"},
        {"index": 4, "filename": "04-clean.wav", "reason": "no_violations"},
    ],
}
```

**Rules:**
- Anchor is always in `skipped` with `reason: "is_anchor"`.
- A track is correctable when it has a LUFS `severity: "outlier"` violation. Other violations may co-exist — they're reported in the check but don't block correction.
- A track with **only** non-LUFS outliers is **not correctable** in MVP — it shows up in `corrections` with `correctable: False` so the JSON is transparent about the scope limitation.
- `corrected_target_lufs` is the anchor's **measured** LUFS (what the anchor actually ended up at after its own mastering pass), not the preset's `target_lufs` — this guarantees convergence because we're chasing real output, not an idealized target that mastering may have missed by a few tenths of a dB.

### Handler contracts

#### `album_coherence_check`

```python
async def album_coherence_check(
    album_slug: str,
    subfolder: str = "mastered",
    genre: str = "",
    anchor_track: int | None = None,
) -> str:
```

Args mirror `measure_album_signature`. **Genre is required for a meaningful check** because that's where the tolerances come from — the handler returns an error JSON if `genre` is empty (unlike `measure_album_signature` which tolerates no-genre runs). Exception: if `genre` is empty but `anchor_track` is set, the handler falls back to the hardcoded default tolerances and emits a warning.

Response shape:

```python
{
    "album_slug": "my-album",
    "source_dir": "/abs/path/to/mastered",
    "settings": {
        "genre":         "pop",
        "subfolder":     "mastered",
        "tolerances":    { ...load_tolerances output... },
    },
    "album": { ...signature.album... },
    "anchor": { ...select_anchor output + deltas... },
    "classifications": [ ...classify_outliers output... ],
    "summary": {
        "track_count":          10,
        "outlier_count":        2,
        "correctable_count":    1,     # LUFS-only outliers
        "uncorrectable_count":  1,     # non-LUFS-only outliers
        "metric_breakdown": {
            "lufs":       {"outliers": 1, "missing": 0},
            "stl_95":     {"outliers": 1, "missing": 0},
            "lra_floor":  {"outliers": 1, "missing": 0},
            "low_rms":    {"outliers": 0, "missing": 0},
            "vocal_rms":  {"outliers": 0, "missing": 0},
        },
    },
}
```

#### `album_coherence_correct`

```python
async def album_coherence_correct(
    album_slug: str,
    genre: str,                                     # required — drives tolerances + preset
    source_subfolder: str = "polished",             # where to re-master FROM
    check_subfolder:  str = "mastered",             # where to measure the current state
    target_lufs: float = -14.0,
    ceiling_db: float = -1.0,
    cut_highmid: float = 0.0,
    cut_highs: float = 0.0,
    anchor_track: int | None = None,
    dry_run: bool = False,
) -> str:
```

**Required genre** — correction depends on preset fields. The handler returns an error JSON if `genre` is empty.

**Flow:**
1. Resolve audio dir + both subfolders (`mastered/` for check, `polished/` for re-master source).
2. Validate that every WAV in `mastered/` has a matching WAV in `polished/` — the correction path needs a pre-limiter source to re-master from. Fail fast with a clear error listing missing files if not.
3. Run the coherence check (analyze `mastered/`, select anchor, classify outliers).
4. Build the correction plan.
5. If `dry_run=True`: return `{plan: ..., performed: false}` — nothing written.
6. Otherwise, for each correctable track:
   - Build `modified_preset = {**effective_preset, "target_lufs": anchor_lufs}`.
   - Call `master_track(input=polished/<name>, output=staging/<name>, preset=modified_preset)`.
   - On success, stage the file; on failure, abort the whole correction pass and clean up staging.
7. Atomically promote staging WAVs into `mastered/` (overwrite originals).
8. Re-measure `mastered/` and emit a post-correction signature + updated classifications in the response.

**Staging pattern:** Identical to `master_album`'s existing `.coherence_staging/` subfolder approach — all-or-nothing atomic move; failure path clears staging.

**Response shape:**

```python
{
    "album_slug": "my-album",
    "dry_run":    false,
    "settings":   { ...subset of args... },
    "pre_correction":  { ...coherence_check response body... },
    "plan":            { ...build_correction_plan output... },
    "corrections": [
        {
            "filename":              "01-opening.wav",
            "original_lufs":         -12.8,
            "applied_target_lufs":   -14.1,
            "result_lufs":           -14.05,         # post-re-master measured
            "status":                "ok",           # or "failed"
            "delta_from_anchor":     0.05,           # (result_lufs - anchor_lufs)
            "within_tolerance":      true,
        },
    ],
    "post_correction": { ...fresh signature + classifications... },
    "summary": {
        "corrected":      1,
        "skipped":        2,
        "failed":         0,
        "anchor_lufs":    -14.1,
        "outliers_before": 2,
        "outliers_after":  1,    # if 1 non-LUFS outlier remained
    },
}
```

### Why re-master from `polished/` not `mastered/`

Re-running the limiter on an already-mastered file stacks transient shaping — the second pass compresses peaks the first pass already flattened, and LUFS readings drift as limiters pile up. Re-mastering from the **pre-limiter** source (`polished/`, which is what `master_album` consumed the first time) gives a clean pass with the adjusted target. This matches the polish-master contract from issue #290: polish runs once and is frozen; master consumes the frozen input.

If `polished/` is missing, the correction handler returns an error with the suggestion: "Run polish_audio first, then re-master with master_album, then re-run album_coherence_correct." We do **not** attempt to re-master from the raw Suno source — that would bypass polish and produce different-sounding output.

### State-cache integration

No new frontmatter fields needed — `anchor_track` from phase 2 already carries through. Track status stays `Final` after correction (correction doesn't transition status; the track was already `Final` when `master_album` completed).

### Test strategy

**Pure-Python tests (`test_coherence.py`):**
- `load_tolerances` — partial preset merges with defaults key-by-key.
- `classify_outliers` — LUFS outlier, STL-95 outlier, LRA floor breach, low-RMS outlier, vocal-RMS outlier, missing-metric handling, anchor row has empty violations, multiple simultaneous violations on one track.
- `build_correction_plan` — LUFS-only correctable, non-LUFS-only marked uncorrectable, anchor in `skipped`, clean tracks in `skipped`.

**Integration tests (`test_album_coherence_handlers.py`):**
Use real sine-wave WAVs at controlled amplitudes so the analyzer produces predictable LUFS values, enabling deterministic outlier assertions. At least:
- `album_coherence_check` with 3 tracks at `{−14.0, −12.5, −14.2}` LUFS (track 2 is the outlier) → `summary.outlier_count == 1`, violation list includes `metric=lufs`.
- `album_coherence_check` fails fast when `genre` empty and no `anchor_track`.
- `album_coherence_correct` with `dry_run=True` → response has `performed: false`, no files written.
- `album_coherence_correct` end-to-end: creates `polished/` + `mastered/` with a known-outlier track, runs correction, asserts re-mastered file's post-measurement lands within tolerance of anchor.
- `album_coherence_correct` errors when `polished/` is missing a track present in `mastered/`.

Synthetic-WAV loudness control: amplitude scaling on a known sine at a known duration gives deterministic LUFS within ±0.2 LU (BS.1770 gating is predictable on constant-tone input). Use `amplitude=0.3` for ~−14 LUFS baseline, `amplitude=0.5` for ~−10 LUFS outlier.

---

## Task 1: Add coherence tolerance fields to `genre-presets.yaml`

**Files:**
- Modify: `tools/mastering/genre-presets.yaml`

- [ ] **Step 1: Write a failing test that asserts the new defaults exist**

Create `tests/unit/mastering/test_coherence_presets.py`:

```python
#!/usr/bin/env python3
"""Tests verifying coherence tolerance fields are present in genre defaults (#290 phase 3b)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.master_tracks import load_genre_presets


COHERENCE_FIELDS = {
    "coherence_stl_95_lu":    0.5,
    "coherence_lra_floor_lu": 1.0,
    "coherence_low_rms_db":   2.0,
    "coherence_vocal_rms_db": 2.0,
}


class TestCoherenceTolerancesInDefaults:
    def test_all_four_fields_present_in_defaults_block(self):
        presets = load_genre_presets()
        # load_genre_presets merges defaults into every genre. Pick "pop" —
        # it's the canonical test genre and doesn't override these fields.
        pop = presets["pop"]
        for key, expected in COHERENCE_FIELDS.items():
            assert key in pop, f"{key} missing from merged pop preset"
            assert pop[key] == pytest.approx(expected), (
                f"{key} default = {pop[key]}, expected {expected}"
            )
```

- [ ] **Step 2: Run test to verify failure**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_coherence_presets.py -v
```

Expected: FAIL with `KeyError: 'coherence_stl_95_lu'` (or similar — field missing).

- [ ] **Step 3: Add the fields to `tools/mastering/genre-presets.yaml`**

In the `defaults:` block, immediately after the `spectral_reference_energy:` sub-dict (which ends at line 153 in the current file), add:

```yaml
  # Album-mastering coherence tolerance bands (#290 phase 3b).
  # Used by album_coherence_check / album_coherence_correct to classify
  # outlier tracks relative to the selected anchor. All thresholds are
  # absolute-value deltas from the anchor unless otherwise noted.
  coherence_stl_95_lu: 0.5         # ±LU around anchor's STL-95
  coherence_lra_floor_lu: 1.0      # minimum short_term_range allowed (absolute)
  coherence_low_rms_db: 2.0        # ±dB around anchor's low_rms
  coherence_vocal_rms_db: 2.0      # ±dB around anchor's vocal_rms
```

Also extend the header comment block (lines 1–82) by adding these four lines **immediately after** the existing `spectral_reference_energy` documentation block (which currently ends at line 82):

```yaml
#   coherence_stl_95_lu    - Max |track.stl_95 - anchor.stl_95| (LU) before
#                            the track is classified an STL-95 outlier by
#                            album_coherence_check (#290 phase 3b). Default 0.5.
#   coherence_lra_floor_lu - Minimum short_term_range (LU) allowed; tracks
#                            below trip an LRA-floor violation regardless of
#                            anchor. Default 1.0.
#   coherence_low_rms_db   - Max |delta_low_rms| (dB) before low-RMS outlier.
#                            Default 2.0.
#   coherence_vocal_rms_db - Max |delta_vocal_rms| (dB) before vocal-RMS outlier.
#                            Default 2.0.
```

- [ ] **Step 4: Run test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_coherence_presets.py -v
```

Expected: PASS.

- [ ] **Step 5: Regression-check: run all existing mastering tests**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/ 2>&1 | tail -5
```

Expected: all pass (phase 3a's test count + 1 new test, all green).

- [ ] **Step 6: Commit**

```bash
git add tools/mastering/genre-presets.yaml tests/unit/mastering/test_coherence_presets.py
git commit -m "$(cat <<'EOF'
feat: add coherence tolerance fields to genre-presets defaults (#290 phase 3b)

Four new fields in the defaults block:
- coherence_stl_95_lu:    0.5 (±LU around anchor's STL-95)
- coherence_lra_floor_lu: 1.0 (minimum short_term_range allowed)
- coherence_low_rms_db:   2.0 (±dB around anchor's low_rms)
- coherence_vocal_rms_db: 2.0 (±dB around anchor's vocal_rms)

Consumed by the upcoming album_coherence_check / album_coherence_correct
MCP tools to classify outlier tracks relative to the anchor. Default
pop-balanced values ship in defaults; per-genre overrides can be added
incrementally as reference-album tuning reveals needs.

Header-comment block extended with per-field docstrings.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Create `coherence.py` with `load_tolerances` + `classify_outliers`

**Files:**
- Create: `tools/mastering/coherence.py`
- Create: `tests/unit/mastering/test_coherence.py`

- [ ] **Step 1: Write failing tests for `load_tolerances`**

Create `tests/unit/mastering/test_coherence.py`:

```python
#!/usr/bin/env python3
"""Unit tests for album coherence classification + correction planning (#290 phase 3b)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.coherence import (
    DEFAULTS,
    classify_outliers,
    build_correction_plan,
    load_tolerances,
)


class TestLoadTolerances:
    def test_none_preset_returns_defaults(self):
        tolerances = load_tolerances(None)
        assert tolerances["coherence_stl_95_lu"] == pytest.approx(0.5)
        assert tolerances["coherence_lra_floor_lu"] == pytest.approx(1.0)
        assert tolerances["coherence_low_rms_db"] == pytest.approx(2.0)
        assert tolerances["coherence_vocal_rms_db"] == pytest.approx(2.0)
        assert tolerances["lufs_tolerance_lu"] == pytest.approx(0.5)

    def test_empty_preset_returns_defaults(self):
        assert load_tolerances({}) == DEFAULTS

    def test_partial_preset_merges_with_defaults(self):
        preset = {"coherence_stl_95_lu": 0.8}  # only override one
        tolerances = load_tolerances(preset)
        assert tolerances["coherence_stl_95_lu"] == pytest.approx(0.8)
        # Other fields fall back to defaults
        assert tolerances["coherence_lra_floor_lu"] == pytest.approx(1.0)

    def test_lufs_tolerance_not_overridable_from_preset(self):
        # lufs_tolerance_lu is hardcoded — presets can't change it
        preset = {"lufs_tolerance_lu": 99.0}
        tolerances = load_tolerances(preset)
        assert tolerances["lufs_tolerance_lu"] == pytest.approx(0.5)
```

- [ ] **Step 2: Run test to verify module missing**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_coherence.py::TestLoadTolerances -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tools.mastering.coherence'`.

- [ ] **Step 3: Create `tools/mastering/coherence.py` skeleton**

```python
"""Album coherence classification + correction planning (#290 phase 3b).

Pure-Python module — no I/O, no MCP coupling. Consumed by the
``album_coherence_check`` / ``album_coherence_correct`` handlers in
``servers/bitwize-music-server/handlers/processing/audio.py``.

Depends only on phase 3a's ``album_signature.AGGREGATE_KEYS`` /
``compute_anchor_deltas`` output shape and the phase 1b analyzer fields.

Scope limit (MVP): ``build_correction_plan`` marks only LUFS outliers
as correctable. STL-95 / LRA / RMS violations are reported by
``classify_outliers`` but deferred for correction to a later phase —
fixing those requires per-track compression/EQ adjustment that this
phase intentionally doesn't ship.
"""

from __future__ import annotations

from typing import Any

DEFAULTS: dict[str, float] = {
    "coherence_stl_95_lu":    0.5,
    "coherence_lra_floor_lu": 1.0,
    "coherence_low_rms_db":   2.0,
    "coherence_vocal_rms_db": 2.0,
    # Hardcoded — matches master_album Stage 5 verify spec. Not a preset field.
    "lufs_tolerance_lu":      0.5,
}


def load_tolerances(preset: dict[str, Any] | None) -> dict[str, float]:
    """Return effective tolerance-band dict, merging preset on top of defaults.

    ``lufs_tolerance_lu`` is always the hardcoded default (0.5) — preset
    values for that key are ignored. All other keys honor preset overrides.
    """
    out = dict(DEFAULTS)
    if preset:
        for key in (
            "coherence_stl_95_lu",
            "coherence_lra_floor_lu",
            "coherence_low_rms_db",
            "coherence_vocal_rms_db",
        ):
            if key in preset and preset[key] is not None:
                out[key] = float(preset[key])
    return out


def classify_outliers(
    deltas: list[dict[str, Any]],
    analysis_results: list[dict[str, Any]],
    tolerances: dict[str, float],
    anchor_index_1based: int,
) -> list[dict[str, Any]]:
    """Classify each track as outlier / ok / missing per metric.

    Implementation lands in Task 3.
    """
    raise NotImplementedError


def build_correction_plan(
    classifications: list[dict[str, Any]],
    analysis_results: list[dict[str, Any]],
    anchor_index_1based: int,
) -> dict[str, Any]:
    """Build per-track correction plan targeting LUFS outliers.

    Implementation lands in Task 4.
    """
    raise NotImplementedError
```

- [ ] **Step 4: Run test to verify `load_tolerances` passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_coherence.py::TestLoadTolerances -v
```

Expected: all four tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/mastering/coherence.py tests/unit/mastering/test_coherence.py
git commit -m "$(cat <<'EOF'
feat: add tools/mastering/coherence.py with load_tolerances (#290 phase 3b)

Introduces a new pure-Python module that will own tolerance-band
merging, outlier classification, and correction planning for the
upcoming album_coherence_check / album_coherence_correct handlers.

This commit ships the DEFAULTS constant + load_tolerances():
- DEFAULTS maps the four coherence_* preset fields to their
  documented defaults plus lufs_tolerance_lu (hardcoded 0.5 LU
  matching master_album Stage 5).
- load_tolerances(preset) merges a partial preset on top of
  defaults key-by-key; lufs_tolerance_lu is non-overridable.

classify_outliers + build_correction_plan are stubbed with
NotImplementedError — next commits fill them in with TDD.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Implement `classify_outliers`

**Files:**
- Modify: `tools/mastering/coherence.py`
- Modify: `tests/unit/mastering/test_coherence.py`

- [ ] **Step 1: Write failing tests for `classify_outliers`**

Append to `tests/unit/mastering/test_coherence.py`:

```python
def _delta(**overrides) -> dict:
    """Minimal delta dict matching compute_anchor_deltas output."""
    base = {
        "index": 1,
        "filename": "01.wav",
        "is_anchor": False,
        "delta_lufs": 0.0,
        "delta_peak_db": 0.0,
        "delta_stl_95": 0.0,
        "delta_short_term_range": 0.0,
        "delta_low_rms": 0.0,
        "delta_vocal_rms": 0.0,
    }
    base.update(overrides)
    return base


def _analysis(**overrides) -> dict:
    """Minimal analyze_track dict — only fields the classifier needs."""
    base = {
        "filename": "01.wav",
        "lufs": -14.0,
        "short_term_range": 6.5,
        "stl_95": -10.5,
        "low_rms": -18.0,
        "vocal_rms": -16.0,
    }
    base.update(overrides)
    return base


TOLERANCES = dict(DEFAULTS)


class TestClassifyOutliers:
    def test_anchor_row_has_no_violations(self):
        deltas = [_delta(index=1, is_anchor=True)]
        analyses = [_analysis()]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=1)
        assert len(result) == 1
        assert result[0]["is_anchor"] is True
        assert result[0]["is_outlier"] is False
        assert result[0]["violations"] == []

    def test_lufs_outlier_flagged_and_marked_correctable(self):
        deltas = [
            _delta(index=1, delta_lufs=1.3),  # well beyond tolerance 0.5
            _delta(index=2, is_anchor=True),
        ]
        analyses = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        track1 = result[0]
        assert track1["is_outlier"] is True
        lufs_violations = [v for v in track1["violations"] if v["metric"] == "lufs"]
        assert len(lufs_violations) == 1
        v = lufs_violations[0]
        assert v["delta"] == pytest.approx(1.3)
        assert v["tolerance"] == pytest.approx(0.5)
        assert v["severity"] == "outlier"
        assert v["correctable"] is True

    def test_lufs_within_tolerance_is_ok(self):
        deltas = [_delta(index=1, delta_lufs=0.3)]  # within ±0.5
        analyses = [_analysis()]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=1)
        # Anchor + one track — anchor index 1 means the only track IS the anchor.
        # For this test, redo with track 1 non-anchor (need ≥2 tracks)
        deltas = [
            _delta(index=1, delta_lufs=0.3),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        track1 = result[0]
        assert track1["is_outlier"] is False
        lufs_violations = [v for v in track1["violations"] if v["metric"] == "lufs"]
        assert len(lufs_violations) == 1
        assert lufs_violations[0]["severity"] == "ok"

    def test_stl_95_outlier_flagged_and_not_correctable(self):
        deltas = [
            _delta(index=1, delta_stl_95=0.9),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        stl_violations = [
            v for v in result[0]["violations"] if v["metric"] == "stl_95"
        ]
        assert len(stl_violations) == 1
        assert stl_violations[0]["severity"] == "outlier"
        assert stl_violations[0]["correctable"] is False

    def test_lra_floor_violation_uses_absolute_threshold(self):
        # anchor preset sets floor = 1.0; a track with short_term_range=0.7 breaches
        deltas = [
            _delta(index=1),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [
            _analysis(filename="01.wav", short_term_range=0.7),   # below floor
            _analysis(filename="02.wav", short_term_range=6.5),
        ]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        floor_violations = [
            v for v in result[0]["violations"] if v["metric"] == "lra_floor"
        ]
        assert len(floor_violations) == 1
        assert floor_violations[0]["value"] == pytest.approx(0.7)
        assert floor_violations[0]["floor"] == pytest.approx(1.0)
        assert floor_violations[0]["severity"] == "outlier"
        assert floor_violations[0]["correctable"] is False

    def test_low_rms_outlier_flagged(self):
        deltas = [
            _delta(index=1, delta_low_rms=2.5),  # beyond ±2.0
            _delta(index=2, is_anchor=True),
        ]
        analyses = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        lr_violations = [
            v for v in result[0]["violations"] if v["metric"] == "low_rms"
        ]
        assert len(lr_violations) == 1
        assert lr_violations[0]["severity"] == "outlier"
        assert lr_violations[0]["correctable"] is False

    def test_vocal_rms_outlier_flagged(self):
        deltas = [
            _delta(index=1, delta_vocal_rms=-2.8),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        vr = [v for v in result[0]["violations"] if v["metric"] == "vocal_rms"]
        assert vr[0]["severity"] == "outlier"

    def test_missing_metric_produces_missing_severity(self):
        deltas = [
            _delta(index=1, delta_low_rms=None),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [
            _analysis(filename="01.wav", low_rms=None),
            _analysis(filename="02.wav"),
        ]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        lr = [v for v in result[0]["violations"] if v["metric"] == "low_rms"]
        assert len(lr) == 1
        assert lr[0]["severity"] == "missing"
        # Missing doesn't count as is_outlier
        # (unless there's ANOTHER outlier metric on the same track)

    def test_multiple_violations_on_one_track(self):
        deltas = [
            _delta(index=1, delta_lufs=1.3, delta_stl_95=0.9, delta_vocal_rms=2.5),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        track1 = result[0]
        assert track1["is_outlier"] is True
        outlier_metrics = {
            v["metric"] for v in track1["violations"] if v["severity"] == "outlier"
        }
        assert outlier_metrics == {"lufs", "stl_95", "vocal_rms"}

    def test_missing_alone_does_not_flag_outlier(self):
        deltas = [
            _delta(index=1, delta_low_rms=None),
            _delta(index=2, is_anchor=True),
        ]
        analyses = [
            _analysis(filename="01.wav", low_rms=None),
            _analysis(filename="02.wav"),
        ]
        result = classify_outliers(deltas, analyses, TOLERANCES, anchor_index_1based=2)
        assert result[0]["is_outlier"] is False
```

- [ ] **Step 2: Run tests to verify they fail with NotImplementedError**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_coherence.py::TestClassifyOutliers -v
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement `classify_outliers`**

Replace the stub in `tools/mastering/coherence.py`:

```python
def classify_outliers(
    deltas: list[dict[str, Any]],
    analysis_results: list[dict[str, Any]],
    tolerances: dict[str, float],
    anchor_index_1based: int,
) -> list[dict[str, Any]]:
    """Classify each track against the coherence tolerance bands.

    Args:
        deltas: Output of ``album_signature.compute_anchor_deltas``.
        analysis_results: Original ``analyze_track`` dicts (for
            absolute-value checks like ``lra_floor`` that don't fit
            the delta-from-anchor pattern).
        tolerances: Output of ``load_tolerances``.
        anchor_index_1based: 1-based track number of the anchor.
            Anchor's own row is returned with empty violations.

    Returns:
        List of classification dicts — one per track, in track-number
        order. See the phase-3b plan for the full shape.
    """
    if len(deltas) != len(analysis_results):
        raise ValueError(
            f"deltas length ({len(deltas)}) != analysis_results length "
            f"({len(analysis_results)})"
        )

    out: list[dict[str, Any]] = []
    for delta, track in zip(deltas, analysis_results):
        idx = delta["index"]
        is_anchor = (idx == anchor_index_1based)
        row: dict[str, Any] = {
            "index":       idx,
            "filename":    delta.get("filename") or track.get("filename"),
            "is_anchor":   is_anchor,
            "is_outlier":  False,
            "violations":  [],
        }

        if is_anchor:
            out.append(row)
            continue

        # LUFS — correctable in MVP
        row["violations"].append(_delta_check(
            metric="lufs",
            delta=delta.get("delta_lufs"),
            tolerance=tolerances["lufs_tolerance_lu"],
            correctable=True,
        ))
        # STL-95 — not correctable
        row["violations"].append(_delta_check(
            metric="stl_95",
            delta=delta.get("delta_stl_95"),
            tolerance=tolerances["coherence_stl_95_lu"],
            correctable=False,
        ))
        # LRA floor — absolute value check, not delta
        row["violations"].append(_floor_check(
            metric="lra_floor",
            value=track.get("short_term_range"),
            floor=tolerances["coherence_lra_floor_lu"],
        ))
        # low-RMS — not correctable
        row["violations"].append(_delta_check(
            metric="low_rms",
            delta=delta.get("delta_low_rms"),
            tolerance=tolerances["coherence_low_rms_db"],
            correctable=False,
        ))
        # vocal-RMS — not correctable
        row["violations"].append(_delta_check(
            metric="vocal_rms",
            delta=delta.get("delta_vocal_rms"),
            tolerance=tolerances["coherence_vocal_rms_db"],
            correctable=False,
        ))

        row["is_outlier"] = any(
            v["severity"] == "outlier" for v in row["violations"]
        )
        out.append(row)
    return out


def _delta_check(*, metric: str, delta: float | None, tolerance: float,
                 correctable: bool) -> dict[str, Any]:
    if delta is None:
        return {
            "metric":      metric,
            "delta":       None,
            "tolerance":   tolerance,
            "severity":    "missing",
            "correctable": False,
        }
    severity = "outlier" if abs(float(delta)) > float(tolerance) else "ok"
    return {
        "metric":      metric,
        "delta":       float(delta),
        "tolerance":   tolerance,
        "severity":    severity,
        "correctable": correctable if severity == "outlier" else False,
    }


def _floor_check(*, metric: str, value: float | None, floor: float) -> dict[str, Any]:
    if value is None:
        return {
            "metric":      metric,
            "value":       None,
            "floor":       floor,
            "severity":    "missing",
            "correctable": False,
        }
    severity = "outlier" if float(value) < float(floor) else "ok"
    return {
        "metric":      metric,
        "value":       float(value),
        "floor":       floor,
        "severity":    severity,
        "correctable": False,
    }
```

- [ ] **Step 4: Run `TestClassifyOutliers` — verify all pass**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_coherence.py::TestClassifyOutliers -v
```

Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/mastering/coherence.py tests/unit/mastering/test_coherence.py
git commit -m "$(cat <<'EOF'
feat: classify_outliers tolerance classifier (#290 phase 3b)

classify_outliers consumes the phase-3a compute_anchor_deltas output
plus per-genre tolerance bands and produces a per-track violation
list. Five metrics are checked per track:
- lufs:      ±0.5 LU delta (correctable in MVP)
- stl_95:    ±0.5 LU delta (reported, not correctable)
- lra_floor: absolute floor of 1.0 LU on short_term_range
- low_rms:   ±2.0 dB delta (reported, not correctable)
- vocal_rms: ±2.0 dB delta (reported, not correctable)

Missing metrics (e.g., None vocal_rms) produce severity="missing"
which does NOT flag the track as an outlier — can't classify what
the analyzer couldn't compute.

10 new unit tests covering every metric, severity state, and the
anchor / no-anchor paths.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Implement `build_correction_plan`

**Files:**
- Modify: `tools/mastering/coherence.py`
- Modify: `tests/unit/mastering/test_coherence.py`

- [ ] **Step 1: Write failing tests for `build_correction_plan`**

Append to `tests/unit/mastering/test_coherence.py`:

```python
class TestBuildCorrectionPlan:
    def test_anchor_is_in_skipped(self):
        classifications = [
            {"index": 1, "filename": "01.wav", "is_anchor": False,
             "is_outlier": False, "violations": []},
            {"index": 2, "filename": "02.wav", "is_anchor": True,
             "is_outlier": False, "violations": []},
        ]
        analyses = [
            _analysis(filename="01.wav", lufs=-14.0),
            _analysis(filename="02.wav", lufs=-14.1),
        ]
        plan = build_correction_plan(classifications, analyses, anchor_index_1based=2)
        skipped_indices = {s["index"] for s in plan["skipped"]}
        assert 2 in skipped_indices
        anchor_entry = next(s for s in plan["skipped"] if s["index"] == 2)
        assert anchor_entry["reason"] == "is_anchor"

    def test_clean_tracks_are_skipped(self):
        classifications = [
            {"index": 1, "filename": "01.wav", "is_anchor": False,
             "is_outlier": False, "violations": [
                 {"metric": "lufs", "delta": 0.1, "tolerance": 0.5,
                  "severity": "ok", "correctable": False},
             ]},
            {"index": 2, "filename": "02.wav", "is_anchor": True,
             "is_outlier": False, "violations": []},
        ]
        analyses = [
            _analysis(filename="01.wav", lufs=-14.0),
            _analysis(filename="02.wav", lufs=-14.1),
        ]
        plan = build_correction_plan(classifications, analyses, anchor_index_1based=2)
        skipped_reasons = {s["index"]: s["reason"] for s in plan["skipped"]}
        assert skipped_reasons.get(1) == "no_violations"

    def test_lufs_outlier_is_correctable_with_anchor_lufs(self):
        classifications = [
            {"index": 1, "filename": "01.wav", "is_anchor": False,
             "is_outlier": True, "violations": [
                 {"metric": "lufs", "delta": 1.3, "tolerance": 0.5,
                  "severity": "outlier", "correctable": True},
             ]},
            {"index": 2, "filename": "02.wav", "is_anchor": True,
             "is_outlier": False, "violations": []},
        ]
        analyses = [
            _analysis(filename="01.wav", lufs=-12.8),   # outlier
            _analysis(filename="02.wav", lufs=-14.1),   # anchor, measured
        ]
        plan = build_correction_plan(classifications, analyses, anchor_index_1based=2)

        assert plan["anchor_index"] == 2
        assert plan["anchor_lufs"] == pytest.approx(-14.1)
        correctable = [c for c in plan["corrections"] if c["correctable"]]
        assert len(correctable) == 1
        entry = correctable[0]
        assert entry["index"] == 1
        assert entry["corrected_target_lufs"] == pytest.approx(-14.1)
        assert "LUFS outlier" in entry["reason"]

    def test_non_lufs_only_outlier_is_not_correctable(self):
        classifications = [
            {"index": 1, "filename": "01.wav", "is_anchor": False,
             "is_outlier": True, "violations": [
                 {"metric": "lufs", "delta": 0.2, "tolerance": 0.5,
                  "severity": "ok", "correctable": False},
                 {"metric": "stl_95", "delta": 0.9, "tolerance": 0.5,
                  "severity": "outlier", "correctable": False},
             ]},
            {"index": 2, "filename": "02.wav", "is_anchor": True,
             "is_outlier": False, "violations": []},
        ]
        analyses = [
            _analysis(filename="01.wav", lufs=-14.0),
            _analysis(filename="02.wav", lufs=-14.1),
        ]
        plan = build_correction_plan(classifications, analyses, anchor_index_1based=2)

        uncorrectable = [c for c in plan["corrections"] if not c["correctable"]]
        assert len(uncorrectable) == 1
        assert "MVP scope" in uncorrectable[0]["reason"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_coherence.py::TestBuildCorrectionPlan -v
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement `build_correction_plan`**

Replace the stub in `tools/mastering/coherence.py`:

```python
def build_correction_plan(
    classifications: list[dict[str, Any]],
    analysis_results: list[dict[str, Any]],
    anchor_index_1based: int,
) -> dict[str, Any]:
    """Build a per-track correction plan targeting LUFS outliers.

    Args:
        classifications: Output of ``classify_outliers``.
        analysis_results: Original ``analyze_track`` dicts (used for
            anchor LUFS lookup and the ``original_target_lufs`` field —
            though the latter isn't strictly known here; we leave it
            to the caller to fill in from the preset if desired).
        anchor_index_1based: 1-based track number of the anchor.

    Returns:
        Dict with:
          anchor_index: 1-based anchor index
          anchor_lufs:  measured LUFS of the anchor (ground truth)
          corrections:  list of per-track correction dicts
          skipped:      list of {index, filename, reason} for the
                        anchor + clean tracks
    """
    if not (1 <= anchor_index_1based <= len(analysis_results)):
        raise ValueError(
            f"anchor_index_1based={anchor_index_1based} out of range "
            f"[1, {len(analysis_results)}]"
        )

    anchor_analysis = analysis_results[anchor_index_1based - 1]
    anchor_lufs = float(anchor_analysis.get("lufs", 0.0))

    corrections: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for cls in classifications:
        if cls["is_anchor"]:
            skipped.append({
                "index":    cls["index"],
                "filename": cls.get("filename"),
                "reason":   "is_anchor",
            })
            continue

        lufs_violation = next(
            (v for v in cls["violations"]
             if v["metric"] == "lufs" and v["severity"] == "outlier"),
            None,
        )
        non_lufs_outliers = [
            v for v in cls["violations"]
            if v["metric"] != "lufs" and v["severity"] == "outlier"
        ]

        if lufs_violation is not None:
            corrections.append({
                "index":                cls["index"],
                "filename":             cls.get("filename"),
                "correctable":          True,
                "corrected_target_lufs": anchor_lufs,
                "reason": (
                    f"LUFS outlier: delta={lufs_violation['delta']:+.2f}, "
                    f"tolerance=±{lufs_violation['tolerance']:.2f}"
                ),
            })
        elif non_lufs_outliers:
            metrics = ", ".join(sorted({v["metric"] for v in non_lufs_outliers}))
            corrections.append({
                "index":       cls["index"],
                "filename":    cls.get("filename"),
                "correctable": False,
                "reason": (
                    f"Only non-LUFS violations ({metrics}) — MVP scope "
                    f"skips; revisit when compression-ratio correction lands."
                ),
            })
        else:
            skipped.append({
                "index":    cls["index"],
                "filename": cls.get("filename"),
                "reason":   "no_violations",
            })

    return {
        "anchor_index":  anchor_index_1based,
        "anchor_lufs":   anchor_lufs,
        "corrections":   corrections,
        "skipped":       skipped,
    }
```

- [ ] **Step 4: Run tests to verify all pass**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_coherence.py -v
```

Expected: all tests PASS (4 load_tolerances + 10 classify_outliers + 4 build_correction_plan = 18 tests).

- [ ] **Step 5: Commit**

```bash
git add tools/mastering/coherence.py tests/unit/mastering/test_coherence.py
git commit -m "$(cat <<'EOF'
feat: build_correction_plan for LUFS-only correction (#290 phase 3b)

build_correction_plan consumes classify_outliers output and produces
a per-track plan:
- Anchor track → skipped with reason="is_anchor"
- Clean tracks → skipped with reason="no_violations"
- LUFS-outlier tracks → correctable, corrected_target_lufs = anchor's
  measured LUFS (ground truth, not the preset target — guarantees
  convergence because we chase real output)
- Non-LUFS-only outliers → non-correctable with a clear reason string
  explaining the MVP scope limit

The anchor's measured LUFS becomes the correction target so we match
the actual mastered output rather than an idealized preset target that
the first mastering pass may have missed by a few tenths of a dB.

4 new unit tests covering every branch.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Add `album_coherence_check` handler

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py`
- Create: `tests/unit/mastering/test_album_coherence_handlers.py`

- [ ] **Step 1: Write failing integration test**

Create `tests/unit/mastering/test_album_coherence_handlers.py`:

```python
"""Integration tests for album_coherence_check / album_coherence_correct (#290 phase 3b)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402


def _write_sine_wav(path: Path, *, duration: float = 60.0, sample_rate: int = 44100,
                    freq: float = 220.0, amplitude: float = 0.3) -> Path:
    import soundfile as sf

    n = int(duration * sample_rate)
    t = np.arange(n) / sample_rate
    mono = amplitude * np.sin(2 * np.pi * freq * t).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    sf.write(str(path), stereo, sample_rate, subtype="PCM_24")
    return path


def _setup_mastered_album(tmp_path: Path, loudness_amplitudes: list[float]) -> Path:
    """Create mastered/ subdir with N tracks at given amplitudes (→ varying LUFS)."""
    mastered = tmp_path / "mastered"
    mastered.mkdir()
    for i, amp in enumerate(loudness_amplitudes, start=1):
        _write_sine_wav(
            mastered / f"{i:02d}-track.wav",
            freq=200.0 + i * 30.0,
            amplitude=amp,
        )
    return tmp_path


def test_album_coherence_check_flags_lufs_outlier(tmp_path: Path) -> None:
    # Track 2 is ~2-3 LU louder than 1 and 3 → LUFS outlier.
    _setup_mastered_album(tmp_path, loudness_amplitudes=[0.3, 0.6, 0.3])

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_check(
                album_slug="test-album", subfolder="mastered",
                genre="pop", anchor_track=1,
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert "summary" in result
    assert result["summary"]["track_count"] == 3
    # At least one outlier (track 2)
    assert result["summary"]["outlier_count"] >= 1
    # classifications should reveal which track is the outlier
    outliers = [c for c in result["classifications"] if c["is_outlier"]]
    assert any(c["index"] == 2 for c in outliers)


def test_album_coherence_check_errors_without_genre_and_anchor(tmp_path: Path) -> None:
    _setup_mastered_album(tmp_path, loudness_amplitudes=[0.3, 0.3])

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_check(
                album_slug="test-album", subfolder="mastered",
            )
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "genre" in result["error"].lower() or "anchor" in result["error"].lower()


def test_album_coherence_check_falls_back_to_defaults_when_genre_empty_with_anchor(tmp_path: Path) -> None:
    _setup_mastered_album(tmp_path, loudness_amplitudes=[0.3, 0.35])

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_check(
                album_slug="test-album", subfolder="mastered",
                anchor_track=1,  # no genre — should use hardcoded defaults
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert result["settings"]["tolerances"]["coherence_stl_95_lu"] == pytest.approx(0.5)
```

Add `import pytest` at the top of the test file.

- [ ] **Step 2: Run test to verify handler missing**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_album_coherence_handlers.py::test_album_coherence_check_flags_lufs_outlier -v
```

Expected: FAIL with `AttributeError: module 'handlers.processing.audio' has no attribute 'album_coherence_check'`.

- [ ] **Step 3: Add the handler to `audio.py`**

Insert **after** `measure_album_signature` and **before** `def register(mcp: Any)`:

```python
async def album_coherence_check(
    album_slug: str,
    subfolder: str = "mastered",
    genre: str = "",
    anchor_track: int | None = None,
) -> str:
    """Check an album's mastered tracks for coherence outliers vs. the anchor.

    Runs the same measurement pipeline as measure_album_signature, then
    classifies each non-anchor track against per-genre tolerance bands:
      • LUFS delta (±0.5 LU, correctable in MVP)
      • STL-95 delta (±coherence_stl_95_lu, reported)
      • LRA floor (short_term_range ≥ coherence_lra_floor_lu, reported)
      • low-RMS delta (±coherence_low_rms_db, reported)
      • vocal-RMS delta (±coherence_vocal_rms_db, reported)

    Read-only — no files modified. Use album_coherence_correct to
    actually re-master LUFS outliers.

    Args:
        album_slug: Album slug.
        subfolder: Directory to scan for WAVs (default "mastered").
        genre: Genre preset slug. Required unless anchor_track is given
            (in which case hardcoded default tolerances are used and a
            warning is emitted).
        anchor_track: Optional 1-based track number override for the
            anchor. Overrides genre-driven composite scoring + state-
            cache frontmatter.

    Returns:
        JSON string with settings, album aggregates, anchor block,
        per-track classifications, and summary counts.
    """
    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # Resolve source directory.
    if subfolder:
        if not _is_path_confined(audio_dir, subfolder):
            return _safe_json({
                "error": (
                    f"Invalid subfolder: path must not escape the album "
                    f"directory (got {subfolder!r})"
                ),
            })
        source_dir = audio_dir / subfolder
        if not source_dir.is_dir():
            return _safe_json({
                "error": f"Subfolder not found: {source_dir}",
            })
    else:
        source_dir = _find_wav_source_dir(audio_dir)

    wav_files = sorted([
        f for f in source_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])
    if not wav_files:
        return _safe_json({"error": f"No WAV files found in {source_dir}"})

    # Require either genre or explicit anchor — otherwise there are no
    # tolerances to check against and no way to pick an anchor.
    if not genre and anchor_track is None:
        return _safe_json({
            "error": (
                "album_coherence_check requires either a genre (for "
                "tolerances + anchor selection) or an explicit anchor_track "
                "(falls back to default tolerances with a warning)."
            ),
        })

    # Preset + tolerance resolution.
    from tools.mastering.coherence import (
        classify_outliers,
        load_tolerances,
    )

    preset_dict: dict[str, Any] | None = None
    warnings: list[str] = []
    if genre:
        from tools.mastering.config import build_effective_preset
        bundle = build_effective_preset(
            genre=genre,
            cut_highmid_arg=0.0,
            cut_highs_arg=0.0,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        if bundle["error"] is not None:
            return _safe_json({
                "error": bundle["error"]["reason"],
                "available_genres": bundle["error"].get("available_genres", []),
            })
        preset_dict = bundle["preset_dict"]
    else:
        warnings.append(
            "No genre supplied — using default coherence tolerances. "
            "Pass genre= for per-genre-tuned tolerances when they become "
            "available."
        )

    tolerances = load_tolerances(preset_dict)

    # Override resolution (explicit > cache > none).
    override_index: int | None = None
    if isinstance(anchor_track, int) and not isinstance(anchor_track, bool):
        override_index = anchor_track
    elif _shared.cache is not None:
        state_albums = (_shared.cache.get_state() or {}).get("albums", {})
        album_state = state_albums.get(_normalize_slug(album_slug), {})
        raw_override = album_state.get("anchor_track")
        if isinstance(raw_override, int) and not isinstance(raw_override, bool):
            override_index = raw_override

    # Run analysis, build signature, select anchor, compute deltas, classify.
    from tools.mastering.analyze_tracks import analyze_track
    from tools.mastering.album_signature import (
        build_signature,
        compute_anchor_deltas,
    )
    from tools.mastering.anchor_selector import select_anchor

    loop = asyncio.get_running_loop()
    analysis_results: list[dict[str, Any]] = []
    for wav in wav_files:
        result = await loop.run_in_executor(None, analyze_track, str(wav))
        analysis_results.append(result)

    signature = build_signature(analysis_results)

    anchor_result = select_anchor(
        analysis_results,
        preset_dict or {},
        override_index=override_index,
    )

    anchor_block: dict[str, Any] = {
        "selected_index":  anchor_result["selected_index"],
        "method":          anchor_result["method"],
        "override_index":  anchor_result["override_index"],
        "override_reason": anchor_result["override_reason"],
        "scores":          anchor_result["scores"],
    }

    classifications: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "track_count":          len(analysis_results),
        "outlier_count":        0,
        "correctable_count":    0,
        "uncorrectable_count":  0,
        "metric_breakdown": {
            m: {"outliers": 0, "missing": 0}
            for m in ("lufs", "stl_95", "lra_floor", "low_rms", "vocal_rms")
        },
    }

    selected = anchor_result["selected_index"]
    if isinstance(selected, int) and 1 <= selected <= len(analysis_results):
        deltas = compute_anchor_deltas(analysis_results, anchor_index_1based=selected)
        anchor_block["deltas"] = deltas
        classifications = classify_outliers(
            deltas, analysis_results, tolerances, anchor_index_1based=selected,
        )
        for cls in classifications:
            has_lufs_correctable = any(
                v["metric"] == "lufs" and v["severity"] == "outlier"
                for v in cls["violations"]
            )
            has_non_lufs_outlier = any(
                v["metric"] != "lufs" and v["severity"] == "outlier"
                for v in cls["violations"]
            )
            if cls["is_outlier"]:
                summary["outlier_count"] += 1
                if has_lufs_correctable:
                    summary["correctable_count"] += 1
                elif has_non_lufs_outlier:
                    summary["uncorrectable_count"] += 1
            for v in cls["violations"]:
                metric = v["metric"]
                if v["severity"] == "outlier":
                    summary["metric_breakdown"][metric]["outliers"] += 1
                elif v["severity"] == "missing":
                    summary["metric_breakdown"][metric]["missing"] += 1
    else:
        anchor_block["deltas"] = []
        warnings.append(
            "Anchor selector returned no eligible tracks; classifications "
            "skipped. Check signature metrics — some tracks likely have "
            "stl_95=None or missing band_energy."
        )

    response = {
        "album_slug": album_slug,
        "source_dir": str(source_dir),
        "settings": {
            "genre":      genre.lower() if genre else None,
            "subfolder":  subfolder,
            "tolerances": tolerances,
        },
        "album":           signature["album"],
        "anchor":          anchor_block,
        "classifications": classifications,
        "summary":         summary,
    }
    if warnings:
        response["warnings"] = warnings
    return _safe_json(response)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_album_coherence_handlers.py -v
```

Expected: all three tests PASS.

- [ ] **Step 5: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py \
        tests/unit/mastering/test_album_coherence_handlers.py
git commit -m "$(cat <<'EOF'
feat: add album_coherence_check handler (#290 phase 3b)

Read-only MCP tool that classifies each mastered track against the
selected anchor using five per-genre tolerance bands:
- lufs      (±0.5 LU, hardcoded, correctable)
- stl_95    (±coherence_stl_95_lu, reported)
- lra_floor (absolute floor, reported)
- low_rms   (±coherence_low_rms_db, reported)
- vocal_rms (±coherence_vocal_rms_db, reported)

Requires either genre= (preferred) or anchor_track= (falls back to
default tolerances with a warning in the response). Response includes
a summary block with outlier counts broken down by metric so callers
can triage at a glance.

Three integration tests:
- LUFS outlier detected (amplitude-varied sine tracks)
- Errors without genre + anchor
- Falls back to default tolerances when anchor_track is given without genre

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Add `album_coherence_correct` handler

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py`
- Modify: `tests/unit/mastering/test_album_coherence_handlers.py`

- [ ] **Step 1: Write failing integration tests**

Append to `tests/unit/mastering/test_album_coherence_handlers.py`:

```python
def _setup_full_album(tmp_path: Path, amplitudes: list[float]) -> Path:
    """Create polished/ + mastered/ subdirs with matching WAV names."""
    polished = tmp_path / "polished"
    polished.mkdir()
    mastered = tmp_path / "mastered"
    mastered.mkdir()
    for i, amp in enumerate(amplitudes, start=1):
        name = f"{i:02d}-track.wav"
        _write_sine_wav(polished / name, freq=200.0 + i * 30.0, amplitude=amp)
        _write_sine_wav(mastered / name, freq=200.0 + i * 30.0, amplitude=amp)
    return tmp_path


def test_album_coherence_correct_dry_run_does_not_write(tmp_path: Path) -> None:
    _setup_full_album(tmp_path, amplitudes=[0.3, 0.6, 0.3])
    mastered_bytes_before = (tmp_path / "mastered" / "02-track.wav").read_bytes()

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_correct(
                album_slug="test-album",
                genre="pop",
                source_subfolder="polished",
                check_subfolder="mastered",
                anchor_track=1,
                dry_run=True,
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert result["dry_run"] is True
    assert "plan" in result
    # Mastered file unchanged
    assert (tmp_path / "mastered" / "02-track.wav").read_bytes() == mastered_bytes_before


def test_album_coherence_correct_errors_when_polished_missing(tmp_path: Path) -> None:
    # Set up mastered/ but not polished/
    _setup_mastered_album(tmp_path, loudness_amplitudes=[0.3, 0.6])

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_correct(
                album_slug="test-album",
                genre="pop",
                source_subfolder="polished",
                anchor_track=1,
            )
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "polished" in result["error"].lower() or "not found" in result["error"].lower()


def test_album_coherence_correct_errors_when_polished_missing_a_track(tmp_path: Path) -> None:
    _setup_full_album(tmp_path, amplitudes=[0.3, 0.6])
    # Remove polished/02 so mastered has it but polished doesn't.
    (tmp_path / "polished" / "02-track.wav").unlink()

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_correct(
                album_slug="test-album",
                genre="pop",
                source_subfolder="polished",
                anchor_track=1,
            )
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "missing" in result["error"].lower() or "02-track" in result["error"]


def test_album_coherence_correct_remasters_lufs_outlier(tmp_path: Path) -> None:
    # Track 2 starts much louder (amplitude 0.6 → ~-7 LUFS vs -14 LUFS).
    # After correction it should land within tolerance of track 1 (anchor).
    _setup_full_album(tmp_path, amplitudes=[0.3, 0.6, 0.3])

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.album_coherence_correct(
                album_slug="test-album",
                genre="pop",
                source_subfolder="polished",
                check_subfolder="mastered",
                anchor_track=1,
                dry_run=False,
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert result["dry_run"] is False
    # At least one track was corrected
    assert result["summary"]["corrected"] >= 1
    # Post-correction outliers should be ≤ pre-correction outliers
    assert result["summary"]["outliers_after"] <= result["summary"]["outliers_before"]
    # Track 2's corrected LUFS should be within 1 dB of anchor's LUFS
    # (synthetic sines don't master as cleanly as real music, so allow 1 dB)
    correction = next(c for c in result["corrections"] if c["filename"] == "02-track.wav")
    assert correction["status"] == "ok"
    assert abs(correction["delta_from_anchor"]) < 1.0
```

- [ ] **Step 2: Run tests to verify they fail with AttributeError**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_album_coherence_handlers.py -v -k correct
```

Expected: FAIL with `AttributeError: ... has no attribute 'album_coherence_correct'`.

- [ ] **Step 3: Add the handler to `audio.py`**

Insert **after** `album_coherence_check`:

```python
async def album_coherence_correct(
    album_slug: str,
    genre: str,
    source_subfolder: str = "polished",
    check_subfolder: str = "mastered",
    target_lufs: float = -14.0,
    ceiling_db: float = -1.0,
    cut_highmid: float = 0.0,
    cut_highs: float = 0.0,
    anchor_track: int | None = None,
    dry_run: bool = False,
) -> str:
    """Re-master LUFS-outlier tracks from polished/ into mastered/.

    First runs the same logic as album_coherence_check to identify
    outliers, then — for each LUFS outlier — re-runs master_track on
    the corresponding polished/<track>.wav with target_lufs set to the
    anchor's measured LUFS. Outputs stage into a .coherence_staging/
    subfolder and atomically replace the originals in mastered/ on
    full success.

    Non-LUFS outliers (STL-95, LRA floor, low-RMS, vocal-RMS) are
    reported in the response but NOT corrected in MVP — fixing those
    requires per-track compression/EQ adjustment that this phase
    intentionally defers.

    Args:
        album_slug: Album slug.
        genre: Genre preset — required (tolerances + preset base).
        source_subfolder: Directory to re-master from (default "polished").
        check_subfolder: Directory to measure first (default "mastered").
        target_lufs / ceiling_db / cut_highmid / cut_highs: Mastering
            overrides — same semantics as master_album. Used only as
            the initial preset; per-track target_lufs is overridden
            with the anchor's measured LUFS during correction.
        anchor_track: Optional explicit anchor.
        dry_run: When True, build the correction plan and return it
            without writing any files. Useful for CI preview.

    Returns:
        JSON with pre-correction measurement, plan, per-track
        correction results, post-correction re-measurement, and
        summary. On error, returns {"error": ...}.
    """
    if not genre:
        return _safe_json({
            "error": "album_coherence_correct requires a genre for tolerance + preset resolution.",
        })

    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # Validate both subfolders exist and contain matching file sets.
    if not _is_path_confined(audio_dir, source_subfolder) \
            or not _is_path_confined(audio_dir, check_subfolder):
        return _safe_json({
            "error": "Invalid subfolder: path must not escape album directory.",
        })
    polished_dir = audio_dir / source_subfolder
    mastered_dir = audio_dir / check_subfolder
    if not polished_dir.is_dir():
        return _safe_json({
            "error": (
                f"Source subfolder not found: {polished_dir}. "
                f"Run polish_audio first, then master_album, then retry."
            ),
        })
    if not mastered_dir.is_dir():
        return _safe_json({
            "error": f"Check subfolder not found: {mastered_dir}",
        })

    polished_names = {
        f.name for f in polished_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    }
    mastered_names = {
        f.name for f in mastered_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    }
    missing_in_polished = sorted(mastered_names - polished_names)
    if missing_in_polished:
        return _safe_json({
            "error": (
                f"Tracks present in {check_subfolder}/ but missing from "
                f"{source_subfolder}/: {missing_in_polished}. Cannot re-master "
                f"without pre-limiter source."
            ),
        })

    # Delegate check to the shared measure-then-classify path by calling
    # album_coherence_check's own handler for the pre-correction report.
    pre_json = await album_coherence_check(
        album_slug=album_slug,
        subfolder=check_subfolder,
        genre=genre,
        anchor_track=anchor_track,
    )
    pre = json.loads(pre_json)
    if "error" in pre:
        return _safe_json({"error": pre["error"], **pre})

    # Build correction plan.
    from tools.mastering.coherence import build_correction_plan
    classifications = pre["classifications"]
    anchor_idx = pre["anchor"]["selected_index"]
    if anchor_idx is None:
        return _safe_json({
            "error": "Anchor selector returned no eligible tracks — cannot correct.",
            "pre_correction": pre,
        })

    # We need analysis_results for the plan builder. Re-analyze the
    # mastered/ dir (cheap on small albums and ensures the plan builder
    # sees exactly what the check saw).
    from tools.mastering.analyze_tracks import analyze_track
    loop = asyncio.get_running_loop()
    mastered_wavs = sorted([
        f for f in mastered_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])
    pre_analysis: list[dict[str, Any]] = []
    for wav in mastered_wavs:
        result = await loop.run_in_executor(None, analyze_track, str(wav))
        pre_analysis.append(result)

    plan = build_correction_plan(
        classifications, pre_analysis, anchor_index_1based=anchor_idx,
    )

    response: dict[str, Any] = {
        "album_slug": album_slug,
        "dry_run":    dry_run,
        "settings": {
            "genre":             genre,
            "source_subfolder":  source_subfolder,
            "check_subfolder":   check_subfolder,
        },
        "pre_correction": pre,
        "plan":           plan,
        "corrections":    [],
    }

    if dry_run:
        response["summary"] = {
            "corrected":       0,
            "skipped":         len(plan["skipped"]),
            "failed":          0,
            "anchor_lufs":     plan["anchor_lufs"],
            "outliers_before": pre["summary"]["outlier_count"],
            "outliers_after":  pre["summary"]["outlier_count"],
        }
        return _safe_json(response)

    # Build the base effective preset once — shared by all corrections.
    from tools.mastering.config import build_effective_preset
    from tools.mastering.master_tracks import master_track

    import soundfile as _sf
    try:
        source_sample_rate = int(_sf.info(str(mastered_wavs[0])).samplerate)
    except Exception:
        source_sample_rate = None

    bundle = build_effective_preset(
        genre=genre,
        cut_highmid_arg=cut_highmid,
        cut_highs_arg=cut_highs,
        target_lufs_arg=target_lufs,
        ceiling_db_arg=ceiling_db,
        source_sample_rate=source_sample_rate,
    )
    if bundle["error"] is not None:
        return _safe_json({
            "error": bundle["error"]["reason"],
            "available_genres": bundle["error"].get("available_genres", []),
        })
    effective_preset = bundle["effective_preset"]

    staging_dir = mastered_dir.parent / ".coherence_staging"
    staging_dir.mkdir(exist_ok=True)

    failed = 0
    try:
        for entry in plan["corrections"]:
            if not entry["correctable"]:
                continue
            filename = entry["filename"]
            src = polished_dir / filename
            if not src.is_file():
                response["corrections"].append({
                    "filename":           filename,
                    "status":             "failed",
                    "failure_reason":     f"Polished source missing: {src}",
                    "applied_target_lufs": entry["corrected_target_lufs"],
                })
                failed += 1
                continue
            modified_preset = dict(effective_preset)
            modified_preset["target_lufs"] = entry["corrected_target_lufs"]
            staged = staging_dir / filename
            try:
                await loop.run_in_executor(
                    None,
                    lambda sp=src, op=staged, mp=modified_preset:
                        master_track(sp, op, preset=mp),
                )
            except Exception as exc:  # pragma: no cover - defensive
                response["corrections"].append({
                    "filename":           filename,
                    "status":             "failed",
                    "failure_reason":     f"master_track raised: {exc}",
                    "applied_target_lufs": entry["corrected_target_lufs"],
                })
                failed += 1
                continue

            # Re-measure the staged file to confirm convergence.
            staged_result = await loop.run_in_executor(
                None, analyze_track, str(staged),
            )
            delta = staged_result["lufs"] - plan["anchor_lufs"]
            response["corrections"].append({
                "filename":             filename,
                "original_lufs":        next(
                    (t["lufs"] for t in pre_analysis if t["filename"] == filename),
                    None,
                ),
                "applied_target_lufs":  entry["corrected_target_lufs"],
                "result_lufs":          staged_result["lufs"],
                "status":               "ok",
                "delta_from_anchor":    delta,
                "within_tolerance":     abs(delta) <= 0.5,
            })

        # Atomic promote: move staged files over the originals.
        if failed == 0 and response["corrections"]:
            for entry in response["corrections"]:
                if entry["status"] != "ok":
                    continue
                staged = staging_dir / entry["filename"]
                final = mastered_dir / entry["filename"]
                staged.replace(final)
    finally:
        # Clean up staging — either we promoted or we're aborting.
        for f in staging_dir.iterdir():
            try:
                f.unlink()
            except OSError:
                pass
        try:
            staging_dir.rmdir()
        except OSError:
            pass

    # Re-run check against the now-updated mastered/ dir for the post-report.
    post_json = await album_coherence_check(
        album_slug=album_slug,
        subfolder=check_subfolder,
        genre=genre,
        anchor_track=anchor_track,
    )
    post = json.loads(post_json)
    response["post_correction"] = post

    response["summary"] = {
        "corrected":       sum(1 for c in response["corrections"] if c["status"] == "ok"),
        "skipped":         len(plan["skipped"])
                          + sum(1 for c in plan["corrections"] if not c["correctable"]),
        "failed":          failed,
        "anchor_lufs":     plan["anchor_lufs"],
        "outliers_before": pre["summary"]["outlier_count"],
        "outliers_after":  post.get("summary", {}).get("outlier_count", -1),
    }
    return _safe_json(response)
```

- [ ] **Step 4: Run all coherence handler tests**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_album_coherence_handlers.py -v
```

Expected: all 7 tests PASS (3 check + 4 correct).

- [ ] **Step 5: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py \
        tests/unit/mastering/test_album_coherence_handlers.py
git commit -m "$(cat <<'EOF'
feat: add album_coherence_correct handler (#290 phase 3b)

Re-masters LUFS-outlier tracks from polished/ into mastered/ using
the anchor's measured LUFS as the per-track target. Staging pattern
mirrors master_album:
- .coherence_staging/ receives master_track output
- atomic replace into mastered/ on full success
- staging cleaned up on any failure (no partial writes)

Pre-flight validates:
- polished/ and mastered/ both exist
- every track in mastered/ has a matching file in polished/
- anchor is selectable (otherwise no correction reference)
- genre is set (tolerances + preset base require it)

Scope limits (MVP — documented in docstring):
- Corrects LUFS outliers only
- Non-LUFS outliers reported but not auto-corrected
- Single-pass (no iteration budget)

dry_run=True returns the plan without writing anything — useful for
CI preview and for the release-director skill to preview changes
before committing.

4 new integration tests covering dry-run, missing-polished,
polished/mastered file-set mismatch, and end-to-end correction
convergence (amplitude-varied sine outlier pulled within 1 dB of
anchor).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: MCP registration + re-exports

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py`
- Modify: `servers/bitwize-music-server/handlers/processing/__init__.py`
- Modify: `servers/bitwize-music-server/server.py`

- [ ] **Step 1: Register handlers with MCP**

In `servers/bitwize-music-server/handlers/processing/audio.py`, add to the `register(mcp)` block:

```python
    mcp.tool()(measure_album_signature)
    mcp.tool()(album_coherence_check)
    mcp.tool()(album_coherence_correct)
```

- [ ] **Step 2: Re-export from package `__init__`**

In `servers/bitwize-music-server/handlers/processing/__init__.py`, add alphabetically:

```python
from handlers.processing.audio import (  # noqa: F401
    album_coherence_check,
    album_coherence_correct,
    analyze_audio,
    fix_dynamic_track,
    master_album,
    master_audio,
    master_with_reference,
    measure_album_signature,
    mono_fold_check,
    prune_archival,
    qc_audio,
    render_codec_preview,
)
```

- [ ] **Step 3: Re-export from `server.py`**

In `servers/bitwize-music-server/server.py`'s `from handlers.processing import (...)` block, add alphabetically:

```python
from handlers.processing import (  # noqa: F401
    album_coherence_check,
    album_coherence_correct,
    analyze_audio,
    analyze_mix_issues,
    ...
    master_with_reference,
    measure_album_signature,
    mono_fold_check,
    ...
)
```

- [ ] **Step 4: Run the re-export integrity test**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/state/test_server.py::TestReExportCompleteness -v
```

Expected: PASS.

- [ ] **Step 5: Run the full plugin test suite**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/ --tb=short 2>&1 | tail -10
```

Expected: all green (phase 3a counts + phase 3b additions).

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py \
        servers/bitwize-music-server/handlers/processing/__init__.py \
        servers/bitwize-music-server/server.py
git commit -m "$(cat <<'EOF'
chore: register album_coherence_{check,correct} with MCP server (#290 phase 3b)

Adds the two new handlers to:
- handlers.processing.audio.register() (MCP tool registration)
- handlers.processing.__init__ (package re-export)
- server.py (top-level re-export)

Required for the integrity test TestReExportCompleteness to pass and
for the tools to be callable from the Claude Code client.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: CHANGELOG entry + end-to-end verification + PR

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add CHANGELOG entry**

In `CHANGELOG.md`, under the `## [Unreleased]` section's `### Added` block, add **above** the phase 3a entry:

```markdown
- **Album coherence check + correct (issue #290 phase 3b)** — Two new MCP tools. `album_coherence_check` measures the mastered album, selects an anchor, and classifies every other track against per-genre tolerance bands: LUFS (±0.5 LU), STL-95 (`coherence_stl_95_lu`, default ±0.5 LU), LRA floor (`coherence_lra_floor_lu`, default 1.0 LU minimum), low-RMS (`coherence_low_rms_db`, default ±2.0 dB), vocal-RMS (`coherence_vocal_rms_db`, default ±2.0 dB). Read-only — returns per-track violation lists + a summary with outlier counts broken down by metric. `album_coherence_correct` takes the same check output and re-masters LUFS-outlier tracks from `polished/` into `mastered/` (atomic staging pattern, mirrors `master_album`) with the per-track `target_lufs` overridden to the anchor's **measured** LUFS — chasing real output rather than an idealized preset target guarantees convergence. Supports `dry_run=True` for CI preview. MVP scope: LUFS correction only; STL-95 / LRA / RMS outliers are reported but not auto-corrected (compression-ratio correction comes in a later phase). Four new tolerance fields added to the `defaults:` block in `genre-presets.yaml`.
```

- [ ] **Step 2: Run full plugin test suite one last time**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/ --tb=short 2>&1 | tail -5
```

Expected: all pass.

- [ ] **Step 3: Push the branch and open the PR**

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'EOF'
docs: CHANGELOG entry for album coherence check + correct (#290 phase 3b)

Documents the two new MCP tools, the four new coherence_* preset
fields, and the MVP scope limit (LUFS-only correction).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"

git push -u origin feat/290-phase-3b-album-coherence

gh pr create --base develop \
  --title "feat: album coherence check + correct (#290 phase 3b)" \
  --body "$(cat <<'EOF'
## Summary

- Adds `tools/mastering/coherence.py` — pure-Python tolerance classifier (`classify_outliers`) + correction-plan builder (`build_correction_plan`). No I/O, no MCP coupling.
- Adds four new tolerance fields to the `defaults:` block in `tools/mastering/genre-presets.yaml` (`coherence_stl_95_lu`, `coherence_lra_floor_lu`, `coherence_low_rms_db`, `coherence_vocal_rms_db`).
- Adds **`album_coherence_check`** MCP handler — read-only per-track classification against the anchor + per-genre tolerance bands. Returns violations, summary counts, and a metric-level outlier breakdown.
- Adds **`album_coherence_correct`** MCP handler — re-masters LUFS outliers from `polished/` into `mastered/` using the anchor's measured LUFS as the per-track target. Atomic staging pattern (same approach as `master_album`). Supports `dry_run=True`.
- MVP scope: **LUFS-only correction**. STL-95 / LRA / RMS outliers are reported but not auto-corrected. Compression-ratio / EQ correction deferred to a later phase.

Depends on phase 3a (`measure_album_signature` / `build_signature` / `compute_anchor_deltas`) landing first — see PR #307.

Part of #290.

## Test plan

- [x] `pytest tests/unit/mastering/test_coherence_presets.py` — four new preset fields present in merged pop preset.
- [x] `pytest tests/unit/mastering/test_coherence.py` — 18 unit tests: `load_tolerances` merging, `classify_outliers` for every metric + missing-data + anchor path, `build_correction_plan` LUFS-only + skipped-anchor paths.
- [x] `pytest tests/unit/mastering/test_album_coherence_handlers.py` — 7 integration tests: check outlier detection, check errors-without-genre, check falls-back-to-defaults, correct dry-run doesn't write, correct errors when polished missing, correct errors on file-set mismatch, correct converges outlier within 1 dB of anchor.
- [x] `pytest tests/` — no regressions.
- [x] `tests/plugin/` integrity — re-exports + MCP registration complete.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR opens against `develop`. Return the URL.

---

## Self-Review

**Spec coverage (against issue #290 checklist):**

- ✅ `album_coherence_check` MCP tool — Task 5.
- ✅ `album_coherence_correct` MCP tool — Task 6.
- ✅ Coherence tolerance preset fields (`coherence_stl_95_lu`, `coherence_lra_floor_lu`, `coherence_low_rms_db`, `coherence_vocal_rms_db`) — Task 1.
- ⬜ Coherence correction iteration budget / convergence loop — **intentionally deferred** (MVP is single-pass). Documented in the plan header, handler docstring, and CHANGELOG.
- ⬜ Album-ceiling guard — separate checklist item.
- ⬜ `tests/fixtures/albums/coherence/` — tests use tmp_path + synthetic sine WAVs instead of a persistent fixture album. Persistent fixtures can land in a future phase if the coherence test suite grows large enough to justify the setup.
- ⬜ `ALBUM_SIGNATURE.yaml` persistence — phase 3c.

**Placeholder scan:** No TBDs, no "add appropriate error handling", no "similar to Task N". Every step has the exact code / command / expected output.

**Type consistency:**
- `classify_outliers(deltas, analysis_results, tolerances, anchor_index_1based)` — same arg names used consistently in Task 3 tests and Task 5 handler. ✅
- `build_correction_plan(classifications, analysis_results, anchor_index_1based)` — same arg names in Task 4 tests and Task 6 handler. ✅
- `load_tolerances(preset)` — consumed by both check and correct handlers. ✅
- Violation dict shape: `{"metric", "delta" | "value", "tolerance" | "floor", "severity", "correctable"}` — identical between `_delta_check`, `_floor_check`, and all test expectations. ✅
- `correction` dict shape (`{filename, original_lufs, applied_target_lufs, result_lufs, status, delta_from_anchor, within_tolerance}`) — matches the Task 6 integration test assertion on `correction["delta_from_anchor"]`. ✅

**Execution order sanity:**
- Task 1 → 2: Task 1's tolerance fields are read by Task 2's `load_tolerances` via `master_tracks.load_genre_presets()`. Order matters — Task 2 tests use `DEFAULTS` directly so they don't technically depend on Task 1's YAML, but any integration test that goes through `build_effective_preset` would.
- Task 4 → 5: Task 5's handler calls `classify_outliers` (from Task 3) but does NOT yet call `build_correction_plan` (Task 4) — the check handler only reports, doesn't plan. So Task 5 could theoretically run before Task 4 if needed. Still, tasks are ordered as written because the Task 4 plan builder is the natural bridge from classifier to correct-handler.
- Task 6 imports `build_correction_plan` — so Task 4 must land first.

---

## Execution notes

- Task 5 and Task 6 both create integration tests that write 60-second sine WAVs to tmp_path. The correct end-to-end test actually runs `master_track` on one file, which takes 3-5 seconds per track on the reference machine. Full test file runs in ~30 seconds — acceptable for CI.
- The correct handler's inner `loop.run_in_executor(None, lambda ...)` pattern has a subtle default-argument trap: the `lambda sp=src, op=staged, mp=modified_preset: master_track(sp, op, preset=mp)` binds current values so the executor sees the right file per iteration. Don't replace with a bare closure or the last iteration's values will leak across all calls.
- When `album_coherence_correct` is called recursively (it calls `album_coherence_check` twice — pre and post), the recursion depth is bounded at 2. No infinite-loop risk; just documented in the docstring.
- Synthetic sine waves at `amplitude=0.6` produce roughly `-7 to -8 LUFS`. Mastering to `-14 LUFS` requires pulling ~6-7 dB — well within the limiter's comfort zone. Don't test amplitudes above 0.8 or the staged master may clip pre-limiter and produce misleading results.
- The `album_coherence_correct` integration test asserts `abs(delta_from_anchor) < 1.0` rather than `< 0.5`. Synthetic sines are slightly less predictable than real music because they lack frequency diversity (which affects the limiter's gain-reduction stability) — 1 dB is a defensible loose-but-not-vacuous assertion for this test shape. On real music the assertion could be tightened to 0.5 once a persistent fixture album ships.
