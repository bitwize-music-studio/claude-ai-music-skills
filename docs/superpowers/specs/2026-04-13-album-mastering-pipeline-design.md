# Album-Coherence Mastering Pipeline — Design

**Canonical spec**: [Issue #290](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/290)
**Companion issue**: [#303 — Full-fidelity metadata embedding](https://github.com/bitwize-music-studio/claude-ai-music-skills/issues/303)
**Design date**: 2026-04-13

## Summary

Automated album-coherence mastering pipeline replacing per-track independent targeting with anchor-based matching. 11-stage pipeline: pre-master prep → anchor selection → master anchor → master remaining → coherence check → coherence correct → layout → ceiling guard → ADM validation → final QC → persist + deliver.

Key design elements (all locked in #290):

- **Anchor selection**: composite scoring (0.4 mix_quality + 0.4 representativeness − 1.0 ceiling_penalty) + `anchor_track` README frontmatter override + lowest-track-number tie-breaker.
- **Iteration budgets**: ADM outer loop (max 2) × coherence inner loop (max 2 per ADM cycle, counter resets on ADM re-cycle). ADM re-cycle restarts from step 4, not step 2 (anchor is ceiling-independent).
- **Delivery target**: 24-bit WAV at 96 kHz (upsampled from 44.1 kHz Suno source; honesty caveat surfaced at runtime and documented).
- **Multi-metric signature**: STL-95, LUFS-I, LRA, low-RMS (20–200 Hz, STL-95-windowed only), vocal-RMS (polished stem when present; 1–4 kHz band fallback), TP.
- **Signature persistence**: `ALBUM_SIGNATURE.yaml` written per run; `Released` albums use frozen mode for new/regenerated tracks.
- **Layout & transitions**: LAYOUT.md emits per-boundary `transitions:` block (`gapless` | `gap`); no crossfade overlap support.
- **ADM validation**: afconvert+afclip on macOS (preferred runtime); ffmpeg native `aac` on Linux/Windows and as canonical CI validator; `mastering.adm_aac_encoder` override for libfdk_aac.
- **Album-ceiling guard**: bounded silent pull-down (delta ≤ 0.5 LU); halt + escalate (delta > 0.5 LU).
- **Genre tolerances**: flat fields in `genre-presets.yaml`; `measure_album_signature` MCP tool for empirical tuning from reference albums.
- **Archival**: 32-bit float / 96 kHz pre-downconvert, opt-in (`archival_enabled: false` default), separate subfolder, `prune_archival` for cleanup.
- **Metadata embedding**: MVP (Tier 1) inline in step 11; deeper metadata story in #303.

## Architectural context

- Builds on existing mastering pipeline in `servers/bitwize-music-server/handlers/processing/audio.py` (master_album currently iterates tracks independently).
- Polish stays separate (PR #281): `polish_audio` writes `polished/` once; `master_album` consumes as frozen input. ADM re-cycle does not re-run polish.
- Genre preset system (`tools/mastering/genre-presets.yaml` + `{overrides}/mastering-presets.yaml`) is the extension point for per-genre coherence tolerances.
- Signature measurements extend `analyze_audio` (`tools/mastering/analyze_tracks.py`).
- New MCP tools registered per existing pattern in `handlers/processing/audio.py`.

## Implementation scope

~25 unchecked items in the #290 checklist. Phased PR strategy expected — each phase should be independently testable and non-regressive on existing flows.

Full design rationale, Q&A resolutions (11 locked decisions), and checklist in #290.
