# Phase 2 — Anchor Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automated anchor-track selector to the album-mastering pipeline (issue #290, pipeline step 2) — composite scoring with a README frontmatter override and a deterministic tie-breaker. Also ship the carried-forward D1 refactor: extract a shared `build_effective_preset` helper to de-duplicate the ~30 lines of preset construction currently copy-pasted between `master_audio` and `master_album`.

**Architecture:** Additive. A new pure-Python module (`tools/mastering/anchor_selector.py`) owns scoring. `parse_album_readme` learns one new field (`anchor_track`) so the override flows through the existing state cache. Genre presets gain `genre_ideal_lra_lu` and `spectral_reference_energy` defaults. The `master_album` handler calls the selector after Stage 2 (Analysis) and records the result in `stages["anchor_selection"]` — the mastering loop does **not** change behavior yet (coherence correction is a later phase); selecting the anchor is a metadata step for now.

**Tech Stack:** Python 3.11, `numpy` (already imported in mastering code), `PyYAML`, `pytest` + `tmp_path` fixtures. No new deps.

---

## File Structure

**Create:**
- `tools/mastering/anchor_selector.py` — composite scoring + override + tie-breaker. Pure Python, no MCP coupling.
- `tests/unit/mastering/test_anchor_selector.py` — unit tests for scoring components, tie-breaker, override path.
- `tests/unit/mastering/test_build_effective_preset.py` — unit tests for the extracted helper (parity with existing handler behavior).

**Modify:**
- `tools/mastering/config.py` — add `build_effective_preset()` helper (D1 refactor).
- `tools/mastering/genre-presets.yaml` — add `genre_ideal_lra_lu` and `spectral_reference_energy` to `defaults:` block; document both in the header comment.
- `tools/state/parsers.py` — extend `parse_album_readme` to surface `anchor_track` frontmatter field.
- `tests/unit/state/test_parsers.py` — cover the new `anchor_track` field (present, absent, invalid).
- `templates/album.md` — add `anchor_track:` commented line to the frontmatter block.
- `servers/bitwize-music-server/handlers/processing/audio.py`:
  - Call `build_effective_preset` from `master_audio` and `master_album` (replace the duplicated block).
  - Insert an `anchor_selection` stage in `master_album` between `analysis` and `pre_qc`.
- `tests/unit/mastering/test_master_album_config_wiring.py` — add a test asserting `stages["anchor_selection"]` is populated.

**Not modified:**
- `tools/mastering/master_tracks.py` — `master_track` still consumes a fully-resolved `preset` dict; signature unchanged.
- `tools/mastering/analyze_tracks.py` — already returns the fields the selector needs (`stl_95`, `low_rms`, `vocal_rms`, `band_energy`, `peak_db`, `lra`-equivalent via `short_term_range`).
- MCP tool surface — no new tools; anchor info flows out through the existing `master_album` JSON response.

**Module responsibilities:**
- `anchor_selector.py` — pure scoring math. No I/O. Takes analysis dicts + preset dict + optional override index; returns a selection result dict.
- `config.py::build_effective_preset` — single source of truth for genre → preset-dict → effective-preset merge.
- Parsers continue to own state shape; mastering code never reads README files directly.

---

## Design Details (read before starting any task)

### Composite score (from issue #290)

```
score = 0.4 * mix_quality + 0.4 * representativeness − 1.0 * ceiling_penalty

mix_quality        = 1/(1 + |LRA − genre_ideal_LRA|) * spectral_match_score
representativeness = 1/(1 + sum_normalized_distances_to_album_median)
ceiling_penalty    = max(0, (pre_master_peak_dB − (−3.0)) / 3.0)
```

All three components live in [0, 1] (or [0, ~1] — `ceiling_penalty` is clamped to 0 below `−3 dB peak` and reaches 1.0 at 0 dBFS). Composite score is in roughly [−1, 0.8]; we never normalize, just rank.

**Inputs the selector consumes per track** (names match `analyze_track()` output — see `tools/mastering/analyze_tracks.py` lines 252–269):
- `stl_95` (may be `None` if <20 ST-LUFS windows — treat as missing signature, skip that track for anchor eligibility).
- `short_term_range` (we use this as the LRA proxy; issue #290 calls it "LRA" — the analyzer returns `short_term_range` in LU which is the same computation).
- `low_rms` (dB, may be `None` — treat same as `stl_95 is None`).
- `vocal_rms` (dB, may be `None`).
- `band_energy` (7-key dict: sub_bass/bass/low_mid/mid/high_mid/high/air, percentages summing to ~100).
- `peak_db` (used for `ceiling_penalty`).

**Inputs from genre preset:**
- `genre_ideal_lra_lu` (float, default 8.0).
- `spectral_reference_energy` (7-key dict in same shape as `band_energy`; default = balanced pop curve, documented below).

### `spectral_match_score`

Euclidean distance between the track's normalized 7-band vector and the genre reference vector, mapped to [0, 1] via `1 / (1 + d)`. Both vectors are percentages in [0, 100] already; we divide by 100 first so `d` lives in [0, √7] ≈ [0, 2.65]. That gives `spectral_match_score` ∈ [~0.27, 1.0].

```python
def _spectral_match_score(band_energy: dict, reference: dict) -> float:
    bands = ("sub_bass", "bass", "low_mid", "mid", "high_mid", "high", "air")
    track_vec = np.array([band_energy[b] / 100.0 for b in bands])
    ref_vec   = np.array([reference[b]    / 100.0 for b in bands])
    distance = float(np.linalg.norm(track_vec - ref_vec))
    return 1.0 / (1.0 + distance)
```

### `representativeness`

Sum of absolute z-score-like distances from the album median across the signature metrics (`stl_95`, `short_term_range`, `low_rms`, `vocal_rms`). Each metric normalized by its own median to stay dimensionless:

```python
def _representativeness(track, medians):
    keys = ("stl_95", "short_term_range", "low_rms", "vocal_rms")
    total = 0.0
    for key in keys:
        med = medians[key]
        val = track[key]
        if med is None or val is None:
            continue  # missing metric contributes 0 distance
        # Guard against med == 0 for LRA-like metrics in constant-tone fixtures.
        denom = abs(med) if abs(med) > 1e-6 else 1.0
        total += abs(val - med) / denom
    return 1.0 / (1.0 + total)
```

Use `numpy.median` on the finite-valued subset per metric when computing `medians`. A track with all four metrics equal to their medians scores 1.0; deviation drags the score toward 0.

### Tie-breaker

When the top two scores differ by less than 0.05, pick the track with the lowest index (1-based track number from the WAV filename prefix). Deterministic, no coin-flip.

### README override

Frontmatter `anchor_track:` is a 1-based track number. `null`, missing, empty string, or a value outside [1, N] falls through to composite scoring (and the selector's result dict records why). No exception raised.

### Pop-default spectral reference

Issue #290 allows tuning per genre later. For Phase 2 we ship a single pop default in `defaults:` (individual genres inherit). Curve derived from a balanced pop master target (rough shoulders below 60 Hz, full mid, controlled air):

```yaml
spectral_reference_energy:
  sub_bass: 8.0
  bass:     18.0
  low_mid:  20.0
  mid:      25.0
  high_mid: 14.0
  high:     10.0
  air:       5.0
```

Sum: 100.0. Values are percentages of total spectral energy; we never require a track to match exactly — the score is a soft match.

### Selector return shape

```python
{
    "selected_index": 3,              # 1-based track number, None on total failure
    "method": "composite",            # "override" | "composite" | "tie_breaker" | "no_eligible_tracks"
    "scores": [                       # length N, aligned with input track order
        {"index": 1, "score": 0.412, "mix_quality": 0.63, "representativeness": 0.80, "ceiling_penalty": 0.10, "eligible": True},
        {"index": 2, "score": None,  "eligible": False, "reason": "stl_95 is None (<20 ST-LUFS windows)"},
        ...
    ],
    "override_index": None,           # raw frontmatter value when present, else None
    "override_reason": None,          # e.g. "out of range [1, 10]" when override rejected
}
```

The `master_album` handler JSON-encodes this dict into `stages["anchor_selection"]`.

### D1 helper — `build_effective_preset`

Signature:
```python
def build_effective_preset(
    *,
    genre: str,
    cut_highmid_arg: float,
    cut_highs_arg: float,
    target_lufs_arg: float,
    ceiling_db_arg: float,
    source_sample_rate: int | None = None,
) -> dict[str, Any]:
    """Return an `effective_preset` dict for the mastering pipeline.

    Consolidates the identical ~30-line block currently in both
    master_audio() and master_album() handlers (D1 review item from #304).

    Returns a dict with:
        preset_dict          — raw genre preset (or None if genre="")
        effective_preset     — merged dict passed to master_track(preset=...)
        settings             — flat dict suitable for JSON response
        targets              — output of resolve_mastering_targets()
        genre_applied        — normalized genre key (or None)
        error                — error dict with keys "reason", "available_genres"
                                when genre lookup fails; otherwise None
    """
```

The helper raises no exceptions; on bad genre it returns `error=...` and the caller emits the existing error response. Signature keyword-only on purpose — handlers should not have to remember positional order of 6+ floats.

---

## Task 1: Extract `build_effective_preset` helper (D1 refactor)

**Files:**
- Modify: `tools/mastering/config.py`
- Create: `tests/unit/mastering/test_build_effective_preset.py`

- [ ] **Step 1: Write the failing test for the pop-genre happy path**

Create `tests/unit/mastering/test_build_effective_preset.py`:

```python
#!/usr/bin/env python3
"""Unit tests for build_effective_preset (D1 refactor extraction)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.config import build_effective_preset


class TestBuildEffectivePreset:
    def test_pop_genre_happy_path(self):
        result = build_effective_preset(
            genre="pop",
            cut_highmid_arg=0.0,
            cut_highs_arg=0.0,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
            source_sample_rate=44100,
        )
        assert result["error"] is None
        assert result["genre_applied"] == "pop"
        assert result["preset_dict"] is not None
        # effective_preset must carry resolved delivery targets
        ep = result["effective_preset"]
        assert ep["target_lufs"] == -14.0
        assert ep["output_bits"] == 24
        assert ep["output_sample_rate"] == 96000
        # settings dict is JSON-ready
        s = result["settings"]
        assert s["genre"] == "pop"
        assert s["target_lufs"] == -14.0
        assert s["ceiling_db"] == -1.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_build_effective_preset.py::TestBuildEffectivePreset::test_pop_genre_happy_path -v
```
Expected: FAIL with `ImportError: cannot import name 'build_effective_preset'`.

- [ ] **Step 3: Implement `build_effective_preset` in `tools/mastering/config.py`**

Append to `tools/mastering/config.py` (after `resolve_mastering_targets`, keep the existing imports):

```python
def build_effective_preset(
    *,
    genre: str,
    cut_highmid_arg: float,
    cut_highs_arg: float,
    target_lufs_arg: float,
    ceiling_db_arg: float,
    source_sample_rate: int | None = None,
) -> dict[str, Any]:
    """Return an effective_preset bundle for the mastering pipeline.

    Consolidates the duplicated preset-construction block that used to live in
    both master_audio() and master_album() handlers (D1 review item from #304).

    Returns a dict with keys:
        preset_dict          — raw genre preset (or None if genre="")
        effective_preset     — merged dict suitable for master_track(preset=...)
        settings             — flat dict suitable for the JSON response
        targets              — output of resolve_mastering_targets()
        genre_applied        — normalized genre key (or None)
        error                — None on success, otherwise
                                {"reason": str, "available_genres": list[str]}

    On genre lookup failure, error is populated and all other fields may be
    None / {} — callers must check `error` first.
    """
    # Local import to avoid circular dependency at module load.
    from tools.mastering.master_tracks import load_genre_presets

    effective_highmid = cut_highmid_arg
    effective_highs = cut_highs_arg
    effective_compress = 1.5
    genre_applied: str | None = None
    preset_dict: dict[str, Any] | None = None

    if genre:
        presets = load_genre_presets()
        genre_key = genre.lower()
        if genre_key not in presets:
            return {
                "preset_dict": None,
                "effective_preset": {},
                "settings": {},
                "targets": {},
                "genre_applied": None,
                "error": {
                    "reason": f"Unknown genre: {genre}",
                    "available_genres": sorted(presets.keys()),
                },
            }
        preset_dict = dict(presets[genre_key])
        if cut_highmid_arg == 0.0:
            effective_highmid = preset_dict["cut_highmid"]
        if cut_highs_arg == 0.0:
            effective_highs = preset_dict["cut_highs"]
        effective_compress = preset_dict["compress_ratio"]
        genre_applied = genre_key

    mastering_cfg = load_mastering_config()
    targets = resolve_mastering_targets(
        config=mastering_cfg,
        preset=preset_dict,
        target_lufs_arg=target_lufs_arg,
        ceiling_db_arg=ceiling_db_arg,
        source_sample_rate=source_sample_rate,
    )
    effective_lufs = targets["target_lufs"]
    effective_ceiling = targets["ceiling_db"]

    effective_preset: dict[str, Any] = {
        **(preset_dict or {}),
        "target_lufs": effective_lufs,
        "output_bits": targets["output_bits"],
        "output_sample_rate": targets["output_sample_rate"],
        "cut_highmid": effective_highmid,
        "cut_highs": effective_highs,
        "compress_ratio": effective_compress,
    }

    settings: dict[str, Any] = {
        "genre": genre_applied,
        "target_lufs": effective_lufs,
        "ceiling_db": effective_ceiling,
        "output_bits": targets["output_bits"],
        "output_sample_rate": targets["output_sample_rate"],
        "source_sample_rate": targets["source_sample_rate"],
        "upsampled_from_source": targets["upsampled_from_source"],
        "archival_enabled": targets["archival_enabled"],
        "adm_aac_encoder": targets["adm_aac_encoder"],
        "cut_highmid": effective_highmid,
        "cut_highs": effective_highs,
    }

    return {
        "preset_dict": preset_dict,
        "effective_preset": effective_preset,
        "settings": settings,
        "targets": targets,
        "genre_applied": genre_applied,
        "error": None,
    }
```

- [ ] **Step 4: Run the happy-path test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_build_effective_preset.py::TestBuildEffectivePreset::test_pop_genre_happy_path -v
```
Expected: PASS.

- [ ] **Step 5: Add the empty-genre test**

Append inside `class TestBuildEffectivePreset:`:

```python
    def test_empty_genre_no_preset(self):
        result = build_effective_preset(
            genre="",
            cut_highmid_arg=0.0,
            cut_highs_arg=0.0,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        assert result["error"] is None
        assert result["preset_dict"] is None
        assert result["genre_applied"] is None
        # Still returns a working effective_preset with delivery-target fields
        ep = result["effective_preset"]
        assert ep["target_lufs"] == -14.0
        assert ep["compress_ratio"] == 1.5
        assert ep["cut_highmid"] == 0.0
```

- [ ] **Step 6: Add the unknown-genre test**

```python
    def test_unknown_genre_returns_error(self):
        result = build_effective_preset(
            genre="not-a-real-genre",
            cut_highmid_arg=0.0,
            cut_highs_arg=0.0,
            target_lufs_arg=-14.0,
            ceiling_db_arg=-1.0,
        )
        assert result["error"] is not None
        assert "Unknown genre" in result["error"]["reason"]
        assert "available_genres" in result["error"]
        assert "pop" in result["error"]["available_genres"]
```

- [ ] **Step 7: Add the explicit-arg-overrides-preset test**

```python
    def test_explicit_args_override_preset(self):
        result = build_effective_preset(
            genre="pop",
            cut_highmid_arg=-2.5,  # explicit override
            cut_highs_arg=-1.0,    # explicit override
            target_lufs_arg=-16.0, # explicit override
            ceiling_db_arg=-1.5,   # explicit override
        )
        assert result["error"] is None
        ep = result["effective_preset"]
        assert ep["cut_highmid"] == -2.5
        assert ep["cut_highs"] == -1.0
        assert ep["target_lufs"] == -16.0
        s = result["settings"]
        assert s["ceiling_db"] == -1.5
```

- [ ] **Step 8: Run all tests to verify they pass**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_build_effective_preset.py -v
```
Expected: 4 PASS.

- [ ] **Step 9: Commit**

```bash
git add tools/mastering/config.py tests/unit/mastering/test_build_effective_preset.py
git commit -m "$(cat <<'EOF'
refactor: extract build_effective_preset helper (#290 phase 2)

Consolidates the ~30 lines of preset construction duplicated between
master_audio and master_album handlers (D1 review item from #304).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Wire `build_effective_preset` into `master_audio` and `master_album`

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py`

- [ ] **Step 1: Update `master_audio` to call the helper**

In `servers/bitwize-music-server/handlers/processing/audio.py`, replace lines 264–296 (from `# Apply genre preset if specified` through `effective_ceiling = targets["ceiling_db"]`) with:

```python
    from tools.mastering.config import build_effective_preset
    from tools.mastering.master_tracks import (
        master_track as _master_track,
    )

    bundle = build_effective_preset(
        genre=genre,
        cut_highmid_arg=cut_highmid,
        cut_highs_arg=cut_highs,
        target_lufs_arg=target_lufs,
        ceiling_db_arg=ceiling_db,
    )
    if bundle["error"] is not None:
        return _safe_json({
            "error": bundle["error"]["reason"],
            "available_genres": bundle["error"]["available_genres"],
        })
    preset_dict = bundle["preset_dict"]
    targets = bundle["targets"]
    effective_lufs = targets["target_lufs"]
    effective_ceiling = targets["ceiling_db"]
    effective_highmid = bundle["settings"]["cut_highmid"]
    effective_highs = bundle["settings"]["cut_highs"]
    effective_compress = bundle["effective_preset"]["compress_ratio"]
    genre_applied = bundle["genre_applied"]
```

Then replace the `effective_preset` dict literal inside the track loop (currently lines 352–360) with:

```python
            effective_preset = bundle["effective_preset"]
```

- [ ] **Step 2: Update `master_album` to call the helper**

Replace lines 708–785 (from `# Resolve genre presets and effective settings` through the `settings = {...}` block) with:

```python
    from tools.mastering.config import build_effective_preset
    from tools.mastering.master_tracks import (
        master_track as _master_track,
    )

    source_sample_rate: int | None = None
    try:
        import soundfile as _sf
        source_sample_rate = int(_sf.info(str(wav_files[0])).samplerate)
    except Exception as _probe_exc:  # pragma: no cover - probe is best-effort
        logger.debug(
            "Source sample rate probe failed for %s: %s — "
            "upsampling notice will be suppressed",
            wav_files[0],
            _probe_exc,
        )
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
            "album_slug": album_slug,
            "stage_reached": "pre_flight",
            "stages": stages,
            "failed_stage": "pre_flight",
            "failure_detail": bundle["error"],
        })
    preset_dict = bundle["preset_dict"]
    targets = bundle["targets"]
    effective_lufs = targets["target_lufs"]
    effective_ceiling = targets["ceiling_db"]
    effective_highmid = bundle["settings"]["cut_highmid"]
    effective_highs = bundle["settings"]["cut_highs"]
    effective_compress = bundle["effective_preset"]["compress_ratio"]
    genre_applied = bundle["genre_applied"]
    settings = bundle["settings"]
```

Replace the `effective_preset` dict literal inside the Stage 4 loop (currently lines 924–932) with:

```python
            effective_preset = bundle["effective_preset"]
```

- [ ] **Step 3: Run the existing wiring tests to verify nothing regressed**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_master_audio_config_wiring.py \
    tests/unit/mastering/test_master_album_config_wiring.py \
    -v
```
Expected: all PASS (no behavior change — same outputs from a consolidated call path).

- [ ] **Step 4: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py
git commit -m "$(cat <<'EOF'
refactor: route master_audio+master_album through build_effective_preset (#290 phase 2)

Eliminates the last copy of the preset construction block.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Surface `anchor_track` from album frontmatter

**Files:**
- Modify: `tools/state/parsers.py`
- Modify: `tests/unit/state/test_parsers.py`
- Modify: `templates/album.md`

- [ ] **Step 1: Add failing test for anchor_track extraction**

In `tests/unit/state/test_parsers.py`, add inside the existing `class TestParseAlbumReadme:` (around line 75):

```python
    def test_parses_anchor_track_when_set(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            '---\n'
            'title: "Test"\n'
            'anchor_track: 3\n'
            '---\n'
            '# Test\n'
            '## Album Details\n'
            '| **Status** | Concept |\n'
        )
        result = parse_album_readme(readme)
        assert result.get("anchor_track") == 3

    def test_anchor_track_absent_returns_none(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            '---\n'
            'title: "Test"\n'
            '---\n'
            '# Test\n'
            '## Album Details\n'
            '| **Status** | Concept |\n'
        )
        result = parse_album_readme(readme)
        assert result.get("anchor_track") is None

    def test_anchor_track_null_returns_none(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            '---\n'
            'title: "Test"\n'
            'anchor_track: null\n'
            '---\n'
            '# Test\n'
            '## Album Details\n'
            '| **Status** | Concept |\n'
        )
        result = parse_album_readme(readme)
        assert result.get("anchor_track") is None

    def test_anchor_track_non_int_coerced_to_none(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            '---\n'
            'title: "Test"\n'
            'anchor_track: "not a number"\n'
            '---\n'
            '# Test\n'
            '## Album Details\n'
            '| **Status** | Concept |\n'
        )
        result = parse_album_readme(readme)
        # Malformed value must not crash and must not poison downstream code.
        assert result.get("anchor_track") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/state/test_parsers.py::TestParseAlbumReadme::test_parses_anchor_track_when_set \
    tests/unit/state/test_parsers.py::TestParseAlbumReadme::test_anchor_track_absent_returns_none \
    tests/unit/state/test_parsers.py::TestParseAlbumReadme::test_anchor_track_null_returns_none \
    tests/unit/state/test_parsers.py::TestParseAlbumReadme::test_anchor_track_non_int_coerced_to_none \
    -v
```
Expected: all 4 FAIL with `AssertionError` (either key absent or wrong value).

- [ ] **Step 3: Implement anchor_track extraction in `parse_album_readme`**

In `tools/state/parsers.py`, inside `parse_album_readme` (around line 165, right after `result['explicit'] = fm.get('explicit', False)`), insert:

```python
    # Optional anchor-track override for album mastering (issue #290 phase 2).
    # Frontmatter uses 1-based track numbers. Non-int / null / missing → None,
    # and the mastering pipeline falls through to composite anchor scoring.
    anchor_raw = fm.get('anchor_track')
    if isinstance(anchor_raw, bool):  # bool is an int subclass; exclude it
        result['anchor_track'] = None
    elif isinstance(anchor_raw, int):
        result['anchor_track'] = anchor_raw
    else:
        result['anchor_track'] = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/state/test_parsers.py::TestParseAlbumReadme::test_parses_anchor_track_when_set \
    tests/unit/state/test_parsers.py::TestParseAlbumReadme::test_anchor_track_absent_returns_none \
    tests/unit/state/test_parsers.py::TestParseAlbumReadme::test_anchor_track_null_returns_none \
    tests/unit/state/test_parsers.py::TestParseAlbumReadme::test_anchor_track_non_int_coerced_to_none \
    -v
```
Expected: 4 PASS.

- [ ] **Step 5: Update `templates/album.md` to document the field**

In `templates/album.md`, after line 6 (the `explicit: false` line), insert:

```yaml
# anchor_track: null  # Optional: 1-based track number to anchor album mastering (issue #290). Empty = auto-select by composite score.
```

Keep it commented so the parser treats it as absent for new albums — users opt in by uncommenting.

- [ ] **Step 6: Run the full parsers test suite to verify nothing regressed**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/state/test_parsers.py -v
```
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add tools/state/parsers.py tests/unit/state/test_parsers.py templates/album.md
git commit -m "$(cat <<'EOF'
feat: surface anchor_track frontmatter field (#290 phase 2)

parse_album_readme now extracts the optional anchor_track override so
it flows through the state cache to the mastering pipeline without
mastering code ever reading README files directly.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add genre-preset spectral reference + LRA ideal

**Files:**
- Modify: `tools/mastering/genre-presets.yaml`

- [ ] **Step 1: Add documentation comments and default values**

In `tools/mastering/genre-presets.yaml`, add these lines inside the header comment block (between the existing `mono_fold_correlation_warn` doc line and the blank line before `# Override per-user`, around line 70):

```yaml
#   genre_ideal_lra_lu     - Target loudness-range (LU) used by the album-mastering
#                            anchor selector (#290 phase 2). Tracks whose LRA is
#                            close to this score higher on mix_quality. Default 8.0
#                            matches balanced pop; dynamic genres override upward.
#   spectral_reference_energy - 7-band reference curve (sub_bass / bass / low_mid /
#                            mid / high_mid / high / air) as percentages of total
#                            spectral energy, summing to 100. Anchor selector
#                            compares each track's band_energy to this curve via
#                            Euclidean distance. Genre overrides merge key-by-key;
#                            missing keys inherit from defaults.
```

Then append to the `defaults:` block (after the existing `midside_high_freq: 8000` entry near the end of the defaults block — find it with the `Read` tool and insert immediately before the next top-level `genres:` key):

```yaml
  # Album-mastering anchor selector (#290 phase 2) — pop defaults
  genre_ideal_lra_lu: 8.0
  spectral_reference_energy:
    sub_bass: 8.0
    bass:     18.0
    low_mid:  20.0
    mid:      25.0
    high_mid: 14.0
    high:     10.0
    air:       5.0
```

- [ ] **Step 2: Verify the YAML still parses**

```bash
~/.bitwize-music/venv/bin/python -c "
import yaml, sys
from pathlib import Path
data = yaml.safe_load(Path('tools/mastering/genre-presets.yaml').read_text())
assert 'defaults' in data, 'defaults key missing'
assert data['defaults']['genre_ideal_lra_lu'] == 8.0
ref = data['defaults']['spectral_reference_energy']
for b in ('sub_bass', 'bass', 'low_mid', 'mid', 'high_mid', 'high', 'air'):
    assert b in ref, f'missing band: {b}'
total = sum(ref.values())
assert abs(total - 100.0) < 0.001, f'bands sum to {total}, not 100'
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 3: Verify load_genre_presets() surfaces the new defaults**

```bash
~/.bitwize-music/venv/bin/python -c "
from tools.mastering.master_tracks import load_genre_presets
p = load_genre_presets()
pop = p['pop']
assert pop.get('genre_ideal_lra_lu') == 8.0, pop.get('genre_ideal_lra_lu')
ref = pop.get('spectral_reference_energy')
assert ref is not None, 'pop inherits spectral_reference_energy from defaults'
assert ref['mid'] == 25.0
print('OK')
"
```
Expected: `OK`.

If `load_genre_presets` merges per-key and does not inherit the nested `spectral_reference_energy` dict for every genre (this depends on the merge implementation — check `tools/mastering/master_tracks.py` `load_genre_presets` around line 141), skip this step and the selector will look up defaults directly in Task 5. Record the finding in the commit message.

- [ ] **Step 4: Commit**

```bash
git add tools/mastering/genre-presets.yaml
git commit -m "$(cat <<'EOF'
feat: add genre_ideal_lra + spectral_reference_energy defaults (#290 phase 2)

New preset fields consumed by the album-mastering anchor selector.
Pop-balanced defaults; per-genre overrides can land later as reference
albums are measured with measure_album_signature.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Anchor selector — spectral match score

**Files:**
- Create: `tools/mastering/anchor_selector.py`
- Create: `tests/unit/mastering/test_anchor_selector.py`

- [ ] **Step 1: Write failing test for spectral_match_score**

Create `tests/unit/mastering/test_anchor_selector.py`:

```python
#!/usr/bin/env python3
"""Unit tests for the album-mastering anchor selector (#290 phase 2)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.anchor_selector import (
    _spectral_match_score,
)


REF = {
    "sub_bass": 8.0,
    "bass":     18.0,
    "low_mid":  20.0,
    "mid":      25.0,
    "high_mid": 14.0,
    "high":     10.0,
    "air":       5.0,
}


class TestSpectralMatchScore:
    def test_exact_match_scores_one(self):
        assert _spectral_match_score(REF, REF) == pytest.approx(1.0)

    def test_mismatched_curve_scores_below_match(self):
        off = {**REF, "mid": 5.0, "high": 30.0}  # large distance
        score_match = _spectral_match_score(REF, REF)
        score_off = _spectral_match_score(off, REF)
        assert score_off < score_match
        assert 0.0 < score_off < 1.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_anchor_selector.py::TestSpectralMatchScore -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.mastering.anchor_selector'`.

- [ ] **Step 3: Create `anchor_selector.py` with `_spectral_match_score`**

Create `tools/mastering/anchor_selector.py`:

```python
"""Album-mastering anchor selector (#290 pipeline step 2).

Pure-Python scoring — no I/O, no MCP coupling. The handler in
``servers/bitwize-music-server/handlers/processing/audio.py`` calls
``select_anchor`` after Stage 2 (Analysis) with the list of
``analyze_track`` results plus the resolved genre preset.

Selection strategy (in order):
1. ``override_index`` supplied by caller (from album README
   frontmatter ``anchor_track``). Validated against the track list.
2. Composite scoring: ``0.4 * mix_quality + 0.4 * representativeness
   − 1.0 * ceiling_penalty`` (formula from issue #290).
3. Deterministic tie-breaker when top two scores differ by < 0.05:
   lowest 1-based index wins.

Tracks missing any of ``stl_95`` / ``low_rms`` / ``vocal_rms`` /
``short_term_range`` are considered ineligible and surface with
``eligible: False`` + a ``reason`` in the per-track score list.
"""

from __future__ import annotations

from typing import Any

import numpy as np

BANDS = ("sub_bass", "bass", "low_mid", "mid", "high_mid", "high", "air")
SIGNATURE_KEYS = ("stl_95", "short_term_range", "low_rms", "vocal_rms")
TIE_BREAKER_EPSILON = 0.05


def _spectral_match_score(band_energy: dict[str, float],
                          reference: dict[str, float]) -> float:
    """Euclidean distance between 7-band vectors, mapped to (0, 1].

    Bands are percentages of total spectral energy (sum ≈ 100). We divide
    by 100 so the distance lives in [0, √7], then map with 1/(1+d).
    """
    track_vec = np.array([band_energy[b] / 100.0 for b in BANDS])
    ref_vec   = np.array([reference[b]    / 100.0 for b in BANDS])
    distance = float(np.linalg.norm(track_vec - ref_vec))
    return 1.0 / (1.0 + distance)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_anchor_selector.py::TestSpectralMatchScore -v
```
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/mastering/anchor_selector.py tests/unit/mastering/test_anchor_selector.py
git commit -m "$(cat <<'EOF'
feat: anchor selector — spectral match score (#290 phase 2)

First scoring component for the album-mastering anchor selector:
Euclidean distance between track band_energy and genre reference
curve, mapped to (0, 1].

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Anchor selector — mix_quality, representativeness, ceiling_penalty

**Files:**
- Modify: `tools/mastering/anchor_selector.py`
- Modify: `tests/unit/mastering/test_anchor_selector.py`

- [ ] **Step 1: Write failing tests for the three component scorers**

Append to `tests/unit/mastering/test_anchor_selector.py`:

```python
from tools.mastering.anchor_selector import (
    _mix_quality_score,
    _representativeness_score,
    _ceiling_penalty_score,
    _album_medians,
)


def _track(**overrides) -> dict:
    base = {
        "filename": "01.wav",
        "stl_95": -14.0,
        "short_term_range": 8.0,
        "low_rms": -20.0,
        "vocal_rms": -18.0,
        "peak_db": -4.0,
        "band_energy": dict(REF),
    }
    base.update(overrides)
    return base


class TestMixQuality:
    def test_on_target_lra_and_spectral_match_scores_near_one(self):
        track = _track(short_term_range=8.0, band_energy=dict(REF))
        score = _mix_quality_score(track, REF, genre_ideal_lra=8.0)
        # LRA difference 0 → 1/(1+0)=1; spectral exact → 1; product = 1
        assert score == pytest.approx(1.0)

    def test_off_target_lra_drops_score(self):
        track = _track(short_term_range=14.0, band_energy=dict(REF))
        score = _mix_quality_score(track, REF, genre_ideal_lra=8.0)
        # |14 − 8| = 6 → 1/7 ≈ 0.143; spectral match = 1 → score ≈ 0.143
        assert score == pytest.approx(1.0 / 7.0, rel=1e-3)


class TestRepresentativeness:
    def test_track_at_median_scores_one(self):
        tracks = [
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
        ]
        medians = _album_medians(tracks)
        score = _representativeness_score(tracks[0], medians)
        assert score == pytest.approx(1.0)

    def test_distant_track_scores_below(self):
        tracks = [
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
            _track(stl_95=-14.0, short_term_range=8.0, low_rms=-20.0, vocal_rms=-18.0),
            _track(stl_95=-10.0, short_term_range=3.0, low_rms=-12.0, vocal_rms=-10.0),
        ]
        medians = _album_medians(tracks)
        score_close = _representativeness_score(tracks[0], medians)
        score_far = _representativeness_score(tracks[2], medians)
        assert score_close > score_far
        assert 0.0 < score_far < 1.0


class TestCeilingPenalty:
    def test_peak_below_minus3_no_penalty(self):
        assert _ceiling_penalty_score(-6.0) == 0.0
        assert _ceiling_penalty_score(-3.0) == 0.0

    def test_peak_at_0dbfs_max_penalty(self):
        assert _ceiling_penalty_score(0.0) == pytest.approx(1.0)

    def test_peak_midway_scaled(self):
        assert _ceiling_penalty_score(-1.5) == pytest.approx(0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_anchor_selector.py -v
```
Expected: FAILs with `ImportError` for the new helpers.

- [ ] **Step 3: Implement the three scorers + `_album_medians`**

Append to `tools/mastering/anchor_selector.py`:

```python
def _album_medians(tracks: list[dict[str, Any]]) -> dict[str, float | None]:
    """Median of each signature key across tracks with finite values.

    Returns ``None`` for a key when every track's value is ``None``.
    """
    medians: dict[str, float | None] = {}
    for key in SIGNATURE_KEYS:
        values = [t[key] for t in tracks if t.get(key) is not None]
        medians[key] = float(np.median(values)) if values else None
    return medians


def _mix_quality_score(track: dict[str, Any],
                       spectral_reference: dict[str, float],
                       genre_ideal_lra: float) -> float:
    """Combined LRA-match × spectral-match score, ∈ (0, 1]."""
    lra = track.get("short_term_range")
    if lra is None:
        return 0.0
    lra_match = 1.0 / (1.0 + abs(float(lra) - float(genre_ideal_lra)))
    spectral = _spectral_match_score(track["band_energy"], spectral_reference)
    return lra_match * spectral


def _representativeness_score(track: dict[str, Any],
                              medians: dict[str, float | None]) -> float:
    """How close track's signature sits to the album median across SIGNATURE_KEYS."""
    total = 0.0
    for key in SIGNATURE_KEYS:
        median = medians.get(key)
        value = track.get(key)
        if median is None or value is None:
            continue
        denom = abs(median) if abs(median) > 1e-6 else 1.0
        total += abs(float(value) - float(median)) / denom
    return 1.0 / (1.0 + total)


def _ceiling_penalty_score(peak_db: float) -> float:
    """Penalty for tracks pinned near 0 dBFS. 0 at ≤ -3 dB, 1 at 0 dBFS."""
    return max(0.0, min(1.0, (float(peak_db) - (-3.0)) / 3.0))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_anchor_selector.py -v
```
Expected: all PASS (including the earlier TestSpectralMatchScore).

- [ ] **Step 5: Commit**

```bash
git add tools/mastering/anchor_selector.py tests/unit/mastering/test_anchor_selector.py
git commit -m "$(cat <<'EOF'
feat: anchor selector — mix_quality, representativeness, ceiling_penalty (#290 phase 2)

Implements the three per-track component scores from the issue #290
composite formula. Next task wires them together + override path.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Anchor selector — `select_anchor` composite + override + tie-breaker

**Files:**
- Modify: `tools/mastering/anchor_selector.py`
- Modify: `tests/unit/mastering/test_anchor_selector.py`

- [ ] **Step 1: Write failing test for composite scoring path**

Append to `tests/unit/mastering/test_anchor_selector.py`:

```python
from tools.mastering.anchor_selector import select_anchor


def _preset(ideal_lra: float = 8.0) -> dict:
    return {
        "genre_ideal_lra_lu": ideal_lra,
        "spectral_reference_energy": dict(REF),
    }


class TestSelectAnchorComposite:
    def test_picks_representative_track(self):
        # Track 1 matches album median exactly; track 2 is an outlier.
        t1 = _track(filename="01.wav", stl_95=-14.0, short_term_range=8.0,
                    low_rms=-20.0, vocal_rms=-18.0, peak_db=-5.0)
        t2 = _track(filename="02.wav", stl_95=-14.0, short_term_range=8.0,
                    low_rms=-20.0, vocal_rms=-18.0, peak_db=-5.0)
        t3 = _track(filename="03.wav", stl_95=-10.0, short_term_range=3.0,
                    low_rms=-12.0, vocal_rms=-10.0, peak_db=-2.0)
        result = select_anchor([t1, t2, t3], _preset())
        assert result["method"] == "tie_breaker"  # 01 and 02 identical
        assert result["selected_index"] == 1
        assert result["scores"][2]["score"] < result["scores"][0]["score"]

    def test_ceiling_penalty_demotes_hot_track(self):
        # Representative but near 0 dBFS → penalty beats representativeness.
        t1 = _track(filename="01.wav", stl_95=-14.0, short_term_range=8.0,
                    low_rms=-20.0, vocal_rms=-18.0, peak_db=-0.5)
        t2 = _track(filename="02.wav", stl_95=-14.0, short_term_range=8.0,
                    low_rms=-20.0, vocal_rms=-18.0, peak_db=-6.0)
        result = select_anchor([t1, t2], _preset())
        assert result["selected_index"] == 2  # cooler track wins
        assert result["scores"][0]["ceiling_penalty"] > 0
        assert result["scores"][1]["ceiling_penalty"] == 0.0


class TestSelectAnchorOverride:
    def test_valid_override_short_circuits_scoring(self):
        t1 = _track(filename="01.wav", peak_db=-5.0)
        t2 = _track(filename="02.wav", peak_db=-5.0)
        t3 = _track(filename="03.wav", peak_db=-5.0)
        result = select_anchor([t1, t2, t3], _preset(), override_index=2)
        assert result["method"] == "override"
        assert result["selected_index"] == 2
        assert result["override_index"] == 2
        assert result["override_reason"] is None

    def test_out_of_range_override_falls_through_to_scoring(self):
        t1 = _track(filename="01.wav", peak_db=-5.0)
        t2 = _track(filename="02.wav", peak_db=-5.0)
        result = select_anchor([t1, t2], _preset(), override_index=99)
        assert result["method"] in ("composite", "tie_breaker")
        assert result["override_index"] == 99
        assert "out of range" in (result["override_reason"] or "")

    def test_zero_override_treated_as_no_override(self):
        t1 = _track(filename="01.wav")
        t2 = _track(filename="02.wav")
        result = select_anchor([t1, t2], _preset(), override_index=0)
        assert result["method"] != "override"


class TestSelectAnchorTieBreaker:
    def test_ties_resolve_to_lowest_index(self):
        # Three identical tracks → lowest index wins.
        tracks = [_track(filename=f"0{i}.wav") for i in (1, 2, 3)]
        result = select_anchor(tracks, _preset())
        assert result["method"] == "tie_breaker"
        assert result["selected_index"] == 1

    def test_scores_outside_epsilon_use_composite(self):
        t1 = _track(filename="01.wav", short_term_range=8.0)   # on-target LRA
        t2 = _track(filename="02.wav", short_term_range=20.0)  # far-off LRA
        result = select_anchor([t1, t2], _preset())
        assert result["method"] == "composite"
        assert result["selected_index"] == 1


class TestSelectAnchorEligibility:
    def test_missing_signature_track_marked_ineligible(self):
        t1 = _track(filename="01.wav")
        t2 = _track(filename="02.wav", stl_95=None)  # missing
        result = select_anchor([t1, t2], _preset())
        assert result["selected_index"] == 1
        score_entry = next(s for s in result["scores"] if s["index"] == 2)
        assert score_entry["eligible"] is False
        assert "stl_95" in score_entry["reason"]

    def test_all_ineligible_returns_no_selection(self):
        t1 = _track(filename="01.wav", stl_95=None)
        t2 = _track(filename="02.wav", stl_95=None)
        result = select_anchor([t1, t2], _preset())
        assert result["selected_index"] is None
        assert result["method"] == "no_eligible_tracks"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_anchor_selector.py -v
```
Expected: FAILs with `ImportError` for `select_anchor`.

- [ ] **Step 3: Implement `select_anchor`**

Append to `tools/mastering/anchor_selector.py`:

```python
def _is_eligible(track: dict[str, Any]) -> tuple[bool, str | None]:
    for key in SIGNATURE_KEYS:
        if track.get(key) is None:
            return False, f"{key} is None (analyzer could not compute it)"
    if "band_energy" not in track or not track["band_energy"]:
        return False, "band_energy missing"
    return True, None


def select_anchor(
    tracks: list[dict[str, Any]],
    preset: dict[str, Any],
    override_index: int | None = None,
) -> dict[str, Any]:
    """Select the anchor track for album mastering.

    Args:
        tracks: List of ``analyze_track`` result dicts, in track order
                (index 0 == track #1). Must include ``filename``,
                ``stl_95``, ``short_term_range``, ``low_rms``,
                ``vocal_rms``, ``peak_db``, ``band_energy``.
        preset: Genre preset dict; must include
                ``genre_ideal_lra_lu`` and ``spectral_reference_energy``
                (fall back to defaults.yaml shape when missing).
        override_index: Optional 1-based track number from album README
                frontmatter ``anchor_track``. Values ≤ 0 or > len(tracks)
                fall through to composite scoring.

    Returns:
        Dict — see module docstring + plan design section for shape.
    """
    ideal_lra = float(preset.get("genre_ideal_lra_lu", 8.0))
    spectral_ref = preset.get("spectral_reference_energy") or {
        "sub_bass": 8.0, "bass": 18.0, "low_mid": 20.0, "mid": 25.0,
        "high_mid": 14.0, "high": 10.0, "air": 5.0,
    }

    # Override path
    override_reason: str | None = None
    if override_index is not None and override_index > 0:
        if 1 <= override_index <= len(tracks):
            return {
                "selected_index": override_index,
                "method": "override",
                "scores": [
                    {"index": i + 1,
                     "filename": t.get("filename"),
                     "score": None,
                     "eligible": None,
                     "reason": "skipped — override in effect"}
                    for i, t in enumerate(tracks)
                ],
                "override_index": override_index,
                "override_reason": None,
            }
        override_reason = (
            f"out of range [1, {len(tracks)}] — fell through to composite scoring"
        )
    elif override_index is not None and override_index <= 0:
        override_reason = "non-positive — treated as no override"

    # Composite scoring
    eligible_tracks: list[tuple[int, dict[str, Any]]] = []
    scores: list[dict[str, Any]] = []
    for i, track in enumerate(tracks):
        ok, reason = _is_eligible(track)
        entry: dict[str, Any] = {
            "index": i + 1,
            "filename": track.get("filename"),
            "eligible": ok,
        }
        if not ok:
            entry["score"] = None
            entry["reason"] = reason
            scores.append(entry)
            continue
        eligible_tracks.append((i + 1, track))
        entry["reason"] = None
        scores.append(entry)

    if not eligible_tracks:
        return {
            "selected_index": None,
            "method": "no_eligible_tracks",
            "scores": scores,
            "override_index": override_index,
            "override_reason": override_reason,
        }

    medians = _album_medians([t for _, t in eligible_tracks])
    for entry in scores:
        if not entry["eligible"]:
            continue
        idx = entry["index"]
        track = tracks[idx - 1]
        mq = _mix_quality_score(track, spectral_ref, ideal_lra)
        rp = _representativeness_score(track, medians)
        cp = _ceiling_penalty_score(float(track.get("peak_db", 0.0)))
        composite = 0.4 * mq + 0.4 * rp - 1.0 * cp
        entry["mix_quality"] = mq
        entry["representativeness"] = rp
        entry["ceiling_penalty"] = cp
        entry["score"] = composite

    ranked = sorted(
        (e for e in scores if e["eligible"]),
        key=lambda e: (-e["score"], e["index"]),
    )
    top = ranked[0]
    method = "composite"
    if len(ranked) >= 2 and abs(ranked[0]["score"] - ranked[1]["score"]) < TIE_BREAKER_EPSILON:
        method = "tie_breaker"

    return {
        "selected_index": top["index"],
        "method": method,
        "scores": scores,
        "override_index": override_index,
        "override_reason": override_reason,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/test_anchor_selector.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/mastering/anchor_selector.py tests/unit/mastering/test_anchor_selector.py
git commit -m "$(cat <<'EOF'
feat: select_anchor composite scoring + override + tie-breaker (#290 phase 2)

Wires mix_quality, representativeness, and ceiling_penalty into the
composite formula from issue #290. Supports README frontmatter
override and deterministic tie-breaker on ties within 0.05.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Integrate anchor selector into `master_album` pipeline

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py`
- Modify: `tests/unit/mastering/test_master_album_config_wiring.py`

- [ ] **Step 1: Add failing test asserting `stages["anchor_selection"]` is populated**

Open `tests/unit/mastering/test_master_album_config_wiring.py` and add a new test method to whatever test class owns the end-to-end master_album assertion. (Check the file layout with `Read`; if no class exists, add a module-level async test following the file's existing pattern.)

```python
    def test_master_album_records_anchor_selection_stage(self, album_with_wavs, monkeypatch):
        """#290 phase 2: master_album runs anchor selector after analysis."""
        import asyncio
        import json as _json
        from servers.bitwize-music-server.handlers.processing.audio import master_album

        result_json = asyncio.run(master_album(
            album_slug=album_with_wavs["slug"],
            genre="pop",
        ))
        data = _json.loads(result_json)
        stages = data["stages"]
        assert "anchor_selection" in stages
        anchor = stages["anchor_selection"]
        assert anchor["status"] in ("pass", "warn")
        # Either a valid 1-based index or null for all-ineligible synthetic fixtures
        selected = anchor["selected_index"]
        assert selected is None or 1 <= selected <= album_with_wavs["track_count"]
        assert anchor["method"] in ("composite", "tie_breaker", "override",
                                    "no_eligible_tracks")
        assert "scores" in anchor
```

If `album_with_wavs` isn't an existing fixture in that file, use whatever fixture the file's other happy-path tests use (e.g. scan the file for `monkeypatch` + `tmp_path` patterns and model the new test on them). Key invariant: the test must call `master_album` on a real album dir with at least 2 synthetic WAVs.

Note: the module path `servers.bitwize-music-server.handlers.processing.audio` uses a hyphenated package name. If the imports in the existing tests use `importlib.import_module("servers.bitwize-music-server.handlers.processing.audio")` or similar, copy that pattern.

- [ ] **Step 2: Run test to verify it fails**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_master_album_config_wiring.py::TestClass::test_master_album_records_anchor_selection_stage -v
```

(Replace `TestClass` with the actual class name.)
Expected: FAIL with `KeyError: 'anchor_selection'` or equivalent.

- [ ] **Step 3: Insert the anchor_selection stage in `master_album`**

In `servers/bitwize-music-server/handlers/processing/audio.py`, immediately after the `stages["analysis"] = {...}` block (currently around line 811), insert:

```python
    # --- Stage 2b: Anchor selection (#290 phase 2) ---
    from tools.mastering.anchor_selector import select_anchor

    # Read anchor_track override from state cache (parse_album_readme
    # surfaces it as an int or None).
    anchor_override: int | None = None
    state_albums = (_shared.cache.get_state() or {}).get("albums", {})
    album_state = state_albums.get(_normalize_slug(album_slug), {})
    raw_override = album_state.get("anchor_track")
    if isinstance(raw_override, int) and not isinstance(raw_override, bool):
        anchor_override = raw_override

    # Align analysis results with track-number order. wav_files is already
    # sorted alphabetically — for correctly-numbered filenames (01-, 02-,
    # ...) this is also numeric order.
    anchor_preset = preset_dict or {}
    if "genre_ideal_lra_lu" not in anchor_preset:
        # Fall back to defaults block if the per-genre merge didn't
        # inherit this key (depends on load_genre_presets internals).
        from tools.mastering.master_tracks import load_genre_presets
        anchor_preset = {
            **load_genre_presets().get("defaults", {}),
            **anchor_preset,
        }

    anchor_result = select_anchor(
        analysis_results,
        anchor_preset,
        override_index=anchor_override,
    )

    # Phase 2 records the result but does not yet re-order the mastering
    # loop — coherence correction lands in a later phase.
    stages["anchor_selection"] = {
        "status": "pass" if anchor_result["selected_index"] is not None else "warn",
        "selected_index": anchor_result["selected_index"],
        "method": anchor_result["method"],
        "override_index": anchor_result["override_index"],
        "override_reason": anchor_result["override_reason"],
        "scores": anchor_result["scores"],
    }
    if anchor_result["selected_index"] is None:
        warnings.append(
            "Anchor selector: no eligible tracks (signature metrics missing). "
            "Mastering proceeds without an anchor; coherence correction disabled."
        )
```

- [ ] **Step 4: Run the new test to verify it passes**

```bash
~/.bitwize-music/venv/bin/python -m pytest \
    tests/unit/mastering/test_master_album_config_wiring.py -v
```
Expected: all PASS.

- [ ] **Step 5: Run the broader mastering test suite to verify no regression**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/unit/mastering/ -v
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py tests/unit/mastering/test_master_album_config_wiring.py
git commit -m "$(cat <<'EOF'
feat: integrate anchor selector into master_album pipeline (#290 phase 2)

After Stage 2 (Analysis), master_album now runs the anchor selector
and records its choice in stages["anchor_selection"]. Honors the
optional anchor_track README frontmatter override.

The mastering loop itself is unchanged — this phase ships the selector
as metadata. Coherence correction (which will use the anchor) lands
in the next phase.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: End-to-end verification + PR prep

**Files:**
- None (validation + PR).

- [ ] **Step 1: Run the full plugin test suite via the helper**

```bash
~/.bitwize-music/venv/bin/python -m pytest tests/ -v --tb=short 2>&1 | tail -60
```
Expected: no failures. If anything outside `tests/unit/mastering/` or `tests/unit/state/` fails, investigate — a handler import change may have broken something.

- [ ] **Step 2: Run the plugin integrity test suite**

The bitwize-music `test` skill lives at `{plugin_root}/skills/test/SKILL.md` and runs structural checks (YAML schemas, skill registration, template validity). Invoke it:

```
/bitwize-music:test all
```

Expected: all categories green. Fix any failure before opening the PR.

- [ ] **Step 3: Smoke-test master_album on a real album**

If a local album exists with polished WAVs, run:

```bash
~/.bitwize-music/venv/bin/python -c "
import asyncio, json
import sys
sys.path.insert(0, '.')
from servers.bitwize_music_server.handlers.processing.audio import master_album

data = json.loads(asyncio.run(master_album(album_slug='<local-album>', genre='<genre>')))
print(json.dumps(data['stages'].get('anchor_selection', {}), indent=2))
"
```

(Adjust the import path — the hyphenated server directory name requires `importlib` in the actual codebase. Copy the pattern from an existing smoke-test script.)

Expected: anchor_selection stage reports a plausible selected_index, method, and non-empty scores. Skip this step if no local album is available.

- [ ] **Step 4: Update the issue #290 checklist**

Check off these lines in `gh issue view 290`:

```
- [x] Add anchor selector (composite scoring + `anchor_track` README frontmatter override)
  - [x] Extract shared `build_effective_preset` helper in `tools/mastering/config.py` to deduplicate target resolution between `master_audio` and `master_album` (carried forward from #304 review item D1)
```

The parent checklist line stays unchecked until signature persistence (the sibling bullet) also lands. Post a comment on #290 noting phase 2 shipped:

```bash
gh issue comment 290 --body "$(cat <<'EOF'
Phase 2 (anchor selector) landed in PR #<NN>:
- `build_effective_preset` helper consolidates the duplicated preset construction block (D1 refactor item).
- `anchor_track` frontmatter field surfaces through `parse_album_readme` → state cache → mastering pipeline.
- `tools/mastering/anchor_selector.py` ships composite scoring + override + tie-breaker.
- `master_album` records the selected anchor in `stages["anchor_selection"]`. Coherence correction (which will consume the anchor) comes in phase 3.
EOF
)"
```

(Run after the PR merges; fill in the PR number.)

- [ ] **Step 5: Open the PR**

```bash
gh pr create --base develop --title "feat: anchor selector for album mastering (#290 phase 2)" --body "$(cat <<'EOF'
## Summary

- Extracts shared `build_effective_preset` helper (#304 review item D1) — eliminates ~30 duplicated lines between `master_audio` and `master_album`.
- Adds `tools/mastering/anchor_selector.py` — composite scoring (mix_quality + representativeness − ceiling_penalty), README frontmatter override, deterministic tie-breaker.
- Surfaces `anchor_track` frontmatter field through `parse_album_readme` → state cache → `master_album`.
- Adds `genre_ideal_lra_lu` and `spectral_reference_energy` to `defaults:` in `genre-presets.yaml`.
- Records the selected anchor in `stages["anchor_selection"]`. No change to mastering-loop behavior yet — that comes with coherence correction in phase 3.

Part of #290.

## Test plan

- [x] `pytest tests/unit/mastering/test_build_effective_preset.py` — new helper.
- [x] `pytest tests/unit/mastering/test_anchor_selector.py` — scoring, override, tie-breaker.
- [x] `pytest tests/unit/state/test_parsers.py` — anchor_track frontmatter extraction.
- [x] `pytest tests/unit/mastering/test_master_album_config_wiring.py` — anchor_selection stage integration.
- [x] `pytest tests/` — no regressions.
- [x] `/bitwize-music:test all` — plugin integrity checks.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR opens against `develop`. Return the URL.

---

## Self-Review

**Spec coverage (against issue #290):**
- ✅ Composite scoring formula — Task 5 (spectral) + Task 6 (components) + Task 7 (composite).
- ✅ `anchor_track` README override — Task 3 + Task 7.
- ✅ Deterministic tie-breaker — Task 7, `TestSelectAnchorTieBreaker`.
- ✅ `genre_ideal_lra_lu` + `spectral_reference_energy` — Task 4.
- ✅ D1 carried-forward refactor — Task 1 + Task 2.
- ❌ Frozen-signature mode — **deferred to phase 3 (signature persistence)**; correct scope boundary.
- ❌ `--freeze-signature` / `--new-anchor` CLI flags — **deferred**; the MCP pipeline has no CLI and the flags only make sense once ALBUM_SIGNATURE.yaml exists.
- ❌ Running the mastering loop anchor-first + coherence-correcting others — **deferred to phase 3**; selecting the anchor is phase 2's deliverable.

**Placeholder scan:** no "TBD", "implement later", or "handle edge cases" without concrete code. Every code step contains the actual code. Every command contains the actual command + expected output. The one conditional step (Task 4 Step 3, "if load_genre_presets merges per-key") has an explicit fallback captured in the Task 8 integration code (falls back to `defaults:` block directly), so it is not a placeholder — it is a documented branching decision.

**Type consistency:**
- `select_anchor(tracks, preset, override_index=None)` — signature reused across Tasks 7 and 8.
- `_spectral_match_score`, `_mix_quality_score`, `_representativeness_score`, `_ceiling_penalty_score`, `_album_medians` — all underscore-prefixed private helpers.
- `SIGNATURE_KEYS` tuple used consistently in `_album_medians`, `_is_eligible`, `_representativeness_score`.
- Result dict shape from `select_anchor` matches test assertions in Task 7 and the consumer in Task 8.
- `anchor_track` frontmatter parsed as `int | None` in parsers.py, consumed as `int | None` in the handler — consistent.

No gaps, no placeholders, types are consistent.
