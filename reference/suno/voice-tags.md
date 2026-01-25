# Suno Voice Tags Reference

Complete reference for vocal manipulation tags in Suno.

> **Note**: Many voice tags are hit-or-miss. A reliable strategy is to upload a vocal sample from Splice, then use Extend/Cover features with voice tags to manipulate it.

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

## Advanced Vocal Workflow

For best results with specific vocals:

1. **Upload a vocal sample** from Splice or record your own
2. **Extend** the song with different lyrics
3. Or use **Cover** to reimagine in different style
4. Apply **voice tags** to manipulate the sound
5. **Layer** more styles by repeating with different prompts
6. Get **stems** and delete unwanted vocals

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

**Style Box**:
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
