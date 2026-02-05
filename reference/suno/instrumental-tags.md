# Suno Instrumental Tags Reference

Guide to creating instrumental sections and customizing instruments in Suno.

## Creating Instrumentals

### Switch to Custom Mode

**Important**: Use Custom Mode for instrumentals. Simple 1-prompt mode is unreliable.

1. Choose **Custom Mode** on Create page
2. Set **Instrumental: On** or leave lyrics blank
3. Define genre/style in the Style prompt

## Instrumental Section Tags

Use these like `[Verse]` and `[Chorus]` but without lyrics:

```
[Instrumental]
[Instrumental Break]
[Guitar Solo]
[Piano Solo]
[Drum Solo]
[Bass Solo]
[Synth Solo]
[Saxophone Solo]
[Violin Solo]
[melodic interlude]
[Guitar Solo Interlude]
```

### Genre-Specific Instrumental Tags

```
[Dubstep Bass Drop]
[Bluegrass Fiddle Break]
[Jazz Piano Solo]
[Metal Guitar Shred]
[EDM Build-up]
[Funk Bass Groove]
[Blues Harmonica Solo]
```

## Forcing Instrumental Sounds

### Using Punctuation

Use non-singable text to create instrumental sounds:

```
[Jazzy Trumpet Break]
. .! .. .! !! … ! ! !
```

### Using Onomatopoeia

Sometimes triggers instruments (may be sung as lyrics):

```
[wailing electric guitar]
wah-Wah-WAH-SCREECH
```

```
[funky slap bass]
bowm-bowm-b-b-bowm-bowm
```

```
[drum fill]
ba-da-da-da-CRASH
```

## Genre-Specific Instruments

Match instruments to genre in your Style prompt:

### EDM/Electronic
```
pulsing bassline, synth leads, 808 drums, arpeggiated synths,
sidechained bass, white noise sweeps, pitch-rising synth
```

### House
```
four-on-the-floor beat, deep house bassline, house piano riff,
atmospheric pads, uplifting synth chords, subtle arpeggiator
```

### Rock
```
distorted guitar, power chords, driving drums, bass guitar,
guitar riff, wah pedal, guitar feedback
```

### Jazz
```
walking bass, jazz piano, brushed drums, saxophone,
trumpet, upright bass, jazz guitar, vibraphone
```

### Hip-Hop
```
808 bass, trap hi-hats, boom bap drums, sampled loops,
vinyl scratches, sub bass, crispy snares
```

### Folk/Acoustic
```
acoustic guitar, fingerpicking, banjo, mandolin, violin,
fiddle, harmonica, upright bass, stomps and claps
```

### Orchestral
```
strings, brass section, woodwinds, timpani, harp,
orchestral swells, pizzicato strings, French horn
```

## Instrumental Prompt Examples

### EDM Track
```
Style: High-energy EDM track, pulsing kick drum, electrifying synth leads, powerful bassline

[Intro]
[Build-up]
[Drop]
[Breakdown]
[Build-up]
[Drop]
[Outro]
```

### House Track
```
Style: Energetic house track, four-on-the-floor beat, pulsing bassline, uplifting synth chords

[Intro]
[Main groove]
[Breakdown with atmospheric pads]
[Build]
[Drop]
[Outro]
```

### Jazz Instrumental
```
Style: Smooth jazz, piano trio, walking bass, brushed drums

[Head - main melody]
[Piano Solo]
[Bass Solo]
[Trading fours]
[Head out]
```

## Breaks and Drops

### Break Tags
```
[Break]              - Silence for lead, accompaniment plays
[Percussion Break]   - Drums only
[Bass Drop]          - Heavy bass emphasis
[Breakdown]          - Stripped-down section
```

### Build-up Tags
```
[Build-up]
[Build]
[Rising tension]
```

### Drop Examples
```
EDM build-up, increasing tension, white noise sweep, pitch-rising synth
```

```
[Build-up]
[Bass Drop]
```

## The Producer's Prompt Approach

V5 responds better to **narrative-style descriptions** than flat tag lists. Describe the arrangement like you're talking to a session musician:

```
❌ Tag soup (V3/V4 style):
[Genre: Southern Rock], [Tempo: 110 BPM], [Instrumentation: Slide Guitar, Heavy Drums]

✅ Producer's Prompt (V5 style):
Start with a lonely, overdriven slide guitar intro.
Build into a heavy, stomping drum groove for the verse.
```

**Why**: V5 understands context and fills in gaps intelligently. Flat tag lists cause "prompt fatigue" — the model dilutes attention across too many directives.

### Arrangement Strategies

| Pattern | Technique |
|---------|-----------|
| **Live band sim** | Tag rhythm guitar, lead guitar, bass, drums separately |
| **EDM drops** | Pad build → drop to drums + bass → full stack return |
| **Branding** | Keep 1–2 signature instruments across album tracks for sonic consistency |

---

## Tips

1. **One tag at a time** works best for instrumental sections
2. **Comma-separated combinations** can work but are less predictable
3. **Match instruments to genre** in Style prompt
4. **Use descriptive tags** like `[melodic interlude]` vs just `[Interlude]`
5. **Genre context matters** — a fiddle works better in Country than Hip-Hop (unless that's what you want!)
6. **Avoid tag soup** — V5 gets "prompt fatigue" with too many bracket tags. Keep it to 2–3 instrument cues per section
7. **Punctuation lines can trigger solos**: `!!! --- !!!` between section tags sometimes forces instrumental solos
