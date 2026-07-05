# Covers and Personas

Two Suno features let you carry work forward instead of starting every track from a blank prompt:

- **Personas** save a generated song's vocal identity so the *same singer* can appear across many different songs.
- **Covers** reimagine an *existing* song or sample in a new style or genre, keeping the underlying song while changing the production.

This is the workflow companion. For the underlying feature reference — creation steps, best practices, and limits — see [Personas](../suno/v5-best-practices.md#personas) and [Personas for Vocal Consistency](../suno/tips-and-tricks.md#personas-for-vocal-consistency); this guide points to that material rather than repeating it.

> **Plan note**: Personas and Voices are **Pro/Premier** features. Covers are the **Cover** action in the Suno editor, applied to uploaded audio or a prior generation.

---

## When to Use What

| You want to… | Reach for | Notes |
|--------------|-----------|-------|
| Write a brand-new song from lyrics + a style prompt | **Original generation** | The default for most album tracks. |
| Keep the *same singer* across several different songs | **Persona** | Save one good vocal, reuse it. Pro/Premier. |
| Reinterpret an *existing* song or sample in a new style/genre | **Cover** | Keeps the song, changes the production. |
| Sing a track in *your own real voice* | **Voices** (voice cloning) | V5.5, Pro/Premier. An alternative to a Persona — pick one, not both (see [Voices & Custom Models](../suno/v5-best-practices.md#voices--custom-models)). |
| A consistent voice *and* genre variety across the album | **Persona + Cover** | The Persona holds the voice; the Cover shifts the genre. |

---

## Personas: A Reusable Vocal Identity

A Persona is the most reliable way to keep one voice consistent across an album. Full reference: [Personas](../suno/v5-best-practices.md#personas).

### Creating a Persona

1. Generate a song until the vocal is one you'd happily hear again on other tracks.
2. From the song's menu, save its vocal identity as a Persona.
3. Apply the Persona when generating new songs — it carries the vocal character.
4. Keep the Style Box simple (one or two genres) when a Persona is active; the Persona handles the voice, so you don't re-describe it.

### Using a Persona Across an Album

- A Persona locks a specific AI singer **independent of musical style** — you can move it across genres (the same singer doing a folk track and an electronic track).
- Personas run **dominant** in the mix. If the Style Box fights the Persona, the Persona usually wins — work with it, not against it.
- **Limits**: 200 songs with Personas are included per billing cycle, then 10 credits per song.
- The December 2025 update made Personas more dominant. If a result sounds overprocessed, simplify the Style Box or lower Style Influence.

### Persona (feature) vs the README "persona" field

This project also records an album's voice as a plain-text **persona** description in the album README — e.g. `Male baritone, gravelly, introspective, folk storyteller` (see [terminology.md](../terminology.md)). That description is the *plan*; a Suno Persona is the *saved artifact* that enforces it. Write the description first, generate a track that matches it, then save that track as the Suno Persona so every later track inherits the same voice.

---

## Covers: Reimagining an Existing Song

A Cover reinterprets an existing track in a different style or genre (see [terminology.md](../terminology.md)) — for example, covering a folk song as electronic.

### What a Cover Keeps and Changes

- **Keeps** the underlying song — its topline melody and structure.
- **Changes** the production: genre, instrumentation, tempo feel, era.
- To change the *words*, use **Extend** or a fresh generation instead — a Cover restyles, it doesn't rewrite. See [Working with Splice Samples](../suno/tips-and-tricks.md#working-with-splice-samples) for the Extend-vs-Cover split.

### When to Reach for a Cover

- You have an acoustic demo or a [Splice](../suno/tips-and-tricks.md#working-with-splice-samples) sample you want rendered as a full production.
- You want a second version of a track in a contrasting genre (an album cut plus, say, an electronic remix).
- You're genre-bending — layering new styles onto a song you already like.

### Setting Up a Cover Track

**From an uploaded sample:**

1. Upload the sample (e.g. from Splice).
2. Choose the **Cover** action to reinterpret it in a new style. (Choose **Extend** instead if you want to add or replace lyrics.)
3. Set the destination genre/mood in the Style Box — describe the *new* target style, not the original.
4. Adjust **Audio Influence** — higher lets the uploaded audio shape the output more (closer to the source), lower gives Suno more freedom. The slider appears only when audio is uploaded (see [Creative Sliders](../suno/v5-best-practices.md#creative-sliders)).
5. Optionally pull stems afterward and drop unwanted parts.

**From a prior generation:**

1. Open a song you already generated.
2. Choose **Cover** and set the new target genre/style in the Style Box.
3. Generate and pick the best take.

**Rights note**: Covering your own generations or cleared samples is clean. Covering someone else's copyrighted recording is a rights question like any release — keep to material you have the rights to.

---

## Covers + Personas: Genre-Bending with One Voice

Combining the two is a powerful remixing technique — full notes at [Combining Personas with Covers](../suno/tips-and-tricks.md#combining-personas-with-covers).

1. Generate a song with a Persona applied.
2. Use **Cover** to transform it into a different genre.
3. The Persona's vocal identity carries through the genre shift.
4. Layer multiple Covers for complex genre-bending results.

**Caveat**: Because the December 2025 update made Personas more dominant, a Cover built on a Persona can come back overprocessed. If it does, simplify the Style Box or lower Style Influence.

---

## Covers vs Original Generation: Choosing

- **Start from original generation** whenever the song doesn't exist yet. It gives Suno the most room and is the cleanest path to a strong first take — the default for album tracks.
- **Switch to a Cover** only when you already have audio (a sample or a prior generation) whose *song* you want to keep but whose *style* you want to change. If you'd end up rewriting the lyrics or melody anyway, a fresh generation is usually faster than fighting a Cover.
- **Reach for a Persona** (with or without a Cover) when the thing you need to hold constant is the *voice*, not the song.

---

## Track File Setup

The track template has an optional **Cover / Persona Setup** block (in `templates/track.md`) for recording the original-song reference, the Persona in use, and cover-specific style notes. Fill it in for cover or persona tracks; delete the block for standard original-generation tracks — it does not affect the normal writing flow.

---

## Checklists

**Before saving a Persona:**

- [ ] The source generation's vocal is one you'd happily hear across the album
- [ ] The Style Box was simple enough that you're capturing the voice, not the arrangement

**Before generating a Cover:**

- [ ] The source audio is something you have the rights to (your own generation or a cleared sample)
- [ ] The Style Box describes the NEW target style, not the original
- [ ] Audio Influence is set intentionally (higher hews closer to the source)
- [ ] If a Persona is also applied, the Style Box is kept simple so the Persona isn't fighting the prompt

---

## See Also

- [Personas — v5-best-practices.md](../suno/v5-best-practices.md#personas) — feature reference, best practices, limits
- [Personas for Vocal Consistency — tips-and-tricks.md](../suno/tips-and-tricks.md#personas-for-vocal-consistency) — quick workflow and the Covers combo
- [Combining Personas with Covers — tips-and-tricks.md](../suno/tips-and-tricks.md#combining-personas-with-covers)
- [Working with Splice Samples — tips-and-tricks.md](../suno/tips-and-tricks.md#working-with-splice-samples) — Cover vs Extend on uploads
- [Voices & Custom Models — v5-best-practices.md](../suno/v5-best-practices.md#voices--custom-models) — voice cloning, the alternative to a Persona
- [Creative Sliders — v5-best-practices.md](../suno/v5-best-practices.md#creative-sliders) — Audio Influence and Style Influence
- [terminology.md](../terminology.md) — Cover, Persona, Voice Tags definitions
- [Importing Audio Files](importing-audio.md) — moving finished WAVs into the album
