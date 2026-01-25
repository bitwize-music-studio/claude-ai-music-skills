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

## Tips

1. **One tag at a time** works best
2. **Experiment with commas** to combine elements
3. **Match instruments to genre** in Style prompt
4. **Use descriptive tags** like `[melodic interlude]` vs just `[Interlude]`
5. **Genre context matters** - a fiddle works better in Country than Hip-Hop (unless that's what you want!)
