# Phase 3a — `measure_album_signature` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a new `measure_album_signature` MCP tool that reports per-track signature metrics (LUFS, STL-95, LRA, low-RMS, vocal-RMS, spectral band energy, peak) plus album-level aggregates (median, p95, min, max, range) for a directory of WAV files. Used for (a) tuning genre tolerance presets from reference albums and (b) feeding the coherence check/correct tools in phase 3b.

**Architecture:** Additive. A new pure-Python module (`tools/mastering/album_signature.py`) owns aggregation math and anchor-delta computation — no I/O, no MCP coupling. A new async handler (`measure_album_signature`) in `handlers/processing/audio.py` orchestrates: resolve audio dir → glob WAVs → `analyze_track()` each file → `build_signature()` → optional `select_anchor()` + `compute_anchor_deltas()` → `_safe_json`. Registered alongside the existing `analyze_audio` / `prune_archival` / `master_album` tools. **No changes to `genre-presets.yaml`** — coherence tolerance fields land in phase 3b when they're actually consumed.

**Tech Stack:** Python 3.11, `numpy` (already imported in mastering code), `pytest` + `tmp_path` fixtures, existing `tests/fixtures/audio/` WAV generators. No new deps.

---

## File Structure

**Create:**
- `tools/mastering/album_signature.py` — pure-Python aggregation + delta math. Two public functions: `build_signature`, `compute_anchor_deltas`. No MCP coupling, no filesystem access.
- `tests/unit/mastering/test_album_signature.py` — unit tests for `build_signature` (aggregates, None handling, empty input) and `compute_anchor_deltas` (deltas, out-of-range index, None metric handling).
- `tests/unit/mastering/test_measure_album_signature_handler.py` — integration tests for the MCP handler using `tmp_path` + `tests/fixtures/audio/` WAV generators, asserting top-level JSON shape and the three code paths (no-anchor, genre-selected anchor, explicit-anchor-override).

**Modify:**
- `servers/bitwize-music-server/handlers/processing/audio.py`:
  - Add `measure_album_signature` async handler (~100 lines) after `prune_archival` (currently at line 1670) and before `register()` (currently at line 1730).
  - Add `mcp.tool()(measure_album_signature)` line to `register()` (currently at line 1730-1741).

**Not modified:**
- `tools/mastering/anchor_selector.py` — consumed as-is. `select_anchor()` already returns the per-track scores dict we need.
- `tools/mastering/analyze_tracks.py` — consumed as-is. `analyze_track()` already returns the signature fields from phase 1b.
- `tools/mastering/config.py` — `build_effective_preset()` already handles genre→preset resolution and is called here for anchor-preset setup.
- `tools/mastering/genre-presets.yaml` — **no changes**. Coherence tolerance fields (`coherence_stl_95_lu` etc.) belong to phase 3b.
- `tools/mastering/master_tracks.py` — no mastering is performed by this tool.
- `tools/state/parsers.py` — `anchor_track` frontmatter already surfaces through phase 2.
- `servers/bitwize-music-server/server.py` — registration flows via `handlers.processing.register` → `audio.register`, already wired.

**Module responsibilities:**
- `album_signature.py` — pure math. Aggregates + deltas. No I/O, no logging, no MCP awareness.
- `measure_album_signature` handler — glue: path resolution, WAV iteration, `analyze_track` fan-out, preset resolution for anchor selection, JSON assembly. Handlers own I/O and error JSON shape.
- Handler tests own end-to-end shape; `album_signature` tests own the math.

---

## Design Details (read before starting any task)

### Signature keys

Four "signature" metrics (from phase 1b's `analyze_track` output — see `tools/mastering/analyze_tracks.py:252-269`) plus two supporting:

| Key | Source | Type | Missing sentinel |
|-----|--------|------|------------------|
| `lufs` | `analyze_track` | float (always present) | — |
| `peak_db` | `analyze_track` | float (always present) | — |
| `stl_95` | `analyze_track` | float \| None | `None` when <20 ST-LUFS windows |
| `short_term_range` | `analyze_track` | float (always finite) | — (analyzer returns 0.0 when undefined) |
| `low_rms` | `analyze_track` | float \| None | `None` when stl_95 missing (share the STL-95 window pool) |
| `vocal_rms` | `analyze_track` | float \| None | `None` when both stem + band fallback fail |

`band_energy` is surfaced separately (per-track only, not aggregated into median/p95). It's a 7-key dict — aggregating it meaningfully requires more than median-per-band.

### `build_signature` return shape

```python
{
    "tracks": [
        {
            "index": 1,                        # 1-based
            "filename": "01-opening.wav",
            "duration": 214.7,
            "sample_rate": 96000,
            "lufs": -14.1,
            "peak_db": -1.04,
            "stl_95": -10.5,
            "short_term_range": 6.5,
            "low_rms": -18.3,
            "vocal_rms": -16.1,
            "band_energy": {
                "sub_bass": 7.8, "bass": 18.2, "low_mid": 19.5,
                "mid": 24.9, "high_mid": 14.3, "high": 10.1, "air": 5.2,
            },
            "signature_meta": {
                "stl_window_count": 71,
                "stl_top_5pct_count": 4,
                "vocal_rms_source": "band_fallback",
            },
        },
        ...
    ],
    "album": {
        "track_count": 10,
        "median": {
            "lufs": -14.0, "peak_db": -1.02, "stl_95": -10.6,
            "short_term_range": 6.4, "low_rms": -18.1, "vocal_rms": -16.0,
        },
        "p95": { ... same keys ... },
        "min": { ... same keys ... },
        "max": { ... same keys ... },
        "range": { ... max - min, same keys ... },
        "eligible_count": {
            "stl_95": 10, "low_rms": 10, "vocal_rms": 8,
        },
    },
}
```

**Aggregation rules:**
- Only finite, non-None values contribute to per-metric aggregates.
- If zero tracks have a finite value for a metric, that metric's aggregate entry is `None` (for all of median/p95/min/max/range).
- `eligible_count` surfaces how many tracks contributed to each aggregate (for downstream sanity-checking — e.g., "vocal_rms median is across only 8/10 tracks").
- `p95` uses `numpy.percentile(values, 95)` with default linear interpolation.
- `track_count` counts all tracks in the input, regardless of eligibility.

### `compute_anchor_deltas` return shape

```python
[
    {
        "index": 1,
        "filename": "01-opening.wav",
        "is_anchor": False,
        "delta_lufs": 0.2,              # track - anchor
        "delta_peak_db": 0.1,
        "delta_stl_95": 0.5,
        "delta_short_term_range": -1.0,
        "delta_low_rms": 1.2,
        "delta_vocal_rms": 0.3,
    },
    {
        "index": 3,
        "filename": "03-anchor.wav",
        "is_anchor": True,
        "delta_lufs": 0.0,
        ...  # anchor's own deltas are 0.0 by definition
    },
    ...
]
```

**Delta rules:**
- Convention: `delta_X = track.X - anchor.X`. Positive means the track has a higher value than the anchor.
- If either the track or the anchor has `None` for a metric, the delta for that metric is `None`.
- The anchor's own row has `is_anchor: True` and zeros for every delta.
- Index is 1-based (same as `analyze_track` / anchor-selector convention).
- `anchor_index_1based` of `0`, negative, or `> len(analysis_results)` raises `ValueError` — callers are expected to validate first.

### Handler contract — `measure_album_signature`

**Signature:**
```python
async def measure_album_signature(
    album_slug: str,
    subfolder: str = "mastered",
    genre: str = "",
    anchor_track: int | None = None,
) -> str:
```

**Why `subfolder="mastered"` as default:** The primary use case for this tool is measuring a **released** album so its signature can tune genre tolerances. Released albums have mastered WAVs in `{audio_root}/artists/.../albums/.../{album}/mastered/`. The caller can override to `""` for the base audio dir, `"polished"` for post-mix-engineer output, or any other confined subfolder.

**Precedence for anchor selection** (handler logic, not `select_anchor`'s):
1. Explicit `anchor_track` arg — used directly as `override_index` for `select_anchor`.
2. State-cache `anchor_track` frontmatter (loaded via the same `_shared.cache.get_state()` path as `master_album`, see `audio.py:754-759`) — fallback override.
3. Genre-driven composite scoring — invoked only when both (1) and (2) are empty.
4. No anchor — when neither `genre` nor an override is present, the anchor section is omitted from the response.

**JSON response shape:**

```python
{
    "album_slug": "my-album",
    "source_dir": "/abs/path/to/mastered",
    "settings": {
        "genre": "pop" | None,            # None when no genre resolved
        "subfolder": "mastered",
    },
    "tracks":  [ ... per-track signature dicts, see build_signature ... ],
    "album":   { ... aggregates, see build_signature ... },
    "anchor":  {                            # omitted entirely when no anchor computed
        "selected_index": 3,
        "method": "composite" | "override" | "tie_breaker" | "no_eligible_tracks",
        "override_index": None,
        "override_reason": None,
        "scores": [ ... same shape as select_anchor output ... ],
        "deltas": [ ... compute_anchor_deltas output ... ],
    },
}
```

**Error paths** (returned as JSON with `error:` key, matching existing handler convention):
- Missing mastering deps (numpy/soundfile) → `_helpers._check_mastering_deps()` message.
- Unknown album slug → `_resolve_audio_dir` error JSON.
- Subfolder escapes album dir → `"Invalid subfolder: path must not escape the album directory"`.
- Subfolder missing → `"Subfolder not found: <path>"`.
- No WAV files → `"No WAV files found in <dir>"`.
- Unknown genre (when `genre` provided) → `build_effective_preset`'s error dict surfaced directly (reason + available_genres).
- Explicit `anchor_track` out of range → treated as no override (returned via `anchor.override_reason` like the existing anchor-selector path). Not an error.

**Non-goals:**
- No writing to disk. This is a read-only measurement tool. Persistence comes in phase 3c (`ALBUM_SIGNATURE.yaml`).
- No re-mastering. That's phase 3b's `album_coherence_correct`.
- No tolerance classification ("within spec" / "outside spec"). Phase 3b ships tolerances.
- No CLI — the MCP tool is the only surface.

### Why split `build_signature` from the handler

- **Testability:** Aggregation math is pure. Unit tests consume synthetic dicts, never touch the filesystem.
- **Reuse:** Phase 3b's `album_coherence_check` will consume `build_signature`'s output directly. Keeping it importable without the MCP server means the coherence check module can build on it without importing handlers.
- **Single responsibility:** The handler owns I/O + JSON; the pure module owns math. Phase 2's `anchor_selector.py` established this convention — we follow it.

---

## Task 1: Create `album_signature.py` skeleton with `build_signature` (happy path)

**Files:**
- Create: `tools/mastering/album_signature.py`
- Create: `tests/unit/mastering/test_album_signature.py`

- [ ] **Step 1: Write the failing happy-path test**

Create `tests/unit/mastering/test_album_signature.py`:

```python
#!/usr/bin/env python3
"""Unit tests for album signature aggregation (#290 phase 3a)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.album_signature import (
    build_signature,
    compute_anchor_deltas,
)


def _analysis(**overrides) -> dict:
    """Minimal analyze_track()-shaped dict for tests."""
    base = {
        "filename": "01.wav",
        "duration": 180.0,
        "sample_rate": 96000,
        "lufs": -14.0,
        "peak_db": -1.0,
        "rms_db": -20.0,
        "dynamic_range": 8.0,
        "band_energy": {
            "sub_bass": 8.0, "bass": 18.0, "low_mid": 20.0,
            "mid": 25.0, "high_mid": 14.0, "high": 10.0, "air": 5.0,
        },
        "tinniness_ratio": 0.3,
        "max_short_term_lufs": -10.0,
        "max_momentary_lufs": -8.0,
        "short_term_range": 6.5,
        "stl_95": -10.5,
        "low_rms": -18.0,
        "vocal_rms": -16.0,
        "signature_meta": {
            "stl_window_count": 60,
            "stl_top_5pct_count": 3,
            "vocal_rms_source": "band_fallback",
        },
    }
    base.update(overrides)
    return base


class TestBuildSignatureHappyPath:
    def test_three_track_album_returns_tracks_and_album_blocks(self):
        results = [
            _analysis(filename="01.wav", lufs=-14.0, stl_95=-10.0, peak_db=-1.0),
            _analysis(filename="02.wav", lufs=-13.8, stl_95=-10.2, peak_db=-1.1),
            _analysis(filename="03.wav", lufs=-14.2, stl_95=-10.4, peak_db=-0.9),
        ]
        sig = build_signature(results)

        assert sig["album"]["track_count"] == 3
        assert len(sig["tracks"]) == 3
        assert sig["tracks"][0]["index"] == 1
        assert sig["tracks"][2]["index"] == 3
        assert sig["tracks"][0]["filename"] == "01.wav"

        # Median of {-14.0, -13.8, -14.2} is -14.0
        assert sig["album"]["median"]["lufs"] == pytest.approx(-14.0)
        # Median of {-10.0, -10.2, -10.4} is -10.2
        assert sig["album"]["median"]["stl_95"] == pytest.approx(-10.2)
        # Range: max(-13.8) - min(-14.2) = 0.4
        assert sig["album"]["range"]["lufs"] == pytest.approx(0.4)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_album_signature.py::TestBuildSignatureHappyPath -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tools.mastering.album_signature'`.

- [ ] **Step 3: Create `album_signature.py` with minimal `build_signature`**

Create `tools/mastering/album_signature.py`:

```python
"""Album signature aggregation and anchor-delta computation (#290 phase 3a).

Pure-Python module — no I/O, no MCP coupling. The
``measure_album_signature`` handler in
``servers/bitwize-music-server/handlers/processing/audio.py`` calls
``build_signature`` on a list of ``analyze_track`` results, then
(optionally) ``compute_anchor_deltas`` once an anchor index is known.

Phase 3b (``album_coherence_check`` / ``album_coherence_correct``) will
consume the same signature dict, so this module is intentionally free
of handler-layer concerns.
"""

from __future__ import annotations

from typing import Any

import numpy as np

# Metrics that get aggregated across tracks (median/p95/min/max/range).
# ``band_energy`` is surfaced per-track only — aggregating 7-band vectors
# as independent medians loses the correlation structure that matters.
AGGREGATE_KEYS = (
    "lufs",
    "peak_db",
    "stl_95",
    "short_term_range",
    "low_rms",
    "vocal_rms",
)

# Subset that is required for a track to be considered "signature-eligible"
# (same four keys the anchor selector uses — see
# ``tools/mastering/anchor_selector.py::SIGNATURE_KEYS``).
ELIGIBILITY_KEYS = ("stl_95", "short_term_range", "low_rms", "vocal_rms")


def _finite_values(tracks: list[dict[str, Any]], key: str) -> list[float]:
    """Collect finite, non-None values for ``key`` across all tracks."""
    out: list[float] = []
    for t in tracks:
        v = t.get(key)
        if v is None:
            continue
        try:
            vf = float(v)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(vf):
            continue
        out.append(vf)
    return out


def _aggregate(values: list[float]) -> dict[str, float | None]:
    """Return median / p95 / min / max for a list of values.

    Returns a dict of ``None``s when the input is empty — callers can
    propagate "no data" without special-casing missing keys.
    """
    if not values:
        return {"median": None, "p95": None, "min": None, "max": None}
    arr = np.asarray(values, dtype=float)
    return {
        "median": float(np.median(arr)),
        "p95":    float(np.percentile(arr, 95)),
        "min":    float(arr.min()),
        "max":    float(arr.max()),
    }


def build_signature(analysis_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Build per-track + album-level signature summary.

    Args:
        analysis_results: List of ``analyze_track()`` result dicts, in
            track-number order (index 0 == track #1). Dicts may have
            ``None`` values for ``stl_95`` / ``low_rms`` / ``vocal_rms``.

    Returns:
        Dict with ``tracks`` (per-track signature list) and ``album``
        (aggregates). See the phase-3a plan doc for the full shape.
    """
    tracks: list[dict[str, Any]] = []
    for i, t in enumerate(analysis_results):
        tracks.append({
            "index":              i + 1,
            "filename":           t.get("filename"),
            "duration":           t.get("duration"),
            "sample_rate":        t.get("sample_rate"),
            "lufs":               t.get("lufs"),
            "peak_db":            t.get("peak_db"),
            "stl_95":             t.get("stl_95"),
            "short_term_range":   t.get("short_term_range"),
            "low_rms":            t.get("low_rms"),
            "vocal_rms":          t.get("vocal_rms"),
            "band_energy":        t.get("band_energy"),
            "signature_meta":     t.get("signature_meta"),
        })

    album: dict[str, Any] = {
        "track_count":     len(analysis_results),
        "median":          {},
        "p95":             {},
        "min":             {},
        "max":             {},
        "range":           {},
        "eligible_count":  {},
    }
    for key in AGGREGATE_KEYS:
        vals = _finite_values(analysis_results, key)
        agg = _aggregate(vals)
        album["median"][key] = agg["median"]
        album["p95"][key]    = agg["p95"]
        album["min"][key]    = agg["min"]
        album["max"][key]    = agg["max"]
        if agg["min"] is None or agg["max"] is None:
            album["range"][key] = None
        else:
            album["range"][key] = agg["max"] - agg["min"]
    for key in ELIGIBILITY_KEYS:
        album["eligible_count"][key] = len(_finite_values(analysis_results, key))

    return {"tracks": tracks, "album": album}


def compute_anchor_deltas(
    analysis_results: list[dict[str, Any]],
    anchor_index_1based: int,
) -> list[dict[str, Any]]:
    """Compute per-track deltas from the anchor for every aggregate metric.

    Args:
        analysis_results: Same list of ``analyze_track`` dicts passed to
            ``build_signature``.
        anchor_index_1based: 1-based track number of the anchor. Must be
            in ``[1, len(analysis_results)]``.

    Returns:
        List of per-track delta dicts (length == len(analysis_results)).
        Anchor's own row has ``is_anchor: True`` and zeros for every delta.

    Raises:
        ValueError: if ``anchor_index_1based`` is out of range or the
            list is empty.
    """
    if not analysis_results:
        raise ValueError("analysis_results is empty")
    if not (1 <= anchor_index_1based <= len(analysis_results)):
        raise ValueError(
            f"anchor_index_1based={anchor_index_1based} out of range "
            f"[1, {len(analysis_results)}]"
        )

    anchor = analysis_results[anchor_index_1based - 1]
    out: list[dict[str, Any]] = []
    for i, t in enumerate(analysis_results):
        is_anchor = (i + 1) == anchor_index_1based
        row: dict[str, Any] = {
            "index":     i + 1,
            "filename":  t.get("filename"),
            "is_anchor": is_anchor,
        }
        for key in AGGREGATE_KEYS:
            a_val = anchor.get(key)
            t_val = t.get(key)
            if a_val is None or t_val is None:
                row[f"delta_{key}"] = None
                continue
            try:
                row[f"delta_{key}"] = float(t_val) - float(a_val)
            except (TypeError, ValueError):
                row[f"delta_{key}"] = None
        out.append(row)
    return out
```

- [ ] **Step 4: Run the happy-path test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_album_signature.py::TestBuildSignatureHappyPath -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/mastering/album_signature.py tests/unit/mastering/test_album_signature.py
git commit -m "$(cat <<'EOF'
feat: add build_signature pure-Python aggregator (#290 phase 3a)

Introduces tools/mastering/album_signature.py with build_signature(),
which aggregates a list of analyze_track results into per-track +
album-level signature summaries (median/p95/min/max/range). Pure
Python — no I/O, no MCP coupling. Happy-path unit test covers a
three-track album.

compute_anchor_deltas() is also in the module but not yet covered;
subsequent commits add tests for None handling, aggregate edge cases,
and delta computation.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Cover `build_signature` edge cases (missing metrics, empty album)

**Files:**
- Modify: `tests/unit/mastering/test_album_signature.py`

- [ ] **Step 1: Write the failing tests for missing-metric handling**

Append to `tests/unit/mastering/test_album_signature.py`:

```python
class TestBuildSignatureMissingMetrics:
    def test_none_stl_95_excluded_from_median(self):
        results = [
            _analysis(filename="01.wav", stl_95=-10.0),
            _analysis(filename="02.wav", stl_95=None),
            _analysis(filename="03.wav", stl_95=-10.4),
        ]
        sig = build_signature(results)

        # Median across {-10.0, -10.4} (two finite values) == -10.2
        assert sig["album"]["median"]["stl_95"] == pytest.approx(-10.2)
        assert sig["album"]["eligible_count"]["stl_95"] == 2

    def test_all_none_metric_returns_none_aggregate(self):
        results = [
            _analysis(vocal_rms=None),
            _analysis(vocal_rms=None),
        ]
        sig = build_signature(results)

        assert sig["album"]["median"]["vocal_rms"] is None
        assert sig["album"]["p95"]["vocal_rms"] is None
        assert sig["album"]["min"]["vocal_rms"] is None
        assert sig["album"]["max"]["vocal_rms"] is None
        assert sig["album"]["range"]["vocal_rms"] is None
        assert sig["album"]["eligible_count"]["vocal_rms"] == 0

    def test_nonfinite_lufs_excluded(self):
        results = [
            _analysis(lufs=-14.0),
            _analysis(lufs=float("-inf")),
            _analysis(lufs=float("nan")),
            _analysis(lufs=-13.8),
        ]
        sig = build_signature(results)

        # Only -14.0 and -13.8 contribute
        assert sig["album"]["median"]["lufs"] == pytest.approx(-13.9)
        assert sig["album"]["range"]["lufs"] == pytest.approx(0.2)


class TestBuildSignatureBoundaryCases:
    def test_empty_album_returns_empty_tracks_and_none_aggregates(self):
        sig = build_signature([])

        assert sig["tracks"] == []
        assert sig["album"]["track_count"] == 0
        for key in ("lufs", "stl_95", "low_rms", "vocal_rms"):
            assert sig["album"]["median"][key] is None
            assert sig["album"]["range"][key] is None

    def test_single_track_range_is_zero(self):
        results = [_analysis(lufs=-14.0, stl_95=-10.0)]
        sig = build_signature(results)

        assert sig["album"]["median"]["lufs"] == pytest.approx(-14.0)
        assert sig["album"]["range"]["lufs"] == pytest.approx(0.0)

    def test_p95_with_odd_count_uses_interpolation(self):
        results = [_analysis(lufs=v) for v in (-15.0, -14.5, -14.0, -13.5, -13.0)]
        sig = build_signature(results)

        # numpy.percentile(..., 95) with linear interpolation on this
        # 5-value set returns -13.1 (between -13.5 and -13.0).
        assert sig["album"]["p95"]["lufs"] == pytest.approx(-13.1, abs=1e-6)
```

- [ ] **Step 2: Run the new tests**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_album_signature.py -v
```

Expected: all PASS — the Task 1 implementation already handles these paths (`_finite_values` filters `None`/`inf`/`NaN`; `_aggregate` returns all-None on empty input).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/mastering/test_album_signature.py
git commit -m "$(cat <<'EOF'
test: cover build_signature edge cases (#290 phase 3a)

Adds coverage for:
- None stl_95 values excluded from medians
- all-None metric returns None across aggregates
- non-finite lufs (inf, nan) excluded
- empty album → empty tracks + None aggregates
- single-track album → zero range
- 5-value p95 uses numpy's linear interpolation

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Cover `compute_anchor_deltas`

**Files:**
- Modify: `tests/unit/mastering/test_album_signature.py`

- [ ] **Step 1: Write the failing tests for anchor deltas**

Append to `tests/unit/mastering/test_album_signature.py`:

```python
class TestComputeAnchorDeltas:
    def test_deltas_are_track_minus_anchor(self):
        results = [
            _analysis(filename="01.wav", lufs=-13.0, stl_95=-10.0),
            _analysis(filename="02.wav", lufs=-14.0, stl_95=-10.5),  # anchor
            _analysis(filename="03.wav", lufs=-15.0, stl_95=-11.5),
        ]
        deltas = compute_anchor_deltas(results, anchor_index_1based=2)

        # Track 1 - Anchor: -13.0 - -14.0 = +1.0
        assert deltas[0]["delta_lufs"] == pytest.approx(1.0)
        assert deltas[0]["delta_stl_95"] == pytest.approx(0.5)
        assert deltas[0]["is_anchor"] is False

        # Track 2 (anchor) - itself = 0.0
        assert deltas[1]["delta_lufs"] == pytest.approx(0.0)
        assert deltas[1]["is_anchor"] is True

        # Track 3 - Anchor: -15.0 - -14.0 = -1.0
        assert deltas[2]["delta_lufs"] == pytest.approx(-1.0)
        assert deltas[2]["delta_stl_95"] == pytest.approx(-1.0)
        assert deltas[2]["is_anchor"] is False

    def test_none_in_track_or_anchor_yields_none_delta(self):
        results = [
            _analysis(filename="01.wav", vocal_rms=None),  # track missing
            _analysis(filename="02.wav", vocal_rms=-16.0),  # anchor present
            _analysis(filename="03.wav", vocal_rms=-15.0),
        ]
        deltas = compute_anchor_deltas(results, anchor_index_1based=2)

        assert deltas[0]["delta_vocal_rms"] is None
        assert deltas[1]["delta_vocal_rms"] == pytest.approx(0.0)
        assert deltas[2]["delta_vocal_rms"] == pytest.approx(1.0)

    def test_none_in_anchor_propagates_to_every_row(self):
        results = [
            _analysis(filename="01.wav", low_rms=-18.0),
            _analysis(filename="02.wav", low_rms=None),    # anchor missing
        ]
        deltas = compute_anchor_deltas(results, anchor_index_1based=2)

        assert deltas[0]["delta_low_rms"] is None
        assert deltas[1]["delta_low_rms"] is None
        # Anchor row is still marked, just without a delta value
        assert deltas[1]["is_anchor"] is True

    def test_empty_results_raises(self):
        with pytest.raises(ValueError, match="empty"):
            compute_anchor_deltas([], anchor_index_1based=1)

    def test_out_of_range_anchor_raises(self):
        results = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        with pytest.raises(ValueError, match="out of range"):
            compute_anchor_deltas(results, anchor_index_1based=3)
        with pytest.raises(ValueError, match="out of range"):
            compute_anchor_deltas(results, anchor_index_1based=0)
        with pytest.raises(ValueError, match="out of range"):
            compute_anchor_deltas(results, anchor_index_1based=-1)

    def test_all_aggregate_keys_are_represented(self):
        results = [
            _analysis(filename="01.wav"),
            _analysis(filename="02.wav"),
        ]
        deltas = compute_anchor_deltas(results, anchor_index_1based=1)
        expected_keys = {
            "index", "filename", "is_anchor",
            "delta_lufs", "delta_peak_db", "delta_stl_95",
            "delta_short_term_range", "delta_low_rms", "delta_vocal_rms",
        }
        assert set(deltas[0].keys()) == expected_keys
```

- [ ] **Step 2: Run the new tests**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_album_signature.py::TestComputeAnchorDeltas -v
```

Expected: all PASS — the Task 1 implementation already handles all these paths.

- [ ] **Step 3: Run the full `album_signature` test file as a sanity check**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_album_signature.py -v
```

Expected: all PASS (three test classes, 12+ tests).

- [ ] **Step 4: Commit**

```bash
git add tests/unit/mastering/test_album_signature.py
git commit -m "$(cat <<'EOF'
test: cover compute_anchor_deltas (#290 phase 3a)

Tests the pure-Python delta computation:
- deltas follow track - anchor convention
- None in track or anchor yields None delta
- None anchor propagates to every row's metric
- empty list + out-of-range index raise ValueError
- every AGGREGATE_KEYS metric has a delta_ column

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add the `measure_album_signature` handler (no-anchor happy path)

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py`
- Create: `tests/unit/mastering/test_measure_album_signature_handler.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/unit/mastering/test_measure_album_signature_handler.py`:

```python
"""Integration tests for the measure_album_signature MCP handler (#290 phase 3a)."""

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
    """Write a simple stereo sine-wave WAV long enough for stl_95 to be defined."""
    import soundfile as sf

    n = int(duration * sample_rate)
    t = np.arange(n) / sample_rate
    mono = amplitude * np.sin(2 * np.pi * freq * t).astype(np.float32)
    stereo = np.column_stack([mono, mono])
    sf.write(str(path), stereo, sample_rate, subtype="PCM_24")
    return path


def _setup_album(tmp_path: Path, track_count: int = 3) -> Path:
    mastered = tmp_path / "mastered"
    mastered.mkdir()
    for i in range(1, track_count + 1):
        # Vary frequency across tracks so analyzer produces non-identical
        # signatures even on synthetic sines.
        _write_sine_wav(mastered / f"{i:02d}-track.wav", freq=200.0 + i * 30.0)
    return tmp_path


def test_measure_album_signature_no_anchor_returns_tracks_and_album(tmp_path: Path) -> None:
    _setup_album(tmp_path, track_count=3)

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(album_slug="test-album", subfolder="mastered")
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert result["album_slug"] == "test-album"
    assert result["settings"]["subfolder"] == "mastered"
    assert result["settings"]["genre"] is None
    assert "anchor" not in result     # omitted when no genre + no override

    assert len(result["tracks"]) == 3
    assert result["album"]["track_count"] == 3
    assert result["album"]["median"]["lufs"] is not None
    assert result["tracks"][0]["index"] == 1
    assert result["tracks"][0]["filename"] == "01-track.wav"


def test_measure_album_signature_missing_subfolder_returns_error(tmp_path: Path) -> None:
    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(
                album_slug="test-album", subfolder="nonexistent",
            )
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "not found" in result["error"].lower()


def test_measure_album_signature_subfolder_escape_blocked(tmp_path: Path) -> None:
    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(
                album_slug="test-album", subfolder="../../../etc",
            )
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "escape" in result["error"].lower() or "invalid" in result["error"].lower()


def test_measure_album_signature_no_wavs_returns_error(tmp_path: Path) -> None:
    (tmp_path / "mastered").mkdir()
    # No WAV files.

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(album_slug="test-album", subfolder="mastered")
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "no wav" in result["error"].lower()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_measure_album_signature_handler.py::test_measure_album_signature_no_anchor_returns_tracks_and_album -v
```

Expected: FAIL with `AttributeError: module 'handlers.processing.audio' has no attribute 'measure_album_signature'`.

- [ ] **Step 3: Add the handler to `audio.py`**

Open `servers/bitwize-music-server/handlers/processing/audio.py` and insert the following **before** the `def register(mcp: Any) -> None:` block (currently at line 1730). The function uses only imports already available at the top of the file, plus one local import for the new module.

```python
async def measure_album_signature(
    album_slug: str,
    subfolder: str = "mastered",
    genre: str = "",
    anchor_track: int | None = None,
) -> str:
    """Measure an album's multi-metric signature from its WAV files.

    Runs analyze_track() on every WAV in the album's ``subfolder``
    directory, then aggregates the results into:
      • per-track signature metrics (LUFS, peak, STL-95, short-term
        range, low-RMS, vocal-RMS, spectral band energy);
      • album-level aggregates (median, p95, min, max, range);
      • an optional anchor block (when ``genre`` or ``anchor_track`` is
        given) with the selected-anchor index, the anchor-selector scores,
        and per-track deltas from the anchor.

    The tool is read-only — no files are written. It's intended for
    tuning genre tolerance presets from reference albums and for feeding
    the album_coherence_check / album_coherence_correct tools in phase 3b.

    Args:
        album_slug: Album slug (e.g., "my-album").
        subfolder: Subfolder under the album's audio directory to scan
            for WAVs. Default "mastered". Pass "" to scan the base audio
            dir, or any confined relative path.
        genre: Optional genre preset slug (e.g., "pop"). When set, the
            anchor selector runs with the resolved preset's
            ``genre_ideal_lra_lu`` and ``spectral_reference_energy``.
        anchor_track: Optional explicit 1-based track number to use as
            the anchor. Overrides both ``genre``-based selection and any
            album-README ``anchor_track:`` frontmatter value. Out-of-range
            values fall through to composite scoring (and are surfaced
            via ``anchor.override_reason``).

    Returns:
        JSON string. On success includes ``tracks``, ``album``, and —
        when an anchor was computed — an ``anchor`` block. On failure
        returns ``{"error": str, ...}``.
    """
    dep_err = _helpers._check_mastering_deps()
    if dep_err:
        return _safe_json({"error": dep_err})

    err, audio_dir = _helpers._resolve_audio_dir(album_slug)
    if err:
        return err
    assert audio_dir is not None

    # Resolve source directory (subfolder) with confinement guard.
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
                "suggestion": (
                    f"Pass subfolder='' to scan the base audio dir, or "
                    f"verify {subfolder!r} exists under {audio_dir}."
                ),
            })
    else:
        source_dir = _find_wav_source_dir(audio_dir)

    wav_files = sorted([
        f for f in source_dir.iterdir()
        if f.suffix.lower() == ".wav" and "venv" not in str(f)
    ])
    if not wav_files:
        return _safe_json({
            "error": f"No WAV files found in {source_dir}",
        })

    # Resolve genre preset (only when caller gave a genre — otherwise
    # skip the preset step entirely so unknown-genre doesn't error a
    # signature-only measurement run).
    preset_dict: dict[str, Any] | None = None
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
            return _safe_json({"error": bundle["error"]["reason"], **bundle["error"]})
        preset_dict = bundle["preset_dict"]

    # Determine whether an anchor is requested and which override to use.
    # Precedence: explicit arg > README frontmatter > composite scoring > none.
    override_index: int | None = None
    if isinstance(anchor_track, int) and not isinstance(anchor_track, bool):
        override_index = anchor_track
    else:
        state_albums = (_shared.cache.get_state() or {}).get("albums", {})
        album_state = state_albums.get(_normalize_slug(album_slug), {})
        raw_override = album_state.get("anchor_track")
        if isinstance(raw_override, int) and not isinstance(raw_override, bool):
            override_index = raw_override

    anchor_requested = bool(genre) or override_index is not None

    # Run analyzer on every WAV. Block-executor keeps the event loop responsive.
    from tools.mastering.analyze_tracks import analyze_track
    from tools.mastering.album_signature import (
        build_signature,
        compute_anchor_deltas,
    )

    loop = asyncio.get_running_loop()
    analysis_results: list[dict[str, Any]] = []
    for wav in wav_files:
        result = await loop.run_in_executor(None, analyze_track, str(wav))
        analysis_results.append(result)

    signature = build_signature(analysis_results)
    response: dict[str, Any] = {
        "album_slug": album_slug,
        "source_dir": str(source_dir),
        "settings": {
            "genre": genre.lower() if genre else None,
            "subfolder": subfolder,
        },
        "tracks": signature["tracks"],
        "album":  signature["album"],
    }

    if anchor_requested:
        from tools.mastering.anchor_selector import select_anchor
        anchor_preset = preset_dict or {}
        anchor_result = select_anchor(
            analysis_results,
            anchor_preset,
            override_index=override_index,
        )
        anchor_block: dict[str, Any] = {
            "selected_index":  anchor_result["selected_index"],
            "method":          anchor_result["method"],
            "override_index":  anchor_result["override_index"],
            "override_reason": anchor_result["override_reason"],
            "scores":          anchor_result["scores"],
        }
        selected = anchor_result["selected_index"]
        if isinstance(selected, int) and 1 <= selected <= len(analysis_results):
            anchor_block["deltas"] = compute_anchor_deltas(
                analysis_results, anchor_index_1based=selected,
            )
        else:
            anchor_block["deltas"] = []
        response["anchor"] = anchor_block

    return _safe_json(response)
```

- [ ] **Step 4: Run the integration test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_measure_album_signature_handler.py -v
```

Expected: all four tests PASS (happy path + three error cases).

- [ ] **Step 5: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py \
        tests/unit/mastering/test_measure_album_signature_handler.py
git commit -m "$(cat <<'EOF'
feat: add measure_album_signature handler (#290 phase 3a)

New MCP handler in handlers/processing/audio.py. Resolves the album's
subfolder (default 'mastered/'), runs analyze_track on every WAV,
calls build_signature to produce per-track + album-level aggregates,
and optionally runs the anchor selector + compute_anchor_deltas when
genre or an explicit anchor_track is supplied.

Read-only — no files are written. Used for tuning genre tolerances
from reference albums and for feeding phase 3b coherence tools.

Integration tests cover:
- no-anchor happy path (3 sine-wave tracks)
- missing subfolder → error
- subfolder escape blocked
- empty subfolder → error

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Cover the genre-driven anchor path + explicit-override path

**Files:**
- Modify: `tests/unit/mastering/test_measure_album_signature_handler.py`

- [ ] **Step 1: Write failing tests for the anchor-selection paths**

Append to `tests/unit/mastering/test_measure_album_signature_handler.py`:

```python
def test_measure_album_signature_with_genre_returns_anchor_block(tmp_path: Path) -> None:
    _setup_album(tmp_path, track_count=3)

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(
                album_slug="test-album", subfolder="mastered", genre="pop",
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert result["settings"]["genre"] == "pop"
    assert "anchor" in result
    # Short sine-wave fixtures typically satisfy stl_95 eligibility —
    # but if scoring can't converge (pathological synthetic audio), the
    # selector still returns a structured dict; assert on shape, not
    # specific index.
    anchor = result["anchor"]
    assert "selected_index" in anchor
    assert "method" in anchor
    assert "scores" in anchor
    assert isinstance(anchor["scores"], list)
    assert len(anchor["scores"]) == 3
    if anchor["selected_index"] is not None:
        assert anchor["deltas"]  # non-empty when a selection was made
        # Exactly one delta row should be flagged as the anchor.
        assert sum(1 for r in anchor["deltas"] if r["is_anchor"]) == 1


def test_measure_album_signature_with_explicit_anchor_track(tmp_path: Path) -> None:
    _setup_album(tmp_path, track_count=4)

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(
                album_slug="test-album",
                subfolder="mastered",
                anchor_track=2,
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert "anchor" in result
    anchor = result["anchor"]
    assert anchor["selected_index"] == 2
    assert anchor["method"] == "override"
    assert anchor["override_index"] == 2
    assert len(anchor["deltas"]) == 4
    assert anchor["deltas"][1]["is_anchor"] is True  # track #2 (1-based)


def test_measure_album_signature_unknown_genre_returns_error(tmp_path: Path) -> None:
    _setup_album(tmp_path, track_count=2)

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(
                album_slug="test-album", subfolder="mastered",
                genre="not-a-real-genre",
            )
        )

    result = json.loads(result_json)
    assert "error" in result
    assert "unknown genre" in result["error"].lower()
    # build_effective_preset surfaces the catalogue for fix-forward guidance.
    assert "available_genres" in result


def test_measure_album_signature_out_of_range_override_falls_through(tmp_path: Path) -> None:
    _setup_album(tmp_path, track_count=3)

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(
            audio_mod.measure_album_signature(
                album_slug="test-album", subfolder="mastered",
                anchor_track=99,  # out of range
            )
        )

    result = json.loads(result_json)
    assert "error" not in result
    assert "anchor" in result
    anchor = result["anchor"]
    # Override is rejected but still surfaces in the block for diagnostics.
    assert anchor["override_index"] == 99
    assert anchor["override_reason"] is not None
    assert "out of range" in anchor["override_reason"].lower()
    # method falls through to composite, tie_breaker, or no_eligible_tracks.
    assert anchor["method"] in ("composite", "tie_breaker", "no_eligible_tracks")
```

- [ ] **Step 2: Run the tests**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_measure_album_signature_handler.py -v
```

Expected: all seven tests PASS (4 from Task 4 + 3 new anchor-path tests; the unknown-genre test counts separately).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/mastering/test_measure_album_signature_handler.py
git commit -m "$(cat <<'EOF'
test: cover anchor paths for measure_album_signature (#290 phase 3a)

- genre argument → anchor block populated via select_anchor
- explicit anchor_track=2 → method=override, deltas[1].is_anchor=True
- unknown genre → error JSON with available_genres catalogue
- out-of-range anchor_track → override_reason set, falls through to
  composite scoring

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Register the tool with the MCP server

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py`

- [ ] **Step 1: Add the registration line**

In `servers/bitwize-music-server/handlers/processing/audio.py`, the `register()` function currently reads (lines 1730-1741):

```python
def register(mcp: Any) -> None:
    """Register audio mastering tools."""
    mcp.tool()(analyze_audio)
    mcp.tool()(qc_audio)
    mcp.tool()(master_audio)
    mcp.tool()(fix_dynamic_track)
    mcp.tool()(master_with_reference)
    mcp.tool()(master_album)
    mcp.tool()(render_codec_preview)
    mcp.tool()(mono_fold_check)
    # ... (other registrations)
    mcp.tool()(prune_archival)
```

Add the new tool immediately after `prune_archival` (the other phase-1a/3a read-only signature/delivery tool):

```python
    mcp.tool()(prune_archival)
    mcp.tool()(measure_album_signature)
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
~/.bitwize-music/venv/bin/python -c "
import sys
sys.path.insert(0, 'servers/bitwize-music-server')
from handlers.processing import audio
assert hasattr(audio, 'measure_album_signature'), 'handler not found'
print('OK — measure_album_signature is exposed on the module.')
"
```

Expected: `OK — measure_album_signature is exposed on the module.`

- [ ] **Step 3: Run the full mastering test suite for regression**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/ -v
```

Expected: all PASS, including both `test_album_signature.py` (12+ tests) and `test_measure_album_signature_handler.py` (7 tests).

- [ ] **Step 4: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py
git commit -m "$(cat <<'EOF'
feat: register measure_album_signature with MCP server (#290 phase 3a)

Adds mcp.tool()(measure_album_signature) to the audio-handler
register() so the tool is exposed via the bitwize-music MCP server
alongside analyze_audio / master_album / prune_archival.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: End-to-end verification + PR prep

**Files:**
- None (validation + PR).

- [ ] **Step 1: Run the full plugin test suite**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/ -v --tb=short 2>&1 | tail -60
```

Expected: no failures. If anything outside `tests/unit/mastering/` fails, investigate — a handler edit can surprise the rest of the codebase.

- [ ] **Step 2: Run the plugin integrity test suite**

```
/bitwize-music:test all
```

Expected: all categories green. The `tools:mcp-tools` category should show the new `measure_album_signature` tool. Fix any failure before opening the PR.

- [ ] **Step 3: Smoke-test against a local album (skip if none)**

If a local album with a `mastered/` directory exists, run:

```bash
~/.bitwize-music/venv/bin/python -c "
import asyncio, json, sys, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location(
    'audio',
    Path('servers/bitwize-music-server/handlers/processing/audio.py'),
)
sys.path.insert(0, 'servers/bitwize-music-server')
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)

result = json.loads(asyncio.run(
    audio.measure_album_signature(album_slug='<local-album>', subfolder='mastered')
))
print('track_count:', result['album']['track_count'])
print('album median:', json.dumps(result['album']['median'], indent=2))
print('eligible counts:', json.dumps(result['album']['eligible_count'], indent=2))
"
```

Expected: non-empty `tracks`, populated median with finite values, `eligible_count` shows how many tracks passed each metric's eligibility check. Skip this step if no local album with `mastered/` WAVs is available.

- [ ] **Step 4: Update issue #290 checklist**

The relevant lines in `gh issue view 290 --json body`:

```
- [ ] Add `measure_album_signature` MCP tool
```

Check it off by adding the phase 3a marker. Post a comment noting the PR shipped:

```bash
gh issue comment 290 --body "$(cat <<'EOF'
Phase 3a (`measure_album_signature` MCP tool) landed in PR #<NN>:
- New pure-Python module `tools/mastering/album_signature.py` with `build_signature` + `compute_anchor_deltas` (no I/O, no MCP coupling).
- New `measure_album_signature` MCP handler: resolves subfolder (default `mastered/`), runs `analyze_track` per WAV, aggregates per-track + album-level signature, optionally runs the anchor selector + deltas when `genre` or `anchor_track` is supplied.
- Read-only — no files written. Persistence (`ALBUM_SIGNATURE.yaml`) comes in phase 3c.
- 19+ new tests covering aggregation math, delta computation, and handler I/O.

Phase 3b (`album_coherence_check` / `album_coherence_correct`) is the next slice.
EOF
)"
```

(Run after the PR merges; fill in the PR number.)

- [ ] **Step 5: Open the PR**

```bash
gh pr create --base develop \
  --title "feat: measure_album_signature MCP tool (#290 phase 3a)" \
  --body "$(cat <<'EOF'
## Summary

- Adds `tools/mastering/album_signature.py` — pure-Python aggregator (`build_signature`) + anchor-delta computer (`compute_anchor_deltas`). No I/O, no MCP coupling.
- Adds `measure_album_signature` MCP handler in `handlers/processing/audio.py`. Reads WAVs from the album's `subfolder` (default `mastered/`), runs `analyze_track` per file, then assembles per-track + album-level signature JSON. When `genre` or `anchor_track` is supplied, also runs the phase-2 anchor selector and surfaces per-track deltas from the anchor.
- Read-only — no files written. Persistence (`ALBUM_SIGNATURE.yaml`) comes with phase 3c.
- Enables tuning genre tolerance presets from reference albums and feeds phase 3b's coherence check/correct.

No changes to `genre-presets.yaml` — coherence tolerance fields land in phase 3b when they're consumed.

Part of #290.

## Test plan

- [x] `pytest tests/unit/mastering/test_album_signature.py` — happy path, missing metrics, non-finite values, empty album, single-track range, p95 interpolation, delta math, None-propagation, out-of-range anchor.
- [x] `pytest tests/unit/mastering/test_measure_album_signature_handler.py` — no-anchor happy path, missing subfolder, subfolder escape, empty dir, genre-driven anchor, explicit-override anchor, unknown genre, out-of-range anchor.
- [x] `pytest tests/` — no regressions outside the phase-3a suite.
- [x] `/bitwize-music:test all` — plugin integrity checks green.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR opens against `develop`. Return the URL.

---

## Self-Review

**Spec coverage (against issue #290 checklist):**

- ✅ Add `measure_album_signature` MCP tool — Tasks 1–6 ship the pure-Python module, the handler, tests for each code path, and MCP registration.
- ✅ No-anchor path — Task 4.
- ✅ Anchor override via state-cache `anchor_track` frontmatter — Task 4, lines in handler that read `_shared.cache.get_state()`.
- ✅ Genre-driven anchor selection — Task 5, anchor-block test.
- ✅ Explicit `anchor_track` arg overrides state cache — Task 5.
- ✅ Out-of-range `anchor_track` surfaces `override_reason` — Task 5.
- ✅ Error paths: missing subfolder, subfolder escape, no WAVs, unknown genre — Task 4 + Task 5.
- ✅ Per-track + album aggregates (median / p95 / min / max / range / eligible_count) — Task 1 + Task 2.
- ✅ Delta math with `None` handling — Task 3.
- ⬜ `ALBUM_SIGNATURE.yaml` persistence — **intentionally deferred** to phase 3c (called out in plan header, non-goals, and the PR body).
- ⬜ Coherence tolerance fields in `genre-presets.yaml` — **intentionally deferred** to phase 3b (where they're consumed).

**Placeholder scan:** No TBDs, no "add appropriate error handling" / "similar to Task N". Every test block and implementation block is spelled out.

**Type consistency:**
- `build_signature(analysis_results)` returns `{"tracks": [...], "album": {...}}` — handler spreads this into the response via `signature["tracks"]` / `signature["album"]`. ✅
- `compute_anchor_deltas(analysis_results, anchor_index_1based)` — keyword name matches test calls. ✅
- Handler `measure_album_signature(album_slug, subfolder, genre, anchor_track)` — args match every test call site and the PR doc. ✅
- `select_anchor` return dict keys (`selected_index`, `method`, `override_index`, `override_reason`, `scores`) — handler reads exactly those keys; shape matches `tools/mastering/anchor_selector.py:223-229`. ✅
- `AGGREGATE_KEYS` constant used in both `build_signature` and `compute_anchor_deltas` — single source of truth for which metrics get delta columns. ✅

---

## Execution notes

- Tasks 1–3 are pure Python with no filesystem I/O — they run fast on any machine.
- Task 4's integration test writes ~60-second sine-wave WAVs to `tmp_path`. Each run takes a few seconds (analyzer computes LUFS/STL-95/band-energy per file). Acceptable for CI.
- If Task 5's `test_measure_album_signature_with_genre_returns_anchor_block` test is flaky on synthetic sines (anchor selector classifies short sines as ineligible), lengthen the WAVs from 60s to 90s — enough for the STL-95 window pool + vocal-RMS band fallback.
- Do not modify `genre-presets.yaml` in this PR. Phase 3b will add the four `coherence_*_lu`/`_db` fields.
- The tool is read-only by design. Adding a `--write` or `persist=True` option would blur the phase 3a / 3c boundary; keep it for phase 3c.
