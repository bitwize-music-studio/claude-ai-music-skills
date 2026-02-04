# Lyric Writer Craft Reference

Detailed tables and reference data for the lyric-writer skill.
Read by the lyric-writer when specific craft guidance is needed.

---

## Rhyme Techniques

### Rhyme Types (use variety)
| Type | Description | Example |
|------|-------------|---------|
| Perfect | Exact match | love/dove |
| Slant/Near | Similar but not exact | love/move |
| Consonance | Same ending consonants | blank/think |
| Assonance | Same vowel sounds | lake/fate |
| Internal | Rhymes within a line | "fire and desire higher" |

### Rhyme Scheme Patterns
| Pattern | Effect |
|---------|--------|
| AABB | Stable, immediate resolution |
| ABAB | Classic, delayed resolution |
| ABCB | Lighter, less pressure |
| AAAX | Strong setup, surprise ending |

### Rhyme Schemes by Genre — Quick Reference

**There is no universal default.** Each genre has its own conventions documented in `genres/[genre]/README.md` under "Lyric Conventions." Always read the genre README before writing.

| Genre Family | Default Scheme | Rhyme Strictness | Key Difference |
|---|---|---|---|
| **Hip-Hop / Rap** | AABB (couplet) | High — multisyllabic + internal rhyme mandatory | Rhyme density throughout the bar, not just end rhymes |
| **Pop** | XAXA (conversational) | Low — near rhymes preferred | Conversational phrasing; if it sounds "crafted," it fails |
| **Rock** | XAXA or ABAB | Low — meaning > rhyme | Imagery and emotional energy over technical rhyming |
| **Punk** | AABB (loose) | Low — half-rhymes authentic | Directness, shoutable, works at 150+ BPM |
| **Metal** | Optional | Very low — can skip entirely | Concrete imagery and riff alignment over rhyme |
| **Country / Folk** | ABCB (ballad stanza) | Moderate — near rhymes OK | Storytelling; lines 2 & 4 rhyme, 1 & 3 free |
| **Blues** | AAB (3-line form) | Moderate | Line 1 stated, line 2 repeats, line 3 resolves |
| **Electronic / EDM** | Repetition > rhyme | Minimal | Less is more; single phrases looped, not verses |
| **Ambient / Lo-Fi** | None | None | Vocals are texture, not content |
| **Trip-Hop** | XAXA (loose) | Low | Most lyrical electronic genre; abstract, moody |
| **R&B / Soul** | Flexible | Low — emotion first | Leave space for melisma and vocal runs |
| **Funk** | Minimal | Very low | Groove lock; lyrics accent the downbeat |
| **Gospel** | Repetitive build | Low | Call-and-response; repetition builds intensity |
| **Jazz** | AABA (32-bar) | Sophisticated | Internal rhyme, wordplay; phrasing behind/ahead of beat |
| **Reggae / Dancehall** | Riddim-driven | Moderate | Groove lock; audience participation by design |
| **Afrobeats** | Call-and-response | Low | Code-switching (English/Pidgin/local languages) |
| **Ballad (any)** | ABCB or ABAB | Moderate | Emotion and narrative serve the story |

**How to use**: Before writing lyrics, read `genres/[genre]/README.md` → "Lyric Conventions" section for the specific genre's rules on rhyme scheme, rhyme quality, verse structure, and what to avoid.

### Rhyme Quality Standards (All Genres)

These apply universally regardless of genre:

- **Forced rhymes** are NEVER acceptable — never bend grammar, invent words, or use filler phrases just to land a rhyme
- **No self-rhymes** — never rhyme a word with itself
- **No lazy repeats** — avoid rhyming near-identical words (mind/mind, time/time)
- **Meaning over rhyme** — if a perfect rhyme sounds unnatural, use a near rhyme or restructure the line
- **Consistency within sections** — whatever rhyme scheme you choose, maintain it through the section. No random switching mid-verse.

### Flow Checks (All Genres)

Before finalizing any lyrics, verify:
1. Read each rhyming pair aloud — do the end words actually rhyme (per genre expectations)?
2. Are there any orphan lines that should rhyme with something but don't?
3. Is syllable count roughly consistent across corresponding lines? (see tolerance in Line Length table)
4. Are there filler phrases ("spoke the words", "you know what I mean") padding lines?
5. Do quoted/paraphrased lines come from sourced material (for documentary albums)?
6. Does the rhyme scheme match the genre? (Don't use AABB couplets for a folk ballad, don't use ABCB for hip-hop)
7. Say the lyrics without melody as plain prose — do they sound natural for the genre's vocal style?

### Common Anti-Patterns (All Genres)

- ❌ Using the wrong rhyme scheme for the genre (hip-hop couplets in a folk song, etc.)
- ❌ Forcing perfect rhymes where near rhymes sound more natural
- ❌ Using filler lines to set up quotes ("he stood up and spoke the words")
- ❌ Inventing fake quotes for real people when source quotes exist
- ❌ Ending a verse on a line that doesn't connect to its rhyme partner
- ❌ Inconsistent line lengths that break the vocal pocket
- ❌ Cliché phrases: "cold as ice," "broke my heart," "by my side," "set me free," "tonight" (at line endings), "learning to fly"
- ❌ Telling instead of showing ("I was angry" vs. showing anger through imagery)
- ❌ Generic abstractions when specificity would serve better

---


---

## Line Length

### General Ranges by Genre
| Genre | Syllables/Line | Tolerance |
|-------|----------------|-----------|
| Pop/Folk/Punk | 6-8 | ±2 |
| Rock/Indie | 8-10 | ±2 |
| Hip-Hop/Rap | 10-13+ | ±3 |
| Metal/Electronic | Varies | Flexible |

**Critical**: Verse 1 line lengths must match Verse 2 line lengths.

---

## Song Length

Songs that are too long (800+ words) cause Suno to rush, compress sections, or skip lyrics. Keep songs concise.

### Word Count Targets by Genre

| Genre | Words | Verses | Lines/Verse |
|-------|-------|--------|-------------|
| Pop / Dance-Pop / Synth-Pop | 150–250 | 2 | 4–6 |
| Punk / Pop-Punk | 150–250 | 2 | 4–6 |
| Rock / Alt-Rock | 200–350 | 2–3 | 4–8 |
| Folk / Country / Americana | 200–350 | 2–3 | 4–8 |
| Hip-Hop / Rap | 300–500 | 2–3 | 8–16 |
| Ballad (any genre) | 200–300 | 2–3 | 4–6 |

### Structure Defaults

- **Default**: 2 verses + chorus + bridge. 3 verses max unless user explicitly requests more.
- **Chorus**: 4–6 lines, repeated verbatim — not rewritten each time.
- **Bridge**: 2–4 lines.
- **Outro**: Optional, 2–4 lines max. Not a new verse.

### Length Limits

- **If draft exceeds 350 words (non-hip-hop) or 500 words (hip-hop)**: Cut it down before presenting.
- Count words after drafting. If over target, remove a verse or trim sections — don't just shorten lines.

### Section Length Limits by Genre

**Why this matters**: Suno rushes, compresses, or skips content when sections are too long. These are hard limits — trim before presenting.

#### Hip-Hop / Rap / Trap / Drill / Grime / Phonk / Nerdcore

| Section | Max Lines | Notes |
|---------|-----------|-------|
| Verse | 8 | Standard 16-bar verse (each written line ≈ 2 bars) |
| Chorus / Hook | 4–6 | Shorter hooks hit harder |
| Bridge | 4–6 | |
| Pre-Chorus | 2–4 | |
| Outro | 2–4 | Spoken word / ad-lib sections exempt from limit |

#### Pop / Synth-Pop / Dance-Pop / K-Pop / Piano Pop

| Section | Max Lines | Notes |
|---------|-----------|-------|
| Verse | 6–8 | |
| Chorus | 4–6 | |
| Bridge | 4 | |
| Pre-Chorus | 2–4 | |

#### Rock / Alt-Rock / Indie Rock / Grunge / Garage Rock / Post-Rock / Prog Rock

| Section | Max Lines | Notes |
|---------|-----------|-------|
| Verse | 6–8 | |
| Chorus | 4–6 | |
| Bridge | 4 | |
| Pre-Chorus | 2–4 | |
| Guitar solo / Interlude | 0 (instrumental) | Use `[Guitar Solo]` or `[Interlude]` tag |

#### Punk / Hardcore Punk / Emo / Pop-Punk / Ska Punk

| Section | Max Lines | Notes |
|---------|-----------|-------|
| Verse | 4–6 | Short, fast — keep it tight |
| Chorus | 2–4 | Punchy, shoutable |
| Bridge | 2–4 | |
| Pre-Chorus | 2 | |

#### Metal / Thrash / Doom / Black Metal / Metalcore / Industrial

| Section | Max Lines | Notes |
|---------|-----------|-------|
| Verse | 4–8 | |
| Chorus | 4–6 | |
| Bridge | 4 | |
| Pre-Chorus | 2–4 | |
| Breakdown | 2–4 | Often instrumental or minimal lyrics |

#### Country / Folk / Americana / Bluegrass / Singer-Songwriter / Blues

| Section | Max Lines | Notes |
|---------|-----------|-------|
| Verse | 4–8 | Storytelling verses can use the full 8 |
| Chorus | 4–6 | |
| Bridge | 2–4 | |
| Pre-Chorus | 2–4 | |

#### Electronic / EDM / House / Techno / Trance / Dubstep / DnB / Synthwave

| Section | Max Lines | Notes |
|---------|-----------|-------|
| Verse | 4–6 | Vocals are sparse in electronic — less is more |
| Chorus / Hook | 2–4 | Often just a repeated phrase |
| Bridge | 2–4 | |
| Drop | 0 (instrumental) | Use `[Drop]` or `[Break]` tag |

#### Ambient / Lo-Fi / Chillwave / Trip-Hop / Vaporwave

| Section | Max Lines | Notes |
|---------|-----------|-------|
| Verse | 2–4 | Minimal vocals, atmosphere first |
| Chorus / Hook | 2–4 | |
| Bridge | 2 | |

#### R&B / Soul / Funk / Gospel

| Section | Max Lines | Notes |
|---------|-----------|-------|
| Verse | 6–8 | |
| Chorus | 4–6 | |
| Bridge | 4 | |
| Pre-Chorus | 2–4 | |
| Vamp / Ad-lib | Flexible | Outro vamps are genre-standard |

#### Jazz / Swing / Bossa Nova

| Section | Max Lines | Notes |
|---------|-----------|-------|
| Verse | 4–8 | Standard 32-bar form |
| Chorus | 4–6 | |
| Bridge | 4–8 | Jazz B-sections can run longer |

#### Reggae / Dancehall / Afrobeats

| Section | Max Lines | Notes |
|---------|-----------|-------|
| Verse | 4–8 | |
| Chorus / Hook | 4–6 | |
| Bridge | 2–4 | |
| Toast / DJ | 4–8 | Dancehall toasting sections |

#### Ballad (any genre)

| Section | Max Lines | Notes |
|---------|-----------|-------|
| Verse | 4–6 | Slower tempo = fewer lines needed |
| Chorus | 4–6 | |
| Bridge | 2–4 | |

### Section Length Enforcement

**Hard rules — enforce before presenting lyrics:**

1. **Count lines per section** after drafting. Compare against genre table above.
2. **If a section exceeds its max**: Trim it. Don't ask — cut it down, then present.
3. **Hip-hop verse over 8 lines**: Split into two verses or cut. No exceptions.
4. **Any chorus over 6 lines**: Trim. A long chorus loses its punch and causes Suno to rush.
5. **Electronic verse over 6 lines**: Cut. Electronic tracks need space, not walls of text.
6. **Punk sections over limits**: Punk is short and fast. If it's long, it's not punk.
7. **When unsure about genre**: Use the Pop/Rock defaults (6–8 verse, 4–6 chorus, 4 bridge).
8. **Also check BPM-aware limits** in the Lyric Density & Pacing section below — a genre may allow 8-line verses at fast tempo but only 4 at slow tempo.

**Suno-specific reasoning**: Long sections cause:
- Vocal rushing (cramming words into fixed musical time)
- Loss of clarity (words blur together)
- Section compression (Suno shortens the music to fit)
- Skipped lyrics (Suno drops lines entirely)

---


---

## Lyric Density & Pacing (Suno)

Suno rushes through dense verse blocks. Verse length must match tempo and feel. **The slower the BPM, the fewer lines Suno can handle** without rushing, compressing, or skipping.

**Genre-specific Suno verse limits are in each genre's README** under "Lyric Conventions → Density/pacing (Suno)". Always check the genre README for the track you're writing.

### Suno Verse Length Defaults

| Genre Family | Default Lines/Verse | Max Safe | Topics/Verse | Key Rule |
|---|---|---|---|---|
| **Hip-Hop / Rap** | 8 (4 couplets) | 8 | 2-3 | Never exceed 8; half-time trap = treat as 65-75 BPM |
| **Pop** | 4 | 6-8 | 1-2 | Chorus-first — longer verses bury the hook |
| **Rock** | 6 | 8 | 2 | 120 BPM sweet spot; guitar riffs need space |
| **Punk** | 4 | 4 | 1 | Fast, short, every word punches |
| **Hardcore Punk** | 2-3 | 3 | 1 | Extreme tempo; shouted, minimal |
| **Metal** | 6-8 | 10 | 2-3 | Vocal delivery compresses syllables; thrash handles most |
| **Doom Metal** | 4 | 6 | 1 | Slowest metal; each word carries crushing weight |
| **Country / Folk** | 6 | 8 | 1-2 | Storytelling pace; ballads drop to 4 |
| **Blues** | 3 (AAB) | 3 | 1 | Rigid structure — never break AAB |
| **Electronic / EDM** | 2-4 | 4 | 1 | Production is the star; vocals are texture |
| **Ambient / Shoegaze** | 0-2 | 4 | 1 | Often instrumental; vocals are texture |
| **R&B / Soul** | 6 | 8 | 1-2 | Melisma stretches syllables; groove > density |
| **Jazz** | 6-8 | 8 | 1-2 | Bebop: 2-4 lines; ballads: 6-8 |
| **Singer-Songwriter** | 6-8 | 8 | 2-3 | Confessional; stripped-back production carries words |
| **Progressive Rock** | 8-10 | 12 | 3-4 | The exception — handles long verses |

### BPM-Aware Limits (Universal Fallback)

When a genre README doesn't specify, use this table:

| BPM Range | Max Lines/Verse | Topics/Verse | Feel |
|-----------|----------------|-------------|------|
| < 80 | 4 | 1-2 | Slow, heavy — fewer lines needed |
| 80-94 | 4-6 | 1-2 | Laid back, mid-tempo |
| 94-110 | 6 | 2-3 | Energetic, driving |
| 110-140 | 6-8 | 2-3 | Standard rock/pop range |
| 140+ | 4 | 1 | Fast — short verses, energy over density |

**Default: 4 lines per verse** unless the genre and tempo justify more.

### Topic Density

- Max **1-2 topics per 4-line verse**, **2-3 per 6-8 line verse**
- If a verse covers 3+ topics in 4 lines, split it
- **Prefer more short verses over fewer dense verses** — two 4-line verses beat one 8-line verse

### Red Flags

- 8-line verse at any BPM under 100 — too dense for Suno
- Verse reads like a list of names/facts — it's a Wikipedia entry, not a verse
- Track concept says "laid back" but verses are wall-to-wall syllables
- More than 3 proper nouns introduced in a single verse
- Every verse in the song is dense (no breathing room anywhere)

### Fix

When a verse is too dense:
1. **Prefer adding a verse** over cutting content (spread, don't compress)
2. Let each topic have at least a full couplet (2 lines) to land
3. Re-read with the BPM in mind — can you actually sing/rap this at tempo without rushing?

### Streaming Exception

Streaming lyrics (distributor text) can have longer verse blocks since they aren't generated by Suno. But verse BREAKS should still align with the Suno structure so the text matches what's actually sung.

### Process

Before finalizing any track, ASK: "Does the verse length match the BPM and mood described in Musical Direction?" Check the genre README's `Density/pacing (Suno)` line. If the verse exceeds the default, flag it to the user.

---

