# Coherence-Correct Clamp Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the coherence tilt-EQ clamp as a preset key, downgrade stage severity when remaining outliers are all clamp-bound (benign ceiling hit), and surface per-track diagnostics on the intended tilt, limiting metric, and spectral delta.

**Architecture:** Three additive changes, all contained to the album-mastering subsystem. (1) New `coherence_tilt_max_db` preset key (default 0.5 — behavior unchanged); (2) `_compute_tilt_db` returns a richer tuple threaded through `build_correction_plan` into per-track correction entries; (3) `_stage_coherence_correct` classifies remaining outliers and emits `status: "pass"` + `advisories` when all are clamp-bound, skipping the `ctx.warnings` append. No change to the correction algorithm, iteration cap, or fixed-point detection.

**Tech Stack:** Python 3, pytest, numpy. Existing mastering pipeline in `tools/mastering/` and `servers/bitwize-music-server/handlers/processing/`.

**Spec:** [`docs/superpowers/specs/2026-04-18-coherence-correct-clamp-telemetry-design.md`](../specs/2026-04-18-coherence-correct-clamp-telemetry-design.md)

**Canonical issue:** [#334](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/334)

---

## File Structure

Files touched by this plan:

| File | Role |
|---|---|
| `tools/mastering/coherence.py` | Add `coherence_tilt_max_db` to `DEFAULTS` + `load_tolerances` merge list; expand `_compute_tilt_db` return tuple; thread `max_tilt_db` through `build_correction_plan`; add `intended_tilt_db`/`limiting_metric`/`spectral_delta_db` to plan entries |
| `tools/mastering/master_tracks.py` | Add `coherence_tilt_max_db: 0.5` to `_PRESET_DEFAULTS` |
| `servers/bitwize-music-server/handlers/processing/_album_stages.py` | Pass `max_tilt_db` from tolerances into plan builder (both `_stage_coherence_check` and `_stage_coherence_correct`); thread new diagnostic fields into the unconvergent correction dict; classify remaining outliers as clamp-bound vs. drift-bound; emit `advisories` + downgrade status accordingly |
| `tests/unit/mastering/test_coherence.py` | Unit tests for the expanded `_compute_tilt_db` return shape + `build_correction_plan` threading |
| `tests/unit/mastering/test_coherence_presets.py` | Assert `coherence_tilt_max_db` is present in merged presets |
| `tests/unit/mastering/test_master_album_coherence_stages.py` | Stage-level tests: preset override, severity downgrade, advisories, diagnostic fields on unconvergent entries |

No new files. No dependency changes.

---

## Task 1: Add `coherence_tilt_max_db` preset key

**Files:**
- Modify: `tools/mastering/coherence.py` (`DEFAULTS` dict + `load_tolerances`)
- Modify: `tools/mastering/master_tracks.py` (`_PRESET_DEFAULTS` dict)
- Test: `tests/unit/mastering/test_coherence.py` (existing `TestLoadTolerances` class)
- Test: `tests/unit/mastering/test_coherence_presets.py` (existing `COHERENCE_FIELDS` dict)

- [ ] **Step 1: Write failing test for `load_tolerances`**

Append this test method inside `class TestLoadTolerances` in `tests/unit/mastering/test_coherence.py` (after `test_lufs_tolerance_not_overridable_from_preset`):

```python
    def test_coherence_tilt_max_db_defaults_to_half_db(self):
        tolerances = load_tolerances(None)
        assert tolerances["coherence_tilt_max_db"] == pytest.approx(0.5)

    def test_coherence_tilt_max_db_overridable_from_preset(self):
        tolerances = load_tolerances({"coherence_tilt_max_db": 0.75})
        assert tolerances["coherence_tilt_max_db"] == pytest.approx(0.75)
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/unit/mastering/test_coherence.py::TestLoadTolerances -v`
Expected: FAIL — `KeyError: 'coherence_tilt_max_db'` on both new tests.

- [ ] **Step 3: Add the key to `DEFAULTS` and merge list**

Edit `tools/mastering/coherence.py`. Replace the `DEFAULTS` dict (lines 23–30) with:

```python
DEFAULTS: dict[str, float] = {
    "coherence_stl_95_lu":    0.5,
    "coherence_lra_floor_lu": 1.0,
    "coherence_low_rms_db":   2.0,
    "coherence_vocal_rms_db": 2.0,
    "coherence_tilt_max_db":  0.5,
    # Hardcoded — matches master_album Stage 5 verify spec. Not a preset field.
    "lufs_tolerance_lu":      0.5,
}
```

Then update `load_tolerances` — add `"coherence_tilt_max_db"` to the merge tuple (lines 41–46):

```python
    out = dict(DEFAULTS)
    if preset:
        for key in (
            "coherence_stl_95_lu",
            "coherence_lra_floor_lu",
            "coherence_low_rms_db",
            "coherence_vocal_rms_db",
            "coherence_tilt_max_db",
        ):
            if key in preset and preset[key] is not None:
                out[key] = float(preset[key])
    return out
```

- [ ] **Step 4: Run the tolerance tests — they pass**

Run: `pytest tests/unit/mastering/test_coherence.py::TestLoadTolerances -v`
Expected: PASS (all 6 tests).

- [ ] **Step 5: Write failing test for preset merge in master_tracks**

Edit `tests/unit/mastering/test_coherence_presets.py`. Update the `COHERENCE_FIELDS` dict (lines 16–21) to include the new key:

```python
COHERENCE_FIELDS = {
    "coherence_stl_95_lu":    0.5,
    "coherence_lra_floor_lu": 1.0,
    "coherence_low_rms_db":   2.0,
    "coherence_vocal_rms_db": 2.0,
    "coherence_tilt_max_db":  0.5,
}
```

- [ ] **Step 6: Run failing preset test**

Run: `pytest tests/unit/mastering/test_coherence_presets.py -v`
Expected: FAIL — `coherence_tilt_max_db missing from merged pop preset` (the key isn't in `_PRESET_DEFAULTS` yet, so `load_genre_presets` doesn't put it in merged presets).

- [ ] **Step 7: Add key to `_PRESET_DEFAULTS`**

Edit `tools/mastering/master_tracks.py`. Find the coherence tolerance block (lines 140–145) and add the new key:

```python
    # Album-mastering coherence tolerance bands (issue #290 phase 3b —
    # consumed by tools/mastering/coherence.py via load_tolerances()).
    'coherence_stl_95_lu': 0.5,
    'coherence_lra_floor_lu': 1.0,
    'coherence_low_rms_db': 2.0,
    'coherence_vocal_rms_db': 2.0,
    'coherence_tilt_max_db': 0.5,
```

- [ ] **Step 8: Run preset test — passes**

Run: `pytest tests/unit/mastering/test_coherence_presets.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add tools/mastering/coherence.py tools/mastering/master_tracks.py \
        tests/unit/mastering/test_coherence.py tests/unit/mastering/test_coherence_presets.py
git commit -m "feat: coherence_tilt_max_db preset key (#334)

Adds the tilt-EQ clamp as a configurable preset (default 0.5, unchanged)
so genres with strong spectral character can widen it without patching
tools/mastering/coherence.py. Consumed in later changes; this commit
is structural only — defaults match the hardcoded TILT_CORRECTION_MAX_DB."
```

---

## Task 2: Expand `_compute_tilt_db` return tuple

**Files:**
- Modify: `tools/mastering/coherence.py` (`_compute_tilt_db` signature + body, lines 180–225)
- Test: `tests/unit/mastering/test_coherence.py` (new `TestComputeTiltDb` class)

Design note — the expanded tuple is `(clamped_tilt_db, was_clamped, raw_tilt_db, limiting_metric, delta_db)`:
- `limiting_metric` is `"low_rms_db"` or `"vocal_rms_db"` (whichever branch produced the tilt), or `None` when no spectral outlier drives the result.
- `delta_db` is the signed spectral delta on that metric (for `low_rms`: the anchor-relative delta; for `vocal_rms`: the anchor-relative delta — unnegated, so the tilt sign flip still happens inside `_compute_tilt_db`).

- [ ] **Step 1: Write failing tests for the expanded return tuple**

Add this class to `tests/unit/mastering/test_coherence.py` (at end of file):

```python
class TestComputeTiltDb:
    """#334: _compute_tilt_db returns (tilt, clamped, raw, limiting_metric, delta)."""

    def _violations_low_rms(self, delta: float) -> list[dict]:
        return [
            {"metric": "lufs",      "delta": 0.0, "tolerance": 0.5,
             "severity": "ok",      "correctable": False},
            {"metric": "stl_95",    "delta": 0.0, "tolerance": 0.5,
             "severity": "ok",      "correctable": False},
            {"metric": "lra_floor", "value": 3.0, "floor": 1.0,
             "severity": "ok",      "correctable": False},
            {"metric": "low_rms",   "delta": delta, "tolerance": 2.0,
             "severity": "outlier", "correctable": True},
            {"metric": "vocal_rms", "delta": 0.0, "tolerance": 2.0,
             "severity": "ok",      "correctable": False},
        ]

    def _violations_vocal_rms(self, delta: float) -> list[dict]:
        v = self._violations_low_rms(0.0)
        v[3]["severity"] = "ok"
        v[4] = {"metric": "vocal_rms", "delta": delta, "tolerance": 2.0,
                "severity": "outlier", "correctable": True}
        return v

    def test_low_rms_clamped_returns_full_tuple(self):
        from tools.mastering.coherence import _compute_tilt_db
        tilt, clamped, raw, metric, delta = _compute_tilt_db(self._violations_low_rms(3.0))
        assert tilt == pytest.approx(0.5)
        assert clamped is True
        assert raw == pytest.approx(3.0)
        assert metric == "low_rms_db"
        assert delta == pytest.approx(3.0)

    def test_low_rms_within_clamp_reports_raw_equals_applied(self):
        from tools.mastering.coherence import _compute_tilt_db
        # Force severity=outlier via tolerance tweak so the spectral path fires.
        violations = self._violations_low_rms(0.3)
        violations[3]["tolerance"] = 0.1
        tilt, clamped, raw, metric, delta = _compute_tilt_db(violations)
        assert tilt == pytest.approx(0.3, abs=1e-9)
        assert clamped is False
        assert raw == pytest.approx(0.3, abs=1e-9)
        assert metric == "low_rms_db"
        assert delta == pytest.approx(0.3, abs=1e-9)

    def test_vocal_rms_inverts_sign_and_reports_metric(self):
        from tools.mastering.coherence import _compute_tilt_db
        # vocal_rms delta=+2.0 → raw tilt = -2.0 (sign inverted), clamped at -0.5.
        tilt, clamped, raw, metric, delta = _compute_tilt_db(self._violations_vocal_rms(2.0))
        assert tilt == pytest.approx(-0.5)
        assert clamped is True
        assert raw == pytest.approx(-2.0)
        assert metric == "vocal_rms_db"
        assert delta == pytest.approx(2.0)  # un-inverted signed delta

    def test_no_spectral_violation_returns_zeros_and_none(self):
        from tools.mastering.coherence import _compute_tilt_db
        violations = [
            {"metric": "lufs",     "delta": 0.0, "tolerance": 0.5,
             "severity": "ok",     "correctable": False},
            {"metric": "low_rms",  "delta": 0.0, "tolerance": 2.0,
             "severity": "ok",     "correctable": False},
            {"metric": "vocal_rms","delta": 0.0, "tolerance": 2.0,
             "severity": "ok",     "correctable": False},
        ]
        tilt, clamped, raw, metric, delta = _compute_tilt_db(violations)
        assert tilt == 0.0
        assert clamped is False
        assert raw == 0.0
        assert metric is None
        assert delta is None

    def test_max_tilt_db_override_widens_clamp(self):
        from tools.mastering.coherence import _compute_tilt_db
        tilt, clamped, raw, metric, delta = _compute_tilt_db(
            self._violations_low_rms(0.6), max_tilt_db=0.75
        )
        assert tilt == pytest.approx(0.6)
        assert clamped is False  # 0.6 < 0.75
        assert raw == pytest.approx(0.6)
        assert metric == "low_rms_db"

    def test_max_tilt_db_override_still_clamps_at_new_ceiling(self):
        from tools.mastering.coherence import _compute_tilt_db
        tilt, clamped, raw, _, _ = _compute_tilt_db(
            self._violations_low_rms(1.2), max_tilt_db=0.75
        )
        assert tilt == pytest.approx(0.75)
        assert clamped is True
        assert raw == pytest.approx(1.2)
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/unit/mastering/test_coherence.py::TestComputeTiltDb -v`
Expected: FAIL — `ValueError: not enough values to unpack (expected 5, got 2)` on every test.

- [ ] **Step 3: Expand `_compute_tilt_db` signature and body**

Edit `tools/mastering/coherence.py`. Replace the function (lines 180–225) with:

```python
def _compute_tilt_db(
    violations: list[dict[str, Any]],
    max_tilt_db: float = TILT_CORRECTION_MAX_DB,
) -> tuple[float, bool, float, str | None, float | None]:
    """Derive a bounded tilt-EQ correction from spectral violations.

    Returns ``(tilt_db, clamped, raw_tilt_db, limiting_metric, delta_db)``.
    ``clamped`` is True when the raw tilt exceeded ``max_tilt_db`` and was
    capped — the stage-level coherence loop uses this to detect
    structurally unconvergent corrections (tilt can't close the gap
    regardless of how many iterations run).

    ``limiting_metric`` identifies which spectral band drove the tilt
    request (``"low_rms_db"`` or ``"vocal_rms_db"``); ``delta_db`` is the
    signed anchor-relative delta on that metric. Both are ``None`` when
    no spectral outlier fires.

    ``max_tilt_db`` is loaded from the ``coherence_tilt_max_db`` preset
    (default 0.5). Callers that don't pass it fall back to the module
    constant for backward compatibility.

    Tilt sign convention (matches ``master_tracks.apply_tilt_eq``):
      - positive tilt → cut lows, boost highs (brighter)
      - negative tilt → boost lows, cut highs (warmer)

    ``delta_low_rms`` is the primary signal (#290 calls low-end RMS the
    #1 inter-track variance source). A track with too much bass has
    ``delta_low_rms > 0`` and wants positive tilt (cut bass). Vocal-RMS
    is used as a fallback when low-RMS is clean; since the vocal band
    (1-4 kHz) sits above the 650 Hz pivot, its sign is inverted.
    """
    low = next(
        (v for v in violations
         if v["metric"] == "low_rms" and v["severity"] == "outlier"),
        None,
    )
    if low is not None and low.get("delta") is not None:
        delta = float(low["delta"])
        raw = delta
        clamped = abs(raw) > max_tilt_db
        return (
            max(-max_tilt_db, min(max_tilt_db, raw)),
            clamped,
            raw,
            "low_rms_db",
            delta,
        )

    vocal = next(
        (v for v in violations
         if v["metric"] == "vocal_rms" and v["severity"] == "outlier"),
        None,
    )
    if vocal is not None and vocal.get("delta") is not None:
        delta = float(vocal["delta"])
        raw = -delta
        clamped = abs(raw) > max_tilt_db
        return (
            max(-max_tilt_db, min(max_tilt_db, raw)),
            clamped,
            raw,
            "vocal_rms_db",
            delta,
        )

    return 0.0, False, 0.0, None, None
```

- [ ] **Step 4: Run the tests — they pass**

Run: `pytest tests/unit/mastering/test_coherence.py::TestComputeTiltDb -v`
Expected: PASS (all 6 tests).

- [ ] **Step 5: Update `build_correction_plan` call site for the new tuple shape**

`build_correction_plan` currently unpacks 2 values at line 294: `tilt_db, tilt_clamped = _compute_tilt_db(violations)`. This will break now. Edit `tools/mastering/coherence.py`, replace line 294:

```python
        tilt_db = 0.0
        tilt_clamped = False
        if spectral_violations:
            tilt_db, tilt_clamped, _raw, _metric, _delta = _compute_tilt_db(violations)
```

(The underscored locals are intentional — Task 3 will replace them with real fields in the entry. Keeping the discard here keeps Task 2 as a minimal shape-only change.)

- [ ] **Step 6: Run the full `test_coherence.py` file to confirm nothing regressed**

Run: `pytest tests/unit/mastering/test_coherence.py -v`
Expected: PASS (all tests, including pre-existing `TestTiltClampedFlag`).

- [ ] **Step 7: Commit**

```bash
git add tools/mastering/coherence.py tests/unit/mastering/test_coherence.py
git commit -m "feat: expand _compute_tilt_db return tuple (#334)

Returns (tilt_db, clamped, raw_tilt_db, limiting_metric, delta_db) so
downstream can report what the tilt correction was trying to fix and
how far outside the clamp the track actually was. Accepts max_tilt_db
override (defaults to TILT_CORRECTION_MAX_DB). build_correction_plan
updated to the new shape; new fields are discarded pending #334 task 3."
```

---

## Task 3: Expose `intended_tilt_db` / `limiting_metric` / `spectral_delta_db` on plan entries

**Files:**
- Modify: `tools/mastering/coherence.py` (`build_correction_plan` signature + entry construction, lines 228–342)
- Test: `tests/unit/mastering/test_coherence.py` (new `TestBuildCorrectionPlanDiagnostics` class)

- [ ] **Step 1: Write failing diagnostic test**

Add this class to `tests/unit/mastering/test_coherence.py` (at end of file):

```python
class TestBuildCorrectionPlanDiagnostics:
    """#334: plan entries expose intended_tilt_db, limiting_metric, spectral_delta_db."""

    def _classifications(self, low_rms_delta: float) -> list[dict]:
        return [
            {"index": 1, "filename": "01.wav", "is_anchor": True,
             "is_outlier": False, "violations": []},
            {"index": 2, "filename": "02.wav", "is_anchor": False,
             "is_outlier": True, "violations": [
                {"metric": "lufs",      "delta": 0.0, "tolerance": 0.5,
                 "severity": "ok",      "correctable": False},
                {"metric": "stl_95",    "delta": 0.0, "tolerance": 0.5,
                 "severity": "ok",      "correctable": False},
                {"metric": "lra_floor", "value": 3.0, "floor": 1.0,
                 "severity": "ok",      "correctable": False},
                {"metric": "low_rms",   "delta": low_rms_delta, "tolerance": 2.0,
                 "severity": "outlier", "correctable": True},
                {"metric": "vocal_rms", "delta": 0.0, "tolerance": 2.0,
                 "severity": "ok",      "correctable": False},
             ]},
        ]

    def test_clamped_entry_reports_intended_and_limiting(self):
        classifications = self._classifications(3.0)
        analyses = [
            _analysis(filename="01.wav", lufs=-14.0),
            _analysis(filename="02.wav", lufs=-14.0),
        ]
        plan = build_correction_plan(classifications, analyses, anchor_index_1based=1)
        entry = plan["corrections"][0]
        assert entry["corrected_tilt_db"] == pytest.approx(0.5)
        assert entry["tilt_clamped"] is True
        assert entry["intended_tilt_db"] == pytest.approx(3.0)
        assert entry["limiting_metric"] == "low_rms_db"
        assert entry["spectral_delta_db"] == pytest.approx(3.0)

    def test_unclamped_entry_still_reports_diagnostics(self):
        classifications = self._classifications(0.3)
        # Force outlier severity so spectral path fires below default tolerance.
        classifications[1]["violations"][3]["tolerance"] = 0.1
        analyses = [
            _analysis(filename="01.wav", lufs=-14.0),
            _analysis(filename="02.wav", lufs=-14.0),
        ]
        plan = build_correction_plan(classifications, analyses, anchor_index_1based=1)
        entry = plan["corrections"][0]
        assert entry["intended_tilt_db"] == pytest.approx(0.3, abs=1e-9)
        assert entry["limiting_metric"] == "low_rms_db"
        assert entry["spectral_delta_db"] == pytest.approx(0.3, abs=1e-9)

    def test_max_tilt_db_kwarg_widens_the_clamp(self):
        classifications = self._classifications(0.6)
        analyses = [
            _analysis(filename="01.wav", lufs=-14.0),
            _analysis(filename="02.wav", lufs=-14.0),
        ]
        plan = build_correction_plan(
            classifications, analyses, anchor_index_1based=1, max_tilt_db=0.75
        )
        entry = plan["corrections"][0]
        assert entry["corrected_tilt_db"] == pytest.approx(0.6)
        assert entry["tilt_clamped"] is False
        assert entry["intended_tilt_db"] == pytest.approx(0.6)

    def test_lufs_only_entry_omits_spectral_diagnostics(self):
        # LUFS outlier, no spectral violation → no tilt fields at all.
        classifications = [
            {"index": 1, "filename": "01.wav", "is_anchor": True,
             "is_outlier": False, "violations": []},
            {"index": 2, "filename": "02.wav", "is_anchor": False,
             "is_outlier": True, "violations": [
                {"metric": "lufs",     "delta": 1.0, "tolerance": 0.5,
                 "severity": "outlier", "correctable": True},
                {"metric": "low_rms",  "delta": 0.0, "tolerance": 2.0,
                 "severity": "ok",      "correctable": False},
                {"metric": "vocal_rms","delta": 0.0, "tolerance": 2.0,
                 "severity": "ok",      "correctable": False},
             ]},
        ]
        analyses = [
            _analysis(filename="01.wav", lufs=-14.0),
            _analysis(filename="02.wav", lufs=-15.0),
        ]
        plan = build_correction_plan(classifications, analyses, anchor_index_1based=1)
        entry = plan["corrections"][0]
        assert entry["correctable"] is True
        assert "corrected_target_lufs" in entry
        assert "intended_tilt_db" not in entry
        assert "limiting_metric" not in entry
        assert "spectral_delta_db" not in entry
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/unit/mastering/test_coherence.py::TestBuildCorrectionPlanDiagnostics -v`
Expected: FAIL — `KeyError: 'intended_tilt_db'` on the first three; the fourth passes incidentally.

- [ ] **Step 3: Add `max_tilt_db` kwarg + populate diagnostic fields**

Edit `tools/mastering/coherence.py`. Update the `build_correction_plan` signature (line 228) and body. Replace lines 228–342 with:

```python
def build_correction_plan(
    classifications: list[dict[str, Any]],
    analysis_results: list[dict[str, Any]],
    anchor_index_1based: int,
    max_tilt_db: float | None = None,
) -> dict[str, Any]:
    """Build a per-track correction plan for LUFS + spectral outliers.

    Args:
        classifications: Output of ``classify_outliers``.
        analysis_results: Original ``analyze_track`` dicts (used for
            anchor LUFS lookup).
        anchor_index_1based: 1-based track number of the anchor.
        max_tilt_db: Clamp magnitude for tilt-EQ corrections. ``None``
            falls back to ``TILT_CORRECTION_MAX_DB`` (0.5) so direct
            callers keep working without threading the preset through.

    Returns:
        Dict with:
          anchor_index: 1-based anchor index
          anchor_lufs:  measured LUFS of the anchor (ground truth)
          corrections:  list of per-track correction dicts. Each dict
                        has ``correctable``, ``corrected_target_lufs``
                        (present when gain correction applies),
                        ``corrected_tilt_db`` (non-zero when spectral
                        correction applies, clamped to ±max_tilt_db),
                        and — when a spectral violation fires —
                        ``intended_tilt_db`` (pre-clamp raw tilt),
                        ``limiting_metric`` (``"low_rms_db"`` or
                        ``"vocal_rms_db"``), and ``spectral_delta_db``
                        (signed anchor-relative delta).
          skipped:      list of {index, filename, reason} for the
                        anchor + clean tracks
    """
    if not (1 <= anchor_index_1based <= len(analysis_results)):
        raise ValueError(
            f"anchor_index_1based={anchor_index_1based} out of range "
            f"[1, {len(analysis_results)}]"
        )

    effective_max_tilt = (
        TILT_CORRECTION_MAX_DB if max_tilt_db is None else float(max_tilt_db)
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

        violations = cls["violations"]
        lufs_violation = next(
            (v for v in violations
             if v["metric"] == "lufs" and v["severity"] == "outlier"),
            None,
        )
        spectral_violations = [
            v for v in violations
            if v["metric"] in ("low_rms", "vocal_rms")
            and v["severity"] == "outlier"
        ]
        uncorrectable_outliers = [
            v for v in violations
            if v["metric"] in ("stl_95", "lra_floor")
            and v["severity"] == "outlier"
        ]

        tilt_db = 0.0
        tilt_clamped = False
        raw_tilt_db = 0.0
        limiting_metric: str | None = None
        spectral_delta: float | None = None
        if spectral_violations:
            (
                tilt_db,
                tilt_clamped,
                raw_tilt_db,
                limiting_metric,
                spectral_delta,
            ) = _compute_tilt_db(violations, max_tilt_db=effective_max_tilt)

        if lufs_violation is not None or spectral_violations:
            reason_parts: list[str] = []
            entry: dict[str, Any] = {
                "index":        cls["index"],
                "filename":     cls.get("filename"),
                "correctable":  True,
                "tilt_clamped": tilt_clamped,
            }
            if lufs_violation is not None:
                entry["corrected_target_lufs"] = anchor_lufs
                reason_parts.append(
                    f"LUFS outlier: delta={lufs_violation['delta']:+.2f}, "
                    f"tolerance=±{lufs_violation['tolerance']:.2f}"
                )
            if spectral_violations:
                entry["corrected_tilt_db"] = tilt_db
                entry["intended_tilt_db"] = raw_tilt_db
                entry["limiting_metric"] = limiting_metric
                entry["spectral_delta_db"] = spectral_delta
                metrics = ", ".join(sorted({v["metric"] for v in spectral_violations}))
                clamp_note = " (clamped)" if tilt_clamped else ""
                reason_parts.append(
                    f"Spectral outlier ({metrics}) → tilt_db={tilt_db:+.2f}{clamp_note}"
                )
            entry["reason"] = "; ".join(reason_parts)
            corrections.append(entry)
        elif uncorrectable_outliers:
            metrics = ", ".join(sorted({v["metric"] for v in uncorrectable_outliers}))
            corrections.append({
                "index":       cls["index"],
                "filename":    cls.get("filename"),
                "correctable": False,
                "reason": (
                    f"Only uncorrectable violations ({metrics}) — "
                    f"requires per-track compression changes."
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

- [ ] **Step 4: Run the tests — they pass**

Run: `pytest tests/unit/mastering/test_coherence.py -v`
Expected: PASS (all tests, including the new diagnostics class and the pre-existing `TestTiltClampedFlag`).

- [ ] **Step 5: Commit**

```bash
git add tools/mastering/coherence.py tests/unit/mastering/test_coherence.py
git commit -m "feat: expose tilt-correction diagnostics on plan entries (#334)

build_correction_plan now surfaces intended_tilt_db (pre-clamp raw
value), limiting_metric (low_rms_db | vocal_rms_db), and
spectral_delta_db on correction entries when a spectral violation
fired. Adds max_tilt_db kwarg (falls back to TILT_CORRECTION_MAX_DB
constant) so callers can thread the preset through. No behavior
change for existing callers — all new fields are additive and the
kwarg defaults preserve the previous clamp."
```

---

## Task 4: Thread preset clamp + diagnostics through `_stage_coherence_correct`

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/_album_stages.py` (lines 979, 1027–1074)
- Test: `tests/unit/mastering/test_master_album_coherence_stages.py` (new diagnostic-fields test)

- [ ] **Step 1: Write failing test — unconvergent entry exposes diagnostic fields**

Open `tests/unit/mastering/test_master_album_coherence_stages.py` and find the existing `test_coherence_correct_breaks_on_fixed_point_with_tilt_clamp` function (around line 511). Add a new test immediately after it:

```python
def test_coherence_correct_unconvergent_entry_exposes_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#334: unconvergent entries (fixed_point_tilt_clamp) must include
    intended_tilt_db, limiting_metric, and spectral_delta_db so operators
    can see what the corrector was trying to fix and how far outside the
    clamp the track was."""
    anchor_lufs = -14.0
    source_dir = tmp_path / "polished"
    source_dir.mkdir()
    output_dir = tmp_path / "mastered"
    output_dir.mkdir()
    _write_sine_wav(source_dir / "02-bassy.wav", amplitude=0.2)
    import shutil
    shutil.copy(source_dir / "02-bassy.wav", output_dir / "02-bassy.wav")
    _write_sine_wav(output_dir / "01-anchor.wav")

    def _fake_master_track(src: str, dst: str, **kwargs) -> dict:
        shutil.copy(src, dst)
        return {"status": "ok"}

    import tools.mastering.master_tracks as _mt_mod
    monkeypatch.setattr(_mt_mod, "master_track", _fake_master_track)

    def _fake_plan(classifications, analysis_results, anchor_index_1based, max_tilt_db=None):
        return {
            "anchor_index": anchor_index_1based,
            "anchor_lufs": anchor_lufs,
            "corrections": [
                {
                    "index": 2,
                    "filename": "02-bassy.wav",
                    "correctable": True,
                    "corrected_tilt_db": 0.5,
                    "tilt_clamped": True,
                    "intended_tilt_db": 0.78,
                    "limiting_metric": "low_rms_db",
                    "spectral_delta_db": 0.78,
                    "reason": "Spectral outlier (low_rms) → tilt_db=+0.50 (clamped)",
                }
            ],
            "skipped": [{"index": 1, "filename": "01-anchor.wav", "reason": "is_anchor"}],
        }

    monkeypatch.setattr(album_stages_mod, "_coherence_build_plan", _fake_plan)

    verify_results = [
        _make_verify_result("01-anchor.wav", lufs=anchor_lufs, low_rms=-20.0),
        _make_verify_result("02-bassy.wav", lufs=-14.0, low_rms=-15.0),
    ]

    def _fake_analyze(path: str) -> dict:
        name = Path(path).name
        for r in verify_results:
            if r["filename"] == name:
                return r
        return verify_results[0]

    import tools.mastering.analyze_tracks as _at_mod
    monkeypatch.setattr(_at_mod, "analyze_track", _fake_analyze)

    classifications = [
        {"index": 1, "filename": "01-anchor.wav", "is_anchor": True,
         "is_outlier": False, "violations": []},
        {"index": 2, "filename": "02-bassy.wav", "is_anchor": False,
         "is_outlier": True, "violations": [
            {"metric": "low_rms", "delta": 5.0, "tolerance": 2.0,
             "severity": "outlier", "correctable": True},
         ]},
    ]

    import asyncio
    async def _run():
        ctx = MasterAlbumCtx(
            album_slug="test-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_running_loop(),
        )
        ctx.anchor_result = {"selected_index": 1}
        ctx.verify_results = verify_results
        ctx.coherence_classifications = classifications
        ctx.source_dir = source_dir
        ctx.output_dir = output_dir
        ctx.mastered_files = [
            output_dir / "01-anchor.wav",
            output_dir / "02-bassy.wav",
        ]
        ctx.effective_ceiling = -1.0
        ctx.effective_compress = 1.0
        ctx.effective_preset = {}
        ctx.preset_dict = None
        await _stage_coherence_correct(ctx)
        return ctx

    ctx = asyncio.run(_run())

    corrections = ctx.stages["coherence_correct"]["corrections"]
    unconvergent = [c for c in corrections if c["status"] == "unconvergent"]
    assert len(unconvergent) == 1, f"expected one unconvergent entry, got {corrections}"
    entry = unconvergent[0]
    assert entry["reason"] == "fixed_point_tilt_clamp"
    assert entry["intended_tilt_db"] == pytest.approx(0.78)
    assert entry["limiting_metric"] == "low_rms_db"
    assert entry["spectral_delta_db"] == pytest.approx(0.78)
```

Note: this test re-uses `MasterAlbumCtx`, `_write_sine_wav`, `_make_verify_result`, `_stage_coherence_correct`, and `album_stages_mod` — all of which are already imported or defined at the top of the file (check the existing `test_coherence_correct_breaks_on_fixed_point_with_tilt_clamp` function for the exact pattern). Don't add new fixtures.

- [ ] **Step 2: Run the failing test**

Run: `pytest tests/unit/mastering/test_master_album_coherence_stages.py::test_coherence_correct_unconvergent_entry_exposes_diagnostics -v`
Expected: FAIL — assertion on `intended_tilt_db` fails (key missing from entry).

- [ ] **Step 3: Thread `max_tilt_db` into the plan builder and propagate new fields**

Edit `servers/bitwize-music-server/handlers/processing/_album_stages.py`.

First, find line 979 (inside `_stage_coherence_check`) and update the `build_correction_plan` call to pass the clamp:

```python
    from tools.mastering.coherence import build_correction_plan
    plan = build_correction_plan(
        classifications, ctx.verify_results,
        anchor_index_1based=anchor_idx,
        max_tilt_db=tolerances["coherence_tilt_max_db"],
    )
```

Second, find line 1044 (inside `_stage_coherence_correct`) and update the `_coherence_build_plan` call:

```python
        plan = _coherence_build_plan(
            classifications, current_verify, anchor_idx,
            max_tilt_db=tolerances["coherence_tilt_max_db"],
        )
```

Third, find the fixed-point unconvergent branch (lines 1064–1075) and expand the appended dict to include the new fields:

```python
        if plan_signature == prev_plan_signature and any_tilt_clamped:
            for entry in correctable:
                unconvergent: dict[str, Any] = {
                    "filename": entry["filename"],
                    "status": "unconvergent",
                    "reason": "fixed_point_tilt_clamp",
                    "applied_target_lufs": entry.get("corrected_target_lufs"),
                    "applied_tilt_db": entry.get("corrected_tilt_db"),
                    "tilt_clamped": entry.get("tilt_clamped", False),
                    "iteration": _iter + 1,
                }
                if "intended_tilt_db" in entry:
                    unconvergent["intended_tilt_db"] = entry["intended_tilt_db"]
                if "limiting_metric" in entry:
                    unconvergent["limiting_metric"] = entry["limiting_metric"]
                if "spectral_delta_db" in entry:
                    unconvergent["spectral_delta_db"] = entry["spectral_delta_db"]
                all_corrections.append(unconvergent)
            break
```

(Conditional inclusion keeps the fields omitted — per spec — when the plan entry didn't carry them, e.g., a LUFS-only unconvergent case in some hypothetical future flow.)

- [ ] **Step 4: Run the new test — it passes**

Run: `pytest tests/unit/mastering/test_master_album_coherence_stages.py::test_coherence_correct_unconvergent_entry_exposes_diagnostics -v`
Expected: PASS.

- [ ] **Step 5: Run the whole coherence-stage test file — no regressions**

Run: `pytest tests/unit/mastering/test_master_album_coherence_stages.py -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/_album_stages.py \
        tests/unit/mastering/test_master_album_coherence_stages.py
git commit -m "feat: propagate tilt diagnostics into unconvergent entries (#334)

_stage_coherence_correct and _stage_coherence_check now read
coherence_tilt_max_db from the preset tolerances and pass it to
build_correction_plan. Unconvergent correction entries (fixed-point
tilt clamp) carry intended_tilt_db, limiting_metric, and
spectral_delta_db through to the stage output. Fields are omitted
when the plan entry didn't carry them (additive schema)."
```

---

## Task 5: Severity downgrade + advisories when all remaining outliers are clamp-bound

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/_album_stages.py` (lines 1173–1194)
- Test: `tests/unit/mastering/test_master_album_coherence_stages.py` (two new tests)

Decision logic (from spec, section "Severity & advisories"):

| remaining | all clamp-bound | stage status | `ctx.warnings` append | `advisories` field |
|---|---|---|---|---|
| 0 | — | `pass` | no | omitted |
| >0 | yes | `pass` | no | present |
| >0 | mixed / all-drift | `warn` | yes | present |

Advisory entry shape:

```python
{"filename": str, "kind": "tilt_ceiling",
 "message": f"spectral tilt exceeded ±{max_tilt:.2f} dB clamp "
            f"(intended {intended:+.2f} dB, applied {applied:+.2f} dB)"}
```

- [ ] **Step 1: Write failing test — clamp-only downgrades to pass with advisories**

Add this test after the previous one in `tests/unit/mastering/test_master_album_coherence_stages.py`:

```python
def test_coherence_correct_all_clamp_bound_downgrades_to_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """#334: when all remaining outliers are fixed_point_tilt_clamp, the
    stage downgrades status to 'pass', populates advisories, and does
    NOT append to ctx.warnings (benign ceiling hit, not a real warning)."""
    anchor_lufs = -14.0
    source_dir = tmp_path / "polished"
    source_dir.mkdir()
    output_dir = tmp_path / "mastered"
    output_dir.mkdir()
    _write_sine_wav(source_dir / "02-bassy.wav", amplitude=0.2)
    import shutil
    shutil.copy(source_dir / "02-bassy.wav", output_dir / "02-bassy.wav")
    _write_sine_wav(output_dir / "01-anchor.wav")

    def _fake_master_track(src: str, dst: str, **kwargs) -> dict:
        shutil.copy(src, dst)
        return {"status": "ok"}

    import tools.mastering.master_tracks as _mt_mod
    monkeypatch.setattr(_mt_mod, "master_track", _fake_master_track)

    def _fake_plan(classifications, analysis_results, anchor_index_1based, max_tilt_db=None):
        return {
            "anchor_index": anchor_index_1based,
            "anchor_lufs": anchor_lufs,
            "corrections": [
                {
                    "index": 2,
                    "filename": "02-bassy.wav",
                    "correctable": True,
                    "corrected_tilt_db": 0.5,
                    "tilt_clamped": True,
                    "intended_tilt_db": 0.78,
                    "limiting_metric": "low_rms_db",
                    "spectral_delta_db": 0.78,
                    "reason": "Spectral outlier (low_rms) → tilt_db=+0.50 (clamped)",
                }
            ],
            "skipped": [{"index": 1, "filename": "01-anchor.wav", "reason": "is_anchor"}],
        }

    monkeypatch.setattr(album_stages_mod, "_coherence_build_plan", _fake_plan)

    verify_results = [
        _make_verify_result("01-anchor.wav", lufs=anchor_lufs, low_rms=-20.0),
        _make_verify_result("02-bassy.wav", lufs=-14.0, low_rms=-15.0),
    ]

    def _fake_analyze(path: str) -> dict:
        name = Path(path).name
        for r in verify_results:
            if r["filename"] == name:
                return r
        return verify_results[0]

    import tools.mastering.analyze_tracks as _at_mod
    monkeypatch.setattr(_at_mod, "analyze_track", _fake_analyze)

    # Mark track 2 as an outlier so remaining_outliers > 0.
    classifications = [
        {"index": 1, "filename": "01-anchor.wav", "is_anchor": True,
         "is_outlier": False, "violations": []},
        {"index": 2, "filename": "02-bassy.wav", "is_anchor": False,
         "is_outlier": True, "violations": [
            {"metric": "low_rms", "delta": 5.0, "tolerance": 2.0,
             "severity": "outlier", "correctable": True},
         ]},
    ]

    import asyncio
    async def _run():
        ctx = MasterAlbumCtx(
            album_slug="test-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_running_loop(),
        )
        ctx.anchor_result = {"selected_index": 1}
        ctx.verify_results = verify_results
        ctx.coherence_classifications = classifications
        ctx.source_dir = source_dir
        ctx.output_dir = output_dir
        ctx.mastered_files = [
            output_dir / "01-anchor.wav",
            output_dir / "02-bassy.wav",
        ]
        ctx.effective_ceiling = -1.0
        ctx.effective_compress = 1.0
        ctx.effective_preset = {}
        ctx.preset_dict = None
        await _stage_coherence_correct(ctx)
        return ctx

    ctx = asyncio.run(_run())

    stage = ctx.stages["coherence_correct"]
    assert stage["status"] == "pass", f"expected pass (clamp-only), got {stage['status']}"
    assert "advisories" in stage, f"expected advisories field, got keys {list(stage.keys())}"
    advisories = stage["advisories"]
    assert len(advisories) == 1
    adv = advisories[0]
    assert adv["filename"] == "02-bassy.wav"
    assert adv["kind"] == "tilt_ceiling"
    assert "±0.50 dB clamp" in adv["message"]
    assert "intended +0.78 dB" in adv["message"]
    assert "applied +0.50 dB" in adv["message"]
    # ctx.warnings starts empty; clamp-only must NOT append.
    assert ctx.warnings == [], (
        f"clamp-only should NOT append to ctx.warnings, got {ctx.warnings}"
    )


def test_coherence_correct_mixed_clamp_and_drift_stays_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#334: if any remaining unconvergent entry has a non-clamp reason,
    stage status stays 'warn' and a warning is appended."""
    # Seed all_corrections via a pre-built stage that mixes reasons.
    # Simplest path: post-loop classification logic runs on whatever is in
    # all_corrections — so drive the stage through a plan that returns one
    # clamp-bound entry, then manually inject a drift-bound unconvergent
    # entry before the severity classifier runs. We simulate this by using
    # the fixed-point path for one track and patching all_corrections via
    # a side effect on the plan function.
    anchor_lufs = -14.0
    source_dir = tmp_path / "polished"
    source_dir.mkdir()
    output_dir = tmp_path / "mastered"
    output_dir.mkdir()
    for name in ("02-clamp.wav", "03-drift.wav"):
        _write_sine_wav(source_dir / name, amplitude=0.2)
        import shutil
        shutil.copy(source_dir / name, output_dir / name)
    _write_sine_wav(output_dir / "01-anchor.wav")

    def _fake_master_track(src: str, dst: str, **kwargs) -> dict:
        import shutil
        shutil.copy(src, dst)
        return {"status": "ok"}

    import tools.mastering.master_tracks as _mt_mod
    monkeypatch.setattr(_mt_mod, "master_track", _fake_master_track)

    def _fake_plan(classifications, analysis_results, anchor_index_1based, max_tilt_db=None):
        return {
            "anchor_index": anchor_index_1based,
            "anchor_lufs": anchor_lufs,
            "corrections": [
                {"index": 2, "filename": "02-clamp.wav", "correctable": True,
                 "corrected_tilt_db": 0.5, "tilt_clamped": True,
                 "intended_tilt_db": 0.78, "limiting_metric": "low_rms_db",
                 "spectral_delta_db": 0.78, "reason": "spectral"},
                {"index": 3, "filename": "03-drift.wav", "correctable": True,
                 "corrected_tilt_db": 0.2, "tilt_clamped": False,
                 "intended_tilt_db": 0.2, "limiting_metric": "low_rms_db",
                 "spectral_delta_db": 0.2, "reason": "spectral"},
            ],
            "skipped": [{"index": 1, "filename": "01-anchor.wav", "reason": "is_anchor"}],
        }

    monkeypatch.setattr(album_stages_mod, "_coherence_build_plan", _fake_plan)

    verify_results = [
        _make_verify_result("01-anchor.wav", lufs=anchor_lufs, low_rms=-20.0),
        _make_verify_result("02-clamp.wav", lufs=-14.0, low_rms=-15.0),
        _make_verify_result("03-drift.wav", lufs=-14.0, low_rms=-15.0),
    ]

    def _fake_analyze(path: str) -> dict:
        name = Path(path).name
        for r in verify_results:
            if r["filename"] == name:
                return r
        return verify_results[0]

    import tools.mastering.analyze_tracks as _at_mod
    monkeypatch.setattr(_at_mod, "analyze_track", _fake_analyze)

    # Both tracks remain outliers after correction. Track 2 is clamp-bound
    # (hits fixed-point detection), track 3 is not clamp-bound — it will
    # run corrections but remain an outlier, so the stage's post-loop
    # remaining_outliers count > 0 with mixed clamp/non-clamp unconvergent.
    # To force a non-clamp 'unconvergent' on track 3, we emulate the
    # fixed-point detector firing on both tracks but patch one of the
    # resulting corrections to a drift-style reason post-hoc.
    classifications = [
        {"index": 1, "filename": "01-anchor.wav", "is_anchor": True,
         "is_outlier": False, "violations": []},
        {"index": 2, "filename": "02-clamp.wav", "is_anchor": False,
         "is_outlier": True, "violations": [
            {"metric": "low_rms", "delta": 5.0, "tolerance": 2.0,
             "severity": "outlier", "correctable": True},
         ]},
        {"index": 3, "filename": "03-drift.wav", "is_anchor": False,
         "is_outlier": True, "violations": [
            {"metric": "low_rms", "delta": 0.6, "tolerance": 2.0,
             "severity": "outlier", "correctable": True},
         ]},
    ]

    # Let the stage run its full fixed-point path — both tracks get
    # reason=fixed_point_tilt_clamp. We then mutate one entry's reason to
    # 'drift_regression' and re-invoke the severity classifier helper
    # directly to verify the mixed-case branch.
    import asyncio
    async def _run():
        ctx = MasterAlbumCtx(
            album_slug="test-album", genre="", target_lufs=-14.0,
            ceiling_db=-1.0, cut_highmid=0.0, cut_highs=0.0,
            source_subfolder="", freeze_signature=False, new_anchor=False,
            loop=asyncio.get_running_loop(),
        )
        ctx.anchor_result = {"selected_index": 1}
        ctx.verify_results = verify_results
        ctx.coherence_classifications = classifications
        ctx.source_dir = source_dir
        ctx.output_dir = output_dir
        ctx.mastered_files = [
            output_dir / "01-anchor.wav",
            output_dir / "02-clamp.wav",
            output_dir / "03-drift.wav",
        ]
        ctx.effective_ceiling = -1.0
        ctx.effective_compress = 1.0
        ctx.effective_preset = {}
        ctx.preset_dict = None
        await _stage_coherence_correct(ctx)
        return ctx

    ctx = asyncio.run(_run())

    # Simulate the mixed case: flip one entry's reason to 'drift' and
    # re-run the severity classifier (the _coherence_finalize_stage
    # helper introduced in Task 5).
    stage_corrections = ctx.stages["coherence_correct"]["corrections"]
    drift_idx = next(
        i for i, c in enumerate(stage_corrections)
        if c["filename"] == "03-drift.wav"
    )
    stage_corrections[drift_idx]["reason"] = "drift_regression"
    # Re-run the classifier with the mutated list.
    ctx.warnings.clear()
    ctx.stages["coherence_correct"] = album_stages_mod._coherence_finalize_stage(
        corrections=stage_corrections,
        iterations_run=ctx.stages["coherence_correct"]["iterations"],
        remaining_outliers=2,
        adm_cycle=ctx.adm_cycle,
        tolerances={"coherence_tilt_max_db": 0.5},
        ctx_warnings=ctx.warnings,
    )

    stage = ctx.stages["coherence_correct"]
    assert stage["status"] == "warn", (
        f"mixed clamp+drift must stay warn, got {stage['status']}"
    )
    assert "advisories" in stage
    assert len(stage["advisories"]) == 1  # only the clamp-bound track
    assert stage["advisories"][0]["filename"] == "02-clamp.wav"
    assert len(ctx.warnings) == 1, (
        f"mixed case must append exactly one warning, got {ctx.warnings}"
    )
```

Implementation note: the second test calls a helper `_coherence_finalize_stage` that does not exist yet — Task 5's implementation step creates it. This is deliberate: extracting the classifier into a helper keeps the stage function readable and makes the mixed-case test possible without a full second pipeline run.

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/unit/mastering/test_master_album_coherence_stages.py::test_coherence_correct_all_clamp_bound_downgrades_to_pass tests/unit/mastering/test_master_album_coherence_stages.py::test_coherence_correct_mixed_clamp_and_drift_stays_warn -v`
Expected: FAIL — first test fails on `stage["status"] == "pass"` (currently `warn`) / missing `advisories` key; second test fails on `AttributeError: module ... has no attribute '_coherence_finalize_stage'`.

- [ ] **Step 3: Extract the finalize-stage helper + implement severity logic**

Edit `servers/bitwize-music-server/handlers/processing/_album_stages.py`. Immediately after the helper constants around line 932 (`_COHERENCE_MAX_CORRECTION_DB` / `_COHERENCE_MAX_ITERATIONS`), insert:

```python
def _coherence_finalize_stage(
    *,
    corrections: list[dict[str, Any]],
    iterations_run: int,
    remaining_outliers: int,
    adm_cycle: int,
    tolerances: dict[str, float],
    ctx_warnings: list[str],
) -> dict[str, Any]:
    """Classify remaining unconvergent entries and build the stage-level
    status + advisories dict. Called at the end of _stage_coherence_correct.

    Returns the stage dict (caller assigns to ctx.stages["coherence_correct"]).
    Mutates ``ctx_warnings`` by appending a warning only in the mixed /
    all-drift case (see #334 spec: clamp-only remaining outliers are a
    benign ceiling hit, not a warning).
    """
    if remaining_outliers <= 0:
        return {
            "status": "pass",
            "iterations": iterations_run,
            "corrections": corrections,
        }

    unconvergent = [c for c in corrections if c.get("status") == "unconvergent"]
    clamp_bound = [
        c for c in unconvergent
        if c.get("reason") == "fixed_point_tilt_clamp"
    ]

    max_tilt = float(tolerances.get("coherence_tilt_max_db", 0.5))
    advisories: list[dict[str, Any]] = []
    for entry in clamp_bound:
        intended = entry.get("intended_tilt_db")
        applied = entry.get("applied_tilt_db")
        if intended is None or applied is None:
            message = f"spectral tilt exceeded ±{max_tilt:.2f} dB clamp"
        else:
            message = (
                f"spectral tilt exceeded ±{max_tilt:.2f} dB clamp "
                f"(intended {float(intended):+.2f} dB, "
                f"applied {float(applied):+.2f} dB)"
            )
        advisories.append({
            "filename": entry["filename"],
            "kind":     "tilt_ceiling",
            "message":  message,
        })

    all_clamp_bound = bool(unconvergent) and len(clamp_bound) == len(unconvergent)

    if all_clamp_bound:
        stage = {
            "status": "pass",
            "iterations": iterations_run,
            "corrections": corrections,
            "advisories": advisories,
        }
        logger.info(
            "coherence_correct: %d track(s) at correction ceiling — see advisories",
            len(advisories),
        )
        return stage

    # Mixed (some clamp, some drift) or all-drift: keep warn + warnings list.
    stage = {
        "status": "warn",
        "reason": f"{remaining_outliers} outlier(s) remain after {_COHERENCE_MAX_ITERATIONS} iteration(s)",
        "iterations": iterations_run,
        "corrections": corrections,
        "remaining_outliers": remaining_outliers,
    }
    if advisories:
        stage["advisories"] = advisories
    ctx_warnings.append(
        f"Coherence correct (ADM cycle {adm_cycle + 1}): "
        f"{remaining_outliers} outlier(s) remain after "
        f"{iterations_run} iteration(s); ceiling_guard may apply pull-down."
    )
    return stage
```

If `logger` is not already imported at the top of `_album_stages.py`, add `import logging` and `logger = logging.getLogger(__name__)` in the standard-library-imports block near the top of the file. (Check first — the file may already have one.)

Next, replace the existing terminal-status block in `_stage_coherence_correct` (lines 1173–1194 — the `if remaining_outliers > 0 ... else ...` block at the bottom) with:

```python
    remaining_outliers = sum(1 for c in classifications if c.get("is_outlier"))
    ctx.stages["coherence_correct"] = _coherence_finalize_stage(
        corrections=all_corrections,
        iterations_run=iterations_run,
        remaining_outliers=remaining_outliers,
        adm_cycle=ctx.adm_cycle,
        tolerances=tolerances,
        ctx_warnings=ctx.warnings,
    )
    return None
```

- [ ] **Step 4: Run the two new tests — they pass**

Run: `pytest tests/unit/mastering/test_master_album_coherence_stages.py::test_coherence_correct_all_clamp_bound_downgrades_to_pass tests/unit/mastering/test_master_album_coherence_stages.py::test_coherence_correct_mixed_clamp_and_drift_stays_warn -v`
Expected: PASS.

- [ ] **Step 5: Run full coherence-stage test file + full coherence unit tests**

Run: `pytest tests/unit/mastering/test_master_album_coherence_stages.py tests/unit/mastering/test_coherence.py tests/unit/mastering/test_coherence_presets.py -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/_album_stages.py \
        tests/unit/mastering/test_master_album_coherence_stages.py
git commit -m "feat: downgrade coherence_correct to pass when clamp-only (#334)

When all remaining outliers after the correction loop carry
reason=fixed_point_tilt_clamp, the stage now emits status=pass with
an advisories list (kind=tilt_ceiling) instead of warn + ctx.warnings
append. Mixed clamp+drift or all-drift cases keep warn. Severity
classification extracted into _coherence_finalize_stage helper. Logs
one INFO line when the downgrade fires so live-run operators still
see the ceiling hit."
```

---

## Task 6: Final verification — `make check`

**Files:** none (verification only)

- [ ] **Step 1: Run the full lint + test suite**

From repo root:

```bash
make check
```

Expected: all green. `make check` runs `ruff`, `bandit`, `mypy`, and `pytest` per the CLAUDE.md pre-push gate.

- [ ] **Step 2: If lint fails, fix inline**

Likely `ruff` complaints:
- Unused imports in `_album_stages.py` if `logging` was added but `logger` isn't referenced somewhere it was expected.
- `mypy` complaining about the `tuple[float, bool, float, str | None, float | None]` return type if a caller still unpacks as `tuple[float, bool]`.

Common fix patterns:
- For mypy: ensure both `_stage_coherence_correct` and `build_correction_plan` are consistent with the new tuple shape. The only callers of `_compute_tilt_db` are `build_correction_plan` (updated in Task 2 step 5) and the tests — no other production call sites.
- For ruff: run `ruff check --fix` to auto-fix formatting, then re-run `make check`.

If `make check` surfaces something else (unrelated test failure, bandit warning), stop and read the output — don't blind-fix. Report the exact failure in the PR body.

- [ ] **Step 3: Spot-check the change locally with an actual album**

Run:

```bash
~/.bitwize-music/venv/bin/python3 -c "
from tools.mastering.coherence import _compute_tilt_db
v = [{'metric':'low_rms','delta':3.0,'tolerance':2.0,'severity':'outlier'}]
print(_compute_tilt_db(v))
print(_compute_tilt_db(v, max_tilt_db=0.75))
"
```

Expected output:
```
(0.5, True, 3.0, 'low_rms_db', 3.0)
(0.75, True, 3.0, 'low_rms_db', 3.0)
```

This is a smoke test — confirms the venv can import the expanded module and the clamp parameter is honored.

- [ ] **Step 4: Push and open PR**

```bash
git push -u origin <branch-name>
gh pr create --base develop --title "fix: coherence_correct clamp telemetry (#334)" --body "$(cat <<'EOF'
## Summary
- Exposes the coherence tilt-EQ clamp as a preset key (`coherence_tilt_max_db`, default 0.5 — unchanged)
- Downgrades `coherence_correct` stage to `status: "pass"` with an `advisories` list when all remaining outliers are `fixed_point_tilt_clamp` (benign ceiling hit, not a convergence failure)
- Surfaces `intended_tilt_db`, `limiting_metric`, and `spectral_delta_db` on unconvergent correction entries so operators can see what the corrector was trying to fix

Closes #334. No default values changed — per-genre tuning of the tilt cap is a follow-up that needs audio validation.

## Test plan
- [ ] `make check` passes locally
- [ ] Re-run the repro from the issue (`polish_album` + `master_album` on `if-anyone-makes-it-everyone-dances`, electronic) and confirm:
  - `coherence_correct.status` is now `"pass"` (was `"warn"`)
  - `advisories` lists the 7 clamp-bound tracks
  - Per-track unconvergent entries include `intended_tilt_db`, `limiting_metric`, `spectral_delta_db`
  - No `coherence_correct` entry in `warnings` in the final report
EOF
)"
```

---

## Self-Review Checklist

Run through this after drafting all task code, before committing the plan doc:

**Spec coverage:**
- [x] Preset key (`coherence_tilt_max_db`, default 0.5, per-genre overridable) — Task 1.
- [x] `_compute_tilt_db` expanded tuple — Task 2.
- [x] `build_correction_plan` threads `max_tilt_db`, exposes new fields — Task 3.
- [x] `_stage_coherence_correct` reads preset, propagates new fields to unconvergent entries — Task 4.
- [x] Severity downgrade + advisories when all clamp-bound — Task 5.
- [x] `ctx.warnings` not appended in clamp-only case — Task 5.
- [x] INFO log line when downgraded — Task 5.
- [x] Existing tests still pass (`TestTiltClampedFlag`, fixed-point test) — Task 2 step 6, Task 5 step 5.
- [x] `make check` gate — Task 6.

**Placeholder scan:** No TBDs. All code blocks show real code. No "similar to Task N" references.

**Type consistency:**
- `_compute_tilt_db` return: `tuple[float, bool, float, str | None, float | None]` — same across signature, body, and all call sites.
- `max_tilt_db` kwarg: `float | None` on `build_correction_plan`, `float` (with default) on `_compute_tilt_db`. Asymmetry is deliberate — `build_correction_plan` accepts `None` for API ergonomics and maps it to the module constant; `_compute_tilt_db` is an internal helper and requires a concrete value.
- Advisory kind: fixed string `"tilt_ceiling"` (matches spec).
- Limiting metric values: `"low_rms_db"` / `"vocal_rms_db"` (matches spec).

**Task decomposition:** Each task commits independently. If the plan is halted after Task 2 and merged, the codebase still works (expanded tuple, but no new stage behavior). Tasks 4+5 can't be split further without leaving the preset-read orphaned from the severity classifier — they're one logical feature split by test seam.

## Out of Scope (explicit)

- No changes to `_COHERENCE_MAX_ITERATIONS` (stays 2).
- No per-genre `coherence_tilt_max_db` overrides in `genre-presets.yaml`.
- No new severity level (`notice` / `info`). Stage `status: "pass"` + `advisories` field carries the meaning.
- No final-report renderer changes. Advisories appear in the stage JSON; pretty-printing is a follow-up.
- No drift-vs-clamp reason codes beyond `fixed_point_tilt_clamp`. Mixed-case logic handles the structural shape but there is no second reason code in production today.
