# Streaming Mastering Specs

This document is the authoritative reference for how `master_album` delivers audio to streaming services and how its persistent signature works. It's the companion to issue #290.

## Single-master delivery

`master_album` produces one universal master per track and uploads to DistroKid, which fans out to every DSP. No per-platform variants.

| Setting | Default | Where it lives |
|---|---|---|
| `delivery_format` | `wav` | `mastering:` block, `config.yaml` |
| `delivery_bit_depth` | `24` | ↑ |
| `delivery_sample_rate` | `96000` | ↑ |
| `target_lufs` | `-14.0` | ↑ |
| `true_peak_ceiling` | `-1.0` dBTP | ↑ |
| `archival_enabled` | `false` (opt-in) | ↑ |
| `adm_aac_encoder` | `aac` (ffmpeg native) | ↑ |

### Why 24/96 specifically

- Apple Music **Hi-Res Lossless** badge: ≥24-bit AND **>48 kHz** (strict `>`). 48 kHz doesn't qualify.
- Tidal **Max** badge: 24-bit AND >44.1 kHz.
- Spotify streams at 44.1 kHz regardless; 96 kHz input downsamples cleanly.
- DistroKid accepts up to 192 kHz; 96 kHz is the sweet spot for badge gating vs. file size.

### Honesty caveat on 96 kHz

Suno source is 44.1 kHz. The 96 kHz output is **upsampled** — it satisfies the Apple/Tidal badge sample-rate gates but adds no audio information above ~22 kHz. The mastering report flags this at runtime whenever `delivery_sample_rate` exceeds the source rate.

## Album signature (`ALBUM_SIGNATURE.yaml`)

After every successful `master_album` run, a YAML snapshot is written to the album's audio directory (alongside `mastered/`, `archival/`). The signature captures what was shipped so future re-masters don't drift.

Layout:

```yaml
schema_version: 1
written_at: "2026-04-14T10:00:00Z"
plugin_version: "0.91.0"
album_slug: "my-album"
anchor:
  index: 3              # 1-based
  filename: "03-track.wav"
  method: composite     # composite | override | tie_breaker (persisted file
                        # always preserves the shipped method; the JSON response
                        # may temporarily surface "frozen_signature" during a
                        # frozen-mode run, but that marker is never persisted)
  score: 0.512          # null when method is override or frozen
  signature:            # the anchor's own pre-master signature
    stl_95: -14.8
    low_rms: -22.1
    vocal_rms: -17.6
    short_term_range: 8.4
    lufs: -14.0
    peak_db: -3.1
album_median:           # album-wide medians across tracks
  lufs: -14.0
  stl_95: -14.5
  low_rms: -22.0
  vocal_rms: -17.8
  short_term_range: 8.2
delivery_targets:
  target_lufs: -14.0
  tp_ceiling_db: -1.0
  lra_target_lu: 8.0
  output_bits: 24
  output_sample_rate: 96000
tolerances:
  coherence_stl_95_lu: 1.0
  coherence_lra_floor_lu: 6.0
  coherence_low_rms_db: 2.0
  coherence_vocal_rms_db: 1.5
pipeline:
  polish_subfolder: "polished"
  source_sample_rate: 44100
  upsampled_from_source: true
```

## Re-mastering behavior

| Album state | Signature file present | Default routing | What happens |
|---|---|---|---|
| Not `Released` (any sub-state) | may or may not exist | **fresh** | Full pipeline: score a new anchor across the current track set, rewrite signature on success. |
| `Released` | **must exist** | **frozen** | Skip anchor scoring. Master new/regenerated tracks against the anchor + targets in the signature. |
| `Released` | missing | — | **Halt + escalate.** Signature was deleted or never written. Cannot safely re-master. |

### Manual overrides

- `freeze_signature=True` — force frozen mode regardless of status. Useful for bonus tracks added during release prep. Errors if no signature file exists.
- `new_anchor=True` — force fresh anchor selection regardless of status. Useful when intentionally remastering a released album with a new sonic identity.
- The two flags are mutually exclusive; passing both fails fast in pre-flight.

### Archival stage mirrors `mastered/`

When `archival_enabled: true`, the 32-bit float pre-downconvert master is written to `archival/`. The archival stage now mirrors `mastered/` — entries whose basename is no longer in `mastered/` are pruned. This keeps the archival set in sync across re-masters where tracks are dropped or renamed. The `prune_archival` MCP tool is still available for time-versioned cleanup (keep N newest by mtime) — that's a separate concept.

## AAC encoder selection (future ADM validation step)

Not yet shipped — tracked as a future #290 checklist item. Parity-gap notes for when it lands:

- **macOS**: `afconvert` (Apple's reference encoder) + `afclip` — preferred runtime when available.
- **Linux / Windows / CI**: `ffmpeg -c:a aac` (native) — spec-equivalent for the zero-clip acid test but not bit-identical to Apple's encoder.
- **Override**: `mastering.adm_aac_encoder: libfdk_aac` for users with a non-free ffmpeg build.

## References

- iZotope — How to Master an Album: https://www.izotope.com/en/learn/how-to-master-an-album
- Yamaha Hub — Full Album Mastering: https://hub.yamaha.com/proaudio/recording/the-art-of-mastering-part-5-full-album-mastering/
- DistroKid Tidal Max badge: https://support.distrokid.com/hc/en-us/articles/360059827614
- DistroKid Apple audio badges: https://support.distrokid.com/hc/en-us/articles/4408827366675
- Apple Digital Masters spec (PDF): https://www.apple.com/apple-music/apple-digital-masters/docs/apple-digital-masters.pdf
