# Suno Structure Tags Reference

Complete reference for song structure tags in Suno lyrics.

> **Suno tag/metatag terminology**: "metatag" gets used loosely — here's the actual taxonomy across this plugin's reference docs:
> - **Structure tags** (this file) — `[Verse]`, `[Chorus]`, etc. Define song sections. Go in the Lyrics Box.
> - **Delivery/mood bracket tags** (this file, "Custom Mood/Style Tags" below) — `[Whispered]`, `[Shout]`, etc. Short, standalone Lyrics Box tags that color delivery without defining a section.
> - **Style Box descriptors** ([voice-tags.md](voice-tags.md), [instrumental-tags.md](instrumental-tags.md)) — comma-separated prose in the Style Box (`gravelly, belting, Southern rock vocal`), not bracket tags. This is how Suno V5 actually wants mood/energy/instrumentation — see the "Keep It Simple" guidance in [v5-best-practices.md](v5-best-practices.md).
> - **Inline lyrical metatags** ([tips-and-tricks.md](tips-and-tricks.md#vocal-sounds-too-young-despite-maturedeep-descriptors)) — a per-section descriptor prefixed inside the section tag itself, e.g. `[Verse 1: Raspy older female vocal, husky contralto]`. An escalation technique for stubborn vocal-identity issues, not a default pattern.
>
> Rule of thumb: structure tags are mandatory every section; delivery bracket tags and inline metatags are optional accents (1-3 max per section — see "Performance Cues" below); mood/energy/instrumentation belongs in Style Box prose, not bracket tags.

## Basic Structure Tags

### Intro
```
[Intro]
```
**Note**: The `[Intro]` tag is notoriously unreliable. Better alternatives:
```
[Short Instrumental Intro]
[Intro - Spoken]
```

### Verse
```
[Verse]
[Verse 1]
[Verse 2]
[Catchy Verse]
```

### Chorus
```
[Chorus]
[Catchy Hook]
[Hook]
```

### Bridge
```
[Bridge]
[Pre-Chorus]
[Post-Chorus]
```

### Instrumental Sections
```
[Break]
[Interlude]
[Guitar Solo Interlude]
[Percussion Break]
[melodic interlude]
```

### Endings
```
[Outro]
[End]
[Fade In]
[Fade Out]
[Fade to End]
[Big Finish]
[Refrain]
```

## Custom Mood/Style Tags

These descriptive tags influence delivery. Use 1-3 per section, same discipline as Performance Cues below — stacking many at once causes the "prompt fatigue" described in [v5-best-practices.md](v5-best-practices.md):

```
[Shout]          - Aggressive, shouted delivery
[Whimsical]      - Playful, light tone
[Melancholy]     - Sad, reflective mood
[Spoken]         - Spoken word, not sung
[Whispered]      - Quiet, intimate
[Energetic]      - High energy delivery
[Aggressive]     - Intense, confrontational delivery
[Intimate]       - Personal, close, hushed tone
[Playful]        - Lighthearted, fun energy
[Triumphant]     - Victorious, anthemic delivery
[Vulnerable]     - Raw, exposed emotion
[Haunting]       - Eerie, unsettled mood
```

## Example Song Structure

### Basic Pop/Rock Structure
```
[Short Instrumental Intro]

[Verse 1]
First verse lyrics...

[Chorus]
Hook lyrics...

[Verse 2]
Second verse lyrics...

[Chorus]
Hook lyrics...

[Bridge]
Bridge lyrics...

[Chorus]
Hook lyrics...

[Outro]
Closing lyrics...

[Fade Out]
```

### Hip-Hop Structure
```
[Intro - Spoken]
Intro spoken word...

[Verse 1]
First verse...

[Chorus]
Hook...

[Verse 2]
Second verse...

[Chorus]
Hook...

[Verse 3]
Third verse...

[Outro]
Closing...

[End]
```

### Punk Structure (Short & Fast)
```
[Intro]

[Verse 1]
Fast verse...

[Chorus]
Shout-along chorus...

[Verse 2]
Fast verse...

[Chorus]
Shout-along chorus...

[Break]

[Chorus]
Final chorus...

[Big Finish]
```

## Bar Count Targeting (V5)

V5 supports targeting specific bar counts per section by adding numbers after tags:

```
[INTRO 4] [VERSE 1 8] [PRE 4] [CHORUS 8] [VERSE 2 8] [PRE 4] [CHORUS 8] [BRIDGE 8] [CHORUS 8] [OUTRO 4]
```

Numbers represent target bar counts. Results are approximate — Suno treats them as guidance, not strict limits. Useful for controlling intro/outro length and balancing section proportions.

---

## Performance Cues

Add **1–3 performance cues per section** to influence delivery without overloading:

```
[Verse 1 - quiet, intimate]
Lyrics here...

[Chorus - building, anthemic]
Lyrics here...

[Bridge - raw, exposed]
Lyrics here...
```

**Rule**: More than 3 cues per section causes noise. Keep it focused.

---

## Tag Reliability Notes

V5 improved tag reliability significantly over V4/V4.5. Tags that were inconsistent in earlier versions now produce more predictable results.

### Reliable Tags
- `[Verse]`, `[Verse 1]`, etc.
- `[Chorus]`
- `[End]`
- `[Fade Out]`
- `[Pre-Chorus]` (improved in V5)

### Moderately Reliable
- `[Bridge]`
- `[Break]`
- `[Outro]`

### Less Reliable
- `[Intro]` - Use descriptive alternatives
- `[Post-Chorus]`, `[Fade In]` - Less field-tested than their established counterparts (`[Pre-Chorus]`, `[Fade Out]`) — test before relying on them
- Custom tags - Results vary

## Tips

1. **Use numbered verses** (`[Verse 1]`, `[Verse 2]`) for clarity
2. **Keep intros short** to prevent burying vocals
3. **Combine tags with descriptions**: `[Soft Verse]`, `[Building Chorus]`
4. **End explicitly** with `[End]` or `[Fade Out]` for clean endings
5. **Test variations** - tag effectiveness varies by genre/model

---

## Related Skills

- **`/bitwize-music:lyric-writer`** - Lyric writing with automatic section tagging
  - Automatically adds section tags to lyrics
  - Uses tags from this reference guide
  - Ensures proper song structure

- **`/bitwize-music:suno-engineer`** - Technical Suno V5 prompting
  - Applies section tags correctly in lyrics boxes
  - Optimizes tag placement for generation results
  - Uses this guide as reference for tag selection

- **`/bitwize-music:lyric-reviewer`** - Pre-generation QC
  - Verifies section tags are present and correct
  - Checks for proper song structure
  - Ensures tags follow Suno best practices

## See Also

- **`/reference/suno/v5-best-practices.md`** - Complete Suno V5 prompting guide, style box construction, Sound Effects/Atmospheric tags
- **`/reference/suno/pronunciation-guide.md`** - Phonetic spelling and pronunciation fixes for lyrics
- **`/reference/suno/voice-tags.md`** - Vocal style descriptors, Duet pattern, Production/Vocal FX descriptors
- **`/reference/suno/tips-and-tricks.md`** - Inline lyrical metatags for stubborn vocal-identity issues
- **`/skills/lyric-writer/SKILL.md`** - Complete lyric writing workflow and standards
