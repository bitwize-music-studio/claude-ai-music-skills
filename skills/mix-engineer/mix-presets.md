# Mix Polish Genre Presets

Human-readable guide to what each preset does and when to override defaults.

---

## How Presets Work

Each genre preset adjusts per-stem processing settings. Settings not specified in a genre preset inherit from defaults.

**Defaults** are calibrated for typical Suno V5 output:
- Moderate noise reduction on vocals (0.5)
- Presence boost at 3 kHz for vocal clarity
- Mud cut around 200-300 Hz for low-mid cleanup
- Gentle compression for dynamic consistency
- Unity gain (0 dB) for each stem in the remix

**Genre presets** override specific values. For example, hip-hop boosts vocal and bass gain in the remix to push those elements forward.

---

## Stem Gain (Remix Balance)

Each preset can adjust per-stem gain to change the mix balance:

| Genre Family | Vocals | Drums | Bass | Guitar | Keyboard | Strings | Brass | Woodwinds | Percussion | Synth | Other |
|-------------|--------|-------|------|--------|----------|---------|-------|-----------|------------|-------|-------|
| Default | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB |
| Hip-Hop/Rap | +1 dB | +0.5 dB | +1 dB | 0 dB | 0 dB | -0.5 dB | -0.5 dB | 0 dB | +0.5 dB | -0.5 dB | 0 dB |
| Rock/Metal | 0 dB | +0.5-1 dB | 0 dB | +0.5 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | -0.5 dB | 0 dB |
| EDM/Electronic | 0 dB | +0.5-1 dB | +0.5-1 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | +0.5 dB | +0.5 dB | 0 dB |
| Folk/Country | +0.5 dB | +0.5 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB |
| Jazz/Classical | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | +0.5 dB | 0 dB | 0 dB | 0 dB |
| Funk | 0 dB | +0.5 dB | +0.5 dB | 0 dB | 0 dB | 0 dB | +0.5 dB | 0 dB | +0.5 dB | 0 dB | 0 dB |
| Latin/Afrobeats | +0.5 dB | +0.5-1 dB | +0.5 dB | 0 dB | 0 dB | 0 dB | +0.5 dB | 0 dB | +1 dB | 0 dB | 0 dB |
| Ambient/Lo-Fi | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB | 0 dB |

---

## Common Suno Artifacts

These are the problems mix-engineer is designed to fix:

### AI Hiss / Noise Floor
**What**: Faint background noise, especially on vocal stems
**Fix**: Spectral gating noise reduction (noisereduce library)
**Default**: 0.5 strength on vocals, 0.3 on other instruments
**Override when**: Very clean stems (reduce to 0.1-0.2) or very noisy (increase to 0.7-0.8)

### Digital Clicks / Pops
**What**: Brief transient spikes from generation artifacts
**Fix**: Click detection (amplitude spike > 6σ) + linear interpolation
**Default**: Enabled on drums, available on all stems
**Override when**: Drums have intentional sharp transients (raise threshold to 8-10)

### Muddy Low-Mids
**What**: Excess energy in 150-400 Hz range, makes mix sound thick and undefined
**Fix**: Parametric EQ cut at specific frequency
**Default**: -3 dB at 200 Hz (bass), -2 dB at 300 Hz (other)
**Override when**: Genre needs warmth (reduce cut) or excessive mud (increase cut)

### Harsh High-Mids / Sibilance
**What**: Piercing quality in 5-8 kHz range, especially on vocal "s" sounds
**Fix**: High shelf cut
**Default**: -2 dB at 7 kHz (vocals), -1.5 dB at 8 kHz (other)
**Override when**: Vocals are naturally warm (reduce cut) or very bright (increase cut)

### Sub-Bass Rumble
**What**: Inaudible low-frequency content below 30 Hz that eats headroom
**Fix**: Butterworth highpass filter
**Default**: 30 Hz on bass stem
**Override when**: Genre needs sub-bass (lower to 20-25 Hz) or has rumble problems (raise to 40 Hz)

---

## Genre-Specific Notes

### Hip-Hop / Rap
- Vocals pushed forward (+1 dB) with stronger presence boost (+2.5 dB)
- Bass pushed forward (+1 dB) with lower highpass (25 Hz) to keep sub
- Drums slightly boosted for punch

### Rock / Metal
- More aggressive high taming on vocals (-2.5 to -3 dB) to control harshness
- Drums forward in the mix
- Guitar: saturation for warmth/crunch, heavier mud cut to avoid boxiness
- Metal: extra drum compression and guitar saturation for tight, aggressive sound
- Heavier mud cut on "other" stem (-3 to -3.5 dB) to clear room for guitars

### Electronic / EDM
- Bass and drums pushed forward
- Lower highpass on bass (25 Hz) to preserve sub-bass
- Less high taming on "other" (synths need sparkle)

### Ambient / Lo-Fi
- Lighter processing overall
- Reduced noise reduction (0.2-0.3) — some noise is character
- Reduced presence boost (+1 dB vs. default +2 dB) — warmth over clarity
- Ambient uses lower vocal compression (1.5:1) — preserve dynamics

### Folk / Country / Americana
- Vocals forward (+0.5 dB) for lyric clarity
- Guitar: stronger presence (+2 dB) for acoustic clarity, no stereo width (centered)
- Light mud cut on "other" (-1.5 dB) — preserve acoustic warmth
- Standard compression — don't squash dynamics

### Jazz / Classical
- Reduced compression across all stems — dynamics are critical
- Guitar, keyboard, brass, woodwinds: light saturation (0.1) for analog warmth
- Woodwinds: boosted presence (+1.5 dB) and gain for solo clarity
- Strings: minimal compression (1:1 bypass in classical), wide stereo
- Light mud cuts — preserve natural resonance
- Moderate vocal presence boost (+1.5 dB)

### Funk
- Guitar: saturation and tight compression (3:1) for rhythmic attack
- Keyboard: heavier saturation for clavinet/organ character
- Brass: forward in mix (+0.5 dB) with tight compression
- Percussion: boosted for groove elements

### Latin / Afrobeats
- Percussion: forward in mix (+1 dB) with tighter compression — central to genre
- Brass: forward (+0.5 dB) with boosted presence for salsa/afrobeats arrangements

---

## When to Override Defaults

Use `{overrides}/mix-presets.yaml` when:

1. **Your Suno generations consistently have a specific issue** — e.g., always too much high-mid harshness → increase `high_tame_db`
2. **You have a custom genre** not covered by built-in presets
3. **Your monitoring setup reveals issues** the defaults don't catch
4. **You prefer a specific mix balance** different from genre defaults

Override files deep-merge: you only need to specify the values you want to change.

```yaml
# Example: Custom preset for dark electronic music
genres:
  dark-electronic:
    vocals:
      noise_reduction: 0.7
      high_tame_db: -3.0
      gain_db: -0.5       # vocals slightly back
    bass:
      highpass_cutoff: 20  # keep all the sub
      gain_db: 2.0         # bass way forward
    drums:
      compress_ratio: 3.0  # tight drums
      gain_db: 1.0
```

---

## Full-Mix Fallback

When stems aren't available, mix-engineer processes the full stereo mix directly. This is less effective than per-stem processing but still valuable:

- Noise reduction (0.3 — lighter since it affects everything)
- Highpass at 35 Hz
- Click removal
- Mud cut at 250 Hz (-2 dB)
- Presence boost at 3 kHz (+1.5 dB)
- High tame at 7 kHz (-1.5 dB)
- Gentle compression (2:1)

**Limitation**: Can't adjust stem balance or target processing to specific elements. For best results, always import stems when available.
