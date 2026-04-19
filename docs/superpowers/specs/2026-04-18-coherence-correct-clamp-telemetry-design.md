# Coherence-Correct Clamp Telemetry (Design)

**Canonical issue**: [Issue #334](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/334)
**Design date**: 2026-04-18

## Summary

The coherence-correct stage is functionally a no-op on most tracks of spectral-rich albums because its hardcoded ±0.5 dB tilt clamp is the binding constraint. The fix is telemetry-and-lever focused, not a behavior change:

1. Expose the tilt cap as a preset key (`coherence_tilt_max_db`, default 0.5 — unchanged).
2. Downgrade stage severity when all remaining outliers are clamp-bound (benign ceiling hit) rather than drift (genuine convergence failure).
3. Surface per-track diagnostics on what the corrector was trying to fix (intended tilt, limiting metric, signed spectral delta).

Defaults do not change. Genre-specific overrides are intentionally deferred to a follow-up PR that includes audio validation.

## Architectural context

- `_stage_coherence_correct` (`servers/bitwize-music-server/handlers/processing/_album_stages.py:993–1195`) orchestrates up to `_COHERENCE_MAX_ITERATIONS = 2` correction passes inside the master-album pipeline.
- Per-track tilt computation lives in `tools/mastering/coherence.py::_compute_tilt_db` (lines 180–225). The ±0.5 dB clamp comes from module constant `TILT_CORRECTION_MAX_DB` (line 177).
- Plan construction is `tools/mastering/coherence.py::build_correction_plan` (lines 228–342). The stage consumes each plan entry, re-masters the track with target LUFS + tilt_db, and re-classifies.
- Fixed-point non-convergence detection (added in commit `d9c0580`, PR #327) already correctly exits early when a clamped plan repeats. That logic is **not changing** — we're improving how the result is reported, not when the loop terminates.
- Preset loading: `tools/mastering/master_tracks.py::_PRESET_DEFAULTS` (lines 78–150) + `load_genre_presets` (lines 153–195), consumed by `_album_stages.py::_coherence_load_tolerances` (line 1027). Existing coherence keys: `coherence_stl_95_lu`, `coherence_lra_floor_lu`, `coherence_low_rms_db`, `coherence_vocal_rms_db`. A new tilt-cap key fits this pattern.
- Stage status vocabulary in current use: `pass | warn | fail | skipped | corrected | unconvergent | error`. No `notice` or `info` level exists in the pipeline. Warnings flow through `ctx.warnings`; there is no `ctx.notices`.

## Design decisions

### Preset key — additive, default-preserving

Add `coherence_tilt_max_db` to `_PRESET_DEFAULTS` with default `0.5`. `_coherence_load_tolerances` loads it alongside the other coherence tolerances. The value is threaded as an explicit parameter into `_compute_tilt_db` and `build_correction_plan`, replacing the current `TILT_CORRECTION_MAX_DB` module-constant reference.

`TILT_CORRECTION_MAX_DB = 0.5` remains in `coherence.py` as the **fallback** when callers invoke `_compute_tilt_db` / `build_correction_plan` without the parameter. This preserves backward compatibility for any direct (non-album-stage) caller and gives the clamp a single authoritative default.

No changes to `genre-presets.yaml` in this PR. Operators who want to experiment per-genre can set the key themselves; a follow-up can set per-genre defaults after audio A/B work.

### Severity downgrade — binary, clamp-only

After the correction loop terminates, classify remaining unconvergent outliers:

```python
remaining = [c for c in corrections if c["status"] == "unconvergent"]
clamp_bound = [c for c in remaining if c.get("reason") == "fixed_point_tilt_clamp"]
all_clamp_bound = remaining and len(clamp_bound) == len(remaining)
```

Decision table:

| remaining | all_clamp_bound | stage status | `ctx.warnings` append | `advisories` field |
|---|---|---|---|---|
| 0 | — | `pass` | no | omitted |
| >0 | yes | `pass` | **no** | present |
| >0 | no (mixed or all-drift) | `warn` | yes | present |

Rationale: a clamp-bound outlier means the corrector voluntarily stopped at its design ceiling to avoid over-EQ. That is the intended behavior of the clamp, not a failure of the pipeline. A drift-bound outlier (hypothetical — no current `unconvergent` path other than `fixed_point_tilt_clamp`, but the logic is future-proof) would mean the corrector tried and made things worse or oscillated. Only the latter should surface as a warning.

Mixed cases keep `warn`: if even one track failed for a non-clamp reason, the pipeline deserves operator attention and the clamp-bound tracks ride along in the same stage.

### Advisories — new stage-level field

When non-empty:

```json
"advisories": [
  {
    "filename": "03-friendly-face.wav",
    "kind": "tilt_ceiling",
    "message": "spectral tilt exceeded ±0.50 dB clamp (intended -0.78 dB, applied -0.50 dB)"
  }
]
```

The message formats the clamp value from the active preset, so a run with `coherence_tilt_max_db: 0.75` reports `±0.75 dB clamp` in the text. `kind` is fixed to `"tilt_ceiling"` for this PR — the enum leaves room for future advisory kinds without a schema change. Only present when there is at least one advisory.

When stage status is downgraded to `pass` by clamp-only remaining outliers, emit one line to the run log at INFO level: `coherence_correct: N track(s) at correction ceiling — see advisories`. Operators watching live mastering runs still see something; `ctx.warnings` stays clean.

Alternatives rejected:

- **Introduce a `notice` severity level.** Requires new `ctx.notices` plumbing and final-report renderer changes. Over-engineered for one call site; no other stage needs `notice` today.
- **Reuse an existing field like `notes`.** No existing stage has a `notes` or `advisory` field — there's nothing to reuse. A new named field is clearer than overloading something else.
- **Keep `status: warn` always, just add a breakdown count.** Doesn't solve the false-alarm problem in `ctx.warnings` that was the user complaint.

### Per-track diagnostics — additive

Extend each unconvergent correction entry with three fields:

```json
{
  "filename": "03-friendly-face.wav",
  "status": "unconvergent",
  "reason": "fixed_point_tilt_clamp",
  "applied_target_lufs": -14.1,
  "applied_tilt_db": -0.5,
  "clamped": false,
  "tilt_clamped": true,
  "iteration": 2,

  "intended_tilt_db": -0.78,
  "limiting_metric": "low_rms_db",
  "spectral_delta_db": -1.56
}
```

- `intended_tilt_db` — the raw tilt returned by `_compute_tilt_db` before clamping. Tells operators how far outside the clamp the track actually was. Surfaced on `unconvergent` stage-level entries only; `corrected` entries don't carry it (diagnostics live where they're actionable). The underlying plan-level entry in `build_correction_plan`'s output always carries it when a spectral violation fired.
- `limiting_metric` — which band-delta drove the tilt request: `"low_rms_db"` or `"vocal_rms_db"`. `_compute_tilt_db` short-circuits: if the `low_rms` band is an outlier, it wins; the `vocal_rms` band is only consulted when `low_rms` is within tolerance. There is no combined path today (and therefore no `"mixed"` value).
- `spectral_delta_db` — signed delta from the album anchor on the limiting metric. Negative = track is darker than anchor (corrector wanted more brightness). Positive = track is brighter than anchor.

Implementation: `_compute_tilt_db` currently returns `(clamped_tilt_db, was_clamped)`. Expand to `(clamped_tilt_db, was_clamped, raw_tilt_db, limiting_metric, delta_db)`. `build_correction_plan` threads the extra values into each plan entry. `_stage_coherence_correct` pulls them into the correction dict on unconvergent paths.

These fields are **omitted** (not null) on entries where they don't apply — e.g., `corrected` entries, or `skipped`/`error` entries that never computed a tilt. Additive schema; existing consumers are not affected.

## Testing

Extend `tests/unit/test_master_album_coherence_stages.py`:

1. **Clamp-only remaining outliers** — `status: "pass"`, `advisories` populated with `kind: "tilt_ceiling"` entries, **no** append to `ctx.warnings`.
2. **Mixed clamp + drift remaining outliers** — `status: "warn"`, `advisories` populated, `ctx.warnings` gets one entry. (Mock a non-clamp `unconvergent` reason to simulate drift.)
3. **Preset override** — `coherence_tilt_max_db: 1.0` in a genre preset → a tilt that would clamp at 0.5 now applies at e.g. 0.78 without clamping. `tilt_clamped: false`, no advisory for that track.
4. **Per-track diagnostic fields present** — on unconvergent entries, assert `intended_tilt_db`, `limiting_metric`, `spectral_delta_db` are present with plausible types/signs.
5. **Backward compat** — run with no preset override; behavior identical to pre-change (same clamp at 0.5, same fixed-point detection).

Unit tests in `tests/unit/test_coherence.py` (or equivalent) for the expanded `_compute_tilt_db` return tuple: given synthetic spectral deltas, verify `raw_tilt_db`, `limiting_metric`, and `delta_db` match expected values across single-metric and mixed-metric cases.

## Out of scope

- Changing `_COHERENCE_MAX_ITERATIONS` (stays 2).
- Changing the correction algorithm (_compute_tilt_db math is unchanged except for the returned tuple shape).
- Per-genre default tilt caps in `genre-presets.yaml`.
- Final report renderer changes (advisories appear in stage JSON; operators consuming the raw run output see them; pretty-printing can be a follow-up).
- Drift-vs-clamp reason codes beyond `fixed_point_tilt_clamp` — the code handles the mixed case structurally, but there is no second reason code to test against today.
