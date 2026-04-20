# Polish Consumes Analyzer Recommendations (Design)

**Canonical issue**: [Issue #336](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/336)
**Design date**: 2026-04-19

## Summary

`analyze_mix_issues` emits concrete per-stem EQ recommendations (`mud_cut_db`, `high_tame_db`, `noise_reduction`, `highpass_cutoff`), but `polish_album` only shows them to the user and never feeds them back into processing. Result: tinniness and muddiness flags traverse the whole polish → post-QC pipeline unchanged while no automatic remediation occurs.

Separately, the same track-09 regression (highs going from 0.7 % to 0.6 % through the pipeline) surfaces a second bug: electronic-genre defaults apply `high_tame_db: -1.5` to `synth`/`keyboard`/`other` stems uniformly, further darkening already-dark content.

The fix wires analyzer recommendations into polish as **per-track overrides on top of genre defaults**, and extends the analyzer with a new "already dark" condition that emits `high_tame_db: 0.0` — a sentinel meaning "override genre default to zero, don't tame this track." One mechanism closes both bugs.

## Architectural context

- `analyze_mix_issues` (`servers/bitwize-music-server/handlers/processing/mixing.py:231–417`) returns per-track/per-stem diagnostics including `recommendations: {mud_cut_db, high_tame_db, noise_reduction, highpass_cutoff, click_removal}` — keys present only when a threshold fires.
- `polish_album` (`mixing.py:17–586`) orchestrates three stages: **analyze** (line 472, calls `analyze_mix_issues`) → **polish** (line 492, calls `polish_audio`) → **verify** (lines 545–577). The analyze output is surfaced in the final JSON return (line 583) but never passed to polish.
- `polish_audio` accepts `(album_slug, genre, use_stems, dry_run, track_filename)`. It does not read any per-track state or metadata. For each stem it calls `_get_stem_settings(stem_name, genre)` (line 1033), which deep-merges genre overrides on top of builtin defaults.
- Genre defaults (from `tools/mixing/mix-presets.yaml`) include `high_tame_db: -1.5` at 8–9 kHz for `synth`/`keyboard`/`other` stems on electronic — applied universally regardless of the track's existing spectral profile.
- The analyzer is stem-aware in stems mode: each stem is measured independently (`mixing.py:382–398`). Recommendations in stems mode are keyed by `per_track[track_name][stem_name]` — a shape polish can consume directly.
- Click-removal recommendations already flow through a separate parity path (`_resolve_analyzer_peak_ratio`, commit `272a15d`) and are out of scope for this fix.

## Design decisions

### Scope — wire through four EQ parameters, skip click_removal

Four analyzer recommendations get auto-applied to the polish per-stem settings dict:

- `mud_cut_db` → overrides stem's `mud_cut_db` when present
- `high_tame_db` → overrides stem's `high_tame_db` when present (including new `0.0` sentinel)
- `noise_reduction` → overrides stem's `noise_reduction` when present
- `highpass_cutoff` → overrides stem's `highpass_cutoff` when present

`click_removal` is already wired via `_resolve_analyzer_peak_ratio` and is not an EQ parameter — explicitly excluded from the override path to avoid double-wiring.

**Absence is meaningful.** When the analyzer doesn't emit a key, the genre default applies unchanged. When the analyzer explicitly emits a value — including `0.0` — that value overrides the genre default. `0.0` is not the same as "no recommendation."

### Analyzer extension — dark-track protection

Add one new condition in `_analyze_one` (`mixing.py:332–336`), directly after the existing harsh-highmids branch:

```python
if total_energy > 0:
    high_mid_ratio = float(np.sum(psd[high_mid_mask])) / total_energy
    result["high_mid_ratio"] = high_mid_ratio
    if high_mid_ratio > 0.25:
        result["issues"].append("harsh_highmids")
        result["recommendations"]["high_tame_db"] = -2.0
    elif high_mid_ratio < 0.10:                                    # NEW
        result["issues"].append("already_dark")                    # NEW
        result["recommendations"]["high_tame_db"] = 0.0            # NEW
```

The `0.10` threshold is a conservative first pick: the existing "harsh" threshold is `0.25`, track-09's observed high_mid_ratio was well below `0.10` at pre-QC, and a `0.10`–`0.25` middle band preserves default-genre behavior for the majority of tracks. The threshold becomes a preset key (`analyzer_dark_high_mid_ratio`, default `0.10`) so per-genre tuning is possible later without code changes. The harsh threshold also becomes a preset key (`analyzer_harsh_high_mid_ratio`, default `0.25`) for symmetry.

**No symmetric `mud_cut_db` dark-track guard in this PR.** The genre-default mud cuts are less aggressive than high-tames, and the issue report didn't flag over-cutting of lows. Easy to add the symmetric `low_mid_ratio < X → mud_cut_db: 0.0` later if data surfaces a case. YAGNI.

### Coupling shape — optional kwarg + auto-run fallback

`polish_audio` gains one new kwarg:

```python
polish_audio(
    album_slug, genre="", use_stems=..., dry_run=False, track_filename=None,
    analyzer_results: dict | None = None,    # NEW
)
```

Semantics:

- When `analyzer_results is None` and `dry_run is False`, `polish_audio` invokes `analyze_mix_issues(album_slug, genre)` internally at the start of processing.
- When `analyzer_results` is provided, `polish_audio` uses it as-is (no re-run).
- `polish_album` passes its existing analyze-stage output down to polish, avoiding a duplicate analysis pass.

This keeps direct-call ergonomics: `polish_audio(album_slug, genre="electronic")` works unchanged; anyone relying on the old behavior doesn't need to change callers.

### Merge semantics inside `_get_stem_settings`

`_get_stem_settings(stem_name, genre)` gains an optional `analyzer_rec: dict | None` parameter (per-stem recommendation subset for this track/stem). The merge order becomes:

1. Builtin defaults
2. Genre overrides (deep-merged)
3. **User overrides** from `{overrides}/mix-presets.yaml` (existing, unchanged)
4. **NEW:** per-track analyzer recommendations (scalar keys; last-merge wins)

Analyzer recs land last because they are the most-specific, most-data-driven adjustment. Per-track user overrides (a future follow-up) would layer between steps 3 and 4 — but are not shipped in this PR.

Stem-name resolution: analyzer results in stems mode key per-stem data by filename matching the polish pipeline's stem names (`synth.wav`, `keyboard.wav`, etc.). Polish's `_get_stem_settings` is called per canonical stem name; the lookup is `analyzer_results["per_track"][track_basename][stem_name]` with graceful fallback to empty dict when the track or stem is absent from the analyzer output.

### Stage output — `overrides_applied` list

Polish stage output (`polish` key in the final JSON) gains one new field `overrides_applied: list[dict]`, recording each effective override:

```json
{
  "overrides_applied": [
    {"track": "04-race-condition.wav", "stem": "synth",
     "parameter": "high_tame_db", "genre_default": -1.5,
     "analyzer_rec": -2.0, "applied": -2.0,
     "reason": "harsh_highmids"},
    {"track": "09-carbon-and-silicon.wav", "stem": "synth",
     "parameter": "high_tame_db", "genre_default": -1.5,
     "analyzer_rec": 0.0, "applied": 0.0,
     "reason": "already_dark"}
  ]
}
```

Empty list when no overrides fired — keeps stage output clean on well-behaved albums. The `reason` field comes from the analyzer's `issues` tag (e.g., `harsh_highmids`, `already_dark`, `muddy_low_mids`, `sub_rumble`, `elevated_noise_floor`).

This field is the operator-facing signal that closes the feedback loop the issue complains about: analyzer said X, polish applied X, here's what actually changed.

Alternatives rejected:

- **Per-track nested struct.** Would duplicate track/stem keys already present in the analyzer output; flat list is grep-friendly for operators debugging a specific track.
- **Emitting only on override (skipping entries where `applied == genre_default`).** Handled implicitly — an empty `analyzer_rec` never produces a row; only real overrides are logged.

## Testing

Test modules to create / extend (current mixing test files: `test_detector_parity.py`, `test_mix_tracks.py`, `test_polish_audio_stems.py`, `test_polish_peak_invariant.py`):

**New file `tests/unit/mixing/test_analyze_mix_issues.py`** — analyzer's per-stem condition tests:

1. **Dark-track analyzer condition** — synthetic PSD with `high_mid_ratio < 0.10` produces `issues: ["already_dark"]` and `recommendations: {high_tame_db: 0.0}`.
2. **Harsh + dark thresholds don't overlap** — a track with `high_mid_ratio` in the `0.10–0.25` band produces neither `harsh_highmids` nor `already_dark`.
3. **Preset override of the threshold** — running with `analyzer_dark_high_mid_ratio: 0.15` changes which tracks fire the condition.

**New file `tests/unit/mixing/test_polish_analyzer_overrides.py`** — `_get_stem_settings` merge behavior:

4. **`_get_stem_settings` merges analyzer rec on top of genre default** — given `genre="electronic"` (stem `synth` has default `high_tame_db: -1.5`) and analyzer rec `high_tame_db: -2.0`, the returned dict has `high_tame_db: -2.0`.
5. **Sentinel `0.0` overrides negative default** — same setup but analyzer rec `high_tame_db: 0.0` returns `high_tame_db: 0.0` (not silently dropped).
6. **Missing per-track entry falls through** — when `analyzer_results["per_track"]` has no entry for a given track, genre default is returned unchanged.
7. **Missing per-stem entry falls through** — when the track has analyzer data but not for this specific stem, genre default is returned unchanged.
8. **Non-EQ recommendation ignored** — analyzer's `click_removal: true` does not end up in the returned settings dict (click removal is wired via the detector-parity path).

**Extend `tests/unit/mixing/test_polish_audio_stems.py`** — integration tests for the coupling:

9. **`polish_album` pipes analyze output into polish** — run against a fixture album, assert `polish.overrides_applied` contains at least one entry when the fixture has a harsh-highmid or dark track.
10. **Direct `polish_audio` call auto-runs the analyzer** — call `polish_audio` without passing `analyzer_results`; assert it produces the same overrides on the same fixture.

## Out of scope

- **Per-track user overrides via sidecar YAML or markdown metadata.** The analyzer+polish coupling addresses the automatic-remediation case. A manual override path is a natural follow-up on the same `_get_stem_settings` merge infrastructure.
- **Symmetric mud-cut guard** (`low_mid_ratio < X → mud_cut_db: 0.0`). Not observed in the issue report; add when data surfaces.
- **Threshold tuning per genre.** Shipped as preset keys with conservative defaults; per-genre values in `mix-presets.yaml` are a follow-up.
- **Changing `click_removal` flow.** Already wired via `_resolve_analyzer_peak_ratio` from commit `272a15d`; not touched.
- **New MCP tool surface.** Existing `polish_album` / `polish_audio` signatures stay backward-compatible; no new tools added.
