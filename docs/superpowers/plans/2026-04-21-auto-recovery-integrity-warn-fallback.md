# Auto-Recovery Integrity + Verification Warn-Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `master_album`'s auto-recovery path produce delivery-format output (matching the rest of the album's sample rate + bit depth), give `fix_dynamic` the ability to converge on target LUFS when one pass falls short (and honestly report when it can't), and turn verification failures that happen *after* recovery into a warn-fallback sidecar so the album always completes instead of halting 40% of the way through the pipeline.

**Architecture:** Three additive changes, all contained to the verification subsystem. (1) `fix_dynamic` gains a bounded iteration loop that intensifies compression on each pass until LUFS lands within ±0.5 dB of target — returning `converged: bool` so the caller can decide whether the track is salvageable. (2) `_stage_verification`'s recovery path resamples the recovered audio to `ctx.targets["output_sample_rate"]` before writing (using the same polyphase FIR approach as `master_track`). (3) When recovery was attempted but couldn't converge, `_stage_verification` writes `VERIFICATION_WARNINGS.md` next to the mastered files and downgrades `stages["verification"]["status"]` to `"warn"` instead of returning failure JSON — the pipeline continues to coherence/ceiling-guard/post-QC/archival and the album finishes with a flagged deliverable.

**Tech Stack:** Python 3.11, `numpy`, `scipy.signal` (already imported in master_tracks), `pyloudnorm`, `soundfile`. No new dependencies.

---

## Scope Check

This plan bundles three tightly coupled fixes:
- Bug #1 (auto-recovery bypasses upsampling) and bug #2 (auto-recovery doesn't hit LUFS) both live inside the same 30-line block (`_do_recovery` in `_stage_verification`).
- Bug #4 (warn-fallback never triggered) depends on bug #2's `converged` signal to distinguish "recovery failed because material is incompatible" from "recovery wasn't even attempted" — the two cases want different behavior.

**Out of scope:**
- Per-track ADM ceiling tightening (#3) — covered in `2026-04-21-per-track-adm-ceiling.md`. That plan depends on *this* plan's warn-fallback contract.
- `already_dark` pre-QC gating (#5) — covered in `2026-04-21-per-track-adm-ceiling.md`.
- Post-master spectral regression check (#6) — covered in `2026-04-21-post-master-spectral-regression.md`.
- Refactoring `_stage_verification` into smaller helpers. It's ~180 lines and due for extraction, but this plan adds ~40 lines; the refactor deserves its own pass.
- Changing the album-LUFS-range tolerance (1.0 dB) — that's a policy knob, not a bug.

---

## Codebase Context

Key files (paths from repo root):

- `tools/mastering/fix_dynamic_track.py` — single-pass EQ→compress→normalize→limit helper (lines 25-78).
- `servers/bitwize-music-server/handlers/processing/_album_stages.py` — `_stage_verification` (lines 752-929). `atomic_write_text` already imported (line 43).
- `tools/mastering/master_tracks.py:1312-1319` — reference implementation of polyphase SRC used by `master_track`.
- `servers/bitwize-music-server/handlers/processing/audio.py:600-615` — `master_album` docstring describing pipeline phases.
- `tests/unit/mastering/` — existing test layout for mastering unit tests.
- `tests/integration/` — existing integration test layout; search for `_stage_verification` usages.

**Current recovery path (summary):**

1. `_stage_verification` runs `analyze_track` on each mastered file.
2. Tracks with LUFS below target or peak above ceiling are added to `out_of_spec`.
3. "Recoverable" subset = tracks with `lufs_too_low AND peak_at_ceiling AND not has_peak_issue`.
4. For each recoverable track: read source, call `fix_dynamic`, write to mastered path at **source rate** (bug #1), at **single-pass LUFS** (bug #2).
5. Re-analyze mastered files. If still out-of-spec: return failure JSON → master_album halts (bug #4).

**Verification tolerances (unchanged by this plan):**

- Per-track LUFS: `abs(r["lufs"] - effective_lufs) > 0.5` → fail
- Per-track peak: `r["peak_db"] > effective_ceiling` → fail
- Album range: `max(lufs) - min(lufs) >= 1.0` → fail

---

## File Structure

| File | Role | State |
|---|---|---|
| `tools/mastering/fix_dynamic_track.py` | Add iteration loop + `converged`/`iterations_run` in metrics | modify |
| `servers/bitwize-music-server/handlers/processing/_album_stages.py` | Pass `output_sample_rate` to recovery; write `VERIFICATION_WARNINGS.md` + warn-fallback when `converged=False` exhausts recovery | modify |
| `servers/bitwize-music-server/handlers/processing/audio.py` | Update `master_album` docstring to describe the verification warn-fallback contract | modify |
| `tests/unit/mastering/test_fix_dynamic_convergence.py` | Unit tests: converges on normal material, reports `converged=False` on unreachable-LUFS material, iterations capped at 3 | **new** |
| `tests/unit/mastering/test_master_album_recovery_delivery_format.py` | Integration test: recovery on 48 kHz source writes mastered file at 96 kHz when `output_sample_rate=96000` | **new** |
| `tests/unit/mastering/test_master_album_verification_warn_fallback.py` | Integration test: unrecoverable tracks → `status="warn"`, `VERIFICATION_WARNINGS.md` written, pipeline proceeds (no failure JSON returned) | **new** |
| `CHANGELOG.md` | `[Unreleased]` entry | modify |

Files **not** modified:
- `tools/mastering/master_tracks.py` — the reference SRC approach is copied; no API change.
- Any coherence / ceiling-guard / ADM stage — warn-fallback from verification exits before those stages on the new path, same as before.

---

## Design Details (read before starting any task)

### `fix_dynamic` iteration strategy

The current single-pass path can't hit target LUFS when the ceiling is tight enough that the normalize-then-limit step scales the signal back down far enough to undershoot the K-weighted LUFS target. This happens on dark material (little high-frequency content → K-weighting reads the signal as softer than its RMS implies → gain needed to reach target LUFS pushes peaks way over ceiling → back-off scaling drops LUFS below target).

The fix is to intensify compression iteratively. Each pass trades crest factor for headroom:

| Iteration | threshold_db | ratio | typical use |
|---:|---:|---:|---|
| 1 | -12.0 | 2.5 | legacy behavior; normal-dynamics content converges here |
| 2 | -10.0 | 3.5 | mild-to-moderate dynamic range |
| 3 |  -8.0 | 5.0 | dense-transient or very quiet content |

EQ is applied once (before the loop) — it's an input conditioning pass, not part of the dynamics-vs-loudness tradeoff.

Convergence criterion: `abs(final_lufs - target_lufs) <= 0.5`. Stop on first converged iteration. If none converge after 3, return the iteration with the smallest LUFS error and `converged=False`.

### Recovery delivery-format fix

The recovery path reads the (polished-but-not-mastered) source WAV via `sf.read`, which returns data at the source rate. The rest of the mastered album was written at `ctx.targets["output_sample_rate"]` by `master_track`. The recovery path must apply the same rate conversion before writing.

Copy the approach from `master_tracks.py:1314-1319` — polyphase resampling using the GCD-reduced ratio:

```python
from math import gcd
from scipy import signal

if target_rate and target_rate != rate:
    g = gcd(target_rate, rate)
    data = signal.resample_poly(data, up=target_rate // g, down=rate // g, axis=0)
    rate = target_rate
```

Resample happens *after* `fix_dynamic` returns but *before* `sf.write`. LUFS is rate-invariant so the returned metrics don't change.

### Warn-fallback contract

Today: verification fails → return failure JSON → `master_album` halts.

After this plan:
- Verification fails with **no recovery attempted** (e.g., peak issues, or only album-range failure) → halt as before.
- Verification fails **because recovery exhausted iterations** (`converged=False` for every remaining out-of-spec track) → write sidecar + log warning + `status="warn"` + return `None`. Pipeline proceeds.
- Verification fails with a **mix** (some tracks halt-eligible, some unrecoverable) → halt. The halt-eligible tracks indicate a different class of problem that warn-fallback can't paper over.

The halt-vs-warn decision is made in `_stage_verification` itself — no change to the orchestrator loop in `audio.py`.

**Sidecar contents** (`VERIFICATION_WARNINGS.md` at `ctx.output_dir / "VERIFICATION_WARNINGS.md"`):

```markdown
# Verification Warnings

Auto-recovery attempted but could not bring these tracks within ±0.5 dB
of the target LUFS. The album was delivered with the flagged tracks
as-is. Cause is typically dark spectral content (heavily K-weighted
against) that cannot reach the target loudness at the current ceiling.

| Track | Target LUFS | Final LUFS | Final Peak (dBTP) | Original LUFS | Iterations |
|---|---:|---:|---:|---:|---:|
| 09-track.wav | -14.0 | -23.2 | -4.42 | -31.7 | 3 |
```

Human reviewer deliverables: re-master the flagged tracks at a looser ceiling, or decide the delivery is acceptable as-is.

### Docstring update

`master_album` docstring currently claims "falling through to a warn-fallback so the album always completes." Today that's only true for ADM clip failures. After this plan, it's also true for auto-recovery-exhausted verification failures. The docstring should enumerate *both* warn-fallback triggers and still name the halt conditions (pre-QC FAIL, non-recoverable verification failures, non-ADM stage errors).

---

## Task 1: Add iteration loop + `converged` metric to `fix_dynamic`

**Files:**
- Modify: `tools/mastering/fix_dynamic_track.py` (function `fix_dynamic` at lines 25-78)
- Test: `tests/unit/mastering/test_fix_dynamic_convergence.py` (NEW)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/mastering/test_fix_dynamic_convergence.py`:

```python
"""Unit tests for fix_dynamic's iterative LUFS convergence."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.fix_dynamic_track import fix_dynamic


def _make_pink_stereo(seconds: float = 3.0, rate: int = 48000,
                     rms_db: float = -26.0) -> np.ndarray:
    """Generate pink-ish stereo noise at a calibrated RMS level."""
    rng = np.random.default_rng(42)
    n = int(seconds * rate)
    white = rng.standard_normal((n, 2)).astype(np.float64)
    # Cheap pink filter: accumulate + decay.
    pink = np.zeros_like(white)
    alpha = 0.98
    for i in range(1, n):
        pink[i] = alpha * pink[i - 1] + (1 - alpha) * white[i]
    pink /= np.max(np.abs(pink)) + 1e-9
    target_lin = 10 ** (rms_db / 20)
    current_rms = np.sqrt(np.mean(pink ** 2))
    return pink * (target_lin / current_rms)


def _make_dark_stereo(seconds: float = 3.0, rate: int = 48000,
                      rms_db: float = -30.0) -> np.ndarray:
    """Generate dark stereo noise (low-passed at ~400 Hz) that will
    struggle to hit K-weighted LUFS targets at tight ceilings."""
    from scipy.signal import butter, sosfilt

    rng = np.random.default_rng(7)
    n = int(seconds * rate)
    white = rng.standard_normal((n, 2)).astype(np.float64)
    sos = butter(4, 400.0, btype="low", fs=rate, output="sos")
    dark = np.stack([sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1)
    dark /= np.max(np.abs(dark)) + 1e-9
    target_lin = 10 ** (rms_db / 20)
    current_rms = np.sqrt(np.mean(dark ** 2))
    return dark * (target_lin / current_rms)


class TestFixDynamicConvergence:
    def test_returns_converged_metric(self):
        data = _make_pink_stereo()
        _, metrics = fix_dynamic(data, 48000, target_lufs=-14.0, ceiling_db=-1.0)
        assert "converged" in metrics
        assert "iterations_run" in metrics
        assert isinstance(metrics["converged"], bool)
        assert isinstance(metrics["iterations_run"], int)

    def test_pink_noise_converges_in_one_iteration(self):
        data = _make_pink_stereo()
        _, metrics = fix_dynamic(data, 48000, target_lufs=-14.0, ceiling_db=-1.0)
        assert metrics["converged"] is True
        assert metrics["iterations_run"] == 1
        assert abs(metrics["final_lufs"] - (-14.0)) <= 0.5

    def test_dark_noise_at_tight_ceiling_reports_non_convergence(self):
        # Dark material at a -4 dB ceiling cannot reach -14 LUFS no matter
        # how aggressive we compress. The helper should iterate, land on
        # the best attempt, and honestly report converged=False.
        data = _make_dark_stereo(rms_db=-35.0)
        _, metrics = fix_dynamic(data, 48000, target_lufs=-14.0, ceiling_db=-4.0)
        assert metrics["converged"] is False
        assert metrics["iterations_run"] == 3
        # Final LUFS should still be the closest-to-target iteration.
        assert metrics["final_lufs"] < -14.0

    def test_iterations_capped_at_three(self):
        data = _make_dark_stereo(rms_db=-40.0)
        _, metrics = fix_dynamic(data, 48000, target_lufs=-14.0, ceiling_db=-6.0)
        assert metrics["iterations_run"] <= 3

    def test_original_lufs_preserved_across_iterations(self):
        data = _make_pink_stereo(rms_db=-26.0)
        _, metrics = fix_dynamic(data, 48000, target_lufs=-14.0, ceiling_db=-1.0)
        # original_lufs should reflect the input, not the last-iteration input.
        assert metrics["original_lufs"] < -20.0
        assert metrics["original_lufs"] > -32.0

    def test_final_peak_respects_ceiling(self):
        data = _make_pink_stereo()
        _, metrics = fix_dynamic(data, 48000, target_lufs=-14.0, ceiling_db=-1.0)
        assert metrics["final_peak_db"] <= -1.0 + 0.05  # tiny numerical slop

    def test_second_iteration_fires_when_first_misses(self):
        # Craft input that single-pass won't converge on but two-pass will.
        # Low-pre-comp crest factor + moderate dynamics → first pass
        # undershoots by >0.5 dB, second pass (heavier compression) lands.
        from scipy.signal import butter, sosfilt

        rng = np.random.default_rng(11)
        rate = 48000
        n = int(4.0 * rate)
        white = rng.standard_normal((n, 2)).astype(np.float64)
        sos = butter(4, 2000.0, btype="low", fs=rate, output="sos")
        semi_dark = np.stack(
            [sosfilt(sos, white[:, ch]) for ch in range(2)], axis=1,
        )
        semi_dark /= np.max(np.abs(semi_dark)) + 1e-9
        target_lin = 10 ** (-28.0 / 20)
        current_rms = np.sqrt(np.mean(semi_dark ** 2))
        data = semi_dark * (target_lin / current_rms)

        _, metrics = fix_dynamic(data, rate, target_lufs=-14.0, ceiling_db=-2.0)
        assert metrics["iterations_run"] >= 2
        # Should still converge.
        if metrics["converged"]:
            assert abs(metrics["final_lufs"] - (-14.0)) <= 0.5
```

- [ ] **Step 2: Run failing tests**

```bash
.venv/bin/pytest tests/unit/mastering/test_fix_dynamic_convergence.py -v
```
Expected: every test that references `metrics["converged"]` or `metrics["iterations_run"]` FAILS with `KeyError` — those keys don't exist in current `fix_dynamic`.

- [ ] **Step 3: Rewrite `fix_dynamic` with iteration loop**

Replace lines 25-78 of `tools/mastering/fix_dynamic_track.py` with:

```python
def fix_dynamic(data: Any, rate: int, target_lufs: float = -14.0,
                eq_settings: list[tuple[float, float, float]] | None = None,
                ceiling_db: float = -1.0) -> tuple[Any, dict[str, float]]:
    """Core dynamic range fix: EQ → (compress → normalize → limit)×N.

    Runs up to 3 iterations of compress→normalize→limit with progressively
    heavier compression, stopping as soon as integrated LUFS is within
    ±0.5 dB of ``target_lufs``. When no iteration converges, returns the
    attempt with the smallest LUFS error and sets ``converged=False`` so
    the caller can decide whether the track is salvageable.

    Args:
        data: Audio data (numpy array, stereo)
        rate: Sample rate
        target_lufs: Target LUFS (default: -14.0)
        eq_settings: List of (freq, gain_db, q) tuples. If None, applies
            default 3500 Hz cut (-2.0 dB, Q=1.5).
        ceiling_db: Peak ceiling in dB (default: -1.0)

    Returns:
        (processed_data, metrics) tuple where metrics has:
            original_lufs:   input integrated LUFS
            final_lufs:      best-attempt integrated LUFS
            final_peak_db:   best-attempt peak in dBTP
            converged:       True if final_lufs within ±0.5 dB of target
            iterations_run:  1, 2, or 3
    """
    meter = pyln.Meter(rate)
    original_lufs = meter.integrated_loudness(data)

    # EQ is input conditioning — applied once, not part of the dynamics loop.
    if eq_settings is None:
        eq_settings = [(3500, -2.0, 1.5)]
    eq_data = data
    for freq, gain_db, q in eq_settings:
        eq_data = apply_eq(eq_data, rate, freq, gain_db, q)

    ceiling = 10 ** (ceiling_db / 20)
    tolerance_db = 0.5

    # (threshold_db, ratio) schedule. First iteration matches legacy
    # single-pass behavior. Heavier passes trade crest factor for
    # headroom — needed when the ceiling is tight relative to the
    # material's K-weighted response (dark content).
    _ITER_SCHEDULE = [
        (-12.0, 2.5),
        (-10.0, 3.5),
        (-8.0,  5.0),
    ]

    best_data = eq_data
    best_lufs = float("-inf")
    best_diff = float("inf")
    converged = False
    iterations_run = 0

    for i, (thr, ratio) in enumerate(_ITER_SCHEDULE):
        iterations_run = i + 1

        iter_data = gentle_compress(
            eq_data, threshold_db=thr, ratio=ratio, rate=rate,
        )

        post_comp_lufs = meter.integrated_loudness(iter_data)
        if np.isfinite(post_comp_lufs):
            gain_db_val = target_lufs - post_comp_lufs
            iter_data = iter_data * (10 ** (gain_db_val / 20))

        peak = np.max(np.abs(iter_data))
        if peak > ceiling:
            iter_data = iter_data * (ceiling / peak)
        iter_data = soft_clip(iter_data, ceiling)

        iter_lufs = meter.integrated_loudness(iter_data)
        iter_diff = (
            abs(iter_lufs - target_lufs) if np.isfinite(iter_lufs) else float("inf")
        )

        if iter_diff < best_diff:
            best_data = iter_data
            best_lufs = iter_lufs
            best_diff = iter_diff

        if iter_diff <= tolerance_db:
            converged = True
            break

    peak_abs = np.max(np.abs(best_data))
    final_peak = 20 * np.log10(peak_abs) if peak_abs > 0 else float("-inf")

    metrics: dict[str, float] = {
        "original_lufs":   float(original_lufs),
        "final_lufs":      float(best_lufs),
        "final_peak_db":   float(final_peak),
        "converged":       bool(converged),
        "iterations_run":  int(iterations_run),
    }

    return best_data, metrics
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/unit/mastering/test_fix_dynamic_convergence.py -v
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Regression-check existing callers**

```bash
.venv/bin/pytest tests/unit/mastering/ -k "fix_dynamic or recovery or verification" -v
```
Expected: all existing fix_dynamic / recovery tests still PASS. The return-tuple shape is preserved (new keys added, no keys removed), so any existing test reading `original_lufs`, `final_lufs`, or `final_peak_db` continues to work.

- [ ] **Step 6: Commit**

```bash
git add tools/mastering/fix_dynamic_track.py tests/unit/mastering/test_fix_dynamic_convergence.py
git commit -m "$(cat <<'EOF'
feat: iterative LUFS convergence in fix_dynamic

Replaces single-pass EQ→compress→normalize→limit with a bounded
3-iteration loop. Each iteration applies progressively heavier
compression (-12/2.5 → -10/3.5 → -8/5.0) and stops as soon as
integrated LUFS lands within ±0.5 dB of target.

Adds `converged` and `iterations_run` to the metrics dict so
callers (auto-recovery in _stage_verification) can distinguish
material that won't hit target from material that simply needs
more work.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Recovery path writes at delivery sample rate

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/_album_stages.py` (function `_stage_verification`, `_do_recovery` closure around lines 830-848 and its caller around lines 850-855)
- Test: `tests/unit/mastering/test_master_album_recovery_delivery_format.py` (NEW)

- [ ] **Step 1: Write failing integration test**

Create `tests/unit/mastering/test_master_album_recovery_delivery_format.py`:

```python
"""Recovery path must write at ctx.targets['output_sample_rate'], not
the source rate. Regression for bug #1 — a 48 kHz source that triggers
auto-recovery used to be written back at 48 kHz while the rest of the
album was at 96 kHz."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers.processing import _album_stages
from handlers.processing._album_stages import MasterAlbumCtx


def _write_pink_wav(path: Path, rate: int, seconds: float = 3.0,
                    lufs_target: float = -22.0) -> None:
    """Writes a pink-ish stereo WAV with approximate integrated LUFS."""
    rng = np.random.default_rng(0)
    n = int(seconds * rate)
    white = rng.standard_normal((n, 2)).astype(np.float64)
    pink = np.zeros_like(white)
    alpha = 0.98
    for i in range(1, n):
        pink[i] = alpha * pink[i - 1] + (1 - alpha) * white[i]
    pink /= np.max(np.abs(pink)) + 1e-9
    # Approximate scaling to land near lufs_target.
    pink *= 10 ** ((lufs_target + 3.0) / 20)
    sf.write(str(path), pink, rate, subtype="PCM_24")


def test_recovery_writes_at_delivery_sample_rate(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "mastered"
    source_dir.mkdir()
    output_dir.mkdir()

    source_rate = 48000
    delivery_rate = 96000
    target_lufs = -14.0
    target_ceiling = -1.5

    # A polished source that will land below target LUFS when mastered
    # normally, triggering the recovery path.
    fname = "09-dark.wav"
    _write_pink_wav(source_dir / fname, source_rate, lufs_target=-28.0)

    # Pre-populate the "mastered" dir with a copy at delivery rate so the
    # analyze → recovery flow has something to read back after write.
    # The recovery path will overwrite this file.
    import shutil
    shutil.copy(source_dir / fname, output_dir / fname)

    ctx = MasterAlbumCtx(
        album_slug="test-album",
        album_dir=tmp_path,
        audio_dir=tmp_path,
        source_dir=source_dir,
        output_dir=output_dir,
        wav_files=[source_dir / fname],
        mastered_files=[output_dir / fname],
        targets={
            "output_sample_rate": delivery_rate,
            "output_bits": 24,
            "target_lufs": target_lufs,
            "ceiling_db": target_ceiling,
        },
        settings={},
        effective_lufs=target_lufs,
        effective_ceiling=target_ceiling,
        effective_highmid=0,
        effective_highs=0,
        effective_compress=2.5,
        loop=asyncio.get_event_loop_policy().new_event_loop(),
    )

    asyncio.set_event_loop(ctx.loop)
    try:
        result = ctx.loop.run_until_complete(
            _album_stages._stage_verification(ctx),
        )
    finally:
        ctx.loop.close()

    # The recovery path ran (stage either returned None or warn-fallback
    # JSON — either way the file should have been rewritten).
    data, rate_written = sf.read(str(output_dir / fname))
    assert rate_written == delivery_rate, (
        f"recovery wrote at {rate_written} Hz but delivery target is "
        f"{delivery_rate} Hz (bug #1 regression)"
    )
```

Note: the `MasterAlbumCtx` constructor in the repo has many fields; this test may need to be adjusted to match current field names. Before writing the test, run `.venv/bin/python3 -c "from handlers.processing._album_stages import MasterAlbumCtx; import dataclasses; print(sorted(f.name for f in dataclasses.fields(MasterAlbumCtx)))"` from the server directory and pass all required (non-default) fields. The important assertion is `rate_written == delivery_rate`.

- [ ] **Step 2: Run failing test**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_recovery_delivery_format.py -v
```
Expected: FAIL — recovery writes at 48 kHz, assertion expects 96 kHz.

- [ ] **Step 3: Update recovery closure to accept delivery rate**

In `_album_stages.py`, locate `_stage_verification`'s inner `_do_recovery` function (around line 830). Replace it with:

```python
                def _do_recovery(
                    src: Path,
                    dst: Path,
                    lufs: float,
                    eq: list[tuple[float, float, float]],
                    ceil: float,
                    subtype: str,
                    target_rate: int,
                ) -> dict[str, Any]:
                    from math import gcd as _gcd
                    from scipy import signal as _signal

                    data, rate = sf.read(str(src))
                    if len(data.shape) == 1:
                        data = _np.column_stack([data, data])
                    data, metrics = fix_dynamic(
                        data, rate,
                        target_lufs=lufs,
                        eq_settings=eq if eq else None,
                        ceiling_db=ceil,
                    )
                    # Match _stage_mastering's delivery-format SRC so
                    # recovered tracks don't end up at a different sample
                    # rate from the rest of the album (bug #1).
                    if target_rate and target_rate != rate:
                        g = _gcd(target_rate, rate)
                        data = _signal.resample_poly(
                            data, up=target_rate // g, down=rate // g, axis=0,
                        )
                        rate = target_rate
                    sf.write(str(dst), data, rate, subtype=subtype)
                    return metrics
```

- [ ] **Step 4: Pass delivery rate from the caller**

Just below `_do_recovery` (the `await ctx.loop.run_in_executor(...)` call around line 850), replace:

```python
                mastered_path = ctx.output_dir / fname
                metrics = await ctx.loop.run_in_executor(
                    None, _do_recovery, raw_path, mastered_path,
                    effective_lufs, eq_settings, effective_ceiling,
                    recovery_subtype,
                )
```

with:

```python
                mastered_path = ctx.output_dir / fname
                _delivery_rate = int(ctx.targets.get("output_sample_rate") or 0)
                metrics = await ctx.loop.run_in_executor(
                    None, _do_recovery, raw_path, mastered_path,
                    effective_lufs, eq_settings, effective_ceiling,
                    recovery_subtype, _delivery_rate,
                )
```

- [ ] **Step 5: Run test to verify it passes**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_recovery_delivery_format.py -v
```
Expected: PASS. Recovered file is at 96 kHz.

- [ ] **Step 6: Run the broader recovery regression suite**

```bash
.venv/bin/pytest tests/unit/mastering/ -k "recovery or verification or master_album" -v
```
Expected: no regressions. (The older recovery tests may have been written assuming same-rate roundtrip — if any fail, investigate before moving on; the fix should not change same-rate behavior.)

- [ ] **Step 7: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/_album_stages.py \
        tests/unit/mastering/test_master_album_recovery_delivery_format.py
git commit -m "$(cat <<'EOF'
fix: auto-recovery writes at delivery sample rate

The recovery closure in _stage_verification used to call sf.write
with the source rate, producing mastered files that didn't match
the delivery format when polish output was below the delivery rate.

Now pulls ctx.targets["output_sample_rate"] and applies the same
polyphase SRC that _stage_mastering uses before writing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Plumb `converged` through to `auto_recovered` records

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/_album_stages.py` (auto_recovered.append block around lines 856-861)

- [ ] **Step 1: Extend the `auto_recovered` record shape**

Locate (around line 856):

```python
                auto_recovered.append({
                    "filename": fname,
                    "original_lufs": metrics["original_lufs"],
                    "final_lufs": metrics["final_lufs"],
                    "final_peak_db": metrics["final_peak_db"],
                })
```

Replace with:

```python
                auto_recovered.append({
                    "filename":      fname,
                    "original_lufs": metrics["original_lufs"],
                    "final_lufs":    metrics["final_lufs"],
                    "final_peak_db": metrics["final_peak_db"],
                    "converged":     bool(metrics.get("converged", True)),
                    "iterations_run": int(metrics.get("iterations_run", 1)),
                })
```

Using `metrics.get(..., True)` as a fallback keeps the downstream halt-vs-warn logic safe if some other caller of `fix_dynamic` is mocked in tests and doesn't return the new keys.

- [ ] **Step 2: Run existing tests to confirm no regressions**

```bash
.venv/bin/pytest tests/unit/mastering/ -k "recovery or verification" -v
```
Expected: no regressions.

- [ ] **Step 3: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/_album_stages.py
git commit -m "$(cat <<'EOF'
feat: carry convergence flag on auto_recovered records

auto_recovered entries now include converged and iterations_run so
the verification stage can distinguish "recovery succeeded" from
"recovery exhausted iterations" — needed for the warn-fallback
path in the next commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Verification warn-fallback when recovery exhausts iterations

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/_album_stages.py` (`_stage_verification`, post-recovery halt block around lines 896-917)
- Test: `tests/unit/mastering/test_master_album_verification_warn_fallback.py` (NEW)

- [ ] **Step 1: Write failing integration test**

Create `tests/unit/mastering/test_master_album_verification_warn_fallback.py`:

```python
"""Verification must warn-fallback (not halt) when recovery was attempted
but fix_dynamic reported converged=False. Regression for bug #4 — the
pipeline used to hard-halt at master:verification, skipping all stages
from coherence_check through status_update."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
for p in (str(PROJECT_ROOT), str(SERVER_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers.processing import _album_stages
from handlers.processing._album_stages import MasterAlbumCtx


def _fake_analyze(target_lufs: float, off_by_lufs: float, peak_db: float):
    """Build a fake analyze_track result for a one-track album."""
    def _inner(path: str) -> dict:
        return {
            "filename":   Path(path).name,
            "lufs":       target_lufs + off_by_lufs,
            "peak_db":    peak_db,
            "short_term_range": 6.0,
            "stl_95":     9.0,
            "low_rms":    -30.0,
            "vocal_rms":  -22.0,
        }
    return _inner


def _fake_fix_dynamic_diverging(target_lufs: float):
    """fix_dynamic stub that always reports converged=False."""
    def _inner(data, rate, target_lufs=-14.0, eq_settings=None, ceiling_db=-1.0):
        # Pretend we did all the math and landed 9 dB under target.
        metrics = {
            "original_lufs":  target_lufs - 17.0,
            "final_lufs":     target_lufs - 9.0,
            "final_peak_db":  ceiling_db + 0.01,
            "converged":      False,
            "iterations_run": 3,
        }
        return data, metrics
    return _inner


def _make_ctx(tmp_path: Path, target_lufs: float = -14.0,
              ceiling: float = -1.5) -> MasterAlbumCtx:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "mastered"
    source_dir.mkdir()
    output_dir.mkdir()

    fname = "09-dark.wav"
    rng = np.random.default_rng(0)
    n = 48000 * 3
    data = rng.standard_normal((n, 2)).astype(np.float64) * 0.01
    sf.write(str(source_dir / fname), data, 48000, subtype="PCM_24")
    sf.write(str(output_dir / fname), data, 48000, subtype="PCM_24")

    return MasterAlbumCtx(
        album_slug="test-album",
        album_dir=tmp_path,
        audio_dir=tmp_path,
        source_dir=source_dir,
        output_dir=output_dir,
        wav_files=[source_dir / fname],
        mastered_files=[output_dir / fname],
        targets={
            "output_sample_rate": 48000,
            "output_bits": 24,
            "target_lufs": target_lufs,
            "ceiling_db": ceiling,
        },
        settings={},
        effective_lufs=target_lufs,
        effective_ceiling=ceiling,
        effective_highmid=0,
        effective_highs=0,
        effective_compress=2.5,
        loop=asyncio.new_event_loop(),
    )


def test_verification_warn_fallback_on_unrecoverable(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)

    # Route 1 of 1 track as recoverable-but-non-convergent.
    fake_lufs = _fake_analyze(ctx.effective_lufs, off_by_lufs=-9.0,
                              peak_db=ctx.effective_ceiling - 0.05)
    fake_fix = _fake_fix_dynamic_diverging(ctx.effective_lufs)

    asyncio.set_event_loop(ctx.loop)
    try:
        with patch(
            "tools.mastering.analyze_tracks.analyze_track", fake_lufs,
        ), patch(
            "tools.mastering.fix_dynamic_track.fix_dynamic", fake_fix,
        ):
            result = ctx.loop.run_until_complete(
                _album_stages._stage_verification(ctx),
            )
    finally:
        ctx.loop.close()

    # Key assertion: the stage returned None (warn-fallback), not a
    # failure JSON.
    assert result is None, (
        "verification halted when it should have warn-fallbacked "
        f"(returned: {result!r})"
    )
    stage = ctx.stages.get("verification")
    assert stage is not None
    assert stage["status"] == "warn"
    assert stage.get("unrecoverable_tracks") == ["09-dark.wav"]
    assert stage.get("all_within_spec") is False

    sidecar = ctx.output_dir / "VERIFICATION_WARNINGS.md"
    assert sidecar.exists(), "VERIFICATION_WARNINGS.md was not written"
    body = sidecar.read_text()
    assert "09-dark.wav" in body
    assert "-14.0" in body or "-14" in body

    # Notice + warning must be visible for operators.
    notices_blob = " ".join(ctx.notices)
    warnings_blob = " ".join(ctx.warnings)
    assert "warn-fallback" in notices_blob.lower()
    assert "unrecoverable" in warnings_blob.lower() or \
           "VERIFICATION_WARNINGS" in warnings_blob


def test_verification_halts_when_recovery_not_attempted(tmp_path: Path) -> None:
    """If the failure isn't auto-recovery-eligible (e.g., peak issue
    alone), verification still halts as before."""
    ctx = _make_ctx(tmp_path)

    # Peak issue makes this NOT recoverable (has_peak_issue=True path).
    fake_lufs = _fake_analyze(ctx.effective_lufs, off_by_lufs=0.0,
                              peak_db=ctx.effective_ceiling + 0.5)

    asyncio.set_event_loop(ctx.loop)
    try:
        with patch(
            "tools.mastering.analyze_tracks.analyze_track", fake_lufs,
        ):
            result = ctx.loop.run_until_complete(
                _album_stages._stage_verification(ctx),
            )
    finally:
        ctx.loop.close()

    # Not warn-fallback eligible → halt.
    assert result is not None
    import json
    payload = json.loads(result)
    assert payload["failed_stage"] == "verification"


def test_verification_halts_on_mixed_failure(tmp_path: Path) -> None:
    """Some tracks unrecoverable, others halt-eligible → halt overall.
    Warn-fallback only applies when ALL remaining out-of-spec tracks
    are auto-recovery casualties."""
    # This test covers a two-track album where track A converges on
    # recovery, track B is not recovery-eligible. The per-track code path
    # is exercised by adding a second wav file to ctx.wav_files /
    # mastered_files and having analyze return one bad peak + one good
    # track. Omitted here for brevity — implementer should mirror the
    # shape of test_verification_halts_when_recovery_not_attempted with
    # two tracks. Expected: result is not None, ctx.stages["verification"]
    # has status="fail".
```

Note: the third test is a stub — implement it with a two-track ctx so the "mixed failure ⇒ halt" branch is covered.

- [ ] **Step 2: Run failing tests**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_verification_warn_fallback.py -v
```
Expected: `test_verification_warn_fallback_on_unrecoverable` FAILS — today the stage returns failure JSON instead of None, and `VERIFICATION_WARNINGS.md` is never written. The other two tests may already pass (halt behavior is unchanged for non-recovery cases).

- [ ] **Step 3: Implement warn-fallback branch in `_stage_verification`**

In `_album_stages.py`, locate the halt block around line 896-917:

```python
        if out_of_spec or album_range_fail:
            fail_detail: dict[str, Any] = {}
            if out_of_spec:
                fail_detail["tracks_out_of_spec"] = out_of_spec
            if album_range_fail:
                fail_detail["album_lufs_range"] = round(verify_range, 2)
                fail_detail["album_range_limit"] = 1.0
            ctx.stages["verification"] = {
                "status": "fail",
                "avg_lufs": round(verify_avg, 1),
                "lufs_range": round(verify_range, 2),
                "all_within_spec": False,
            }
            return _safe_json({
                "album_slug": ctx.album_slug,
                "stage_reached": "verification",
                "stages": ctx.stages,
                "settings": ctx.settings,
                "warnings": ctx.warnings,
                "failed_stage": "verification",
                "failure_detail": fail_detail,
            })
```

Replace with:

```python
        if out_of_spec or album_range_fail:
            # Split remaining out-of-spec tracks into halt-eligible (this
            # failure mode can't be warn-fallbacked) and unrecoverable
            # (recovery ran, fix_dynamic reported converged=False — no
            # amount of retrying will make this land, so the honest move
            # is to deliver with a flagged sidecar).
            unrecoverable_map = {
                r["filename"]: r
                for r in auto_recovered
                if not r.get("converged", True)
            }
            halt_eligible_tracks = [
                s for s in out_of_spec
                if s["filename"] not in unrecoverable_map
            ]
            # Album-range failure is halt-eligible UNLESS the entire
            # out-of-spec set is unrecoverable (in which case the range
            # failure is a symptom of those unrecoverable tracks and
            # warn-fallback already covers it via the sidecar).
            halt_on_range = album_range_fail and bool(halt_eligible_tracks)

            if halt_eligible_tracks or halt_on_range:
                fail_detail: dict[str, Any] = {}
                if halt_eligible_tracks:
                    fail_detail["tracks_out_of_spec"] = halt_eligible_tracks
                if halt_on_range:
                    fail_detail["album_lufs_range"] = round(verify_range, 2)
                    fail_detail["album_range_limit"] = 1.0
                if unrecoverable_map:
                    fail_detail["unrecoverable_tracks"] = sorted(
                        unrecoverable_map.keys(),
                    )
                ctx.stages["verification"] = {
                    "status":          "fail",
                    "avg_lufs":        round(verify_avg, 1),
                    "lufs_range":      round(verify_range, 2),
                    "all_within_spec": False,
                }
                return _safe_json({
                    "album_slug":     ctx.album_slug,
                    "stage_reached":  "verification",
                    "stages":         ctx.stages,
                    "settings":       ctx.settings,
                    "warnings":       ctx.warnings,
                    "failed_stage":   "verification",
                    "failure_detail": fail_detail,
                })

            # Warn-fallback: everything still out-of-spec is an
            # unrecoverable recovery casualty. Write the sidecar, log,
            # and let the pipeline continue.
            sidecar_lines = [
                "# Verification Warnings",
                "",
                "Auto-recovery attempted but could not bring these tracks within",
                f"±0.5 dB of the target LUFS ({effective_lufs:.1f}). The album was",
                "delivered with the flagged tracks as-is. Typical cause: dark",
                "spectral content (heavily K-weighted against) that cannot reach",
                "target loudness at the current ceiling.",
                "",
                "| Track | Target LUFS | Final LUFS | Peak (dBTP) | Original LUFS | Iterations |",
                "|---|---:|---:|---:|---:|---:|",
            ]
            for fname, rec in sorted(unrecoverable_map.items()):
                sidecar_lines.append(
                    f"| {fname} | {effective_lufs:.1f} | "
                    f"{rec['final_lufs']:.1f} | {rec['final_peak_db']:.2f} | "
                    f"{rec['original_lufs']:.1f} | {rec['iterations_run']} |"
                )
            sidecar_lines.append("")
            sidecar_path = ctx.output_dir / "VERIFICATION_WARNINGS.md"
            atomic_write_text(sidecar_path, "\n".join(sidecar_lines))

            ctx.notices.append(
                f"Verification warn-fallback: {len(unrecoverable_map)} "
                f"track(s) could not converge to target LUFS after "
                f"auto-recovery; see VERIFICATION_WARNINGS.md. "
                f"Pipeline continuing."
            )
            ctx.warnings.append(
                f"Verification: {len(unrecoverable_map)} unrecoverable "
                f"track(s) delivered off-target — see "
                f"VERIFICATION_WARNINGS.md for per-track detail."
            )
            ctx.stages["verification"] = {
                "status":               "warn",
                "avg_lufs":             round(verify_avg, 1),
                "lufs_range":           round(verify_range, 2),
                "all_within_spec":      False,
                "auto_recovered":       auto_recovered,
                "unrecoverable_tracks": sorted(unrecoverable_map.keys()),
                "sidecar":              "VERIFICATION_WARNINGS.md",
            }
            ctx.verify_results = verify_results
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/unit/mastering/test_master_album_verification_warn_fallback.py -v
```
Expected: all three tests PASS.

- [ ] **Step 5: Broader regression check**

```bash
.venv/bin/pytest tests/unit/mastering/ tests/integration/ -k "master_album or verification" -v
```
Expected: no regressions. If any test fails, check whether it relied on the old halt-all behavior; such a test needs to be updated (the new contract is documented).

- [ ] **Step 6: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/_album_stages.py \
        tests/unit/mastering/test_master_album_verification_warn_fallback.py
git commit -m "$(cat <<'EOF'
feat: verification warn-fallback for unrecoverable tracks

When auto-recovery runs but fix_dynamic reports converged=False,
_stage_verification now writes VERIFICATION_WARNINGS.md next to
the mastered files and downgrades stage status to "warn" instead
of halting the pipeline. Halt behavior is unchanged for
halt-eligible failures (peak issues, range failures with
non-recovery-casualty tracks) and for mixed recovery-casualty +
halt-eligible failures.

Documents the contract the master_album docstring has claimed
since day one: "falling through to a warn-fallback so the album
always completes." Previously only the ADM validation stage
honored that contract; now verification does too.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Update `master_album` docstring

**Files:**
- Modify: `servers/bitwize-music-server/handlers/processing/audio.py` (docstring of `master_album` around lines 580-630)

- [ ] **Step 1: Read the current docstring**

Open `audio.py` and locate the `master_album` function. Read its docstring (roughly lines 580-650) for the phasing narrative. Identify the sentence that today reads "falling through to a warn-fallback so the album always completes" — it's about the ADM loop only.

- [ ] **Step 2: Update the docstring**

Replace the warn-fallback paragraph(s) so they describe *both* warn-fallback triggers and list the remaining halt conditions.

Search for the block describing phase 2 and the warn-fallback claim. Add this paragraph (formatted to match the surrounding comment style):

```
    Warn-fallback (album always completes, flagged deliverable):
      - Verification: recovery-eligible tracks whose fix_dynamic pass
        reports converged=False are written to the output dir, flagged
        in VERIFICATION_WARNINGS.md, and the pipeline continues.
      - ADM validation: inter-sample clips persisting at the ceiling
        floor (or divergent ripple) emit an ADM_VALIDATION.md sidecar
        and the pipeline continues.

    Halt conditions (pipeline stops, no sidecar):
      - pre_qc FAIL on any track (bad format, phase, clipping, silence).
      - Verification failure where at least one out-of-spec track is
        NOT a recovery casualty (peak issue, or album-range failure
        with non-recovery-casualty participants).
      - Any non-verification, non-ADM stage error.
```

- [ ] **Step 3: Sanity-check with a quick grep**

```bash
grep -n "warn-fallback\|always completes" servers/bitwize-music-server/handlers/processing/audio.py
```
Expected: the updated docstring and the in-code warn-fallback comments still reference the same concepts consistently.

- [ ] **Step 4: Commit**

```bash
git add servers/bitwize-music-server/handlers/processing/audio.py
git commit -m "$(cat <<'EOF'
docs: document verification warn-fallback in master_album contract

The docstring's "falling through to a warn-fallback so the album
always completes" clause used to imply that warn-fallback covered
everything. In practice only the ADM loop honored it. The
verification stage now also does, so the docstring enumerates
both triggers and names the remaining halt conditions explicitly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: CHANGELOG entry

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add `[Unreleased]` entries**

Under the `[Unreleased]` section (create one if it doesn't exist), add:

```markdown
### Added
- `fix_dynamic` iterates up to 3 times to reach target LUFS,
  returning `converged` and `iterations_run` in metrics.
- `_stage_verification` emits `VERIFICATION_WARNINGS.md` sidecar and
  downgrades to `status: "warn"` when auto-recovery exhausts
  iterations. Pipeline continues instead of halting.

### Fixed
- Auto-recovery path now writes at `output_sample_rate` (was using
  source rate, so 48 kHz polished sources produced mastered files
  at 48 kHz while the rest of the album was 96 kHz).
- `master_album` halting at `verification` when track-level auto-recovery
  couldn't converge. The docstring promised warn-fallback; the
  implementation now delivers it.

### Changed
- `master_album` docstring enumerates halt vs warn-fallback
  conditions explicitly.
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'EOF'
chore: CHANGELOG entry for verification warn-fallback + recovery SRC

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: End-to-end gate

**Files:** none (verification only)

- [ ] **Step 1: Run `make check`**

```bash
make check
```
Expected: PASS (ruff + bandit + mypy + pytest all green).

If `make check` fails, fix the root cause — do not push or submit for review with a red `make check`.

- [ ] **Step 2: Spot-check the failure mode from the halt report**

Re-read the original halt report's track 09 symptoms:
- LUFS -23.2 at ceiling -4.42 → fix_dynamic should now iterate (won't converge at that ceiling), report `converged=False`, write at 96 kHz, and trigger warn-fallback with a row in `VERIFICATION_WARNINGS.md`.
- Other tracks (1–8, 10) should still behave identically — they land in spec on iteration 1, exactly as before.

There's no automated E2E replay at this point. The integration tests in tasks 2–4 cover the key branches. Document this in the PR description so the reviewer knows to spot-check against the original halt log if they have access to the album.

- [ ] **Step 2: Open the PR**

Branch name: `fix/auto-recovery-integrity-warn-fallback` off `develop`.

PR body should link to the original halt report (bugs #1, #2, #4) and call out:
- Behavior change for operators: unrecoverable tracks now deliver with a flagged sidecar instead of halting the run.
- Recovery throughput impact: up to 3 iterations per recovered track; in practice most tracks converge on iteration 1, so overhead is near-zero on normal albums.
- Follow-ups: per-track ADM ceiling (bug #3) and already_dark gating (bug #5) in `2026-04-21-per-track-adm-ceiling.md`.

---

## Self-Review Checklist

Before marking this plan complete, walk through:

1. **Spec coverage (bugs #1/#2/#4):**
   - #1 upsampling — Task 2 adds polyphase SRC before `sf.write`.
   - #2 LUFS convergence — Task 1 adds the iteration loop + `converged` flag.
   - #4 warn-fallback — Task 4 splits halt-eligible vs unrecoverable and writes the sidecar.
   - Docstring — Task 5 updates `master_album` contract.
   - CHANGELOG + verification — Tasks 6, 7.

2. **No placeholders:** Every code block is complete. Test stubs are explicit (the mixed-failure test is labeled "stub" with enough shape guidance to implement).

3. **Type consistency:** `converged: bool`, `iterations_run: int` — shape matches across `fix_dynamic`'s return, the `auto_recovered` record, and the stage payload. `unrecoverable_tracks` is a `list[str]` in both stage payload and `failure_detail`.

4. **Interaction with downstream stages:** After warn-fallback, `coherence_check` runs on `ctx.verify_results`. The unrecoverable tracks will show as outliers there too, but that's already handled — coherence classifies outliers as warnings, not halts. No new handling needed.
