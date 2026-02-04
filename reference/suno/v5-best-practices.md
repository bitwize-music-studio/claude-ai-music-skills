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

### Keep It Simple — Avoid Prompt Fatigue

V5 is literal. Complex descriptions confuse it. The **sweet spot is 4–7 descriptors** — fewer than 4 lacks direction, more than 7 causes "prompt fatigue" where V5 dilutes or ignores tags.

```
❌ Bad (prompt fatigue — too many tags):
"Ethereal indie folk with vintage analog warmth and melancholic
undertones, finger-picked acoustic, tape hiss, lo-fi, intimate,
breathy, whispery, nostalgic, contemplative, minimalist production"

❌ Bad (too vague):
"Nice upbeat music"

✅ Good (4-7 descriptors):
"Sad indie folk, acoustic, gentle, breathy female vocal, intimate"
```

**Rule of thumb**: If your prompt has 8+ comma-separated descriptors, cut it. V5 understands context and fills in gaps intelligently.

### The Four-Part Anatomy

```
1. Genre + Era + Influences
   "90s alt-rock with Britpop undertones"

2. Tempo/BPM + Key (optional)
   "120 BPM, A minor"

3. Instrumentation & Arrangement
   "Live drums with room ambience; palm-muted guitars; warm bass"

4. Production & Mix Notes
   "Analog glue compression; tape saturation; lead vocal upfront"
```

### Alternative: Top-Loaded Palette Formula

A simpler approach that front-loads the most impactful elements:

```
[Mood] + [Energy] + [2 Instruments] + [Vocal Identity]
```

**Example**:
```
Melancholic, slow-burn, piano and strings, female alto with subtle vibrato
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

### Keep Lyrics Concise

Shorter lyrics generate better results. Dense or long lyrics cause Suno to rush, compress sections, or skip content entirely. Target **200–350 words** for most genres (up to 500 for hip-hop/rap). Two verses plus chorus plus bridge is the sweet spot — avoid 4–5 verse songs.

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

For environmental sounds (rain, wind, fire), mention in **both** the Lyrics Box and Style Prompt:

**Lyrics Box**:
```
[Verse]
Rain falling on the window
Thunder in the distance
```

**Style Prompt**:
```
lofi effects rain, ambient thunder
```

**Why Both?**: Repetition strengthens AI recognition of desired atmosphere

**Common Atmospheres**:
- `rain` + "lofi effects rain" (style prompt)
- `wind` + "ambient wind textures" (style prompt)
- `fire` + "crackling fire ambience" (style prompt)
- `ocean` + "ocean waves background" (style prompt)

### Syllable Control

- **Verse lines**: 7–9 syllables per line for best vocal lock-in
- **Chorus lines**: 10–12 syllables per line
- **Overall range**: 6–12 syllables per line
- Use hyphens for sustained notes: `lo-ove`, `sooo-long`
- Writing `Loooove` or `Ohhhh` creates sustained notes and vocal emphasis
- ALL CAPS can create a shouting effect: `NEVER AGAIN`
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

## Bar Count Targeting

V5 supports targeting specific bar counts per section using numbers after section tags:

```
[INTRO 4] [VERSE 1 8] [PRE 4] [CHORUS 8] [VERSE 2 8] [PRE 4] [CHORUS 8] [BRIDGE 8] [CHORUS 8] [OUTRO 4]
```

The numbers represent target bar counts for each section. This gives you finer control over song structure and pacing beyond just section tags.

**Notes**:
- Results are approximate — Suno treats these as targets, not guarantees
- Combine with explicit section tags in the lyrics box for best results
- Works well for controlling intro/outro length

---

## Creative Sliders

V5 includes sliders in the generation interface that affect output:

| Slider | Effect | Guidance |
|--------|--------|----------|
| **Weirdness** | Higher = more experimental and unexpected choices | Raise to explore; lower for predictable, hooky results |
| **Style Influence** | Higher = tighter adherence to style prompt | Raise for genre purity; lower for looser fusions |
| **Audio Influence** | Controls how much uploaded audio shapes the output | Appears only when audio is uploaded |

**Tips**:
- Start with default values and adjust after hearing the first generation
- High Weirdness + specific genre tag = interesting results within a genre
- Low Style Influence is useful when you want the AI to surprise you

---

## Personas

**Available to**: Pro and Premier subscribers

Personas let you save the "essence" of a generated song — vocals, style, vibe — and reuse it across different songs. This is the most reliable way to maintain vocal consistency across an album.

### Creating a Persona

1. Generate a song with vocals you like
2. Save the song's vocal identity as a Persona
3. Apply the Persona to future generations

### Best Practices

- **Keep prompts simple when using Personas** (1–2 genres). The Persona carries the vocal identity, so you don't need to re-describe the voice.
- **Personas can be dominant** — if your style prompt fights the Persona, the Persona usually wins. Work with it, not against it.
- **Voice Personas lock in a specific AI singer** independent of musical style. You can move a Persona across genres (e.g., same singer doing folk and electronic).

### Limitations

- 200 free songs with Personas per billing cycle; then 10 credits per song
- December 2025 update made Personas more dominant in the mix — adjust style prompts if the Persona is overpowering other elements

---

## Song Editor

V5 includes a section-level Song Editor that lets you modify individual parts of a generated song without regenerating the whole track.

### Capabilities

| Action | Description |
|--------|-------------|
| **Remake** | Regenerate a section with the same prompt |
| **Rewrite** | Change lyrics/melody for a section while preserving role and intent |
| **Extend** | Append bars at the tail of a section |
| **Reorder** | Move sections around in the arrangement |
| **Delete** | Remove weak sections; transitions are engine-handled |

### Workflow

1. Generate a full song
2. Identify sections that need improvement
3. Use Remake/Rewrite on individual sections
4. Extend 1–2 bars into/out of a chorus for smooth transitions
5. Delete weak regions — the engine handles transition smoothing

**Note**: Keep extensions to 2–3 times max per song. Extending too many times causes uneven lyrics, weaker vocals, and quality drops.

---

## Token Biases Warning

Suno's model has known token biases — it gravitates toward certain words when generating or interpreting lyrics. These are model preferences, not creative choices:

**Common bias words**: Neon, Echo, Ghost, Silver, Shadow, Whisper, Crystal, Velvet

If you find these words appearing in your generations when you didn't write them, it's the model defaulting to its favorites. Use the "Do not change any words. Sing exactly as written." instruction to prevent unwanted substitutions.

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

## Suno Output Loudness (Pre-Mastering)

These are typical loudness levels Suno generates — **not** final mastering targets. For streaming platform delivery, master all tracks to **-14 LUFS / -1.0 dBTP** regardless of genre. See `/reference/mastering/mastering-workflow.md` for mastering procedures.

| Genre | Typical Suno Output |
|-------|---------------------|
| Pop/EDM | -9 to -7 LUFS |
| Lo-Fi | -12 to -11 LUFS |
| Podcast/Spoken | -16 to -14 LUFS |

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
- **V4.5 may produce better results for heavy genres** (metal, hardcore) — consider testing both if V5 output sounds thin

---

## Ownership & Licensing (Post-November 2025)

Following the Warner Music Group partnership (November 2025):

- Subscribers get **"commercial use rights"** but are **"generally not considered the owner"** of generated content
- Suno will **not take a revenue share** from monetization
- Artists/songwriters retain full control over name/image/likeness/voice use
- New models trained on **licensed WMG catalog** are planned for 2026
- Current models will be **deprecated** when licensed models launch — download your catalog

**Action item**: Download all important generations now. Current-model content may become inaccessible when licensed models roll out.

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
  - Constructs style prompts and genre tags
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
- [How to Write Effective Prompts for Suno Music (2026)](https://www.soundverse.ai/blog/article/how-to-write-effective-prompts-for-suno-music-1128)
- [Suno V5 Secrets: Crafting AI-Generated Songs](https://iflow.bot/suno-v5-secrets-crafting-ai-generated-songs/)
- [Suno V5 Playbook: Complete Guide](https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/suno-v5-playbook-complete-guide)
- [Song Editor in Suno V5: Composer's Workflow](https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/song-editor-in-suno-v5-workflow)
- [Introducing Personas — Suno Blog](https://suno.com/blog/personas)
- [Suno AI Personas Update (Dec 2025)](https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/suno-ai-personas-update-dec-2025-what-changed-how-to-use-it)
- [Suno Previews 2026 Changes Under Warner Music Deal](https://www.digitalmusicnews.com/2025/12/22/suno-warner-music-deal-changes/)
- [WMG and Suno Partnership Announcement](https://www.prnewswire.com/news-releases/warner-music-group-and-suno-forge-groundbreaking-partnership-302626017.html)
