# Suno Best Practices

Comprehensive guide for getting the best results with Suno. Per-model detail (v6, v6-wild, v6-mini, Custom Models) lives in [models.md](models.md).

> **Related skills**: `/bitwize-music:suno-engineer` (interactive prompting), `/bitwize-music:pronunciation-specialist` (phonetic review)
> **Related docs**: [pronunciation-guide.md](pronunciation-guide.md), [structure-tags.md](structure-tags.md), [voice-tags.md](voice-tags.md), [tips-and-tricks.md](tips-and-tricks.md)

---

## The Current Models

Suno's models are the **v6 family**: `v6` (flagship; Pro/Premier), `v6-wild` (exploration; Pro/Premier) and `v6-mini` (everyone), plus private **Custom Models**. Which to pick, and each model's defaults and quirks: [models.md](models.md).

**The prompt surface:**

| Field / limit | Value | Notes |
|---|---|---|
| Style box | 1,000 chars | |
| Lyrics box | 5,000 chars | |
| Exclude Styles | 1,000 chars | the only reliable negative path |
| Simple-mode prompt | 3,000 chars | Simple Mode is not the plugin's path (see below) |
| Maximum length | 8 minutes | Auto and Extend; the Duration slider's Custom range is 10 s–6:00 |
| Structure tags, Performance Cues | bracket tags shape arrangement; per-section cues are read **(unverified — see CHANGELOG open verification)** | |
| Weirdness / Style Influence / Audio Influence | defaults 50 / 50 / 25 | see [creative-sliders.md](creative-sliders.md) |
| Vocal Gender, Exclude Styles, Duration (Auto / Custom) | under More Options in Advanced Mode | |
| Credits | 10 per generation (two songs) | same on all three models |

**Two controls decide whether your prompt is used as written.**

- **Variety** (More Options; default *Normal* on v6 and v6-mini, *Off* on v6-wild). At any setting above Off, Suno **rewrites and expands your style prompt** and diverges the two takes. Suno's own FAQ: "If you'd like to retain full control of your style tags, reduce the Variety slider to 0." **This plugin's rule: Variety Off whenever the Style Box was engineered.** The five stops and the mechanism are in [creative-sliders.md § Variety](creative-sliders.md#variety).
- **Max Mode** (toggle). Suno's copy: "Uses more compute to maximize consistency throughout the song. Costs 2x credits per song." — so a generation costs 20 credits. Suno recommends it for songs longer than two minutes, covers that should stay close to the source, style transfer, and keeping vocals consistent. Several users report the mix going muffled after roughly 2:30 on standard mode **(unverified)**; for album tracks the plugin defaults Max Mode On.

**Simple Mode vs Advanced Mode.** Suno's headline features (plain-language section edits, single-lyric swaps, multi-source mashups, sample-and-isolate, image / video / voice-memo inputs) live in **Simple Mode**. Simple Mode treats typed lyrics as a seed and writes extra lines, and switching to Advanced does not carry the prompt across; its single-word lyric replacement is reported unreliable and syllable-sensitive (single source). **The plugin's workflow is Advanced Mode only**: finished lyrics in the Lyrics Box, an engineered Style Box, settings from the track's Generation Settings table.

**Prompting posture.** Suno's own advice: start with the default settings, and "if you want imperfect vocals, write that directly into your prompt … describe the instrumentation, the recording quality, or maybe the performance." On Duration Auto, outputs often run slower, sparser and longer than the prompt implies — state tempo and density explicitly. Output quality is genre-dependent: rock, metal, grunge, blues-rock and alt-country are the weakest (vocals drift to a generic or artifact-laden timbre — reported independently by several testers, including a professional mixer), while pop, drum & bass and UK garage were praised; `v6-wild` is the better first pass on the weak genres, then Cover the keeper on `v6`. Two testers report a narrower stereo image than they expected. Covers hold the source melody and structure well when Variety is Off; with Variety on, melodies drift (Max Mode also counters it). Prompts written for earlier Suno generations do not transfer — re-prompt, don't rerun (see [models.md § Made before v6](models.md#made-before-v6)).

**Artist names** are rewritten with a visible notice ("Artist name '…' replaced"). The label deals fund future opt-in artist products, not prompt targets.

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

## Key Capabilities

| Feature | Description |
|---------|-------------|
| Intelligent Composition | Coherent structure from 30-second hooks to 8-minute epics |
| Studio-Grade Audio | 44.1 kHz output with a full, balanced mix |
| Vocal Engine | Human-like vocals with breath, emotion, vibrato control |
| Stem Separation (3 modes) | Auto Split (12 stems), Split from Mix (target + the rest), Advanced Split (~100 instruments) — Auto Split output shows bleed/shared reverb in practice; see § Stem Extraction |
| Extended Length | Up to 8 minutes per generation (Auto/Extend; Custom Duration caps at 6:00) |
| Persistent Memory | Vocal characters and instruments remain stable across project generations |
| Granular Controls | Tempo, key, dynamics, arrangement with optional automation |

## Prompt Construction

### Keep It Simple — Avoid Prompt Fatigue

Suno is literal, and it dilutes attention when descriptors repeat the same idea. **Every descriptor should earn its place** — genre, instrument, vocal identity, production texture, mood, tempo. A focused style box of ~10 descriptors works well; what hurts is a *synonym-pile* (five mood words that all mean "soft") that gives Suno nothing new to act on.

> **On the "4–7 descriptors" rule of thumb**: 4–7 is a useful starting point, **not a Suno-official rule**. Rich ~10-descriptor style boxes are common and effective when every term does distinct work. Trim *synonyms*, not *detail*. (The hard "cut everything past 7" version of this rule traces to a single third-party guide and isn't borne out in practice — real style boxes routinely run richer.)

```
❌ Bad (synonym-pile — overlapping mood words that add nothing new):
"Ethereal indie folk with vintage analog warmth and melancholic
undertones, finger-picked acoustic, tape hiss, lo-fi, intimate,
breathy, whispery, nostalgic, contemplative, minimalist production"

❌ Bad (too vague):
"Nice upbeat music"

✅ Good (every descriptor pulls its weight):
"Sad indie folk, acoustic, gentle, breathy female vocal, intimate"
```

**Rule of thumb**: if descriptors start restating the same idea (intimate / breathy / whispery / soft), collapse them into one. Don't pad — but don't strip out genuinely distinct instrument, vocal, or production detail just to hit a number.

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

### K-Pop

K-pop presents unique challenges for Suno due to its maximalist production, multi-vocal architecture, language mixing, and mid-song genre shifts.

**Core style prompt approach:**
- Always include `K-pop` explicitly plus specific production terms (`maximalist`, `glossy`, `dynamic shifts`)
- Place vocal description first: `mixed group vocals, layered harmonies, K-pop idol group`
- Specify concept type: `girl crush`, `cute concept`, `dark concept`, `retro disco`
- Include BPM (dance tracks: 120-140, ballads: 60-80, hip-hop: 80-100)

**Getting the group vocal sound:**
- `mixed group vocals` is the single most important tag for simulating a multi-member group
- Add `layered harmonies`, `gang vocals`, `group chant` for chorus density
- Use parenthetical backing vocals in lyrics: `I'm on fire (on fire!)` to trigger echo/response
- Use `[All]` or `[Group]` section tags before chant sections
- Separate rap verses with `[Rap Verse]` tags to signal a different vocal character

**Korean-English code-switching:**
- Suno handles Korean (Hangul), but romanized Korean with hyphens remains more reliable for pronunciation control
- Format: `Sa-rang-hae` not `Saranghae`
- Add `[Clear Vocals]` or `[High Fidelity Vocals]` when mixing languages
- Keep English hooks and Korean verses as separate sections when possible

**The "switch-up" (mid-song genre change):**
- Use parenthetical genre cues at each section, not just in the global style prompt:
  ```
  [Verse 1]
  (Soft R&B groove, gentle piano)
  ...lyrics...

  [Chorus]
  (Explosive EDM drop, heavy bass, full energy)
  ...lyrics...

  [Rap Verse]
  (Aggressive trap flow, 808 bass)
  ...lyrics...

  [Bridge]
  (Stripped-back ballad, solo piano)
  ...lyrics...
  ```
- Include `genre-fluid`, `dynamic shifts`, `maximalist K-pop production` in style prompt

**K-pop section structure (more sections than Western pop):**
- Intro → Verse 1 → Pre-Chorus → Chorus → Post-Chorus → Verse 2 → Pre-Chorus → Chorus → Rap Verse → Bridge → Dance Break → Final Chorus (key change up) → Outro
- Use `[Dance Break]` with `(Instrumental, heavy beat)` and minimal/no lyrics
- Final chorus often modulates up a half-step — note `(key change up, maximum energy)` in parenthetical

**Common K-pop Suno issues:**

| Problem | Solution |
|---------|----------|
| Sounds like generic pop, not K-pop | Add `K-pop` + `maximalist` + `glossy` + specific concept keywords |
| Solo voice instead of group | Add `mixed group vocals`, `layered harmonies`, `K-pop idol group` |
| No genre switch-up mid-song | Use parenthetical genre cues per section, not just global prompt |
| Korean pronunciation garbled | Use romanized Korean with hyphens; add `[Clear Vocals]` |
| Rap verse sounds same as singing | Use `[Rap Verse]` tag with `(aggressive rap flow)` parenthetical |
| Dance break has singing | Keep lyrics minimal/empty in `[Dance Break]`; add `(Instrumental)` |

**Example K-pop style prompts by concept:**

Girl crush:
```
K-pop girl group, fierce EDM trap, sassy vocals, heavy bass drop, chant chorus, 135 BPM, confident attitude, glossy production
```

Bright/cute:
```
K-pop, bubblegum pop, bright synths, chirpy vocals, catchy hook, youthful energy, 125 BPM, layered harmonies
```

Dark/experimental:
```
K-pop, industrial synths, aggressive rap, EDM bass drops, distorted bass, maximalist chaos, 140 BPM, mixed group vocals
```

K-ballad:
```
Korean ballad, emotional piano, string orchestra, soaring vocals, key change final chorus, 70 BPM, cinematic, lush arrangement
```

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

**Human:**
- `[laughter]` - Natural laughing
- `[screaming]` - Vocal scream
- `[whisper]` - Whispered delivery
- `[sigh]` - Breathing out, reflective
- `[gasp]` - Sharp intake of breath
- `[cough]` - Clearing throat, realistic aside

**Crowd:**
- `[crowd]` - Crowd noise
- `[applause]` - Clapping/applause
- `[cheering]` - Crowd excitement

**Mechanical/transition:**
- `[echo]` - Echo/reverb effect
- `[phone ringing]` - Telephone sound, narrative device
- `[static]` - Radio noise, transition
- `[record scratch]` - DJ/hip-hop transition marker

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

Exclusions **shift the odds** against an element — they're probabilistic, not a hard filter, and won't override a prompt that strongly implies the thing you're excluding.

**Two ways to exclude:**
- **Dedicated Exclude Styles field** (Custom Mode → Advanced Options, **Pro/Premier**) — the reliable path. Put exclusions here, not buried in the main style prompt.
- **v6 ignores prompt-level exclusions.** A launch-week test typed "no drums" and "monotone vocals" into the prompt and both were ignored (The Verge, Sep 2026); use the dedicated **Exclude Styles** field (Advanced Mode → More Options, 1,000 chars) — there is no working inline fallback.

Keep it to **2–4 items** — over-specifying dilutes the effect.

### Typical Exclude Styles values (enter the element, not "no element"):
- Instruments: "drums", "electric guitar"
- Vocal effects: "autotune", "heavy reverb"
- Stylistic elements: "EDM drops", "screaming"
- **Unwanted group vocals** (a common Suno over-add): "choir", "crowd vocals", "backing vocals", "gang vocals", "call-and-response", "vocal harmonies", "layered vocals" **(unverified on v6)**

### Best Practices

```
✅ Good:
Style Box: "Acoustic folk, warm, intimate"
Exclude Styles: drums, electric instruments

❌ Bad (over-specified):
Exclude Styles: drums, bass, synths, reverb, distortion, ...
```

> **Group vocals** are probabilistic to suppress: excluding "choir / crowd / backing vocals" improves your odds, but a big anthemic prompt can still pull them back in. Pair the exclusion with a leaner, more intimate style prompt for the strongest effect.

---

## Bar Count Targeting

Suno supports targeting specific bar counts per section using numbers after section tags:

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

Suno includes sliders in the generation interface that affect output:

| Slider | Effect | Guidance |
|--------|--------|----------|
| **Weirdness** | Higher = more experimental and unexpected choices | Raise to explore; lower for predictable, hooky results |
| **Style Influence** | Higher = tighter adherence to style prompt | Raise for genre purity; lower for looser fusions |
| **Audio Influence** | Controls how much uploaded audio shapes the output | Appears only when audio is uploaded |

**Tips**:
- Start with default values and adjust after hearing the first generation
- High Weirdness + specific genre tag = interesting results within a genre
- Low Style Influence is useful when you want the AI to surprise you

> **Deep dive**: [creative-sliders.md](creative-sliders.md) — per-slider behavior, genre starting ranges, interaction effects, and when to move a slider vs. rewrite the prompt.

---

## Voices, Custom Models & My Taste

**Pro and Premier subscribers** (Voices has a limited free trial). All three carried over to v6.

### Voices (voice cloning)

Upload a clean acapella, a full track with background music, or sing directly into a mic (15 seconds to 4 minutes; the cleaner the source, the less needed). Suno then has you read a spoken phrase aloud and matches it to the upload as a consent check. Own voice only; 18+.

- **Upgrade Voice to v6.** Voices made before v6 keep working, and the Create form offers a one-click upgrade ("Upgrade your Voice for better vocal consistency. You will still be able to use it the old way if you wish."). The picker distinguishes **Voice (new) — better vocal consistency** from **Style Voice (legacy) — the old method**. Upgrade before an album run so every track uses the same engine. Which v6 models accept a Voice without the upgrade is **(unverified)**.
- **Not on instrumentals.** "Songs with Voices cannot be instrumental."
- **Max Mode On** when a Voice is attached — Suno's own recommendation for voice consistency; keep Audio Influence fairly high (~0.70–0.85, see [creative-sliders.md](creative-sliders.md)).
- **Prompting with a Voice**: drop gender/register descriptors from the style box — the Voice carries them. Keep the style prompt to 1–2 genres plus instrumentation.
- Reported, not verified: likeness is "bent rather than reproduced" on big choruses, and a Custom Model beat a Voice for vocal consistency in one launch-day test. If a Voice keeps drifting, try a Custom Model.
- Suno's Voices FAQ is stale — it still tells you to select a retired model; the picker only offers v6 models.

### Custom Models (fine-tuning)

Upload **at least 6 original tracks** (Suno: "Upload 24+ songs for best results"); creation costs **100 credits**; build time 2–5 minutes; up to **3 models per account**; private. Custom Models created before v6 were **upgraded automatically** — nothing to rebuild.

**Prompting with a Custom Model**:
- Drop generic production language ("glossy", "modern pop production") — the model already encodes your aesthetic.
- Keep genre and section-level direction. Tempo, featured instrument and mood shifts still matter.
- Best for album consistency; plain v6 is often better for deliberately off-brand tracks. A Custom Model and a Voice can be stacked.

### My Taste (all tiers)

Passive preference learning. In v6 it also feeds the **Personalize** toggle next to Variety ("Make Variety match your taste"); Personalize is off by default and only does anything when Variety is above Off — so with the plugin's Variety-Off rule it is inert. Leave it off.

---

## Personas (now Voices)

Suno folded Personas into the Voices menu in March 2026 ("Personas are now Voices"); a **Legacy** option remains for existing ones. A saved Voice does what a Persona did — carries one vocal identity across songs — plus own-voice cloning. Workflow guidance, including keeping the Style Box simple when a Voice is applied, lives in [reference/workflows/covers-and-personas.md](../workflows/covers-and-personas.md).

---

## Song Editor

Suno includes a section-level Song Editor that lets you modify individual parts of a generated song without regenerating the whole track.

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
4. **Try different models** - v6 and v6-wild read the same prompt differently; for heavy or "attitude" genres run a first pass on v6-wild and Cover the keeper on v6 (see [models.md](models.md))
5. **Use extends** to build on good sections

---

## Stem Extraction

Suno's stem separation was overhauled in June 2026 into **three selectable modes**. Suno's own materials describe the new pipeline as "listening to" the finished track and regenerating each stem from scratch with its latest model, rather than slicing the mix apart by frequency — the company frames this as why pulls sound cleaner than the old approach. That claim is Suno's own and hasn't been independently verified; some independent write-ups instead describe **Auto Split** specifically as classic frequency/spectral-mask separation, with the regenerative framing applying most clearly to **Advanced Split**.

In practice, stems pulled via **Auto Split** — the mode most people reach for — still show behavior consistent with post-hoc source separation performed on the rendered stereo mix: bleed/crosstalk between stems, reverb embedded and shared across multiple stems, and separation artifacts. Auto Split also returns a file for every one of the 12 stem categories even when the source has none of that content — expect a near-silent (~-55 dBFS) placeholder stem, not an omission. Plan mix polish around these observed behaviors, not around an assumption that "generative" means artifact-free or independently synthesized.

### Split Modes

| Mode | What it does | Output |
|------|--------------|--------|
| **Auto Split** | The classic model — splits a song into 12 stem categories at once | 12 stems |
| **Split from Mix** | Pulls one chosen instrument or voice out of the mix | 2 stems: the target, and everything-else-without-it |
| **Advanced Split** | Extracts one specific instrument chosen from a list of ~100 (drum kit to didgeridoo) | 1 targeted stem *(Premier; per-extraction credit cost)* |

**Auto Split — the 12 stems:**
```
Vocals, Backing Vocals, Drums, Bass, Guitar,
Keyboard, Strings, Brass, Woodwinds,
Percussion, Synth, FX/Other
```

### Extraction Workflow

1. Click **More Actions (...)** on any clip
2. Hover over **Get Stems**
3. Choose your split mode — **Auto Split** (all 12), **Split from Mix** (one target + the rest), or **Advanced Split** (one instrument from ~100)
4. Import into DAW

### Cleaner Single-Stem Pulls

For an isolated vocal or instrument, **Split from Mix** targeting that part is usually cleaner in one pass than the old carve-and-repeat trick. If a stem still bleeds — a real possibility even with the new pipeline, see § Stem Extraction above — run extraction again on the extracted stem.

> **Tier note:** Advanced Split is Premier-tier with a per-extraction credit cost (exact costs vary — check Suno's current pricing). Auto Split / Split from Mix availability follows your plan.

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

**Reported (launch week)**: asking Studio to "regenerate section" produced garbled or invented-language vocals for two creators; generating a single instrument no longer adds extra parts (an improvement); one creator saw an imported-keys timing offset on multitrack export. Verify Studio output by ear before exporting.

### Pitch Transposition

**Access**: Remix → Suno Studio (Premier plan)

1. Click generated song on timeline
2. Locate transpose slider under clip settings
3. Adjust pitch by semitones (±12 range)
4. Preserves melody, phrasing, and rhythm

**Benefit**: Fix key mismatches without wasting credits on regeneration

---

## Known Limitations

- Heavy electric guitars can sound "dirty" or blend together
- Acoustic nuance not always captured perfectly
- Niche subgenres (metalcore, extreme styles) may miss hallmarks
- Extreme cross-style fusions → muddy results
- Quality may degrade past 6-7 minutes
- Heavy genres (metal, hardcore, blues-rock) remain the weakest; v6-wild is the better first pass, then Cover on v6.
- Prompt-level "no drums" / "monotone vocals" requests are ignored — use Exclude Styles (v6 hands-on, The Verge, Sep 2026)
- Rock/metal vocals drift toward a generic post-grunge timbre; try v6-wild, then Cover on v6, or a Custom Model

---

## Ownership, Rights & Downloads (Terms effective September 3, 2026)

- **Pro and Premier**: Suno assigns you its rights in your outputs, but **commercial use requires a permitted download on a paid plan** (Pro 20 / Premier 60 per month; Studio exports uncapped). Suno "makes no representation or warranty … that any copyright will vest in any Output", and rights holders "may also have the right to collect revenue related to distribution of Outputs on third party platforms."
- **Free**: personal, non-commercial use only; up to 7 lifetime trial downloads.
- **Remixes** of other people's songs are never commercial.
- **Watermark and fingerprint**: the watermark is embedded in the audio itself, not just metadata (reported live by users), and outputs are fingerprinted; the Terms forbid removing, altering or circumventing either. Tools advertised as "watermark removers" violate the Terms — none of this plugin's polish or mastering steps touch the watermark.
- **Distribution**: Believe/TuneCore distribute only tracks made on the current model family; check other distributors' policies.

**Action item**: download the WAV of every keeper while the monthly allowance is open — one song is one download, stems included.

---

## Quick Reference Card

**Generation Settings (Advanced Mode → More Options)** — the plugin records these per track (`templates/track.md` § Generation Settings): Model `v6` · Variety **Off** · Max Mode **On** for tracks over ~2:00, covers and Voices (20 credits) · Duration Auto unless the track sets a target · Weirdness 50 · Style Influence 50 · Vocal Gender from the vocal description. Model choice: [models.md § How to choose](models.md#how-to-choose).

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

- **`/bitwize-music:suno-engineer`** - Technical Suno prompting expert (v6 family)
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

- **`/reference/suno/models.md`** - Model catalog: v6 / v6-wild / v6-mini / Custom Models, tiers, defaults, when to use which
- **`/reference/suno/creative-sliders.md`** - Weirdness / Style Influence / Audio Influence deep dive: genre starting ranges, interaction effects, slider-vs-prompt
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
- [Suno v5.5: More Expressive. More You. — Suno Blog](https://suno.com/blog/v5-5)
- [Suno v5.5 Guide: Voices, Custom Models & My Taste — Hookgenius](https://hookgenius.app/learn/suno-v5-5-guide/)
- [Suno v5.5 — What's New and How to Clean Tracks (TrackWasher)](https://www.trackwasher.com/suno-v5-5)
- [Suno v5.5: What is new and How to Use it Via API & Studio — CometAPI](https://www.cometapi.com/suno-v5-5-what-is-new-and-how-to-use-it-via-api--studio/)
- [Suno Launches Version 5.5 With New 'Voices' Feature — Digital Music News](https://www.digitalmusicnews.com/2026/03/26/suno-launches-version-5-5/)
- [Introducing v6 — Suno Blog](https://suno.com/blog/introducing-v6) (Sep 9, 2026)
- [v6 FAQ — Suno Help](https://help.suno.com/en/articles/13924481) (Variety, Max Mode, credits, custom-model upgrade)
- [What's new in v6? — Suno Help](https://help.suno.com/en/articles/13924801)
- [Suno v6 Is Here: Everything You Need to Know — Suno (YouTube)](https://youtu.be/_lHvWn2SNC4)
- [Suno v6: How to Transition Your Workflow — Suno (YouTube)](https://youtu.be/tkKGNBzkHwE)
- [Suno v6 Guide: What Actually Changed (Tested Day One) — HookGenius](https://hookgenius.app/learn/suno-v6-guide/)
- [Suno releases its first AI music model made with record industry help — The Verge](https://www.theverge.com/ai-artificial-intelligence/991977/suno-releases-its-first-ai-music-model-made-with-record-industry-help)
