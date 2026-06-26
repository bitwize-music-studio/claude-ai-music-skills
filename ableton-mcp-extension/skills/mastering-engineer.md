# Mastering Engineer Skill for Ableton

**Description**: Guides audio mastering for streaming platforms including loudness optimization, tonal balance, and final preparation for distribution.

**Use Case**: After mixing is complete and tracks are approved for release.

---

## Core Principles

### Loudness is Not Volume
- **LUFS** (Loudness Units Full Scale) measures perceived loudness
- Streaming platforms normalize to target LUFS
- Too loud = squashed dynamics, fatiguing
- Too quiet = listener turns up volume, loses impact

### Universal Target
**Master to -14 LUFS, -1.0 dBTP** = works everywhere

### Genre Informs Targets
| Genre | Target LUFS | Dynamic Range | Notes |
|-------|-------------|---------------|-------|
| Classical/Jazz | -16 to -18 LUFS | High | Preserve natural dynamics |
| Rock/Pop | -12 to -14 LUFS | Moderate | Balance punch and dynamics |
| EDM/Hip-Hop | -8 to -12 LUFS | Low | Competitive loudness |
| Ambient/Lo-Fi | -14 to -16 LUFS | Moderate-High | Preserve atmosphere |

### Platform Considerations
| Platform | Normalization | True Peak Limit | Notes |
|----------|---------------|-----------------|-------|
| Spotify | -14 LUFS | -1.0 dBTP | Loudness normalization on by default |
| Apple Music | -16 LUFS | -1.0 dBTP | Sound Check enabled |
| YouTube | -14 LUFS | -1.0 dBTP | Integrated loudness |
| Tidal | -14 LUFS | -1.0 dBTP | HiFi tier preserves dynamics |
| Bandcamp | No normalization | -1.0 dBTP | Artist-controlled |
| SoundCloud | -8 to -13 LUFS | -1.0 dBTP | Varies by content type |

---

## Mastering Chain

### Standard Processing Order
1. **EQ (Corrective)** — Surgical cuts for problem frequencies
2. **EQ (Tonal)** — Broad strokes for tonal balance
3. **Compression** — Glue compression for cohesion (1.5:1 to 2:1)
4. **Saturation** — Harmonic enhancement (subtle, 0.1-0.3 drive)
5. **Stereo Imaging** — Width control (mono below 120 Hz)
6. **Limiting** — True peak limiting to -1.0 dBTP
7. **Dither** — When reducing bit depth (24-bit → 16-bit for CD)

### Frequency Coordination with Mix Stage
- **Mix presence boost**: 3 kHz (clarity from mix stage)
- **Mastering harshness cut**: 3.5 kHz (taming at master bus)
- These don't cancel because they target different center frequencies

---

## Per-Genre Presets

### Hip-Hop/Rap
```yaml
target_lufs: -10
true_peak: -1.0
compress_ratio: 2.0
compress_attack: 30
compress_release: 100
eq_low_shelf: +1.5 @ 100Hz    # Weight
eq_high_shelf: +1.0 @ 10kHz   # Air
saturation_drive: 0.2
stereo_width: 1.1
mono_below: 120Hz
```

### Rock/Metal
```yaml
target_lufs: -12
true_peak: -1.0
compress_ratio: 2.5
compress_attack: 15
compress_release: 80
eq_low_shelf: +0.5 @ 80Hz     # Tight low end
eq_mid_cut: -1.5 @ 400Hz      # Reduce boxiness
eq_high_shelf: +1.5 @ 8kHz    # Guitar/bite
saturation_drive: 0.3
stereo_width: 1.15
mono_below: 100Hz
```

### EDM/Electronic
```yaml
target_lufs: -9
true_peak: -1.0
compress_ratio: 1.5
compress_attack: 50
compress_release: 150
eq_low_shelf: +2.0 @ 60Hz     # Sub-bass weight
eq_high_shelf: +2.0 @ 12kHz   # Sparkle
saturation_drive: 0.25
stereo_width: 1.25
mono_below: 140Hz
multiband_compress: true      # Control low-mid separately
```

### Pop
```yaml
target_lufs: -11
true_peak: -1.0
compress_ratio: 2.0
compress_attack: 25
compress_release: 100
eq_low_shelf: +1.0 @ 100Hz    # Warmth
eq_presence: +1.5 @ 3kHz      # Vocal clarity
eq_high_shelf: +1.5 @ 10kHz   # Polish
saturation_drive: 0.2
stereo_width: 1.2
mono_below: 120Hz
```

### Jazz/Acoustic
```yaml
target_lufs: -16
true_peak: -1.0
compress_ratio: 1.5
compress_attack: 40
compress_release: 120
eq_low_shelf: +0.5 @ 80Hz     # Subtle warmth
eq_high_shelf: +0.5 @ 8kHz    # Gentle air
saturation_drive: 0.1         # Minimal
stereo_width: 1.1
mono_below: 100Hz
preserve_dynamics: true
```

### Classical/Orchestral
```yaml
target_lufs: -18
true_peak: -1.0
compress_ratio: 1.2           # Very light
compress_attack: 50
compress_release: 150
eq_low_shelf: 0               # Flat
eq_high_shelf: 0              # Flat
saturation_drive: 0           # None
stereo_width: 1.0             # Preserve original image
mono_below: 80Hz
preserve_dynamics: true
no_limiting: true             # Or very gentle
```

### Ambient/Lo-Fi
```yaml
target_lufs: -15
true_peak: -1.0
compress_ratio: 1.5
compress_attack: 60
compress_release: 200
eq_low_shelf: +0.5 @ 100Hz    # Warmth
eq_high_shelf: -0.5 @ 10kHz   # Darker character
saturation_drive: 0.15        # Tape warmth
stereo_width: 1.3             # Wide atmosphere
mono_below: 100Hz
```

### Funk/Soul
```yaml
target_lufs: -12
true_peak: -1.0
compress_ratio: 2.0
compress_attack: 20
compress_release: 80
eq_low_shelf: +1.0 @ 80Hz     # Bass weight
eq_mid_boost: +1.0 @ 800Hz    # Groove pocket
eq_high_shelf: +1.5 @ 8kHz    # Horn/brass bite
saturation_drive: 0.25        # Analog warmth
stereo_width: 1.15
mono_below: 120Hz
```

### Latin/Afrobeats
```yaml
target_lufs: -10
true_peak: -1.0
compress_ratio: 2.0
compress_attack: 20
compress_release: 90
eq_low_shelf: +1.5 @ 70Hz     # Percussion weight
eq_presence: +1.5 @ 4kHz      # Percussion clarity
eq_high_shelf: +1.5 @ 10kHz   # Shimmer
saturation_drive: 0.2
stereo_width: 1.2
mono_below: 120Hz
percussion_forward: true
```

---

## Workflow

### Step 1: Pre-Flight Check
Before mastering, verify:
1. **Mixed files exist** — polished/ folder or final mixes
2. **Headroom available** — peaks around -6 dBFS ideal
3. **No clipping** — check for intersample peaks
4. If issues found: "Return to mix stage for corrections"

### Step 2: Analyze Tracks
Call analysis tool to measure:
- Integrated LUFS (current loudness)
- True peak level
- Frequency balance (spectrum analysis)
- Dynamic range (DR score)
- Stereo width

Report findings with recommendations.

### Step 3: Choose Genre Preset
Select appropriate preset based on:
- Primary genre of the track
- Reference tracks provided
- Target platform(s)
- User preferences (loud vs. dynamic)

### Step 4: Apply Mastering Chain
Execute in order:
1. Insert EQ (corrective cuts)
2. Insert EQ (tonal shaping)
3. Insert compressor (glue)
4. Insert saturator (harmonics)
5. Insert stereo imager
6. Insert limiter (ceiling -1.0 dBTP)
7. Set output gain to hit target LUFS

### Step 5: Validate
Check mastered output:
- [ ] Target LUFS achieved (±0.5)
- [ ] True peak ≤ -1.0 dBTP
- [ ] No distortion artifacts
- [ ] Frequency balance matches reference
- [ ] Dynamic range appropriate for genre

### Step 6: Export
Generate delivery files:
- **Streaming**: 24-bit/44.1kHz WAV, -14 LUFS universal
- **Platform-specific**: Adjust per platform if needed
- **Metadata**: Embed ISRC, artist, title, album info

---

## Quality Standards

### Before Delivery
- [ ] Target LUFS achieved within tolerance
- [ ] True peak compliant (-1.0 dBTP)
- [ ] No clipping or intersample peaks
- [ ] Frequency balance translates across systems
- [ ] Dynamic range appropriate for genre
- [ ] Metadata embedded correctly
- [ ] File format matches delivery requirements

---

## Common Mistakes

### Don't: Over-compress
**Wrong:** 4:1 ratio, -6 dB threshold, fast attack  
**Right:** 1.5:1 to 2:1 ratio, gentle settings, preserve transients

### Don't: Ignore Reference Tracks
**Wrong:** Master in isolation  
**Right:** A/B against commercial references in same genre

### Don't: Chase Loudness at All Costs
**Wrong:** -6 LUFS with no dynamics  
**Right:** Genre-appropriate loudness with preserved punch

### Don't: Master from Raw Files
**Wrong:** Master unpolished mixes  
**Right:** Master from polished/mixed files only

### Don't: Use Same Settings for Everything
**Wrong:** One preset for all genres  
**Right:** Adjust per genre, per track

---

## MCP Tools for Ableton Integration

| Tool | Purpose |
|------|---------|
| `ableton_get_master_bus()` | Retrieve master track chain and settings |
| `ableton_insert_effect()` | Insert mastering plugins on master bus |
| `ableton_analyze_audio()` | Measure LUFS, peaks, frequency spectrum |
| `ableton_export_master()` | Render final mastered file |
| `ableton_set_parameter()` | Adjust plugin parameters programmatically |
| `ableton_get_project_info()` | Get project sample rate, bit depth, tempo |

---

## Remember

1. **Target -14 LUFS, -1.0 dBTP** for universal streaming compatibility
2. **Genre matters** — classical needs more dynamics than EDM
3. **Reference constantly** — A/B against commercial releases
4. **Less is more** — subtle processing beats aggressive chains
5. **Validate on multiple systems** — headphones, monitors, car speakers
6. **Preserve transients** — don't squash the life out of the music
7. **Mono-compatible** — check low end in mono
8. **Your deliverable**: Delivery-ready files with correct metadata
