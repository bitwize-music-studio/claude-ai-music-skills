# Suno Structure Tags Reference

Complete reference for song structure tags in Suno lyrics.

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
```

### Bridge
```
[Bridge]
[Pre-Chorus]
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
[Fade Out]
[Fade to End]
[Big Finish]
[Refrain]
```

## Custom Mood/Style Tags

These descriptive tags influence delivery:

```
[Shout]          - Aggressive, shouted delivery
[Whimsical]      - Playful, light tone
[Melancholy]     - Sad, reflective mood
[Spoken]         - Spoken word, not sung
[Whispered]      - Quiet, intimate
[Energetic]      - High energy delivery
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

## Tag Reliability Notes

### Reliable Tags
- `[Verse]`, `[Verse 1]`, etc.
- `[Chorus]`
- `[End]`
- `[Fade Out]`

### Moderately Reliable
- `[Bridge]`
- `[Break]`
- `[Outro]`

### Less Reliable
- `[Intro]` - Use descriptive alternatives
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

- **`/reference/suno/v5-best-practices.md`** - Complete Suno V5 prompting guide, style box construction
- **`/reference/suno/pronunciation-guide.md`** - Phonetic spelling and pronunciation fixes for lyrics
- **`/reference/suno/voice-tags.md`** - Vocal style descriptors and manipulation tags
- **`/skills/lyric-writer/SKILL.md`** - Complete lyric writing workflow and standards
