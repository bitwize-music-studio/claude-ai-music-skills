# Suno Song Editor Workflow

The Song Editor lets you fix a generated track section by section — remake, rewrite, extend, reorder, or delete individual parts — without throwing away the whole take. This guide covers *when* to reach for it (versus full regeneration or the mix-engineer polish pass), what each operation is good for, and how section edits fit the download → polish → master pipeline.

> **Related docs**: [v5-best-practices.md#song-editor](../suno/v5-best-practices.md#song-editor) (capability table), [error-recovery.md](error-recovery.md), [importing-audio.md](importing-audio.md), [mastering-workflow.md](../mastering/mastering-workflow.md)

*This guide intentionally does not repeat the operation-by-operation capability table — see [v5-best-practices.md#song-editor](../suno/v5-best-practices.md#song-editor) for that. Here we cover when and why.*

---

## Where Song Editor Lives in the Workflow

Song Editor runs **inside Suno, before you download.** It edits the generation in place. Everything after download — stem extraction, mix polish, mastering — operates on a fixed WAV:

```
Generate → [Song Editor: remake / rewrite / extend / reorder / delete] → download WAV/stems
         → import-audio → mix-engineer (polish) → mastering-engineer → release
```

The single most important rule: **lock the arrangement in Song Editor before you download.** (See [Clip Extension & the Mastering Pipeline](#clip-extension--the-mastering-pipeline) below for why.)

---

## Decision Matrix: Song Editor vs Regeneration vs Polish

When a take isn't right, first ask **what kind of wrong it is** — the answer picks the tool.

| Symptom | Scope | Tool | Why |
|---------|-------|------|-----|
| One section off (cracked chorus note, rushed bridge); rest is a keeper | Section | **Song Editor — Remake** | Re-rolls only the bad section; approved sections stay untouched |
| Wrong words/melody in a section (factual error, weak line, pronunciation) | Section | **Song Editor — Rewrite** | Changes content, keeps the section's role and the rest of the take |
| Section order or length wrong (bridge should precede final chorus; song runs long) | Arrangement | **Song Editor — Reorder / Delete / Extend** | Restructures without re-rolling performances you like |
| Whole track wrong: genre, tempo, mood, overall vibe | Whole track | **Full regeneration** | A global problem needs a new take; per-section edits can't fix the foundation |
| You changed the Style Box or rewrote most of the lyrics | Whole track | **Full regeneration** | The generation no longer matches its inputs |
| Performance & words are right, but audio is noisy / muddy / harsh / clicky | Audio quality | **mix-engineer polish** | Not a content problem — clean the stems; no Suno credits, no re-roll |

Two rules of thumb:

- **Localized problem, keeper take → Song Editor.** It preserves everything you've already approved and re-rolls only what you point at. Reach for it *before* full regeneration whenever the rest of the take is worth keeping — full regeneration is non-deterministic and can lose the good parts.
- **Audio-quality-only problem → polish, not regeneration.** If the notes and words are right and only the *sound* is off, Song Editor and regeneration are the wrong tools — they re-roll the performance and spend credits. Use the [mix-engineer](../../skills/mix-engineer/SKILL.md) pass instead: it processes stems, changes no content, and costs no Suno credits.

---

## Section Operations & When to Use Them

Definitions live in the [capability table](../suno/v5-best-practices.md#song-editor). Below is *when each operation earns its place* and what to watch for.

### Remake — same prompt, new take of one section

**Use it when** a single section is the only weak spot in an otherwise-keeper take: a chorus vocal cracked, one verse drifted off-genre, the bridge felt rushed. Remake rolls the dice on just that region and locks the rest.

**Watch for**: the remade section can land at a slightly different timbre or level than its neighbors. Audition the seams. Mastering's whole-track normalization blends minor differences later, but an obvious tonal jump is better fixed with another remake *before* download.

### Rewrite — new lyrics/melody, same role

**Use it when** the content of a section is wrong but its slot in the arrangement is right: a factual error in a documentary verse, a weak line you tightened with [lyric-writer](../../skills/lyric-writer/SKILL.md), a hook that isn't landing, or a pronunciation fix that needs fresh audio for just that section.

**Do first**: run the fix through lyric-writer and the pronunciation-specialist so you rewrite once, not three times.

**Watch for**: keep the section's structural role. Rewriting a pre-chorus into a second verse breaks the song's shape — that's a job for full regeneration, not a section rewrite. And **update the track file** (see [Keep the Track File in Sync](#keep-the-track-file-in-sync)).

### Extend — append bars at a section's tail

**Use it when** a section ends too abruptly or a transition needs room: 1–2 bars into or out of a chorus for a smoother hand-off, an outro that needs to breathe, a longer intro runway.

**Watch for**: the documented **2–3 extensions max per song** ceiling — over-extending causes uneven lyrics, weaker vocals, and quality drops. Extension also changes total track length, which has pipeline consequences (see below).

### Reorder — move sections in the arrangement

**Use it when** the running order plays better rearranged: the bridge lands harder right before the final chorus, or two verses swap for a stronger narrative order. As with Delete, the engine bridges the newly-adjacent sections.

**Watch for**: continuity. On documentary/story albums, reordering can scramble chronology or break a callback set up earlier. Re-read the full lyric flow after reordering, and sync the track file's lyric order to match.

### Delete — remove a weak section

**Use it when** the song is stronger without a part: a redundant "twin verse," a dead instrumental stretch, a second bridge that adds nothing, or trimming length (Suno quality [degrades past ~6–7 minutes](../suno/v5-best-practices.md#known-v5-limitations)). The engine smooths the transition.

**Watch for**: two things. Deleting can pull the track under its **Target Duration** — check against the album/track duration target. And on documentary tracks, deleting a verse may drop a *sourced* fact — make sure nothing load-bearing (or cited) leaves with it.

### Keep the Track File in Sync

Song Editor changes the **audio**, not the **markdown.** After any Rewrite, Reorder, or Delete, update the track file's lyrics (and their order) and add a Generation Log row noting the edit. A track file whose lyrics don't match the audio is the same hazard [error-recovery.md](error-recovery.md#5-lyrics-mistake-after-generation) warns about — and on source-based albums it breaks the audit trail between lyrics and verified sources.

---

## Clip Extension & the Mastering Pipeline

Everything downstream of Suno — stem extraction, [mix polish](../../skills/mix-engineer/SKILL.md), and [mastering](../mastering/mastering-workflow.md) — runs on the **downloaded WAV.** Song Editor runs *upstream* of that. So:

**Finalize every Song Editor edit before you download, extract stems, polish, or master.**

Why it matters:

- **Any section edit changes the source audio.** Extend appends bars (longer track, new tail); Rewrite and Remake replace audio inside a section; Reorder and Delete change what's where. Once you've downloaded and started polishing or mastering, going back into Song Editor produces a *new* WAV — the stems you extracted are stale, and the polish/master you ran no longer applies. You re-run the whole downstream pipeline for that track.
- **Master the finished track as one unit — never section by section.** Mastering normalizes the full track to **-14 LUFS / -1.0 dBTP** with under 1 dB of variation across the album (see [mastering-workflow.md](../mastering/mastering-workflow.md)). A remade or extended section is still raw Suno output at Suno's [pre-mastering loudness](../suno/v5-best-practices.md#suno-output-loudness-pre-mastering) (e.g., pop/EDM around -9 to -7 LUFS) — it is *not* mastered just because the surrounding track was. Send the whole, arrangement-locked track through mastering once so loudness and limiting stay consistent across the seams.
- **Fix gross seams in Suno, not in the master.** The mix-engineer's per-stem processing and mastering's whole-track normalization blend *minor* level/timbre differences between an edited section and its neighbors. A jarring mismatch, though, should be re-rolled with another Remake before download — mastering evens loudness, it doesn't rebuild a performance.

Practical gate: a track isn't ready for `import-audio` until its arrangement is locked. Add **"all Song Editor edits final?"** to your pre-download check alongside the "Before Mastering" list in [error-recovery.md](error-recovery.md#prevention-checklist).

---

## Integration with the Regeneration Workflow

CLAUDE.md's [Regeneration Workflow](../../CLAUDE.md#regeneration-workflow) is the spine for handling a rejected `Generated` track. Song Editor slots into it as a lower-risk fourth path — usually the right first move when the problem is *localized.*

The four steps are unchanged; Song Editor mainly expands **Step 2 (decide the fix path):**

| Rejection reason | Fix path |
|------------------|----------|
| Whole track wrong (genre, tempo, mood) | Revise Style Box via suno-engineer → **full regenerate** |
| Wrong words / pronunciation in one or a few sections | Fix via lyric-writer + pronunciation-specialist → **Song Editor Rewrite** on those sections |
| One flubbed section, take otherwise a keeper (Suno non-determinism) | **Song Editor Remake** on that section |
| Order or length wrong | **Song Editor Reorder / Delete / Extend** |
| Words & performance right, only the audio quality is off | **mix-engineer polish** (not a regeneration) |

The rest of the workflow carries over exactly:

- **Step 1 — Log the rejection.** A Song Editor edit is still an attempt: note the reason, then log which section and operation you used.
- **Step 3 — Regenerate / log the new attempt.** Add a Generation Log row for the edit the same way you would for a full regeneration.
- **Step 4 — When satisfied.** Mark the keeper with ✓ in the Rating column and advance Status to `Final`.
- **Status stays `Generated`.** Section edits never move status backward, exactly like full regeneration. A track is `Final` only once it has a ✓. (See [status-tracking.md](status-tracking.md).)

**Rule of thumb**: when the rest of the take is a keeper, reach for Song Editor before full regeneration. Full regeneration discards approved sections and re-rolls the dice; Song Editor keeps what works and re-rolls only what you point at.

---

## Quick Checklist

Before a Song Editor pass:

- [ ] Confirm the problem is *localized* (section-level), not global — global → full regenerate
- [ ] Confirm it's a *content/performance* problem, not audio quality — audio-only → mix-engineer polish
- [ ] For Rewrite: run lyric-writer + pronunciation-specialist first

After a Song Editor pass:

- [ ] Audition the seams between edited and untouched sections
- [ ] Update the track file's lyrics/order to match the new audio (Rewrite/Reorder/Delete)
- [ ] Add a Generation Log row noting the section + operation
- [ ] Confirm total extensions stay within the 2–3 ceiling
- [ ] Arrangement locked before download → import-audio → polish → master

---

## See Also

- [v5-best-practices.md#song-editor](../suno/v5-best-practices.md#song-editor) — capability table (Remake / Rewrite / Extend / Reorder / Delete)
- [tips-and-tricks.md#song-editor-v5](../suno/tips-and-tricks.md#song-editor-v5) — quick-reference tips
- [CLAUDE.md#regeneration-workflow](../../CLAUDE.md#regeneration-workflow) — rejected-track decision spine
- [mix-engineer skill](../../skills/mix-engineer/SKILL.md) — stem polish (the audio-quality path)
- [mastering-workflow.md](../mastering/mastering-workflow.md) — loudness normalization and limiting
- [importing-audio.md](importing-audio.md) — moving the downloaded WAV into place
- [error-recovery.md](error-recovery.md) — recovery procedures for lyric/audio mismatches
