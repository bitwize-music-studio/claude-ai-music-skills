# Suno Voice Tags Reference

Complete reference for vocal manipulation tags in Suno.

> **Note**: Many voice tags are hit-or-miss. A reliable strategy is to upload a vocal sample from Splice, then use Extend/Cover features with voice tags to manipulate it. For album-wide vocal consistency, use **Personas** (see [v5-best-practices.md](v5-best-practices.md#personas)).

## V5 Voice Gender Selector

V5 has a dedicated **Voice Gender** selector in Advanced Options (male/female). This provides the most reliable gender control — more consistent than style prompt descriptions alone.

You can still control gender via style prompt ("male baritone") or Personas, but the Advanced Options selector is the baseline.

## Vocal Style Tags

Control how the singer performs each note or phrase:

| Tag | Description |
|-----|-------------|
| `Staccato` | Short, detached notes |
| `Legato` | Smooth, connected notes |
| `Vibrato-heavy` | Strong pitch oscillation |
| `Monotone` | Flat, single-pitch delivery |
| `Melismatic` | Multiple notes per syllable |
| `Syncopated` | Off-beat rhythmic emphasis |
| `Operatic` | Classical opera style |
| `Chanting` | Repetitive, ritualistic |
| `Spoken-word` | Speech-like delivery |
| `Growling` | Aggressive, guttural |
| `Belting` | Powerful, projected singing |
| `Yodeling` | Rapid pitch changes |
| `Humming` | Closed-mouth singing |
| `Rapping` | Rhythmic speech |
| `Scatting` | Jazz vocal improvisation |
| `Falsetto runs` | High-pitched runs |
| `Yelping` | Sharp, cry-like sounds |
| `Grunting` | Low, forceful sounds |
| `Call-and-response` | Interactive vocal pattern |

## Vocal Texture Tags

Control how the voice interacts with the mix:

| Tag | Description |
|-----|-------------|
| `Whispered` | Soft, breathy, intimate |
| `Gravelly` | Rough, textured |
| `Velvety` | Smooth, rich |
| `Dreamy` | Ethereal, floaty |
| `Resonant` | Full, vibrant |
| `Nasal` | Through-the-nose quality |
| `Brassy` | Bright, bold |
| `Metallic` | Hard, ringing quality |
| `Saturated` | Warm, full-bodied |
| `Smoky` | Husky, sensual |
| `Chilled` | Relaxed, cool |
| `Rough-edged` | Raw, unpolished |
| `Shimmery` | Light, sparkling |
| `Glassy` | Clear, crystalline |
| `Crunchy` | Distorted, gritty |
| `Liquid-like` | Flowing, fluid |
| `Breathy exhale` | Airy, exhaled quality |

## Regional Vocal Styles

Add geographic/cultural flavor:

- `[British rock vocal]`
- `[Southern gospel]`
- `[Nashville country]`
- `[New York hip-hop]`
- `[Jamaican dancehall]`
- `[Irish folk]`

## Voice Description Examples

Add these to your style prompt:

```
Pop, upbeat, clear and prominent vocals, 120 BPM
```

```
Rock, gravelly male vocals, powerful, emotional
```

```
R&B, sultry female singer, smooth, soulful
```

```
Hip-hop, aggressive rap delivery, hard-hitting flow
```

```
Folk, intimate whispered vocals, acoustic, gentle
```

## Vocal & Choral Genres

Genres focused on vocal performances:

- Acapella
- Barbershop
- Beatboxing
- Choir
- Christmas Carol
- Doo Wop
- Gregorian Chant
- Throat Singing
- Vocal Jazz
- Vocaloid

## Sustained Notes & Emphasis

Control vocal delivery with text formatting:

| Technique | Example | Effect |
|-----------|---------|--------|
| **Extended vowels** | `Loooove`, `Ohhhh` | Sustained notes, vocal emphasis |
| **Hyphens** | `lo-ove`, `sooo-long` | Extended vowels with syllable guidance |
| **ALL CAPS** | `NEVER AGAIN` | Shouting/screaming effect |

**Note**: ALL CAPS can be unpredictable — test with a short generation first.

## Emotion Arc Mapping

V5 supports mapping different emotional qualities to different sections:

```
Vocal: female alto, breathy, intimate, close-mic.
Performance: whispered verse with micro-pauses at line ends, minimal vibrato;
chorus slightly wider and warmer with gentle vibrato on sustained notes;
bridge raw and exposed, single-take feel.
```

This lets you create an **emotional arc** across the song rather than a flat vocal performance throughout.

## Advanced Vocal Workflow

For best results with specific vocals:

1. **Use Personas** (Pro/Premier) for the most consistent vocal identity across tracks
2. **Upload a vocal sample** from Splice or record your own
3. **Extend** the song with different lyrics
4. Or use **Cover** to reimagine in different style
5. Apply **voice tags** to manipulate the sound
6. **Layer** more styles by repeating with different prompts
7. Get **stems** and delete unwanted vocals

## Combining Tags

Mix texture + style + regional for unique results:

```
Gravelly, belting, Southern rock vocal
```

```
Whispered, dreamy, British indie vocal
```

```
Nasal, rapping, New York hip-hop flow
```

---

## Non-Human Character Voices

Creating alien, robot, or creature voices requires **overloading the style prompt** with descriptive adjectives.

### Don't Just Name the Character

❌ **Bad**: "goblin voice"
✅ **Good**: "raspy, guttural, high-pitched, cackling, snarling goblin voice"

### Robot/Synthetic Voices

**Style Prompt**:
```
metallic, autotuned, monotone, robotic, synthetic voice
```

Add modifiers:
- `glitchy` - Digital artifacts
- `vocoded` - Heavy vocoder effect
- `bitcrushed` - Lo-fi digital degradation

### Creature Voices

**Goblin**:
```
raspy, guttural, high-pitched, cackling, snarling, menacing
```

**Demon**:
```
deep, growling, distorted, rumbling, ominous, demonic
```

**Alien**:
```
ethereal, otherworldly, modulated, echoing, strange harmonics
```

### Technique

1. **List 5-8 descriptive adjectives** in style box
2. **Combine with genre** for context (e.g., "industrial metal, robotic voice")
3. **Test and iterate** - results vary by character type

**Why It Works**: Overloading adjectives overrides Suno's default human voice training, forcing the model to degrade/modify the voice in the described ways.
