# Suno V5 Best Practices

Comprehensive guide for getting the best results with Suno V5.

> **Related skills**: `/bitwize-music:suno-engineer` (interactive prompting), `/bitwize-music:pronunciation-specialist` (phonetic review)
> **Related docs**: [pronunciation-guide.md](pronunciation-guide.md), [structure-tags.md](structure-tags.md), [voice-tags.md](voice-tags.md), [tips-and-tricks.md](tips-and-tricks.md)

## Quick Start Formula

```
[genre], [subgenre], [instruments], [mood], [tempo], [vocal description]
```

**Example**:
```
nerdcore hip-hop, glitchy IDM beats, lo-fi digital artifacts,
nostalgic, melancholic, 85 BPM, male vocals, gravelly voice, introspective
```

---

## V5 Key Improvements

| Feature | Description |
|---------|-------------|
| Intelligent Composition | Coherent structure from 30-second hooks to 8-minute epics |
| Studio-Grade Audio | 44.1 kHz output with fuller, more balanced mixes |
| Vocal Engine | Human-like vocals with breath, emotion, vibrato control |
| 10x Faster | Seconds instead of minutes for generation |
| 12 Stem Extraction | Vocals, drums, bass, guitar, keyboard, strings, brass, etc. |
| Extended Length | Up to 8 minutes per generation |
| Persistent Memory | Vocal characters and instruments remain stable across project generations |
| Granular Controls | Tempo, key, dynamics, arrangement with optional automation |

## Critical Rule: Don't Reuse Old Prompts

**Suno CTO's #1 recommendation**: Don't rerun old V4/V4.5 prompts on V5.

V5 listens differently and needs less instruction. Write new prompts and experiment.

---

## Prompt Construction

### Keep It Simple

V5 is literal. Complex descriptions confuse it.

```
❌ Bad:
"Ethereal indie folk with vintage analog warmth and melancholic
undertones reminiscent of early morning mist"

✅ Good:
"Sad indie folk, acoustic, gentle"
```

### The Four-Part Anatomy

```
1. Genre + Era + Influences
   "90s alt-rock with Britpop undertones; Oasis meets The Verve"

2. Tempo/BPM + Key (optional)
   "120 BPM, A minor"

3. Instrumentation & Arrangement
   "Live drums with room ambience; palm-muted guitars; warm bass"

4. Production & Mix Notes
   "Analog glue compression; tape saturation; lead vocal upfront"
```

---

## Genre-Specific Tips

### Hip-Hop / Rap
- Specify subgenre: boom bap, trap, lo-fi, nerdcore
- Include beat style: 808s, sampled drums, crispy snares
- Describe flow if important

### Punk
- Specify subgenre: pop-punk, hardcore, skate punk
- Note tempo (punk is usually fast)
- Describe vocal style: snotty, shouted, melodic

### Electronic
- Name specific subgenres: house, techno, IDM, synthwave
- Describe synth types: analog, digital, chiptune
- Include BPM (critical for dance music)

### Folk/Acoustic
- Specify instruments: fingerpicking, banjo, mandolin
- Note tempo and mood
- Describe vocal intimacy level

---

## Vocal Control

### Top-Anchor Approach

Start your prompt with vocal description before lyrics:

```
Female pop vocalist, breathy, intimate, 90s R&B groove

[Verse 1]
Lying in the dark tonight...
```

### Vocal Persona Examples

```
Male tenor, warm, slightly raspy, indie rock delivery
```
```
Female alto, sultry, breathy, R&B phrasing with subtle runs
```
```
Male baritone, gravelly, introspective, folk storyteller
```

### Section-by-Section Dynamics

| Section | Dynamics | Phrasing | Vibrato |
|---------|----------|----------|---------|
| Verse | Low | Tight | Minimal |
| Pre-Chorus | Rising | Shorter | Growing |
| Chorus | High/Open | Sustained | Full |
| Bridge | Variable | New texture | Altered |

---

## Lyric Formatting

### Use Explicit Section Tags

```
[Verse 1]
Walking through the rain tonight
Memories fading out of sight

[Pre-Chorus]
But I still remember when

[Chorus]
We were young and free
```

### Sound Effects

Trigger vocal sound effects by placing them in brackets:

```
[Verse 1]
Walking through the night [footsteps]
I hear a voice calling [echo]
Then suddenly [laughter] breaks the silence
```

**Common Effects**:
- `[laughter]` - Natural laughing
- `[screaming]` - Vocal scream
- `[whisper]` - Whispered delivery
- `[echo]` - Echo/reverb effect
- `[crowd]` - Crowd noise
- `[applause]` - Clapping/applause

**Note**: Effects work best when placed mid-line, not as standalone lines

### Atmospheric Effects

For environmental sounds (rain, wind, fire), mention in **both** lyrics and style box:

**Lyrics Box**:
```
[Verse]
Rain falling on the window
Thunder in the distance
```

**Style Box**:
```
lofi effects rain, ambient thunder
```

**Why Both?**: Repetition strengthens AI recognition of desired atmosphere

**Common Atmospheres**:
- `rain` + "lofi effects rain" (style box)
- `wind` + "ambient wind textures" (style box)
- `fire` + "crackling fire ambience" (style box)
- `ocean` + "ocean waves background" (style box)

### Syllable Control

- Specify ranges: "Verse lines: 8–10 syllables each"
- Use hyphens for sustained notes: `lo-ove`, `sooo-long`
- Punctuation signals phrasing: commas = pauses, ellipses = trailing

### Prevent Lyric Alterations

Add at the top of your prompt:
```
Do not change any words. Sing exactly as written.
```

---

## Negative Prompting

V5 handles exclusions reliably.

### What You Can Exclude
- Instruments: "no drums", "no electric guitar"
- Vocal effects: "no autotune", "no heavy reverb"
- Stylistic elements: "no EDM drops", "no screaming"

### Best Practices

```
✅ Good:
"Acoustic folk, warm, intimate, no drums, no electric instruments"

❌ Bad (over-specified):
"No drums, no bass, no synths, no reverb, no distortion, no..."
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Vocal too buried | Add: "lead vocal 1–2 dB louder than band" |
| Mix feels flat | Add: "bus compression 2–3 dB, slow attack/fast release" |
| Arrangement too busy | Specify rests: "verse 2: bass rests for 4 bars" |
| Genre drift | Reassert influences mid-prompt |
| Chorus not lifting | Add: "double-time hats; octave guitars" |

---

## Mix & Master Targets

| Genre | LUFS Target |
|-------|-------------|
| Pop/EDM | -9 to -7 |
| Lo-Fi | -12 to -11 |
| Podcast/Spoken | -16 to -14 |

---

## Iteration Tips

1. **Start broad**, then refine
2. **Log every attempt** - note what worked/didn't
3. **Adjust one element at a time** when refining
4. **Try different models** - V4.5 vs V5 produce different results
5. **Use extends** to build on good sections

---

## Stem Extraction

### Available Stems (12 total)

```
Vocals, Backing Vocals, Drums, Bass, Guitar,
Keyboard, Strings, Brass, Woodwinds,
Percussion, Synth, FX/Other
```

### Extraction Workflow

1. Click **More Actions (...)** on any clip
2. Hover over **Get Stems**
3. Choose **Original** or **12 Track**
4. Import into DAW

### Double-Processing for Cleaner Vocals

If vocals still contain background:
1. Run Get Stems on original
2. Run Get Stems again on extracted vocal

---

## Suno Studio (Premier Plan)

**Released**: September 25, 2025
**Availability**: Premier plan required

Suno Studio is a generative audio workstation that combines AI music generation with professional editing tools.

### Key Features

| Feature | Description |
|---------|-------------|
| **Multitrack Editor** | Timeline-based editing with drag-and-drop |
| **Stem Controls** | Generate, separate, and manipulate individual tracks |
| **MIDI Export** | Export compositions as MIDI for DAW integration |
| **Audio Upload** | Import existing audio and manipulate with AI |
| **Sample to Song** | Upload short snippets and expand to full compositions |
| **Pitch Transpose** | Adjust pitch by semitones without regenerating |

### Sample to Song Workflow

1. Click **Upload** in Suno Studio
2. Select a short audio file (guitar riff, vocal melody, etc.)
3. Describe the desired full composition in the prompt
4. Suno expands the snippet into a complete track
5. Edit on timeline, adjust stems, export MIDI

**Use Cases**:
- Record guitar lines and build full arrangements around them
- Capture vocal ideas and develop into complete songs
- Import samples and integrate into AI-generated tracks

### Pitch Transposition

**Access**: Remix → Suno Studio (Premier plan)

1. Click generated song on timeline
2. Locate transpose slider under clip settings
3. Adjust pitch by semitones (±12 range)
4. Preserves melody, phrasing, and rhythm

**Benefit**: Fix key mismatches without wasting credits on regeneration

---

## Known V5 Limitations

- Heavy electric guitars can sound "dirty" or blend together
- Acoustic nuance not always captured perfectly
- Niche subgenres (metalcore, extreme styles) may miss hallmarks
- Extreme cross-style fusions → muddy results
- Quality may degrade past 6-7 minutes

---

## Quick Reference Card

```
PROMPT TEMPLATE:
[Genre], [BPM], [mood/vibe]
[Vocal]: [gender], [texture], [style]
[Instruments]: [2-4 key instruments]
[Mix]: [1-2 production hints]

STRUCTURE TAGS:
[Intro] [Verse] [Pre-Chorus] [Chorus]
[Bridge] [Breakdown] [Outro] [End]

VOCAL TAGS:
breathy, raspy, powerful, intimate, ethereal,
gravelly, smooth, aggressive, tender, soulful

MIX TAGS:
punchy, wide stereo, vintage, modern, lo-fi,
crisp, warm, bright, deep, spacious
```

---

## Related Skills

- **`/bitwize-music:suno-engineer`** - Technical Suno V5 prompting expert
  - Uses this guide as reference
  - Constructs style boxes and genre tags
  - Optimizes prompts for best generation results

- **`/bitwize-music:lyric-writer`** - Lyric writing with Suno formatting
  - Automatically formats lyrics with section tags
  - Prepares Suno-ready lyrics boxes
  - Applies pronunciation fixes for Suno

- **`/bitwize-music:lyric-reviewer`** - Pre-generation QC gate
  - Verifies lyrics follow Suno best practices
  - Checks section tags and structure
  - Ensures lyrics are ready for generation

## See Also

- **`/reference/suno/pronunciation-guide.md`** - Phonetic spelling, homographs, pronunciation fixes
- **`/reference/suno/structure-tags.md`** - Complete list of section tags ([Verse], [Chorus], etc.)
- **`/reference/suno/genre-list.md`** - 500+ genre tags for style prompts
- **`/reference/suno/voice-tags.md`** - Vocal style descriptors and tags
- **`/reference/suno/tips-and-tricks.md`** - Troubleshooting, extending tracks, operational tips
- **`/skills/suno-engineer/SKILL.md`** - Complete Suno engineer skill documentation

---

## Sources

- [10 Suno v5 Prompt Patterns That Never Miss](https://plainenglish.io/blog/i-made-10-suno-v5-prompt-patterns-that-never-miss)
- [Negative Prompting in Suno v5](https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/negative-prompting-suno-v5-guide)
- [How to Instruct Suno v5 with Lyrics](https://www.cometapi.com/how-to-instruct-suno-v5-with-lyrics/)
