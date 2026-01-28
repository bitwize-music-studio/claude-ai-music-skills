# Genre-Specific Mastering Presets

Quick reference for choosing the right mastering settings by genre.

---

## How Genre Presets Work

The `--genre` flag applies:
1. **Target LUFS** - Genre-appropriate loudness
2. **High-mid EQ cut** - Reduces harshness at 3.5kHz
3. **High shelf cut** - Optional cut above 8kHz

```bash
python3 {plugin_root}/tools/mastering/master_tracks.py {audio_path}/ --genre rock
```

---

## Preset Reference by Category

### Pop & Mainstream

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| pop | -14 | -1.0 dB | Bright, polished, radio-ready |
| k-pop | -14 | -1.0 dB | Crisp, punchy, vocal-forward |
| hyperpop | -14 | -1.5 dB | Aggressive brightness, needs taming |

**When to use**: Commercial releases, playlists, radio submission.

**Customization**: For vintage pop, try `--cut-highmid -2` for warmth.

---

### Hip-Hop & Rap

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| hip-hop | -14 | -1.0 dB | Standard, bass-forward |
| rap | -14 | -1.0 dB | Same as hip-hop |
| trap | -14 | -1.0 dB | Keep hi-hat brightness |
| drill | -14 | -1.5 dB | Dark, aggressive |
| phonk | -14 | -1.5 dB | Lo-fi aesthetic, warmer |
| grime | -14 | -1.0 dB | UK sound, punchy |
| nerdcore | -14 | -1.0 dB | Clear vocals, nerdy themes |

**When to use**: Any hip-hop subgenre.

**Customization**: For boom-bap, use `--cut-highmid -2` for vintage warmth.

---

### R&B, Soul & Funk

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| rnb | -14 | -1.5 dB | Smooth, vocal clarity |
| soul | -14 | -1.5 dB | Warm, analog feel |
| funk | -14 | -1.5 dB | Punchy, groove-focused |
| disco | -14 | -1.5 dB | Bright but not harsh |
| gospel | -14 | -1.5 dB | Vocal warmth, choir clarity |

**When to use**: Smooth, vocal-driven music.

**Customization**: For neo-soul, try `--target-lufs -16` for more dynamics.

---

### Rock

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| rock | -14 | -2.0 dB | Standard rock, tame guitar harshness |
| indie-rock | -14 | -1.5 dB | Less aggressive |
| alternative | -14 | -2.0 dB | Varied, safe middle ground |
| grunge | -14 | -2.5 dB | Gritty but controlled |
| garage-rock | -14 | -2.0 dB | Raw energy |
| surf-rock | -14 | -1.5 dB | Bright twang, less cut needed |

**When to use**: Guitar-driven rock music.

**Customization**: For live recordings, use `--cut-highmid -3` to tame room harshness.

---

### Dynamic Rock (More Headroom)

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| psychedelic-rock | -16 | -1.5 dB | Preserve dynamics, trippy |
| progressive-rock | -16 | -1.5 dB | Complex, dynamic |
| post-rock | -16 | -1.5 dB | Build-ups need room |

**When to use**: Music with intentional dynamic range.

**Customization**: These genres benefit from `-16 LUFS` - don't push louder.

---

### Punk & Hardcore

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| punk | -14 | -2.0 dB | Raw but listenable |
| hardcore-punk | -14 | -2.5 dB | Aggressive, needs more cut |
| ska-punk | -14 | -2.0 dB | Brass can be harsh |
| celtic-punk | -14 | -2.0 dB | Fiddle brightness |
| emo | -14 | -2.0 dB | Emotional clarity |

**When to use**: Fast, aggressive music.

**Customization**: For lo-fi punk, use `--cut-highmid -1` to preserve rawness.

---

### Metal

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| metal | -14 | -2.5 dB | Heavy, needs harshness control |
| thrash-metal | -14 | -3.0 dB | Very aggressive |
| black-metal | -14 | -3.0 dB | Treble-heavy, needs taming |
| doom-metal | -14 | -2.5 dB | Slow, heavy |
| metalcore | -14 | -2.5 dB | Modern, punchy |
| industrial | -14 | -2.5 dB | Harsh by design |

**When to use**: Heavy, distorted music.

**Customization**: Some black metal fans prefer raw sound - use `-1.5 dB` cut.

---

### Electronic & Dance

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| electronic | -14 | -1.0 dB | General electronic |
| edm | -14 | -1.0 dB | Festival-ready |
| house | -14 | -1.0 dB | Four-on-floor |
| techno | -14 | -1.0 dB | Driving, minimal |
| trance | -14 | -1.0 dB | Euphoric builds |
| dubstep | -14 | -1.5 dB | Bass-heavy, mid-range drops |
| drum-and-bass | -14 | -1.0 dB | Fast, punchy |
| synthwave | -14 | -1.0 dB | Retro brightness |
| new-wave | -14 | -1.5 dB | 80s sound |
| dancehall | -14 | -1.0 dB | Jamaican club |

**When to use**: Club and festival music.

**Customization**: For vinyl release, use `--target-lufs -12` (vinyl is louder).

---

### Ambient & Chill

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| ambient | -16 | -1.0 dB | Quiet, atmospheric |
| lo-fi | -14 | -1.0 dB | Warm, nostalgic |
| chillwave | -14 | -1.0 dB | Dreamy, hazy |
| trip-hop | -14 | -1.5 dB | Dark, moody |
| vaporwave | -14 | -1.0 dB | Retro processing |
| shoegaze | -14 | -1.5 dB | Wall of sound |

**When to use**: Background listening, relaxation.

**Customization**: Lo-fi often sounds better with no EQ cut at all.

---

### Folk & Country

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| folk | -14 | -1.5 dB | Acoustic warmth |
| country | -14 | -2.0 dB | Twangy guitars need taming |
| americana | -14 | -1.5 dB | Roots sound |
| bluegrass | -14 | -2.0 dB | Fast picking, bright |
| indie-folk | -14 | -1.5 dB | Intimate, natural |

**When to use**: Acoustic and roots music.

**Customization**: For live/raw recordings, increase cut to `-2.5 dB`.

---

### Jazz & Blues

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| jazz | -16 | 0 dB | Preserve natural dynamics |
| blues | -14 | -1.5 dB | Warm, classic tone |
| swing | -14 | -1.0 dB | Big band brightness |
| bossa-nova | -16 | 0 dB | Gentle, intimate |

**When to use**: Dynamic, acoustic music.

**Customization**: Jazz purists prefer no EQ - use `--cut-highmid 0`.

---

### Classical & Cinematic

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| classical | -18 | 0 dB | Maximum dynamics |
| opera | -16 | 0 dB | Vocal dynamics |
| cinematic | -16 | 0 dB | Film scoring standard |

**When to use**: Orchestral, dynamic range is essential.

**Customization**: Never compress classical music - dynamics are the point.

---

### Latin & World

| Genre | LUFS | High-Mid Cut | Notes |
|-------|------|--------------|-------|
| latin | -14 | -1.0 dB | General Latin |
| afrobeats | -14 | -1.0 dB | West African pop |
| reggae | -14 | -1.5 dB | Warm, bass-heavy |

**When to use**: World music genres.

**Customization**: Reggae benefits from extra bass warmth.

---

## Choosing the Right Preset

1. **Start with the closest genre match**
2. **Listen critically** - does it sound harsh or dull?
3. **Adjust if needed**:
   - Still harsh? Increase cut: `--cut-highmid -3`
   - Too dull? Decrease cut: `--cut-highmid -1`
4. **A/B test** against commercial references

---

## When NOT to Use Presets

- **Reference mastering** - Use `reference_master.py` instead
- **Already mastered audio** - Don't double-process
- **Specific client requests** - Override with manual settings
- **Mixed-genre albums** - Master track-by-track with different presets
