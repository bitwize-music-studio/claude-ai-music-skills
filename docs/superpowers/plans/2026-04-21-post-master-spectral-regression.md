# Post-Master Spectral Regression Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Catch cases where mastering pushed a track's high-mid energy *up* relative to its polished input — a telltale side effect of limiter-driven harmonic generation when the ceiling is tight, especially on the electronic preset. When post-master `tinniness_ratio` exceeds an absolute floor AND grew by a meaningful delta from pre-master, emit a post-QC WARN so operators can catch regressions before they hit streaming.

**Architecture:** Single-stage addition to `_stage_post_qc`. `analyze_track` already computes `tinniness_ratio = band_energy['high_mid'] / band_energy['mid']`. `ctx.analysis_results` has pre-master values; `ctx.verify_results` has post-master values. The check cross-references the two by filename and emits a per-track WARN plus a stage-level summary. No halt — the goal is observability, not gating.

**Tech Stack:** Python 3.11. No new dependencies.

---

## Scope Check

This is a small, self-contained observability addition. It doesn't touch mastering, ADM, polish, or verification — it reads existing artifacts and emits structured warnings.

**Out of scope:**
- Automatic remediation (re-mastering with a softer preset, etc.). Operators receive the WARN and decide.
- Tuning `mastering-preset.yaml` for the electronic preset. If the WARN fires systematically on electronic albums, that's a preset-tuning follow-up, not part of this plan.
- New DSP (e.g., post-limiter de-essing or high-shelf cut). Same reason.
- Per-track post-QC halting on tinniness — spectral taste is genre-dependent and a hard fail would create too many false positives.

---

## Codebase Context

Key files (paths from repo root):

- `servers/bitwize-music-server/handlers/processing/_album_stages.py:1555-1670` — `_stage_post_qc`.
- `tools/mastering/analyze_tracks.py:146-147` — `tinniness_ratio = band_energy['high_mid'] / band_energy['mid']`.
- `tools/mastering/analyze_tracks.py:253-269` — `analyze_track` return dict; already includes `tinniness_ratio`.
- `_stage_post_qc` reads `ctx.verify_results` (populated by `_stage_verification` — has post-master analyze_track results) and `ctx.analysis_results` (populated by `_stage_analysis` — pre-master analyze_track results).

Both result sets already carry `tinniness_ratio`. The data plumbing is already in place — this plan just reads it.

---

## File Structure

| File | Role | State |
|---|---|---|
| `servers/bitwize-music-server/handlers/processing/_album_stages.py` | Add the regression check block to `_stage_post_qc` | modify |
| `tools/mastering/master_tracks.py` | Add `post_qc_tinniness_warn_floor` + `post_qc_tinniness_warn_delta` to `_PRESET_DEFAULTS` (preset-tunable thresholds) | modify |
| `tests/unit/mastering/test_post_master_spectral_regression.py` | Unit + integration tests for the new check | **new** |
| `CHANGELOG.md` | `[Unreleased]` entry | modify |

Files **not** modified:
- `tools/mastering/analyze_tracks.py` — `tinniness_ratio` already returned.
- `tools/mastering/qc_tracks.py` — spectral check stays at its current per-track scope; cross-track regression is an `_stage_post_qc` concern, not a qc_track concern.

---

## Design Details (read before starting any task)

### The two-condition test

Flagging on absolute `tinniness_ratio > 0.6` alone would produce false positives on genres that are inherently tinny-adjacent (some lo-fi electronic, some DnB). Flagging on delta alone (e.g., +0.10 from pre-master) would fire on tracks that started low and ended moderate — not a regression, just a choice.

The combined test captures the actual pathology (mastering *introduced* tinniness that wasn't there in polish):

```python
post_ratio > post_qc_tinniness_warn_floor  AND
(post_ratio - pre_ratio) > post_qc_tinniness_warn_delta
```

Default thresholds (both preset-tunable):
- `post_qc_tinniness_warn_floor`: `0.6` (matches the existing `analyze_tracks.py:381` flag)
- `post_qc_tinniness_warn_delta`: `0.10`

### Preset plumbing

Preset-tunable knobs live in `tools/mastering/master_tracks.py::_PRESET_DEFAULTS`. The `_stage_post_qc` reads them via `ctx.effective_preset`. If a preset doesn't set them, the defaults apply.

### Stage output shape

Extend `ctx.stages["post_qc"]` with a `tinniness_regressions` field:

```python
ctx.stages["post_qc"] = {
    "status": "pass" | "warn" | "fail",
    "passed": int,
    "warned": int,
    "failed": int,
    "verdict": "...",
    "tinniness_regressions": [  # NEW
        {
            "filename": "04-track.wav",
            "pre_tinniness":  0.55,
            "post_tinniness": 0.82,
            "delta":          0.27,
        },
        ...
    ],
}
```

When regressions are found and the current status would be `"pass"`, downgrade to `"warn"`.

Also emit a `ctx.warnings.append(...)` per regression so operators see it in the warnings stream.

### Why post-QC and not verification

Verification has a narrow contract (LUFS + peak). Broadening it to spectral checks would entangle the warn-fallback contract (Plan A) with taste-level judgments. Post-QC is the right spot — it's the stage that says "album is technically shippable," which is exactly where "tinny regression" belongs.

---

## Task 1: Preset defaults for tinniness WARN thresholds

**Files:**
- Modify: `tools/mastering/master_tracks.py` (locate `_PRESET_DEFAULTS`)

- [ ] **Step 1: Find `_PRESET_DEFAULTS`**

```bash
grep -n "_PRESET_DEFAULTS" tools/mastering/master_tracks.py | head -5
```

- [ ] **Step 2: Add the two new keys**

Inside `_PRESET_DEFAULTS`, add near the other `post_qc_*` / tolerance entries:

```python
    # Post-master spectral regression: tinniness_ratio = high_mid / mid
    # (from analyze_track). WARN when post-master ratio exceeds floor AND
    # grew by more than delta from pre-master. Both conditions must hold.
    "post_qc_tinniness_warn_floor": 0.6,
    "post_qc_tinniness_warn_delta": 0.10,
```

- [ ] **Step 3: If there is a `load_tolerances` or `build_effective_preset` merge list, add both keys**

```bash
grep -n "post_qc_\|coherence_stl_95\|load_tolerances" tools/mastering/*.py servers/bitwize-music-server/handlers/processing/*.py
```

Identify where `_PRESET_DEFAULTS` keys get merged into `effective_preset`. If there's a whitelist that requires explicit mention, add both new keys to it.

- [ ] **Step 4: Commit**

```bash
git add tools/mastering/master_tracks.py
git commit -m "$(cat <<'EOF'
feat: preset defaults for post-master tinniness WARN thresholds

post_qc_tinniness_warn_floor (0.6) and post_qc_tinniness_warn_delta
(0.10) gate the upcoming post-master spectral regression check.
Both preset-tunable so per-genre calibration is possible without a
code change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Post-QC regression check

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/_album_stages.py` (`_stage_post_qc`, around line 1663-1669 where the pass path builds the stage dict)
- Test: `tests/unit/mastering/test_post_master_spectral_regression.py` (NEW)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/mastering/test_post_master_spectral_regression.py`:

```python
"""Post-QC emits tinniness-regression WARN when mastering pushes
high_mid/mid ratio up significantly from the polished input."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers.processing import _album_stages
from handlers.processing._album_stages import MasterAlbumCtx


def _analysis_result(fname: str, tinniness: float) -> dict:
    """Minimal analyze_track result shape with just the fields that
    _stage_post_qc reads for the regression check."""
    return {
        "filename": fname,
        "lufs": -14.0,
        "peak_db": -1.5,
        "short_term_range": 6.0,
        "tinniness_ratio": tinniness,
    }


def _make_ctx(
    tmp_path: Path,
    pre_post: list[tuple[str, float, float]],
    preset: dict | None = None,
) -> MasterAlbumCtx:
    """Build a ctx populated with per-track pre/post tinniness."""
    analysis = [_analysis_result(f, p) for f, p, _ in pre_post]
    verify = [_analysis_result(f, q) for f, _, q in pre_post]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    mastered_dir = tmp_path / "mastered"
    mastered_dir.mkdir()
    # Real empty-ish files — qc_track will be mocked out anyway.
    import numpy as np
    import soundfile as sf
    rng = np.random.default_rng(0)
    mastered_files = []
    for f, _, _ in pre_post:
        path = mastered_dir / f
        sf.write(
            str(path),
            (rng.standard_normal((48000, 2)) * 0.05).astype("float64"),
            48000, subtype="PCM_24",
        )
        mastered_files.append(path)

    return MasterAlbumCtx(
        album_slug="test",
        album_dir=tmp_path,
        audio_dir=tmp_path,
        source_dir=tmp_path,
        output_dir=mastered_dir,
        wav_files=mastered_files,
        mastered_files=mastered_files,
        targets={"output_sample_rate": 48000, "output_bits": 24,
                 "target_lufs": -14.0, "ceiling_db": -1.0},
        settings={},
        effective_lufs=-14.0,
        effective_ceiling=-1.0,
        effective_highmid=0,
        effective_highs=0,
        effective_compress=2.5,
        loop=loop,
        analysis_results=analysis,
        verify_results=verify,
        effective_preset=preset or {
            "post_qc_tinniness_warn_floor": 0.6,
            "post_qc_tinniness_warn_delta": 0.10,
        },
    )


def _run_post_qc(ctx: MasterAlbumCtx) -> str | None:
    """Run _stage_post_qc with qc_track mocked to return a trivial PASS."""
    from unittest.mock import patch

    def _fake_qc(path, checks, genre):
        return {
            "filename": Path(path).name,
            "verdict": "PASS",
            "checks": {},
        }

    try:
        with patch("tools.mastering.qc_tracks.qc_track", _fake_qc):
            return ctx.loop.run_until_complete(
                _album_stages._stage_post_qc(ctx),
            )
    finally:
        ctx.loop.close()


class TestTinninessRegression:
    def test_regression_emits_warn(self, tmp_path: Path) -> None:
        ctx = _make_ctx(tmp_path, [
            ("04-regressed.wav", 0.45, 0.82),  # floor=0.6, delta=+0.37
        ])
        result = _run_post_qc(ctx)
        assert result is None
        stage = ctx.stages["post_qc"]
        assert stage["status"] == "warn"
        regressions = stage["tinniness_regressions"]
        assert len(regressions) == 1
        assert regressions[0]["filename"] == "04-regressed.wav"
        assert regressions[0]["pre_tinniness"] == pytest.approx(0.45)
        assert regressions[0]["post_tinniness"] == pytest.approx(0.82)
        assert regressions[0]["delta"] == pytest.approx(0.37)
        assert any(
            "tinniness" in w.lower() and "04-regressed" in w
            for w in ctx.warnings
        )

    def test_no_regression_stays_pass(self, tmp_path: Path) -> None:
        ctx = _make_ctx(tmp_path, [
            ("01-clean.wav", 0.30, 0.32),  # below floor, tiny delta
        ])
        result = _run_post_qc(ctx)
        assert result is None
        stage = ctx.stages["post_qc"]
        assert stage["status"] == "pass"
        assert stage.get("tinniness_regressions", []) == []

    def test_tinny_input_not_flagged_as_regression(self, tmp_path: Path) -> None:
        """Track that was already tinny pre-master shouldn't be flagged
        as a regression just because the post-master ratio is still
        tinny — the delta must also exceed threshold."""
        ctx = _make_ctx(tmp_path, [
            ("05-already-tinny.wav", 0.78, 0.80),  # above floor but delta=0.02
        ])
        result = _run_post_qc(ctx)
        stage = ctx.stages["post_qc"]
        assert stage.get("tinniness_regressions", []) == []
        assert stage["status"] == "pass"

    def test_below_floor_not_flagged(self, tmp_path: Path) -> None:
        """Ratio that grew from 0.30 to 0.50 — large delta but below the
        absolute floor, so no WARN. (Taste-level judgement: moderate
        ratios aren't audible regressions.)"""
        ctx = _make_ctx(tmp_path, [
            ("06-growth-under-floor.wav", 0.30, 0.50),
        ])
        result = _run_post_qc(ctx)
        stage = ctx.stages["post_qc"]
        assert stage.get("tinniness_regressions", []) == []
        assert stage["status"] == "pass"

    def test_preset_thresholds_are_respected(self, tmp_path: Path) -> None:
        """A loose preset with floor=0.9 should not flag a 0.82 post."""
        ctx = _make_ctx(
            tmp_path,
            [("04-regressed.wav", 0.45, 0.82)],
            preset={
                "post_qc_tinniness_warn_floor": 0.9,
                "post_qc_tinniness_warn_delta": 0.10,
            },
        )
        result = _run_post_qc(ctx)
        stage = ctx.stages["post_qc"]
        assert stage.get("tinniness_regressions", []) == []
        assert stage["status"] == "pass"

    def test_multiple_regressions_all_reported(self, tmp_path: Path) -> None:
        ctx = _make_ctx(tmp_path, [
            ("01-clean.wav",     0.30, 0.32),
            ("04-regressed.wav", 0.45, 0.82),
            ("07-regressed.wav", 0.50, 0.64),
        ])
        result = _run_post_qc(ctx)
        stage = ctx.stages["post_qc"]
        regressions = stage["tinniness_regressions"]
        assert len(regressions) == 2
        names = sorted(r["filename"] for r in regressions)
        assert names == ["04-regressed.wav", "07-regressed.wav"]
        assert stage["status"] == "warn"
```

- [ ] **Step 2: Run failing tests**

```bash
.venv/bin/pytest tests/unit/mastering/test_post_master_spectral_regression.py -v
```
Expected: every test FAILS — `tinniness_regressions` key doesn't exist on the stage dict.

- [ ] **Step 3: Implement the check in `_stage_post_qc`**

Open `_album_stages.py` at `_stage_post_qc`. The function currently ends with (around line 1663):

```python
    ctx.stages["post_qc"] = {
        "status": "pass",
        "passed": post_passed,
        "warned": post_warned,
        "failed": 0,
        "verdict": "ALL PASS" if post_warned == 0 else "WARNINGS",
    }
    return None
```

Immediately *before* this final block (i.e., after the LRA-floor check returns None implicitly by falling through), insert:

```python
    # ── Spectral regression (tinniness) guard ────────────────────────────────
    # Mastering sometimes pushes high_mid/mid ratio up — typical cause is
    # limiter-driven harmonic generation at tight ceilings, especially
    # with the electronic preset. Cross-reference pre- vs post-master
    # tinniness_ratio and WARN when both floor and delta are breached.
    preset_for_tinniness = ctx.effective_preset or {}
    warn_floor = float(
        preset_for_tinniness.get("post_qc_tinniness_warn_floor", 0.6),
    )
    warn_delta = float(
        preset_for_tinniness.get("post_qc_tinniness_warn_delta", 0.10),
    )
    pre_by_fname = {
        a["filename"]: float(a.get("tinniness_ratio", 0.0) or 0.0)
        for a in (ctx.analysis_results or [])
        if a.get("filename")
    }
    tinniness_regressions: list[dict[str, Any]] = []
    for vr in (ctx.verify_results or []):
        fname = vr.get("filename")
        if not fname or fname not in pre_by_fname:
            continue
        post_ratio = float(vr.get("tinniness_ratio", 0.0) or 0.0)
        pre_ratio = pre_by_fname[fname]
        if post_ratio > warn_floor and (post_ratio - pre_ratio) > warn_delta:
            tinniness_regressions.append({
                "filename":       fname,
                "pre_tinniness":  round(pre_ratio, 3),
                "post_tinniness": round(post_ratio, 3),
                "delta":          round(post_ratio - pre_ratio, 3),
            })
            ctx.warnings.append(
                f"Post-QC {fname}: tinniness regression — "
                f"pre={pre_ratio:.2f}, post={post_ratio:.2f} "
                f"(Δ{post_ratio - pre_ratio:+.2f}; floor={warn_floor}, "
                f"delta={warn_delta})"
            )
```

Then replace the final stage-dict builder with logic that downgrades to `"warn"` when regressions exist:

```python
    has_regressions = bool(tinniness_regressions)
    base_status = "pass"
    if has_regressions or post_warned > 0:
        base_status = "warn"
    verdict = (
        "ALL PASS"
        if not has_regressions and post_warned == 0
        else ("WARNINGS" if post_warned > 0 else "TINNINESS REGRESSION")
        if has_regressions else "WARNINGS"
    )
    ctx.stages["post_qc"] = {
        "status":                 base_status,
        "passed":                 post_passed,
        "warned":                 post_warned,
        "failed":                 0,
        "verdict":                verdict,
        "tinniness_regressions":  tinniness_regressions,
    }
    return None
```

The ternary expression above is intentionally explicit (not compact) — simplify it if you prefer an imperative form. The assertion from the tests only checks `status`, `tinniness_regressions`, and the warning text, so `verdict` phrasing is flexible.

- [ ] **Step 4: Verify tests pass**

```bash
.venv/bin/pytest tests/unit/mastering/test_post_master_spectral_regression.py -v
```
Expected: all six tests PASS.

- [ ] **Step 5: Regression-check the full post-QC suite**

```bash
.venv/bin/pytest tests/unit/mastering/ tests/integration/ -k "post_qc or master_album" -v
```
Expected: no regressions. The check is additive — `status="pass"` without regressions behaves identically to before.

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/_album_stages.py \
        tests/unit/mastering/test_post_master_spectral_regression.py
git commit -m "$(cat <<'EOF'
feat: post-master tinniness regression WARN in post_qc

Cross-references ctx.analysis_results (pre-master) with
ctx.verify_results (post-master) and emits a WARN per track where
post tinniness_ratio exceeds the floor AND grew by more than the
delta from pre. Downgrades post_qc stage status to "warn" when
regressions are found.

Does not halt — the goal is observability. Operators decide
whether to re-master with a softer preset, manually high-shelf
the regressed tracks, or accept the delivery.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: CHANGELOG + gate

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: CHANGELOG entry**

Under `[Unreleased]`:

```markdown
### Added
- Post-QC spectral regression guard — WARN when mastering pushed a
  track's `tinniness_ratio` (high_mid/mid) above 0.6 AND the ratio
  grew by more than +0.10 from pre-master. Preset-tunable via
  `post_qc_tinniness_warn_floor` and `post_qc_tinniness_warn_delta`.
  Flags the regressed track(s) in `ctx.stages["post_qc"]
  ["tinniness_regressions"]` and in `ctx.warnings`.
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'EOF'
chore: CHANGELOG entry for post-master spectral regression WARN

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

Branch name: `feat/post-master-spectral-regression-guard` off `develop`.

PR body should:
- Reference bug #6 (track 04 landed at tinniness_ratio 0.82, track 07 at 0.64 after the halt-report album).
- Note the check is observability-only (no halt), and the thresholds are preset-tunable for genre calibration.
- Flag that if this WARN fires systematically on the electronic preset, that's a preset-tuning follow-up, not a bug in this check.

---

## Self-Review Checklist

1. **Spec coverage:** Bug #6 (tinny regression on tracks that polish high-tamed) is detected by this plan via post>pre tinniness_ratio. ✅

2. **No placeholders:** All test and implementation code is complete.

3. **Type consistency:** `tinniness_regressions` is `list[dict[str, Any]]` with keys `filename: str, pre_tinniness: float, post_tinniness: float, delta: float`. Matches between implementation and tests.

4. **Interaction with other plans:**
   - Plan A's verification warn-fallback keeps `ctx.verify_results` populated on warn paths, so this check runs for unrecoverable tracks too (their tinniness is still informative).
   - Plan B's per-track ADM loop doesn't change what tinniness looks like — it changes *which* tracks are tightened. The check is orthogonal.

5. **Observability vs gating:** Chose observability. A taste-level threshold shouldn't halt a pipeline; operators make the call based on the sidecar / WARN stream.
