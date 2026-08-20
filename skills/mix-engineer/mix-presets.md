# Mix Polish Genre Presets

Human-readable guide to what each preset does and when to override defaults.

---

## How Presets Work

Each genre preset adjusts per-stem processing settings. Settings not specified in a genre preset inherit from defaults.

**Defaults** are calibrated for typical Suno V5 output:
- Noise reduction off (0) on every stem — Suno stems are synthesized, not recorded, so there's no stationary noise floor to profile; spectral gating would strip quiet musical content instead. Enable per stem only for imported/recorded audio.
- Presence boost at 3 kHz for vocal clarity
- Mud cut around 200-300 Hz for low-mid cleanup
- Gentle compression for dynamic consistency
- Unity gain (0 dB) for each stem in the remix

**Genre presets** override specific values. For example, hip-hop boosts vocal and bass gain in the remix to push those elements forward.

**User overrides** live in `{overrides}/mix-presets.yaml` and deep-merge on top of the shipped file. Genre and stem keys are matched case-insensitively, so `Electronic:` / `Vocals:` work as well as the lowercase forms. Every polish run re-reads the file, so an edit takes effect on the next run — no server restart needed.

**Scope matters.** A value under `defaults: <stem>:` applies to every genre *unless* that genre's section sets the same key — a genre entry always wins, even when it repeats the shipped default. If a `defaults:`-scope override seems to have no effect, check whether the genre you're polishing with pins that key.

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

### AI Hiss / Noise Floor (Imported/Recorded Audio Only)
**What**: Faint background noise from a real recording chain. Suno-synthesized stems don't have this — there's no stationary noise floor to profile, so spectral gating strips quiet musical content (consonants, breath, sibilance decay) instead of noise.
**Fix**: Spectral gating noise reduction (noisereduce library) — enable per stem, only for imported/recorded audio
**Default**: 0 (off) on every stem
**Override when**: Importing a real recording with an audible noise floor — start at 0.3-0.5 and adjust from there

### Digital Clicks / Pops
**What**: Brief transient spikes from generation artifacts
**Fix**: The detector splits the stem into 10 ms windows and flags any window whose peak-to-RMS ratio exceeds `click_peak_ratio` (default **15.0**), then repairs the loudest sample in each flagged window — linear interpolation on most stems, cubic spline on drums/percussion. A genuine digital click is a single-sample discontinuity that spikes one window's crest factor; a musical transient spreads its energy across the window and stays below. Genre mastering presets can lower the ratio for dense-transient genres (e.g. electronic: 10), and `analyze_mix_issues` uses the same threshold so analysis and polish report the same events.
**Default**: On for every stem except vocals, backing_vocals, and the full-mix fallback (off there — a peak/RMS detector can't reliably tell a clean synthetic consonant from a click, and the full mix *contains* the vocals). Where it's off, polish still runs the detector and reports `clicks_detected` plus a note, so a genuine click surfaces during polish rather than at `master_album`'s post-QC hard fail.
**Override when**: Real transients are being flagged as clicks — **raise** `click_peak_ratio` above 15 (try 20-25) to make the detector *less* aggressive, since a higher ratio means a window has to be more spike-like to count. Lower it (10-12) only when genuine clicks are slipping through. Imported/recorded vocals that need click cleanup: set `click_removal: true` for that stem.

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

### Empty / Near-Silent Stems
**What**: Suno's Auto Split returns every requested stem category, including ones the track has no audio for. Those come back as a ~-55 dBFS noise floor, not digital silence.
**Fix**: A silence gate skips the whole chain for those stems — they pass through to the remix bit-identical. `analyze_mix_issues` reports them as `skipped_empty` for the same reason, so analysis and polish agree.
**Default**: `silence_gate_dbfs: -40.0` (not listed per stem in the preset file — it falls back to this constant)
**Override when**: A genuinely quiet stem is being discarded (a fade-in intro, a distant pad) — lower it per stem, e.g. `silence_gate_dbfs: -80`. Raise it to discard more. True digital silence is always skipped regardless.

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
# (noise_reduction here assumes imported/recorded vocals with a real noise
# floor — leave it at 0 for standard Suno-synthesized stems; see SKILL.md
# "Stems First")
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

- Noise reduction off (0) — same synthesized-audio rationale as per-stem processing; enable only when the full mix comes from imported/recorded audio
- Highpass at 35 Hz
- Click removal
- Mud cut at 250 Hz (-2 dB)
- Presence boost at 3 kHz (+1.5 dB)
- High tame at 7 kHz (-1.5 dB)
- Gentle compression (2:1)

**Limitation**: Can't adjust stem balance or target processing to specific elements. For best results, always import stems when available.
