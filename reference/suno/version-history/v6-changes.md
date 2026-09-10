# Suno V5.5 → V6 Migration Guide

**V6 Release Date**: September 9, 2026
**Availability**: v6 and v6-wild — Pro/Premier; v6-mini — all plans
**Status**: Stable; all earlier models retired the same day

---

## Summary of Changes

The v6 family (`v6`, `v6-wild`, `v6-mini`) replaced every earlier Suno model. The prompt surface is unchanged; two new generation controls and a new download/ToS regime are what actually change a workflow. Per-model detail: [../models.md](../models.md).

### Breaking Changes

**None in prompt syntax.** Style box 1,000 / Lyrics 5,000 / Exclude Styles 1,000 chars, 8-minute cap, bracket structure tags, Weirdness / Style Influence / Audio Influence, Vocal Gender, Exclude Styles and Duration all carry over.

**All older models are retired.** You cannot generate a fresh v5.5 (or v5, v4.5) take. Existing songs stay in the library; Extend, Cover and Remaster of them run on v6 and "may sound different from the original generation".

### New Controls (Advanced Mode → More Options)

| Control | What it does | Default | Plugin rule |
|---|---|---|---|
| **Variety** | Rewrites and expands the style prompt and diverges the two takes. Stops: Off "Exact style" · Normal "Balanced variety" · High "Distinct styles" · Extra "Bold exploration" · Max "Unreasonably varied" | Normal (v6, v6-mini, Custom); Off (v6-wild) | **Off** for an engineered Style Box |
| **Personalize** | "Make Variety match your taste" (needs Variety above Off) | Off | Off |
| **Max Mode** | "Uses more compute to maximize consistency throughout the song. Costs 2x credits per song." | Off | On for tracks over ~2:00, covers, Voices |

### Feature Carry-over

| Feature | v6 status |
|---|---|
| Custom Models trained on v5.5 | auto-upgraded to v6; no rebuild |
| Voices | work on v6; one-click "Upgrade Voice to v6"; "Voice (new)" vs "Style Voice (legacy)"; not on instrumentals |
| Personas | "Personas are now Voices"; legacy option remains |
| Covers / Extend / Replace Section / Song Editor / Remaster / Inspire / Sounds | "all powered by v6" |
| Stems | unchanged: Auto Split (up to 12, 50 credits), Split from Mix (10/stem), Advanced Split (~100 instruments, Premier, 10/stem) |
| Duration slider | present: Auto, or Custom 10 s–6:00 (default 3:00) |
| Simple Mode multimodal inputs (image / video / voice memo), plain-language edits, lyric swaps, mashups | new, **Simple Mode only**; Simple Mode expands typed lyrics — not the plugin's path |

### Credits

10 per generation (two songs) on all three models. Max Mode doubles it. Many attached images/videos add an unpublished surcharge. Custom Model creation 100.

### Downloads and Terms (effective 2026-09-03, before v6)

- Free: 7 lifetime trial downloads, personal use only. Pro: 20 / month. Premier: 60 / month. Reset on the billing date; no rollover; extra downloads purchasable.
- One song = one download regardless of format; WAV + MP3 + all stems of the same song count once; re-downloads are free. Applies to the whole library retroactively.
- **Suno Studio exports are uncapped** (Premier) and arrive as 32-bit float / 48 kHz WAV.
- Commercial rights require a permitted paid-plan download; Remixes are never commercial; **the ToS forbids removing, altering or circumventing Suno's watermark, fingerprint or metadata**.
- Believe / TuneCore distribute only tracks made on the new model family.

---

## What to Re-check on Existing Tracks

- [ ] Add a `### Generation Settings` table to every track still to be generated (`templates/track.md`); set Model `v6`, Variety `Off`.
- [ ] Tracks over ~2:00: Max Mode `On` (budget 20 credits per generation).
- [ ] Any track that leaned on a Persona: confirm it appears under Voices; upgrade the Voice to v6 before an album run.
- [ ] Re-prompt rather than rerun: expect slower, sparser, longer output from the same v5.5 prompt. Write imperfections and production texture into the prompt explicitly.
- [ ] Rock / metal / blues-rock tracks: first pass on `v6-wild`, then Cover the keeper on `v6`.
- [ ] Plan downloads against the monthly cap (or use Studio exports on Premier); download WAV first, stems later at no extra cost.

---

## Open Verification (as of 2026-09-10)

Nobody outside Suno has run a controlled test of these on v6; the docs tag them **(unverified)** until the maintainer's own-account tests land: structure tags and Performance Cues behaving as before; Max Mode fixing the reported late-song muffling; Exclude Styles still suppressing group vocals; which v6 models accept a Voice without the upgrade; Create-page WAV sample rate / bit depth; Duration Custom vs an overlong lyric; bar-count tags.

---

**Previous Version**: [v5-changes.md](v5-changes.md) (V4 → V5) · archived guide [v5-best-practices.md](v5-best-practices.md)
**Last Updated**: 2026-09-10
