# Fix #323 Coherence Convergence + ADM Retry Test Gap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the pipeline bugs surfaced by the 2026-04-17 re-test comment on issue #323: coherence_correct non-convergence and the correctable_count mismatch, plus harden the ADM retry test to lock in the tightened-ceiling contract.

**Architecture:** Three scoped fixes, each with its own test:

1. **`correctable_count` alignment (Bug 1a):** `_stage_coherence_check` currently counts only LUFS outliers as "correctable". But `_stage_coherence_correct` acts on any entry marked `correctable=True` by `build_correction_plan`, which includes spectral (`low_rms`/`vocal_rms`) outliers. Fix: the check stage should delegate to `build_correction_plan` so both stages agree on "correctable".

2. **Fixed-point detection (Bug 1b):** When the required tilt exceeds the ±0.5 dB clamp, each coherence iteration re-masters from the same polished source with the same clamped tilt — identical result, zero progress. Fix: (a) expose `tilt_clamped` on each correction record for transparency, and (b) detect when consecutive iterations produce identical correction plans and break out of the loop with a clear `unconvergent` status instead of burning the full iteration budget.

3. **ADM retry test hardening (Bug 2):** The existing `test_adm_retry_tightens_ceiling_on_clips` only asserts the ADM check was called twice; it never verifies that `master_track` received the tightened `ceiling_db` on cycle 2. Add an assertion that locks in the retry contract so future regressions are caught.

Track 09's outlier profile (Bug 3) is content-driven (AAC intersample overshoot on bass-heavy content), not a pipeline bug — no code change.

**Tech Stack:** Python 3.10+, pytest, existing pure-Python `tools/mastering/coherence.py` module, MCP-server stage handlers in `servers/bitwize-music-server/handlers/processing/_album_stages.py`.

---

## File Structure

**Files modified:**
- `tools/mastering/coherence.py` — add `tilt_clamped` flag to correction entries in `build_correction_plan`; expose the correctable-count logic as a reusable helper.
- `servers/bitwize-music-server/handlers/processing/_album_stages.py` — rewrite `correctable_count` in `_stage_coherence_check` to match the plan logic; add fixed-point detection in `_stage_coherence_correct`.

**Tests modified/created:**
- `tests/unit/mastering/test_coherence.py` — add unit tests for `tilt_clamped` + correctable-count parity.
- `tests/unit/mastering/test_master_album_coherence_stages.py` — add stage-level fixed-point test (multi-iteration, non-monkey-patched `_COHERENCE_MAX_ITERATIONS`).
- `tests/unit/mastering/test_master_album_adm_retry.py` — add assertion in `test_adm_retry_tightens_ceiling_on_clips` that `master_track` received tightened ceiling on cycle 2.

No new files created — all fixes integrate into existing modules.

---

## Task 1: Add `tilt_clamped` flag to correction plan entries

**Why:** The existing `clamped` field on a correction entry refers only to the LUFS-window clamp (±1.5 dB around anchor). When tilt is clamped at ±0.5 dB, that fact is invisible — callers can't tell that further iterations won't move the track closer to tolerance. Exposing `tilt_clamped` is prerequisite for both user-facing transparency and the fixed-point logic in Task 3.

**Files:**
- Modify: `tools/mastering/coherence.py` — `_compute_tilt_db` and `build_correction_plan`
- Test: `tests/unit/mastering/test_coherence.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/mastering/test_coherence.py`:

```python
def test_build_correction_plan_tilt_clamped_flag():
    """Correction entries must expose tilt_clamped=True when raw tilt exceeded ±0.5 dB."""
    from tools.mastering.coherence import build_correction_plan

    # Track 2 has delta_low_rms = +3.0 dB → raw tilt = +3.0 → clamped to +0.5
    classifications = [
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
            {"metric": "low_rms",   "delta": 3.0, "tolerance": 2.0,
             "severity": "outlier", "correctable": True},
            {"metric": "vocal_rms", "delta": 0.0, "tolerance": 2.0,
             "severity": "ok",      "correctable": False},
         ]},
    ]
    analysis = [
        {"lufs": -14.0, "filename": "01.wav"},
        {"lufs": -14.0, "filename": "02.wav"},
    ]
    plan = build_correction_plan(classifications, analysis, anchor_index_1based=1)
    assert len(plan["corrections"]) == 1
    entry = plan["corrections"][0]
    assert entry["correctable"] is True
    assert entry["corrected_tilt_db"] == 0.5  # clamped
    assert entry["tilt_clamped"] is True


def test_build_correction_plan_tilt_not_clamped():
    """tilt_clamped=False when raw tilt is within ±0.5 dB."""
    from tools.mastering.coherence import build_correction_plan

    classifications = [
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
            {"metric": "low_rms",   "delta": 2.3, "tolerance": 2.0,
             "severity": "outlier", "correctable": True},
            {"metric": "vocal_rms", "delta": 0.0, "tolerance": 2.0,
             "severity": "ok",      "correctable": False},
         ]},
    ]
    analysis = [
        {"lufs": -14.0, "filename": "01.wav"},
        {"lufs": -14.0, "filename": "02.wav"},
    ]
    plan = build_correction_plan(classifications, analysis, anchor_index_1based=1)
    entry = plan["corrections"][0]
    assert entry["corrected_tilt_db"] == pytest.approx(0.3, abs=1e-9)
    assert entry["tilt_clamped"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/bitwize/GitHub/claude-ai-music-skills/.worktrees/fix-323-coherence
.venv/bin/pytest tests/unit/mastering/test_coherence.py::test_build_correction_plan_tilt_clamped_flag tests/unit/mastering/test_coherence.py::test_build_correction_plan_tilt_not_clamped -v
```

Expected: FAIL with `KeyError: 'tilt_clamped'` or `AssertionError`.

- [ ] **Step 3: Update `_compute_tilt_db` to return clamp status**

In `tools/mastering/coherence.py`, replace the existing `_compute_tilt_db` with:

```python
def _compute_tilt_db(violations: list[dict[str, Any]]) -> tuple[float, bool]:
    """Derive a bounded tilt-EQ correction from spectral violations.

    Returns (tilt_db, clamped) — clamped=True when the raw tilt exceeded
    ``TILT_CORRECTION_MAX_DB``. The clamp flag lets the stage-level
    coherence loop detect structurally unconvergent corrections.

    Tilt sign convention (matches ``master_tracks.apply_tilt_eq``):
      - positive tilt → cut lows, boost highs (brighter)
      - negative tilt → boost lows, cut highs (warmer)
    """
    low = next(
        (v for v in violations
         if v["metric"] == "low_rms" and v["severity"] == "outlier"),
        None,
    )
    if low is not None and low.get("delta") is not None:
        raw = float(low["delta"])
        clamped = abs(raw) > TILT_CORRECTION_MAX_DB
        return max(-TILT_CORRECTION_MAX_DB, min(TILT_CORRECTION_MAX_DB, raw)), clamped

    vocal = next(
        (v for v in violations
         if v["metric"] == "vocal_rms" and v["severity"] == "outlier"),
        None,
    )
    if vocal is not None and vocal.get("delta") is not None:
        raw = -float(vocal["delta"])
        clamped = abs(raw) > TILT_CORRECTION_MAX_DB
        return max(-TILT_CORRECTION_MAX_DB, min(TILT_CORRECTION_MAX_DB, raw)), clamped

    return 0.0, False
```

- [ ] **Step 4: Update `build_correction_plan` to surface `tilt_clamped`**

Replace the relevant block in `build_correction_plan`:

```python
        tilt_db = 0.0
        tilt_clamped = False
        if spectral_violations:
            tilt_db, tilt_clamped = _compute_tilt_db(violations)

        if lufs_violation is not None or spectral_violations:
            reason_parts: list[str] = []
            entry: dict[str, Any] = {
                "index":         cls["index"],
                "filename":      cls.get("filename"),
                "correctable":   True,
                "tilt_clamped":  tilt_clamped,
            }
            if lufs_violation is not None:
                entry["corrected_target_lufs"] = anchor_lufs
                reason_parts.append(
                    f"LUFS outlier: delta={lufs_violation['delta']:+.2f}, "
                    f"tolerance=±{lufs_violation['tolerance']:.2f}"
                )
            if spectral_violations:
                entry["corrected_tilt_db"] = tilt_db
                metrics = ", ".join(sorted({v["metric"] for v in spectral_violations}))
                reason_parts.append(
                    f"Spectral outlier ({metrics}) → tilt_db={tilt_db:+.2f}"
                    f"{' (clamped)' if tilt_clamped else ''}"
                )
            entry["reason"] = "; ".join(reason_parts)
            corrections.append(entry)
```

Leave the `elif uncorrectable_outliers:` and `else:` branches unchanged — they don't set `tilt_clamped` because they are not correctable.

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/unit/mastering/test_coherence.py -v
```

Expected: all tests pass, including the two new ones.

- [ ] **Step 6: Commit**

```bash
git add tools/mastering/coherence.py tests/unit/mastering/test_coherence.py
git commit -m "fix: expose tilt_clamped on coherence correction entries (#323 comment)"
```

---

## Task 2: Align `correctable_count` with `build_correction_plan`

**Why:** `_stage_coherence_check` reports `correctable_count: 0` while `_stage_coherence_correct` runs corrections. The two views must agree on "correctable" — otherwise operators see false reassurance followed by iteration churn.

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/_album_stages.py:965-985`
- Test: `tests/unit/mastering/test_master_album_coherence_stages.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/mastering/test_master_album_coherence_stages.py`:

```python
def test_coherence_check_counts_spectral_correctables():
    """correctable_count must include spectral outliers, not just LUFS."""
    import asyncio
    from handlers.processing._album_stages import (
        MasterAlbumCtx, _stage_coherence_check,
    )

    ctx = MasterAlbumCtx(album_slug="test")
    ctx.anchor_result = {"selected_index": 1}
    # Two tracks: anchor clean, track 2 has spectral outlier only (no LUFS)
    ctx.verify_results = [
        {"filename": "01.wav", "lufs": -14.0, "low_rms_db": -20.0,
         "vocal_rms_db": -18.0, "short_term_range": 8.0, "lra": 5.0,
         "stl_95_lu": -12.0},
        {"filename": "02.wav", "lufs": -14.0, "low_rms_db": -17.0,
         "vocal_rms_db": -18.0, "short_term_range": 8.0, "lra": 5.0,
         "stl_95_lu": -12.0},
    ]
    ctx.preset_dict = {}
    ctx.stages = {}

    asyncio.run(_stage_coherence_check(ctx))

    check = ctx.stages["coherence_check"]
    assert check["outlier_count"] == 1       # track 2 is spectral-outlier
    assert check["correctable_count"] == 1   # spectral counts as correctable
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_coherence_stages.py::test_coherence_check_counts_spectral_correctables -v
```

Expected: FAIL with `assert 0 == 1` on the `correctable_count` assertion.

- [ ] **Step 3: Rewrite `correctable_count` in `_stage_coherence_check`**

In `servers/bitwize-music-server/handlers/processing/_album_stages.py`, replace the `correctable_count` computation (currently at lines 971-977) with a call to `build_correction_plan`:

```python
    outlier_count = sum(1 for c in classifications if c.get("is_outlier"))

    # Correctable count must match what _stage_coherence_correct will actually
    # act on. Delegate to build_correction_plan so both stages share one
    # definition of "correctable" (LUFS outliers OR spectral outliers with
    # tilt-EQ correction available). Previously this counted LUFS only, which
    # hid spectral corrections from the pre-correct report.
    from tools.mastering.coherence import build_correction_plan
    plan = build_correction_plan(
        classifications, ctx.verify_results, anchor_index_1based=anchor_idx
    )
    correctable_count = sum(1 for c in plan["corrections"] if c["correctable"])

    ctx.stages["coherence_check"] = {
        "status": "pass" if outlier_count == 0 else "warn",
        "outlier_count": outlier_count,
        "correctable_count": correctable_count,
        "anchor_index": anchor_idx,
    }
    return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_coherence_stages.py::test_coherence_check_counts_spectral_correctables -v
```

Expected: PASS.

- [ ] **Step 5: Run broader coherence test suite to catch regressions**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_coherence_stages.py tests/unit/mastering/test_coherence.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/_album_stages.py tests/unit/mastering/test_master_album_coherence_stages.py
git commit -m "fix: align correctable_count with coherence_correct gate (#323 comment)"
```

---

## Task 3: Detect fixed-point non-convergence in `_stage_coherence_correct`

**Why:** When clamped tilt is insufficient to move a spectral outlier inside tolerance, every iteration re-masters from the same polished source with the same clamped tilt — zero progress, identical output, but the loop still burns all `_COHERENCE_MAX_ITERATIONS` cycles. Detect that fixed point and break early with a clear `unconvergent` status so operators know the stage hit a structural ceiling rather than a transient miss.

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/_album_stages.py:1036-1149`
- Test: `tests/unit/mastering/test_master_album_coherence_stages.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/mastering/test_master_album_coherence_stages.py`:

```python
def test_coherence_correct_breaks_on_fixed_point(monkeypatch, tmp_path):
    """When consecutive iterations produce identical correction plans and
    tilt is clamped, coherence_correct must break out early and flag the
    stuck tracks rather than burning the full iteration budget."""
    import asyncio
    from pathlib import Path
    from handlers.processing import _album_stages as stages_mod
    from handlers.processing._album_stages import (
        MasterAlbumCtx, _stage_coherence_correct,
    )

    # Two tracks, anchor clean, track 2 has low_rms delta = +5.0 → clamped tilt +0.5
    # Fresh analyses always return the same outlier (no progress).
    track2_analysis = {
        "filename": "02.wav", "lufs": -14.0, "low_rms_db": -15.0,
        "vocal_rms_db": -18.0, "short_term_range": 8.0, "lra": 5.0,
        "stl_95_lu": -12.0,
    }
    anchor_analysis = {
        "filename": "01.wav", "lufs": -14.0, "low_rms_db": -20.0,
        "vocal_rms_db": -18.0, "short_term_range": 8.0, "lra": 5.0,
        "stl_95_lu": -12.0,
    }

    (tmp_path / "01.wav").write_bytes(b"")
    (tmp_path / "02.wav").write_bytes(b"")
    (tmp_path / "out").mkdir()

    # Patch master_track (sync) + analyze_track to stay deterministic.
    monkeypatch.setattr(
        "tools.mastering.master_tracks.master_track",
        lambda *a, **kw: {"filename": Path(a[1]).name, "applied_target_lufs": -14.0},
    )
    monkeypatch.setattr(
        "tools.mastering.analyze_tracks.analyze_track",
        lambda path: track2_analysis if Path(path).name == "02.wav" else anchor_analysis,
    )

    ctx = MasterAlbumCtx(album_slug="test")
    ctx.anchor_result = {"selected_index": 1}
    ctx.verify_results = [anchor_analysis, track2_analysis]
    ctx.source_dir = tmp_path
    ctx.output_dir = tmp_path / "out"
    ctx.mastered_files = [tmp_path / "out" / "01.wav", tmp_path / "out" / "02.wav"]
    ctx.effective_ceiling = -1.0
    ctx.effective_compress = 1.0
    ctx.effective_preset = {}
    ctx.preset_dict = {}
    ctx.loop = asyncio.new_event_loop()
    ctx.adm_cycle = 0
    ctx.coherence_classifications = [
        {"index": 1, "filename": "01.wav", "is_anchor": True,
         "is_outlier": False, "violations": []},
        {"index": 2, "filename": "02.wav", "is_anchor": False,
         "is_outlier": True, "violations": [
            {"metric": "lufs",      "delta": 0.0, "tolerance": 0.5,
             "severity": "ok",      "correctable": False},
            {"metric": "stl_95",    "delta": 0.0, "tolerance": 0.5,
             "severity": "ok",      "correctable": False},
            {"metric": "lra_floor", "value": 5.0, "floor": 1.0,
             "severity": "ok",      "correctable": False},
            {"metric": "low_rms",   "delta": 5.0, "tolerance": 2.0,
             "severity": "outlier", "correctable": True},
            {"metric": "vocal_rms", "delta": 0.0, "tolerance": 2.0,
             "severity": "ok",      "correctable": False},
         ]},
    ]
    ctx.stages = {}
    ctx.warnings = []
    ctx.coherence_corrected_tracks = []

    # Do NOT monkey-patch _COHERENCE_MAX_ITERATIONS — full budget should not be used
    try:
        ctx.loop.run_until_complete(_stage_coherence_correct(ctx))
    finally:
        ctx.loop.close()

    stage = ctx.stages["coherence_correct"]
    # Must break early on fixed point — iterations should be <= 2 (first
    # apply, then detect repeat and bail). Never should it run full budget.
    assert stage["iterations"] <= 2, (
        f"Expected early break on fixed point, ran {stage['iterations']} iterations"
    )
    # Must flag the stuck track with a clear reason.
    assert any(
        c["status"] == "unconvergent" and c["filename"] == "02.wav"
        for c in stage["corrections"]
    ), f"Expected unconvergent status for 02.wav, got: {stage['corrections']}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_coherence_stages.py::test_coherence_correct_breaks_on_fixed_point -v
```

Expected: FAIL — either stage runs the full iteration budget, or no `unconvergent` status appears.

- [ ] **Step 3: Add fixed-point detection to `_stage_coherence_correct`**

In `servers/bitwize-music-server/handlers/processing/_album_stages.py`, modify the iteration loop in `_stage_coherence_correct` (around line 1036) to track the correction-plan signature between iterations and break when it repeats:

```python
    prev_plan_signature: tuple[tuple[str, float, float], ...] | None = None

    for _iter in range(_COHERENCE_MAX_ITERATIONS):
        plan = _coherence_build_plan(classifications, current_verify, anchor_idx)
        correctable = [c for c in plan["corrections"] if c["correctable"]]
        if not correctable:
            break

        # Fixed-point detection: if this iteration's correction plan is
        # identical to the previous one AND at least one entry has tilt
        # clamped, re-mastering will produce the same output. Flag each
        # unconvergent track and break the loop rather than burning the
        # remaining iteration budget on a result we already know.
        plan_signature = tuple(
            (
                str(c["filename"]),
                round(float(c.get("corrected_target_lufs", 0.0)), 3),
                round(float(c.get("corrected_tilt_db", 0.0)), 3),
            )
            for c in correctable
        )
        any_tilt_clamped = any(c.get("tilt_clamped") for c in correctable)
        if plan_signature == prev_plan_signature and any_tilt_clamped:
            for entry in correctable:
                all_corrections.append({
                    "filename": entry["filename"],
                    "status": "unconvergent",
                    "reason": "fixed_point_tilt_clamp",
                    "applied_target_lufs": entry.get("corrected_target_lufs"),
                    "applied_tilt_db": entry.get("corrected_tilt_db"),
                    "tilt_clamped": entry.get("tilt_clamped", False),
                    "iteration": _iter + 1,
                })
            break
        prev_plan_signature = plan_signature

        anchor_lufs = frozen_anchor_lufs
        iterations_run += 1

        # ... (rest of the iteration body unchanged)
```

Leave the body of the for-loop after `iterations_run += 1` unchanged.

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_coherence_stages.py::test_coherence_correct_breaks_on_fixed_point -v
```

Expected: PASS.

- [ ] **Step 5: Run broader coherence test suite**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_coherence_stages.py tests/unit/mastering/test_coherence.py -v
```

Expected: all tests pass. If any prior test fails because it expected the old "always run full budget" behavior, inspect it — the old behavior was wrong, so the test should be updated to match the new semantics.

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/_album_stages.py tests/unit/mastering/test_master_album_coherence_stages.py
git commit -m "fix: break coherence_correct loop on fixed-point non-convergence (#323 comment)"
```

---

## Task 4: Harden ADM retry test to verify tightened ceiling reaches mastering

**Why:** The existing `test_adm_retry_tightens_ceiling_on_clips` asserts only that the ADM check was called twice. It never verifies that `master_track` received the tightened `ceiling_db` kwarg on cycle 2. Add an assertion so future regressions in ceiling-propagation are caught.

**Files:**
- Modify: `tests/unit/mastering/test_master_album_adm_retry.py:86-134`

- [ ] **Step 1: Write the failing assertion inside the existing test**

Modify `test_adm_retry_tightens_ceiling_on_clips` to capture the ceilings passed to `master_track` on each cycle. Insert this after `_install_album(...)` and before the `call_count` definition:

```python
    mastered_ceilings: list[float] = []

    _orig_master_track = None
    try:
        from tools.mastering import master_tracks as _mt_mod
        _orig_master_track = _mt_mod.master_track
    except Exception:  # pragma: no cover
        pass

    def _capture_master_track(src, dst, *, target_lufs, ceiling_db, **kwargs):
        mastered_ceilings.append(float(ceiling_db))
        # Write a minimal stereo WAV to dst so downstream stages don't fail
        import soundfile as sf
        import numpy as np
        sr = 44100
        n = int(1.0 * sr)
        silence = np.zeros((n, 2), dtype=np.float32)
        sf.write(str(dst), silence, sr, subtype="PCM_24")
        return {"filename": Path(dst).name, "applied_target_lufs": target_lufs}

    monkeypatch.setattr(album_stages_mod, "_master_track", _capture_master_track)
```

Then add these assertions at the end of the test body (after the existing `notices` assertion):

```python
    # Cycle 2 must re-master with the tightened ceiling. Default starting
    # ceiling is -1.0 dBTP; tightened by 0.5 → -1.5 dBTP on cycle 2.
    assert mastered_ceilings, (
        f"Expected _master_track to be called, got no calls"
    )
    tightened = [c for c in mastered_ceilings if c <= -1.4]
    assert tightened, (
        f"Expected at least one master_track call with ceiling <= -1.5 dBTP "
        f"on cycle 2, got ceilings: {mastered_ceilings}"
    )
```

- [ ] **Step 2: Run test to verify it passes (this is a regression-lock, not a new failure)**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_adm_retry.py::test_adm_retry_tightens_ceiling_on_clips -v
```

Expected: PASS. If it fails, the ceiling is not reaching `_master_track` — investigate (this would be a real regression on top of the test gap).

- [ ] **Step 3: Temporarily break the contract to prove the assertion fires**

Temporarily edit `servers/bitwize-music-server/handlers/processing/audio.py:672` to skip the ceiling update:

```python
                if is_adm_clip:
                    # ctx.effective_ceiling -= 0.5   # TEMPORARILY DISABLED
                    ctx.targets["ceiling_db"] = ctx.effective_ceiling
```

Run the test:

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_adm_retry.py::test_adm_retry_tightens_ceiling_on_clips -v
```

Expected: FAIL on the new tightened-ceiling assertion (proves it catches the regression).

Revert the temporary change:

```bash
git checkout -- servers/bitwize-music-server/handlers/processing/audio.py
```

Re-run the test:

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_adm_retry.py::test_adm_retry_tightens_ceiling_on_clips -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/mastering/test_master_album_adm_retry.py
git commit -m "test: assert ADM retry tightened ceiling reaches master_track (#323 comment)"
```

---

## Task 5: Full test + lint gate

- [ ] **Step 1: Run `make check`**

```bash
cd /home/bitwize/GitHub/claude-ai-music-skills/.worktrees/fix-323-coherence
make check
```

Expected: PASS — all `ruff`, `bandit`, `mypy`, `pytest` suites green.

If any step fails, fix the root cause before proceeding. Do not push with red CI.

- [ ] **Step 2: Push and open PR**

```bash
git push -u origin fix/323-coherence-convergence
gh pr create --base develop --title "fix: coherence convergence + ADM retry test gap (#323 comment)" --body "$(cat <<'EOF'
## Summary

Addresses the three findings from the 2026-04-17 re-test comment on #323:

- **Bug 1a — `correctable_count` mismatch:** `_stage_coherence_check` now uses `build_correction_plan` to count correctable entries, so it agrees with `_stage_coherence_correct`. Spectral (low_rms/vocal_rms) outliers are now counted as correctable (matches what the correct stage acts on).
- **Bug 1b — Fixed-point non-convergence:** `_stage_coherence_correct` now tracks the correction-plan signature across iterations. When consecutive iterations produce identical plans AND at least one entry has `tilt_clamped=True`, the loop breaks early with an `unconvergent` status instead of burning the full iteration budget on a known-futile repeat.
- **Bug 2 — ADM retry test gap:** `test_adm_retry_tightens_ceiling_on_clips` now asserts that `_master_track` received the tightened ceiling (≤ -1.5 dBTP) on cycle 2. Previously the test only checked the ADM function was called twice.

**Bug 3 (track 09 outlier):** Not a pipeline bug — content-driven AAC intersample overshoot on bass-heavy electronic content. Documented in the comment thread; no code change.

## Test plan

- [x] `pytest tests/unit/mastering/test_coherence.py` — new tilt_clamped unit tests pass
- [x] `pytest tests/unit/mastering/test_master_album_coherence_stages.py` — new correctable_count + fixed-point stage tests pass
- [x] `pytest tests/unit/mastering/test_master_album_adm_retry.py` — hardened retry assertion passes
- [x] `make check` — full ruff + bandit + mypy + pytest gate green

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**Spec coverage:**
- Bug 1a (correctable_count mismatch) → Task 2 ✓
- Bug 1b (non-convergence) → Task 1 (tilt_clamped) + Task 3 (fixed-point break) ✓
- Bug 2 (ADM retry test gap) → Task 4 ✓
- Bug 3 (track 09 outlier) → Documented in PR body, no code change (content-driven, not pipeline)

**Placeholder scan:** No TBDs, no "implement later", every code block complete.

**Type consistency:** `_compute_tilt_db` returns `tuple[float, bool]` in Task 1, consumed correctly in `build_correction_plan`. `tilt_clamped` key name is consistent across all tasks (entry field + signature check + test assertions).
